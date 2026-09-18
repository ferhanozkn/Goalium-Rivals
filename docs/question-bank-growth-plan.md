# Soru havuzunu kademeli büyütme planı

**Araştırma tarihi:** 18 Eylül 2026  
**Durum:** Uygulama planı; bu belge veri çekme veya soru yayınlama işlemi başlatmaz.  
**Ürün kuralı:** [`PROJECT.MD`](../PROJECT.MD) ve [`phase-0.md`](phase-0.md) geçerlidir. Sorular PostgreSQL'de tutulur; yalnız editörce onaylanan, Türkçe ve İngilizce tamamlanan, kullanım hakkı doğrulanan kayıtlar yayınlanır. Doğru cevap istemciye gitmez.

Pilot adaylarını çekip `draft` olarak hazırlamak için backend içinde şu komut kullanılır:

```bash
python manage.py prepare_question_bank
```

Komut varsayılan olarak 20 tarihi skor, 10 **futbolcu çöp adamı**, 20 süreli genel kültür, 10 kariyer yolu ve 5 ilk 11 adayı üretir. İlk 11 adaylarının kaynağı lisans incelemesi beklediği için yayınlanabilir kabul edilmez. Tekrar çalıştırma aynı `seed_key` değerlerini günceller; editör akışına girmiş kayıtları ezmez.

Lisansı doğrulanmış pilot soruları yayınlama işlemi ayrıca onay parametresiyle çalıştırılır:

```bash
python manage.py publish_question_bank --prefix pilot: --confirm
```

Bu komut doğrulanmamış kaynaklara bağlı soruları atlar; ilk 11 adayları hak incelemesi tamamlanana kadar `draft` kalır.

## 1. Başlangıç ve hedefler

Depodaki `seed_phase3_content` komutu altı örnek soru üretir. Bu sayı canlı veritabanındaki toplam yayınlanmış soru sayısı olarak varsayılmamalı; ilk iş durum, mod, dil ve kaynak bazında gerçek envanteri çıkarmaktır. Aşağıdaki rakamlar **kümülatif, onaylanmış soru hedefidir**; pilot verim ve kaynak haklarına göre yeniden ayarlanır.

| Mod | Örnek seed | Dalga 1 · pilot | Dalga 2 · beta | Dalga 3 · genişleme |
|---|---:|---:|---:|---:|
| Çöp adam | 1 | 10 | 30 | 100 |
| Kariyer yolu | 1 | 10 | 30 | 80 |
| Süreli genel kültür | 2 | 20 | 60 | 200 |
| Tarihi maç skoru | 1 | 20 | 60 | 150 |
| İlk 11'de eksik oyuncu | 1 | 5* | 15* | 40* |
| **Toplam** | **6** | **65** | **195** | **570** |

\* İlk 11 hedefleri **yayın izni ve 11 oyuncu + dizilişin güvenilir doğrulaması bulunursa** geçerlidir. Uygun kaynak yoksa sayı zorlanmaz; adaylar `draft` kalır.

Dalga 1 her mod için veri kalitesini ve üretim süresini ölçer. Dalga 2, başarılı şablonları farklı lig/sezon/ülkelere yayar. Dalga 3, tekrar eden olgular yerine yeni maç ve oyuncu kapsamı ekler. Her dalga mevcut havuza ekleme yapar; aynı olgudan gereksiz soru varyasyonları hedefe sayılmaz.

## 2. Ücretsiz kaynak araştırması

