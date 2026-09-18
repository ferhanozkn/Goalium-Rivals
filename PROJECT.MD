# PROJECT.MD

**Çalışma adı:** Futbol Bilgi Oyunu (web + sonraki aşamada mobil)
**Doküman dili:** Türkçe
**Hedef okuyucu:** Codex, Claude Code ve insan geliştiriciler
**Durum:** Faz 6 tamamlandı — kritik oyun/API akışları, iki tarayıcılı canlı maç, erişilebilirlik, temel yük, katalog kalitesi ve PostgreSQL yedekleme/geri yükleme kontrolleri geçti. Karar kaydı: [`docs/phase-0.md`](docs/phase-0.md); faz notları: [`docs/phase-1.md`](docs/phase-1.md), [`docs/phase-2.md`](docs/phase-2.md), [`docs/phase-3.md`](docs/phase-3.md), [`docs/phase-4.md`](docs/phase-4.md), [`docs/phase-5.md`](docs/phase-5.md), [`docs/phase-6.md`](docs/phase-6.md).

---

## 0. Bu doküman nasıl kullanılır

Bu dosya projenin tek referans dokümanıdır. Kod üreten bir ajan (Codex, Claude Code) bir göreve başlamadan önce ilgili bölümü okur ve dokümandaki kurallara aykırı kod yazmaz.

Kurallar:

1. Bu dokümanla çelişen bir istek gelirse önce doküman güncellenir, sonra kod yazılır.
2. Dokümanda "öneri" veya "Faz 0'da kesinleşecek" etiketi taşıyan sayısal değerler koda sabit (magic number) olarak gömülmez; ayar/konfigürasyon katmanından okunur.
3. Yeni bir mod, ekran, tablo veya API uç noktası eklendiğinde bu dosyanın ilgili bölümü aynı değişiklik setinde güncellenir.

---

## 1. Ürün özeti

Futbol bilgisini ölçen, iki dilli (Türkçe/İngilizce), tarayıcı tabanlı bir yarışma oyunu. Oyuncular beş farklı modda tek başına pratik yapar veya çevrim içi olarak birbirleriyle yarışır.

İlk sürüm web'dir. Mobil uygulama sonradan gelir ve **aynı Django backend'ine, aynı sürümlü API üzerinden** bağlanır. Mobil için ayrı backend, ayrı veritabanı veya ayrı iş kuralı yazılmaz.

### Beş mod

| # | Mod | Kısa tanım |
|---|---|---|
| 1 | Çöp adam | Futbolla ilgili bir kelimeyi harf tahmin ederek bulma |
| 2 | Kariyer yolu | Kulüp geçmişinden oyuncuyu bulma |
| 3 | Süreli genel kültür | Sabit sürede olabildiğince çok soru yanıtlama |
| 4 | Tarihi maç skoru | 2010 sonrası bir maçın skorunu bilme |
| 5 | İlk 11'deki eksik oyuncu | Gösterilen ilk 11'de gizlenen oyuncuyu bulma |

### Oyun biçimleri

- **Pratik:** tek oyunculu, her mod için, misafirlere de açık.
- **Canlı bire bir maç:** iki oyuncu gerçek zamanlı, aynı soruları aynı anda görür.
- **Farklı zamanlı düello (asenkron):** bir oyuncu oynar, rakip aynı soru setini kendi zamanında oynar.
- **Özel oda:** 2–8 kişi, oda kodu ile, canlı.

Maçlar **karışık** (turlar arasında mod değişir) veya **tek modlu** olabilir.

### Ranked kuralı (kritik)

Ortak ranked puanı **yalnız** şu koşulların tamamını sağlayan maçlardan etkilenir:

- canlı (gerçek zamanlı),
- bire bir,
- karışık modlu,
- **eşleştirme sistemiyle (matchmaking) başlamış** olan maç.

Davetle başlayan maçlar, özel odalar, asenkron düellolar ve pratik oyunlar ranked puanını **etkilemez**. Bu kural motorun içinde tek bir noktada uygulanır (bkz. §7).

---

## 2. Temel ilkeler

