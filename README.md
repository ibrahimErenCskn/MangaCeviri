# 🌐 Manhwa Çeviri

<div align="center">

**Webtoon / Manhwa sayfalarındaki İngilizce metinleri yapay zeka ile otomatik olarak Türkçe'ye (veya 10+ dile) çeviren tam yığın çeviri sistemi.**

Chrome Uzantısı · Python Backend · Masaüstü Uygulaması

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Chrome Extension](https://img.shields.io/badge/Chrome_Extension-Manifest_V3-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)
![CUDA](https://img.shields.io/badge/CUDA-12.6-76B900?style=for-the-badge&logo=nvidia&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

</div>

---

## 📖 Proje Hakkında

**Manhwa Çeviri**, webtoon okurken dil bariyerini tamamen ortadan kaldırmak için geliştirilmiş uçtan uca bir çeviri sistemidir. Proje üç ana bileşenden oluşur:

1. **Chrome Uzantısı** — Herhangi bir webtoon sitesinde görsellerin üzerine çeviri butonu ekler, tek tıkla veya toplu çeviri yapar.
2. **Python Backend (FastAPI)** — OCR ile metin tespiti, yapay zeka ile bağlamsal çeviri gerçekleştirir.
3. **Masaüstü Uygulaması** — Yerel dosyalardan toplu sayfa çevirisi yapar ve çevrilmiş görselleri diske kaydeder.

---

## ✨ Özellikler

### 🔍 Çift OCR Motoru
| Motor | Açıklama | Hız | Doğruluk |
|-------|----------|-----|----------|
| **⚡ PaddleOCR** | Hafif, CPU tabanlı metin tespiti. Uzun görselleri otomatik dilimleme ile işler. | Hızlı | İyi |
| **🧠 GLM-OCR + YOLOv8** | YOLOv8 ile konuşma balonu tespiti + GLM-OCR ile balon içi metin okuma. GPU (CUDA) gerektirir. | Orta | Yüksek |

- Popup veya masaüstü uygulamasından motorlar arası **anında geçiş** yapılabilir.

### 🌍 Yapay Zeka Çeviri (Gemma 3 27B)
- **Google Gemini API** üzerinden **Gemma-3-27b-it** modeli kullanılır.
- Tüm konuşma metinleri tek seferde gönderilir: model **bağlamı** ve **konuşma akışını** koruyarak çeviri yapar.
- Ses efektleri, noktalama işaretleri ve kısa ifadeler korunur.
- Hata durumunda orijinal metin fallback olarak kullanılır (boş balon bırakmaz).

### 🖥️ Chrome Uzantısı (Manifest V3)
- Sayfa üzerindeki büyük webtoon görsellerini **otomatik tespit** eder (logo, banner, avatar gibi öğeleri akıllıca filtreler).
- Her görselin sağ üst köşesine mor **🌐 çeviri butonu** ekler.
- **Tek tık çeviri** — Buton tıklanınca görsel backend'e gönderilir, çevrilen metinler görselin üstüne overlay olarak yerleştirilir.
- **Toplu çeviri** — Popup'tan "Bölümdeki Görselleri Çevir" butonuyla sayfadaki tüm görseller sırayla çevrilir (otomatik scroll + lazy-load desteği).
- **Hover modu** — Fare ile çevirinin üstüne gelindiğinde çeviri görünür olur.
- **Doğrudan yazı modu** — Çeviri balonun üstüne kalıcı olarak yazılır (toggle ile değiştirilebilir).
- **CORS & Hotlink bypass** — `declarativeNetRequest` (DNR) ile Referer/Origin header'ları spoof'lanır; webtoons.com gibi korumalı sitelerden görsel indirilir.
- **MutationObserver** — Lazy-load ile sonradan yüklenen görseller de otomatik yakalanır.
- **10+ dil desteği** — Popup'tan hedef dil anında değiştirilebilir.

### 🖱️ Masaüstü Uygulaması (CustomTkinter)
- Yerel dosyalardan **çoklu görsel seçimi** ve küçük resim önizlemesi.
- OCR motoru ve **font seçimi** (Arial, Comic Sans MS, Impact, Georgia, Verdana, Tahoma).
- Çevrilmiş metinler görselin orijinal konuşma balonlarının üzerine **otomatik renk algılama** ile yazılır (arka plan rengine uygun metin rengi).
- **Dinamik font boyutlandırma** — Metin kutuya sığana kadar font küçültülür, kelime kaydırma uygulanır.
- İlerleme çubuğu ve durum bildirimleri ile kullanıcı dostu arayüz.
- Çıktılar seçilen klasöre `*_tr.png` olarak kaydedilir.

---

## 🏗️ Mimari

```
┌──────────────────────────────────────────────────────────────────┐
│                        KULLANICI                                 │
│                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────────┐    │
│  │  Chrome Uzantısı    │         │  Masaüstü Uygulaması    │    │
│  │  (Manifest V3)      │         │  (CustomTkinter)        │    │
│  │                     │         │                         │    │
│  │  • content.js       │         │  • desktop_app.py       │    │
│  │  • popup.html/js    │         │  • Toplu sayfa çevirisi │    │
│  │  • background.js    │         │  • Font/renk yönetimi   │    │
│  └────────┬────────────┘         └────────┬────────────────┘    │
│           │ HTTP POST                      │ HTTP POST           │
│           └──────────┬─────────────────────┘                     │
│                      ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             FastAPI Backend (port 8899)                  │    │
│  │                                                         │    │
│  │  POST /api/translate    → Görsel yükle, OCR + Çevir     │    │
│  │  GET  /api/health       → Sağlık kontrolü               │    │
│  │  GET  /api/languages    → Desteklenen diller             │    │
│  │  GET  /api/ocr-engine   → Aktif OCR motoru               │    │
│  │  POST /api/ocr-engine   → OCR motoru değiştir            │    │
│  │                                                         │    │
│  │  ┌──────────────────┐  ┌──────────────────────────┐     │    │
│  │  │  PaddleOCR (CPU) │  │  YOLOv8 + GLM-OCR (GPU) │     │    │
│  │  │  ocr_engine.py   │  │  glm_ocr_engine.py       │     │    │
│  │  └──────────────────┘  └──────────────────────────┘     │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Gemma-3-27b-it via Gemini API (translator.py)   │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📁 Proje Yapısı

```
manhwaCeviri/
├── backend/
│   ├── main.py               # FastAPI ana uygulama, endpoint'ler ve yaşam döngüsü
│   ├── config.py              # Konfigürasyon (sunucu, OCR, dil, CORS ayarları)
│   ├── ocr_engine.py          # PaddleOCR metin tespiti (dilimleme + gruplama)
│   ├── glm_ocr_engine.py      # YOLOv8 balon tespiti + GLM-OCR metin okuma
│   ├── translator.py          # Gemma-3-27b-it ile bağlamsal çeviri (Gemini API)
│   ├── requirements.txt       # Python bağımlılıkları
│   ├── debug_images/          # OCR debug görselleri (otomatik oluşur)
│   └── venv/                  # Python sanal ortamı
├── extension/
│   ├── manifest.json          # Chrome Extension Manifest V3
│   ├── content.js             # Content script (görsel tarama, overlay, toplu çeviri)
│   ├── content.css            # Stil dosyası (butonlar, overlay, toast, panel)
│   ├── background.js          # Service worker (CORS bypass, DNR, mesaj yönetimi)
│   ├── popup.html             # Popup arayüzü (premium dark UI)
│   ├── popup.js               # Popup mantığı (motor/dil/mod seçimi)
│   └── icons/                 # Extension ikonları (16, 48, 128px)
├── desktop_app.py             # Masaüstü çeviri asistanı (CustomTkinter)
├── start_backend.bat          # Backend otomatik kurulum ve başlatma
├── Masaustu_App.bat           # Masaüstü uygulaması başlatma
├── .gitignore
└── README.md
```

---

## 🔧 Gereksinimler

| Bileşen | Gereksinim |
|---------|-----------|
| **İşletim Sistemi** | Windows 10/11 |
| **Python** | 3.10+ |
| **GPU (isteğe bağlı)** | NVIDIA GPU + CUDA 12.6 (GLM-OCR modu için) |
| **Tarayıcı** | Google Chrome / Chromium tabanlı tarayıcılar |
| **İnternet** | Gemini API çağrıları için gerekli |

### Temel Python Paketleri
- `fastapi`, `uvicorn` — Web sunucusu
- `paddleocr`, `paddlepaddle` — PaddleOCR motoru
- `torch`, `transformers`, `accelerate` — GLM-OCR motoru (GPU)
- `ultralytics`, `huggingface-hub` — YOLOv8 balon tespiti
- `google-genai` — Gemini API (Gemma-3 çeviri)
- `Pillow`, `numpy`, `opencv-python-headless` — Görsel işleme
- `customtkinter` — Masaüstü uygulaması

---

## 🚀 Kurulum

### 1. Backend Kurulumu

#### Hızlı Başlangıç (Otomatik)
```bash
# Çift tıkla veya terminalde çalıştır:
start_backend.bat
```
Bu script otomatik olarak:
- Sanal ortam (`venv`) oluşturur (yoksa)
- Bağımlılıkları yükler
- Backend'i `http://127.0.0.1:8899` adresinde başlatır

#### Manuel Kurulum
```bash
cd backend

# Sanal ortam oluştur ve aktif et
python -m venv venv
venv\Scripts\activate

# Temel bağımlılıkları yükle
pip install -r requirements.txt
```

#### GPU Desteği (GLM-OCR için, isteğe bağlı)
```bash
# 1. PyTorch + CUDA 12.6
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

# 2. PaddlePaddle GPU (isteğe bağlı)
pip uninstall paddlepaddle paddlepaddle-gpu -y
pip install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# 3. Transformers (son sürüm)
pip install git+https://github.com/huggingface/transformers.git
pip install accelerate
```

#### Backend'i Başlat
```bash
python main.py
```
Backend `http://127.0.0.1:8899` adresinde çalışmaya başlar.

### 2. Chrome Uzantısı Kurulumu

1. Chrome'da `chrome://extensions/` adresine gidin
2. Sağ üstteki **Geliştirici modu** anahtarını açın
3. **Paketlenmemiş uzantı yükle** butonuna tıklayın
4. Proje içindeki `extension/` klasörünü seçin
5. Uzantı simgesi tarayıcı araç çubuğunda görünecektir 🌐

### 3. Masaüstü Uygulaması (İsteğe Bağlı)
```bash
# Backend çalışıyorken:
Masaustu_App.bat

# veya
python desktop_app.py
```

---

## 📖 Kullanım

### 🌐 Chrome Uzantısı ile Çeviri

#### Tekli Çeviri
1. `start_backend.bat` ile backend'i başlatın
2. Herhangi bir webtoon sitesine gidin (webtoons.com, mangadex.org, vb.)
3. Görsellerin sağ üst köşesinde mor **🌐** çeviri butonu görünecektir
4. Butona tıklayın → Görsel backend'e gönderilir → OCR + çeviri yapılır
5. Çeviri tamamlanınca buton yeşile döner ✅
6. **Hover modu**: Çevrilen alanların üstüne fareyi getirin → çeviri görünür
7. **Doğrudan yazı modu**: Popup'tan aktif edin → çeviriler kalıcı olarak görünür
8. Tekrar butona tıklayarak çeviriyi kaldırabilirsiniz (toggle)

#### Toplu Çeviri
1. Uzantı popup'ını açın (araç çubuğundaki 🌐 ikonuna tıklayın)
2. **"Bölümdeki Görselleri Çevir"** butonuna tıklayın
3. Sayfa otomatik olarak kayar, tüm görseller sırayla çevrilir
4. Lazy-load görseller de otomatik olarak yakalanır

### 🖱️ Masaüstü Uygulaması ile Çeviri
1. Backend'in çalıştığından emin olun
2. `Masaustu_App.bat` ile uygulamayı açın
3. **"Görselleri Seç"** butonuyla çevrilecek sayfaları seçin
4. OCR motoru ve font tercihini yapın
5. **"Seçili Tüm Sayfaları Çevir"** butonuna tıklayın
6. Çıktılar varsayılan olarak `Masaüstü/Manhwa_Ceviri_Ciktilari/` klasörüne kaydedilir

---

## ⚙️ Yapılandırma

### Desteklenen Diller

| Bayrak | Dil | Kod |
|--------|-----|-----|
| 🇹🇷 | Türkçe (varsayılan) | `tr` |
| 🇬🇧 | English | `en` |
| 🇩🇪 | Deutsch | `de` |
| 🇫🇷 | Français | `fr` |
| 🇪🇸 | Español | `es` |
| 🇯🇵 | 日本語 | `ja` |
| 🇰🇷 | 한국어 | `ko` |
| 🇨🇳 | 中文 | `zh-cn` |
| 🇸🇦 | العربية | `ar` |
| 🇷🇺 | Русский | `ru` |

### Backend Konfigürasyonu (`backend/config.py`)

```python
HOST = "127.0.0.1"          # Sunucu adresi
PORT = 8899                  # Sunucu portu
OCR_ENGINE = "paddle"        # Varsayılan OCR motoru: "paddle" veya "glm-ocr"
OCR_LANG = "en"              # Kaynak dil (PaddleOCR)
OCR_USE_GPU = False          # PaddleOCR GPU kullanımı
GLM_OCR_MODEL = "zai-org/GLM-OCR"    # GLM-OCR model adı
GLM_OCR_DEVICE = "cuda"      # GLM-OCR cihazı: "cuda" veya "cpu"
DEFAULT_TARGET_LANG = "tr"   # Varsayılan hedef dil
```

---

## 🔌 API Referansı

Backend `http://127.0.0.1:8899` adresinde çalışır:

| Endpoint | Yöntem | Açıklama |
|----------|--------|----------|
| `/api/health` | `GET` | Sağlık kontrolü |
| `/api/languages` | `GET` | Desteklenen dilleri listeler |
| `/api/ocr-engine` | `GET` | Aktif OCR motorunu döner |
| `/api/ocr-engine` | `POST` | OCR motorunu değiştirir (`engine`: `paddle` / `glm-ocr`) |
| `/api/translate` | `POST` | Görsel yükle → OCR → Çeviri → JSON sonuç |

### Çeviri İsteği (POST `/api/translate`)

**İstek:**
```
Content-Type: multipart/form-data
- image: Görsel dosyası (PNG, JPG, WEBP)
- target_lang: Hedef dil kodu (varsayılan: "tr")
```

**Yanıt:**
```json
{
  "success": true,
  "image_width": 800,
  "image_height": 1200,
  "ocr_engine": "paddle",
  "translations": [
    {
      "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
      "original_text": "Hello",
      "translated_text": "Merhaba",
      "confidence": 0.95,
      "source_lang": "auto",
      "target_lang": "tr"
    }
  ],
  "processing_time_ms": 1234
}
```

---

## 🧩 İşlem Akışı

```
Kullanıcı Tıklaması
       │
       ▼
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Görsel İndir   │────▶│  OCR Metin       │────▶│  Metinleri Grupla  │
│  (CORS bypass)  │     │  Tespiti         │     │  (Balon birleştir) │
└─────────────────┘     └──────────────────┘     └────────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Overlay / Panel│◀────│  JSON Yanıt      │◀────│  Gemma-3-27b ile   │
│  Oluştur        │     │  Hazırla         │     │  Bağlamsal Çeviri  │
└─────────────────┘     └──────────────────┘     └────────────────────┘
```

---

## ❓ Sık Sorulan Sorular

<details>
<summary><strong>Backend bağlantı hatası alıyorum</strong></summary>

- `start_backend.bat` dosyasının çalıştığından emin olun.
- Port 8899'un başka bir uygulama tarafından kullanılmadığını kontrol edin.
- Firewall/antivirüs'ün localhost bağlantısını engellemediğinden emin olun.
</details>

<details>
<summary><strong>GLM-OCR motoru çalışmıyor</strong></summary>

- NVIDIA GPU ve CUDA 12.6 sürücülerinin yüklü olduğundan emin olun.
- `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126` komutunu çalıştırın.
- VRAM yetersiz hatası alıyorsanız PaddleOCR motoruna geçin.
</details>

<details>
<summary><strong>Bazı görsellerde çeviri butonu görünmüyor</strong></summary>

- Uzantı yalnızca **500px genişlik** ve **650px yükseklik** üzerindeki görselleri işler.
- Header, footer, nav gibi alanlardaki görseller filtrelenir.
- Logo, banner, thumb gibi anahtar kelimeler içeren görseller atlanır.
</details>

<details>
<summary><strong>Çeviriler eksik veya yanlış geliyor</strong></summary>

- Gemma-3-27b-it modeli bağlamsal çeviri yapar. Az miktarda metin içeren görsellerde doğruluk düşebilir.
- Hata durumunda orijinal (İngilizce) metin gösterilir; boş balon bırakılmaz.
- OCR motorunu değiştirmeyi deneyin (PaddleOCR ↔ GLM-OCR).
</details>

---

## 🔮 Gelecek Planları

- [ ] Lokal LLM ile çeviri desteği (Qwen2.5, NLLB vb.)
- [ ] Çeviri önbelleği (aynı sayfayı tekrar çevirmeme)
- [ ] Metin stilini koruma (font, renk, gölge)
- [ ] Manga/manhwa sitesi otomatik tespiti
- [ ] Firefox eklentisi desteği
- [ ] Docker ile tek komutla kurulum

---

## 🤝 Katkıda Bulunma

1. Bu repoyu forklayın
2. Yeni bir branch oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Değişikliklerinizi commit edin (`git commit -m 'Yeni özellik eklendi'`)
4. Branch'inizi push edin (`git push origin feature/yeni-ozellik`)
5. Pull Request açın

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.

---

<div align="center">

**Manhwa Çeviri** ile keyifli okumalar! 📚🌐

*Webtoon'ları kendi dilinizde okuyun.*

</div>
