"""
Uygulama ayarları (Turso/Gemini/Sheets bağlantı bilgileri + görünüm tercihi).

PySide6 sürümünden farklı olarak burada `platformdirs` kullanmıyoruz — o
sadece masaüstü dosya sisteminde çalışır, Android/iOS'ta işe yaramaz. Bunun
yerine Flet'in `SharedPreferences` servisini (Flutter'ın `shared_preferences`
paketini sarmalıyor) kullanıyoruz — aynı kod hem masaüstünde hem web'de hem
de gelecekte derlenecek Android/iOS uygulamasında sorunsuz çalışır.

SharedPreferences API'si async olduğu için (ft.Page'e bağlı bir servis),
`load()`/`save()` de async — çağıran taraf `await` etmeli.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

import flet as ft

_STORAGE_KEY = "uretim_satis_defteri.settings"


@dataclass
class AppSettings:
    turso_database_url: str = ""
    turso_auth_token: str = ""
    gemini_api_key: str = ""
    sheets_url: str = ""
    # Son seçilen rol (uretim/satis/admin) — bir sonraki açılışta hatırlanır.
    last_profile: str = ""
    # Görünüm: "dark" / "light" / "system" + serbestçe seçilebilir aksan rengi.
    theme_mode: str = "dark"
    accent_color: str = "#10B981"

    def is_configured(self) -> bool:
        return bool(self.turso_database_url and self.turso_auth_token)


async def load_settings(prefs: ft.SharedPreferences) -> AppSettings:
    raw = await prefs.get(_STORAGE_KEY)
    if not raw:
        return AppSettings()
    try:
        data = json.loads(raw)
        defaults = AppSettings()
        # Eksik alanlar (ör. eski bir kayıtta henüz olmayan yeni tema
        # alanları) her zaman kendi varsayılanını alır — "" değil, aksi
        # halde tema uygulaması boş renk/mod ile bozulurdu.
        known = {f.name for f in fields(AppSettings)}
        return AppSettings(
            **{k: data.get(k, getattr(defaults, k)) for k in known}
        )
    except (json.JSONDecodeError, TypeError):
        return AppSettings()


async def save_settings(prefs: ft.SharedPreferences, settings: AppSettings) -> None:
    await prefs.set(_STORAGE_KEY, json.dumps(asdict(settings), ensure_ascii=False))
