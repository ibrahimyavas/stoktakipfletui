"""Kayıt Defteri — ortak taban sınıfı. Üretim ve Satış rollerinin kendi
dashboard'ları (`ui/page_dashboard_uretim.py`, `ui/page_dashboard_satis.py`)
burayı miras alır; aralarındaki TEK fark hangi "miktar" sekmelerinin
görüneceğidir (`show_uretim_fire` / `show_satis` bayrakları). Kaydetme,
silme, stok zinciri, kilit, arama/tablo gibi tüm iş mantığı (rolden
bağımsız, PySide6 sürümüyle birebir aynı) burada tek yerde yaşıyor —
rol başına ayrı dosyada tekrar tekrar yazılmıyor.

Admin rolü de doğrudan bu sınıfı (her iki bayrak da açık) kullanıyor, çünkü
tüm alanlara erişimi var."""

from __future__ import annotations

import asyncio
import time
import uuid

import flet as ft

from core.app_state import AppState
from core.models import PROFILES, new_record_defaults
from core.stock_logic import (
    calculate_ending_stock,
    format_date_tr,
    format_number,
    generate_sale_id,
    get_previous_record,
    get_today_date_string,
    has_locked_starting_stock,
    recalculate_product_stock_chain,
)
from ui.util import is_mounted


def _new_id() -> str:
    return f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"


def _num_field(label: str, width: int = 110) -> ft.TextField:
    return ft.TextField(label=label, value="0", width=width, keyboard_type=ft.KeyboardType.NUMBER)


def _num(tf: ft.TextField) -> float:
    try:
        return float((tf.value or "0").replace(",", "."))
    except ValueError:
        return 0.0