| Kaynak | Erişim ve veri | Bu proje için karar |
|---|---|---|
| [Wikidata SPARQL / Wikibase API](https://www.wikidata.org/wiki/Wikidata:Data_access) | Ücretsiz; yapılandırılmış verisi [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing). Oyuncu/kulüp etiketleri ve `P54` takım üyeliğinin `P580`/`P582` zaman niteleyicileri kullanılabilir. [Sorgu servisinde süre/yük sınırları](https://www.mediawiki.org/wiki/Wikidata_query_service/User_Manual) var. | **Birincil kaynak.** Çöp adam, kariyer yolu ve bazı bilgi soruları için aday üret. Eksik tarih, yanlış kulüp türü ve TR/EN etiket yokluğunu editör kontrol etsin. Toplu tarama yerine küçük, önbelleklenen sorgular; tanımlayıcı User-Agent ve 429/Retry-After uyumu. |
| [openfootball/football.json](https://github.com/openfootball/football.json) | GitHub üzerinden anahtarsız HTTP JSON; gerçek zamanlı API değil, [CC0 veri deposu](https://github.com/openfootball/football.json/blob/master/LICENSE.md). Sezon/maç/takım ve `score.ft` sunar; kaynak Football.TXT güncellemesinin gecikebileceğini [depo açıklıyor](https://github.com/openfootball/football.json#frequently-asked-questions--answers). | **Birincil kaynak.** 2010+ lig maçlarından normal süre skorları ve doğrulanabilir genel kültür olguları üret. İçe aktarmada commit SHA, dosya URL'si ve erişim tarihini sakla. Kupa maçında `ft` alanını doğrudan 90 dakika skoru sayma. Kadro/diziliş verisi bekleme. |
| [OpenLigaDB](https://openligadb.de/) | Ücretsiz, kimlik doğrulaması istemeyen [JSON API](https://github.com/OpenLigaDB/OpenLigaDB-Samples); topluluk verisi. Sağlayıcı [ODbL](https://openligadb.de/) lisansı bildiriyor. | **Koşullu yedek kaynak.** Özellikle Alman lig sonuçları için değerlendirilebilir. ODbL'nin atıf, türetilmiş veritabanı ve paylaşım koşulları proje dağıtımıyla uyumlu biçimde belgelenmeden `verified` yapılmaz. Veri kalitesi ikinci kaynakla kontrol edilir. |
| [football-data.org Free](https://www.football-data.org/pricing) | Ücretsiz planda [12 yarışma ve 10 çağrı/dakika](https://docs.football-data.org/general/v4/policies.html); fikstür/sonuç var, ilk 11 verisi ücretli pakette. [Koşullar](https://www.football-data.org/client/register) görünür atıf ister ve abonelik bittiğinde API'den alınan verilere sitede referans verilmesini kısıtlar. | **Kalıcı soru havuzu için seçilmedi.** API ile çekilen verinin süresiz PostgreSQL soru bankasında kullanımı netleştirilmeden yayın yapılmaz. Kapsam/format karşılaştırması için değerlendirme adayıdır. |
| [TheSportsDB v1 Free](https://www.thesportsdb.com/documentation) | Ücretsiz `123` anahtarı; [30 çağrı/dakika ve event lineup uç noktası](https://www.thesportsdb.com/documentation). [17.09.2026 koşulları](https://www.thesportsdb.com/docs_terms_of_use.php) ücretsiz kullanımı geliştirme projeleriyle tanımlar, app store yayını için ücretli abonelik ister ve üçüncü taraf haklarını ayrıca şart koşar. | **Prototip/inceleme adayı.** İlk 11 verisi bulunabilir fakat oyun sorularını kalıcı yayınlama ve ileride mobil mağaza kullanımı için yazılı hak açıklığı gerekir. Görsel/logo çekilmez. |
| [StatsBomb Open Data](https://github.com/hudl/open-data) | Ücretsiz JSON dosyalarında seçili maçların lineup ve event kayıtları var. Depo kullanım amacını araştırma/analiz olarak tarif eder ve yayımlanan türevlerde kaynak + logo ister. | **Üretim kaynağı olarak beklet.** Serbest erişim, bu oyunda toplu kadro sorusu yayınlama hakkını tek başına kanıtlamaz. Sağlayıcıdan açık izin ve ürünün görsel varlık politikasıyla uyum sağlanırsa tekrar değerlendirilir. |
| [API-Football Free](https://www.api-football.com/pricing) | Ücretsiz planda 100 çağrı/gün ve lineup uç noktası bulunur; fakat [koşulları](https://www.api-football.com/terms) veriyi yayımlamak için gerekli izinlerin kullanıcıca ayrıca alınacağını söyler. | **Üretime alınmaz.** Faz 0 kararı korunur; yazılı yayın hakkı gelmeden aday içerik `published` olmaz. |

**Öneri:** İlk iki dalganın omurgası Wikidata + openfootball olsun. API kaynağı maç ekranında anlık sorgulanmasın; kaynak verisi kontrollü import edilip doğrulanmış soru olarak PostgreSQL'e yazılsın. FIFA, UEFA, federasyon ve kulüp sayfaları olgu doğrulaması için referans olarak kullanılabilir; metin/görseller otomatik kopyalanmaz. Bu, [`phase-0.md`](phase-0.md) hak politikasıyla uyumludur.

## 3. Mod bazında üretim kuralları

| Mod | Aday üretimi | Yayın öncesi zorunlu kontrol |
|---|---|---|
| Çöp adam | CC0 oyuncu, kulüp, stat ve turnuva varlıklarından uygun TR/EN adlar. | Tek anlamlı cevap, doğru kategori, dil başına yazım ve takma ad, bozuk/çok kısa ad elemesi, aynı cevabın tekrarı kontrolü. |
| Kariyer yolu | Wikidata `P54` + başlangıç/bitiş niteleyicilerinden kronolojik kulüp yolu. | En az üç ayırt edici **senior kulüp**; milli takım/genç takım ayrımı; kiralık dönem ve tarih çakışması kontrolü; belirsiz kariyer `draft`. Kulüp veya federasyon sayfasıyla editör karşı kontrolü. |
| Süreli genel kültür | Wikidata olguları ve açık maç sonuçlarından soru şablonları; ör. sezon/turnuva/maç kazananı. | Dört şık aynı varlık türünden; tam bir doğru cevap; doğru cevabı ima eden metin yok; tarih ve turnuva bağlamı açık; TR/EN şıklar eşdeğer. |
| Tarihi maç skoru | openfootball'dan 2010+ bitmiş lig maçları. | Ev/deplasman, tarih ve lig tekil; **90 dakika skoru** kesin; uzatma/penaltı belirsiz kupa maçları elenir; ikinci referansla örneklem doğrulaması. |
| İlk 11'de eksik oyuncu | Hakları temizlenmiş tam kadro + diziliş kaydı bulunduğunda soru adayı. | Tam 11 ilk oyuncu, aynı maç/takım/tarih, doğrulanmış diziliş, kaleciden hücuma doğru 11 slot, 1–2 gizli slot ve cevapların yalnız `answer_data` içinde kalması. Sırf 11 isim veren ama diziliş vermeyen kaynak otomatik saha sorusu üretmez. |

## 4. Uygulama sırası ve kapılar

1. **Envanter ve hak denetimi:** Canlı katalogda mod × dil × durum × kaynak sayıları çıkar. `seed_phase3_content` ile üretim verisi ayrılır. Mevcut örnek ilk 11 kaydının CC0 dayanağı ve diziliş kaynağı gözden geçirilir. Kodda DFB kaynak bağlantısı şu an 2018 şampiyonu genel kültür kaydında, ilk 11 kaydında değil; kaynak–soru eşlemesi düzeltilmelidir. Hak kanıtı eksik soru `draft`/`retired` sürecine alınır.
2. **Kaynak bağlayıcıları:** Wikidata sorgularını ve openfootball JSON'larını sürümlü, küçük partiler hâlinde al. Ham yanıt, kaynak URL, lisans kanıtı, erişim zamanı ve kaynak sürümünü `ImportJob`/`ImportRecord` ile ilişkilendir; mevcut modellerde bulunmayan kanıt/sürüm alanlarını önce ekle. Tekrar çalıştırma aynı `external_id`'yi güncellesin; ağ hatasında kaldığı yerden devam etsin.
3. **Aday soru üretimi:** Mevcut importer yalnız referans `competition/player/match/lineup` kayıtlarını içe aktarır; **soru üretmez**. Her mod için referans kayıttan `Question` + `QuestionPayload` + iki `QuestionTranslation` oluşturan ayrı, idempotent taslak üretici gerekir. Otomatik üretilen her soru `draft` başlar; tekil `seed_key`/olgusal anahtar ve kanonik varlık kimlikleriyle mükerrerler elenir.
4. **Otomatik doğrulama:** Şema, hak, TR/EN eşdeğerliği, 2010+ kapsamı, skorun 90 dakika oluşu, kariyer sıralaması, lineup slot/diziliş toplamı, dört şıkta tek doğru cevap ve public payload içinde cevap sızıntısı denetlenir. Kaynak lisansını yalnız `license_status=verified` yazarak geçilmiş sayma; bağlantı ve kullanım gerekçesi editörce kontrol edilsin.
5. **Editör yayını:** Her dalga için adaylar `draft → in_review → approved → published` akışından geçer. Editör olguyu en az bir güvenilir kaynakla karşılaştırır, sorunlu soruları `retired` yapar. Yayın başlamadan katalog doğrulama komutu ve tüm modların pratik/çok oyunculu testleri çalışır.
6. **Dalga değerlendirmesi:** Kabul edilen soru sayısı, aday→yayın dönüşüm oranı, ret nedenleri, soru başına kaynak sayısı, çift dil eksikleri, oyuncu hata bildirimleri ve aynı sorunun yeniden görünme oranı raporlanır. Sonraki hedefler yalnız bu rapora göre artırılır.

**Geçiş koşulu:** Her dalga hedefindeki sayılar `published` ve iki dilde oynanabilir olmalı; telif/atıf sorunu, doğrulanmamış skor veya gizli cevabı açığa çıkaran yük olmamalı. Bir mod koşulu sağlayamazsa diğer modların artışı devam eder, o modun hedefi açık bekler.

## 5. İlk uygulanacak küçük paket

Önce 10 futbolcu çöp adamı + 20 tarihi lig skoru + 20 genel kültür hedefiyle başlayın. Bunlar CC0 kaynaklardan en temiz otomasyon yolunu sunar. Aynı dönemde 10 kariyer adayını ve 5 ilk 11 adayını yalnız hak ve veri bütünlüğü süzgecinden geçirin; yayın kararı bu süzgeçten sonra verilsin. Pilotun gerçek üretim/verim ölçümleri Dalga 2 hedefini kesinleştirsin.
