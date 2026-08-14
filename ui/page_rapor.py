"""Haftalık / Aylık Rapor — PySide6 sürümündeki page_rapor.py'nin Flet
karşılığı. KPI kartları, düşük stok uyarısı, aylık üretim/satış grafiği.

Not: Bu Flet sürümünde (0.86.x) hazır bir grafik kontrolü (BarChart/
LineChart) yok — `flet.charts` diye bir modül hiç mevcut değil (eski Flet
sürümlerinde vardı, bu sürümde kaldırılmış). Ekstra bir grafik kütüphanesi
eklemek yerine basit bir çubuk grafiği doğrudan renkli `Container`'ların
oranlı yüksekliğiyle çiziyoruz — harici bağımlılık yok, web/Android'de de
sorunsuz çalışır."""

from __future__ import annotations

from collections import defaultdict

import flet as ft

from core.app_state import AppState
from core.stock_logic import MONTH_SHORT_TR, format_number
from ui.util import is_mounted

UNIT_FIELD = {
    "Kg": ("uretimKg", "fireKg", "satisKg", "bitisStokKg"),
    "Teneke": ("uretimTeneke", "fireTeneke", "satisTeneke", "bitisStokTeneke"),
    "Adet": ("uretimAdet", "fireAdet", "satisAdet", "bitisStokAdet"),
}

CHART_HEIGHT = 180


