"""Uygulama teması — Flet'in Material 3 `color_scheme_seed` özelliğiyle,
kullanıcının seçtiği TEK bir renkten otomatik olarak tam bir açık/koyu renk
paleti türetiliyor. PySide6/qt-material sürümünde elle bir XML üretmemiz
gerekiyordu; Flet'te bu yerleşik olarak geliyor.

Bu dosya sadece `color_scheme_seed` seçmekle kalmıyor — kartlar, butonlar,
tablolar, sekmeler ve diyaloglar için de tutarlı bir görsel dil (yuvarlak
köşeler, hafif gölge/elevation, daha net başlık/gövde tipografi ayrımı)
tanımlıyor. Bu ayarlar `page.theme`/`page.dark_theme` üzerinden global
olarak uygulandığı için her ekranda tekrar tekrar yazılmıyor."""

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

_CARD_RADIUS = 14
_BUTTON_RADIUS = 10
_DIALOG_RADIUS = 16


def _button_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=_BUTTON_RADIUS),
        padding=ft.Padding(18, 14, 18, 14),
        animation_duration=120,
    )


def _build_theme(accent: str) -> ft.Theme:
    """Hem açık hem koyu mod için ortak bileşen görünümü — sadece
    `color_scheme_seed` farklılaşıyor (o da Material 3'ün kendi açık/koyu
    palet üretim mantığıyla otomatik ayarlanıyor)."""
    return ft.Theme(
        color_scheme_seed=accent,
        use_material3=True,
        visual_density=ft.VisualDensity.COMFORTABLE,
        card_theme=ft.CardTheme(
            elevation=1,
            shape=ft.RoundedRectangleBorder(radius=_CARD_RADIUS),
            margin=ft.Margin(0, 0, 0, 0),
        ),
        filled_button_theme=ft.FilledButtonTheme(style=_button_style()),
        outlined_button_theme=ft.OutlinedButtonTheme(style=_button_style()),
        text_button_theme=ft.TextButtonTheme(style=_button_style()),
        dialog_theme=ft.DialogTheme(
            shape=ft.RoundedRectangleBorder(radius=_DIALOG_RADIUS),
        ),
        divider_theme=ft.DividerTheme(thickness=1, space=24),
        data_table_theme=ft.DataTableTheme(
            column_spacing=28,
            data_row_min_height=44,
            data_row_max_height=56,
            heading_row_height=44,
            divider_thickness=0.5,
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=13),
        ),
        tab_bar_theme=ft.TabBarTheme(
            label_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=13),
            unselected_label_text_style=ft.TextStyle(size=13),
        ),
    )


def apply_theme(page: ft.Page, mode: str, accent: str) -> None:
    """Sayfanın tamamına açık/koyu mod + seçilen aksan rengini uygular.
    Ayarlar ekranından her değiştirildiğinde tekrar çağrılabilir (canlı
    önizleme) — `page.update()` çağıranın sorumluluğunda."""
    page.theme_mode = _MODE_MAP.get(mode, ft.ThemeMode.DARK)
    page.theme = _build_theme(accent)
    page.dark_theme = _build_theme(accent)
