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
from core.auth import generate_remember_token
from core.db_core import DbCore
from core.models import PAGE_LABELS, PROFILES, compute_effective_access, roles_from_field
from core.settings import AppSettings, load_settings, save_settings
from ui.dashboard_common import DashboardBase
from ui.dialog_barcode_mapper import BarcodeMapperDialog
from ui.dialog_user_management import UserManagementDialog
from ui.dialog_waybill_vault import WaybillVaultDialog
from ui.page_genel import GenelPage
from ui.page_login import build_login_screen
from ui.page_rapor import RaporPage
from ui.page_satislar import SatislarPage
from ui.profile_selector import build_profile_selector
from ui.theme import apply_theme

# Üst sekme çubuğundaki her sayfa için ikon — sadece görsel, PAGE_LABELS'ın
# (core/models.py, PySide6 sürümüyle paylaşılan) yanına Flet'e özgü bir
# eşleme olarak burada tutuluyor.
PAGE_ICONS = {
    "defter": ft.Icons.EDIT_NOTE,
    "rapor": ft.Icons.INSIGHTS,
    "satis": ft.Icons.STOREFRONT,
    "genel": ft.Icons.TABLE_CHART,
}


async def _load_settings_with_retry(prefs: ft.SharedPreferences, attempts: int = 2) -> AppSettings:
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            return await load_settings(prefs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    assert last_exc is not None
    raise last_exc


def _center_screen(page: ft.Page) -> None:
    """Tek başına duran ekranları (ayarlar, giriş, rol seçimi, hata/yükleniyor
    durumları) pencere/ekran boyutu ne olursa olsun ortalar — Flet bunu
    page.horizontal_alignment/vertical_alignment ile otomatik olarak mevcut
    ekran boyutuna göre yeniden hesaplıyor, sabit bir piksel koordinatı
    vermemize gerek kalmıyor. Ana kabuk (dashboard) bunun tam tersini ister
    (tam genişlik, sol üstten başlayan düzen) — bkz. _uncenter_screen."""
    # Not: page.scroll'u burada AÇMIYORUZ — sayfa scroll edilebilir olunca
    # bir alanda autofocus (ör. giriş ekranındaki Kullanıcı Adı) Flutter'ı
    # o alanı görünüre getirmek için sayfayı sol üste kaydırıyor, bu da
    # ortalamayı bozuyordu. Ortalamak için sadece hizalama yeterli; taşma
    # olursa (çok küçük ekran) içerik kırpılmak yerine kendi bünyesindeki
    # Column'lar (ör. Kullanıcı Yönetimi listesi) zaten kendi scroll'una
    # sahip.
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER


def _uncenter_screen(page: ft.Page) -> None:
    page.horizontal_alignment = ft.CrossAxisAlignment.START
    page.vertical_alignment = ft.MainAxisAlignment.START


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
        _center_screen(page)
        page.add(
            ft.Column(
                [
                    ft.Text("Ayarlar okunamadı.", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                    ft.Text(f"Muhtemelen yavaş/kararsız bir bağlantı ({exc})."),
                    ft.FilledButton("Tekrar Dene", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(main, page)),
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
    _center_screen(page)
    page.add(ft.Row([ft.ProgressRing(), ft.Text("Veritabanına bağlanılıyor...")]))
    page.update()

    try:
        db = await asyncio.to_thread(
            DbCore, url=settings.turso_database_url, auth_token=settings.turso_auth_token
        )
    except Exception as exc:  # noqa: BLE001
        page.controls.clear()
        _center_screen(page)
        page.add(
            ft.Column(
                [
                    ft.Text("Veritabanına bağlanılamadı.", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                    ft.Text(str(exc)),
                    ft.FilledButton("Ayarları Düzenle", icon=ft.Icons.SETTINGS, on_click=lambda e: _show_first_run_settings(page, prefs, settings)),
                ]
            )
        )
        page.update()
        return

    state = AppState(db)
    await asyncio.to_thread(state.load_all)

    if state.users:
        # Hesap-tabanlı mod: admin en az bir kullanıcı tanımlamış. "Beni
        # Hatırla" ile bırakılmış geçerli bir oturum varsa (kullanıcı adı +
        # belirteç HEM bu cihazda HEM o kullanıcının DB satırında eşleşiyorsa
        # — şifre sıfırlanınca DB tarafı temizlenir, otomatik giriş iptal
        # olur) doğrudan içeri alınır; yoksa giriş ekranı gösterilir.
        remembered_user = None
        if settings.remembered_username and settings.remembered_token:
            candidate = next(
                (u for u in state.users if (u.get("name") or "") == settings.remembered_username), None
            )
            if candidate and candidate.get("rememberToken") and candidate["rememberToken"] == settings.remembered_token:
                remembered_user = candidate
        if remembered_user:
            _show_main_shell(
                page, state, roles_from_field(remembered_user.get("role")), prefs, settings, current_user=remembered_user
            )
        else:
            _show_login(page, state, prefs, settings)
    elif state.profile and state.profile in PROFILES:
        # Eski serbest rol modu — hiç kullanıcı tanımlanmamışken (yeni
        # kurulum ya da bu özellik onaylanmadan önceki mevcut kullanım)
        # geriye dönük uyumluluk için korunuyor. Admin, Kullanıcı
        # Yönetimi'nden ilk hesabı tanımlayınca bir sonraki açılıştan
        # itibaren giriş ekranına geçilir.
        _show_main_shell(page, state, [state.profile], prefs, settings)
    else:
        _show_profile_selector(page, state, prefs, settings)


def _show_login(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    def on_success(user: dict, remember: bool) -> None:
        page.run_task(_complete_login, page, state, prefs, settings, user, remember)

    page.controls.clear()
    _center_screen(page)
    page.add(build_login_screen(page, state, on_success, remembered_username=settings.remembered_username))
    page.update()


async def _complete_login(
    page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings, user: dict, remember: bool
) -> None:
    if remember:
        token = generate_remember_token()
        await asyncio.to_thread(state.save_users, [{**user, "rememberToken": token}])
        user = next((u for u in state.users if u["id"] == user["id"]), user)
        settings.remembered_username = user.get("name") or ""
        settings.remembered_token = token
    else:
        settings.remembered_username = ""
        settings.remembered_token = ""
    await save_settings(prefs, settings)
    _show_main_shell(page, state, roles_from_field(user.get("role")), prefs, settings, current_user=user)


async def _logout(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    settings.remembered_username = ""
    settings.remembered_token = ""
    await save_settings(prefs, settings)
    _show_login(page, state, prefs, settings)


async def _sync_now(
    page: ft.Page,
    state: AppState,
    role_keys: list[str],
    prefs: ft.SharedPreferences,
    settings: AppSettings,
    current_user: dict | None,
) -> None:
    await asyncio.to_thread(state.load_all)
    _show_main_shell(page, state, role_keys, prefs, settings, current_user=current_user)


def _show_profile_selector(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    def on_select(role_key: str) -> None:
        page.run_task(_select_profile, page, state, role_key, prefs, settings)

    page.controls.clear()
    _center_screen(page)
    page.add(build_profile_selector(on_select))
    page.update()


async def _select_profile(page: ft.Page, state: AppState, role_key: str, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    await asyncio.to_thread(state.db.save_all_data, profile=role_key)
    state.profile = role_key
    _show_main_shell(page, state, [role_key], prefs, settings)


def _show_main_shell(
    page: ft.Page,
    state: AppState,
    role_keys: list[str],
    prefs: ft.SharedPreferences,
    settings: AppSettings,
    current_user: dict | None = None,
) -> None:
    info = compute_effective_access(role_keys)
    page.controls.clear()

    saving_text = ft.Text("", color=ft.Colors.GREEN, size=12)

    def set_saving(saving: bool) -> None:
        saving_text.value = "Kaydediliyor..." if saving else ""
        if page.controls:
            saving_text.update()

    def change_profile(e) -> None:
        page.run_task(_change_profile, page, state, prefs, settings)

    def do_logout(e) -> None:
        page.run_task(_logout, page, state, prefs, settings)

    def do_sync_now(e) -> None:
        page.run_task(_sync_now, page, state, role_keys, prefs, settings, current_user)

    def open_barcode_mapper(e) -> None:
        # Ürün/fiyat/başlangıç stoğu değişiklikleri Kayıt Defteri, Genel
        # Tablo ve Satışlar sekmelerindeki ürün listelerini de etkiliyor —
        # bu yüzden kaydedince en basit doğru çözüm olarak tüm kabuğu
        # (page_bodies dahil) taze state ile yeniden kuruyoruz.
        BarcodeMapperDialog(
            page, state,
            on_saved=lambda: _show_main_shell(page, state, role_keys, prefs, settings, current_user=current_user),
        ).open()

    def open_waybill_vault(e) -> None:
        # İrsaliye ekleme/silme diğer sekmeleri etkilemiyor, dialog kendi
        # listesini zaten kendi içinde tazeliyor.
        WaybillVaultDialog(page, state, settings.gemini_api_key, on_saved=lambda: None).open()

    def open_user_management(e) -> None:
        UserManagementDialog(
            page, state,
            current_user_id=(current_user or {}).get("id"),
            on_saved=lambda: _show_main_shell(page, state, role_keys, prefs, settings, current_user=current_user),
        ).open()

    # Not: yeni Flet sürümünde ft.Tab sadece başlığı temsil ediyor — içerik
    # ft.TabBarView ile eşleştiriliyor (Tabs'ın kendi kabul ettiği yapı).
    page_bodies: list[ft.Control] = []
    for page_key in info.pages:
        if page_key == "defter":
            # Üretim ve Satış'ın kendi özel dashboard sınıfları (page_dashboard_
            # uretim.py / page_dashboard_satis.py) sadece show_uretim_fire/
            # show_satis bayraklarını sabit veren birer DashboardBase kısayolu.
            # Bir kullanıcı artık birden fazla role sahip olabildiği (ör. hem
            # Üretim hem Satış) için tek-tip DashboardBase'i doğrudan,
            # `info`'nun BİRLEŞTİRİLMİŞ bayraklarıyla kullanıyoruz — tek rollü
            # kullanıcılar için davranış birebir eskisiyle aynı, çoklu rollü
            # kullanıcılar (admin dahil) ilgili tüm alanları aynı ekranda görür.
            body = DashboardBase(
                page, state, role_keys[0], on_saving=set_saving,
                show_uretim_fire=info.show_uretim_fire, show_satis=info.show_satis,
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
                ft.TabBar(
                    tabs=[
                        ft.Tab(label=PAGE_LABELS.get(p, p), icon=PAGE_ICONS.get(p))
                        for p in info.pages
                    ]
                ),
                ft.TabBarView(controls=page_bodies, expand=True),
            ],
            expand=True,
        ),
    )

    identity_chip: ft.Control
    if current_user:
        identity_chip = ft.Container(
            content=ft.Text(f"{current_user.get('name')} — {info.label}", color=info.color, weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.with_opacity(0.15, info.color),
            border_radius=8,
            padding=ft.Padding(10, 3, 10, 3),
        )
    else:
        identity_chip = ft.Container(
            content=ft.Text(info.label, color=info.color, weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.with_opacity(0.15, info.color),
            border_radius=8,
            padding=ft.Padding(10, 3, 10, 3),
        )

    # Hesap-tabanlı mod (current_user var): "Rol Değiştir" yerine "Çıkış
    # Yap" — rol artık kullanıcı hesabına bağlı, serbestçe değiştirilmiyor.
    # Eski serbest-rol modunda (current_user yok) davranış aynı kalıyor.
    account_action = (
        ft.OutlinedButton("Çıkış Yap", icon=ft.Icons.LOGOUT, on_click=do_logout)
        if current_user
        else ft.OutlinedButton("Rol Değiştir", icon=ft.Icons.SWAP_HORIZ, on_click=change_profile)
    )

    header_controls = [
        ft.Icon(ft.Icons.INVENTORY, color=info.color, size=22),
        ft.Text("Üretim & Satış Defteri", weight=ft.FontWeight.BOLD, size=16),
        identity_chip,
        saving_text,
        ft.Container(expand=True),
        # Not: bu Row'a asla wrap=True verme — expand=True olan `tabs`
        # Column'ının altındaki TÜM içeriği sessizce (hiçbir hata izi
        # bırakmadan) gri bir kutuya çeviren gerçek bir Flet/Flutter
        # bug'ı bulundu ve doğrulandı. Buton metinlerini kısa tutup dar
        # ekranlarda yatay kaydırmaya izin vermek daha güvenli.
        ft.OutlinedButton("Senkronize Et", icon=ft.Icons.CLOUD_SYNC, on_click=do_sync_now),
        ft.OutlinedButton("Barkod Eşleştirme", icon=ft.Icons.QR_CODE_2, on_click=open_barcode_mapper),
        ft.OutlinedButton("İrsaliye Arşivi", icon=ft.Icons.DESCRIPTION, on_click=open_waybill_vault),
    ]
    if info.is_admin:
        header_controls.append(
            ft.OutlinedButton("Kullanıcı Yönetimi", icon=ft.Icons.MANAGE_ACCOUNTS, on_click=open_user_management)
        )
    header_controls.append(account_action)

    header = ft.Row(header_controls, scroll=ft.ScrollMode.AUTO)

    _uncenter_screen(page)
    page.add(ft.Column([header, tabs], expand=True))
    page.update()


async def _change_profile(page: ft.Page, state: AppState, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    await asyncio.to_thread(state.db.save_all_data, profile="")
    state.profile = None
    _show_profile_selector(page, state, prefs, settings)


def _show_first_run_settings(page: ft.Page, prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    page.controls.clear()
    _center_screen(page)

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
                ft.FilledButton("Kaydet ve Devam Et", icon=ft.Icons.ARROW_FORWARD, on_click=on_save),
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
