"""Satışlar & Firmalar — PySide6 sürümündeki page_satis.py + dialog_complete_sale.py
+ dialog_qr.py'nin Flet karşılığı. 4 sekme: Stok & Yeni Satış, Bekleyen
Satışlar, Firmalar, Satış Listesi. "Satışı Tamamla" akışı ("Firmaya İşle")
hem "Yeni Satış Başlat" hem "Bekleyen Satışlar" tarafından paylaşılan tek bir
AlertDialog ile yapılıyor."""

from __future__ import annotations

import asyncio
import io
import time
import uuid

import flet as ft
import qrcode

from core.app_state import AppState
from core.stock_logic import (
    calculate_total_amount,
    format_date_tr,
    format_number,
    generate_sale_id,
    get_today_date_string,
    recalculate_product_stock_chain,
)
from ui.util import is_mounted


def _new_id() -> str:
    return f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"


def _num_field(label: str, width: int = 120) -> ft.TextField:
    return ft.TextField(label=label, value="0", width=width, keyboard_type=ft.KeyboardType.NUMBER)


def _num(tf: ft.TextField) -> float:
    try:
        return float((tf.value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _qr_png_bytes(code: str) -> bytes:
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class SatislarPage:
    def __init__(self, page: ft.Page, state: AppState, on_saving=None):
        self.page = page
        self.state = state
        self.on_saving = on_saving or (lambda saving: None)

        self.file_picker = ft.FilePicker()
        if self.page:
            self.page.services.append(self.file_picker)

        # -- Stok & Yeni Satış -------------------------------------------
        self.quick_product_dropdown = ft.Dropdown(label="Ürün", options=[], width=340)
        self.quick_teneke, self.quick_kg, self.quick_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        self.quick_start_btn = ft.FilledButton("Satışı Başlat → Firmaya İşle", on_click=self._on_quick_start_click)
        self.stock_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in ("Ürün", "Teneke", "Kg", "Adet")], rows=[]
        )

        # -- Bekleyen Satışlar ---------------------------------------------
        self.pending_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in ("Tarih", "Ürün", "Satış", "Satış ID", "İşlem")], rows=[]
        )

        # -- Firmalar -------------------------------------------------------
        self.company_edit_id: str | None = None
        self.company_kod = ft.TextField(label="Kod", width=140)
        self.company_ad = ft.TextField(label="Ad", width=240)
        self.company_tel = ft.TextField(label="Telefon", width=160)
        self.company_save_btn = ft.FilledButton("Kaydet", on_click=self._on_company_save_click)
        self.company_clear_btn = ft.OutlinedButton("Temizle", on_click=lambda e: self._clear_company_form())
        self.company_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in ("Kod", "Ad", "Telefon", "İşlem")], rows=[]
        )

        # -- Satış Listesi ----------------------------------------------------
        self.sales_search = ft.TextField(
            label="Ara (Satış ID, firma, ürün)", width=360, on_change=lambda e: self._refresh_sales_list()
        )
        self.sales_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in ("Satış ID", "Firma", "Ürün", "Miktar", "Tutar", "Tarih", "İşlem")],
            rows=[],
        )

        self.control = self._build_control()
        self.on_data_refreshed()

    # -- Yerleşim ------------------------------------------------------------

    def _build_control(self) -> ft.Control:
        stok_tab = ft.Container(
            ft.Column(
                [
                    ft.Card(
                        content=ft.Container(
                            ft.Column(
                                [
                                    ft.Text("Yeni Satış Başlat", weight=ft.FontWeight.BOLD),
                                    self.quick_product_dropdown,
                                    ft.Row([self.quick_teneke, self.quick_kg, self.quick_adet], wrap=True),
                                    self.quick_start_btn,
                                ],
                                spacing=10,
                            ),
                            padding=14,
                        )
                    ),
                    ft.Container(height=8),
                    ft.Container(content=self.stock_table, expand=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=12,
        )
        pending_tab = ft.Container(
            ft.Column(
                [
                    ft.Text("Satış miktarı girilmiş ama henüz bir firmaya işlenmemiş kayıtlar:"),
                    ft.Container(content=self.pending_table, expand=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=12,
        )
        company_tab = ft.Container(
            ft.Column(
                [
                    ft.Card(
                        content=ft.Container(
                            ft.Column(
                                [
                                    ft.Text("Firma Ekle / Düzenle", weight=ft.FontWeight.BOLD),
                                    ft.Row([self.company_kod, self.company_ad, self.company_tel], wrap=True),
                                    ft.Row([self.company_save_btn, self.company_clear_btn]),
                                ],
                                spacing=10,
                            ),
                            padding=14,
                        )
                    ),
                    ft.Container(height=8),
                    ft.Container(content=self.company_table, expand=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=12,
        )
        sales_tab = ft.Container(
            ft.Column(
                [
                    self.sales_search,
                    ft.Container(content=self.sales_table, expand=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=12,
        )

        return ft.Tabs(
            length=4,
            expand=True,
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Stok & Yeni Satış"),
                            ft.Tab(label="Bekleyen Satışlar"),
                            ft.Tab(label="Firmalar"),
                            ft.Tab(label="Satış Listesi"),
                        ]
                    ),
                    # Not: dashboard_common.py'deki aynı "TabBarView: height is
                    # unbounded" hatasından kaçınmak için sabit height + her
                    # sekme gövdesinde iç scroll kullanılıyor (kanıtlanmış desen).
                    ft.TabBarView(controls=[stok_tab, pending_tab, company_tab, sales_tab], height=560),
                ],
                expand=True,
            ),
        )

    def on_data_refreshed(self) -> None:
        self._refresh_stock()
        self._refresh_pending()
        self._refresh_companies()
        self._refresh_sales_list()

    # -- Stok & Yeni Satış -----------------------------------------------

    def _latest_stock_by_product(self) -> dict[str, dict]:
        latest: dict[str, dict] = {}
        for r in self.state.records:
            code = r["urunKodu"]
            existing = latest.get(code)
            if not existing or r["tarih"] > existing["tarih"] or r["id"] > existing["id"]:
                latest[code] = r
        return latest

    def _refresh_stock(self) -> None:
        latest = self._latest_stock_by_product()
        self.quick_product_dropdown.options = [
            ft.DropdownOption(key=code, text=f"{r['urunAdi']} ({code})")
            for code, r in sorted(latest.items(), key=lambda kv: kv[1]["urunAdi"])
        ]
        rows = []
        for code, r in sorted(latest.items(), key=lambda kv: kv[1]["urunAdi"]):
            out_of_stock = (
                (r.get("bitisStokTeneke") or 0) <= 0
                and (r.get("bitisStokKg") or 0) <= 0
                and (r.get("bitisStokAdet") or 0) <= 0
            )
            name_color = ft.Colors.RED if out_of_stock else None
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{r['urunAdi']} ({code})", color=name_color)),
                        ft.DataCell(ft.Text(format_number(r.get("bitisStokTeneke")))),
                        ft.DataCell(ft.Text(format_number(r.get("bitisStokKg")))),
                        ft.DataCell(ft.Text(format_number(r.get("bitisStokAdet")))),
                    ]
                )
            )
        self.stock_table.rows = rows
        if is_mounted(self.quick_product_dropdown):
            self.quick_product_dropdown.update()
        if is_mounted(self.stock_table):
            self.stock_table.update()

    def _on_quick_start_click(self, e) -> None:
        self.page.run_task(self._quick_start)

    async def _quick_start(self) -> None:
        code = self.quick_product_dropdown.value
        if not code:
            self._snack("Lütfen satılacak ürünü seçin.")
            return
        if _num(self.quick_teneke) <= 0 and _num(self.quick_kg) <= 0 and _num(self.quick_adet) <= 0:
            self._snack("Lütfen en az bir satış miktarı girin.")
            return

        latest = self._latest_stock_by_product().get(code)
        available_teneke = (latest or {}).get("bitisStokTeneke") or 0
        available_kg = (latest or {}).get("bitisStokKg") or 0
        available_adet = (latest or {}).get("bitisStokAdet") or 0
        if _num(self.quick_teneke) > available_teneke or _num(self.quick_kg) > available_kg or _num(self.quick_adet) > available_adet:
            self._snack("Girilen miktar mevcut stoğu aşıyor.")
            return

        new_record = {
            "id": _new_id(),
            "tarih": get_today_date_string(),
            "urunKodu": code,
            "urunAdi": latest["urunAdi"] if latest else code,
            "barcode": (latest or {}).get("barcode") or code,
            "uretimKg": 0, "uretimTeneke": 0, "uretimAdet": 0,
            "fireKg": 0, "fireTeneke": 0, "fireAdet": 0,
            "satisKg": _num(self.quick_kg), "satisTeneke": _num(self.quick_teneke), "satisAdet": _num(self.quick_adet),
            "baslangicStokKg": 0, "baslangicStokTeneke": 0, "baslangicStokAdet": 0,
            "fiyatTeneke": (latest or {}).get("fiyatTeneke") or 0,
            "fiyatKg": (latest or {}).get("fiyatKg") or 0,
            "fiyatAdet": (latest or {}).get("fiyatAdet") or 0,
            "satisId": "", "linkedSaleId": None, "manualBaslangicStok": False, "baslangicStokKilitli": False,
        }

        self.on_saving(True)
        try:
            updated_list = recalculate_product_stock_chain([*self.state.records, new_record], code)
            to_upsert = [r for r in updated_list if r["urunKodu"].strip().lower() == code.strip().lower()]
            await asyncio.to_thread(self.state.db.save_all_data, records=to_upsert)
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Satış başlatılamadı: {exc}")
            self.on_saving(False)
            return
        self.on_saving(False)

        rec = next(r for r in self.state.records if r["id"] == new_record["id"])
        self.quick_teneke.value = "0"
        self.quick_kg.value = "0"
        self.quick_adet.value = "0"
        self.on_data_refreshed()
        self._open_complete_sale_dialog(rec)

    # -- Bekleyen Satışlar -------------------------------------------------

    def _pending_records(self) -> list[dict]:
        linked_sale_ids = {s["id"] for s in self.state.sales}
        pending = []
        for r in self.state.records:
            has_qty = (r.get("satisKg") or 0) > 0 or (r.get("satisTeneke") or 0) > 0 or (r.get("satisAdet") or 0) > 0
            has_id = bool(r.get("satisId"))
            if not (has_qty or has_id):
                continue
            already_linked = r.get("linkedSaleId") and r["linkedSaleId"] in linked_sale_ids
            if already_linked:
                continue
            pending.append(r)
        return pending

    def _refresh_pending(self) -> None:
        rows = []
        for r in self._pending_records():
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(format_date_tr(r.get("tarih")))),
                        ft.DataCell(ft.Text(f"{r['urunAdi']} ({r['urunKodu']})")),
                        ft.DataCell(ft.Text(f"{format_number(r.get('satisTeneke'))} T / {format_number(r.get('satisKg'))} Kg")),
                        ft.DataCell(ft.Text(r.get("satisId") or "-")),
                        ft.DataCell(
                            ft.FilledButton("Firmaya İşle", on_click=lambda e, rec=r: self._open_complete_sale_dialog(rec))
                        ),
                    ]
                )
            )
        self.pending_table.rows = rows
        if is_mounted(self.pending_table):
            self.pending_table.update()

    # -- Satışı Tamamla mantığı (UI'dan bağımsız, test edilebilir) -----------

    async def _complete_sale(
        self,
        rec: dict,
        *,
        firma_kod: str | None,
        satis_id_input: str,
        plaka: str,
        fiyat_kg: float,
        fiyat_teneke: float,
        fiyat_adet: float,
        irsaliye_tarihi: str,
        fatura_tarihi: str,
        photo_data_url: str,
    ) -> dict | None:
        """Bir Defter kaydını tam bir SaleItem'a dönüştürüp kaydeder ("Firmaya
        İşle"). Başarılıysa {"sale_id":..., "tutar":...} döner, doğrulama
        hatasında None döner (kullanıcıya snack ile bildirilir)."""
        if not firma_kod:
            self._snack("Lütfen bir firma seçin.")
            return None
        firma = next((c for c in self.state.companies if c["kod"] == firma_kod), None)
        if not firma:
            self._snack("Seçilen firma bulunamadı.")
            return None

        existing_ids = {s["id"] for s in self.state.sales}
        entered_id = satis_id_input.strip().upper()
        sale_id = entered_id or rec.get("satisId") or generate_sale_id(existing_ids, rec.get("tarih"))

        total = calculate_total_amount(
            rec.get("satisTeneke"), rec.get("satisKg"),
            fiyat_teneke, fiyat_kg,
            rec.get("satisAdet"), fiyat_adet,
        )

        sale_item = {
            "id": sale_id,
            "kaynak": "defter",
            "kaynakKayitId": rec["id"],
            "irsaliyeTarihi": irsaliye_tarihi.strip(),
            "faturaTarihi": fatura_tarihi.strip(),
            "sirketKodu": firma["kod"],
            "sirketAdi": firma["ad"],
            "aracPlakasi": plaka.strip().upper(),
            "urunKodu": rec["urunKodu"],
            "urunAdi": rec["urunAdi"],
            "miktarTeneke": rec.get("satisTeneke") or 0,
            "miktarKg": rec.get("satisKg") or 0,
            "miktarAdet": rec.get("satisAdet") or 0,
            "fiyatTeneke": fiyat_teneke,
            "fiyatKg": fiyat_kg,
            "fiyatAdet": fiyat_adet,
            "tutar": total,
            "barcode": rec.get("barcode") or rec["urunKodu"],
            "irsaliyeFotoUrl": photo_data_url,
        }
        updated_record = {
            **rec,
            "satisId": sale_id,
            "linkedSaleId": sale_id,
            "fiyatTeneke": fiyat_teneke,
            "fiyatKg": fiyat_kg,
            "fiyatAdet": fiyat_adet,
        }

        self.on_saving(True)
        try:
            await asyncio.to_thread(self.state.db.save_all_data, sales=[sale_item], records=[updated_record])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Satış tamamlanamadı: {exc}")
            self.on_saving(False)
            return None
        self.on_saving(False)
        return {"sale_id": sale_id, "tutar": total}

    # -- Satışı Tamamla diyaloğu --------------------------------------------

    def _open_complete_sale_dialog(self, rec: dict) -> None:
        satis_id_field = ft.TextField(label="Satış ID", value=rec.get("satisId") or rec["id"], width=380)
        firma_dropdown = ft.Dropdown(
            label="Firma *",
            width=380,
            options=[
                ft.DropdownOption(key=c["kod"], text=f"{c['ad']} ({c['kod']})")
                for c in sorted(self.state.companies, key=lambda c: c["ad"])
            ],
        )
        plaka_field = ft.TextField(label="Araç Plakası", width=380)
        fiyat_kg = _num_field("Kilo Fiyatı (₺/Kg)", width=180)
        fiyat_kg.value = str(rec.get("fiyatKg") or 0)
        fiyat_teneke = _num_field("Teneke Fiyatı (₺/Teneke)", width=180)
        fiyat_teneke.value = str(rec.get("fiyatTeneke") or 0)
        fiyat_adet = _num_field("Adet Fiyatı (₺/Adet)", width=180)
        fiyat_adet.value = str(rec.get("fiyatAdet") or 0)
        irsaliye_tarihi = ft.TextField(label="İrsaliye Tarihi", value=rec.get("tarih") or get_today_date_string(), width=180)
        fatura_tarihi = ft.TextField(label="Fatura Tarihi", value=rec.get("tarih") or get_today_date_string(), width=180)
        total_text = ft.Text("Toplam Tutar: ₺0", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
        photo_status = ft.Text("", size=12)
        photo_bytes_holder: dict[str, bytes | None] = {"data": None}

        # İlişkili bir satışa zaten bağlıysa (edit-in-place), o kaydın
        # bilgilerini önceden doldur.
        linked = None
        if rec.get("linkedSaleId"):
            linked = next((s for s in self.state.sales if s["id"] == rec["linkedSaleId"]), None)
        if not linked and rec.get("satisId"):
            linked = next((s for s in self.state.sales if s["id"] == rec["satisId"]), None)
        if linked:
            firma_dropdown.value = linked.get("sirketKodu")
            plaka_field.value = linked.get("aracPlakasi") or ""
            irsaliye_tarihi.value = linked.get("irsaliyeTarihi") or irsaliye_tarihi.value
            fatura_tarihi.value = linked.get("faturaTarihi") or fatura_tarihi.value

        def refresh_total(e=None) -> None:
            total = calculate_total_amount(
                rec.get("satisTeneke"), rec.get("satisKg"),
                _num(fiyat_teneke), _num(fiyat_kg),
                rec.get("satisAdet"), _num(fiyat_adet),
            )
            total_text.value = f"Toplam Tutar: ₺{format_number(total)}"
            if is_mounted(total_text):
                total_text.update()

        for f in (fiyat_kg, fiyat_teneke, fiyat_adet):
            f.on_change = refresh_total

        async def attach_photo(e) -> None:
            files = await self.file_picker.pick_files(
                dialog_title="İrsaliye Fotoğrafı Seç",
                allowed_extensions=["png", "jpg", "jpeg"],
                with_data=True,
            )
            if files and files[0].bytes:
                photo_bytes_holder["data"] = files[0].bytes
                photo_status.value = f"Eklendi: {files[0].name}"
                if is_mounted(photo_status):
                    photo_status.update()

        photo_btn = ft.OutlinedButton("İrsaliye Fotoğrafı Ekle...", on_click=lambda e: self.page.run_task(attach_photo, e))

        async def on_save(e) -> None:
            photo_data = photo_bytes_holder["data"]
            photo_data_url = ""
            if photo_data:
                import base64
                photo_data_url = f"data:image/jpeg;base64,{base64.b64encode(photo_data).decode('ascii')}"
            elif linked:
                photo_data_url = linked.get("irsaliyeFotoUrl") or ""

            result = await self._complete_sale(
                rec,
                firma_kod=firma_dropdown.value,
                satis_id_input=satis_id_field.value or "",
                plaka=plaka_field.value or "",
                fiyat_kg=_num(fiyat_kg),
                fiyat_teneke=_num(fiyat_teneke),
                fiyat_adet=_num(fiyat_adet),
                irsaliye_tarihi=irsaliye_tarihi.value or "",
                fatura_tarihi=fatura_tarihi.value or "",
                photo_data_url=photo_data_url,
            )
            if result is None:
                return
            close_dialog(None)
            self.on_data_refreshed()
            self._snack(f"Satış tamamlandı — ID: {result['sale_id']}, Toplam: ₺{format_number(result['tutar'])}")

        def close_dialog(e) -> None:
            dialog.open = False
            if is_mounted(dialog):
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Satışı Tamamla / Firmaya İşle"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text(f"{rec['urunAdi']} ({rec['urunKodu']}) — {format_number(rec.get('satisTeneke'))} T / {format_number(rec.get('satisKg'))} Kg"),
                        satis_id_field,
                        firma_dropdown,
                        plaka_field,
                        ft.Row([fiyat_kg, fiyat_teneke, fiyat_adet], wrap=True),
                        ft.Row([irsaliye_tarihi, fatura_tarihi], wrap=True),
                        photo_btn,
                        photo_status,
                        total_text,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=420,
                height=440,
            ),
            actions=[
                ft.TextButton("Vazgeç", on_click=close_dialog),
                ft.FilledButton("Satışı Tamamla", on_click=lambda e: self.page.run_task(on_save, e)),
            ],
        )
        refresh_total()
        if self.page:
            self.page.show_dialog(dialog)

    # -- Firmalar ------------------------------------------------------------

    def _refresh_companies(self) -> None:
        rows = []
        for c in sorted(self.state.companies, key=lambda c: c["ad"]):
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(c["kod"])),
                        ft.DataCell(ft.Text(c["ad"])),
                        ft.DataCell(ft.Text(c.get("telefon") or "")),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(ft.Icons.EDIT, tooltip="Düzenle", on_click=lambda e, comp=c: self._load_company(comp)),
                                    ft.IconButton(ft.Icons.DELETE, tooltip="Sil", icon_color=ft.Colors.RED, on_click=lambda e, comp=c: self._on_delete_company_click(comp)),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )
        self.company_table.rows = rows
        if is_mounted(self.company_table):
            self.company_table.update()

    def _load_company(self, c: dict) -> None:
        self.company_edit_id = c["id"]
        self.company_kod.value = c["kod"]
        self.company_ad.value = c["ad"]
        self.company_tel.value = c.get("telefon") or ""
        if self.page:
            self.page.update()

    def _clear_company_form(self) -> None:
        self.company_edit_id = None
        self.company_kod.value = ""
        self.company_ad.value = ""
        self.company_tel.value = ""
        if self.page:
            self.page.update()

    def _on_company_save_click(self, e) -> None:
        self.page.run_task(self._save_company)

    async def _save_company(self) -> None:
        kod = (self.company_kod.value or "").strip().upper()
        ad = (self.company_ad.value or "").strip()
        if not kod or not ad:
            self._snack("Firma kodu ve adı zorunludur.")
            return
        company = {
            "id": self.company_edit_id or _new_id(),
            "kod": kod,
            "ad": ad,
            "telefon": (self.company_tel.value or "").strip(),
            "eposta": "",
            "adres": "",
        }
        self.on_saving(True)
        try:
            await asyncio.to_thread(self.state.db.save_all_data, companies=[company])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Firma kaydedilemedi: {exc}")
            self.on_saving(False)
            return
        self.on_saving(False)
        self._clear_company_form()
        self.on_data_refreshed()

    def _on_delete_company_click(self, c: dict) -> None:
        if any(s.get("sirketKodu") == c["kod"] for s in self.state.sales):
            self._snack(f"'{c['ad']}' firmasına ait satış kayıtları var, önce onları silin/taşıyın.")
            return
        self._confirm(
            f"'{c['ad']}' firmasını silmek istiyor musunuz?",
            lambda: self.page.run_task(self._delete_company, c),
        )

    async def _delete_company(self, c: dict) -> None:
        self.on_saving(True)
        try:
            await asyncio.to_thread(self.state.db.save_all_data, deleted_company_ids=[c["id"]])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Firma silinemedi: {exc}")
            self.on_saving(False)
            return
        self.on_saving(False)
        self.on_data_refreshed()

    # -- Satış Listesi -------------------------------------------------------

    def _refresh_sales_list(self) -> None:
        query = (self.sales_search.value or "").strip().lower()
        rows_data = [
            s
            for s in self.state.sales
            if not query
            or query in (s.get("id") or "").lower()
            or query in (s.get("sirketAdi") or "").lower()
            or query in (s.get("urunAdi") or "").lower()
        ]
        rows_data.sort(key=lambda s: s.get("irsaliyeTarihi") or "", reverse=True)

        rows = []
        for s in rows_data:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(s.get("id") or "")),
                        ft.DataCell(ft.Text(s.get("sirketAdi") or "")),
                        ft.DataCell(ft.Text(s.get("urunAdi") or "")),
                        ft.DataCell(ft.Text(f"{format_number(s.get('miktarTeneke'))} T / {format_number(s.get('miktarKg'))} Kg")),
                        ft.DataCell(ft.Text(f"₺{format_number(s.get('tutar'))}")),
                        ft.DataCell(ft.Text(format_date_tr(s.get("irsaliyeTarihi")))),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(ft.Icons.QR_CODE, tooltip="QR Fiş", on_click=lambda e, sale=s: self._show_qr_dialog(sale)),
                                    ft.IconButton(ft.Icons.DELETE, tooltip="Sil", icon_color=ft.Colors.RED, on_click=lambda e, sale=s: self._on_delete_sale_click(sale)),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )
        self.sales_table.rows = rows
        if is_mounted(self.sales_table):
            self.sales_table.update()

    def _show_qr_dialog(self, sale: dict) -> None:
        code = sale.get("id") or ""
        png_bytes = _qr_png_bytes(code)
        details = [
            ("Firma", sale.get("sirketAdi") or ""),
            ("Ürün", sale.get("urunAdi") or ""),
            ("Plaka", sale.get("aracPlakasi") or ""),
            ("Miktar", f"{format_number(sale.get('miktarTeneke'))} T / {format_number(sale.get('miktarKg'))} Kg"),
            ("Tutar", f"₺{format_number(sale.get('tutar'))}"),
        ]

        def close_dialog(e) -> None:
            dialog.open = False
            if is_mounted(dialog):
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Satış Fişi — {code}"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Image(src=png_bytes, width=220, height=220),
                        ft.Text(code, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN, selectable=True),
                        *[ft.Row([ft.Text(f"{k}:", weight=ft.FontWeight.BOLD), ft.Text(v)]) for k, v in details],
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                width=300,
            ),
            actions=[ft.TextButton("Kapat", on_click=close_dialog)],
        )
        if self.page:
            self.page.show_dialog(dialog)

    def _on_delete_sale_click(self, sale: dict) -> None:
        self._confirm(
            f"'{sale.get('id')}' satışını silmek istiyor musunuz?",
            lambda: self.page.run_task(self._delete_sale, sale),
        )

    async def _delete_sale(self, sale: dict) -> None:
        # İlişkili Defter kaydının bağlantısını kaldır (satisId korunur, tekrar
        # işlenebilsin diye) — PySide6 sürümüyle birebir aynı davranış.
        linked_record = next(
            (r for r in self.state.records if r.get("linkedSaleId") == sale["id"] or r.get("satisId") == sale["id"]),
            None,
        )
        self.on_saving(True)
        try:
            if linked_record:
                updated = {**linked_record, "linkedSaleId": None}
                await asyncio.to_thread(self.state.db.save_all_data, records=[updated], deleted_sale_ids=[sale["id"]])
            else:
                await asyncio.to_thread(self.state.db.save_all_data, deleted_sale_ids=[sale["id"]])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Satış silinemedi: {exc}")
            self.on_saving(False)
            return
        self.on_saving(False)
        self.on_data_refreshed()

    # -- Ortak yardımcılar -----------------------------------------------

    def _confirm(self, message: str, on_yes) -> None:
        def close_dialog(e) -> None:
            dialog.open = False
            if is_mounted(dialog):
                dialog.update()

        def yes_clicked(e) -> None:
            close_dialog(e)
            on_yes()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Emin misiniz?"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Vazgeç", on_click=close_dialog),
                ft.FilledButton("Evet", on_click=yes_clicked),
            ],
        )
        if self.page:
            self.page.show_dialog(dialog)

    def _snack(self, msg: str) -> None:
        if self.page:
            self.page.show_dialog(ft.SnackBar(ft.Text(msg)))
