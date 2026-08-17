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

- **Düşük stok eşiği artık kullanıcı tarafından ayarlanabilir** (Rapor
  ekranı) — Teneke/Kg/Adet için ayrı ayrı eşik girilebiliyor, "Eşiği
  Kaydet" ile Turso'daki paylaşılan `meta` tablosuna yazılıyor
  (`core/app_state.py::save_low_stock_thresholds`) — yani bir cihazdan
  değiştirilen eşik TÜM cihazlarda/rollerde geçerli olur, sadece o
  tarayıcı sekmesinde değil. Önceden web/PySide6 sürümlerinde de sabit
  kodluydu (Teneke≤5, Kg≤50, Adet≤10); aynı varsayılanlar korunuyor.

- **Kullanıcı hesapları + giriş ekranı** — admin, Kullanıcı Yönetimi'nden
  isim+şifre+rol ile hesap tanımlayabiliyor; en az bir hesap tanımlanınca
  açılışta serbest Rol Seçimi yerine giriş ekranı çıkıyor, "Beni Hatırla"
  ile cihaz bazlı otomatik giriş yapılabiliyor. Header'da her sekmeden
  erişilebilen tek bir "Senkronize Et" butonu var. Detaylar için aşağıdaki
  "Kullanıcı hesapları, giriş ekranı, senkron ve ortalanmış ekranlar"
  bölümüne bakın. Bir kullanıcıya birden fazla rol de verilebiliyor (ör.
  hem Üretim hem Satış) — erişimler birleşiyor, detaylar "Hız iyileştirmesi
  ve çoklu rol desteği" bölümünde.
- **Excel / CSV İçe Aktarma** — admin, header'daki "Excel İçe Aktar"
  butonundan herhangi bir .xlsx/.csv dosyasını Kayıt Defteri/Firmalar/
  Satışlar'dan birine, sütunları otomatik önerilen (elle düzeltilebilir)
  bir eşleştirmeyle aktarabiliyor. Detaylar için "Excel / CSV İçe Aktarma"
  bölümüne bakın.

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

## Silme davranışları + ortak veritabanı entegrasyonu (UI dışı, doğrudan fonksiyon seviyesinde test)

Kullanıcı isteği üzerine: "işlemlerin veri silindiğinde mantıklı tepkiler
verip vermediği" ve "json-react (web) ve py (Flet/PySide6) ortak bir
veritabanına erişip girdi yapabildiği" UI'dan bağımsız, doğrudan fonksiyon
çağrılarıyla, gerçek Turso DB'sine karşı test edildi:

- ✅ **Zincirin ortasındaki kaydı silme**: kalan kayıtlar doğru yeniden
  zincirleniyor (silinen kayda değil, bir öncekine bağlanıyor) —
  `recalculate_product_stock_chain` "hayalet" referans bırakmıyor.
- ✅ **Bir ürünün tüm kayıtlarını silme**: hiçbir yerde (stok listeleri
  dahil) çökme ya da hayalet veri kalmıyor.
- ✅ **Kilitli başlangıç stoğunun kilitli (en erken) kaydını silme** —
  dürüst bulgu: kilit bilgisi o TEK satıra bağlı olduğu için satırla
  birlikte kayboluyor (web/PySide6 sürümüyle birebir aynı, önceden var
  olan bir tasarım sınırı — burada "düzeltilmedi", sadece davranış
  doğrulandı ve belgelendi).
- ✅ **Firma silme**: satışı olan firma engelleniyor, olmayan başarıyla
  siliniyor.
- ✅ **Satış silme**: ilişkili Defter kaydı otomatik olarak "Bekleyen
  Satışlar"a geri dönüyor (`satisId` korunarak, tekrar "Firmaya İşle"
  ile işlenebilir durumda).