1. **PostgreSQL zorunlu veritabanıdır ve kalıcı veriler için tek doğruluk kaynağıdır.** Kullanıcı, içerik, maç, cevap ve derece kayıtları PostgreSQL'de tutulur. SQLite geliştirme ortamında dahi kullanılmaz.
2. **Redis kalıcı veri tutmaz.** Redis yalnız gerçek zamanlı mesajlaşma (Channels layer), kısa ömürlü oturum durumu, eşleştirme kuyruğu ve önbellek içindir. Redis tamamen silinse oyun verisi kaybolmaz; yalnız devam eden canlı maçlar düşer.
3. **Sunucu otoritesidir.** Soru seçimi, süre ölçümü, cevap doğrulama ve puanlama sunucuda yapılır. İstemciden gelen skor, süre veya "doğru bildim" bilgisine güvenilmez. Doğru cevap, soru gönderilirken istemciye **gönderilmez**.
4. **İstemci veritabanına doğrudan erişmez.** Vue ve gelecekteki mobil istemci yalnız sürümlü REST + WebSocket API'yi kullanır.
5. **Doğrulanmamış içerik oyuncuya gösterilmez.** Her soru bir editör onayı durumundan geçer.
6. **İki dil eşdeğerdir.** Arayüz ve sorular Türkçe ve İngilizce hazırlanır; bir dilde eksik içerik varsa o soru o dilde yayınlanmaz.

---

## 3. Teknoloji yığını

| Katman | Seçim | Not |
|---|---|---|
| Backend | Django (LTS) + Django REST Framework | Tek backend, web ve mobil ortak |
| Gerçek zamanlı | Django Channels + WebSocket | Tasarım referansı: https://channels.readthedocs.io/en/stable/ |
| Veritabanı | **PostgreSQL** | Zorunlu, tek doğruluk kaynağı |
| Ara katman | Redis | Channels layer, eşleştirme kuyruğu, önbellek, kilit |
| Zamanlanmış işler | Celery + Redis (veya Django-Q) | İçe aktarma, süresi dolan düellolar, temizlik |
| Frontend | Vue 3 + Vite + Pinia + Vue Router + vue-i18n | Modern, futbol temalı arayüz |
| API şeması | OpenAPI (drf-spectacular) | Mobil istemci sözleşmesinin kaynağı |
| Test | pytest + pytest-django, Vitest, Playwright | Playwright iki tarayıcılı canlı maç testleri için |
| Dağıtım | Docker Compose (geliştirme), DigitalOcean (bulut) | postgres, redis, backend, worker, frontend servisleri |

**Bulut sağlayıcısı:** DigitalOcean kullanılacaktır. Yerel geliştirme Docker Compose ile yapılır; staging ve üretim ortamları container tabanlı servisler olarak DigitalOcean üzerinde çalıştırılır. DigitalOcean ürün seçimi, bölge ve ağ/topoloji ayrıntıları dağıtım tasarımında kesinleştirilecek; PostgreSQL kalıcı verinin, Redis ise yalnız geçici gerçek zamanlı durumun kaynağı olmaya devam edecektir.

---

## 4. Oyun modları — kurallar

Aşağıdaki sayısal değerler **Faz 0'da kesinleştirilmiştir**. Hepsi konfigürasyondan okunur, koda gömülmez; ayrıntılı formüller [`docs/phase-0.md`](docs/phase-0.md) içindedir.

Ortak kurallar:

- Her tur için sunucu bir `deadline` (UTC) üretir ve istemciye gönderir. Süre sunucu saatine göre ölçülür.
- Süre aşımı = yanlış cevap sayılmaz, **ayrı bir sonuç türüdür** (`timeout`) ve puanı sıfırdır.
- Cevap normalizasyonu: Unicode NFKC, `tr` yerelinde küçük harfe çevirme, baştaki/sondaki boşluk temizliği, çoklu boşluk sadeleştirme, noktalama temizliği, Türkçe karakter eşdeğerliği (ı/i, ş/s, ğ/g, ü/u, ö/o, ç/c), takma ad tablosu araması, ardından uzunluk 1–3 için 0, 4–7 için 1, 8+ için 2 Levenshtein toleransı.
- Türkçe büyük/küçük harf dönüşümünde `tr` yereli kullanılır (I/ı, İ/i tuzağı).

### 4.1 Çöp adam

- **Soru:** futbolla ilgili bir kelime/ifade (oyuncu, kulüp, teknik direktör, stadyum, turnuva) + kategori etiketi.
- **Gösterim:** boşluk ve tire baştan açık; harfler gizli.
- **Hak:** 6 yanlış harf. Süre: 90 sn.
- **İpucu:** en fazla 2 ipucu (ör. ülke, dönem); her ipucu 15 puan düşürür.
- **Puan:** `max(0, 100 − (yanlış harf × 10) − (ipucu × 15)) + floor(kalan saniye / 5)`.
- **Dil:** Türkçe kelime seti Türk alfabesi ile, İngilizce set Latin alfabesi ile oynanır. Aynı varlık iki dilde farklı yazılabilir; her dil için ayrı kelime kaydı tutulur.

### 4.2 Kariyer yolu

