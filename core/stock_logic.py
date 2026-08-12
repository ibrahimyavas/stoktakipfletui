"""
src/lib/utils.ts'teki iş mantığının birebir Python karşılığı (stok zinciri,
satış ID üretimi, toplam tutar hesaplama vb.). Kayıtlar dict olarak temsil
ediliyor — db_core.py ile aynı alan adları.
"""

from __future__ import annotations

from datetime import date, datetime

MONTH_NAMES_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

MONTH_SHORT_TR = [
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
]


def get_today_date_string() -> str:
    return date.today().isoformat()


def format_number(val) -> str:
    try:
        num = float(val) if val not in (None, "") else 0.0
    except (TypeError, ValueError):
        num = 0.0
    # tr-TR locale: binlik ayraç nokta, ondalık virgül; en fazla 2 ondalık,
    # gereksiz sondaki sıfırlar atılır (JS toLocaleString ile aynı davranış).
    s = f"{num:,.2f}"
    integer_part, _, frac_part = s.partition(".")
    frac_part = frac_part.rstrip("0")
    integer_part = integer_part.replace(",", ".")
    if frac_part:
        return f"{integer_part},{frac_part}"
    return integer_part


def format_date_tr(date_str: str | None) -> str:
    if not date_str:
        return "-"
    parts = date_str.split("-")
    if len(parts) < 3:
        return date_str
    year, month, day = parts[0], parts[1], parts[2]
    return f"{day}.{month}.{year}"


def generate_sale_id(existing_ids: set[str], date_str: str | None = None) -> str:
    if date_str:
        d = datetime.fromisoformat(date_str)
    else:
        d = datetime.now()
    day = f"{d.day:02d}"
    month = f"{d.month:02d}"
    year_two_digits = f"{d.year % 100:02d}"

    prefix = f"{month}{year_two_digits}-{day}"  # aayy-gg

    seq = 1
    candidate = f"{prefix}-{seq:03d}"
    while candidate in existing_ids:
        seq += 1
        candidate = f"{prefix}-{seq:03d}"
    return candidate


def calculate_total_amount(
    m_teneke, m_kg, f_teneke, f_kg, m_adet=None, f_adet=None
) -> float:
    def n(v) -> float:
        try:
            return float(v) if v not in (None, "") else 0.0
        except (TypeError, ValueError):
            return 0.0

    kg, teneke, adet = n(m_kg), n(m_teneke), n(m_adet)
    fiyat_k, fiyat_t, fiyat_a = n(f_kg), n(f_teneke), n(f_adet)

    total = (kg * fiyat_k) + (teneke * fiyat_t) + (adet * fiyat_a)
    if total > 0:
        return total

    # Öncelik sıralı fallback
    if fiyat_k > 0 and kg > 0:
        return kg * fiyat_k
    if fiyat_t > 0 and teneke > 0:
        return teneke * fiyat_t
    if fiyat_a > 0 and adet > 0:
        return adet * fiyat_a
    return 0.0


def _n(rec: dict, key: str) -> float:
    v = rec.get(key)
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def calculate_ending_stock(rec: dict) -> dict:
    bitis_stok_kg = _n(rec, "baslangicStokKg") + _n(rec, "uretimKg") - _n(rec, "fireKg") - _n(rec, "satisKg")
    bitis_stok_teneke = (
        _n(rec, "baslangicStokTeneke") + _n(rec, "uretimTeneke") - _n(rec, "fireTeneke") - _n(rec, "satisTeneke")
    )
    bitis_stok_adet = _n(rec, "baslangicStokAdet") + _n(rec, "uretimAdet") - _n(rec, "fireAdet") - _n(rec, "satisAdet")
    return {
        "bitisStokKg": bitis_stok_kg,
        "bitisStokTeneke": bitis_stok_teneke,
        "bitisStokAdet": bitis_stok_adet,
    }


