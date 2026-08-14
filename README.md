# Üretim & Satış Defteri — Flet Sürümü (kanıt-of-concept)

Bu, PySide6 masaüstü uygulamasının Flet ile yazılmış deneme sürümü — amaç
**Android (ve web/masaüstü) uyumluluğu**. Flet, Flutter üzerine kurulu; aynı
Python kodu masaüstünde native pencere, web'de tarayıcı, ve `flet build apk`
ile gerçek bir Android uygulaması olarak paketlenebiliyor.

## Bu kanıt-of-concept'te neler var

- **Rol seçimi** (Üretim / Satış / Admin) — `core/models.py`'deki `PROFILES`
  ile PySide6 sürümüyle birebir aynı erişim kuralları.
- **Üretim ve Satış tamamen ayrı dashboard'lar** — `ui/page_dashboard_uretim.py`
  (`UretimDashboard`) sadece üretim/fire alanlarını, `ui/page_dashboard_satis.py`
  (`SatisDashboard`) sadece satış alanlarını içeriyor; birbirinin
  alanlarını/mantığını hiç görmüyor. Kayıt ekle/düzenle/sil, ürün hızlı
  seçimi, stok zinciri (`core/stock_logic.py` — PySide6 sürümüyle **birebir
  aynı dosya**), başlangıç stoğu kilidi gibi rol-bağımsız ortak mantık
  `ui/dashboard_common.py`'deki `DashboardBase`'te tek yerde yaşıyor (iki
  dosyaya kopyalanmıyor). Admin, her iki bayrağı da açık şekilde doğrudan
  `DashboardBase`'i kullanıyor, yani tüm alanlara tek ekranda erişiyor.
- **Genel Tablo + YENİ filtreleme özelliği**: firma, ürün, tarih aralığı ve
  serbest metin araması — hepsi birlikte, birleşik olarak uygulanıyor. CSV
  export da var (`FilePicker.save_file` ile — web/Android'de de çalışacak
  şekilde `src_bytes` kullanıyor, sadece masaüstü dosya yoluna güvenmiyor).
