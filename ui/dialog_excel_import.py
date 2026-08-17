"""Excel/CSV İçe Aktarma diyaloğu — herhangi bir Excel (.xlsx) ya da CSV
dosyasını Kayıt Defteri / Firmalar / Satışlar tablolarından birine aktarır.
Tabloya özel bir kod değil; tek genel bir akış:

    dosya seç → hedef tablo seç → sütunları eşleştir (otomatik öneri +
    elle düzeltme) → önizle → onayla → tek round-trip'te yaz

Sütun eşleştirmesi elle onaylanmadan hiçbir veri yazılmaz — otomatik öneri
sadece bir başlangıç noktası, sessizce yanlış eşleşme riski yok. Excel'de
`id` sütunu mevcut bir kayıtla eşleşirse GÜNCELLEME, eşleşmezse (ya da hiç
eşlenmezse) YENİ KAYIT olarak eklenir — `core/db_core.py`'nin upsert
modeliyle birebir aynı."""

from __future__ import annotations

import csv
import io
import time
import uuid

import flet as ft
import openpyxl

from core.app_state import AppState
from core.db_core import COMPANY_COLUMNS, RECORD_COLUMNS, SALE_COLUMNS
from core.models import new_company_defaults, new_record_defaults, new_sale_defaults
from ui.util import is_mounted, responsive_width


def _new_id() -> str:
    return f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"


# Hedef tablo tanımları: (görünen ad, sütun listesi, boş-satır varsayılanı)
_TARGETS: dict[str, tuple[str, list[str], "callable"]] = {
    "records": ("Kayıt Defteri (üretim / fire / satış / stok kayıtları — ürün tanımları da dahil)", RECORD_COLUMNS, new_record_defaults),
    "companies": ("Firmalar", COMPANY_COLUMNS, new_company_defaults),
    "sales": ("Satışlar", SALE_COLUMNS, new_sale_defaults),
}

_NUMERIC_FIELDS = {
    "records": {
        "uretimKg", "uretimTeneke", "uretimAdet", "fireKg", "fireTeneke", "fireAdet",
        "satisKg", "satisTeneke", "satisAdet",
        "baslangicStokKg", "baslangicStokTeneke", "baslangicStokAdet",
        "bitisStokKg", "bitisStokTeneke", "bitisStokAdet",
        "fiyatTeneke", "fiyatKg", "fiyatAdet",
    },
    "companies": set(),
    "sales": {"miktarTeneke", "miktarKg", "miktarAdet", "fiyatTeneke", "fiyatKg", "fiyatAdet", "tutar"},
}

_BOOL_FIELDS = {"manualBaslangicStok", "baslangicStokKilitli"}

# En az biri dolu olmayan satırlar atlanır (zorunlu alan kontrolü).
_REQUIRED_ANY = {
    "records": ["urunKodu", "urunAdi"],
    "companies": ["ad"],
    "sales": ["urunAdi", "sirketAdi"],
}

_SKIP = "— (bu sütunu içe aktarma) —"


