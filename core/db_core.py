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

# Bu tablo web app/PySide6 sürümünde YOK — sadece bu Flet sürümüne özgü,
# admin panelinden kullanıcı tanımlama + giriş ekranı için eklendi. Şifre asla
# düz metin saklanmıyor (core/auth.py::hash_password, tuzlu PBKDF2-HMAC-SHA256).
USER_COLUMNS = [
    "id", "name", "passwordHash", "passwordSalt", "role", "rememberToken", "createdAt",
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
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        passwordHash TEXT,
        passwordSalt TEXT,
        role TEXT,
        rememberToken TEXT,
        createdAt TEXT
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
    users: list[dict] = field(default_factory=list)
    sheetsUrl: str = ""
    profile: str | None = None
    updatedAt: str | None = None
    # JSON string, örn. '{"teneke": 5, "kg": 50, "adet": 10}' — boşsa
    # çağıran taraf kendi varsayılanını kullanır. `meta` tablosundaki genel
    # key/value deposuna ek bir satır olarak yazılıyor; web app/PySide6
    # sürümü bu anahtarı hiç bilmiyor/okumuyor, dolayısıyla onlarla
    # paylaşılan şemayı bozmuyor (geriye dönük uyumlu, katkısal bir alan).
    lowStockThresholds: str = ""


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

    # Performans notu: `libsql_client`'ın `.batch()`'i, listedeki tüm
    # ifadeleri (farklı SQL'ler olsalar bile) TEK bir ağ round-trip'inde
    # çalıştırıp sırayla eşleşen bir `ResultSet` listesi döndürüyor. Turso
    # uzak bir sunucu olduğu için asıl gecikme sorgu başına sabit bir ağ
    # gidiş-dönüş maliyeti — satır/tablo sayısı değil. Önceden `get_all_data`
    # 9, `save_all_data` (tabloya göre) 10'a kadar ayrı `.execute()` çağrısı
    # yapıyordu; şimdi ikisi de her zaman TEK `.batch()` çağrısına
    # indirgeniyor — hiçbir özellik/davranış değişmedi, sadece kaç kere
    # ağa çıkıldığı değişti.

    def _upsert_stmts(self, table: str, columns: list[str], rows: list[dict]) -> list[tuple[str, tuple]]:
        """Her satır için bir UPSERT (INSERT ... ON CONFLICT DO UPDATE) ifadesi
        üretir (henüz ÇALIŞTIRMAZ) — böylece başka bir cihazın/uygulamanın eş
        zamanlı eklediği, bu isteğin haberdar olmadığı satırlar ASLA silinmez;
        sadece bu istekte gönderilen satırlar yazılır/güncellenir.
        """
        if not rows:
            return []
        placeholders = ", ".join("?" for _ in columns)
        update_assignments = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {update_assignments}"
        )
        return [(sql, tuple(_normalize_value(row.get(c)) for c in columns)) for row in rows]

    def _delete_stmt(self, table: str, ids: list[str]) -> tuple[str, tuple] | None:
        """Yalnızca çağıranın açıkça 'sildim' dediği id'leri silen ifadeyi
        üretir — tabloyu topyekûn boşaltıp yeniden doldurmaz."""
        if not ids:
            return None
        placeholders = ", ".join("?" for _ in ids)
        return (f"DELETE FROM {table} WHERE id IN ({placeholders})", tuple(ids))

    @staticmethod
    def _set_meta_stmt(key: str, value: str) -> tuple[str, tuple]:
        return (
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # -- genel API ---------------------------------------------------------

    def get_all_data(self) -> AllData:
        # Sıra önemli: sonuçlar isteklerle aynı sırada dönüyor.
        table_specs = [
            ("records", RECORD_COLUMNS),
            ("companies", COMPANY_COLUMNS),
            ("sales", SALE_COLUMNS),
            ("waybills", WAYBILL_COLUMNS),
            ("users", USER_COLUMNS),
        ]
        meta_keys = ["sheetsUrl", "profile", "updatedAt", "lowStockThresholds"]
        stmts: list = [
            f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid ASC" for table, cols in table_specs
        ] + [("SELECT value FROM meta WHERE key = ?", (key,)) for key in meta_keys]

        results = self._client.batch(stmts)
        table_results = {table: [row.asdict() for row in results[i].rows] for i, (table, _) in enumerate(table_specs)}
        meta_results = {
            key: (results[len(table_specs) + i].rows[0]["value"] if results[len(table_specs) + i].rows else None)
            for i, key in enumerate(meta_keys)
        }

        records = table_results["records"]
        for r in records:
            r["manualBaslangicStok"] = bool(r.get("manualBaslangicStok"))
            r["baslangicStokKilitli"] = bool(r.get("baslangicStokKilitli"))

        return AllData(
            records=records,
            companies=table_results["companies"],
            sales=table_results["sales"],
            waybills=table_results["waybills"],
            users=table_results["users"],
            sheetsUrl=meta_results["sheetsUrl"] or "",
            profile=meta_results["profile"],
            updatedAt=meta_results["updatedAt"],
            lowStockThresholds=meta_results["lowStockThresholds"] or "",
        )

    def save_all_data(
        self,
        records: list[dict] | None = None,
        companies: list[dict] | None = None,
        sales: list[dict] | None = None,
        waybills: list[dict] | None = None,
        users: list[dict] | None = None,
        sheets_url: str | None = None,
        profile: str | None = None,
        low_stock_thresholds: str | None = None,
        deleted_record_ids: list[str] | None = None,
        deleted_company_ids: list[str] | None = None,
        deleted_sale_ids: list[str] | None = None,
        deleted_waybill_ids: list[str] | None = None,
        deleted_user_ids: list[str] | None = None,
    ) -> str:
        stmts: list[tuple[str, tuple]] = []

        stmts += self._upsert_stmts("records", RECORD_COLUMNS, records or [])
        if d := self._delete_stmt("records", deleted_record_ids or []):
            stmts.append(d)

        stmts += self._upsert_stmts("companies", COMPANY_COLUMNS, companies or [])
        if d := self._delete_stmt("companies", deleted_company_ids or []):
            stmts.append(d)

        stmts += self._upsert_stmts("sales", SALE_COLUMNS, sales or [])
        if d := self._delete_stmt("sales", deleted_sale_ids or []):
            stmts.append(d)

        stmts += self._upsert_stmts("waybills", WAYBILL_COLUMNS, waybills or [])
        if d := self._delete_stmt("waybills", deleted_waybill_ids or []):
            stmts.append(d)

        stmts += self._upsert_stmts("users", USER_COLUMNS, users or [])
        if d := self._delete_stmt("users", deleted_user_ids or []):
            stmts.append(d)

        if sheets_url is not None:
            stmts.append(self._set_meta_stmt("sheetsUrl", sheets_url))
        if profile is not None:
            stmts.append(self._set_meta_stmt("profile", profile or ""))
        if low_stock_thresholds is not None:
            stmts.append(self._set_meta_stmt("lowStockThresholds", low_stock_thresholds))

        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        stmts.append(self._set_meta_stmt("updatedAt", updated_at))

        self._client.batch(stmts)
        return updated_at
