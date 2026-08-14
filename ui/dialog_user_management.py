"""Kullanıcı Yönetimi diyaloğu — sadece admin rolüne görünen, header'dan
açılan bir panel. Kullanıcı adı + şifre + rol ile hesap tanımlar; bu Flet
sürümüne özgü bir özellik (web app/PySide6 sürümünde yok, onlar serbest rol
seçimini koruyor)."""

from __future__ import annotations

import asyncio
import time
import uuid

import flet as ft

from core.app_state import AppState
from core.auth import hash_password
from core.models import PROFILES
from ui.util import is_mounted


def _new_id() -> str:
    return f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"


class UserManagementDialog:
    def __init__(self, page: ft.Page, state: AppState, current_user_id: str | None = None, on_saved=None):
        self.page = page
        self.state = state
        self.current_user_id = current_user_id
        self.on_saved = on_saved or (lambda: None)
        self.editing_id: str | None = None

        self.name_field = ft.TextField(label="Kullanıcı Adı", width=220)
        self.password_field = ft.TextField(
            label="Şifre", width=220, password=True, can_reveal_password=True,
            hint_text="Düzenlerken boş bırakılırsa şifre değişmez",
        )
        self.role_dropdown = ft.Dropdown(
            label="Rol",
            width=180,
            value="uretim",
            options=[ft.DropdownOption(key=key, text=info.label) for key, info in PROFILES.items()],
        )
        self.status_text = ft.Text("", size=12)
        self.save_btn = ft.FilledButton("Kaydet", icon=ft.Icons.SAVE, on_click=lambda e: self.page.run_task(self._save))
        self.clear_btn = ft.OutlinedButton("Temizle", icon=ft.Icons.CLEAR, on_click=lambda e: self._clear_form())
        self.user_list = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO, height=220)

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Kullanıcı Yönetimi"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Kullanıcı Ekle / Düzenle", weight=ft.FontWeight.BOLD),
                        ft.Row([self.name_field, self.password_field, self.role_dropdown], wrap=True),
                        ft.Row([self.save_btn, self.clear_btn]),
                        self.status_text,
                        ft.Divider(),
                        ft.Text("Kayıtlı Kullanıcılar", weight=ft.FontWeight.BOLD),
                        self.user_list,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=560,
                height=480,
            ),
            actions=[ft.TextButton("Kapat", on_click=self._close)],
        )
        self._refresh_list()

    def open(self) -> None:
        if self.page:
            self.page.show_dialog(self.dialog)

    def _close(self, e) -> None:
        self.dialog.open = False
        if is_mounted(self.dialog):
            self.dialog.update()

    # -- Liste -----------------------------------------------------------

    def _refresh_list(self) -> None:
        rows = []
        for u in sorted(self.state.users, key=lambda u: (u.get("name") or "").lower()):
            role_info = PROFILES.get(u.get("role"))
            role_label = role_info.label if role_info else (u.get("role") or "?")
            role_color = role_info.color if role_info else None
            rows.append(
                ft.ListTile(
                    title=ft.Text(u.get("name") or ""),
                    subtitle=ft.Text(role_label, color=role_color),
                    trailing=ft.Row(
                        [
                            ft.IconButton(ft.Icons.EDIT, tooltip="Düzenle", on_click=lambda e, user=u: self._load_user(user)),
                            ft.IconButton(
                                ft.Icons.DELETE, tooltip="Sil", icon_color=ft.Colors.RED,
                                on_click=lambda e, user=u: self._on_delete_click(user),
                            ),
                        ],
                        spacing=0,
                        tight=True,
                    ),
                    dense=True,
                )
            )
        self.user_list.controls = rows or [ft.Text("Henüz kullanıcı tanımlanmadı.", italic=True, size=12)]
        if is_mounted(self.user_list):
            self.user_list.update()

    def _load_user(self, u: dict) -> None:
        self.editing_id = u["id"]
        self.name_field.value = u.get("name") or ""
        self.password_field.value = ""
        self.role_dropdown.value = u.get("role") or "uretim"
        self.status_text.value = ""
        if self.page:
            self.page.update()

    def _clear_form(self) -> None:
        self.editing_id = None
        self.name_field.value = ""
        self.password_field.value = ""
        self.role_dropdown.value = "uretim"
        self.status_text.value = ""
        if self.page:
            self.page.update()

    # -- Kaydetme (UI'dan bağımsız, test edilebilir) ------------------------

    async def _save(self) -> bool:
        name = (self.name_field.value or "").strip()
        password = self.password_field.value or ""
        role = self.role_dropdown.value or "uretim"

        if not name:
            self._set_status("Kullanıcı adı zorunludur.", error=True)
            return False
        if role not in PROFILES:
            self._set_status("Geçersiz rol.", error=True)
            return False

        existing = next((u for u in self.state.users if u["id"] == self.editing_id), None) if self.editing_id else None
        duplicate = next(
            (u for u in self.state.users if (u.get("name") or "").strip().lower() == name.lower() and u["id"] != (existing["id"] if existing else None)),
            None,
        )
        if duplicate:
            self._set_status(f"'{name}' adında başka bir kullanıcı zaten var.", error=True)
            return False

        if not existing and not password:
            self._set_status("Yeni kullanıcı için şifre zorunludur.", error=True)
            return False

        if password:
            password_hash, salt = hash_password(password)
        elif existing:
            password_hash, salt = existing.get("passwordHash") or "", existing.get("passwordSalt") or ""
        else:
            password_hash, salt = "", ""

        user = {
            "id": self.editing_id or _new_id(),
            "name": name,
            "passwordHash": password_hash,
            "passwordSalt": salt,
            "role": role,
            # Şifre değişince (ya da yeni kullanıcıda) önceki "Beni Hatırla"
            # oturumları geçersiz kılınır — kullanıcı tekrar şifre girmeli.
            "rememberToken": "" if password else (existing.get("rememberToken") if existing else ""),
            "createdAt": existing.get("createdAt") if existing else time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        try:
            await asyncio.to_thread(self.state.save_users, [user])
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Kaydedilemedi: {exc}", error=True)
            return False

        self._set_status(f"'{name}' kaydedildi.", error=False)
        self._clear_form()
        self._refresh_list()
        self.on_saved()
        return True

    def _on_delete_click(self, u: dict) -> None:
        if u["id"] == self.current_user_id:
            self._set_status("Şu an giriş yapmış olduğunuz hesabı silemezsiniz.", error=True)
            return
        admins = [x for x in self.state.users if x.get("role") == "admin"]
        if u.get("role") == "admin" and len(admins) <= 1:
            self._set_status("Son admin hesabı silinemez — önce başka bir admin tanımlayın.", error=True)
            return
        self._confirm(
            f"'{u.get('name')}' kullanıcısını silmek istiyor musunuz?",
            lambda: self.page.run_task(self._delete_user, u),
        )

    async def _delete_user(self, u: dict) -> None:
        try:
            await asyncio.to_thread(self.state.save_users, None, [u["id"]])
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Silinemedi: {exc}", error=True)
            return
        self._refresh_list()
        self.on_saved()

    def _confirm(self, message: str, on_yes) -> None:
        def close_dialog(e) -> None:
            confirm_dialog.open = False
            if is_mounted(confirm_dialog):
                confirm_dialog.update()

        def yes_clicked(e) -> None:
            close_dialog(e)
            on_yes()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Emin misiniz?"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Vazgeç", on_click=close_dialog),
                ft.FilledButton("Evet", on_click=yes_clicked),
            ],
        )
        if self.page:
            self.page.show_dialog(confirm_dialog)

    def _set_status(self, msg: str, *, error: bool) -> None:
        self.status_text.value = msg
        self.status_text.color = ft.Colors.RED if error else ft.Colors.GREEN
        if is_mounted(self.status_text):
            self.status_text.update()
