"""Rol seçim ekranı — PySide6 sürümündeki ProfileSelector'ın Flet karşılığı."""

from __future__ import annotations

from typing import Callable

import flet as ft

from core.models import PAGE_LABELS, PROFILES


def _role_card(role_key: str, on_click: Callable[[str], None]) -> ft.Card:
    info = PROFILES[role_key]

    chips = ft.Row(
        [
            ft.Container(
                content=ft.Text(PAGE_LABELS.get(p, p), size=11, weight=ft.FontWeight.BOLD, color=info.color),
                bgcolor=ft.Colors.with_opacity(0.15, info.color),
                border_radius=10,
                padding=ft.Padding(8, 3, 8, 3),
            )
            for p in info.pages
        ],
        wrap=True,
        spacing=6,
    )

    return ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(info.label, size=20, weight=ft.FontWeight.BOLD, color=info.color),
                    ft.Text(info.description, size=13),
                    chips,
                    ft.Container(height=8),
                    ft.FilledButton(
                        f"{info.label} olarak devam et",
                        on_click=lambda e: on_click(role_key),
                        style=ft.ButtonStyle(bgcolor=info.color, color="#04120C"),
                        width=300,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            padding=20,
            width=300,
        ),
    )


def build_profile_selector(on_select: Callable[[str], None]) -> ft.Control:
    return ft.Column(
        [
            ft.Text("Üretim & Satış Defteri", size=26, weight=ft.FontWeight.BOLD),
            ft.Text("Devam etmek için rolünüzü seçin"),
            ft.Container(height=10),
            ft.ResponsiveRow(
                [
                    ft.Container(_role_card(role_key, on_select), col={"sm": 12, "md": 4})
                    for role_key in ("uretim", "satis", "admin")
                ],
            ),
        ],
        spacing=10,
    )
