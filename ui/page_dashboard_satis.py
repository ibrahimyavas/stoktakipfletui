"""Satış Dashboard — sadece satış rolüyle ilgili kısım: satış girişi (miktar
+ Satış ID) + stok & fiyat. Üretim/fire ile ilgili hiçbir alan/mantık burada
yok; ortak kayıt/silme/stok-zinciri/kilit mantığı `ui/dashboard_common.py`'de
yaşıyor."""

from __future__ import annotations

import flet as ft

from core.app_state import AppState
from ui.dashboard_common import DashboardBase


class SatisDashboard(DashboardBase):
    def __init__(self, page: ft.Page, state: AppState, on_saving=None):
        super().__init__(
            page,
            state,
            profile_role="satis",
            on_saving=on_saving,
            show_uretim_fire=False,
            show_satis=True,
        )
