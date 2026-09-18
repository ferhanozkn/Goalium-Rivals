# Faz 0 — Kurallar ve veri doğrulaması

**Durum:** Tamamlandı
**Karar tarihi:** 2026-09-18
**Kapsam:** Beş oyun modunun uygulanabilir kuralları, örnek içerik doğrulaması ve veri kullanım politikası.

## 1. Faz 0 karar özeti

| Konu | Kesin karar |
|---|---|
| Çöp adam | 90 sn, 6 yanlış harf, en fazla 2 ipucu; taban 100 puan. |
| Kariyer yolu | 60 sn, 3 tahmin; ilk kulüp açık, sonraki kulüp satırı her 10 sn'de açılır. |
| Süreli genel kültür | 60 sn toplam süre; yanlış cevap deadline'dan 3 sn düşer, pas cezasızdır. |
| Tarihi maç skoru | 45 sn, tek gönderim; normal süre skoru sorulur, tam skor 30, yalnız sonuç doğruysa 15 puan. |
| İlk 11'deki eksik oyuncu | 45 sn, 2 tahmin; kolayda 1, zorda 2 oyuncu gizlenir. |
| Ranked beraberlik | Puan eşitliği toplam cevap süresiyle çözülür; o da eşitse ani ölüm; ani ölüm de eşitse iki tarafa 0.5 sonuç puanı. |
| Misafir canlı oyun | Misafir, derecesiz canlı 1v1'e katılabilir; ranked ve asenkron düello hesap ister. |
| Karışık maç | 5 tur; beş modun her birinden tam bir tur, sıra sunucu tarafından karıştırılır. |
| Veri kaynakları | Birincil açık veri seti olarak Wikidata + openfootball/football.json seçildi. Proprietary API yalnız yazılı yayın izni alınırsa değerlendirilecek. |
| Görsel varlıklar | Faz 0–6'da logo, oyuncu fotoğrafı ve kulüp arması yok; metin ve kendi ürettiğimiz arayüz varlıkları kullanılır. |
| Misafirden hesaba geçiş | Misafir ilerlemesi hesaba taşınmaz; misafir oturumu sona erince silinir. |

## 2. Ortak cevap ve zaman politikası

1. Sunucu her tur için UTC `deadline` üretir. Cevabın geçerli olup olmadığı istemci saatine veya istemcinin gönderdiği süre alanına göre değil, sunucunun aldığı zamana göre belirlenir.
2. Deadline sonrasında gelen cevap `timeout` olur; `wrong` ile karıştırılmaz ve puanı sıfırdır.
3. Serbest metin normalizasyonu sırasıyla Unicode NFKC, Türkçe yerelinde küçük harfe çevirme, baş/son boşluk temizliği, çoklu boşluk sadeleştirme, Unicode noktalama işaretlerini kaldırma ve şu eşlemeleri uygular: `ı/i`, `ş/s`, `ğ/g`, `ü/u`, `ö/o`, `ç/c`. Sonra aynı dildeki canonical cevap ve alias kayıtları aranır.
4. Exact alias eşleşmesinden sonra Levenshtein toleransı uygulanır: uzunluk 1–3 için 0, 4–7 için en fazla 1, 8 ve üzeri için en fazla 2. Fuzzy eşleşme yalnız aynı dildeki yayınlanmış alias havuzunda yapılır.
5. Skorlar tam sayıdır. Ondalık katsayılarda yarım yukarı yuvarlama uygulanır. Sonuç türleri `correct`, `wrong`, `timeout`, `skipped` olarak saklanır.

## 3. Kesin mod kuralları ve örnekler

### 3.1 Çöp adam

- Süre: 90 sn.
- Hak: 6 yanlış harf. Kelime 6 yanlış harften önce tamamlanmazsa tur `wrong` biter; süre biterse `timeout` olur.
- İpucu: En fazla 2; her ipucu 15 puan keser.
- Puan: `max(0, 100 - 10 × yanlış_harf - 15 × ipucu) + floor(kalan_saniye / 5)`.
- Boşluk ve tire başlangıçta görünür; harfler gizlidir.

**Doğrulanmış örnek:**