- **Soru:** bir oyuncunun kronolojik kulüp geçmişi (sezon aralığı + kulüp), oyuncu adı gizli.
- **Gösterim:** ilk kulüp açık; 10, 20, 30, 40 ve 50. saniyelerde birer satır daha açılır. Süre: 60 sn.
- **Hak:** 3 tahmin.
- **Cevap:** serbest metin, normalizasyon + takma ad tablosu ile eşleştirilir.
- **Puan:** `max(0, 100 − (açılan ek satır × 15) − (yanlış tahmin × 10)) + min(10, floor(kalan saniye / 10))`.

### 4.3 Süreli genel kültür

- **Soru:** 4 şıklı çoktan seçmeli, zorluk etiketli.
- **Format:** sabit toplam sürede (60 sn) arka arkaya soru; soru başına ayrıca deadline yoktur.
- **Ceza:** yanlış cevapta toplam deadline'dan 3 sn kesilir; pas hakkı serbest ve cezasızdır.
- **Puan:** `round_half_up(10 × zorluk katsayısı) + max(0, 5 − floor(soruya cevap süresi / 2))`. Katsayılar: kolay 1.0, orta 1.5, zor 2.0.
- **Canlı maçta:** iki oyuncu aynı soru dizisini aynı sırayla alır.

### 4.4 Tarihi maç skoru

- **Kapsam:** yalnız **2010 ve sonrası** maçlar.
- **Soru:** iki takım, turnuva/lig, tarih; isteğe bağlı ipucu (stat, gol atanlardan biri).
- **Cevap:** iki sayı alanı (ev – deplasman). Esas alınan skor **normal süre (90 dk) sonucudur**; uzatma veya penaltı varsa soru metninde ayrıca belirtilir ve ayrı alan sorulmaz.
- **Süre:** 45 sn. Tek gönderim hakkı.
- **Puan:** normal süre skoru tam doğruysa 30; resmi nihai sonuç (kazanan/beraberlik) doğru ama skor yanlışsa 15; ikisi de yanlışsa 0.

### 4.5 İlk 11'deki eksik oyuncu

- **Soru:** belirli bir maçın ilk 11'i saha diziliminde gösterilir; zorluğa göre 1 veya 2 oyuncu gizlenir.
- **Gösterim verisi:** yayınlanan soru yükünde `formation` (ör. `4-2-3-1`) ve kaleciden hücuma doğru sıralanmış 11 öğelik `lineup` bulunur. Gizli oyuncu adı yalnız `answer_data` içinde saklanır; istemciye giden `lineup` içindeki yeri `____` ile belirtilir. Pratik, özel oda ve ranked aynı mini saha bileşenini kullanır.
- **Cevap:** serbest metin (zor) veya 4 şık (kolay).
- **Hak:** 2 tahmin. Süre: 45 sn.
- **Puan:** doğru oyuncu başına 50 + tek kalan süre bonusu `min(20, floor(kalan saniye / 5))`.

---

## 5. Oyun biçimleri — akışlar

### 5.1 Pratik (tek oyunculu)

- Misafir veya hesaplı kullanıcı oynayabilir.
- Sunucu soru seçer, süreyi ölçer, sonucu kaydeder.
- Misafirin ilerlemesi kalıcı değildir; oturum sona erince kaybolur (hesap açıldığında devredilmez).

### 5.2 Canlı bire bir maç

1. Oyuncu eşleştirme kuyruğuna girer (`ranked` veya `derecesiz`) veya doğrudan davet gönderir.
2. Sunucu maç kaydı oluşturur, iki oyuncuyu aynı WebSocket grubuna alır.
3. Her tur için **aynı soru** iki oyuncuya **aynı anda** gönderilir (aynı `round_id`, aynı `deadline`).
4. Her iki cevap geldiğinde veya süre dolduğunda tur kapanır ve sonuç yayınlanır.
5. Tüm turlar bitince maç sonucu tek bir PostgreSQL işlemi içinde yazılır.

**Bağlantı kopması:** oyuncunun 30 saniyelik yeniden bağlanma penceresi vardır. Bu sürede tur süresi durmaz; kaçırılan turlar `timeout` sayılır. İki tur üst üste hiç cevap gelmezse maç hükmen sonuçlanır (`forfeit`) ve ranked maçta puan hareketi normal şekilde uygulanır.

**Beraberlik:** puanlar eşitse toplam cevap süresi karşılaştırılır. O da eşitse tek soruluk ani ölüm turu oynanır. Ani ölüm de eşitse maç beraberliktir ve ranked sonucu iki oyuncu için 0.5 olarak işlenir.

**Karışık maç:** 5 turdur; beş modun her biri tam bir kez seçilir ve sıra sunucu tarafından karıştırılır. Tek modlu maçta aynı mod birden fazla tur kullanılabilir.

### 5.3 Farklı zamanlı düello (asenkron)