def has_locked_starting_stock(records: list[dict], urun_kodu: str) -> bool:
    """Bir ürünün başlangıç stoğunun Barkod Eşleştirme ekranından girilip
    kilitlendiğini (Üretim Kayıt Defteri'nde artık elle düzenlenemeyeceğini)
    bildirir. Barkod Eşleştirme ekranından girilmediyse False döner ve alan
    Üretim ekranında serbestçe elle girilebilir kalır."""
    code = (urun_kodu or "").strip().lower()
    if not code:
        return False
    return any(
        (r.get("urunKodu") or "").strip().lower() == code and bool(r.get("baslangicStokKilitli"))
        for r in records
    )


def get_previous_record(
    records: list[dict], urun_kodu: str, tarih: str, current_id: str | None = None
) -> dict | None:
    code = (urun_kodu or "").strip().lower()
    if not code or not tarih:
        return None

    candidates = []
    for r in records:
        if (r.get("urunKodu") or "").strip().lower() != code:
            continue
        if current_id and r.get("id") == current_id:
            continue
        r_tarih = r.get("tarih") or ""
        if r_tarih < tarih:
            candidates.append(r)
        elif r_tarih == tarih:
            if current_id:
                if (r.get("id") or "") < current_id:
                    candidates.append(r)
            else:
                candidates.append(r)

    if not candidates:
        return None

    candidates.sort(
        key=lambda r: (r.get("tarih") or "", r.get("id") or ""), reverse=True
    )
    return candidates[0]


def recalculate_product_stock_chain(records: list[dict], urun_kodu: str) -> list[dict]:
    """Bir ürünün tüm kayıtlarını tarihe göre sıralayıp zincirleme olarak
    başlangıç/bitiş stoklarını yeniden hesaplar. `manualBaslangicStok` True
    olan kayıtların başlangıç stoğu, önceki kaydın bitiş stoğuyla ezilmez —
    kullanıcının girdiği değer esas alınır (yalnızca zincirin ilk kaydından
    sonrakiler için anlamlı; ilk kayıt zaten önceki bir kayıttan almaz)."""
    code = (urun_kodu or "").strip().lower()
    if not code:
        return records

    product_records = sorted(
        (r for r in records if (r.get("urunKodu") or "").strip().lower() == code),
        key=lambda r: (r.get("tarih") or "", r.get("id") or ""),
    )

    update_map: dict[str, dict] = {}
    prev_stock_kg: float | None = None
    prev_stock_teneke: float | None = None
    prev_stock_adet: float | None = None

    for idx, rec in enumerate(product_records):
        baslangic_kg = _n(rec, "baslangicStokKg")
        baslangic_teneke = _n(rec, "baslangicStokTeneke")
        baslangic_adet = _n(rec, "baslangicStokAdet")

        if (
            idx > 0
            and not rec.get("manualBaslangicStok")
            and prev_stock_kg is not None
            and prev_stock_teneke is not None
        ):
            baslangic_kg = prev_stock_kg
            baslangic_teneke = prev_stock_teneke
            if prev_stock_adet is not None:
                baslangic_adet = prev_stock_adet

        ending = calculate_ending_stock(
            {
                "baslangicStokKg": baslangic_kg,
                "baslangicStokTeneke": baslangic_teneke,
                "baslangicStokAdet": baslangic_adet,
                "uretimKg": rec.get("uretimKg"),
                "uretimTeneke": rec.get("uretimTeneke"),
                "uretimAdet": rec.get("uretimAdet"),
                "fireKg": rec.get("fireKg"),
                "fireTeneke": rec.get("fireTeneke"),
                "fireAdet": rec.get("fireAdet"),
                "satisKg": rec.get("satisKg"),
                "satisTeneke": rec.get("satisTeneke"),
                "satisAdet": rec.get("satisAdet"),
            }
        )

        updated = {
            **rec,
            "baslangicStokKg": baslangic_kg,
            "baslangicStokTeneke": baslangic_teneke,
            "baslangicStokAdet": baslangic_adet,
            **ending,
        }
        update_map[rec["id"]] = updated

        prev_stock_kg = ending["bitisStokKg"]
        prev_stock_teneke = ending["bitisStokTeneke"]
        prev_stock_adet = ending["bitisStokAdet"]

    return [update_map.get(r["id"], r) for r in records]
