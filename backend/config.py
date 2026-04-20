# --- Manhwa Çeviri Backend Konfigürasyonu ---

# Sunucu ayarları
HOST = "127.0.0.1"
PORT = 8899

# OCR Ayarları
OCR_ENGINE = "paddle"     # "paddle" veya "glm-ocr"
OCR_LANG = "en"           # Kaynak dil (PaddleOCR için)
OCR_USE_GPU = False       # PaddleOCR CPU (CUDA = PyTorch/GLM-OCR tarafında)

# GLM-OCR Ayarları
GLM_OCR_MODEL = "zai-org/GLM-OCR"
GLM_OCR_DEVICE = "cuda"   # "cuda" veya "cpu"

# Çeviri ayarları
DEFAULT_TARGET_LANG = "tr"   # Varsayılan hedef dil: Türkçe
SUPPORTED_LANGS = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "ja": "日本語",
    "ko": "한국어",
    "zh-cn": "中文",
    "ar": "العربية",
    "ru": "Русский",
}

# CORS — Chrome extension'dan gelen isteklere izin ver
CORS_ORIGINS = ["*"]