- Davet eden oyuncu soru setini oynar; set (soru kimlikleri ve sırası) **sabitlenir ve saklanır**.
- Rakip 48 saat içinde aynı seti oynar.
- Süre dolarsa davet eden hükmen kazanır; düello kapanır.
- **Hesap gerektirir.** Ranked'ı etkilemez.

### 5.4 Özel oda

- 2–8 oyuncu, oda kodu ile katılım. **Misafirler katılabilir.**
- Oda sahibi ayarlar: mod (karışık/tek), tur sayısı, süre çarpanı, dil.
- Canlı oynanır, sonuç odaya özel tabloda gösterilir. Ranked'ı etkilemez.

---

## 6. Hesap, misafir ve ilerleme

| Özellik | Misafir | Hesaplı |
|---|---|---|
| Pratik | ✅ | ✅ |
| Özel odaya katılma | ✅ | ✅ |
| Canlı derecesiz maç | ✅ | ✅ |
| Ranked maç | ❌ | ✅ |
| Asenkron düello | ❌ | ✅ |
| Kalıcı ilerleme, istatistik, liderlik tablosu | ❌ | ✅ |

- Misafir oturumu imzalı bir token ile temsil edilir; PostgreSQL'de geçici bir `guest_session` kaydı tutulur ve belirli bir süre sonra temizlenir.
- Misafirler derecesiz canlı 1v1'e katılabilir; ranked ve asenkron düello hesap gerektirir.
- Misafirden hesaba geçişte geçmiş ilerleme **taşınmaz**.

---

## 7. Puanlama ve ranked

### 7.1 Tur puanı

Her modun kendi puan formülü vardır (§4). Tur puanı sunucuda hesaplanır ve `rounds`/`answers` kayıtlarına yazılır.

### 7.2 Maç sonucu

Maç sonucu turların toplamıdır. Sonuç `matches` tablosuna `status = finished` ile tek işlemde yazılır.

### 7.3 Ranked derecesi

- Ortak tek bir ranked puanı vardır (mod bazlı ayrı derece **yoktur**).
- Elo tabanlı: başlangıç 1000, normal K = 32. İlk 10 maç yerleştirme maçı sayılır ve K = 48 kullanılır.
- **Uygunluk kontrolü tek bir fonksiyonda toplanır:** `is_ranked_eligible(match)` → canlı + 1v1 + karışık mod + `origin = matchmaking`. Bu fonksiyonun dışında hiçbir yerde derece yazılmaz.
- Derece hareketi PostgreSQL işlemi içinde atomik yazılır:
  - `SELECT ... FOR UPDATE` ile ilgili `ratings` satırları kilitlenir,
  - `rating_events` tablosuna `(match_id, user_id)` **UNIQUE** kısıtı ile yazılır,
  - aynı maç sonucu tekrar işlenirse ikinci yazma kısıt ihlali verir ve sessizce yok sayılır (idempotent).
- Terk edilen/hükmen biten ranked maç kaybolarak işlenir.

### 7.4 Liderlik tablosu

- Genel (global) ve dönemsel (sezon) tablo. PostgreSQL'den okunur, kısa süreli önbellek Redis'te tutulabilir; önbellek doğruluk kaynağı değildir.

---

## 8. İçerik kapsamı ve dil

**Ligler ve turnuvalar:**

- Beş büyük Avrupa ligi: İngiltere, İspanya, Almanya, İtalya, Fransa
- Türkiye, Portekiz, Hollanda ligleri
- UEFA kulüp turnuvaları (Şampiyonlar Ligi, Avrupa Ligi, Konferans Ligi)
- Seçilmiş Dünya Kupası ve Avrupa Şampiyonası maçları

**Dönem:** tarihi maç ve ilk 11 soruları **2010 ve sonrası**. Kariyer yolu ve genel kültür daha eski dönemi kapsayabilir.

**Dil:** her soru kaydı en az `tr` ve `en` çevirisiyle yayınlanır. Bir dil eksikse soru o dilde havuza girmez. Cevap eşleştirmesi her dil için ayrı alternatif/takma ad listesi kullanır (ör. "Bayern Münih" / "Bayern Munich" / "FC Bayern").

**İçerik durumları:** `draft → in_review → approved → published → retired`. Yalnız `published` sorular oyuna girer.

---

## 9. Veri modeli (PostgreSQL)

Aşağıdaki tablolar Django modelleri olarak tanımlanır. Tüm şema değişiklikleri migration ile yapılır; elle SQL ile şema değiştirilmez.

**Kimlik ve oturum**

- `users` — Django kullanıcı modeli (özelleştirilmiş), dil tercihi, görünen ad
- `guest_sessions` — token hash, oluşturma, son görülme, son kullanma tarihi
- `user_profiles` — avatar, tercih edilen dil, istatistik özetleri

**Futbol verisi (referans)**

