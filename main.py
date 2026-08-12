"""Üretim & Satış Defteri — Flet (Android/web/masaüstü uyumlu) sürüm giriş
noktası. Bu, PySide6 masaüstü sürümünün küçük bir kanıt-of-concept
versiyonu: Rol Seçimi + Üretim Kayıt Defteri + Genel Tablo (filtrelemeli).
Diğer ekranlar (Satış, Rapor, İrsaliye Arşivi, Ayarlar diyaloğu vb.) bu
kanıt onaylandıktan sonra eklenecek."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import flet as ft

from core.app_state import AppState
from core.db_core import DbCore
from core.models import PAGE_LABELS, PROFILES
from core.settings import AppSettings, load_settings, save_settings
from ui.page_defter import DefterPage
from ui.page_genel import GenelPage
from ui.profile_selector import build_profile_selector
from ui.theme import apply_theme


async def main(page: ft.Page) -> None:
    page.title = "Üretim & Satış Defteri"
    page.padding = 20

    prefs = ft.SharedPreferences()
    page.services.append(prefs)

    settings = await load_settings(prefs)
    apply_theme(page, settings.theme_mode, settings.accent_color)

    if not settings.is_configured():
        _show_first_run_settings(page, prefs, settings)
        return

    page.controls.clear()
    page.add(ft.Row([ft.ProgressRing(), ft.Text("Veritabanına bağlanılıyor...")]))
    page.update()

    try:
        db = await asyncio.to_thread(
            DbCore, url=settings.turso_database_url, auth_token=settings.turso_auth_token
        )
    except Exception as exc:  # noqa: BLE001
        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Veritabanına bağlanılamadı.", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                    ft.Text(str(exc)),
                    ft.FilledButton("Ayarları Düzenle", on_click=lambda e: _show_first_run_settings(page, prefs, settings)),
                ]
            )
        )
        page.update()
        return

    state = AppState(db)
    await asyncio.to_thread(state.load_all)

    if state.profile and state.profile in PROFILES:
        _show_main_shell(page, state, state.profile, prefs, settings)
    else:
        _show_profile_selector(page, state, prefs, settings)


def _show_profile_selector(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    def on_select(role_key: str) -> None:
        page.run_task(_select_profile, page, state, role_key, prefs, settings)

    page.controls.clear()
    page.add(build_profile_selector(on_select))
    page.update()


async def _select_profile(page: ft.Page, state: AppState, role_key: str, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    await asyncio.to_thread(state.db.save_all_data, profile=role_key)
    state.profile = role_key
    _show_main_shell(page, state, role_key, prefs, settings)


def _show_main_shell(page: ft.Page, state: AppState, role_key: str, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    info = PROFILES[role_key]
    page.controls.clear()

    saving_text = ft.Text("", color=ft.Colors.GREEN, size=12)

    def set_saving(saving: bool) -> None:
        saving_text.value = "Kaydediliyor..." if saving else ""
        if page.controls:
            saving_text.update()

    def change_profile(e) -> None:
        page.run_task(_change_profile, page, state, prefs, settings)

    # Not: yeni Flet sürümünde ft.Tab sadece başlığı temsil ediyor — içerik
    # ft.TabBarView ile eşleştiriliyor (Tabs'ın kendi kabul ettiği yapı).
    page_bodies: list[ft.Control] = []
    for page_key in info.pages:
        if page_key == "defter":
            body = DefterPage(page, state, role_key, on_saving=set_saving).control
        elif page_key == "genel":
            body = GenelPage(page, state).control
        else:
            body = ft.Container(
                ft.Text(f"{PAGE_LABELS.get(page_key, page_key)} — bu ekran henüz eklenmedi (bu kanıt-of-concept sürümde).", italic=True),
                padding=20,
            )
        page_bodies.append(body)

    tabs = ft.Tabs(
        length=len(info.pages),
        expand=True,
        content=ft.Column(
            [
                ft.TabBar(tabs=[ft.Tab(label=PAGE_LABELS.get(p, p)) for p in info.pages]),
                ft.TabBarView(controls=page_bodies, expand=True),
            ],
            expand=True,
        ),
    )

    header = ft.Row(
        [
            ft.Text("Üretim & Satış Defteri", weight=ft.FontWeight.BOLD, size=16),
            ft.Container(
                content=ft.Text(info.label, color=info.color, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.with_opacity(0.15, info.color),
                border_radius=8,
                padding=ft.Padding(10, 3, 10, 3),
            ),
            saving_text,
            ft.Container(expand=True),
            ft.OutlinedButton("Rol Değiştir", on_click=change_profile),
        ]
    )

    page.add(ft.Column([header, tabs], expand=True))
    page.update()


async def _change_profile(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    await asyncio.to_thread(state.db.save_all_data, profile="")
    state.profile = None
    _show_profile_selector(page, state, prefs, settings)


def _show_first_run_settings(page: ft.Page, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    page.controls.clear()

    url_field = ft.TextField(label="Turso Database URL *", value=settings.turso_database_url, width=420)
    token_field = ft.TextField(label="Turso Auth Token *", value=settings.turso_auth_token, password=True, can_reveal_password=True, width=420)
    gemini_field = ft.TextField(label="Gemini API Key (opsiyonel)", value=settings.gemini_api_key, password=True, can_reveal_password=True, width=420)
    error_text = ft.Text("", color=ft.Colors.RED)

    def on_save(e) -> None:
        page.run_task(_save_first_run_settings, page, prefs, settings, url_field, token_field, gemini_field, error_text)

    page.add(
        ft.Column(
            [
                ft.Text("Hoş Geldiniz", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("Devam etmeden önce veritabanı bağlantı bilgilerinizi girin."),
                url_field,
                token_field,
                gemini_field,
                error_text,
                ft.FilledButton("Kaydet ve Devam Et", on_click=on_save),
            ],
            spacing=14,
        )
    )
    page.update()


async def _save_first_run_settings(
    page: ft.Page,
    prefs: ft.SharedPreferences,
    settings: AppSettings,
    url_field: ft.TextField,
    token_field: ft.TextField,
    gemini_field: ft.TextField,
    error_text: ft.Text,
) -> None:
    url = (url_field.value or "").strip()
    token = (token_field.value or "").strip()
    if not url or not token:
        error_text.value = "Turso Database URL ve Auth Token zorunludur."
        error_text.update()
        return

    settings.turso_database_url = url
    settings.turso_auth_token = token
    settings.gemini_api_key = (gemini_field.value or "").strip()
    await save_settings(prefs, settings)
    await main(page)


if __name__ == "__main__":
    # no_cdn=True: Flet varsayılan olarak CanvasKit/skwasm/font dosyalarını
    # harici bir CDN'den (gstatic.com) çekmeye çalışıyor — bu yüzden
    # tarayıcı yükleme ekranında sonsuza kadar takılı kalıyordu (CDN'e
    # erişim yavaş/engelliyse). Bu dosyalar zaten yerel olarak da
    # paketleniyor; no_cdn=True ile tarayıcı bunları doğrudan bizim
    # sunucumuzdan alır, internet bağlantısına bağımlılık kalmaz.
    ft.run(main, no_cdn=True)
