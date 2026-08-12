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

## Bu depoda ne test edildi

- ✅ **Tüm iş mantığı** (kayıt kaydetme/düzenleme/silme, stok zinciri,
  başlangıç stoğu kilidi, YENİ filtreleme özelliğinin 5 senaryosu) gerçek
  Turso veritabanına karşı `page=None` ile (Flet çalışma zamanı olmadan,
  doğrudan Python fonksiyon çağrılarıyla) test edildi, hepsi geçti.
- ✅ **7 gerçek Flet API/davranış hatası** bulunup düzeltildi:
  - `Dropdown(on_change=...)` → `on_select`
  - `Tab(text=...)` → `label`
  - `Tab(content=...)` artık yok, içerik `TabBarView` ile ayrı veriliyor
  - **Tarayıcı sonsuza kadar yükleme ekranında takılı kalıyordu** —
    sebebi Flet'in varsayılan olarak CanvasKit/skwasm/font dosyalarını
    harici bir CDN'den (`gstatic.com`) çekmeye çalışması; bu dosyalar
    zaten yerel olarak da sunucu tarafından servis ediliyor. `main.py`'da
    `ft.run(main, no_cdn=True)` ile düzeltildi — artık hiçbir harici ağ
    bağlantısına ihtiyaç yok. (İlk başta bunu "sandbox'a özgü bir kısıt"
    sandım, ama kullanıcı gerçek tarayıcısında da aynı takılmayı
    yaşayınca gerçek bir kod hatası olduğu ortaya çıktı.)
  - **Yükleme bitince ekran açılıyor ama hiçbir yazı görünmüyordu**
    (kutular/ikonlar/buton şekli görünüyor, başlıklar/etiketler/buton
    yazısı tamamen boş) — sebebi `web_renderer="auto"` seçiminin, tarayıcı
    WebGL + WasmGC destekliyorsa Flet'in yeni/deneysel `skwasm` motorunu
    seçmesi; bu motorda yazı tipi glyph'leri çizilmiyor. `main.py`'da
    `web_renderer=ft.WebRenderer.CANVAS_KIT` ile daha olgun CanvasKit
    motoru zorlanarak düzeltildi.
  - **"Control must be added to the page first" hatası** — `DefterPage`/
    `GenelPage.__init__` içinde ilk veri yüklemesi sırasında (dropdown/
    tablo doldurulurken) `.update()` çağrılıyordu, ama o an kontrol henüz
    sayfa ağacına eklenmemişti. `if self.page:` koruması yeterli değildi
    (o hep sayfa nesnesinin kendisini kontrol ediyordu, kontrolün mount
    durumunu değil). `ui/util.py`'deki `is_mounted()` yardımcı fonksiyonu
    ile düzeltildi.
  - **"Unknown control: FilePicker"** — `FilePicker` artık `SharedPreferences`
    ile aynı kategoride bir "Service"; eski `page.overlay.append(...)`
    yerine `page.services.append(...)` gerekiyormuş.
  - **"TabBarView: height is unbounded"** — `DefterPage`'in kendi iç
    sekmelerindeki (`Üretim/Fire`, `Satış`, `Stok & Fiyat`) `TabBarView`'a
    sınırsız yükseklikte bir üst öğe içinde yer verilmişti. Sabit
    `height=240` + taşarsa iç scroll ile düzeltildi.
- ✅ **Görsel doğrulama yapıldı** — sadece ilk ekran değil, **uçtan uca tam
  akış**: Ayarlar → Rol Seçimi → Kayıt Defteri (iç sekmeler dahil) →
  Genel Tablo (gerçek Turso verisiyle, filtreler dahil) — hepsi Playwright
  ekran görüntüleriyle, gerçek Turso veritabanına karşı doğrulandı, hiçbir
  hata banner'ı çıkmadı.

## Sıradaki adım

`python3 main.py` ile dene, geri bildirim ver — beğenirsen kalan ekranlara
geçeriz, sonunda hepsini bu depoya (`stoktakipfletui`) push'larız.
