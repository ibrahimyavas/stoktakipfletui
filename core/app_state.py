"""
Uygulama genelinde paylaşılan veri durumu — React tarafındaki App.tsx'in
kaldırılmış (lifted) state'inin karşılığı. Tüm ekranlar aynı AppState
örneğini kullanır; bir ekran veri değiştirdiğinde diğerleri de görür.

DB erişimi senkron (libsql-client'ın create_client_sync'i) ama yine de ağ
üzerinden gittiği için UI thread'ini kilitlememek adına her çağıran taraf
(sayfalar) uzun sürebilecek işlemleri QThread/worker üzerinden tetiklemeli —
bu modül sadece veri + DB çağrılarını sarmalıyor, thread yönetimini çağıran
koda bırakıyor (bkz. ui/workers.py).
"""

from __future__ import annotations

from core.db_core import DbCore


class AppState:
    def __init__(self, db: DbCore):
        self.db = db
        self.records: list[dict] = []
        self.companies: list[dict] = []
        self.sales: list[dict] = []
        self.waybills: list[dict] = []
        self.sheets_url: str = ""
        self.profile: str | None = None
        self.updated_at: str | None = None

    def load_all(self) -> None:
        data = self.db.get_all_data()
        self.records = data.records
        self.companies = data.companies
        self.sales = data.sales
        self.waybills = data.waybills
        self.sheets_url = data.sheetsUrl
        self.profile = data.profile
        self.updated_at = data.updatedAt

    # -- Kaydetme yardımcıları — her biri doğrudan tek bir koleksiyonu
    # günceller (web tarafındaki tam-dizi-diff modeli yerine, masaüstünde her
    # CRUD eylemi kendi upsert/delete çağrısını doğrudan yapar).

    def save_records(self, upsert: list[dict] | None = None, deleted_ids: list[str] | None = None) -> None:
        self.db.save_all_data(records=upsert, deleted_record_ids=deleted_ids)
        self.load_all()

    def save_companies(self, upsert: list[dict] | None = None, deleted_ids: list[str] | None = None) -> None:
        self.db.save_all_data(companies=upsert, deleted_company_ids=deleted_ids)
        self.load_all()

    def save_sales(self, upsert: list[dict] | None = None, deleted_ids: list[str] | None = None) -> None:
        self.db.save_all_data(sales=upsert, deleted_sale_ids=deleted_ids)
        self.load_all()

    def save_waybills(self, upsert: list[dict] | None = None, deleted_ids: list[str] | None = None) -> None:
        self.db.save_all_data(waybills=upsert, deleted_waybill_ids=deleted_ids)
        self.load_all()

    def save_sheets_url(self, url: str) -> None:
        self.db.save_all_data(sheets_url=url)
        self.sheets_url = url

    def save_profile(self, role: str) -> None:
        self.db.save_all_data(profile=role)
        self.profile = role