- TR soru: `Kategori: Kural — Futbolda rakibin kale çizgisine toptan ve sondan ikinci rakipten daha yakın olma durumuyla ilgili kelimeyi bulun.`
- EN question: `Category: Rule — Find the football term for being nearer to the opponents' goal line than both the ball and the second-last opponent.`
- Cevaplar: TR `ofsayt`; EN `offside`.
- Doğrulama: [IFAB Law 11 — Offside](https://www.theifab.com/laws/latest/offside/).
- Örnek puan: 2 yanlış harf, 1 ipucu, 37 sn kalan → `100 - 20 - 15 + 7 = 72`.

### 3.2 Kariyer yolu

- Süre: 60 sn.
- İlk kulüp satırı açık gelir. Sonraki satırlar 10, 20, 30, 40 ve 50. saniyelerde açılır.
- Hak: 3 tahmin. Yanlış tahmin sayısı puanı etkiler; üçüncü yanlışta tur `wrong` biter.
- Puan: `max(0, 100 - 15 × açılan_ek_satır - 10 × yanlış_tahmin) + min(10, floor(kalan_saniye / 10))`.

**Doğrulanmış örnek:**

- TR soru: `Oyuncuyu kulüp geçmişinden bulun: Barcelona (2002–2018) → Vissel Kobe (2018–2023) → Emirates Club (2023–2024).`
- EN question: `Identify the player from this club path: Barcelona (2002–2018) → Vissel Kobe (2018–2023) → Emirates Club (2023–2024).`
- Cevap: `Andrés Iniesta`; kabul edilen alias: `Andres Iniesta`, `Iniesta`.
- Doğrulama: [FC Barcelona player profile](https://players.fcbarcelona.com/en/player/405-iniesta-andres-iniesta).
- Örnek puan: 1 ek satır açılmış, 1 yanlış tahmin, 32 sn kalan → `100 - 15 - 10 + 3 = 78`.

### 3.3 Süreli genel kültür

- Toplam süre: 60 sn.
- Soru başına ayrıca sabit deadline yoktur; sunucu toplam session deadline'ını takip eder. Cevaptan sonra yeni soru hemen verilir.
- Zorluk katsayıları: kolay `1.0`, orta `1.5`, zor `2.0`.
- Doğru cevap puanı: `round_half_up(10 × zorluk_katsayısı) + max(0, 5 - floor(soruya_cevap_süresi / 2))`.
- Yanlış cevap puan vermez ve toplam deadline'dan 3 sn düşer. Pas `skipped` kaydıdır ve süre düşürmez.

**Doğrulanmış örnek:**

- TR soru: `2010 FIFA Dünya Kupası finalinde İspanya adına uzatmalarda gol atan oyuncu kimdir?`
- EN question: `Who scored Spain's extra-time goal in the 2010 FIFA World Cup final?`
- Şıklar: `Andrés Iniesta`, `Xavi Hernández`, `David Villa`, `Carles Puyol`.
- Doğru cevap: `Andrés Iniesta`.
- Doğrulama: [FIFA — Spain–Netherlands 2010 final](https://www.fifa.com/es/articles/asi-fue-la-final-andres-iniesta-en-la-copa-mundial-fifa-sudafrica-2010).
- Örnek puan: orta zorlukta 4 sn'de cevap → `round_half_up(10 × 1.5) + (5 - 2) = 18`.

### 3.4 Tarihi maç skoru

- Kapsam: 2010 ve sonrası.
- Süre: 45 sn; tek gönderim hakkı.
- Soru, uzatma veya penaltı varsa bunu açıkça belirtir.
- Cevap alanları ev sahibi ve deplasman normal süre golleridir.
- Puan: normal süre skorunun ikisi de doğruysa `30`; maçın resmi nihai sonucundaki kazanan/beraberlik doğru, skor yanlışsa `15`; diğer durumda `0`.

**Doğrulanmış örnek:**

- TR soru: `11 Temmuz 2010 FIFA Dünya Kupası finalinde Hollanda–İspanya maçının normal süre skoru neydi? Maç uzatmada İspanya'nın 1–0 galibiyetiyle bitti.`
- EN question: `What was the score after 90 minutes in the Netherlands–Spain final of the 2010 FIFA World Cup? The match ended 1–0 to Spain after extra time.`
- Cevap: `0–0` normal süre; resmi nihai sonuç `0–1` uzatma sonrası.
- Doğrulama: [FIFA — 2010 final](https://www.fifa.com/es/articles/asi-fue-la-final-andres-iniesta-en-la-copa-mundial-fifa-sudafrica-2010), [FIFA — all-European finals](https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/magic-moments-in-all-european-finals).
- Örnek puan: `0–0` → 30 puan; `0–1` → sonuç doğru, skor yanlış olduğu için 15 puan.

### 3.5 İlk 11'deki eksik oyuncu

- Süre: 45 sn; en fazla 2 tahmin.
- Kolay soru: 1 oyuncu gizlenir ve 4 şık sunulur. Zor soru: 2 oyuncu gizlenir ve serbest metin alınır.
- Puan: doğru gizli oyuncu başına `50` + tek bir kalan süre bonusu `min(20, floor(kalan_saniye / 5))`. Birden fazla gizli oyuncudan yalnız doğru bulunanlar puan alır; tüm gizli oyuncular doğruysa sonuç `correct`, aksi halde `wrong` olur.

**Doğrulanmış örnek:**

- TR soru: `2018 FIFA Dünya Kupası finalindeki Fransa ilk 11'inde eksik oyuncuyu bulun: Hugo Lloris, Benjamin Pavard, Raphaël Varane, Samuel Umtiti, Lucas Hernandez, N'Golo Kanté, Paul Pogba, Blaise Matuidi, Kylian Mbappé, Olivier Giroud, ____.`
- EN question: `Find the missing player in France's starting XI in the 2018 FIFA World Cup final: Hugo Lloris, Benjamin Pavard, Raphaël Varane, Samuel Umtiti, Lucas Hernandez, N'Golo Kanté, Paul Pogba, Blaise Matuidi, Kylian Mbappé, Olivier Giroud, ____.`
- Cevap: `Antoine Griezmann`; kabul edilen alias: `Griezmann`.
- Doğrulama: [FIFA 2018 World Cup technical report](https://img.fifa.com/image/upload/evdvpfdkueqrdlbbrrus.pdf), [FIFA final summary](https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/worldcupathome-france-croatia-russia-2018-3072767).
- Örnek puan: 18 sn kalan → `50 + floor(18 / 5) = 53`.

## 4. Maç, ranked ve misafir kararları

- Karışık canlı maç 5 turdan oluşur ve her mod tam bir kez kullanılır. Mod sırası ve soru kimlikleri sunucuda seçilip kalıcı maç kaydına yazılır.
- Puanlar eşitse önce toplam cevap süresi karşılaştırılır. Eşitlik sürerse tek bir ani ölüm turu oynanır. Ani ölüm de eşitse maç beraberliktir; ranked sonuç beklentisi iki oyuncu için `0.5` olarak hesaplanır.
- Ranked başlangıç puanı `1000`, normal K katsayısı `32`, ilk 10 maç için yerleştirme K katsayısı `48`'dir.
- Misafirler derecesiz canlı 1v1'e katılabilir; guest session puanı ve ilerlemesi kalıcı istatistiğe yazılmaz. Ranked, asenkron düello ve liderlik tablosu hesaplı kullanıcı gerektirir.
- Ranked uygunluğu hâlâ yalnız `is_ranked_eligible(match)` ile belirlenir: canlı + 1v1 + karışık + `origin=matchmaking`.

## 5. Veri kaynağı ve hak politikası

Faz 0 için seçilen açık veri tabanı kombinasyonu:

1. **[Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing):** oyuncu, takım, dil etiketleri ve mümkün olan kariyer ilişkileri için. Yapılandırılmış veri CC0 olarak sunulur; proje kaynak URL'sini ve erişim tarihini kaydeder.
2. **[openfootball/football.json](https://github.com/openfootball/football.json):** fikstür ve maç sonucu başlangıç verisi için. Depo, veri ve şemayı kamu malı/CC0 olarak tanımlar.
3. **IFAB, FIFA, UEFA ve kulüp sayfaları:** örnekleri doğrulamak ve editörün kaynak göstermek için kullandığı referanslar. Bu sayfaların metni, görselleri veya logoları toplu olarak kopyalanmaz.

API-Football üretim kaynağı olarak seçilmedi. Güncel şartları, verinin yayınlanması için lisans vermediğini ve gerekli üçüncü taraf izinlerinin kullanıcı tarafından alınması gerektiğini açıkça belirtiyor: [API-Football Terms of Service](https://www.api-football.com/terms). Bu nedenle proprietary API kullanılacaksa Faz 2 içerik yayınından önce yazılı yayın hakkı ve kapsam doğrulaması gerekir.

Kapsam kararı: uygulamanın ilk sürümünde logo, fotoğraf ve arma kullanılmaz. Lineup/career alanı CC0 kaynaktan doğrulanamıyorsa kayıt `draft` kalır; lisans belirsizliği oyuncuya gösterilecek içeriğe dönüşmez.

## 6. Faz 0 kabul kontrolü

- [x] Beş modun süre, hak, timeout, cevap ve puan kuralları kesinleştirildi.
- [x] Ranked beraberliği, misafir canlı oyunu ve karışık maç dağılımı kesinleştirildi.
- [x] Her mod için TR/EN örnek soru, canonical cevap ve puan hesabı yazıldı.
- [x] Örnekler IFAB, FIFA ve FC Barcelona gibi birincil/kurumsal kaynaklarla kontrol edildi.
- [x] Açık veri kaynakları ve proprietary veri için lisans kapısı belirlendi.
- [x] Logo/fotoğraf kararı ve misafirden hesaba geçiş kararı kapatıldı.
- [x] Faz 1'e geçiş için gerekli kurallar `PROJECT.MD` içine işlendi.

## 7. Faz 1'e devredilen sınır

Faz 0 içerik ve kural kararıdır; Django/Vue kodu, PostgreSQL migration'ı, REST/WebSocket ve otomatik testler Faz 1'de başlayacaktır. Bu dokümandaki formüller config katmanından okunacak, magic number olarak iş kuralına gömülmeyecektir.
