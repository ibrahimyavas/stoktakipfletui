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

# Sayfaların sekme çubuğunda görünme sırası — birleştirilmiş (çoklu rol)
# erişimde de bu sıra korunur.
_PAGE_ORDER = (PAGE_DEFTER, PAGE_RAPOR, PAGE_SATIS, PAGE_GENEL)

# Çoklu rol seçilebildiğinde kullanılacak vurgu rengi (herhangi bir tekil rol
# rengiyle karışmasın diye ayrı bir ton) — admin seçiliyse admin rengi kazanır.
_MULTI_ROLE_COLOR = "#F59E0B"


@dataclass(frozen=True)
class EffectiveAccess:
    """Bir kullanıcının (tek ya da birden çok rolünün BİRLEŞİMİNDEN) sahip
    olduğu fiili erişim — `ui/dashboard_common.py` ve `main.py` PROFILES'ı
    doğrudan değil, hep bunun üzerinden okur. Tek rol verilirse (mevcut/eski
    kullanım) üretilen değerler o rolün kendi `ProfileInfo`'suyla birebir
    aynıdır — yani bu, mevcut davranışı bozmayan katkısal bir soyutlama."""

    role_keys: tuple[str, ...]
    label: str
    color: str
    pages: tuple[str, ...]
    is_admin: bool
    show_uretim_fire: bool
    show_satis: bool


def compute_effective_access(role_keys: list[str] | tuple[str, ...]) -> EffectiveAccess:
    valid = [r for r in dict.fromkeys(role_keys) if r in PROFILES]  # sırayı + tekliği koru
    if not valid:
        valid = ["uretim"]  # bozuk/boş veri için güvenli varsayılan

    is_admin = "admin" in valid
    pages_set: set[str] = set()
    for r in valid:
        pages_set.update(PROFILES[r].pages)
    pages = tuple(p for p in _PAGE_ORDER if p in pages_set)

    label = " + ".join(PROFILES[r].label for r in valid)
    if is_admin:
        color = PROFILES["admin"].color
    elif len(valid) == 1:
        color = PROFILES[valid[0]].color
    else:
        color = _MULTI_ROLE_COLOR

    return EffectiveAccess(
        role_keys=tuple(valid),
        label=label,
        color=color,
        pages=pages,
        is_admin=is_admin,
        show_uretim_fire=is_admin or "uretim" in valid,
        show_satis=is_admin or "satis" in valid,
    )


def roles_to_field(role_keys: list[str] | tuple[str, ...]) -> str:
    """Kullanıcı satırındaki `role` sütununa yazılacak virgülle ayrılmış
    metni üretir (ör. `"uretim,satis"`). Tek rol de aynı şekilde saklanır
    (`"admin"`), yani eski tek-rollü satırlarla biçim uyumlu."""
    valid = [r for r in dict.fromkeys(role_keys) if r in PROFILES]
    return ",".join(valid) if valid else "uretim"


def roles_from_field(role_field: str | None) -> list[str]:
    """`role` sütunundaki virgülle ayrılmış metni listeye çevirir. Eski
    tek-rollü satırlarda (`"admin"`, virgül yok) da sorunsuz çalışır."""
    if not role_field:
        return ["uretim"]
    valid = [r.strip() for r in role_field.split(",") if r.strip() in PROFILES]
    return valid or ["uretim"]

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
