/**
 * Manhwa Çeviri — Content Script
 *
 * Sayfa üzerindeki büyük görselleri tespit eder, sağ üst köşelerine çeviri
 * butonu ekler. Buton tıklanınca görseli backend'e gönderir ve dönen
 * çevirileri şeffaf overlay olarak görselin üstüne yerleştirir.
 * Fare ile overlay'in üstüne gelindiğinde çeviri görünür olur.
 */

(() => {
  "use strict";

  // ── Ayarlar ──
  const API_BASE = "http://127.0.0.1:8899";
  const MIN_IMAGE_WIDTH = 500;   // Sadece webtoon panelleri alınsın
  const MIN_IMAGE_HEIGHT = 650;  // Ufak banner, logo vb atlansın
  const PROCESSED_ATTR = "data-manhwa-processed";
  const WRAPPER_CLASS = "manhwa-image-wrapper";

  // Eklentinin işlemeyeceği resim class/src kelimeleri
  const IGNORE_KEYWORDS = ["logo", "banner", "thumb", "avatar", "icon", "promo", "ad-", "ads", "sponsor"];

  // İçindeki görsellerin es geçileceği parent HTML etiketleri 
  const IGNORE_PARENTS = ["HEADER", "FOOTER", "NAV", "ASIDE"];

  // Kullanıcının seçtiği dil (popup'tan değiştirilebilir)
  let targetLang = "tr";

  // Doğrudan yazı modu (kalıcı overlay vs hover)
  let directOverlayMode = false;

  // Storage'dan doğrudan yazı modunu oku
  try {
    chrome.storage.local.get("directOverlay", (data) => {
      directOverlayMode = !!data.directOverlay;
    });
  } catch {}

  // ── SVG İkonlar ──
  const TRANSLATE_SVG = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zm5.63-3.07h-2L12 22h2l1.12-3H20l1.12 3h2l-4.5-10zm-2.62 5l1.62-4.33L19.12 17h-3.24z"/>
  </svg>`;

  const LOADING_SVG = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
  </svg>`;

  // ── Yardımcı Fonksiyonlar ──

  /**
   * Toast bildirim göster
   */
  function showToast(message, type = "info") {
    const existing = document.querySelector(".manhwa-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = `manhwa-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3500);
  }

  /**
   * Görseli blob olarak indir — Background worker üzerinden (CORS bypass)
   */
  async function fetchImageAsBlob(imgSrc) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "FETCH_IMAGE", url: imgSrc, pageUrl: window.location.href },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          if (!response || !response.ok) {
            reject(new Error(response?.error || "Görsel indirilemedi"));
            return;
          }
          // Base64 data URL'yi blob'a çevir
          fetch(response.dataUrl)
            .then((r) => r.blob())
            .then(resolve)
            .catch(reject);
        }
      );
    });
  }

  /**
   * Çeviri ikonunu oluştur
   */
  function createTranslateIcon() {
    const btn = document.createElement("div");
    btn.className = "manhwa-translate-icon";
    btn.innerHTML = TRANSLATE_SVG;
    btn.title = "Bu görseli çevir";
    return btn;
  }

  /**
   * Görseli wrapper ile sar ve çeviri butonunu ekle
   */
  function wrapImage(img) {
    if (img.getAttribute(PROCESSED_ATTR)) return null;

    // Görsel boyut kontrolü
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    if (w < MIN_IMAGE_WIDTH || h < MIN_IMAGE_HEIGHT) return null;

    // Sezgisel Filtreleme: Logo, Banner, Thumb, Avatar gibi istenmeyen öğeleri atla
    const src = (img.src || "").toLowerCase();
    const className = (img.className || "").toLowerCase();
    if (IGNORE_KEYWORDS.some((kw) => src.includes(kw) || className.includes(kw))) {
      return null;
    }

    // Sezgisel Filtreleme: Görselin üst elemanlarında Header, Footer vs varsa atla
    let parent = img.parentElement;
    while (parent) {
      if (IGNORE_PARENTS.includes(parent.tagName)) return null;
      parent = parent.parentElement;
    }

    // Wrapper oluştur
    const wrapper = document.createElement("div");
    wrapper.className = WRAPPER_CLASS;

    // Görselin mevcut styling'ini koru
    const computedStyle = getComputedStyle(img);
    wrapper.style.display = computedStyle.display === "inline" ? "inline-block" : computedStyle.display;
    wrapper.style.width = computedStyle.width;
    wrapper.style.maxWidth = "100%";

    // Görseli wrapper'a taşı
    img.parentNode.insertBefore(wrapper, img);
    wrapper.appendChild(img);

    // Çeviri butonunu ekle
    const icon = createTranslateIcon();
    wrapper.appendChild(icon);

    img.setAttribute(PROCESSED_ATTR, "true");

    // Tıklama: çeviri işlemi başlat
    icon.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleTranslate(img, icon, wrapper);
    });

    return wrapper;
  }

  /**
   * Ana çeviri işleyicisi: Görseli backend'e gönder, sonuçları overlay et
   */
  async function handleTranslate(img, icon, wrapper) {
    // Zaten yükleniyor mu?
    if (icon.classList.contains("loading")) return;

    // Daha önce çeviri yapılmışsa, overlay'leri kaldır (toggle)
    const existingOverlay = wrapper.querySelector(".manhwa-overlay-container");
    if (existingOverlay) {
      existingOverlay.remove();
      icon.classList.remove("done");
      icon.innerHTML = TRANSLATE_SVG;
      icon.title = "Bu görseli çevir";
      return;
    }

    // Loading durumuna geç
    icon.classList.add("loading");
    icon.innerHTML = LOADING_SVG;
    icon.title = "Çevriliyor...";

    try {
      // 1. Görseli blob olarak al
      const blob = await fetchImageAsBlob(img.src);

      // 2. Backend'e gönder
      const formData = new FormData();
      formData.append("image", blob, "webtoon.png");
      formData.append("target_lang", targetLang);

      const response = await fetch(`${API_BASE}/api/translate`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Sunucu hatası (${response.status})`);
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error("Backend yanıtı başarısız.");
      }

      if (data.translations.length === 0) {
        showToast("Görselde metin bulunamadı, sonrakine geçiliyor.", "info");
        icon.classList.remove("loading");
        icon.classList.add("done"); // Döngüye girmemesi için bitti olarak işaretle
        icon.innerHTML = TRANSLATE_SVG;
        icon.title = "Metin bulunamadı";
        return;
      }

      // 3. Overlay veya panel oluştur (display mode'a göre)
      if (data.display_mode === "panel") {
        createPanel(wrapper, img, data);
      } else {
        createOverlay(wrapper, img, data);
      }

      // Başarılı duruma geç
      icon.classList.remove("loading");
      icon.classList.add("done");
      icon.innerHTML = TRANSLATE_SVG;
      icon.title = `✅ ${data.translations.length} metin çevrildi [${data.ocr_engine || "?"}] (${data.processing_time_ms}ms) — Kaldırmak için tıkla`;

      showToast(
        `✅ ${data.translations.length} metin çevrildi [${data.ocr_engine || "?"}] (${data.processing_time_ms}ms)`,
        "success"
      );

    } catch (err) {
      console.error("[Manhwa Çeviri] Hata:", err);
      icon.classList.remove("loading");
      icon.classList.add("error");
      icon.innerHTML = TRANSLATE_SVG;
      icon.title = `Hata: ${err.message}`;
      showToast(`❌ Çeviri hatası: ${err.message}`, "error");

      // 3 saniye sonra error durumunu temizle
      setTimeout(() => {
        icon.classList.remove("error");
      }, 3000);
    }
  }

  /**
   * [PADDLE MODE] Çeviri verilerini görselin üstüne overlay olarak yerleştir.
   * Her çeviri kutusu, OCR'ın tespit ettiği bounding box'a göre konumlandırılır.
   */
  function createOverlay(wrapper, img, data) {
    const container = document.createElement("div");
    container.className = "manhwa-overlay-container";

    // Görselin ekranda gösterilen boyutu vs. gerçek boyutu oranı
    const displayWidth = img.clientWidth;
    const displayHeight = img.clientHeight;
    const scaleX = displayWidth / data.image_width;
    const scaleY = displayHeight / data.image_height;

    for (const t of data.translations) {
      const box = document.createElement("div");
      box.className = "manhwa-translation-box";

      // Doğrudan yazı modu aktifse sınıf ekle
      if (directOverlayMode) {
        box.classList.add("direct-mode");
      }

      // Bounding box koordinatları: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
      const allX = t.bbox.map((p) => p[0]);
      const allY = t.bbox.map((p) => p[1]);
      const minX = Math.min(...allX);
      const minY = Math.min(...allY);
      const maxX = Math.max(...allX);
      const maxY = Math.max(...allY);

      const left = minX * scaleX;
      const top = minY * scaleY;
      const width = (maxX - minX) * scaleX;
      const height = (maxY - minY) * scaleY;

      box.style.left = `${left}px`;
      box.style.top = `${top}px`;
      box.style.width = `${width}px`;
      box.style.height = `${height}px`;

      // Font boyutunu kutu yüksekliğine göre ayarla
      const fontSize = Math.max(10, Math.min(height * 0.55, width * 0.12, 22));
      
      const textEl = document.createElement("span");
      textEl.className = "manhwa-translated-text";
      textEl.textContent = t.translated_text;
      textEl.style.fontSize = `${fontSize}px`;

      box.appendChild(textEl);

      // Tooltip: orijinal metin
      box.title = `Orijinal: ${t.original_text}\nGüven: ${(t.confidence * 100).toFixed(1)}%`;

      container.appendChild(box);
    }

    wrapper.appendChild(container);
  }

  /**
   * [GLM-OCR MODE] Çevirileri kaydırılabilir panel olarak gösterir.
   * GLM-OCR bbox vermediğinden, tüm çeviriler bir listede gösterilir.
   */
  function createPanel(wrapper, img, data) {
    const panel = document.createElement("div");
    panel.className = "manhwa-overlay-container manhwa-translation-panel";

    // Başlık
    const header = document.createElement("div");
    header.className = "manhwa-panel-header";
    header.textContent = `🧠 GLM-OCR — ${data.translations.length} metin`;
    panel.appendChild(header);

    // Çeviri listesi
    const list = document.createElement("div");
    list.className = "manhwa-panel-list";

    for (const t of data.translations) {
      const item = document.createElement("div");
      item.className = "manhwa-panel-item";

      const orig = document.createElement("div");
      orig.className = "manhwa-panel-original";
      orig.textContent = t.original_text;

      const arrow = document.createElement("div");
      arrow.className = "manhwa-panel-arrow";
      arrow.textContent = "→";

      const translated = document.createElement("div");
      translated.className = "manhwa-panel-translated";
      translated.textContent = t.translated_text;

      item.appendChild(orig);
      item.appendChild(arrow);
      item.appendChild(translated);
      list.appendChild(item);
    }

    panel.appendChild(list);
    wrapper.appendChild(panel);
  }

  /**
   * Sayfadaki görselleri tara ve büyük olanları işle
   */
  function scanImages() {
    const images = document.querySelectorAll(`img:not([${PROCESSED_ATTR}])`);
    let count = 0;

    for (const img of images) {
      // Görsel yüklendiyse hemen işle, değilse yüklenince işle
      if (img.complete && img.naturalWidth > 0) {
        if (wrapImage(img)) count++;
      } else {
        img.addEventListener("load", () => wrapImage(img), { once: true });
      }
    }

    if (count > 0) {
      console.log(`[Manhwa Çeviri] ${count} yeni görsel tespit edildi.`);
    }
  }

  // ── Mesaj Dinleyicisi (popup'tan işlemler) ──
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "SET_LANG") {
      targetLang = msg.lang;
      console.log(`[Manhwa Çeviri] Hedef dil değiştirildi: ${targetLang}`);
      sendResponse({ ok: true });
    }
    else if (msg.type === "GET_LANG") {
      sendResponse({ lang: targetLang });
    }
    else if (msg.type === "SET_DIRECT_OVERLAY") {
      directOverlayMode = !!msg.enabled;
      console.log(`[Manhwa Çeviri] Doğrudan yazı modu: ${directOverlayMode}`);

      // Mevcut tüm overlay kutularını güncelle
      document.querySelectorAll(".manhwa-translation-box").forEach((box) => {
        if (directOverlayMode) {
          box.classList.add("direct-mode");
        } else {
          box.classList.remove("direct-mode");
        }
      });

      sendResponse({ ok: true });
    }
    else if (msg.type === "TRANSLATE_ALL") {
      showToast("Toplu çeviri başlatıldı! Sayfa otomatik kaydırılacak...", "info");
      
      let consecutiveEmptyChecks = 0;
      let isTranslating = false;

      // Backend'i boğmamak ve lazy-load görselleri kaçırmamak için dinamik ilerle
      const processNext = () => {
        // En üstte kalan ve henüz çevrilmemiş İLK butonu al
        const nextBtn = document.querySelector('.manhwa-translate-icon:not(.loading):not(.done)');
        
        if (nextBtn) {
          isTranslating = true;
          consecutiveEmptyChecks = 0;
          
          // Görsele kaydır (kullanıcı görsün ve site resmi yüklemiş olsun)
          nextBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
          
          // Biraz bekleyip butona tıklayalım (kaydırma efekti tamamlansın)
          setTimeout(() => {
            nextBtn.click();
            
            // Backend'in bitmesini bekle
            const checkDone = setInterval(() => {
              if (!nextBtn.classList.contains("loading")) {
                clearInterval(checkDone);
                // Çeviri tamamlanınca biraz dinlenip sıradakini ara
                setTimeout(processNext, 500);
              }
            }, 1000);
          }, 400);

        } else {
          isTranslating = false;
          // Ekranda çevrilecek ikon yoksa bölüm bitmemiş ama "Lazy Load" (henüz inmemiş resim) bekliyor olabiliriz.
          // Aşağıya doğru biraz scrol atıp resimlerin internetten inmesini zorlayalım:
          window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' });
          consecutiveEmptyChecks++;

          // Sayfanın en altına ulaşıp ulaşmadığımızı kontrol et:
          const isAtBottom = (window.innerHeight + Math.round(window.scrollY)) >= document.body.offsetHeight - 50;

          // Eğer 5 kez sürekli aşağı scroll edip hiçbir ikon bulamazsak YA DA sayfanın altına geldiysek bitir.
          if (consecutiveEmptyChecks > 5 || (isAtBottom && consecutiveEmptyChecks > 2)) {
            showToast("Bölümdeki tüm görseller çevrildi!", "success");
            return;
          }

          // Resmin inmesi ve ikonun MutationObserver tarafından eklenmesi için bekle
          setTimeout(processNext, 1200);
        }
      };

      // Döngüyü başlat
      processNext();
      sendResponse({ message: "Toplu çeviri başlatıldı" });
    }
    
    return true; // Send response asenkron olarak dönebilir
  });

  // ── Başlangıç: mevcut görselleri tara ──
  scanImages();

  // ── MutationObserver: dinamik veya lazy-load yüklenen görselleri yakala ──
  const observer = new MutationObserver((mutations) => {
    let hasNewImages = false;
    for (const m of mutations) {
      if (m.type === "childList") {
        for (const node of m.addedNodes) {
          if (node.nodeName === "IMG") hasNewImages = true;
          if (node.querySelectorAll) {
            const imgs = node.querySelectorAll("img");
            if (imgs.length > 0) hasNewImages = true;
          }
        }
      } else if (m.type === "attributes") {
        if (m.target.nodeName === "IMG") {
          // Eğer resmin src veya data-* niteliği değişirse (Lazy load durumları için)
          hasNewImages = true;
        }
      }
    }
    if (hasNewImages) {
      // Debounce: çok kısa sürede birçok görsel eklenirse veya src değişirse tek seferde tara
      clearTimeout(scanImages._debounceTimer);
      scanImages._debounceTimer = setTimeout(scanImages, 500);
    }
  });

  observer.observe(document.body, { 
    childList: true, 
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "data-url", "data-src"] 
  });

  console.log("[Manhwa Çeviri] Content script yüklendi ✅");
})();
