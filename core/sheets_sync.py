"""storage.ts'teki syncToSheets/syncAllToSheets karşılığı — Google Apps
Script webhook'una tek yönlü (fire-and-forget) POST. Web sürümü tarayıcının
`mode: 'no-cors'` kısıtı yüzünden gerçek hata kontrolü yapamıyordu; burada
gerçek bir HTTP istemcisi (requests) kullandığımız için hata durumunu daha
güvenilir şekilde bildirebiliyoruz."""

from __future__ import annotations

import requests


def sync_to_sheets(sheet_type: str, data, url: str, timeout: int = 15) -> tuple[bool, str]:
    if not url or not url.strip():
        return False, "URL boş."
    try:
        resp = requests.post(url, json={"type": sheet_type, "data": data}, timeout=timeout)
        if resp.status_code >= 400:
            return False, f"Sunucu {resp.status_code} döndü."
        return True, "OK"
    except requests.RequestException as exc:
        return False, str(exc)


def sync_all_to_sheets(records, companies, sales, url: str) -> tuple[bool, str]:
    results = [
        sync_to_sheets("records", records, url),
        sync_to_sheets("companies", companies, url),
        sync_to_sheets("sales", sales, url),
    ]
    if all(ok for ok, _ in results):
        return True, "Tüm veriler gönderildi."
    errors = "; ".join(msg for ok, msg in results if not ok)
    return False, errors