def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    for a, b in {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c", "i̇": "i"}.items():
        s = s.replace(a, b)
    return "".join(ch for ch in s if ch.isalnum())


# Bazı yaygın Türkçe/İngilizce başlıklar normalize edilse bile alan adıyla
# örtüşmüyor (ör. "Barkod" vs "barcode") — bunlar için küçük bir eş anlamlı
# sözlüğü, genel substring eşleştirmesinden ÖNCE denenir.
_SYNONYMS = {
    "barkod": "barcode",
    "urunbarkodu": "barcode",
    # Genel Tablo'nun kendi CSV export'u "Firma Kodu/Adı" başlıklarını
    # kullanıyor ama Satışlar tablosundaki alanlar "sirketKodu/sirketAdi" —
    # bu yüzden export edilip Excel'de düzenlenip geri içe aktarılan bir
    # dosya, ekstra elle düzeltmeye gerek kalmadan otomatik eşleşsin diye.
    "firmakodu": "sirketKodu",
    "firmaadi": "sirketAdi",
}


def _best_match(header: str, columns: list[str]) -> str | None:
    norm_header = _normalize(header)
    if not norm_header:
        return None
    alias = _SYNONYMS.get(norm_header)
    if alias and alias in columns:
        return alias
    for c in columns:
        if _normalize(c) == norm_header:
            return c
    for c in columns:
        nc = _normalize(c)
        if nc and (nc in norm_header or norm_header in nc):
            return c
    return None


def _to_number(raw) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def _to_bool(raw) -> bool:
    return str(raw).strip().lower() in ("1", "true", "evet", "yes", "doğru", "dogru", "x")


def _decode_csv_bytes(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def parse_file(filename: str, data: bytes) -> tuple[list[str], list[list]]:
    """Dosya adına göre .xlsx ya da .csv olarak ayrıştırır; (başlıklar,
    satırlar) döndürür. İlk sayfa/tüm satırlar kullanılır."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        ws = wb.worksheets[0]
        rows_iter = ws.iter_rows(values_only=True)
        header = [("" if h is None else str(h)) for h in next(rows_iter, ())]
        rows = [list(r) for r in rows_iter if any(v is not None and str(v).strip() != "" for v in r)]
        return header, rows

    text = _decode_csv_bytes(data)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    all_rows = list(csv.reader(io.StringIO(text), dialect))
    if not all_rows:
        return [], []
    header, *rows = all_rows
    rows = [r for r in rows if any((v or "").strip() for v in r)]
    return header, rows


class ExcelImportDialog:
    def __init__(self, page: ft.Page, state: AppState, on_saved=None):
        self.page = page
        self.state = state
        self.on_saved = on_saved or (lambda: None)

        self.file_picker = ft.FilePicker()
        if self.page:
            self.page.services.append(self.file_picker)

        self._filename: str = ""
        self._headers: list[str] = []
        self._rows: list[list] = []
        self._mapping_dropdowns: dict[str, ft.Dropdown] = {}  # excel başlığı -> Dropdown

        self.target_dropdown = ft.Dropdown(
            label="Hedef Tablo",
            width=responsive_width(page, 420),
            options=[ft.DropdownOption(key=key, text=label) for key, (label, _, _) in _TARGETS.items()],
        )
        self.file_status = ft.Text("Henüz dosya seçilmedi.", size=12, italic=True)
        self.pick_btn = ft.OutlinedButton(
            "Dosya Seç (.xlsx / .csv)", icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.page.run_task(self._pick_file),
        )
        self.mapping_column = ft.Column([], spacing=6, scroll=ft.ScrollMode.AUTO, height=220)
        self.preview_table = ft.DataTable(columns=[ft.DataColumn(ft.Text(""))], rows=[])
        self.summary_text = ft.Text("", size=12)
        self.status_text = ft.Text("", size=12)

        self.map_btn = ft.FilledButton(
            "Sütunları Eşleştir", icon=ft.Icons.SYNC_ALT, on_click=lambda e: self._build_mapping()
        )
        self.preview_btn = ft.OutlinedButton(
            "Önizle", icon=ft.Icons.VISIBILITY, on_click=lambda e: self._build_preview()
        )
        self.import_btn = ft.FilledButton(
            "İçe Aktar", icon=ft.Icons.SAVE_ALT,
            on_click=lambda e: self.page.run_task(self._do_import),
            disabled=True,
        )

        self.body = ft.Column(
            [
                ft.Text(
                    "Bir Excel/CSV dosyası seçip hangi tabloya (Kayıt Defteri / "
                    "Firmalar / Satışlar) aktarılacağını belirleyin. Sütun "
                    "eşleştirmesi otomatik önerilir, onaylamadan hiçbir veri "
                    "yazılmaz.",
                    size=12,
                ),
                ft.Row([self.pick_btn, self.file_status], wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.target_dropdown,
                self.map_btn,
                ft.Text("Sütun Eşleştirme:", weight=ft.FontWeight.BOLD, size=12),
                self.mapping_column,
                ft.Row([self.preview_btn, self.import_btn]),
                self.summary_text,
                ft.Text("Önizleme (ilk 5 satır):", weight=ft.FontWeight.BOLD, size=12),
                ft.Row([self.preview_table], scroll=ft.ScrollMode.AUTO, expand=True),
                self.status_text,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Excel / CSV İçe Aktar"),
            content=ft.Container(self.body, width=responsive_width(page, 680), height=560),
            actions=[ft.TextButton("Kapat", on_click=self._close)],
        )

    def open(self) -> None:
        if self.page:
            self.page.show_dialog(self.dialog)

    def _close(self, e) -> None:
        self.dialog.open = False
        if is_mounted(self.dialog):
            self.dialog.update()

    # -- 1. Dosya seçimi --------------------------------------------------

    async def _pick_file(self) -> None:
        files = await self.file_picker.pick_files(
            dialog_title="İçe aktarılacak Excel/CSV dosyasını seçin",
            allowed_extensions=["xlsx", "xlsm", "csv"],
            with_data=True,
        )
        if not files or not files[0].bytes:
            return
        self._filename = files[0].name
        try:
            self._headers, self._rows = parse_file(self._filename, files[0].bytes)
        except Exception as exc:  # noqa: BLE001
            self.file_status.value = f"Dosya okunamadı: {exc}"
            self.file_status.color = ft.Colors.RED
            if is_mounted(self.file_status):
                self.file_status.update()
            return
        self.file_status.value = f"'{self._filename}' — {len(self._headers)} sütun, {len(self._rows)} satır bulundu."
        self.file_status.color = ft.Colors.GREEN
        self.mapping_column.controls = []
        self.import_btn.disabled = True
        if is_mounted(self.file_status):
            self.file_status.update()
        if is_mounted(self.mapping_column):
            self.mapping_column.update()
        if is_mounted(self.import_btn):
            self.import_btn.update()

    # -- 2. Sütun eşleştirme ------------------------------------------------

    def _target_columns(self) -> list[str]:
        target = self.target_dropdown.value
        if not target or target not in _TARGETS:
            return []
        return _TARGETS[target][1]

    def _build_mapping(self) -> None:
        if not self._headers:
            self._set_status("Önce bir dosya seçin.", error=True)
            return
        if not self.target_dropdown.value:
            self._set_status("Önce hedef tabloyu seçin.", error=True)
            return

        columns = self._target_columns()
        self._mapping_dropdowns = {}
        rows: list[ft.Control] = []
        for header in self._headers:
            suggestion = _best_match(header, columns) or _SKIP
            dd = ft.Dropdown(
                width=responsive_width(self.page, 260, margin=140),
                value=suggestion,
                options=[ft.DropdownOption(key=_SKIP, text=_SKIP)]
                + [ft.DropdownOption(key=c, text=c) for c in columns],
            )
            self._mapping_dropdowns[header] = dd
            rows.append(
                ft.Row(
                    [ft.Container(ft.Text(header, size=12), width=responsive_width(self.page, 220, margin=180)), ft.Icon(ft.Icons.ARROW_FORWARD, size=14), dd],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                )
            )
        self.mapping_column.controls = rows
        self._set_status(f"{len(self._headers)} sütun için eşleştirme önerildi — gerekirse düzeltip 'Önizle'ye basın.", error=False)
        if is_mounted(self.mapping_column):
            self.mapping_column.update()

    def _current_mapping(self) -> dict[str, str]:
        """Excel başlığı -> hedef alan adı (sadece '(Atla)' olmayanlar)."""
        return {h: dd.value for h, dd in self._mapping_dropdowns.items() if dd.value and dd.value != _SKIP}

    # -- 3. Satır dönüştürme (UI'dan bağımsız, test edilebilir) -------------

    def build_rows(self) -> tuple[list[dict], int]:
        """(hazır satır listesi, atlanan satır sayısı) döndürür."""
        target = self.target_dropdown.value
        if not target or target not in _TARGETS:
            return [], 0
        _, columns, make_default = _TARGETS[target]
        mapping = self._current_mapping()
        numeric_fields = _NUMERIC_FIELDS.get(target, set())
        required_any = _REQUIRED_ANY.get(target, [])
        header_index = {h: i for i, h in enumerate(self._headers)}

        out: list[dict] = []
        skipped = 0
        for raw_row in self._rows:
            row = make_default()
            row["id"] = ""  # eşleştirmede id varsa aşağıda üzerine yazılır
            for header, field in mapping.items():
                idx = header_index.get(header)
                if idx is None or idx >= len(raw_row):
                    continue
                value = raw_row[idx]
                if field in _BOOL_FIELDS:
                    row[field] = _to_bool(value)
                elif field in numeric_fields:
                    row[field] = _to_number(value)
                else:
                    row[field] = "" if value is None else str(value).strip()

            if not any((row.get(f) or "").strip() if isinstance(row.get(f), str) else row.get(f) for f in required_any):
                skipped += 1
                continue

            if not row.get("id"):
                row["id"] = _new_id()
            out.append(row)
        return out, skipped

    def _build_preview(self) -> None:
        if not self._mapping_dropdowns:
            self._set_status("Önce 'Sütunları Eşleştir'e basın.", error=True)
            return
        rows, skipped = self.build_rows()
        mapped_fields = sorted(set(self._current_mapping().values()))

        self.preview_table.columns = [ft.DataColumn(ft.Text(f, size=11)) for f in mapped_fields] or [ft.DataColumn(ft.Text(""))]
        self.preview_table.rows = [
            ft.DataRow(cells=[ft.DataCell(ft.Text(str(r.get(f, ""))[:24], size=11)) for f in mapped_fields])
            for r in rows[:5]
        ]
        self.summary_text.value = (
            f"Toplam {len(self._rows)} satırdan {len(rows)}'i içe aktarılacak, "
            f"{skipped} satır zorunlu alan (ör. ürün adı/kodu ya da firma adı) "
            f"boş olduğu için atlanacak."
        )
        self.summary_text.color = ft.Colors.GREEN if rows else ft.Colors.RED
        self.import_btn.disabled = not rows
        self._set_status("", error=False)
        if is_mounted(self.preview_table):
            self.preview_table.update()
        if is_mounted(self.summary_text):
            self.summary_text.update()
        if is_mounted(self.import_btn):
            self.import_btn.update()

    # -- 4. Onayla ve tek seferde yaz ---------------------------------------

    async def _do_import(self) -> bool:
        target = self.target_dropdown.value
        rows, skipped = self.build_rows()
        if not rows:
            self._set_status("İçe aktarılacak satır yok.", error=True)
            return False
        try:
            import asyncio

            if target == "records":
                await asyncio.to_thread(self.state.db.save_all_data, records=rows)
            elif target == "companies":
                await asyncio.to_thread(self.state.db.save_all_data, companies=rows)
            elif target == "sales":
                await asyncio.to_thread(self.state.db.save_all_data, sales=rows)
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"İçe aktarılamadı: {exc}", error=True)
            return False

        self._set_status(f"{len(rows)} satır başarıyla içe aktarıldı ({skipped} satır atlandı).", error=False)
        self.on_saved()
        return True

    def _set_status(self, msg: str, *, error: bool) -> None:
        self.status_text.value = msg
        self.status_text.color = ft.Colors.RED if error else ft.Colors.GREEN
        if is_mounted(self.status_text):
            self.status_text.update()
