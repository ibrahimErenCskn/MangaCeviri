"""
OCR Engine — PaddleOCR ile webtoon görsellerindeki metinleri tespit eder.
Her metin kutusu için: bounding-box koordinatları + metin + güven skoru döner.

Uzun webtoon görselleri otomatik olarak parçalara bölünür ve
her parçada ayrı OCR çalıştırılır, sonuçlar birleştirilir.
"""

import io
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

import config

logger = logging.getLogger(__name__)

# Singleton OCR instance — model bir kez yüklenir
_ocr_instance: PaddleOCR | None = None

# ── Slicing ayarları ──
SLICE_HEIGHT = 3000       # Parça yüksekliği (büyük = daha az parça = daha hızlı)
SLICE_OVERLAP = 200       # Parçalar arası örtüşme (kenar metinlerini kaçırmamak için)
MAX_HEIGHT_NO_SLICE = 4000  # Bu yüksekliğin altı parçalanmaz

# ── Debug ──
SAVE_DEBUG = False        # True yaparsanız parçaları kaydeder, False = hızlı mod
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug_images")
os.makedirs(DEBUG_DIR, exist_ok=True)


def _get_ocr() -> PaddleOCR:
    """Lazy-init: PaddleOCR modelini yalnızca ilk çağrıda yükler."""
    global _ocr_instance
    if _ocr_instance is None:
        print(f"[OCR] PaddleOCR modeli yükleniyor (lang={config.OCR_LANG}, gpu={config.OCR_USE_GPU})...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=False,       # Açı tespiti kapalı = daha hızlı
            lang=config.OCR_LANG,
            use_gpu=config.OCR_USE_GPU,
            show_log=False,
        )
        print("[OCR] PaddleOCR modeli hazır.")
    return _ocr_instance


def _ocr_on_array(img_array: np.ndarray) -> List[Dict[str, Any]]:
    """Tek bir numpy array üzerinde OCR çalıştırır. Preprocessing yok = hızlı."""
    ocr = _get_ocr()
    results = ocr.ocr(img_array, cls=False)  # cls=False → açı sınıflandırma kapalı

    detections: List[Dict[str, Any]] = []

    if not results or not results[0]:
        return detections

    for line in results[0]:
        bbox = line[0]
        text = line[1][0]
        confidence = float(line[1][1])

        if confidence < 0.3:
            continue

        detections.append({
            "bbox": bbox,
            "text": text.strip(),
            "confidence": round(confidence, 4),
        })

    return detections


def _is_duplicate(det: Dict, existing: List[Dict], tolerance: float = 25.0) -> bool:
    """Örtüşen parçalardan gelen mükerrer tespitleri kontrol eder."""
    det_cx = sum(p[0] for p in det["bbox"]) / 4
    det_cy = sum(p[1] for p in det["bbox"]) / 4

    for e in existing:
        if e["text"] != det["text"]:
            continue
        e_cx = sum(p[0] for p in e["bbox"]) / 4
        e_cy = sum(p[1] for p in e["bbox"]) / 4
        if abs(det_cx - e_cx) < tolerance and abs(det_cy - e_cy) < tolerance:
            return True
    return False


def detect_texts(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Verilen görsel byte'larından metin tespiti yapar.
    Uzun görseller otomatik olarak parçalanır.
    """
    import time as _time
    t0 = _time.time()

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_width, img_height = image.size

    # Kısa görseller → doğrudan OCR
    if img_height <= MAX_HEIGHT_NO_SLICE:
        print(f"[OCR] Doğrudan OCR ({img_width}x{img_height})...")
        img_array = np.array(image)
        detections = _ocr_on_array(img_array)
        elapsed = round((_time.time() - t0) * 1000)
        print(f"[OCR] {len(detections)} metin, {elapsed}ms")
        return detections

    # ── Uzun görseller → parçala ──
    num_slices = 0
    y = 0
    all_detections: List[Dict[str, Any]] = []

    total_slices = (img_height // (SLICE_HEIGHT - SLICE_OVERLAP)) + 1
    print(f"[OCR] Uzun görsel ({img_width}x{img_height}), ~{total_slices} parça...")

    while y < img_height:
        y_end = min(y + SLICE_HEIGHT, img_height)
        slice_img = image.crop((0, y, img_width, y_end))
        slice_array = np.array(slice_img)

        num_slices += 1

        # OCR çalıştır
        slice_dets = _ocr_on_array(slice_array)

        # Koordinatları orijinal görsele göre offset'le
        for det in slice_dets:
            det["bbox"] = [[p[0], p[1] + y] for p in det["bbox"]]
            if not _is_duplicate(det, all_detections):
                all_detections.append(det)

        # Sonraki parçaya geç
        y += SLICE_HEIGHT - SLICE_OVERLAP
        if y_end >= img_height:
            break

    elapsed = round((_time.time() - t0) * 1000)
    print(f"[OCR] {num_slices} parçada {len(all_detections)} metin, {elapsed}ms")
    return all_detections


def group_nearby_texts(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Dikey olarak yakın olan metin kutularını gruplar (konuşma balonu birleştirme).
    Dinamik eşik: metin yüksekliğinin 1.2 katı.
    """
    if not detections:
        return []

    sorted_dets = sorted(detections, key=lambda d: min(p[1] for p in d["bbox"]))

    def _box_height(det):
        ys = [p[1] for p in det["bbox"]]
        return max(ys) - min(ys)

    groups: List[Dict[str, Any]] = []
    current_group = {
        "texts": [sorted_dets[0]["text"]],
        "bboxes": [sorted_dets[0]["bbox"]],
        "confidences": [sorted_dets[0]["confidence"]],
    }

    for i in range(1, len(sorted_dets)):
        prev = sorted_dets[i - 1]
        curr = sorted_dets[i]

        prev_bottom = max(p[1] for p in prev["bbox"])
        curr_top = min(p[1] for p in curr["bbox"])
        gap = abs(curr_top - prev_bottom)

        dynamic_threshold = max(30.0, 1.2 * max(_box_height(prev), _box_height(curr)))

        prev_left = min(p[0] for p in prev["bbox"])
        prev_right = max(p[0] for p in prev["bbox"])
        curr_left = min(p[0] for p in curr["bbox"])
        curr_right = max(p[0] for p in curr["bbox"])

        horizontal_overlap = not (curr_right < prev_left - 50 or curr_left > prev_right + 50)
        vertical_close = gap < dynamic_threshold

        if vertical_close and horizontal_overlap:
            current_group["texts"].append(curr["text"])
            current_group["bboxes"].append(curr["bbox"])
            current_group["confidences"].append(curr["confidence"])
        else:
            groups.append(_finalize_group(current_group))
            current_group = {
                "texts": [curr["text"]],
                "bboxes": [curr["bbox"]],
                "confidences": [curr["confidence"]],
            }

    groups.append(_finalize_group(current_group))
    return groups


def _finalize_group(group: Dict) -> Dict[str, Any]:
    """Bir grup metin kutusunu tek bir sonuç öğesine dönüştürür."""
    all_bboxes = group["bboxes"]
    all_x = [p[0] for bbox in all_bboxes for p in bbox]
    all_y = [p[1] for bbox in all_bboxes for p in bbox]

    merged_bbox = [
        [min(all_x), min(all_y)],
        [max(all_x), min(all_y)],
        [max(all_x), max(all_y)],
        [min(all_x), max(all_y)],
    ]

    return {
        "bbox": merged_bbox,
        "text": " ".join(group["texts"]),
        "confidence": round(sum(group["confidences"]) / len(group["confidences"]), 4),
    }
