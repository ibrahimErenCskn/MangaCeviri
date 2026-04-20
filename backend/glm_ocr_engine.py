"""
GLM-OCR Engine — YOLOv8 & zai-org/GLM-OCR Hızlı Hibrit Çözüm.

HİBRİT YAKLAŞIM (YENİ MODEL):
  - YOLOv8 (ogkalu/comic-speech-bubble-detector-yolov8m) → Manga konuşma balonlarını ışık hızında bulur (Bounding Box).
  - GLM-OCR (zai-org/GLM-OCR)  → Bulunan konuşma balonlarının içindeki metinleri okur.
"""

import io
import os
import logging
from typing import List, Dict, Any

from PIL import Image
import numpy as np

import config

logger = logging.getLogger(__name__)

# Singleton models & processors
_glm_model = None
_glm_processor = None
_yolo_model = None

# Slicing & Debug
SLICE_HEIGHT_YOLO = 2000      # YOLO için webtoon dilimleme yüksekliği
SLICE_OVERLAP_YOLO = 300      # Dilimler arası kesişim (balon bölünürse yakalamak için)
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug_images")
os.makedirs(DEBUG_DIR, exist_ok=True)

def _get_yolo_model():
    """Lazy-init: Konuşma balonu dedektörünü HF üzerinden indirip yükler."""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model

    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    
    repo_id = "ogkalu/comic-speech-bubble-detector-yolov8m"
    filename = "comic-speech-bubble-detector.pt"
    
    print(f"[YOLO] Konuşma balonu tespit modeli indiriliyor/yükleniyor... ({repo_id})")
    
    # Model Yoksa HuggingFace'den çeker, varsa cache'den alır.
    model_path = hf_hub_download(repo_id=repo_id, filename=filename)
    
    _yolo_model = YOLO(model_path)
    # CUDA mevcutsa ultralytics modeli otomatik olarak GPU'ya alır.
    print(f"[YOLO] Bubble dedektör modeli hazır. Device: {_yolo_model.device}")
    
    return _yolo_model


def _get_glm_model():
    """Lazy-init: GLM-OCR modelini yükler."""
    global _glm_model, _glm_processor
    if _glm_model is not None:
        return _glm_model, _glm_processor

    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText

    print(f"[GLM-OCR] Metin okuma modeli yükleniyor: {config.GLM_OCR_MODEL} (device={config.GLM_OCR_DEVICE})...")

    _glm_processor = AutoProcessor.from_pretrained(config.GLM_OCR_MODEL)
    _glm_model = AutoModelForImageTextToText.from_pretrained(
        pretrained_model_name_or_path=config.GLM_OCR_MODEL,
        torch_dtype="auto",
        device_map=config.GLM_OCR_DEVICE,
    )

    print(f"[GLM-OCR] Model hazır. Device: {_glm_model.device}")
    return _glm_model, _glm_processor


def _run_glm_ocr_on_crop(model, processor, crop_image: Image.Image) -> str:
    import torch
    
    temp_path = os.path.join(DEBUG_DIR, "_glm_temp_crop.png")
    crop_image.save(temp_path)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": temp_path},
                {"type": "text", "text": "Text Recognition:"},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    inputs.pop("token_type_ids", None)

    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)

    output_text = processor.decode(
        generated_ids[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )

    text = output_text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("```")]
    return " ".join(lines)


def _is_duplicate_bbox(bbox, existing_bboxes, tolerance=30):
    """Bulunan YOLO_bbox'ın daha öncekilerle örtüşüp örtüşmediğini denetler."""
    bx = (bbox[0] + bbox[2]) / 2
    by = (bbox[1] + bbox[3]) / 2

    for e_box in existing_bboxes:
        ex = (e_box[0] + e_box[2]) / 2
        ey = (e_box[1] + e_box[3]) / 2
        if abs(bx - ex) < tolerance and abs(by - ey) < tolerance:
            return True
    return False


def detect_texts_glm(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    1. YOLOv8 ile konuşma balonu yerlerini bul (Saniyeler sürer, GPU tabanlı).
    2. Bulunan baloncuk içindeki yazıları GLM-OCR ile oku.
    """
    import torch
    import time
    t0 = time.time()
    
    print("[YOLO+GLM-OCR] Hibrit dedektör başlatıldı.")
    
    yolo_model = _get_yolo_model()
    glm_model, glm_processor = _get_glm_model()

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_w, img_h = image.size

    # YOLOv8 doğrudan tüm görselde çalıştırılır (Webtoon oranlarına uyumlu eğitilmiştir)
    results = yolo_model(image, verbose=False)
    raw_bboxes = []
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            if box.conf[0] < 0.25:
                continue
            
            # Bounding box koordinatları [x1, y1, x2, y2]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            new_box = [x1, y1, x2, y2]
            
            if not _is_duplicate_bbox(new_box, raw_bboxes):
                raw_bboxes.append(new_box)
                
    total_bboxes = len(raw_bboxes)
    print(f"[YOLO] {total_bboxes} konuşma balonu bulundu. (YOLO Süresi: {round(time.time() - t0, 2)}s)")
    
    # 2. Bounding Box'ları okutup listeye ekle
    results_list = []
    
    for i, box in enumerate(raw_bboxes):
        x1, y1, x2, y2 = box
        
        # Padding ekle (Balondaki metnin uçları kırpılmasın)
        pad = 10
        cx1 = max(0, int(x1) - pad)
        cy1 = max(0, int(y1) - pad)
        cx2 = min(img_w, int(x2) + pad)
        cy2 = min(img_h, int(y2) + pad)
        
        # Çok küçük kutuları atla
        if (cx2 - cx1) < 20 or (cy2 - cy1) < 20:
            continue
            
        crop = image.crop((cx1, cy1, cx2, cy2))
        
        try:
            glm_text = _run_glm_ocr_on_crop(glm_model, glm_processor, crop)
        except torch.cuda.OutOfMemoryError:
            print(f"[GLM-OCR] Grup {i+1}: VRAM yetersiz, CUDA belleğini temizliyor...")
            torch.cuda.empty_cache()
            glm_text = "?" 
        
        # Boş döndüyse atla
        if not glm_text or len(glm_text) < 1:
            glm_text = ""
        else:
            print(f'[GLM-OCR] Balon {i+1}/{total_bboxes} Okundu: "{glm_text}"')

        # PaddleOCR formatına uygun 4 köşe koordinatı (x, y)
        paddle_format_bbox = [
            [cx1, cy1], 
            [cx2, cy1], 
            [cx2, cy2], 
            [cx1, cy2]
        ]
        
        results_list.append({
            "bbox": paddle_format_bbox,
            "text": glm_text,
            "confidence": 0.95
        })
        
    print(f"[YOLO+GLM-OCR] Toplam İşlem Tamamlandı. (Süre: {round(time.time() - t0, 2)}s)")
    return results_list


def group_nearby_texts_glm(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    YOLOv8 zaten konuşma balonlarını bütün olarak yakaladığı için 
    metinleri ekstra gruplandırmaya ihtiyaç yoktur.
    """
    return detections
