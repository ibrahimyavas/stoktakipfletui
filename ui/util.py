"""Küçük paylaşılan UI yardımcıları."""

from __future__ import annotations

import flet as ft


def is_mounted(control: ft.Control) -> bool:
    """Bir kontrolün sayfaya eklenip eklenmediğini güvenle kontrol eder.

    Flet'te henüz `page.add(...)` ile sayfaya eklenmemiş bir kontrolün
    `.page` özelliğine erişmek `RuntimeError` fırlatıyor (None dönmüyor).
    Sayfa nesnesinin kendisi (`self.page`) her zaman "doğru" olduğu için
    `if self.page:` ile korumak yeterli değil — __init__ içinde ilk veri
    yüklemesi sırasında (sayfa nesnesi var ama kontrol henüz ağaca
    eklenmemişken) `.update()` çağrısı bu RuntimeError'ı fırlatıyordu.
    Bu yardımcı, o RuntimeError'ı yakalayıp güvenli bir False'a çeviriyor."""
    try:
        return control.page is not None
    except RuntimeError:
        return False


def responsive_width(page: ft.Page | None, ideal: int, margin: int = 32, minimum: int = 240) -> int:
    """Form alanları / diyalog genişlikleri gibi sabit piksel değerlerini,
    telefon ekranı `ideal`den darsa küçültür — masaüstünde davranış birebir
    aynı kalır (idealde kalır). Bu olmadan ör. 420px'lik bir alan 393px'lik
    (Android'de yaygın) bir ekranda taşıyor, alan kısmen görünmez/tıklanamaz
    hale geliyordu — bu, gerçek bir telefon genişliğinde test edilirken
    bulundu (bkz. README)."""
    if page and page.width and page.width < ideal + margin:
        return max(minimum, int(page.width - margin))
    return ideal