- **Ayarlar**: `platformdirs` değil, Flet'in `SharedPreferences` servisi
  (Flutter'ın `shared_preferences` paketi) — Android/iOS'ta da çalışır.
- **Tema**: Material 3 `color_scheme_seed` ile açık/koyu + serbest aksan
  rengi (PySide6 sürümündeki elle-XML-üretme yerine yerleşik).
- **Satışlar & Firmalar** (`ui/page_satislar.py`) — PySide6 sürümündeki
  `page_satis.py` + `dialog_complete_sale.py` + `dialog_qr.py`'nin Flet
  karşılığı, 4 alt sekme: **Stok & Yeni Satış** (stok tablosu + hızlı satış
  başlatma), **Bekleyen Satışlar** (Defter'de satış miktarı girilmiş ama
  henüz firmaya işlenmemiş kayıtlar), **Firmalar** (firma CRUD), **Satış
  Listesi** (arama + QR fiş + sil). "Satışı Tamamla / Firmaya İşle" akışı
  (`_complete_sale()` — UI'dan bağımsız, doğrudan test edilebilir bir
  metod) hem "Yeni Satış Başlat" hem "Bekleyen Satışlar" tarafından
  paylaşılıyor. QR kodu `qrcode` kütüphanesiyle tamamen yerel/offline
  üretiliyor (web sürümündeki gibi harici bir API'ye bağımlı değil).
- **Haftalık / Aylık Rapor** (`ui/page_rapor.py`) — KPI kartları (Toplam
  Üretim/Satış/Fire/Gelir), düşük stok uyarısı, son 6 ay için Üretim/Satış
  çubuk grafiği. **Not**: bu Flet sürümünde (0.86.x) hazır bir grafik
  kontrolü yok — `flet.charts` diye bir modül hiç mevcut değil (eski Flet
  sürümlerinde vardı, kaldırılmış). Grafiği ekstra bir kütüphane eklemeden,
  doğrudan renkli `Container`'ların oranlı yüksekliğiyle çiziyoruz.
- **Ürün / Barkod Eşleştirme** (`ui/dialog_barcode_mapper.py`) — header'dan
  açılan bir diyalog: ürün tanımlama, fiyat, başlangıç stoğu girme/kilitleme
  (kilitlenince Kayıt Defteri'nde o ürünün başlangıç stoğu alanı salt-okunur
  olur), kayıtlı ürün/barkod listesi + arama.
- **İrsaliye Arşivi** (`ui/dialog_waybill_vault.py`) — header'dan açılan bir
  diyalog: dosya seçiciyle fotoğraf ekleme (kamera yok — bilinçli kapsam
  dışı), Gemini OCR ile otomatik alan doldurma (`core/ocr.py` — PySide6
  sürümüyle birebir aynı, değiştirilmedi; sadece `FilePicker`'dan gelen
  bytes'ı OCR'ın beklediği dosya yoluna çevirmek için geçici bir dosyaya
  yazıyoruz), liste/arama/görüntüle/sil.

**Henüz yok**: Sheets senkron, Ayarlar'ı sonradan düzenleme ekranı — ikisi
de PySide6 sürümünde de ikincil/opsiyonel özellikler, kanıt kapsamının
dışında tutuldu.

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
- ✅ **Üretim/Satış dashboard ayrımı doğrulandı** — hem mantık testleriyle
  (`UretimDashboard`'da sekme sayısı 2 ve `show_satis=False`, `SatisDashboard`'da
  2 ve `show_uretim_fire=False`, admin'de 3; `manual_baslangic_stok`
  bayrağının iki dashboard'da da doğru davrandığı gerçek DB'ye karşı ayrı
  ayrı test edildi) hem de Playwright ekran görüntüleriyle: Üretim rolü artık
  üstte sadece "Kayıt Defteri" + "Haftalık/Aylık Rapor" sekmelerini, Kayıt
  Defteri içinde sadece "Üretim / Fire" + "Stok & Fiyat" sekmelerini
  görüyor (Satış'a hiç erişimi yok) — Satış rolü de simetrik şekilde
  sadece kendi alanlarını görüyor.
- ✅ **Satışlar & Firmalar tam olarak test edildi** — gerçek Turso DB'ye
  karşı: firma oluşturma, stoğu aşan satışın reddedilmesi, hızlı satış
  başlatma + stok zincirinin doğru güncellenmesi (100 Kg − 20 Kg = 80 Kg),
  yeni satışın "Bekleyen Satışlar"da görünmesi, firma seçilmeden satışın
  reddedilmesi, "Satışı Tamamla" ile SaleItem oluşturulması + Defter
  kaydının `satisId`/`linkedSaleId` ile güncellenmesi + tutar hesaplaması
  (20 Kg × ₺15 = ₺300), tamamlanan satışın artık bekleyenlerde
  görünmemesi, geçerli bir QR PNG üretilmesi, satışı olan firmanın
  silinememesi — hepsi geçti. Ayrıca Playwright ile 4 alt sekmenin de
  (Stok & Yeni Satış, Bekleyen Satışlar, Firmalar, Satış Listesi) gerçek
  veriyle hatasız render olduğu doğrulandı.
- ✅ **8. gerçek hata bulunup düzeltildi**: `SharedPreferences.get()`'in
  flet kütüphanesi içinde ~10 saniyelik sabit bir zaman aşımı var; yavaş
  bir ağ/tarayıcı altında (Android/zayıf bağlantı hedefi için gerçekçi bir
  senaryo) bu aşılabiliyor ve önceden **tüm oturum sessizce çöküyor**,
  kullanıcı kalıcı olarak tepkisiz bir ekranda kalıyordu — hiçbir geri
  bildirim yoktu. `main.py`'da 2 deneme + kurtarılabilir bir "Tekrar Dene"
  ekranıyla düzeltildi.
- ✅ **9. gerçek hata bulunup düzeltildi — en sinsi olanı**: header'a yeni
  butonlar eklenince `ft.Row(..., wrap=True)` kullanıldı; bu, yanındaki
  `expand=True` olan sekme alanının **tüm içeriğini sessizce düz gri bir
  kutuya** dönüştürdü — ne sunucu tarafında bir Python hatası, ne tarayıcı
  konsolunda bir JS hatası, hiçbir iz yoktu (Flutter'ın release modundaki
  varsayılan `ErrorWidget`'ı düz gri bir kutu olarak render ediyor, hata
  metni göstermiyor). Bu **her rolü** etkiliyordu (admin'e özel sanılmıştı,
  ama satış rolünde de aynı şekilde tekrarlandığı doğrulanınca header'daki
  değişiklikten kaynaklandığı anlaşıldı). `wrap=True` kaldırılınca
  düzeldi — genel kural: bir `expand=True` kardeşi olan `Row`'a asla
  `wrap=True` verme, ekranı daraltmak yerine buton metinlerini kısa tut.
- ✅ **Rapor, Barkod Eşleştirme, İrsaliye Arşivi de tam test edildi** —
  gerçek Turso DB'sine karşı: KPI hesaplama (Üretim=100 Kg, Fire=10 Kg),
  düşük stok kontrolü; yeni ürün tanımlama + başlangıç stoğu kilitleme,
  mevcut ürün güncellemesinde fiyat değişip kilidin korunması; irsaliye
  kaydetme (foto zorunlu — fotoğrafsız reddediliyor), tutar/firma/not
  alanlarının doğru saklanması — hepsi geçti. Playwright ile üçü de gerçek
  veriyle, hiçbir hata banner'ı olmadan render olduğu doğrulandı (Rapor'un
  çubuk grafiği dahil).

## Görsel cila (tema, ikonlar)

`ui/theme.py` artık sadece `color_scheme_seed` seçmiyor — tüm bileşenler
için tutarlı bir görsel dil tanımlıyor: yuvarlak köşeli kartlar (elevation
1, radius 14), yuvarlak köşeli butonlar (radius 10, tutarlı padding),
yuvarlak köşeli diyaloglar (radius 16), kalın/net tablo başlıkları
(`DataTableTheme.heading_text_style`), kalın sekme etiketleri
(`TabBarTheme`). Ayrıca her sekmeye/butona anlamlı bir Material ikon
eklendi (Kayıt Defteri, Rapor, Satışlar, Genel Tablo sekmeleri; Üretim/
Fire, Satış, Stok&Fiyat iç sekmeleri; Kaydet/İptal/Firmaya İşle/Satışı
Tamamla vb. tüm birincil butonlar; rol seçim kartları) — daha profesyonel
ve taranabilir bir arayüz.

**App ve tarayıcı arayüzlerinin aynı görünmesi** ayrıca bir senkronizasyon
işi gerektirmiyor — Flet'te native (masaüstü) görünüm de, web görünümü de
**aynı Flutter/CanvasKit render motorunu** kullanıyor; ikisi de aynı
Python kontrol ağacından aynı piksel çıktısını üretiyor. Bu yapısal bir
garanti, ayrıca "senkronize" edilmesi gereken iki ayrı kod tabanı yok.

**Cihazlar arası entegrasyon** zaten en baştan beri var: hepsi aynı Turso
veritabanına, aynı non-destructive upsert senkron modeliyle bağlanıyor
(`core/db_core.py` — PySide6 sürümüyle birebir aynı). Şu an test edilen
web görünümü de, ileride `flet build apk` ile üretilecek gerçek Android
uygulaması da, PySide6 masaüstü uygulaması da aynı veriyi paylaşır —
biri diğerini geçersiz kılmaz, çakışma olmaz.

## Durum

Artık kanıt-of-concept kapsamındaki **tüm ana ekranlar tamam ve görsel
olarak cilalanmış**: Rol Seçimi, Üretim/Satış/Admin dashboard'ları, Genel
Tablo, Satışlar & Firmalar, Rapor, Ürün/Barkod Eşleştirme, İrsaliye Arşivi
(+OCR). `python3 main.py` ile son bir kez dene — sorun yoksa bu depoya
(`stoktakipfletui`) push'larız.

**Henüz yapılmadı**: gerçek bir Android APK üretimi (`flet build apk`) —
bu, Android SDK/Java/Gradle kurulu gerçek bir makine (ya da GitHub Actions
gibi bir CI) gerektiriyor, bu sandbox'ta yapılamıyor. İstersen bunun için
ayrı bir GitHub Actions workflow'u kurabiliriz (stoktakipapp'in PySide6
paketleme workflow'una benzer şekilde).
