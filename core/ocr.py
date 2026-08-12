"""shared/ocr-prompts.ts + server.ts/worker/index.ts'teki OCR çağrısının
Python karşılığı — Gemini REST API'sine düz HTTP isteği (SDK gerektirmez)."""

from __future__ import annotations

import base64
import json
import re

import requests

GEMINI_MODEL = "gemini-flash-latest"


def build_ocr_prompt(prompt_type: str | None) -> str:
    if prompt_type == "irsaliye":
        return """Bu görsel bir irsaliye, fatura veya teslim belgesidir. Lütfen görseldeki metinleri analiz et ve aşağıdaki JSON formatında Türkçe olarak dön:
{
  "irsaliyeNo": "İrsaliye / Belge numarası (bulunamazsa boş bırak)",
  "firmaAdi": "Düzenleyen veya alıcı şirket / firma adı (bulunamazsa boş)",
  "tarih": "Tarih (YYYY-MM-DD veya GG.AA.YYYY)",
  "tutar": "Varsa toplam tutar rakam olarak (bulunamazsa 0)",
  "notlar": "Notlar veya ürün kalemleri özeti",
  "metin": "Görselde okunan tüm metinlerin ham listesi"
}
Lütfen sadece saf JSON dön, markdown bloğu ekleme."""
    return """Bu görseldeki tüm okunabilir metinleri, ürün isimlerini, barkod/kod numaralarını tespit et.
Aşağıdaki JSON formatında dön:
{
  "metin": "Tüm okunan metin satırları",
  "kodlar": ["Tespit edilen sayısal veya alfanümerik kodlar veya barkodlar"],
  "urunIsimleri": ["Tespit edilen ürün adları"]
}
Lütfen sadece saf JSON dön, markdown bloğu ekleme."""


def parse_ocr_response_text(text_output: str) -> dict:
    try:
        clean_json = re.sub(r"```json|```", "", text_output).strip()
        return json.loads(clean_json)
    except (json.JSONDecodeError, TypeError):
        return {"metin": text_output, "kodlar": [], "urunIsimleri": []}


def run_ocr(image_path: str, prompt_type: str, api_key: str, timeout: int = 30) -> dict:
    """Bir görsel dosyasını okuyup Gemini'ye gönderir, ayrıştırılmış sonucu
    döner. Ağ/insan hatalarını `{"error": "..."}` şeklinde döner — çağıran
    taraf (UI) bunu kullanıcıya gösterebilir."""
    if not api_key:
        return {"error": "GEMINI_API_KEY ayarlanmamış. Ayarlar'dan ekleyin."}

    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_data = base64.b64encode(image_bytes).decode("ascii")

    prompt_text = build_ocr_prompt(prompt_type)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt_text},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_data}},
                ],
            }
        ]
    }

    try:
        resp = requests.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {"error": f"Yazı okuma isteği başarısız oldu: {exc}"}

    data = resp.json()
    try:
        text_output = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        text_output = ""

    return parse_ocr_response_text(text_output)
