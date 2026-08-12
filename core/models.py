"""
src/types.ts'in Python karşılığı. Kayıtlar burada dict olarak tutuluyor
(DB katmanıyla aynı şekil), ama alan adları ve rol/erişim tabloları burada
tek yerden yönetiliyor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Rol / sayfa erişimi (ProfileSelector.tsx'teki PROFILES ile birebir) ---

PAGE_DEFTER = "defter"
PAGE_RAPOR = "rapor"
PAGE_SATIS = "satis"
PAGE_GENEL = "genel"


@dataclass(frozen=True)
class ProfileInfo:
    key: str
    label: str
    description: str
    pages: tuple[str, ...]
    color: str


PROFILES: dict[str, ProfileInfo] = {
    "uretim": ProfileInfo(
        key="uretim",
        label="Üretim",
        description=(
            "Defter üzerinden stok, üretim ve fire girişi yapar, yeni ürün "
            "tanımlar, stok takibi ve raporları inceler."
        ),
        pages=(PAGE_DEFTER, PAGE_RAPOR),
        color="#10B981",
    ),
    "satis": ProfileInfo(
        key="satis",
        label="Satış",
        description=(
            "Defterde sadece satış girişi yapar ve stok takibi gerçekleştirir. "
            "Satış ID ile firmaya faturaya dönüştürür."
        ),
        pages=(PAGE_DEFTER, PAGE_SATIS, PAGE_GENEL),
        color="#3B82F6",
    ),
    "admin": ProfileInfo(
        key="admin",
        label="Admin",
        description=(
            "Tüm sayfalara, firma yönetimine, barkod birleştirme ve genel "
            "tablolara tam erişim."
        ),
        pages=(PAGE_DEFTER, PAGE_RAPOR, PAGE_SATIS, PAGE_GENEL),
        color="#8B5CF6",
    ),
}

PAGE_LABELS: dict[str, str] = {
    PAGE_DEFTER: "Kayıt Defteri",
    PAGE_RAPOR: "Haftalık / Aylık Rapor",
    PAGE_SATIS: "Satışlar & Firmalar",
    PAGE_GENEL: "Genel Tablo",
}

# --- Kayıt şemaları — sütun adları db_core.RECORD_COLUMNS vb. ile birebir ---
# Not: Kayıtlar uygulama içinde dict olarak taşınıyor (DB satırlarıyla aynı
# şekil); bu sabitler sadece "yeni boş kayıt" oluştururken varsayılan
# değerleri tek yerden vermek için.


def new_record_defaults() -> dict:
    return {
        "id": "",
        "tarih": "",
        "urunKodu": "",
        "urunAdi": "",
        "barcode": "",
        "uretimKg": 0, "uretimTeneke": 0, "uretimAdet": 0,
        "fireKg": 0, "fireTeneke": 0, "fireAdet": 0,
        "satisKg": 0, "satisTeneke": 0, "satisAdet": 0,
        "baslangicStokKg": 0, "baslangicStokTeneke": 0, "baslangicStokAdet": 0,
        "bitisStokKg": 0, "bitisStokTeneke": 0, "bitisStokAdet": 0,
        "fiyatTeneke": 0, "fiyatKg": 0, "fiyatAdet": 0,
        "satisId": "",
        "linkedSaleId": None,
        "manualBaslangicStok": False,
        "baslangicStokKilitli": False,
    }


def new_company_defaults() -> dict:
    return {"id": "", "kod": "", "ad": "", "telefon": "", "eposta": "", "adres": ""}


def new_sale_defaults() -> dict:
    return {
        "id": "",
        "kaynak": "defter",
        "kaynakKayitId": None,
        "irsaliyeTarihi": "",
        "faturaTarihi": "",
        "sirketKodu": "",
        "sirketAdi": "",
        "aracPlakasi": "",
        "urunKodu": "",
        "urunAdi": "",
        "miktarTeneke": 0, "miktarKg": 0, "miktarAdet": 0,
        "fiyatTeneke": 0, "fiyatKg": 0, "fiyatAdet": 0,
        "tutar": 0,
        "barcode": "",
        "irsaliyeFotoUrl": "",
    }


def new_waybill_defaults() -> dict:
    return {
        "id": "",
        "irsaliyeNo": "",
        "firmaAdi": "",
        "tarih": "",
        "tutar": 0,
        "notlar": "",
        "fotoUrl": "",
        "okunanMetin": "",
        "eklenmeTarihi": "",
    }
