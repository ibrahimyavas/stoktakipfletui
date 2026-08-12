"""
Depolama çekirdeği — shared/db-core.ts'in (web/Cloudflare tarafındaki TypeScript
sürümü) birebir Python karşılığı. Aynı Turso veritabanına, aynı şemayla,
aynı senkron modeliyle bağlanır — web app ile bu masaüstü uygulaması aynı
anda, aynı veritabanına güvenle yazabilir.

ÖNEMLİ: Kayıt/güncelleme tabloyu SİLİP YENİDEN YAZMAZ (bu, aynı anda birden
fazla cihaz kaydettiğinde diğerinin eklediği satırları sessizce yok ederdi).
Bunun yerine her satır id'sine göre UPSERT edilir; silme işlemi yalnızca
çağıranın açıkça bildirdiği id listesiyle yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import libsql_client

RECORD_COLUMNS = [
    "id", "tarih", "urunKodu", "urunAdi", "barcode",
    "uretimKg", "uretimTeneke", "uretimAdet",
    "fireKg", "fireTeneke", "fireAdet",
    "satisKg", "satisTeneke", "satisAdet",
    "baslangicStokKg", "baslangicStokTeneke", "baslangicStokAdet",
    "bitisStokKg", "bitisStokTeneke", "bitisStokAdet",
    "fiyatTeneke", "fiyatKg", "fiyatAdet",
    "satisId", "linkedSaleId", "manualBaslangicStok", "baslangicStokKilitli",
]

COMPANY_COLUMNS = ["id", "kod", "ad", "telefon", "eposta", "adres"]

SALE_COLUMNS = [
    "id", "kaynak", "kaynakKayitId", "irsaliyeTarihi", "faturaTarihi",
    "sirketKodu", "sirketAdi", "aracPlakasi", "urunKodu", "urunAdi",
    "miktarTeneke", "miktarKg", "miktarAdet",
    "fiyatTeneke", "fiyatKg", "fiyatAdet",
    "tutar", "barcode", "irsaliyeFotoUrl",
]

WAYBILL_COLUMNS = [
    "id", "irsaliyeNo", "firmaAdi", "tarih",
    "tutar", "notlar", "fotoUrl", "okunanMetin", "eklenmeTarihi",
]

_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        tarih TEXT,
        urunKodu TEXT,
        urunAdi TEXT,
        barcode TEXT,
        uretimKg REAL, uretimTeneke REAL, uretimAdet REAL,
        fireKg REAL, fireTeneke REAL, fireAdet REAL,
        satisKg REAL, satisTeneke REAL, satisAdet REAL,
        baslangicStokKg REAL, baslangicStokTeneke REAL, baslangicStokAdet REAL,
        bitisStokKg REAL, bitisStokTeneke REAL, bitisStokAdet REAL,
        fiyatTeneke REAL, fiyatKg REAL, fiyatAdet REAL,
        satisId TEXT, linkedSaleId TEXT, manualBaslangicStok INTEGER,
        baslangicStokKilitli INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS companies (
        id TEXT PRIMARY KEY,
        kod TEXT, ad TEXT, telefon TEXT, eposta TEXT, adres TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        kaynak TEXT, kaynakKayitId TEXT,
        irsaliyeTarihi TEXT, faturaTarihi TEXT,
        sirketKodu TEXT, sirketAdi TEXT, aracPlakasi TEXT,
        urunKodu TEXT, urunAdi TEXT,
        miktarTeneke REAL, miktarKg REAL, miktarAdet REAL,
        fiyatTeneke REAL, fiyatKg REAL, fiyatAdet REAL,
        tutar REAL, barcode TEXT, irsaliyeFotoUrl TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS waybills (
        id TEXT PRIMARY KEY,
        irsaliyeNo TEXT, firmaAdi TEXT, tarih TEXT,
        tutar REAL, notlar TEXT, fotoUrl TEXT, okunanMetin TEXT, eklenmeTarihi TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
]


def _normalize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    return v


@dataclass
class AllData:
    records: list[dict] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    sales: list[dict] = field(default_factory=list)
    waybills: list[dict] = field(default_factory=list)
    sheetsUrl: str = ""
    profile: str | None = None
    updatedAt: str | None = None


class DbCore:
    """Turso/libSQL üzerinden senkron (bloklamayan-thread'li) veritabanı erişimi.

    `libsql_client.create_client_sync()` içeride kendi arka plan thread'inde
    bir asyncio event loop'u çalıştırıp senkron bir `.execute()/.batch()`
    API'si sunuyor — burada asyncio ile hiç uğraşmıyoruz.
    """

    def __init__(self, url: str, auth_token: str | None = None):
        # `libsql://` (Hrana/WebSocket) bu Python istemcisinde bazı Turso
        # sunucularıyla el sıkışma hatası veriyor; `https://` (düz HTTP)
        # aynı veritabanına sorunsuz bağlanıyor. Kullanıcı yine de standart
        # `turso db show --url` çıktısını (libsql://...) girebilsin diye
        # burada şeffaf şekilde çeviriyoruz.
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://") :]
        self._client = libsql_client.create_client_sync(url=url, auth_token=auth_token)
        self._init_schema()

    def close(self) -> None:
        self._client.close()

    def _init_schema(self) -> None:
        for stmt in _SCHEMA_STATEMENTS:
            self._client.execute(stmt)

        # CREATE TABLE IF NOT EXISTS zaten var olan bir tabloya yeni sütun
        # eklemez. Önceden oluşturulmuş veritabanlarında eksikse
        # baslangicStokKilitli sütununu sonradan ekler; sütun zaten varsa
        # hatayı yok sayar.
        try:
            self._client.execute("ALTER TABLE records ADD COLUMN baslangicStokKilitli INTEGER")
        except Exception:
            pass  # sütun zaten mevcut

    # -- yazma -----------------------------------------------------------

    def _upsert_rows(self, table: str, columns: list[str], rows: list[dict]) -> None:
        """Her satırı id'ye göre UPSERT eder (INSERT ... ON CONFLICT DO UPDATE).
        Böylece başka bir cihazın/uygulamanın eş zamanlı eklediği, bu isteğin
        haberdar olmadığı satırlar ASLA silinmez — sadece bu istekte
        gönderilen satırlar yazılır/güncellenir.
        """
        if not rows:
            return
        placeholders = ", ".join("?" for _ in columns)
        update_assignments = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {update_assignments}"
        )
        stmts = [(sql, tuple(_normalize_value(row.get(c)) for c in columns)) for row in rows]
        self._client.batch(stmts)

    def _delete_rows(self, table: str, ids: list[str]) -> None:
        """Yalnızca çağıranın açıkça 'sildim' dediği id'leri siler — tabloyu
        topyekûn boşaltıp yeniden doldurmaz."""
        if not ids:
            return
        placeholders = ", ".join("?" for _ in ids)
        self._client.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", tuple(ids))

    def _get_meta(self, key: str) -> str | None:
        res = self._client.execute("SELECT value FROM meta WHERE key = ?", (key,))
        if not res.rows:
            return None
        return res.rows[0]["value"]

    def _set_meta(self, key: str, value: str) -> None:
        self._client.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _read_table(self, table: str, columns: list[str]) -> list[dict]:
        res = self._client.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY rowid ASC")
        return [row.asdict() for row in res.rows]

    # -- genel API ---------------------------------------------------------

    def get_all_data(self) -> AllData:
        records = self._read_table("records", RECORD_COLUMNS)
        for r in records:
            r["manualBaslangicStok"] = bool(r.get("manualBaslangicStok"))
            r["baslangicStokKilitli"] = bool(r.get("baslangicStokKilitli"))

        return AllData(
            records=records,
            companies=self._read_table("companies", COMPANY_COLUMNS),
            sales=self._read_table("sales", SALE_COLUMNS),
            waybills=self._read_table("waybills", WAYBILL_COLUMNS),
            sheetsUrl=self._get_meta("sheetsUrl") or "",
            profile=self._get_meta("profile"),
            updatedAt=self._get_meta("updatedAt"),
        )

    def save_all_data(
        self,
        records: list[dict] | None = None,
        companies: list[dict] | None = None,
        sales: list[dict] | None = None,
        waybills: list[dict] | None = None,
        sheets_url: str | None = None,
        profile: str | None = None,
        deleted_record_ids: list[str] | None = None,
        deleted_company_ids: list[str] | None = None,
        deleted_sale_ids: list[str] | None = None,
        deleted_waybill_ids: list[str] | None = None,
    ) -> str:
        if records is not None:
            self._upsert_rows("records", RECORD_COLUMNS, records)
        if deleted_record_ids:
            self._delete_rows("records", deleted_record_ids)

        if companies is not None:
            self._upsert_rows("companies", COMPANY_COLUMNS, companies)
        if deleted_company_ids:
            self._delete_rows("companies", deleted_company_ids)

        if sales is not None:
            self._upsert_rows("sales", SALE_COLUMNS, sales)
        if deleted_sale_ids:
            self._delete_rows("sales", deleted_sale_ids)

        if waybills is not None:
            self._upsert_rows("waybills", WAYBILL_COLUMNS, waybills)
        if deleted_waybill_ids:
            self._delete_rows("waybills", deleted_waybill_ids)

        if sheets_url is not None:
            self._set_meta("sheetsUrl", sheets_url)
        if profile is not None:
            self._set_meta("profile", profile or "")

        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._set_meta("updatedAt", updated_at)
        return updated_at