class RaporPage:
    def __init__(self, page: ft.Page, state: AppState):
        self.page = page
        self.state = state

        self.unit_dropdown = ft.Dropdown(
            label="Birim",
            width=140,
            value="Kg",
            options=[ft.DropdownOption(key=u, text=u) for u in UNIT_FIELD],
            on_select=lambda e: self._recompute(),
        )
        self.product_dropdown = ft.Dropdown(
            label="Ürün", width=280, value="", on_select=lambda e: self._recompute()
        )

        self.low_stock_banner = ft.Container(
            content=ft.Text("", color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.RED)),
                top=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.RED)),
                right=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.RED)),
                bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.RED)),
            ),
            border_radius=8,
            padding=10,
            visible=False,
        )

        self.kpi_uretim = self._kpi_card("Toplam Üretim", "#34D399")
        self.kpi_satis = self._kpi_card("Toplam Satış", "#60A5FA")
        self.kpi_fire = self._kpi_card("Fire / Wastage", "#F87171")
        self.kpi_gelir = self._kpi_card("Toplam Gelir (₺)", "#FBBF24")

        self.chart_container = ft.Container(height=CHART_HEIGHT + 40, alignment=ft.Alignment(0, 1))
        self.chart_legend = ft.Row(
            [
                ft.Row([ft.Container(width=12, height=12, bgcolor="#10B981", border_radius=2), ft.Text("Üretim", size=12)], spacing=4),
                ft.Row([ft.Container(width=12, height=12, bgcolor="#3B82F6", border_radius=2), ft.Text("Satış", size=12)], spacing=4),
            ],
            spacing=16,
        )

        self.control = ft.Column(
            [
                ft.Row([self.unit_dropdown, self.product_dropdown], wrap=True),
                self.low_stock_banner,
                ft.ResponsiveRow(
                    [
                        ft.Container(self.kpi_uretim[0], col={"sm": 6, "md": 3}),
                        ft.Container(self.kpi_satis[0], col={"sm": 6, "md": 3}),
                        ft.Container(self.kpi_fire[0], col={"sm": 6, "md": 3}),
                        ft.Container(self.kpi_gelir[0], col={"sm": 6, "md": 3}),
                    ]
                ),
                ft.Text("Son 6 Ay — Üretim / Satış", weight=ft.FontWeight.BOLD),
                self.chart_legend,
                self.chart_container,
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.on_data_refreshed()

    def _kpi_card(self, title: str, color: str) -> tuple[ft.Card, ft.Text]:
        value_text = ft.Text("0", size=22, weight=ft.FontWeight.W_800, color=color)
        card = ft.Card(
            content=ft.Container(
                ft.Column([ft.Text(title, size=12), value_text], spacing=4),
                padding=14,
            )
        )
        return card, value_text

    # -- Veri yenileme ----------------------------------------------------

    def on_data_refreshed(self) -> None:
        current = self.product_dropdown.value
        codes = sorted({r["urunKodu"] for r in self.state.records})
        self.product_dropdown.options = [ft.DropdownOption(key="", text="Tüm Ürünler")] + [
            ft.DropdownOption(
                key=code,
                text=f"{next((r['urunAdi'] for r in self.state.records if r['urunKodu'] == code), code)} ({code})",
            )
            for code in codes
        ]
        self.product_dropdown.value = current if current in ({"", *codes}) else ""
        if is_mounted(self.product_dropdown):
            self.product_dropdown.update()
        self._recompute()

    def _filtered_records(self) -> list[dict]:
        code = self.product_dropdown.value
        if not code:
            return self.state.records
        return [r for r in self.state.records if r["urunKodu"] == code]

    def _filtered_sales(self) -> list[dict]:
        code = self.product_dropdown.value
        if not code:
            return self.state.sales
        return [s for s in self.state.sales if s["urunKodu"] == code]

    def _recompute(self) -> None:
        unit = self.unit_dropdown.value or "Kg"
        uretim_field, fire_field, satis_field, _bitis_field = UNIT_FIELD[unit]
        records = self._filtered_records()
        sales = self._filtered_sales()

        total_uretim = sum(r.get(uretim_field) or 0 for r in records)
        total_fire = sum(r.get(fire_field) or 0 for r in records)
        total_satis = sum(r.get(satis_field) or 0 for r in records)
        total_gelir = sum(s.get("tutar") or 0 for s in sales)

        # Fire oranı: üretimi sıfırdan farklı olan ilk birimi öncelik
        # sırasıyla kullan (Kg > Teneke > Adet) — web/PySide6 sürümüyle
        # birebir aynı öncelik mantığı.
        fire_uretim = sum(r.get("uretimKg") or 0 for r in records)
        fire_fire = sum(r.get("fireKg") or 0 for r in records)
        if fire_uretim == 0:
            fire_uretim = sum(r.get("uretimTeneke") or 0 for r in records)
            fire_fire = sum(r.get("fireTeneke") or 0 for r in records)
        if fire_uretim == 0:
            fire_uretim = sum(r.get("uretimAdet") or 0 for r in records)
            fire_fire = sum(r.get("fireAdet") or 0 for r in records)
        fire_rate = (fire_fire / fire_uretim * 100) if fire_uretim else 0

        self.kpi_uretim[1].value = f"{format_number(total_uretim)} {unit}"
        self.kpi_satis[1].value = f"{format_number(total_satis)} {unit}"
        self.kpi_fire[1].value = f"{format_number(total_fire)} {unit}  ({format_number(fire_rate)}%)"
        self.kpi_gelir[1].value = f"₺{format_number(total_gelir)}"
        for _, value_text in (self.kpi_uretim, self.kpi_satis, self.kpi_fire, self.kpi_gelir):
            if is_mounted(value_text):
                value_text.update()

        self._recompute_low_stock()
        self._recompute_chart(records, uretim_field, satis_field)

    def _recompute_low_stock(self) -> None:
        latest: dict[str, dict] = {}
        for r in self.state.records:
            code = r["urunKodu"]
            existing = latest.get(code)
            if not existing or r["tarih"] > existing["tarih"]:
                latest[code] = r

        low = []
        for r in latest.values():
            teneke = r.get("bitisStokTeneke") or 0
            kg = r.get("bitisStokKg") or 0
            adet = r.get("bitisStokAdet") or 0
            if teneke <= 5 or kg <= 50 or (adet > 0 and adet <= 10):
                low.append(f"{r['urunAdi']}: {format_number(teneke)} T / {format_number(kg)} Kg / {format_number(adet)} Ad")

        if low:
            self.low_stock_banner.content.value = "⚠ Düşük Stok Uyarısı: " + " | ".join(low)
            self.low_stock_banner.visible = True
        else:
            self.low_stock_banner.visible = False
        if is_mounted(self.low_stock_banner):
            self.low_stock_banner.update()

    def _recompute_chart(self, records: list[dict], uretim_field: str, satis_field: str) -> None:
        monthly_uretim: dict[str, float] = defaultdict(float)
        monthly_satis: dict[str, float] = defaultdict(float)
        for r in records:
            tarih = r.get("tarih") or ""
            if len(tarih) < 7:
                continue
            key = tarih[:7]  # YYYY-MM
            monthly_uretim[key] += r.get(uretim_field) or 0
            monthly_satis[key] += r.get(satis_field) or 0

        months = sorted(set(monthly_uretim) | set(monthly_satis))[-6:]
        max_val = max([*(monthly_uretim.get(m, 0) for m in months), *(monthly_satis.get(m, 0) for m in months), 1])

        columns: list[ft.Control] = []
        if not months:
            columns.append(ft.Text("Henüz veri yok.", italic=True))
        for m in months:
            year, mon = m.split("-")
            label = f"{MONTH_SHORT_TR[int(mon) - 1]} {year[2:]}"
            u_val = monthly_uretim.get(m, 0)
            s_val = monthly_satis.get(m, 0)
            u_h = max((u_val / max_val) * CHART_HEIGHT, 2) if max_val else 2
            s_h = max((s_val / max_val) * CHART_HEIGHT, 2) if max_val else 2
            columns.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    width=18, height=u_h, bgcolor="#10B981", border_radius=3,
                                    tooltip=f"Üretim: {format_number(u_val)}",
                                ),
                                ft.Container(
                                    width=18, height=s_h, bgcolor="#3B82F6", border_radius=3,
                                    tooltip=f"Satış: {format_number(s_val)}",
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        ft.Text(label, size=11),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            )

        self.chart_container.content = ft.Row(
            columns, alignment=ft.MainAxisAlignment.SPACE_EVENLY, vertical_alignment=ft.CrossAxisAlignment.END
        )
        if is_mounted(self.chart_container):
            self.chart_container.update()
