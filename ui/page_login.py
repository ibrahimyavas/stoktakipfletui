"""Giriş ekranı — admin tarafından tanımlanmış kullanıcılar için. Sadece
`state.users` doluysa gösteriliyor (bkz. main.py); hiç kullanıcı
tanımlanmamışsa eski serbest Rol Seçimi ekranı çalışmaya devam ediyor,
böylece mevcut kurulumlar/testler bozulmuyor."""

from __future__ import annotations

from typing import Callable

import flet as ft

from core.app_state import AppState
from core.auth import verify_password


def build_login_screen(
    page: ft.Page,
    state: AppState,
    on_success: Callable[[dict, bool], None],
    remembered_username: str = "",
) -> ft.Control:
    username_field = ft.TextField(label="Kullanıcı Adı", value=remembered_username, width=320, autofocus=not remembered_username)
    password_field = ft.TextField(label="Şifre", width=320, password=True, can_reveal_password=True, autofocus=bool(remembered_username))
    remember_checkbox = ft.Checkbox(label="Beni Hatırla", value=bool(remembered_username))
    error_text = ft.Text("", color=ft.Colors.RED)

    def do_login(e) -> None:
        name = (username_field.value or "").strip()
        password = password_field.value or ""
        if not name or not password:
            error_text.value = "Kullanıcı adı ve şifre zorunludur."
            error_text.update()
            return

        user = next((u for u in state.users if (u.get("name") or "").strip().lower() == name.lower()), None)
        if not user or not verify_password(password, user.get("passwordHash") or "", user.get("passwordSalt") or ""):
            error_text.value = "Kullanıcı adı veya şifre hatalı."
            error_text.update()
            return

        on_success(user, bool(remember_checkbox.value))

    password_field.on_submit = do_login

    return ft.Column(
        [
            ft.Text("Üretim & Satış Defteri", size=26, weight=ft.FontWeight.BOLD),
            ft.Text("Devam etmek için giriş yapın"),
            ft.Container(height=10),
            username_field,
            password_field,
            ft.Row([remember_checkbox], tight=True),
            error_text,
            ft.FilledButton("Giriş Yap", icon=ft.Icons.LOGIN, on_click=do_login),
        ],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
