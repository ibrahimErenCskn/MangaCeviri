"""
Manhwa Çeviri Backend — Ana FastAPI Uygulaması

Endpoint'ler:
  POST /api/translate   — Görsel yükle, OCR + çeviri yap, sonuçları dön
  GET  /api/health      — Sağlık kontrolü
  GET  /api/languages   — Desteklenen diller
"""

import logging
import time
import os
import io
import glob
from datetime import datetime
from contextlib import asynccontextmanager

# ⚠️ Windows'ta NVIDIA CUDA/cuDNN DLL'lerini kaydet (paddlepaddle-gpu için gerekli)
if os.name == 'nt':
    # nvidia pip paketlerinin DLL klasörlerini sisteme tanıt
    import importlib.util
    nvidia_spec = importlib.util.find_spec("nvidia")
    if nvidia_spec and nvidia_spec.submodule_search_locations:
        for nvidia_dir in nvidia_spec.submodule_search_locations:
            for dll_dir in glob.glob(os.path.join(nvidia_dir, "**", "bin"), recursive=True):
                if os.path.isdir(dll_dir):
                    os.add_dll_directory(dll_dir)
                    print(f"[INIT] DLL dizini eklendi: {dll_dir}")

# ⚠️ torch MUST be imported BEFORE paddlepaddle/paddleocr
# Both ship CUDA DLLs — torch must load first to avoid shm.dll conflict
try:
    import torch
    print(f"[INIT] PyTorch {torch.__version__} yüklendi (CUDA: {torch.cuda.is_available()})")
except ImportError:
    print("[INIT] PyTorch yüklü değil — GLM-OCR kullanılamaz")

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from ocr_engine import detect_texts as paddle_detect, group_nearby_texts as paddle_group
from glm_ocr_engine import detect_texts_glm, group_nearby_texts_glm
from translator import translate_texts
from PIL import Image as PILImage

# Aktif OCR motoru (runtime'da değiştirilebilir)
_active_engine = config.OCR_ENGINE  # "paddle" veya "glm-ocr"

# Debug klasörü oluştur
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug_images")
os.makedirs(DEBUG_DIR, exist_ok=True)