- ✅ **Toplu (çoklu id) silme** tek çağrıda sorunsuz çalışıyor.
- ✅ **Ortak veritabanı — gerçek uçtan uca doğrulama**: Python'ın
  (`core/db_core.py`) yazdığı bir kayıt, web app'in kullandığı canlı
  Cloudflare Worker API'sinden (`stoktakip4.ibrahim-yavas998.workers.dev/api/data`,
  gerçek `GET`) okunarak doğrulandı; tersine, Worker'ın `POST
  /api/data` ile (web app'in gerçek yazma yolu) yazdığı bir kayıt da
  Python'ın `state.records`'unda göründü. Worker'ın `DELETE` yolu
  (`deletedRecordIds` vb.) de aynı şekilde doğrulandı. Yani Flet,
  PySide6 ve web app **gerçekten aynı anda, aynı veritabanına, çakışma
  olmadan** yazıp okuyabiliyor — bu iddia değil, canlı ortama karşı
  ölçüldü.
- ✅ **10. gerçek hata bulunup düzeltildi (bu turda)**: Düşük stok
  kontrolü, sadece TEK birimde (ör. yalnızca Adet) takip edilen bir
  ürünü, diğer iki birim (Teneke/Kg) hep 0 olduğu için **kalıcı olarak
  yanlış alarmla işaretliyordu** (ör. gerçek veride "Tereyağ(1kg): 0 T /
  0 Kg / 500 Ad" sağlıklı olmasına rağmen sürekli uyarı veriyordu — bu
  web/PySide6 sürümünde de var olan, adet için `>0` koruması olup
  teneke/kg için olmayan asimetrik bir mantık hatasıydı). Artık her
  ürün için hangi birim(ler)in geçmişte gerçekten kullanıldığı tespit
  edilip eşik kontrolü sadece o birimlere uygulanıyor; tamamen tükenmiş
  ürünler yine doğru yakalanıyor, hiç kullanılmayan birimler artık
  yanlış alarm üretmiyor. Ayrıca küçük bir ikinci kusur da giderildi:
  uyarı banner'ı gizlenince eski metni temizlemiyordu (görsel olarak
  zararsız ama testi/kodu okuyanı yanıltabilirdi).

## Kullanıcı hesapları, giriş ekranı, senkron ve ortalanmış ekranlar (bu tur)

Kullanıcı isteği: her sayfaya SQL'e senkronize eden bir buton (otomatik
senkron korunarak), admin paneline isim+şifreyle kullanıcı tanımlama, ve
açılışta giriş ekranı + "Beni Hatırla".

- **"Senkronize Et"** — her sayfadan ayrı ayrı değil, **header'da tek, her
  sekmeden görünen bir buton** olarak eklendi (`main.py::_sync_now`) —
  header sekmeler arasında değişmediği için 6+ sayfaya aynı butonu ayrı
  ayrı kopyalamak yerine DRY bir çözüm. Otomatik senkron (her kayıt
  sonrası zaten var olan davranış) aynen korunuyor; bu buton sadece
  **elle, anında** taze veri çekmek/göndermek isteyenler için ek bir yol.
  İstersen her sayfaya kendi butonunu da eklerim, şimdilik bu tasarım
  tercihiyle ilerledim.
- **Kullanıcı Yönetimi** (`ui/dialog_user_management.py`, admin'e özel,
  header'dan açılıyor) — isim + şifre + rol ile hesap tanımlama/düzenleme/
  silme. Şifreler **düz metin olarak hiçbir yerde saklanmıyor**:
  `core/auth.py`, PBKDF2-HMAC-SHA256 + kullanıcıya özel rastgele `salt` +
  200.000 iterasyonla hash'liyor, DB'ye sadece `passwordHash`/`passwordSalt`
  yazılıyor. **Neden Turso/libSQL'in kendi "login role" mekanizması değil
  de bir `users` tablosu?** — Turso yalnızca *tüm veritabanına* erişim için
  tek bir bağlantı token'ı sağlıyor; Postgres'teki `CREATE ROLE ... LOGIN`
  gibi, veritabanı içinde ayrı ayrı uygulama kullanıcıları tanımlayan bir
  mekanizma yok. Yani mağaza personelinin adıyla/şifresiyle giriş yapması
  için tek pratik/standart yöntem, hash'lenmiş şifrelerin tutulduğu bir
  uygulama-seviyesi tablo — büyük servislerin (Firebase, Supabase dahil)
  içeride yaptığı da bu.
- **Giriş ekranı** (`ui/page_login.py`) — sadece `state.users` doluysa
  gösteriliyor; hiç kullanıcı tanımlanmamışken (yeni kurulum ya da bu
  özellikten önceki mevcut kullanım) eski serbest Rol Seçimi ekranı **hiç
  bozulmadan** çalışmaya devam ediyor — admin, Kullanıcı Yönetimi'nden ilk
  hesabı tanımlayınca bir sonraki açılıştan itibaren giriş ekranına geçiliyor.
- **"Beni Hatırla"** — şifre hiçbir zaman cihazda saklanmıyor; sadece
  rastgele bir oturum belirteci (`generate_remember_token`) hem cihazda
  (Flet `SharedPreferences`) hem o kullanıcının DB satırında tutulup
  açılışta karşılaştırılıyor. Şifre değişince (ya da yeni şifre verilince)
  DB'deki belirteç temizleniyor — yani şifre sıfırlanan bir hesabın eski
  "hatırlanan" oturumları **tüm cihazlarda** otomatik iptal oluyor. Bu, o
  cihaz fiziksel olarak aynı kaldığı sürece (telefon değişmediği sürece)
  tekrar şifre sormadan giren "Google ile Giriş Yap"a benzer bir sonuç
  veriyor — ayrı bir Google/Firebase OAuth entegrasyonuna (ki bu paket
  adı+SHA-1 fingerprint için ayrı bir Google Cloud projesi kurulumu
  gerektirir) şimdilik gerek bırakmıyor.
- **11. gerçek hata bulunup düzeltildi — ekran ortalama**: kullanıcı,
  tek başına duran ekranların (Ayarlar/Giriş/Rol Seçimi) pencere sol
  üstüne sabit kaldığını, ekran boyutuna göre otomatik ortalanmadığını
  fark etti. `page.horizontal_alignment`/`vertical_alignment=CENTER` ile
  düzeltilmeye çalışılırken **iki ayrı gizli Flet/Flutter davranışı**
  ortaya çıktı: (1) `page.scroll` açıkken bir alanda `autofocus=True`
  olması, Flutter'ın o alanı görünüre getirmek için sayfayı sol-üste
  kaydırmasına yol açıp ortalamayı bozuyordu — sayfa seviyesinde scroll'u
  kapatarak düzeltildi (taşma olursa zaten alt bileşenler kendi scroll'unu
  kullanıyor); (2) `ft.Checkbox` tek başına bir `Column` içinde tam
  genişliğe yayılan bir kutu raporluyor, bu da onu içeren `Column`'un
  "ortalanması"nı anlamsızlaştırıyordu (zaten tam genişlik olduğu için
  ortalamanın hiçbir görünür etkisi olmuyordu) — `ft.Row([checkbox],
  tight=True)` ile checkbox'ı kendi doğal genişliğine sıkıştırıp
  düzeltildi. Artık Giriş/Ayarlar/Rol Seçimi ekranları hem masaüstü hem
  telefon boyutunda (420px genişlik dahil test edildi) otomatik olarak
  hem yatayda hem dikeyde ortalanıyor.
- ✅ **Uçtan uca Playwright doğrulaması**: Ayarlar kaydet → (yeni)
  kullanıcı varken otomatik olarak Giriş ekranına düşme → doğru
  kullanıcı adı/şifreyle giriş → "Beni Hatırla" işaretli giriş →
  Dashboard'da kimlik rozeti (`"ad — Rol"`) + "Çıkış Yap" (artık "Rol
  Değiştir" değil) görünmesi → "Senkronize Et" hatasız çalışması →
  "Çıkış Yap" ile ortalanmış Giriş ekranına geri dönülmesi — hepsi
  gerçek Turso DB'sine karşı, sıfır `PAGEERROR` ile doğrulandı.

## Hız iyileştirmesi ve çoklu rol desteği (bu tur)

Kullanıcı isteği: uygulamanın daha hızlı çalışması ("özellik bozulmadığı
sürece her şeyi değiştirebilirsin" yetkisiyle) ve bir kullanıcıya birden
fazla rol tanımlanabilmesi.

- **DB katmanı tek round-trip'e indirildi** (`core/db_core.py`) — hiçbir
  davranış/özellik değişmedi, sadece **kaç kere ağa çıkıldığı** değişti.
  Önceden `get_all_data()` 9 ayrı `.execute()` (5 tablo + 4 meta anahtarı),
  `save_all_data()` ise tabloya göre 10'a kadar ayrı çağrı yapıyordu; Turso
  uzak bir sunucu olduğu için asıl gecikme sorgu **başına** sabit bir ağ
  gidiş-dönüşü — satır sayısı değil. `libsql_client`'ın `.batch()`'i farklı
  SQL'leri bile tek round-trip'te çalıştırıp sırayla eşleşen sonuç listesi
  döndürdüğü için artık ikisi de her zaman **tam olarak 1** `.batch()`
  çağrısına indirgeniyor. Gerçek Turso veritabanına karşı ölçüldü:
  `get_all_data()` önceden çok saniye sürerken artık **~0.07s**,
  `save_all_data()` **~0.11s**. Round-trip write/read/cleanup testiyle
  hiçbir veri kaybı/regresyon olmadığı doğrulandı.
- **Bir kullanıcıya birden fazla rol** (`core/models.py::compute_effective_access`)
  — Kullanıcı Yönetimi'nde artık tek seçimlik Dropdown yerine Üretim/Satış/
  Admin için ayrı ayrı işaretlenebilen kutucuklar var; en az biri seçili
  olmalı. Kullanıcının fiili erişimi seçtiği rollerin **birleşimi**:
  sayfalar (Kayıt Defteri/Rapor/Satış/Genel Tablo) birleşir, Kayıt
  Defteri'nde Üretim+Satış alanları birlikte görünür. DB'de `role` sütunu
  artık virgülle ayrılmış bir liste (`"uretim,satis"`); eski tek-rollü
  satırlar (`"admin"`) hiçbir değişiklik gerekmeden aynı şekilde okunuyor
  (`roles_from_field`/`roles_to_field`). Tek rol seçilen kullanıcılar için
  davranış (renk, etiket, erişilebilir sayfalar) **eskisiyle birebir aynı**
  — bu katkısal bir genişletme, geriye dönük kırılma yok. Çoklu rollü bir
  kullanıcı için kimlik rozeti `"ad — Üretim + Satış"` şeklinde, ayırt
  edici bir aksan renkte (`#F59E0B`) gösteriliyor; admin seçiliyse admin
  rengi/etiketi kazanıyor.
