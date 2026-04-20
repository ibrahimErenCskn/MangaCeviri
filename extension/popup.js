/**
 * Manhwa Çeviri — Popup Script
 * OCR motoru seçimi, dil seçimi, doğrudan yazı modu ve backend sağlık kontrolü.
 */

const API_BASE = "http://127.0.0.1:8899";

document.addEventListener("DOMContentLoaded", async () => {
  const langSelect = document.getElementById("lang-select");
  const engineSelect = document.getElementById("engine-select");
  const statusBar = document.getElementById("status-bar");
  const statusText = document.getElementById("status-text");
  const directOverlayToggle = document.getElementById("direct-overlay-toggle");

  // ── Mevcut dili al ──
  try {
    chrome.runtime.sendMessage({ type: "GET_CURRENT_LANG" }, (response) => {
      if (response && response.lang) {
        langSelect.value = response.lang;
      }
    });
  } catch {
    // Content script yüklenmemiş olabilir
  }

  // ── Mevcut doğrudan yazı modunu al ──
  chrome.storage.local.get("directOverlay", (data) => {
    directOverlayToggle.checked = !!data.directOverlay;
  });

  // ── Doğrudan yazı modu değişikliği ──
  directOverlayToggle.addEventListener("change", () => {
    const enabled = directOverlayToggle.checked;
    chrome.storage.local.set({ directOverlay: enabled });

    // Content script'e bildirim gönder
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "SET_DIRECT_OVERLAY", enabled });
      }
    });

    statusText.textContent = enabled ? "Doğrudan yazı modu aktif ✏️" : "Hover modu aktif 👆";
  });

  // Toggle row tıklama — label'a tıklayınca da toggle çalışsın
  document.getElementById("overlay-toggle-row").addEventListener("click", (e) => {
    if (e.target.tagName !== "INPUT") {
      directOverlayToggle.checked = !directOverlayToggle.checked;
      directOverlayToggle.dispatchEvent(new Event("change"));
    }
  });

  // ── Mevcut OCR motorunu al ──
  try {
    const res = await fetch(`${API_BASE}/api/ocr-engine`);
    if (res.ok) {
      const data = await res.json();
      engineSelect.value = data.active;
    }
  } catch {
    // Backend çevrimdışı olabilir
  }

  // ── OCR motoru değişikliği ──
  engineSelect.addEventListener("change", async () => {
    const engine = engineSelect.value;
    try {
      const formData = new FormData();
      formData.append("engine", engine);

      const res = await fetch(`${API_BASE}/api/ocr-engine`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        statusText.textContent = `Motor: ${engine === "glm-ocr" ? "🧠 GLM-OCR" : "⚡ PaddleOCR"}`;
      } else {
        statusText.textContent = "Motor değiştirilemedi!";
      }
    } catch {
      statusText.textContent = "Backend bağlantı hatası";
    }
  });

  // ── Dil değişikliği ──
  langSelect.addEventListener("change", () => {
    const lang = langSelect.value;
    chrome.runtime.sendMessage({ type: "CHANGE_LANG", lang }, (response) => {
      if (response && response.ok) {
        statusText.textContent = `Dil: ${langSelect.options[langSelect.selectedIndex].text}`;
      }
    });
  });

  // ── Backend sağlık kontrolü ──
  try {
    const response = await fetch(`${API_BASE}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(3000),
    });

    if (response.ok) {
      statusBar.classList.remove("offline");

      try {
        const engineRes = await fetch(`${API_BASE}/api/ocr-engine`);
        if (engineRes.ok) {
          const engineData = await engineRes.json();
          const engineLabel = engineData.active === "glm-ocr" ? "🧠 GLM-OCR" : "⚡ PaddleOCR";
          statusText.textContent = `Backend ✓ | ${engineLabel}`;
        } else {
          statusText.textContent = "Backend çalışıyor ✓";
        }
      } catch {
        statusText.textContent = "Backend çalışıyor ✓";
      }
    } else {
      throw new Error("Bad response");
    }
  } catch {
    statusBar.classList.add("offline");
    statusText.textContent = "Backend çevrimdışı — Sunucuyu başlatın";
  }

  // ── Tümünü Çevir Butonu ──
  const translateAllBtn = document.getElementById("translate-all-btn");
  const translateAllText = document.getElementById("translate-all-text");

  translateAllBtn.addEventListener("click", () => {
    translateAllBtn.disabled = true;
    translateAllText.textContent = "Başlatılıyor...";

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (activeTab) {
        chrome.tabs.sendMessage(activeTab.id, { type: "TRANSLATE_ALL" }, (response) => {
          setTimeout(() => {
            translateAllBtn.disabled = false;
            translateAllText.textContent = "Bölümdeki Görselleri Çevir";
            if (chrome.runtime.lastError) {
              statusText.textContent = "Sayfa yenilenmeli!";
            } else {
              statusText.textContent = response?.message || "Tüm çeviriler başlatıldı";
            }
          }, 1000);
        });
      }
    });
  });
});
