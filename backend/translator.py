"""
Translator — Google Gemini API (google-genai SDK) kullanarak
Gemma-3-27b-it modeli ile yüksek kaliteli bağlamsal webtoon çevirisi yapar.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

# API Key gömülü
GEMINI_API_KEY = "AIzaSyBw6FB4RJjGaUqLw2deJV8h6l_efZToyyo"
MODEL_NAME = "gemma-3-27b-it"

def _translate_batch_gemma(texts: List[str], target_lang: str) -> List[str]:
    """Senkron API çağrısı: Verilen metin dizisini Gemini API'ye gönderip json olarak alır."""
    if not texts:
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)

    # İstem oluştur: Sisteme metinlerin bir webtoon'dan geldiğini ve JSON listesi dönmesini söyle
    prompt = f"""You are an expert webtoon/manga translator.
The following input is a JSON array of texts extracted from a single comic page, ordered sequentially (top to bottom).
These texts are part of a continuous conversational flow and narrative.

CRITICAL INSTRUCTION:
1. Translate them into {target_lang}.
2. Maintain the context and conversational flow between sentences.
3. Adapt the translations to sound natural, casual, and appropriate for comic dialogues.
4. You MUST keep the EXACT SAME number of items. DO NOT merge, combine, or skip any strings.
5. Even if a string is just punctuation (like "..."), a sound effect (like "ugh", "ha"), or a single letter, you MUST include it as a separate item in the output array.
6. The length of the input array is {len(texts)}. The length of your output array MUST ALSO BE EXACTLY {len(texts)}.
7. Your output MUST be ONLY a valid raw JSON array of translated strings in the EXACT SAME ORDER. Do not include markdown formatting or extra text.

Input texts:
{json.dumps(texts, ensure_ascii=False)}
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        
        import re
        
        result_text = response.text.strip()
        
        # Regex ile sadece [ ... ] arasındaki kısmı al (Markdown veya başka metinleri yoksay)
        match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if match:
            clean_json = match.group(0)
            translated_list = json.loads(clean_json)
        else:
            raise ValueError("Cevap içerisinde geçerli bir JSON array bulunamadı.")
        
        # Güvenlik kontrolü
        if isinstance(translated_list, list) and len(translated_list) == len(texts):
            return translated_list
        else:
            logger.warning(f"Gemma yapısal hata döndü (Beklenen: {len(texts)}, Gelen: {len(translated_list)}). Fallback kullanılıyor.")
            
    except Exception as e:
        logger.error(f"Gemma 3 27B API veya Parse hatası: {e}\nGelen Ham Cevap: {response.text if 'response' in locals() and hasattr(response, 'text') else 'Yok'}")

    # Fallback (Eğer JSON parse fail olursa veya sayı tutmazsa hata mesajı bas boşluk doldur)
    return [t for t in texts] # Hata olursa boş balon yerine en azından İngilizce (orijinal) metni geri bassın ki balonlar boş kalmasın


async def translate_texts(
    detections: List[Dict[str, Any]],
    target_lang: str = None,
) -> List[Dict[str, Any]]:
    """
    OCR tespitlerindeki metinleri hedef dile çevirir.
    
    Args:
        detections: OCR'dan gelen tespit listesi (bbox + text + confidence)
        target_lang: Hedef dil kodu (varsayılan: config.DEFAULT_TARGET_LANG)

    Returns:
        Her tespit için orijinal bilgilere ek olarak 'translated' alanı içeren liste.
    """
    if target_lang is None:
        target_lang = config.DEFAULT_TARGET_LANG

    if not detections:
        return []

    texts_to_translate = [d["text"] for d in detections]
    results: List[Dict[str, Any]] = []

    try:
        # Senkron API çağrısını async loop'ta çalıştır (bloklamayı önle)
        loop = asyncio.get_event_loop()
        translations = await loop.run_in_executor(
            None,
            lambda: _translate_batch_gemma(texts_to_translate, target_lang),
        )

        for detection, translated_text in zip(detections, translations):
            results.append({
                "bbox": detection["bbox"],
                "original_text": detection["text"],
                "translated_text": translated_text,
                "confidence": detection["confidence"],
                "source_lang": "auto",
                "target_lang": target_lang,
            })

        logger.info(
            "%d metin Gemma-3-27b-it ile bağlamsal olarak başarıyla çevrildi (→ %s)",
            len(results),
            target_lang,
        )

    except Exception as e:
        logger.error("Çeviri hatası: %s", str(e))
        # Hata durumunda orijinal metinleri dön
        for detection in detections:
            results.append({
                "bbox": detection["bbox"],
                "original_text": detection["text"],
                "translated_text": f"[Çeviri hatası: {str(e)[:50]}]",
                "confidence": detection["confidence"],
                "source_lang": "?",
                "target_lang": target_lang,
            })

    return results