- `competitions` — lig/turnuva, ülke, tip
- `seasons` — turnuva + sezon aralığı
- `teams` — ad, ülke, alternatif adlar
- `players` — ad, doğum tarihi, uyruk, mevki, alternatif adlar
- `player_career_entries` — oyuncu, takım, başlangıç/bitiş sezonu, transfer tipi
- `football_matches` — sezon, ev/deplasman takımı, tarih, normal süre skoru, uzatma/penaltı bilgisi
- `match_lineups` — maç, takım, dizilim
- `lineup_slots` — dizilimdeki pozisyon, oyuncu

**İçerik**

- `questions` — mod, zorluk, durum, kaynak referansı, oluşturma/onay bilgisi
- `question_payloads` — moda özgü yapılandırılmış veri (JSONB) + doğru cevap
- `question_translations` — soru, dil, metin, şıklar, ipuçları, istemciye açık moda özgü veri
- `answer_aliases` — varlık (oyuncu/takım), dil, kabul edilen alternatif yazımlar
- `import_jobs`, `import_records` — sağlayıcıdan çekilen ham veri, eşleme durumu, çakışma kayıtları

**Oyun**

- `game_sessions` — pratik/canlı/asenkron/oda, mod seti, dil, başlangıç, deadline, durum
- `matches` — tip (`practice|live_1v1|async_duel|room`), `origin` (`matchmaking|invite|room|practice`), karışık mı, ranked uygun mu, oda kodu/ayarları, durum, sonuç
- `match_participants` — maç, kullanıcı veya misafir oturumu, skor, bağlantı durumu
- `rounds` — maç, sıra no, soru, `deadline`, durum
- `answers` — tur, katılımcı, ham cevap, normalize cevap, sonuç (`correct|wrong|timeout|skipped`), süre (ms), puan
- `participant_round_states` — katılımcı, sabit tur, katılımcıya özel deadline ve ara cevap durumu
- `question_exposures` — kullanıcı, soru, tarih — tekrar gösterimi engellemek için

**Derece**

- `ratings` — kullanıcı, ranked puanı, maç sayısı, yerleştirme durumu
- `rating_events` — maç, kullanıcı, önceki/sonraki puan, delta — **UNIQUE (match_id, user_id)**
- `leaderboard_snapshots` — dönemsel sıralama anlık görüntüsü

Ranked başlangıç puanı `1000`'dir. İlk 10 ranked maçta K=48, sonraki maçlarda K=32 kullanılır; bu değerler `backend/apps/ranking/engine.py` içindeki tekil rating servisinde tanımlıdır.

**Kısıtlar ve indeksler (asgari)**

- `rating_events (match_id, user_id)` UNIQUE
- `answers (round_id, participant_id)` UNIQUE — bir tura tek cevap
- `question_translations (question_id, language)` UNIQUE
- `matches (status, created_at)` ve `question_exposures (user_id, question_id)` indeksli

---

## 10. API ve gerçek zamanlı sözleşmeler

### 10.1 REST

- Kök: `/api/v1/`. Kırıcı değişiklik yeni sürüm (`/api/v2/`) açar; eski sürüm en az bir yayın döngüsü desteklenir.
- Kimlik: JWT (erişim + yenileme) veya oturum token'ı; misafir için ayrı misafir token'ı.
- OpenAPI şeması otomatik üretilir ve `docs/openapi.json` olarak sürümlenir. **Mobil istemci sözleşmesi budur.**

Örnek uç noktalar:

```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/guest/session
GET  /api/v1/modes
GET  /api/v1/content/questions?language=tr
GET  /api/v1/content/questions/{id}?language=en
GET  /api/v1/health
POST /api/v1/content/editor/questions
POST /api/v1/content/editor/questions/{id}/transition
POST /api/v1/content/imports
POST /api/v1/practice/sessions            # pratik oyun başlat
GET  /api/v1/practice/sessions/{id}       # aktif pratik turunu getir
POST /api/v1/practice/sessions/{id}/answers
POST /api/v1/duels                         # hesaplı kullanıcı asenkron düello oluşturur
GET  /api/v1/duels/{id}
POST /api/v1/duels/{id}/join
POST /api/v1/duels/{id}/play
POST /api/v1/rooms                          # misafir veya hesaplı özel oda oluşturur
GET  /api/v1/rooms/{code}
POST /api/v1/rooms/{code}/join
POST /api/v1/rooms/{code}/start
POST /api/v1/rooms/{code}/answers            # REST fallback; canlı istemci WebSocket kullanır
POST /api/v1/matchmaking/queue            # ranked kuyruğuna gir
DELETE /api/v1/matchmaking/queue
GET  /api/v1/matchmaking/queue/status
POST /api/v1/matches/{id}/answers         # canlı ranked REST fallback
POST /api/v1/duels                        # asenkron düello oluştur
POST /api/v1/duels/{id}/play
POST /api/v1/rooms                        # özel oda oluştur
POST /api/v1/rooms/{code}/join
GET  /api/v1/leaderboard
GET  /api/v1/me/stats
```