- ✅ Gerçek Turso DB'sine karşı hem saf mantık hem uçtan uca Playwright ile
  doğrulandı: Üretim+Satış işaretlenmiş bir kullanıcı oluşturma (gerçek
  tıklamalarla), listede doğru görünmesi, o kullanıcıyla giriş yapınca
  Kayıt Defteri'nde hem Üretim/Fire hem Satış sekmelerinin, header'da hem
  4 sayfanın da (Rapor dahil) görünmesi, "Satışlar & Firmalar" sekmesinin
  tam çalışması — sıfır hata.

## Excel / CSV İçe Aktarma (bu tur)

Kullanıcı isteği: elde olan bir Excel dosyasının ilgili alanla eşleştirilip
işlenebilmesi — "tablo isimlerini nasıl eşleştireceğiz" sorusuna karşılık,
tabloya özel olmayan, tek genel bir akış kuruldu (`ui/dialog_excel_import.py`,
admin'e özel, header'daki "Excel İçe Aktar" butonundan açılıyor):

**dosya seç (.xlsx/.csv) → hedef tablo seç (Kayıt Defteri / Firmalar /
Satışlar) → sütunlar otomatik eşleştirilir (elle düzeltilebilir) → önizle →
onayla → tek round-trip'te yaz.**

- **Otomatik sütun eşleştirme**: Excel başlığı ile hedef tablonun alan adı
  normalize edilip (Türkçe karakter sadeleştirme, boşluk/sembol temizleme)
  karşılaştırılıyor; birebir ya da alt-dize eşleşmesi yoksa (ör. "Barkod" vs
  `barcode`, "Firma Adı" vs `sirketAdi`) küçük bir eş anlamlı sözlüğü devreye
  giriyor. Hiçbir eşleştirme sessizce yanlış gitmiyor — her sütunun yanında
  elle düzeltilebilir bir seçici var, önizleme onaylanmadan hiçbir veri
  yazılmıyor.
