"""Barkod / Ürün Eşleştirme diyaloğu — PySide6 sürümündeki
dialog_barcode_mapper.py'nin Flet karşılığı. Ürün tanımlama, fiyat, ve
başlangıç stoğu girme/kilitleme mantığı web/PySide6 sürümüyle birebir aynı.
Header'daki "Ürün / Barkod Eşleştirme" butonundan açılan bir AlertDialog."""

from __future__ import annotations

import asyncio
import time
import uuid

import flet as ft

from core.app_state import AppState
from core.stock_logic import calculate_ending_stock, format_number, recalculate_product_stock_chain
from ui.util import is_mounted, responsive_width


def _new_id() -> str:
    return f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"


def _num_field(label: str, width: int = 150) -> ft.TextField:
    return ft.TextField(label=label, value="0", width=width, keyboard_type=ft.KeyboardType.NUMBER)


def _num(tf: ft.TextField) -> float:
    try:
        return float((tf.value or "0").replace(",", "."))
    except ValueError:
        return 0.0


class BarcodeMapperDialog:
    def __init__(self, page: ft.Page, state: AppState, on_saved=None):
        self.page = page
        self.state = state
        self.on_saved = on_saved or (lambda: None)
        self.selected_code: str | None = None

        self.app_id_field = ft.TextField(label="App İçi Ürün ID / Kodu", width=280)
        self.name_field = ft.TextField(label="Ürün Adı", width=280)
        self.barcode_field = ft.TextField(label="Fiziksel Barkod / QR", width=280)
        self.price_kg = _num_field("Kilo Fiyatı (₺/Kg)")
        self.price_teneke = _num_field("Teneke Fiyatı (₺/Teneke)")
        self.price_adet = _num_field("Adet Fiyatı (₺/Adet)")
        self.stock_teneke = _num_field("Teneke")
        self.stock_kg = _num_field("Kg")
        self.stock_adet = _num_field("Adet")
        self.lock_notice = ft.Text("", color=ft.Colors.AMBER, size=12)
        self.search_field = ft.TextField(
            label="Ürün veya barkod ara...", width=560, on_change=lambda e: self._refresh_list()
        )
        self.list_column = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO, height=180)
        self.status_text = ft.Text("", size=12)

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Barkod - App İçi ID Eşleştirme & Birleştirme"),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text("Yeni Barkod / ID Birleştirme", weight=ft.FontWeight.BOLD),
                        ft.Row([self.app_id_field, self.name_field], wrap=True),
                        self.barcode_field,
                        ft.Row([self.price_kg, self.price_teneke, self.price_adet], wrap=True),
                        ft.Text(
                            "Başlangıç Stoğu (opsiyonel — girilirse Üretim Kayıt "
                            "Defteri'nde bu ürün için başlangıç stoğu alanı kilitlenir)",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Row([self.stock_teneke, self.stock_kg, self.stock_adet], wrap=True),
                        self.lock_notice,
                        self.status_text,
                        ft.Divider(),
                        ft.Text("Kayıtlı Ürün ve Barkod Listesi", weight=ft.FontWeight.BOLD),
                        self.search_field,
                        self.list_column,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=responsive_width(page, 600),
                height=560,
            ),
            actions=[
                ft.OutlinedButton("Temizle", icon=ft.Icons.CLEAR, on_click=lambda e: self._clear_form()),
                ft.TextButton("Kapat", on_click=self._close),
                ft.FilledButton(
                    "Eşleştirmeyi Kaydet", icon=ft.Icons.SAVE, on_click=lambda e: self.page.run_task(self._on_save_click)
                ),
            ],
        )
        self._refresh_list()

    def open(self) -> None:
        if self.page:
            self.page.show_dialog(self.dialog)

    def _close(self, e) -> None:
        self.dialog.open = False
        if is_mounted(self.dialog):
            self.dialog.update()

    # -- Yardımcılar ---------------------------------------------------

    def _unique_products(self) -> dict[str, dict]:
        products: dict[str, dict] = {}
        for r in self.state.records:
            code = r["urunKodu"].strip().upper()
            existing = products.get(code)
            if not existing:
                products[code] = {
                    "urunKodu": code,
                    "urunAdi": r["urunAdi"],
                    "barcode": r.get("barcode") or code,
                    "fiyatKg": r.get("fiyatKg") or 0,
                    "fiyatTeneke": r.get("fiyatTeneke") or 0,
                    "fiyatAdet": r.get("fiyatAdet") or 0,
                }
            else:
                if r.get("barcode"):
                    existing["barcode"] = r["barcode"]
                if r.get("fiyatKg"):
                    existing["fiyatKg"] = r["fiyatKg"]
                if r.get("fiyatTeneke"):
                    existing["fiyatTeneke"] = r["fiyatTeneke"]
                if r.get("fiyatAdet"):
                    existing["fiyatAdet"] = r["fiyatAdet"]
        return products

    def _earliest_record(self, code: str) -> dict | None:
        clean = code.strip().upper()
        matches = [r for r in self.state.records if r["urunKodu"].strip().upper() == clean]
        if not matches:
            return None
        return sorted(matches, key=lambda r: (r.get("tarih") or "", r.get("id") or ""))[0]

    def _refresh_list(self) -> None:
        query = (self.search_field.value or "").strip().lower()
        rows = []
        for code, p in sorted(self._unique_products().items(), key=lambda kv: kv[1]["urunAdi"]):
            if query and query not in p["urunAdi"].lower() and query not in code.lower() and query not in p["barcode"].lower():
                continue
            rows.append(
                ft.ListTile(
                    title=ft.Text(f"{p['urunAdi']} ({code})"),
                    subtitle=ft.Text(
                        f"Barkod: {p['barcode']} — ₺{format_number(p['fiyatKg'])}/Kg, ₺{format_number(p['fiyatTeneke'])}/Teneke"
                    ),
                    on_click=lambda e, c=code: self._on_list_item_click(c),
                    dense=True,
                )
            )
        self.list_column.controls = rows or [ft.Text("Kayıt yok.", italic=True, size=12)]
        if is_mounted(self.list_column):
            self.list_column.update()

    def _on_list_item_click(self, code: str) -> None:
        products = self._unique_products()
        p = products.get(code)
        if not p:
            return
        self.selected_code = code
        self.app_id_field.value = p["urunKodu"]
        self.name_field.value = p["urunAdi"]
        self.barcode_field.value = p["barcode"]
        self.price_kg.value = str(p["fiyatKg"])
        self.price_teneke.value = str(p["fiyatTeneke"])
        self.price_adet.value = str(p["fiyatAdet"])

        earliest = self._earliest_record(code)
        locked = bool(earliest and earliest.get("baslangicStokKilitli"))
        if locked:
            self.stock_teneke.value = str(earliest.get("baslangicStokTeneke") or 0)
            self.stock_kg.value = str(earliest.get("baslangicStokKg") or 0)
            self.stock_adet.value = str(earliest.get("baslangicStokAdet") or 0)
            self.lock_notice.value = (
                "Bu ürünün başlangıç stoğu zaten bu ekrandan kilitlenmiş. "
                "Değiştirip kaydederseniz Üretim ekranındaki değer de güncellenir."
            )
        else:
            self.stock_teneke.value = "0"
            self.stock_kg.value = "0"
            self.stock_adet.value = "0"
            self.lock_notice.value = ""
        if self.page:
            self.page.update()

    def _clear_form(self) -> None:
        self.selected_code = None
        self.app_id_field.value = ""
        self.name_field.value = ""
        self.barcode_field.value = ""
        for tf in (self.price_kg, self.price_teneke, self.price_adet, self.stock_teneke, self.stock_kg, self.stock_adet):
            tf.value = "0"
        self.lock_notice.value = ""
        self.status_text.value = ""
        if self.page:
            self.page.update()

    # -- Kaydetme (UI'dan bağımsız, test edilebilir) ------------------------

    def _on_save_click(self):
        return self._save()

    async def _save(self) -> bool:
        clean_app_id = (self.app_id_field.value or "").strip().upper()
        clean_name = (self.name_field.value or "").strip()
        clean_barcode = (self.barcode_field.value or "").strip()

        if not clean_app_id:
            self.status_text.value = "Lütfen bir App İçi Ürün ID / Kodu girin."
            if is_mounted(self.status_text):
                self.status_text.update()
            return False
        if not clean_name:
            self.status_text.value = "Lütfen bir Ürün Adı girin."
            if is_mounted(self.status_text):
                self.status_text.update()
            return False

        has_existing = any(r["urunKodu"].strip().upper() == clean_app_id for r in self.state.records)
        # Başlangıç stoğu alanlarından en az biri sıfırdan farklıysa "girildi"
        # say — tamamı boş/sıfır bırakılırsa mevcut kilit durumuna dokunulmaz.
        has_entered_stock = _num(self.stock_teneke) != 0 or _num(self.stock_kg) != 0 or _num(self.stock_adet) != 0

        if has_existing:
            earliest = self._earliest_record(clean_app_id)
            earliest_id = earliest["id"] if earliest else None
            updated_records = []
            for r in self.state.records:
                if r["urunKodu"].strip().upper() != clean_app_id:
                    updated_records.append(r)
                    continue
                updated = {
                    **r,
                    "urunAdi": clean_name,
                    "barcode": clean_barcode or clean_app_id,
                    "fiyatKg": _num(self.price_kg) or r.get("fiyatKg"),
                    "fiyatTeneke": _num(self.price_teneke) or r.get("fiyatTeneke"),
                    "fiyatAdet": _num(self.price_adet) or r.get("fiyatAdet"),
                }
                if r["id"] == earliest_id and has_entered_stock:
                    updated["baslangicStokTeneke"] = _num(self.stock_teneke)
                    updated["baslangicStokKg"] = _num(self.stock_kg)
                    updated["baslangicStokAdet"] = _num(self.stock_adet)
                    updated["baslangicStokKilitli"] = True
                updated_records.append(updated)

            if has_entered_stock:
                updated_records = recalculate_product_stock_chain(updated_records, clean_app_id)

            to_upsert = [r for r in updated_records if r["urunKodu"].strip().upper() == clean_app_id]
        else:
            base_record = {
                "id": _new_id(),
                "tarih": time.strftime("%Y-%m-%d"),
                "urunKodu": clean_app_id,
                "urunAdi": clean_name,
                "barcode": clean_barcode or clean_app_id,
                "uretimKg": 0, "uretimTeneke": 0, "uretimAdet": 0,
                "fireKg": 0, "fireTeneke": 0, "fireAdet": 0,
                "satisKg": 0, "satisTeneke": 0, "satisAdet": 0,
                "baslangicStokKg": _num(self.stock_kg),
                "baslangicStokTeneke": _num(self.stock_teneke),
                "baslangicStokAdet": _num(self.stock_adet),
                "fiyatTeneke": _num(self.price_teneke),
                "fiyatKg": _num(self.price_kg),
                "fiyatAdet": _num(self.price_adet),
                "baslangicStokKilitli": has_entered_stock,
                "satisId": "", "linkedSaleId": None, "manualBaslangicStok": False,
            }
            base_record.update(calculate_ending_stock(base_record))
            to_upsert = [base_record]

        try:
            await asyncio.to_thread(self.state.db.save_all_data, records=to_upsert)
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self.status_text.value = f"Eşleştirme kaydedilemedi: {exc}"
            self.status_text.color = ft.Colors.RED
            if is_mounted(self.status_text):
                self.status_text.update()
            return False

        self.status_text.value = f'"{clean_app_id}" - "{clean_name}" barkod eşleştirmesi güncellendi.'
        self.status_text.color = ft.Colors.GREEN
        if is_mounted(self.status_text):
            self.status_text.update()
        self._clear_form()
        self._refresh_list()
        self.on_saved()
        return True