### 10.2 WebSocket

- Yol: `/ws/v1/match/{match_id}/`
- Bağlantıda kimlik doğrulanır; katılımcı olmayan bağlantı reddedilir.
- Mesajlar JSON, `type` alanı ile ayrışır.

Sunucu → istemci:

```
match.state        # katılımcılar, tur no, skorlar
round.start        # round_id, mode, payload (CEVAPSIZ), deadline
round.opponent_answered
round.result       # doğru cevap, her iki oyuncunun sonucu, puanlar
match.finished     # nihai skor, kazanan, rating_delta (varsa)
error
```

İstemci → sunucu:

```
answer.submit      # round_id, cevap
ping
rejoin
```

Kurallar:

- `round.start` içinde doğru cevap **asla** bulunmaz.
- İstemcinin gönderdiği süre bilgisi puanlamada kullanılmaz.
- `answer.submit` aynı tur için ikinci kez gelirse yok sayılır.

---

## 11. Mimari kararlar

1. **Oyun motoru Django tarafında, framework'ten bağımsız bir servis katmanındadır** (`apps/quiz/engine/`). Channels tüketicileri ve REST görünümleri aynı motoru çağırır; iş kuralı iki yerde tekrarlanmaz.
2. **Redis'in rolü sınırlıdır:** Channels layer, eşleştirme kuyruğu, dağıtık kilit, önbellek. Maç durumu Redis'te tutulabilir ama **her tur sonunda PostgreSQL'e yazılır**; Redis kaybı puan kaybına yol açmaz.
3. **İdempotenslik:** maç sonucu ve derece yazımı tekrar edilebilir çağrılara karşı UNIQUE kısıtlarla korunur.
4. **Saat:** tüm zamanlar UTC saklanır; istemci yerelleştirmeyi kendisi yapar.
5. **İçe aktarma sağlayıcıdan bağımsızdır:** harici veri önce `import_records` içine ham olarak yazılır, sonra eşleme (mapping) katmanı iç modellere dönüştürür. Sağlayıcı değişirse yalnız eşleme katmanı değişir.
6. **Hile önleme:** doğru cevap sunucuda kalır; soru havuzundan seçim sunucuda yapılır. `round.start` payload'ı ve server-authoritative cevap akışı Faz 6 testleriyle korunur; anormal hızlı cevap ve aşırı yüksek isabet oranları için işaretleme mekanizması sonraki operasyonel izleme paketi olarak takip edilir.

---

## 12. Geliştirme fazları

| Faz | İşler | Tamamlanma ölçütü |
|---|---|---|
| **0 — Kurallar ve veri doğrulaması** | Beş modun cevap, süre, hata ve puan kurallarını kesinleştirmek; örnek içerik ve veri kullanım haklarını incelemek. | Her mod için doğrulanmış örnek soru ve uygulanabilir oyun kuralları vardır. |
| **1 — Temel altyapı** | Django backend, **PostgreSQL şeması ve migration'ları**, REST API, WebSocket altyapısı, Vue uygulaması, hesap ve misafir oturumları. | Web istemcisi API'ye bağlanır; kalıcı kayıtlar PostgreSQL'de tutulur; iki istemci canlı oturuma bağlanır. **Tamamlandı.** |
| **2 — İçerik yönetimi** | Futbolcu, takım, kariyer, maç, skor ve ilk 11 verilerini PostgreSQL'de modellemek; API içe aktarma, editör onayı, çeviri ve yayın akışı. | Beş mod için onaylı sorular üretilebilir; doğrulanmamış veri oyuncuya gösterilmez. **Tamamlandı.** |
| **3 — Oyun motoru ve pratik** | Sunucu tarafında soru seçimi, süre, cevap doğrulaması ve puanlama; Vue tarafında beş modun modern, futbol temalı ekranları. | Beş mod iki dilde tek başına baştan sona oynanır. **Tamamlandı.** |
| **4 — Derecesiz çok oyunculu oyun** | Asenkron düello, davet, özel oda ve canlı derecesiz maçlar; bağlantı kopması ve süresi dolan oyunların ele alınması. | Düello farklı zamanlarda tamamlanır; 2–8 kişi özel odada oynar. **Tamamlandı.** |
| **5 — Ranked ve liderlik tablosu** | Canlı eşleştirme, maç sonucu ve ortak derece; derece hareketlerinin **PostgreSQL işlemleriyle atomik** kaydı. | Yalnız uygun maç dereceyi değiştirir; tekrar gelen sonuç aynı maça ikinci kez puan yazmaz. **Tamamlandı.** |
| **6 — Kalite ve kapalı beta** | Oyun, API ve iki tarayıcılı canlı maç testleri; erişilebilirlik, yük, içerik kalitesi ve **PostgreSQL yedekleme/geri yükleme** kontrolleri. | Kritik akışlar ve veri kurtarma doğrulanır; web sürümü kapalı beta için hazırdır. **Tamamlandı.** Ayrıntılar: [`docs/phase-6.md`](docs/phase-6.md) |
| **7 — Mobil hazırlığı** | REST ve WebSocket sözleşmelerini sürümleyip mobil istemci için belgelemek. | Mobil uygulama aynı backend ve PostgreSQL verilerini API aracılığıyla kullanabilecek şekilde tasarım tamamlanır. |

