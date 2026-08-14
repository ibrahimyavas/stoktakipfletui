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
from ui.dashboard_common import DashboardBase
from ui.dialog_barcode_mapper import BarcodeMapperDialog
from ui.dialog_waybill_vault import WaybillVaultDialog
from ui.page_dashboard_satis import SatisDashboard
from ui.page_dashboard_uretim import UretimDashboard
from ui.page_genel import GenelPage
from ui.page_rapor import RaporPage
from ui.page_satislar import SatislarPage
from ui.profile_selector import build_profile_selector
from ui.theme import apply_theme


async def _load_settings_with_retry(prefs: ft.SharedPreferences, attempts: int = 2) -> AppSettings:
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            return await load_settings(prefs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    assert last_exc is not None
    raise last_exc


async def main(page: ft.Page) -> None:
    page.title = "Üretim & Satış Defteri"
    page.padding = 20

    prefs = ft.SharedPreferences()
    page.services.append(prefs)

    try:
        settings = await _load_settings_with_retry(prefs)
    except Exception as exc:  # noqa: BLE001
        # SharedPreferences.get() içeride ~10 saniye sabit bir zaman
        # aşımına sahip (flet kütüphanesi tarafında, dışarıdan
        # değiştirilemiyor) — yavaş bir ağ/tarayıcı altında (özellikle
        # Android/zayıf bağlantı hedefi düşünülünce beklenmedik değil) bu
        # aşılabiliyordu ve önceden tüm oturum burada sessizce çöküp
        # kullanıcı kalıcı olarak boş/tepkisiz bir ekranda kalıyordu — hiç
        # geri bildirim yoktu. 2 deneme + en azından kurtarılabilir bir
        # "Tekrar Dene" ekranıyla düzeltildi.
        page.theme_mode = ft.ThemeMode.DARK
        page.controls.clear()
        page.add(
            ft.Column(
                [
                    ft.Text("Ayarlar okunamadı.", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                    ft.Text(f"Muhtemelen yavaş/kararsız bir bağlantı ({exc})."),
                    ft.FilledButton("Tekrar Dene", on_click=lambda e: page.run_task(main, page)),
                ]
            )
        )
        page.update()
        return

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

    def open_barcode_mapper(e) -> None:
        # Ürün/fiyat/başlangıç stoğu değişiklikleri Kayıt Defteri, Genel
        # Tablo ve Satışlar sekmelerindeki ürün listelerini de etkiliyor —
        # bu yüzden kaydedince en basit doğru çözüm olarak tüm kabuğu
        # (page_bodies dahil) taze state ile yeniden kuruyoruz.
        BarcodeMapperDialog(
            page, state, on_saved=lambda: _show_main_shell(page, state, role_key, prefs, settings)
        ).open()

    def open_waybill_vault(e) -> None:
        # İrsaliye ekleme/silme diğer sekmeleri etkilemiyor, dialog kendi
        # listesini zaten kendi içinde tazeliyor.
        WaybillVaultDialog(page, state, settings.gemini_api_key, on_saved=lambda: None).open()

    # Not: yeni Flet sürümünde ft.Tab sadece başlığı temsil ediyor — içerik
    # ft.TabBarView ile eşleştiriliyor (Tabs'ın kendi kabul ettiği yapı).
    page_bodies: list[ft.Control] = []
    for page_key in info.pages:
        if page_key == "defter":
            # Üretim ve Satış artık tamamen ayrı dashboard sınıfları
            # (page_dashboard_uretim.py / page_dashboard_satis.py) — birbirinin
            # alanlarını hiç görmüyor. Admin ikisine de aynı anda erişmesi
            # gerektiği için ortak taban sınıfı DashboardBase'i doğrudan, her
            # iki bayrak da açık şekilde kullanıyor.
            if role_key == "uretim":
                body = UretimDashboard(page, state, on_saving=set_saving).control
            elif role_key == "satis":
                body = SatisDashboard(page, state, on_saving=set_saving).control
            else:
                body = DashboardBase(
                    page, state, role_key, on_saving=set_saving, show_uretim_fire=True, show_satis=True
                ).control
        elif page_key == "genel":
            body = GenelPage(page, state).control
        elif page_key == "satis":
            body = SatislarPage(page, state, on_saving=set_saving).control
        elif page_key == "rapor":
            body = RaporPage(page, state).control
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
            ft.OutlinedButton("Ürün / Barkod Eşleştirme", on_click=open_barcode_mapper),
            ft.OutlinedButton("İrsaliye Arşivi", on_click=open_waybill_vault),
            ft.OutlinedButton("Rol Değiştir", on_click=change_profile),
        ],
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
    # view=WEB_BROWSER, port=8551: Varsayılan native pencere görünümü
    # (FLET_APP) bu makinede (Wayland, XWayland yok) hiç görünmüyordu —
    # süreç canlı ama ekranda pencere çıkmıyordu. Ayrıca varsayılan
    # port=0 + native görünüm birleşimi Flet'in kendi içinde her zaman
    # 8000'e sabitleniyor (flet/app.py'deki bilinen bir kısayol) — bu da
    # önceki bir çalışmadan kalma süreç hâlâ o portu tutuyorsa
    # "address already in use" hatasına yol açıyordu. Açık bir port
    # vermek bu sabitlemeyi devre dışı bırakıyor. Tarayıcıda
    # http://localhost:8551 adresini aç.
    #
    # no_cdn=True: Flet varsayılan olarak CanvasKit/skwasm/font dosyalarını
    # harici bir CDN'den (gstatic.com) çekmeye çalışıyor — bu yüzden
    # tarayıcı yükleme ekranında sonsuza kadar takılı kalıyordu (CDN'e
    # erişim yavaş/engelliyse). Bu dosyalar zaten yerel olarak da
    # paketleniyor; no_cdn=True ile tarayıcı bunları doğrudan bizim
    # sunucumuzdan alır, internet bağlantısına bağımlılık kalmaz.
    #
    # web_renderer=CANVAS_KIT: "auto" seçildiğinde (varsayılan), tarayıcı
    # WebGL + WasmGC destekliyorsa Flet daha yeni/deneysel "skwasm"
    # motorunu seçiyor — bu motorda metinler (yazı tipi glyph'leri) hiç
    # çizilmiyor, kutular/ikonlar görünüyor ama tüm yazılar görünmez
    # kalıyordu. CanvasKit'i açıkça zorlamak bunu çözüyor (ekran
    # görüntüsüyle doğrulandı).
    print("\nTarayıcıda şu adresi aç: http://localhost:8551\n")
    ft.run(
        main,
        view=ft.AppView.WEB_BROWSER,
        port=8551,
        no_cdn=True,
        web_renderer=ft.WebRenderer.CANVAS_KIT,
    )
