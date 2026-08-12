"""Uygulama teması — Flet'in Material 3 `color_scheme_seed` özelliğiyle,
kullanıcının seçtiği TEK bir renkten otomatik olarak tam bir açık/koyu renk
paleti türetiliyor. PySide6/qt-material sürümünde elle bir XML üretmemiz
gerekiyordu; Flet'te bu yerleşik olarak geliyor."""

from __future__ import annotations

import flet as ft

PRESET_ACCENTS: dict[str, str] = {
    "Yeşil": "#10B981",
    "Mavi": "#3B82F6",
    "Mor": "#8B5CF6",
    "Turuncu": "#F59E0B",
    "Kırmızı": "#EF4444",
    "Camgöbeği": "#06B6D4",
    "Pembe": "#EC4899",
}

DEFAULT_ACCENT = PRESET_ACCENTS["Yeşil"]
DEFAULT_MODE = "dark"

# Rol rozetleri için sabit renkler — kullanıcının seçtiği genel aksan
# renginden bağımsız, rolü her zaman aynı şekilde ayırt eder.
ROLE_COLORS = {"uretim": "#10B981", "satis": "#3B82F6", "admin": "#8B5CF6"}

_MODE_MAP = {
    "dark": ft.ThemeMode.DARK,
    "light": ft.ThemeMode.LIGHT,
    "system": ft.ThemeMode.SYSTEM,
}


def apply_theme(page: ft.Page, mode: str, accent: str) -> None:
    """Sayfanın tamamına açık/koyu mod + seçilen aksan rengini uygular.
    Ayarlar ekranından her değiştirildiğinde tekrar çağrılabilir (canlı
    önizleme) — `page.update()` çağıranın sorumluluğunda."""
    page.theme_mode = _MODE_MAP.get(mode, ft.ThemeMode.DARK)
    theme = ft.Theme(color_scheme_seed=accent, use_material3=True)
    page.theme = theme
    page.dark_theme = ft.Theme(color_scheme_seed=accent, use_material3=True)