---

## 13. Kabul ölçütleri ve test planı

Her madde otomatik testle doğrulanır.

### 13.1 Mod kuralları (beş mod için ayrı ayrı)

- Doğru cevap beklenen puanı üretir ve `answers.result = correct` yazılır.
- Yanlış cevap puan üretmez, hak/ceza doğru azalır.
- Süre aşımı `timeout` olarak kaydedilir; `wrong` ile karıştırılmaz.
- Süre sunucu saatine göre ölçülür; istemciden gelen süre bilgisi sonucu değiştirmez.
- `round.start` yükünde doğru cevap bulunmaz (yük şeması testi).

### 13.7 Faz 3 pratik akışı

- `POST /practice/sessions` yalnız `published` ve istenen dilde çevirisi bulunan sorulardan ilk turu üretir.
- Cevaplar `POST /practice/sessions/{id}/answers` ile sunucuya gönderilir; `round.private_state` ve `question_payload.answer_data` istemciye serialize edilmez.
- Pratikte misafir ve hesaplı kullanıcılar oynayabilir; pratik maçları ranked puanını değiştirmez.
- Vue ekranı gerçek `deadline`, `round`, `result` ve `score` alanlarını gösterir; istemci süre veya puan hesaplamaz.

### 13.2 İki dilde cevap eşleştirmesi

- Türkçe ve İngilizce yazımlar, takma adlar ve aksan/Türkçe karakter farkları doğru kabul edilir.
- `tr` yerelinde I/ı ve İ/i dönüşümü doğru çalışır.
- Bir dilde çevirisi olmayan soru o dilin havuzuna girmez.

### 13.3 Canlı maç

- İki oyuncuya aynı turda **aynı soru** ve **aynı deadline** gider.
- Aynı tura ikinci cevap gönderimi yok sayılır.
- Bağlantı kopan oyuncu 30 sn içinde dönerse maça devam eder; dönmezse kaçırdığı turlar `timeout` olur.
- İki tur üst üste cevapsız kalırsa maç `forfeit` ile biter.
- Beraberlikte tie-break kuralı uygulanır ve sonuç tek bir işlemle yazılır.

### 13.4 Ranked

- Eşleştirmeyle başlamış, canlı, 1v1, karışık maç dereceyi değiştirir.
- Davetle başlayan maç, özel oda, asenkron düello ve pratik dereceyi **değiştirmez**.
- Aynı maç sonucu iki kez işlenirse ikinci kez puan yazılmaz (`rating_events` UNIQUE testi).
- Eşzamanlı iki sonuç işleme denemesinde kilitleme sayesinde puan bozulmaz.

### 13.5 PostgreSQL

- Tüm migration'lar boş veritabanında sıfırdan çalışır (`migrate` testi).
- Migration'lar örnek veri içeren veritabanında da çalışır.
- Maç sonucu + derece yazımı tek işlemdedir: işlem ortasında hata verilirse hiçbir kısmi kayıt kalmaz.
- Yedekten geri yükleme tatbikatı: `pg_dump` alınır, temiz bir örneğe geri yüklenir, maç ve derece kayıtlarının bütünlüğü doğrulanır.

### 13.6 Diğer

- API sözleşme testleri (OpenAPI şemasına uyum).
- Playwright ile iki tarayıcı açıp uçtan uca canlı maç.
- Erişilebilirlik: klavye ile oynanabilirlik, odak göstergesi, kontrast, ekran okuyucu etiketleri.
- Yük smoke testi: health uç noktasında 8 eşzamanlı istekle 80 istek; median 56.5 ms, p95 83.12 ms, hata 0. Canlı maç kapasite hedefi üretim gözlemleriyle ayrıca kesinleştirilecektir.

---

## 14. Yedekleme ve kurtarma

