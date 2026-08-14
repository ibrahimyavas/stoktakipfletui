"""Genel Tablo — PySide6 sürümündeki page_genel.py'nin Flet karşılığı, artık
filtreleme seçenekleriyle: firma, ürün, tarih aralığı ve serbest metin
araması bir arada, hepsi aynı anda uygulanır."""

from __future__ import annotations

import csv
import io

import flet as ft

from core.app_state import AppState
from core.stock_logic import format_date_tr, format_number
from ui.util import is_mounted


class GenelPage:
    def __init__(self, page: ft.Page, state: AppState):
        self.page = page
        self.state = state

        self.search_field = ft.TextField(
            label="Ara (Satış ID, firma, ürün, plaka)", width=320, on_change=lambda e: self._refresh()
        )
        self.firma_dropdown = ft.Dropdown(label="Firma", width=220, options=[], on_select=lambda e: self._refresh())
        self.urun_dropdown = ft.Dropdown(label="Ürün", width=220, options=[], on_select=lambda e: self._refresh())
        self.tarih_baslangic = ft.TextField(label="Başlangıç Tarihi (YYYY-AA-GG)", width=200, on_change=lambda e: self._refresh())
        self.tarih_bitis = ft.TextField(label="Bitiş Tarihi (YYYY-AA-GG)", width=200, on_change=lambda e: self._refresh())

        clear_btn = ft.OutlinedButton("Filtreleri Temizle", icon=ft.Icons.FILTER_ALT_OFF, on_click=self._clear_filters)
        export_btn = ft.FilledButton("CSV Olarak Dışa Aktar", icon=ft.Icons.DOWNLOAD, on_click=self._export_csv)

        self.result_count_text = ft.Text("", size=12)
        self.table = ft.DataTable(columns=self._columns(), rows=[])

        # Not: FilePicker artık bir "Service" (SharedPreferences ile aynı
        # kategori) — eski `page.overlay.append(...)` deseni "Unknown
        # control: FilePicker" hatası veriyordu, `page.services` gerekiyor.
        self.file_picker = ft.FilePicker()
        if self.page:
            self.page.services.append(self.file_picker)

        self.control = ft.Column(
            [
                ft.Text("Genel Tablo", size=18, weight=ft.FontWeight.BOLD),
                ft.Card(
                    content=ft.Container(
                        ft.Column(
                            [
                                ft.Text("Filtreler", weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [self.search_field, self.firma_dropdown, self.urun_dropdown],
                                    wrap=True,
                                ),
                                ft.Row([self.tarih_baslangic, self.tarih_bitis, clear_btn, export_btn], wrap=True),
                                self.result_count_text,
                            ],
                            spacing=10,
                        ),
                        padding=14,
                    )
                ),
                ft.Container(content=self.table, expand=True),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self.on_data_refreshed()

    def _columns(self) -> list[ft.DataColumn]:
        return [
            ft.DataColumn(ft.Text(c))
            for c in ["Satış ID", "Tarih", "Firma", "Ürün", "Plaka", "Miktar", "Fiyat", "Tutar"]
        ]

    # -- Veri ------------------------------------------------------------

    def _master_rows(self) -> list[dict]:
        company_by_kod = {c["kod"]: c for c in self.state.companies}
        rows = []
        for s in self.state.sales:
            row = {**s, "_firma": company_by_kod.get(s.get("sirketKodu"), {}).get("ad", s.get("sirketAdi", ""))}
            rows.append(row)
        rows.sort(key=lambda r: r.get("irsaliyeTarihi") or "", reverse=True)
        return rows

    def on_data_refreshed(self) -> None:
        self._refresh_filter_options()
        self._refresh()

    def _refresh_filter_options(self) -> None:
        current_firma = self.firma_dropdown.value
        current_urun = self.urun_dropdown.value

        firmalar = sorted({(s.get("sirketKodu"), s.get("_firma") or s.get("sirketAdi")) for s in self._master_rows()}, key=lambda t: t[1] or "")
        self.firma_dropdown.options = [ft.DropdownOption(key="", text="Tüm Firmalar")] + [
            ft.DropdownOption(key=kod, text=ad) for kod, ad in firmalar if kod
        ]

        urunler = sorted({(s.get("urunKodu"), s.get("urunAdi")) for s in self.state.sales}, key=lambda t: t[1] or "")
        self.urun_dropdown.options = [ft.DropdownOption(key="", text="Tüm Ürünler")] + [
            ft.DropdownOption(key=kod, text=ad) for kod, ad in urunler if kod
        ]

        self.firma_dropdown.value = current_firma
        self.urun_dropdown.value = current_urun
        if is_mounted(self.firma_dropdown):
            self.firma_dropdown.update()
        if is_mounted(self.urun_dropdown):
            self.urun_dropdown.update()

    def _filtered_rows(self) -> list[dict]:
        query = (self.search_field.value or "").strip().lower()
        firma_kod = self.firma_dropdown.value or ""
        urun_kod = self.urun_dropdown.value or ""
        tarih_bas = (self.tarih_baslangic.value or "").strip()
        tarih_bit = (self.tarih_bitis.value or "").strip()

        rows = []
        for r in self._master_rows():
            if query and not (
                query in (r.get("id") or "").lower()
                or query in (r.get("_firma") or "").lower()
                or query in (r.get("urunAdi") or "").lower()
                or query in (r.get("aracPlakasi") or "").lower()
            ):
                continue
            if firma_kod and r.get("sirketKodu") != firma_kod:
                continue
            if urun_kod and r.get("urunKodu") != urun_kod:
                continue
            tarih = r.get("irsaliyeTarihi") or ""
            if tarih_bas and tarih < tarih_bas:
                continue
            if tarih_bit and tarih > tarih_bit:
                continue
            rows.append(r)
        return rows

    def _refresh(self) -> None:
        rows = self._filtered_rows()
        self.result_count_text.value = f"{len(rows)} kayıt bulundu (toplam {len(self.state.sales)})"

        data_rows = []
        for r in rows:
            data_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(r.get("id") or "")),
                        ft.DataCell(ft.Text(format_date_tr(r.get("irsaliyeTarihi")))),
                        ft.DataCell(ft.Text(r.get("_firma") or "")),
                        ft.DataCell(ft.Text(r.get("urunAdi") or "")),
                        ft.DataCell(ft.Text(r.get("aracPlakasi") or "")),
                        ft.DataCell(ft.Text(f"{format_number(r.get('miktarTeneke'))} T / {format_number(r.get('miktarKg'))} Kg")),
                        ft.DataCell(ft.Text(f"₺{format_number(r.get('fiyatKg') or r.get('fiyatTeneke'))}")),
                        ft.DataCell(ft.Text(f"₺{format_number(r.get('tutar'))}")),
                    ]
                )
            )
        self.table.rows = data_rows
        if is_mounted(self.table):
            self.table.update()
        if is_mounted(self.result_count_text):
            self.result_count_text.update()

    def _clear_filters(self, e) -> None:
        self.search_field.value = ""
        self.firma_dropdown.value = ""
        self.urun_dropdown.value = ""
        self.tarih_baslangic.value = ""
        self.tarih_bitis.value = ""
        self.page.update()
        self._refresh()

    # -- CSV export ----------------------------------------------------------

    def _export_csv(self, e) -> None:
        self.page.run_task(self._export_csv_async)

    async def _export_csv_async(self) -> None:
        rows = self._filtered_rows()
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(
            ["Satış ID", "İrsaliye Tarihi", "Fatura Tarihi", "Firma Kodu", "Firma Adı", "Araç Plakası",
             "Ürün Kodu", "Ürün Adı", "Miktar (Teneke)", "Miktar (Kg)", "Miktar (Adet)",
             "Fiyat (Teneke)", "Fiyat (Kg)", "Fiyat (Adet)", "Tutar", "Barkod"]
        )
        for r in rows:
            writer.writerow(
                [
                    r.get("id"), r.get("irsaliyeTarihi"), r.get("faturaTarihi"), r.get("sirketKodu"),
                    r.get("_firma"), r.get("aracPlakasi"), r.get("urunKodu"), r.get("urunAdi"),
                    r.get("miktarTeneke"), r.get("miktarKg"), r.get("miktarAdet"),
                    r.get("fiyatTeneke"), r.get("fiyatKg"), r.get("fiyatAdet"), r.get("tutar"), r.get("barcode"),
                ]
            )
        # src_bytes her zaman gönderiliyor — masaüstünde olduğu gibi web/Android'de
        # de çalışması için (o platformlarda gerçek bir dosya yolu/yerel dosya
        # sistemi yok, save_file bunu zorunlu kılıyor).
        csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")
        path = await self.file_picker.save_file(
            file_name="genel-tablo.csv", allowed_extensions=["csv"], src_bytes=csv_bytes
        )
        if path:
            self.page.show_dialog(ft.SnackBar(ft.Text(f"CSV kaydedildi: {path}")))
