/**
 * Manhwa Çeviri — Background Service Worker
 * Extension lifecycle, mesaj yönetimi ve cross-origin görsel indirme.
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Manhwa Çeviri] Extension yüklendi.");
});

let ruleCounter = 1;

/**
 * Görsel URL'sini fetch edip base64'e çevirir.
 * Background worker CORS kısıtlamalarından muaftır.
 * Ayrıca sitelerin (webtoons.com, vb.) Hotlink/Referer korumalarını aşmak için
 * DNR (declarativeNetRequest) kullanarak Referer header'ını spoof'lar.
 */
async function fetchImageAsBase64(url, pageUrl) {
  const ruleId = ruleCounter++;
  
  // Eğer referer (sayfa URL'si) biliniyorsa, ağ isteğinden hemen önce DNR kuralı ekle
  if (pageUrl && chrome.declarativeNetRequest) {
    try {
      await chrome.declarativeNetRequest.updateDynamicRules({
        addRules: [{
          id: ruleId,
          priority: 1,
          action: {
            type: "modifyHeaders",
            requestHeaders: [
              { header: "Referer", operation: "set", value: pageUrl },
              { header: "Origin", operation: "set", value: pageUrl }
            ]
          },
          condition: {
            urlFilter: url.split("?")[0].replace(/^https?:\/\//, "*"), 
            resourceTypes: ["xmlhttprequest"]
          }
        }],
        removeRuleIds: [ruleId]
      });
    } catch (e) {
      console.error("[DNR Error]", e);
    }
  }

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();

    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } finally {
    // İşlem bitince kuralı temizle
    if (pageUrl && chrome.declarativeNetRequest) {
      chrome.declarativeNetRequest.updateDynamicRules({
        removeRuleIds: [ruleId]
      }).catch(() => {});
    }
  }
}

// Mesaj dinleyicisi
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  // ── Görsel indirme (CORS bypass + Referer bypass) ──
  if (msg.type === "FETCH_IMAGE") {
    fetchImageAsBase64(msg.url, msg.pageUrl)
      .then((dataUrl) => sendResponse({ ok: true, dataUrl }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // async yanıt
  }

  // ── Dil değişikliği (popup → content script) ──
  if (msg.type === "CHANGE_LANG") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {
          type: "SET_LANG",
          lang: msg.lang,
        }, (response) => {
          sendResponse(response || { ok: false });
        });
      }
    });
    return true;
  }

  // ── Mevcut dil sorgulama ──
  if (msg.type === "GET_CURRENT_LANG") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "GET_LANG" }, (response) => {
          sendResponse(response || { lang: "tr" });
        });
      } else {
        sendResponse({ lang: "tr" });
      }
    });
    return true;
  }
});
