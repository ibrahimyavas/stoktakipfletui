"""İrsaliye Arşivi diyaloğu — PySide6 sürümündeki dialog_waybill_vault.py'nin
Flet karşılığı. Kamera yerine dosya seçiciyle fotoğraf ekleme (kullanıcı
kararı — bu proje kapsamında canlı kamera taraması bilinçli olarak kapsam
dışı bırakıldı), Gemini OCR ile otomatik alan doldurma, liste/arama/
görüntüle/sil."""

from __future__ import annotations

import asyncio
import base64
import re
import tempfile
import time
from pathlib import Path

import flet as ft

from core.app_state import AppState
from core.ocr import run_ocr
from core.stock_logic import format_date_tr, get_today_date_string
from ui.util import is_mounted, responsive_width


def _new_id() -> str:
    return f"IRS-{int(time.time() * 1000)}"


class WaybillVaultDialog:
    def __init__(self, page: ft.Page, state: AppState, gemini_api_key: str, on_saved=None):
        self.page = page
        self.state = state
        self.gemini_api_key = gemini_api_key
        self.on_saved = on_saved or (lambda: None)
        self._photo_bytes: bytes | None = None

        self.file_picker = ft.FilePicker()
        if self.page:
            self.page.services.append(self.file_picker)

        # -- Liste sekmesi ----------------------------------------------
        self.search_field = ft.TextField(
            label="İrsaliye no, firma, tarih veya not ara...", width=500,
            on_change=lambda e: self._refresh_list(),
        )
        self.list_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in ("İrsaliye No", "Firma", "Tarih", "Tutar", "İşlem")],
            rows=[],
        )

        # -- Ekleme sekmesi ---------------------------------------------
        self.photo_preview = ft.Container(
            content=ft.Text("Henüz fotoğraf seçilmedi.", italic=True),
            height=140,
            alignment=ft.Alignment(0, 0),
        )
        self.pick_photo_btn = ft.OutlinedButton(
            "Fotoğraf Seç...", icon=ft.Icons.ADD_A_PHOTO, on_click=lambda e: self.page.run_task(self._pick_photo)
        )
        self.ocr_status = ft.Text("", size=12, color=ft.Colors.GREY)
        self.irsaliye_no_field = ft.TextField(label="İrsaliye No", width=460)
        self.firma_field = ft.TextField(label="Firma", width=460)
        self.tarih_field = ft.TextField(label="Tarih", value=get_today_date_string(), width=460)
        self.tutar_field = ft.TextField(label="Tutar", value="0", width=460, keyboard_type=ft.KeyboardType.NUMBER)
        self.notlar_field = ft.TextField(label="Notlar", width=460)
        self.raw_text_view = ft.TextField(
            label="OCR ile Okunan Ham Metin", multiline=True, min_lines=3, max_lines=5, read_only=True, width=460
        )
        self.add_status_text = ft.Text("", size=12)

        add_tab = ft.Container(
            ft.Column(
                [
                    self.pick_photo_btn,
                    self.photo_preview,
                    self.ocr_status,
                    self.irsaliye_no_field,
                    self.firma_field,
                    self.tarih_field,
                    self.tutar_field,
                    self.notlar_field,
                    self.raw_text_view,
                    self.add_status_text,
                    ft.FilledButton("İrsaliyeyi Kaydet", icon=ft.Icons.SAVE, on_click=lambda e: self.page.run_task(self._save)),
                ],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=12,
        )
        list_tab = ft.Container(
            ft.Column(
                [self.search_field, ft.Row([self.list_table], scroll=ft.ScrollMode.AUTO, expand=True)],
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=12,
        )

        self.tabs = ft.Tabs(
            length=2,
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Kayıtlı İrsaliyeler", icon=ft.Icons.FOLDER),
                            ft.Tab(label="Yeni İrsaliye Fotoğrafı", icon=ft.Icons.ADD_A_PHOTO),
                        ]
                    ),
                    ft.TabBarView(controls=[list_tab, add_tab], height=460),
                ],
            ),
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("İrsaliye Arşivi"),
            content=ft.Container(self.tabs, width=responsive_width(page, 560), height=520),
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

    # -- Liste -------------------------------------------------------------

    def _refresh_list(self) -> None:
        query = (self.search_field.value or "").strip().lower()
        rows_data = [
            w
            for w in self.state.waybills
            if not query
            or query in (w.get("irsaliyeNo") or "").lower()
            or query in (w.get("firmaAdi") or "").lower()
            or query in (w.get("tarih") or "").lower()
            or query in (w.get("notlar") or "").lower()
            or query in (w.get("okunanMetin") or "").lower()
        ]
        rows_data.sort(key=lambda w: w.get("eklenmeTarihi") or "", reverse=True)

        rows = []
        for w in rows_data:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(w.get("irsaliyeNo") or "")),
                        ft.DataCell(ft.Text(w.get("firmaAdi") or "")),
                        ft.DataCell(ft.Text(format_date_tr(w.get("tarih")))),
                        ft.DataCell(ft.Text(str(w.get("tutar") or 0))),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(ft.Icons.VISIBILITY, tooltip="İncele", on_click=lambda e, item=w: self._view(item)),
                                    ft.IconButton(ft.Icons.DELETE, tooltip="Sil", icon_color=ft.Colors.RED, on_click=lambda e, item=w: self._on_delete_click(item)),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )
        self.list_table.rows = rows
        if is_mounted(self.list_table):
            self.list_table.update()

    def _view(self, item: dict) -> None:
        image_control: ft.Control
        try:
            _, b64data = (item.get("fotoUrl") or "").split(",", 1)
            image_control = ft.Image(src=base64.b64decode(b64data), width=460, fit=ft.BoxFit.CONTAIN)
        except (ValueError, IndexError):
            image_control = ft.Text("Görsel yok.", italic=True)

        def close_view(e) -> None:
            view_dialog.open = False
            if is_mounted(view_dialog):
                view_dialog.update()

        view_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(item.get("irsaliyeNo") or "İrsaliye"),
            content=ft.Container(
                ft.Column(
                    [
                        image_control,
                        ft.TextField(
                            value=item.get("okunanMetin") or "", multiline=True, min_lines=3, max_lines=8, read_only=True,
                        ),
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=480,
                height=420,
            ),
            actions=[ft.TextButton("Kapat", on_click=close_view)],
        )
        if self.page:
            self.page.show_dialog(view_dialog)

    def _on_delete_click(self, item: dict) -> None:
        self.page.run_task(self._delete, item)

    async def _delete(self, item: dict) -> None:
        try:
            await asyncio.to_thread(self.state.db.save_all_data, deleted_waybill_ids=[item["id"]])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self.add_status_text.value = f"Silinemedi: {exc}"
            if is_mounted(self.add_status_text):
                self.add_status_text.update()
            return
        self._refresh_list()
        self.on_saved()

    # -- Ekleme --------------------------------------------------------

    async def _pick_photo(self) -> None:
        # file_type=IMAGE (extension filtreleme yerine) Android'in kendi
        # sistem seçicisini tetikliyor — bu, "Kamera" seçeneğini de (CAMERA
        # izni verilmişse) sunuyor; ham uzantı filtresiyle sadece dosya
        # tarayıcısı açılıyor, kamera seçeneği hiç çıkmıyordu.
        files = await self.file_picker.pick_files(
            dialog_title="İrsaliye Fotoğrafı Seç", file_type=ft.FilePickerFileType.IMAGE, with_data=True
        )
        if not files or not files[0].bytes:
            return
        self._photo_bytes = files[0].bytes
        self.photo_preview.content = ft.Image(src=self._photo_bytes, height=140, fit=ft.BoxFit.CONTAIN)
        if is_mounted(self.photo_preview):
            self.photo_preview.update()

        self.ocr_status.value = "Yazı okunuyor (OCR)..."
        if is_mounted(self.ocr_status):
            self.ocr_status.update()

        # run_ocr() gerçek bir dosya yolu bekliyor (core/ocr.py — PySide6
        # sürümüyle birebir aynı, değiştirilmedi); FilePicker'dan gelen
        # bytes'ı geçici bir dosyaya yazıp yolunu veriyoruz. Bu sunucu
        # tarafında (web/Android istemcisinde bile Python her zaman gerçek
        # bir sunucuda çalışıyor) her zaman normal bir dosya sistemi olduğu
        # için güvenli.
        result = await self._run_ocr_via_tempfile(self._photo_bytes)
        self._on_ocr_done(result)

    async def _run_ocr_via_tempfile(self, photo_bytes: bytes) -> dict:
        def _run() -> dict:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(photo_bytes)
                tmp_path = tmp.name
            try:
                return run_ocr(tmp_path, "irsaliye", self.gemini_api_key)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        return await asyncio.to_thread(_run)

    def _on_ocr_done(self, result: dict) -> None:
        if result.get("error"):
            self.ocr_status.value = f"OCR hatası: {result['error']}"
            if is_mounted(self.ocr_status):
                self.ocr_status.update()
            return
        self.ocr_status.value = "OCR tamamlandı — boş alanlar otomatik dolduruldu."

        if not self.irsaliye_no_field.value and result.get("irsaliyeNo"):
            self.irsaliye_no_field.value = str(result["irsaliyeNo"])
        if not self.firma_field.value and result.get("firmaAdi"):
            self.firma_field.value = str(result["firmaAdi"])
        if self.tarih_field.value == get_today_date_string() and result.get("tarih"):
            normalized = str(result["tarih"]).replace(".", "-")
            if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
                self.tarih_field.value = normalized
        if self.tutar_field.value in ("", "0") and result.get("tutar"):
            self.tutar_field.value = str(result["tutar"])
        if not self.notlar_field.value and result.get("notlar"):
            self.notlar_field.value = str(result["notlar"])
        if result.get("metin"):
            self.raw_text_view.value = str(result["metin"])

        if self.page:
            self.page.update()

    async def _save(self, e=None) -> bool:
        if not self._photo_bytes:
            self.add_status_text.value = "Lütfen önce bir fotoğraf seçin."
            self.add_status_text.color = ft.Colors.RED
            if is_mounted(self.add_status_text):
                self.add_status_text.update()
            return False

        try:
            tutar = float((self.tutar_field.value or "0").replace(",", ".")) if self.tutar_field.value else 0
        except ValueError:
            tutar = 0

        photo_data_url = f"data:image/jpeg;base64,{base64.b64encode(self._photo_bytes).decode('ascii')}"
        item = {
            "id": _new_id(),
            "irsaliyeNo": (self.irsaliye_no_field.value or "").strip() or f"İRS-{int(time.time()) % 100000}",
            "firmaAdi": (self.firma_field.value or "").strip() or "Bilinmeyen Firma",
            "tarih": (self.tarih_field.value or "").strip() or get_today_date_string(),
            "tutar": tutar,
            "notlar": (self.notlar_field.value or "").strip(),
            "fotoUrl": photo_data_url,
            "okunanMetin": self.raw_text_view.value or "",
            "eklenmeTarihi": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        try:
            await asyncio.to_thread(self.state.db.save_all_data, waybills=[item])
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self.add_status_text.value = f"İrsaliye kaydedilemedi: {exc}"
            self.add_status_text.color = ft.Colors.RED
            if is_mounted(self.add_status_text):
                self.add_status_text.update()
            return False

        self.add_status_text.value = "İrsaliye arşive eklendi."
        self.add_status_text.color = ft.Colors.GREEN
        self._reset_add_form()
        self._refresh_list()
        self.on_saved()
        if self.page:
            self.page.update()
        return True

    def _reset_add_form(self) -> None:
        self._photo_bytes = None
        self.photo_preview.content = ft.Text("Henüz fotoğraf seçilmedi.", italic=True)
        self.ocr_status.value = ""
        self.irsaliye_no_field.value = ""
        self.firma_field.value = ""
        self.tarih_field.value = get_today_date_string()
        self.tutar_field.value = "0"
        self.notlar_field.value = ""
        self.raw_text_view.value = ""
