# Üretim & Satış Defteri — Flet Sürümü (kanıt-of-concept)

Bu, PySide6 masaüstü uygulamasının Flet ile yazılmış deneme sürümü — amaç
**Android (ve web/masaüstü) uyumluluğu**. Flet, Flutter üzerine kurulu; aynı
Python kodu masaüstünde native pencere, web'de tarayıcı, ve `flet build apk`
ile gerçek bir Android uygulaması olarak paketlenebiliyor.

## Bu kanıt-of-concept'te neler var

- **Rol seçimi** (Üretim / Satış / Admin) — `core/models.py`'deki `PROFILES`
  ile PySide6 sürümüyle birebir aynı erişim kuralları.
- **Üretim Kayıt Defteri** — kayıt ekle/düzenle/sil, ürün hızlı seçimi,
  stok zinciri (`core/stock_logic.py` — PySide6 sürümüyle **birebir aynı
  dosya**), başlangıç stoğu kilidi, rol bazlı sekmeler.
- **Genel Tablo + YENİ filtreleme özelliği**: firma, ürün, tarih aralığı ve
  serbest metin araması — hepsi birlikte, birleşik olarak uygulanıyor. CSV
  export da var (`FilePicker.save_file` ile — web/Android'de de çalışacak
  şekilde `src_bytes` kullanıyor, sadece masaüstü dosya yoluna güvenmiyor).
- **Ayarlar**: `platformdirs` değil, Flet'in `SharedPreferences` servisi
  (Flutter'ın `shared_preferences` paketi) — Android/iOS'ta da çalışır.
- **Tema**: Material 3 `color_scheme_seed` ile açık/koyu + serbest aksan
  rengi (PySide6 sürümündeki elle-XML-üretme yerine yerleşik).

**Henüz yok** (kanıt onaylanınca eklenecek): Satış, Rapor, Barkod
Eşleştirme, İrsaliye Arşivi (+OCR), Sheets senkron, Ayarlar'ı sonradan
düzenleme ekranı.

## Neden `core/` PySide6 sürümüyle aynı?

`core/db_core.py`, `core/stock_logic.py`, `core/models.py`, `core/app_state.py`,
`core/ocr.py`, `core/sheets_sync.py` — hepsi framework'ten bağımsız saf
Python. `stoktakipapp` reposundan **birebir kopyalandı**, tek satır
değiştirilmedi. İki uygulama da aynı Turso veritabanına bağlanıyor ve aynı
non-destructive upsert senkron modelini kullanıyor — istersen ikisini aynı
anda kullanabilirsin, veri kaybı olmaz.

## Çalıştırma

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

İlk açılışta Turso bağlantı bilgilerini isteyecek. Masaüstünde native bir
pencere açılır (`flet run` ile aynı); web önizlemesi için:

```bash
flet run --web main.py
```

## Bu depoda ne test edildi, ne edilemedi

Geliştirme ortamının (bu konuşmanın çalıştığı sandbox) headless-chromium'u,
Flet'in kullandığı Flutter/CanvasKit WASM motorunu başlatamadı — bu **kod
hatası değil**, sandbox'a özgü bir kısıt (sunucu tarafı HTTP 200 dönüyor,
istemci tarafı hiç bağlanamıyor). Bu yüzden:

- ✅ **Tüm iş mantığı** (kayıt kaydetme/düzenleme/silme, stok zinciri,
  başlangıç stoğu kilidi, YENİ filtreleme özelliğinin 5 senaryosu) gerçek
  Turso veritabanına karşı `page=None` ile (Flet çalışma zamanı olmadan,
  doğrudan Python fonksiyon çağrılarıyla) test edildi, hepsi geçti.
- ✅ Bu süreçte **3 gerçek Flet API uyumsuzluğu** bulunup düzeltildi
  (`Dropdown(on_change=...)` → `on_select`; `Tab(text=...)` → `label`;
  `Tab(content=...)` artık yok, içerik `TabBarView` ile ayrı veriliyor).
  Bunlar test edilmeseydi, uygulama ilk açılışta çökerdi.
- ⚠️ **Görsel/etkileşimli doğrulama henüz yapılmadı** — `flet run` ile
  gerçek bir ekranda (senin bilgisayarında) denenmesi gerekiyor.

## Sıradaki adım

`python3 main.py` ile dene, geri bildirim ver — beğenirsen kalan ekranlara
geçeriz, sonunda hepsini bu depoya (`stoktakipfletui`) push'larız.