- **Güvenli atlama**: hedef tabloya göre zorunlu alan(lar) (records için
  ürün kodu/adı, companies için ad, sales için ürün adı/firma adı) hiçbiri
  eşleşip dolu değilse o satır sessizce değil, **sayılarak** atlanıyor
  ("X satır aktarılacak, Y satır atlanacak"). Yanlış hedef tablo seçilirse
  (ör. şeması hiç uymayan bir CSV) bütün satırlar güvenle atlanıyor, hiçbir
  satır yanlış alanlara zorla yazılmıyor.
- **id sütunu eşlenirse güncelleme, eşlenmezse yeni kayıt** — `core/db_core.py`'nin
  var olan upsert modeliyle birebir aynı; yani Genel Tablo'dan dışa
  aktarılmış bir CSV, Excel'de düzenlenip aynı şekilde geri içe aktarılabilir
  (id'ler eşleştiği için satırlar güncellenir, çoğalmaz).
- Gerçek dosyalarla test edildi: Genel Tablo'nun kendi CSV export'u (`;`
  ayraçlı, BOM'lu, Türkçe başlıklı) doğru ayrıştırıldı ve tüm sütunlar
  otomatik eşleşti; şeması tamamen farklı bir CSV hedef tabloyla
  eşleşmeyince hiçbir satır yazılmadı (güvenlik testi). Gerçek tarayıcıdan,
  gerçek dosya seçiciyle (Playwright'ın `expect_file_chooser` ile), gerçek
  Turso DB'sine karşı uçtan uca doğrulandı: dosya seç → "Firmalar" hedefi →
  otomatik eşleştirme → önizleme özeti doğru → içe aktar → iki satır da
  doğru alanlarla DB'de göründü — sıfır hata.

## Tema anahtarı ve telefon genişliğinde kullanılabilirlik (bu tur)

Kullanıcı isteği: arayüzü güzelleştirme, dark mode seçenekleri, ve Android
uygulamasının gerçekten kullanılabilir olması. Framework değişikliği
(baştan başka bir GUI) değerlendirildi ama gerekmedi — sorunlar Flet'in
kendi imkanlarıyla (Material 3 tema sistemi zaten vardı, sadece hiç
bağlanmamıştı; responsive genişlik hesaplaması) çözüldü, mevcut/test edilmiş
kod tabanı korunarak.

- **Tema anahtarı artık gerçekten çalışıyor** — `ui/theme.py`'deki koyu/açık/
  sistem + 7 aksan renkli altyapı bu tura kadar hiçbir düğmeye bağlı değildi
  (`apply_theme` sadece açılışta bir kere, sabit "dark" ile çağrılıyordu).
  Header'a bir ay/güneş simgesi eklendi — tıklandıkça Koyu → Açık → Sistem
  arasında döngüsel geçiş yapıyor, seçim `SharedPreferences`'a kaydedilip
  bir sonraki açılışta hatırlanıyor. Canlı olarak (sayfa yeniden yüklenmeden)
  tüm renk paletini değiştirdiği doğrulandı.
- **Header telefon genişliğine göre daralıyor** — önceden 6-7 metinli buton
  hiçbir zaman 393px'lik (yaygın Android) bir ekrana sığmıyordu, görünmeyen
  kısım yatay kaydırmaya kalıyordu (keşfedilmesi zor). Şimdi: sık kullanılan
  işlemler (tema, senkron) simge-buton olarak kalıyor, seyrek kullanılanlar
  (Barkod Eşleştirme, İrsaliye Arşivi, admin'de Kullanıcı Yönetimi + Excel
  İçe Aktar) tek bir "⋮" menüsünde toplandı. `page.width < 520` olduğunda
  (gerçek telefon genişliği) başlık metni gizleniyor, kimlik rozetesi sadece
  isme iniyor (tam bilgi tooltip'te), "Çıkış Yap" da simgeye dönüşüyor —
  masaüstünde davranış birebir eskisiyle aynı.
- **12. gerçek hata bulunup düzeltildi — sabit piksel genişlikler telefonda
  taşıyordu**: İlk-açılış Ayarlar ekranındaki alanlar `width=420` sabitti;
  393px'lik bir ekranda bu, alanın bir kısmının görünmez/tıklanamaz hale
  gelmesine yol açıyordu — **gerçek bir telefon genişliğinde test edilene
  kadar fark edilmedi** (masaüstü genişliğinde tamamen normal görünüyordu).
  Aynı sorun Giriş ekranı (320px) ve tüm diyalogların (Kullanıcı Yönetimi,
  Excel İçe Aktar, Barkod Eşleştirme, İrsaliye Arşivi) dış kapsayıcı
  genişliklerinde de vardı. `ui/util.py::responsive_width(page, ideal)` —
  `page.width` ekrandan darsa değeri küçültüyor, geniş ekranda idealde
  kalıyor — tüm bu yerlere uygulandı.
- ✅ Gerçek bir Android telefon görünüm alanında (393×851, Pixel 5 boyutu)
  uçtan uca doğrulandı: Ayarlar ekranı artık taşmıyor → Giriş ekranı doğru
  ortalanıyor → Dashboard header'ı tek satıra sığıyor, hiçbir buton
  görünmez kalmıyor → "⋮" menüsü açılıp doğru konumlanıyor → Kullanıcı
  Yönetimi diyaloğu (alanlar + rol kutucukları) taşmadan tek sütuna
  diziliyor. 1300px masaüstü genişliğinde hiçbir görsel regresyon yok
  (başlık metni, tam kimlik rozetesi, "Çıkış Yap" metinli buton aynen
  duruyor) — sıfır hata.

## Durum

Artık kanıt-of-concept kapsamındaki **tüm ana ekranlar + hesap/giriş
sistemi tamam ve görsel olarak cilalanmış**: Rol Seçimi, Üretim/Satış/Admin
dashboard'ları, Genel Tablo, Satışlar & Firmalar, Rapor, Ürün/Barkod
Eşleştirme, İrsaliye Arşivi (+OCR), Giriş ekranı + Beni Hatırla + Kullanıcı
Yönetimi + Senkronize Et. `python3 main.py` ile `http://localhost:8551`
üzerinden denenebilir.

**Android APK derlemesi artık ayrı bir repoda**:
[ibrahimyavas/Stoktakipandroidapp](https://github.com/ibrahimyavas/Stoktakipandroidapp)
— Android SDK/Java/Gradle gerektirdiği için bu sandbox'ta yapılamıyor,
GitHub Actions'a taşındı. O repo bu koddan bir KOPYA değil; her derlemede
buradaki (`stoktakipfletui`) kodu taze çekip üzerinde `flet build apk`
çalıştırıyor — yani geliştirme her zaman burada devam ediyor, tek gerçek
kaynak bu repo.