class DashboardBase:
    def __init__(
        self,
        page: ft.Page,
        state: AppState,
        profile_role: str,
        on_saving=None,
        *,
        show_uretim_fire: bool,
        show_satis: bool,
    ):
        self.page = page
        self.state = state
        self.profile_role = profile_role
        self.on_saving = on_saving or (lambda saving: None)
        # Bu iki bayrak, eskiden dosyanın 5 farklı yerine dağılmış
        # "if profile_role in (...)" kontrollerinin yerini alıyor — Üretim
        # ve Satış dashboard'ları bunları sabit değer olarak veriyor, Admin
        # ikisini de açık veriyor.
        self.show_uretim_fire = show_uretim_fire
        self.show_satis = show_satis
        # Tek-rollü dashboard'lar (Üretim ya da Satış) kendi PROFILES rengini
        # alıyor; Admin (her iki bayrak da açık) iki ayrı miktar türünü tek
        # ekranda karıştırdığı için nötr kalıyor, kendi rengiyle işaretlenmiyor.
        single_role = show_uretim_fire != show_satis
        info = PROFILES.get(profile_role)
        self.accent_color = info.color if (single_role and info) else None
        self.dashboard_title = (
            f"{info.label} — Kayıt Ekle / Düzenle" if (single_role and info) else "Kayıt Ekle / Düzenle"
        )
        self.editing_id: str | None = None
        self._starting_stock_locked = False

        self.tarih = ft.TextField(label="Tarih", value=get_today_date_string(), width=160)
        self.urun_kodu = ft.TextField(label="Ürün Kodu", width=200, on_blur=self._on_urun_kodu_blur)
        self.urun_adi = ft.TextField(label="Ürün Adı", width=260)
        self.barcode = ft.TextField(label="Barkod", width=200)

        self.uretim_teneke, self.uretim_kg, self.uretim_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        self.fire_teneke, self.fire_kg, self.fire_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        self.satis_teneke, self.satis_kg, self.satis_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        self.satis_id = ft.TextField(label="Satış ID", width=200)
        self.baslangic_teneke, self.baslangic_kg, self.baslangic_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        self.fiyat_teneke, self.fiyat_kg, self.fiyat_adet = _num_field("Teneke"), _num_field("Kg"), _num_field("Adet")
        for tf in (
            self.uretim_teneke, self.uretim_kg, self.uretim_adet,
            self.fire_teneke, self.fire_kg, self.fire_adet,
            self.satis_teneke, self.satis_kg, self.satis_adet,
            self.baslangic_teneke, self.baslangic_kg, self.baslangic_adet,
        ):
            tf.on_change = self._refresh_ending_preview

        self.bitis_text = ft.Text("0 T / 0 Kg / 0 Ad", weight=ft.FontWeight.BOLD)
        self.lock_banner = ft.Text("", color=ft.Colors.AMBER, size=12, visible=False)

        self.product_dropdown = ft.Dropdown(
            label="Mevcut Ürünlerden Seç",
            options=[],
            on_select=self._on_product_dropdown_change,
            width=420,
        )

        self.search_field = ft.TextField(
            label="Ara (ürün adı, kodu veya barkod)", width=420, on_change=lambda e: self._refresh_table()
        )
        self.table = ft.DataTable(columns=self._table_columns(), rows=[])

        self.save_btn = ft.FilledButton("Kaydet", icon=ft.Icons.SAVE, on_click=self._on_save_click)
        self.cancel_btn = ft.OutlinedButton("İptal / Yeni Kayıt", icon=ft.Icons.REFRESH, on_click=lambda e: self._reset_form())

        self.form_body = self._build_form_body()

        title_row: ft.Control = ft.Text(self.dashboard_title, weight=ft.FontWeight.BOLD, color=self.accent_color)

        form_card = ft.Column(
            [
                title_row,
                self.product_dropdown,
                ft.ResponsiveRow(
                    [
                        ft.Container(self.tarih, col={"sm": 6, "md": 3}),
                        ft.Container(self.urun_kodu, col={"sm": 6, "md": 3}),
                        ft.Container(self.urun_adi, col={"sm": 6, "md": 3}),
                        ft.Container(self.barcode, col={"sm": 6, "md": 3}),
                    ]
                ),
                self.form_body,
                self.lock_banner,
                ft.Row([self.save_btn, self.cancel_btn]),
            ],
            spacing=10,
        )
        card_container = ft.Container(form_card, padding=16)
        if self.accent_color:
            # Tek-rollü dashboard'ları (Üretim/Satış) birbirinden görsel
            # olarak ayırmak için PROFILES'teki rol rengiyle sol kenarlık —
            # aynı renk zaten üst başlıkta ve rol rozetinde de kullanılıyor.
            card_container.border = ft.Border(left=ft.BorderSide(4, self.accent_color))

        self.control = ft.Column(
            [
                ft.Card(content=card_container),
                ft.Container(height=8),
                self.search_field,
                # Tabloyu yatay kaydırılabilir bir Row'a sarmadan, dar
                # (telefon) ekranlarda sütunların bir kısmı görünmeden
                # kırpılıyordu — gerçek bir Android cihazda test edilerek
                # bulundu. scroll=AUTO burada güvenli (wrap=True DEĞİL —
                # o, expand=True bir Column'a komşuyken ayrı, bilinen bir
                # Flet hatasına yol açıyordu, bkz. header'daki not).
                ft.Row([self.table], scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self._refresh_product_dropdown()
        self._refresh_table()

    # -- Form gövdesi ------------------------------------------------------

    def _triple_row(self, teneke, kg, adet) -> ft.Row:
        return ft.Row([teneke, kg, adet], wrap=True)

    def _uretim_fire_section(self) -> ft.Control:
        return ft.Row(
            [
                ft.Column([ft.Text("Üretim Miktarı", weight=ft.FontWeight.BOLD), self._triple_row(self.uretim_teneke, self.uretim_kg, self.uretim_adet)]),
                ft.Column([ft.Text("Fire / Wastage", weight=ft.FontWeight.BOLD), self._triple_row(self.fire_teneke, self.fire_kg, self.fire_adet)]),
            ],
            wrap=True,
            spacing=24,
        )

    def _satis_section(self) -> ft.Control:
        return ft.Column(
            [
                ft.Text("Satış Miktarı", weight=ft.FontWeight.BOLD),
                self._triple_row(self.satis_teneke, self.satis_kg, self.satis_adet),
                self.satis_id,
            ]
        )

    def _stok_fiyat_section(self) -> ft.Control:
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Başlangıç Stoğu", weight=ft.FontWeight.BOLD), self._triple_row(self.baslangic_teneke, self.baslangic_kg, self.baslangic_adet)]),
                        ft.Column([ft.Text("Bitiş Stoğu (otomatik)", weight=ft.FontWeight.BOLD), self.bitis_text]),
                    ],
                    wrap=True,
                    spacing=24,
                ),
                ft.Text("Fiyat (₺)", weight=ft.FontWeight.BOLD),
                self._triple_row(self.fiyat_teneke, self.fiyat_kg, self.fiyat_adet),
            ]
        )

    def _build_form_body(self) -> ft.Control:
        # Admin her iki miktar türünü de görüyor (3 bölüm) — bunları
        # sekmelere ayırmak (yanlışlıkla üretim yaparken satış girmek gibi
        # karışıklıkları önlemek için) hâlâ mantıklı. Tek-rollü Üretim/Satış
        # dashboard'larında ise sadece 2 bölüm var (kendi miktar türü +
        # Stok&Fiyat); bunları sekme arkasına gizlemek yerine tek ekranda,
        # art arda göstermek daha az tıklama gerektiriyor ve her şeyi bir
        # bakışta gösteriyor.
        if self.show_uretim_fire and self.show_satis:
            return self._build_tabs()
        return self._build_flat_form()

    def _build_flat_form(self) -> ft.Control:
        sections: list[ft.Control] = []
        if self.show_uretim_fire:
            sections.append(self._uretim_fire_section())
        if self.show_satis:
            sections.append(self._satis_section())
        sections.append(ft.Divider())
        sections.append(ft.Text("Stok & Fiyat", weight=ft.FontWeight.BOLD, color=self.accent_color))
        sections.append(self._stok_fiyat_section())
        return ft.Column(sections, spacing=12)

    def _build_tabs(self) -> ft.Tabs:
        # Not: yeni Flet sürümünde ft.Tab sadece başlığı temsil ediyor —
        # içerik ayrı bir ft.TabBarView ile eşleştiriliyor (ft.Tabs içinde
        # ft.Column([TabBar(...), TabBarView(...)]) olarak). Eski
        # "Tab(text=..., content=...)" deseni artık çalışmıyor.
        tab_headers: list[ft.Tab] = []
        tab_bodies: list[ft.Control] = []

        if self.show_uretim_fire:
            tab_headers.append(ft.Tab(label="Üretim / Fire", icon=ft.Icons.PRECISION_MANUFACTURING))
            tab_bodies.append(
                ft.Container(ft.Column([self._uretim_fire_section()], scroll=ft.ScrollMode.AUTO), padding=12)
            )
        if self.show_satis:
            tab_headers.append(ft.Tab(label="Satış", icon=ft.Icons.SELL))
            tab_bodies.append(
                ft.Container(ft.Column([self._satis_section()], scroll=ft.ScrollMode.AUTO), padding=12)
            )
        tab_headers.append(ft.Tab(label="Stok & Fiyat", icon=ft.Icons.INVENTORY_2))
        tab_bodies.append(
            ft.Container(ft.Column([self._stok_fiyat_section()], scroll=ft.ScrollMode.AUTO), padding=12)
        )

        # Not: TabBarView'a sınırsız (unbounded) yükseklikte bir Column
        # içinde yer verilince Flutter "height is unbounded" hatası
        # veriyordu — sabit bir height + içerik taşarsa iç scroll (yukarı)
        # ile çözüldü.
        return ft.Tabs(
            length=len(tab_headers),
            content=ft.Column(
                [
                    ft.TabBar(tabs=tab_headers),
                    ft.TabBarView(controls=tab_bodies, height=240),
                ],
            ),
        )

    def _table_columns(self) -> list[ft.DataColumn]:
        cols = ["Tarih", "Ürün"]
        if self.show_uretim_fire:
            cols += ["Üretim", "Fire"]
        cols += ["Satış / ID", "Açılış", "Bitiş", "İşlem"]
        return [ft.DataColumn(ft.Text(c)) for c in cols]

    # -- Veri yenileme ----------------------------------------------------

    def on_data_refreshed(self) -> None:
        self._refresh_product_dropdown()
        self._refresh_table()

    def _refresh_product_dropdown(self) -> None:
        latest_by_code: dict[str, dict] = {}
        for r in self.state.records:
            code = r["urunKodu"]
            existing = latest_by_code.get(code)
            if not existing or r["tarih"] > existing["tarih"] or r["id"] > existing["id"]:
                latest_by_code[code] = r
        self.product_dropdown.options = [
            ft.DropdownOption(key=code, text=f"{r['urunAdi']} ({code}) — Bitiş: {format_number(r['bitisStokTeneke'])} T")
            for code, r in sorted(latest_by_code.items(), key=lambda kv: kv[1]["urunAdi"])
        ]
        if is_mounted(self.product_dropdown):
            self.product_dropdown.update()

    def _refresh_table(self) -> None:
        query = (self.search_field.value or "").strip().lower()
        rows = [
            r
            for r in self.state.records
            if not query
            or query in (r.get("urunAdi") or "").lower()
            or query in (r.get("urunKodu") or "").lower()
            or query in (r.get("barcode") or "").lower()
        ]
        rows.sort(key=lambda r: (r.get("tarih") or "", r.get("id") or ""), reverse=True)

        data_rows = []
        for r in rows:
            cells = [ft.DataCell(ft.Text(format_date_tr(r.get("tarih")))), ft.DataCell(ft.Text(f"{r.get('urunAdi')} ({r.get('urunKodu')})"))]
            if self.show_uretim_fire:
                cells.append(ft.DataCell(ft.Text(f"{format_number(r.get('uretimTeneke'))} T / {format_number(r.get('uretimKg'))} Kg")))
                cells.append(ft.DataCell(ft.Text(f"{format_number(r.get('fireTeneke'))} T / {format_number(r.get('fireKg'))} Kg")))
            satis_text = f"{format_number(r.get('satisTeneke'))} T / {format_number(r.get('satisKg'))} Kg"
            if r.get("satisId"):
                satis_text += f" [{r['satisId']}]"
            cells.append(ft.DataCell(ft.Text(satis_text)))
            cells.append(ft.DataCell(ft.Text(f"{format_number(r.get('baslangicStokTeneke'))} T / {format_number(r.get('baslangicStokKg'))} Kg")))
            cells.append(ft.DataCell(ft.Text(f"{format_number(r.get('bitisStokTeneke'))} T / {format_number(r.get('bitisStokKg'))} Kg")))
            cells.append(
                ft.DataCell(
                    ft.Row(
                        [
                            ft.IconButton(ft.Icons.EDIT, tooltip="Düzenle", on_click=lambda e, rec=r: self._load_record(rec)),
                            ft.IconButton(ft.Icons.DELETE, tooltip="Sil", icon_color=ft.Colors.RED, on_click=lambda e, rec=r: self.page.run_task(self._delete_record, rec)),
                        ],
                        spacing=0,
                    )
                )
            )
            data_rows.append(ft.DataRow(cells=cells))

        self.table.columns = self._table_columns()
        self.table.rows = data_rows
        if is_mounted(self.table):
            self.table.update()

    # -- Form davranışı ----------------------------------------------------

    def _on_product_dropdown_change(self, e) -> None:
        code = self.product_dropdown.value
        if code:
            self._autofill_from_code(code)

    def _on_urun_kodu_blur(self, e) -> None:
        code = (self.urun_kodu.value or "").strip().upper()
        self.urun_kodu.value = code
        if code:
            self._autofill_from_code(code)
        self.page.update()

    def _autofill_from_code(self, code: str) -> None:
        clean = code.strip().lower()
        matched = next(
            (
                r
                for r in self.state.records
                if (r.get("urunKodu") or "").strip().lower() == clean or (r.get("barcode") or "").strip().lower() == clean
            ),
            None,
        )
        if matched:
            self.urun_kodu.value = matched["urunKodu"]
            self.urun_adi.value = matched["urunAdi"]
            if not self.barcode.value:
                self.barcode.value = matched.get("barcode") or matched["urunKodu"]
            if _num(self.fiyat_kg) == 0:
                self.fiyat_kg.value = str(matched.get("fiyatKg") or 0)
            if _num(self.fiyat_teneke) == 0:
                self.fiyat_teneke.value = str(matched.get("fiyatTeneke") or 0)
            if _num(self.fiyat_adet) == 0:
                self.fiyat_adet.value = str(matched.get("fiyatAdet") or 0)
            self._sync_starting_stock_from_chain(matched["urunKodu"])
        self._apply_lock(matched["urunKodu"] if matched else code)
        self._refresh_ending_preview(None)
        self.page.update()

    def _sync_starting_stock_from_chain(self, code: str) -> None:
        prev = get_previous_record(self.state.records, code, self.tarih.value or "", self.editing_id)
        if prev:
            self.baslangic_teneke.value = str(prev.get("bitisStokTeneke") or 0)
            self.baslangic_kg.value = str(prev.get("bitisStokKg") or 0)
            self.baslangic_adet.value = str(prev.get("bitisStokAdet") or 0)

    def _apply_lock(self, code: str) -> None:
        locked = has_locked_starting_stock(self.state.records, code) and self.show_uretim_fire
        self._starting_stock_locked = locked
        for tf in (self.baslangic_teneke, self.baslangic_kg, self.baslangic_adet):
            tf.read_only = locked
        self.lock_banner.value = (
            "Bu ürünün başlangıç stoğu Barkod Eşleştirmeden kilitli — değer zincirden otomatik gelir."
            if locked
            else ""
        )
        self.lock_banner.visible = locked

    def _refresh_ending_preview(self, e) -> None:
        ending = calculate_ending_stock(
            {
                "baslangicStokKg": _num(self.baslangic_kg), "baslangicStokTeneke": _num(self.baslangic_teneke), "baslangicStokAdet": _num(self.baslangic_adet),
                "uretimKg": _num(self.uretim_kg), "uretimTeneke": _num(self.uretim_teneke), "uretimAdet": _num(self.uretim_adet),
                "fireKg": _num(self.fire_kg), "fireTeneke": _num(self.fire_teneke), "fireAdet": _num(self.fire_adet),
                "satisKg": _num(self.satis_kg), "satisTeneke": _num(self.satis_teneke), "satisAdet": _num(self.satis_adet),
            }
        )
        self.bitis_text.value = (
            f"{format_number(ending['bitisStokTeneke'])} T / {format_number(ending['bitisStokKg'])} Kg / {format_number(ending['bitisStokAdet'])} Ad"
        )
        if is_mounted(self.bitis_text):
            self.bitis_text.update()

    def _reset_form(self) -> None:
        self.editing_id = None
        self.tarih.value = get_today_date_string()
        self.urun_kodu.value = ""
        self.urun_adi.value = ""
        self.barcode.value = ""
        for tf in (
            self.uretim_teneke, self.uretim_kg, self.uretim_adet,
            self.fire_teneke, self.fire_kg, self.fire_adet,
            self.satis_teneke, self.satis_kg, self.satis_adet,
            self.baslangic_teneke, self.baslangic_kg, self.baslangic_adet,
            self.fiyat_teneke, self.fiyat_kg, self.fiyat_adet,
        ):
            tf.value = "0"
        self.satis_id.value = ""
        self._apply_lock("")
        self.product_dropdown.value = None
        self._refresh_ending_preview(None)
        if self.page:
            self.page.update()

    def _load_record(self, rec: dict) -> None:
        self.editing_id = rec["id"]
        self.tarih.value = rec.get("tarih") or ""
        self.urun_kodu.value = rec.get("urunKodu") or ""
        self.urun_adi.value = rec.get("urunAdi") or ""
        self.barcode.value = rec.get("barcode") or ""
        self.uretim_teneke.value = str(rec.get("uretimTeneke") or 0)
        self.uretim_kg.value = str(rec.get("uretimKg") or 0)
        self.uretim_adet.value = str(rec.get("uretimAdet") or 0)
        self.fire_teneke.value = str(rec.get("fireTeneke") or 0)
        self.fire_kg.value = str(rec.get("fireKg") or 0)
        self.fire_adet.value = str(rec.get("fireAdet") or 0)
        self.satis_teneke.value = str(rec.get("satisTeneke") or 0)
        self.satis_kg.value = str(rec.get("satisKg") or 0)
        self.satis_adet.value = str(rec.get("satisAdet") or 0)
        self.baslangic_teneke.value = str(rec.get("baslangicStokTeneke") or 0)
        self.baslangic_kg.value = str(rec.get("baslangicStokKg") or 0)
        self.baslangic_adet.value = str(rec.get("baslangicStokAdet") or 0)
        self.fiyat_teneke.value = str(rec.get("fiyatTeneke") or 0)
        self.fiyat_kg.value = str(rec.get("fiyatKg") or 0)
        self.fiyat_adet.value = str(rec.get("fiyatAdet") or 0)
        self.satis_id.value = rec.get("satisId") or ""
        self._apply_lock(rec.get("urunKodu") or "")
        self._refresh_ending_preview(None)
        if self.page:
            self.page.update()

    # -- Kaydetme / Silme ----------------------------------------------------

    def _on_save_click(self, e) -> None:
        self.page.run_task(self._save)

    async def _save(self) -> None:
        urun_kodu = (self.urun_kodu.value or "").strip().upper()
        urun_adi = (self.urun_adi.value or "").strip()
        if not urun_kodu:
            self._snack("Ürün ID'si / Kodu girilmeden kayıt eklenemez.")
            return
        if not urun_adi:
            self._snack("Ürün adı girilmeden kayıt eklenemez.")
            return

        available_teneke = _num(self.baslangic_teneke) + _num(self.uretim_teneke) - _num(self.fire_teneke)
        available_kg = _num(self.baslangic_kg) + _num(self.uretim_kg) - _num(self.fire_kg)
        available_adet = _num(self.baslangic_adet) + _num(self.uretim_adet) - _num(self.fire_adet)
        if _num(self.satis_teneke) > available_teneke or _num(self.satis_kg) > available_kg or _num(self.satis_adet) > available_adet:
            self._snack("Satış miktarı mevcut stoğu aşıyor.")
            return

        old_record = next((r for r in self.state.records if r["id"] == self.editing_id), None) if self.editing_id else None

        if self.show_uretim_fire:
            manual_baslangic_stok = True
        else:
            manual_baslangic_stok = bool(old_record.get("manualBaslangicStok")) if old_record else False

        has_sale = _num(self.satis_kg) > 0 or _num(self.satis_teneke) > 0 or _num(self.satis_adet) > 0
        satis_id = (self.satis_id.value or "").strip().upper()
        if has_sale and not satis_id:
            existing_ids = {s["id"] for s in self.state.sales}
            for r in self.state.records:
                if r.get("satisId") and r["id"] != self.editing_id:
                    existing_ids.add(r["satisId"])
            satis_id = generate_sale_id(existing_ids, self.tarih.value or get_today_date_string())

        new_record = {
            **new_record_defaults(),
            "id": self.editing_id or _new_id(),
            "tarih": self.tarih.value or get_today_date_string(),
            "urunKodu": urun_kodu,
            "urunAdi": urun_adi,
            "barcode": (self.barcode.value or "").strip() or urun_kodu,
            "uretimKg": _num(self.uretim_kg), "uretimTeneke": _num(self.uretim_teneke), "uretimAdet": _num(self.uretim_adet),
            "fireKg": _num(self.fire_kg), "fireTeneke": _num(self.fire_teneke), "fireAdet": _num(self.fire_adet),
            "satisKg": _num(self.satis_kg), "satisTeneke": _num(self.satis_teneke), "satisAdet": _num(self.satis_adet),
            "baslangicStokKg": _num(self.baslangic_kg), "baslangicStokTeneke": _num(self.baslangic_teneke), "baslangicStokAdet": _num(self.baslangic_adet),
            "fiyatTeneke": _num(self.fiyat_teneke), "fiyatKg": _num(self.fiyat_kg), "fiyatAdet": _num(self.fiyat_adet),
            "satisId": satis_id,
            "linkedSaleId": old_record.get("linkedSaleId") if old_record else None,
            "manualBaslangicStok": manual_baslangic_stok,
            "baslangicStokKilitli": bool(old_record.get("baslangicStokKilitli")) if old_record else False,
        }
        new_record.update(calculate_ending_stock(new_record))

        self.on_saving(True)
        try:
            records = self.state.records
            updated_list = (
                [new_record if r["id"] == new_record["id"] else r for r in records]
                if self.editing_id
                else [*records, new_record]
            )
            updated_list = recalculate_product_stock_chain(updated_list, new_record["urunKodu"])
            if old_record and old_record["urunKodu"].strip().lower() != new_record["urunKodu"].strip().lower():
                updated_list = recalculate_product_stock_chain(updated_list, old_record["urunKodu"])

            changed_codes = {new_record["urunKodu"].strip().lower()}
            if old_record:
                changed_codes.add(old_record["urunKodu"].strip().lower())
            to_upsert = [r for r in updated_list if r["urunKodu"].strip().lower() in changed_codes]

            await asyncio.to_thread(self.state.db.save_all_data, records=to_upsert)
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Kayıt sırasında hata: {exc}")
            self.on_saving(False)
            return

        self.on_saving(False)
        self._refresh_product_dropdown()
        self._refresh_table()
        self._reset_form()

    async def _delete_record(self, rec: dict) -> None:
        self.on_saving(True)
        try:
            remaining = [r for r in self.state.records if r["id"] != rec["id"]]
            updated_list = recalculate_product_stock_chain(remaining, rec["urunKodu"])
            to_upsert = [r for r in updated_list if r["urunKodu"].strip().lower() == rec["urunKodu"].strip().lower()]
            await asyncio.to_thread(
                self.state.db.save_all_data, records=to_upsert, deleted_record_ids=[rec["id"]]
            )
            await asyncio.to_thread(self.state.load_all)
        except Exception as exc:  # noqa: BLE001
            self._snack(f"Silme sırasında hata: {exc}")
            self.on_saving(False)
            return
        self.on_saving(False)
        self._refresh_product_dropdown()
        self._refresh_table()

    def _snack(self, msg: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))