# Logging ayarı
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("manhwa-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıcında OCR modelini önceden yükle."""
    logger.info("🚀 Manhwa Çeviri Backend başlatılıyor...")
    # OCR modelini önceden yükle (ilk istek yavaş olmasın)
    # Aktif motora göre ön-yükleme
    try:
        if _active_engine == "paddle":
            from ocr_engine import _get_ocr
            _get_ocr()
            print("✅ PaddleOCR modeli hazır.")
        else:
            print("ℹ️ GLM-OCR modu seçili. Model ilk istek geldiğinde yüklenecek.")
    except Exception as e:
        print(f"⚠️ OCR modeli ön-yüklemesi başarısız: {e}")
    yield
    print("👋 Manhwa Çeviri Backend kapatılıyor.")


app = FastAPI(
    title="Manhwa Çeviri API",
    description="Webtoon görsellerindeki metinleri OCR ile tespit edip çeviren API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — Chrome extension'dan gelen isteklere izin ver
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Sağlık kontrolü."""
    return {"status": "ok", "message": "Manhwa Çeviri API çalışıyor"}


@app.get("/api/languages")
async def get_languages():
    """Desteklenen dilleri listele."""
    return {
        "default": config.DEFAULT_TARGET_LANG,
        "languages": config.SUPPORTED_LANGS,
    }


@app.get("/api/ocr-engine")
async def get_ocr_engine():
    """Aktif OCR motorunu görüntüle."""
    return {
        "active": _active_engine,
        "available": ["paddle", "glm-ocr"],
    }


@app.post("/api/ocr-engine")
async def set_ocr_engine(engine: str = Form(...)):
    """OCR motorunu değiştir. 'paddle' veya 'glm-ocr'"""
    global _active_engine
    if engine not in ("paddle", "glm-ocr"):
        raise HTTPException(status_code=400, detail=f"Geçersiz motor: {engine}. 'paddle' veya 'glm-ocr' olmalı.")
    _active_engine = engine
    print(f"🔄 OCR motoru değiştirildi: {engine}")
    return {"active": _active_engine, "message": f"OCR motoru '{engine}' olarak ayarlandı."}


@app.post("/api/translate")
async def translate_image(
    image: UploadFile = File(...),
    target_lang: str = Form(default=None),
):
    """
    Webtoon görselini al, OCR ile metinleri tespit et, çevir ve sonuçları dön.

    Request:
        - image: Görsel dosyası (PNG, JPG, WEBP)
        - target_lang: Hedef dil kodu (varsayılan: 'tr')

    Response:
        {
            "success": true,
            "image_width": 800,
            "image_height": 1200,
            "translations": [
                {
                    "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
                    "original_text": "Hello",
                    "translated_text": "Merhaba",
                    "confidence": 0.95,
                    "source_lang": "en",
                    "target_lang": "tr"
                }
            ],
            "processing_time_ms": 1234
        }
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Geçersiz dosya tipi. Görsel yükleyin.")

    start = time.time()

    try:
        # 1. Görseli oku
        image_bytes = await image.read()
        print(f"📸 Görsel alındı: {image.filename} ({len(image_bytes)} bytes)")

        # Görsel boyutlarını al
        pil_img = PILImage.open(io.BytesIO(image_bytes))
        img_width, img_height = pil_img.size

        # Görseli debug klasörüne kaydet
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        debug_path = os.path.join(DEBUG_DIR, f"{timestamp}.png")
        pil_img.save(debug_path)
        print(f"💾 Görsel kaydedildi: {debug_path}")

        # 2. OCR — metin tespiti (aktif motora göre)
        print(f"🔍 OCR Motoru: {_active_engine}")
        if _active_engine == "glm-ocr":
            detections = detect_texts_glm(image_bytes)
        else:
            detections = paddle_detect(image_bytes)

        # Tespit edilen metinleri logla
        if detections:
            print(f"\n📝 Tespit edilen metinler ({len(detections)} adet):")
            print("-" * 60)
            for i, det in enumerate(detections, 1):
                bbox_str = f"[{det['bbox'][0]}, {det['bbox'][2]}]"
                print(f"   {i}. [{det['confidence']*100:.1f}%] \"{det['text']}\"  → bbox: {bbox_str}")
            print("-" * 60)
        else:
            print("📝 Görselde hiç metin tespit edilemedi.")

        if not detections:
            elapsed = round((time.time() - start) * 1000)
            return JSONResponse(content={
                "success": True,
                "image_width": img_width,
                "image_height": img_height,
                "translations": [],
                "processing_time_ms": elapsed,
                "message": "Görselde metin tespit edilemedi.",
            })

        # 3. Yakın metinleri grupla (aktif motora göre)
        if _active_engine == "glm-ocr":
            grouped = group_nearby_texts_glm(detections)
        else:
            grouped = paddle_group(detections)

        # Gruplanmış sonuçları logla
        print(f"\n🔗 Gruplanmış metinler ({len(grouped)} grup, {len(detections)} satırdan):")
        print("=" * 60)
        for i, g in enumerate(grouped, 1):
            print(f"   {i}. [{g['confidence']*100:.1f}%] \"{g['text']}\"")
        print("=" * 60)

        # 4. Çeviri
        lang = target_lang if target_lang else config.DEFAULT_TARGET_LANG
        translations = await translate_texts(grouped, target_lang=lang)

        elapsed = round((time.time() - start) * 1000)
        print(f"✅ Çeviri tamamlandı: {len(translations)} grup, {elapsed}ms")

        return JSONResponse(content={
            "success": True,
            "image_width": img_width,
            "image_height": img_height,
            "translations": translations,
            "processing_time_ms": elapsed,
            "ocr_engine": _active_engine,
            "display_mode": "overlay",
        })

    except Exception as e:
        logger.error("❌ İşlem hatası: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"İşlem hatası: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info",
    )
