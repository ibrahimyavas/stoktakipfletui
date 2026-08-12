"""Üretim Dashboard — sadece üretim rolüyle ilgili kısım: üretim/fire girişi
+ stok & fiyat. Satışla ilgili hiçbir alan/mantık burada yok; ortak
kayıt/silme/stok-zinciri/kilit mantığı `ui/dashboard_common.py`'de yaşıyor."""

from __future__ import annotations

import flet as ft

from core.app_state import AppState
from ui.dashboard_common import DashboardBase


class UretimDashboard(DashboardBase):
    def __init__(self, page: ft.Page, state: AppState, on_saving=None):
        super().__init__(
            page,
            state,
            profile_role="uretim",
            on_saving=on_saving,
            show_uretim_fire=True,
            show_satis=False,
        )