- Günlük tam `pg_dump` + sürekli WAL arşivi (üretimde).
- Geri yükleme tatbikatı en az her yayın öncesi bir kez yapılır ve sonucu kayıt altına alınır.
- Yerel tatbikat betiği: [`infra/backup/pg_backup_restore_smoke.sh`](infra/backup/pg_backup_restore_smoke.sh). Üretimde günlük tam `pg_dump` + sürekli WAL arşivi DigitalOcean operasyon planında uygulanır.
- Redis yedeklenmez; kayıp durumunda yalnız devam eden canlı maçlar iptal edilir ve oyunculara bilgi verilir.

---

## 15. Mobil hazırlığı (Faz 7)

- REST ve WebSocket sözleşmeleri `/api/v1` ve `/ws/v1` altında dondurulur.
- OpenAPI şeması + WebSocket mesaj kataloğu `docs/` altında yayımlanır.
- Mobil istemci için ek bir backend, ek bir veritabanı veya yinelenen iş kuralı yazılmaz.
- Sürüm politikası: kırıcı değişiklik → yeni sürüm yolu; eski sürüm en az bir yayın döngüsü desteklenir.

---

## 16. Varsayımlar ve açık kararlar

Faz 0'da aşağıdaki kararlar kapatıldı; ayrıntılı gerekçeler, örnekler ve kaynaklar [`docs/phase-0.md`](docs/phase-0.md) içindedir:

1. Beş modun kesin süre, hak ve puan katsayıları belirlendi.
2. Ranked beraberliği: toplam cevap süresi, ardından ani ölüm; ani ölüm de eşitse iki oyuncuya 0.5.
3. Misafirler derecesiz canlı 1v1'e katılabilir; ranked ve asenkron düello hesap gerektirir.
4. Karışık maç beş turdur ve her mod tam bir kez kullanılır; sıra sunucuda karıştırılır.
5. Açık veri tabanı olarak Wikidata + openfootball/football.json seçildi. API-Football ancak yazılı yayın hakkı alınırsa değerlendirilecek.
6. Faz 0–6'da oyuncu/kulüp logosu, fotoğrafı ve arması kullanılmaz.
7. Misafir → hesap geçişinde ilerleme taşınmaz.

---

## 17. Kod üreten ajanlar için çalışma kuralları

**Dizin yapısı (hedef):**

```
backend/
  config/            # Django ayarları, ASGI, routing
  apps/
    accounts/        # kullanıcı, misafir oturumu
    content/         # futbol verisi, sorular, çeviri, onay akışı
    quiz/            # oyun motoru: soru seçimi, süre, doğrulama, puan
    realtime/        # Channels tüketicileri, maç odaları
    ranking/         # elo, rating_events, liderlik tablosu
    imports/         # sağlayıcı bağımsız içe aktarma
  tests/
frontend/
  src/{components,views,stores,i18n,assets}
docs/                # openapi.json, ws-katalog, karar kayıtları
infra/               # docker-compose, migration/backup betikleri
PROJECT.MD
```

**Kurallar:**

1. Veritabanı PostgreSQL'dir. Ayarlarda SQLite'a düşen bir yedek yol (fallback) yazılmaz.
2. Model değişikliği migration olmadan birleştirilmez. Üretilen migration dosyası değişiklikle aynı sette olur.
3. İş kuralı `apps/quiz/engine` ve `apps/ranking` içinde yaşar; Channels tüketicisi veya Vue bileşeni içine kural yazılmaz.
4. Doğru cevap hiçbir zaman istemciye giden yükte yer almaz. Bunu doğrulayan test yazılmadan özellik tamamlanmış sayılmaz.
5. Ranked uygunluğu yalnız `is_ranked_eligible()` ile belirlenir.
6. Kullanıcıya görünen hiçbir metin koda sabitlenmez; `tr` ve `en` çeviri dosyalarına eklenir.
7. Sır (API anahtarı, parola) koda veya depoya yazılmaz; ortam değişkeninden okunur.
8. **Tanımlı bitti:** kod + testler geçiyor + migration var + PROJECT.MD ilgili bölümü güncel + iki dilde metin mevcut.
9. Belirsizlik varsa tahmin edilerek ilerlenmez; "Açık kararlar" listesine madde eklenir ve sorulur.

---

## 18. Sözlük

| Terim | Karşılığı |
|---|---|
| Tur (round) | Bir soruluk oyun birimi |
| Maç (match) | Birden çok turdan oluşan oyun |
| Karışık maç | Turlar arasında modun değiştiği maç |
| Eşleştirme (matchmaking) | Sistemin rakip bulduğu kuyruk |
| Ranked | Ortak dereceyi etkileyen maç türü |
| Derecesiz | Dereceyi etkilemeyen maç türü |
| Asenkron düello | Oyuncuların farklı zamanlarda aynı seti oynadığı maç |
| Misafir | Hesapsız oyuncu |
