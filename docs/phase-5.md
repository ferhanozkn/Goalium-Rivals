# Faz 5 — Ranked ve liderlik tablosu

**Durum:** Tamamlandı
**Kapsam:** Hesaplı kullanıcılar için canlı ranked matchmaking, ortak Elo derecesi, idempotent rating event kaydı, global/sezon liderlik uçları ve ranked oyun arayüzü.

## 1. Teslim edilen kapsam

- `backend/apps/ranking/` altında bağımsız ranked katmanı:
  - `is_ranked_eligible(match)` tek uygunluk kapısıdır: canlı + 1v1 + karışık + `origin=matchmaking`.
  - Başlangıç puanı 1000, ilk 10 maç K=48, devamında K=32.
  - Derece satırları kullanıcı başına tutulur; galibiyet, beraberlik, mağlubiyet ve yerleştirme durumu saklanır.
  - `RatingEvent` üzerinde `(match, user)` UNIQUE kısıtı vardır.
- Redis yalnız geçici ranked kuyruğu ve eşleşme sonucu bildirimi için kullanılır. Maç, sonuç ve rating event kayıtları PostgreSQL'dedir.
- İkinci hesap kuyruğa girdiğinde iki hesap aynı dilde, karışık modlu, canlı 1v1 matchmaking maçı olarak eşleştirilir.
- Maç bitişi `submit_multiplayer_answer` transaction'ı içinde sonucu ve rating event'lerini birlikte yazar. Aynı sonuç tekrar işlendiğinde mevcut iki event döndürülür, puan ikinci kez değişmez.
- Eşit skor ve eşit toplam cevap süresi için canlı 1v1 maçına tek soruluk sudden-death turu eklenir; bu tur da eşitse beraberlik olarak işlenir.
- Davet, özel oda, asenkron düello ve pratik maçları `is_ranked_eligible` kapısından geçmez.
- Global leaderboard, mevcut yıl sezon leaderboard'u ve hesap istatistikleri PostgreSQL'den okunur.
- Vue ranked ekranı:
  - hesap girişi,
  - rating/placement/record özeti,
  - queue konumu ve iptal,
  - global leaderboard,
  - WebSocket üzerinden canlı ranked maç ve rating delta sonucu,
  - REST answer fallback.

## 2. API sözleşmesi

| Uç nokta | Yetki | Amaç |
|---|---|---|
| `POST /api/v1/matchmaking/queue` | Hesap | Ranked kuyruğuna girer; eşleşirse match ve ilk turu döndürür. |
| `GET /api/v1/matchmaking/queue/status` | Hesap | Kuyruk konumunu veya polling istemcisi için eşleşmiş maçı döndürür. |
| `DELETE /api/v1/matchmaking/queue` | Hesap | Ranked kuyruğundan çıkarır. |
| `POST /api/v1/matches/<id>/answers` | Ranked katılımcısı | WebSocket kullanılamadığında canlı ranked cevabı işler. |
| `GET /api/v1/leaderboard?period=global` | Hesap | Global rating tablosunu getirir. |
| `GET /api/v1/leaderboard?period=season` | Hesap | Mevcut veya istenen yılın sezon tablosunu getirir. |
| `GET /api/v1/me/stats` | Hesap | Rating, maç sayısı, W/D/L ve global/sezon sırasını getirir. |

`POST /api/v1/matches` artık yalnız davet kökenli canlı maç oluşturabilir; `origin=matchmaking` dışarıdan REST ile set edilemez. Ranked kökenli maçlar yalnız kuyruk motorundan çıkar.

## 3. Atomik rating akışı

1. Canlı maçın son turu transaction içinde sonuçlanır.
2. `is_ranked_eligible` kontrol edilir.
3. İki `ratings` satırı kullanıcı kimliği sırasıyla `SELECT ... FOR UPDATE` ile kilitlenir.
4. Elo beklenen sonuç, K katsayısı ve delta hesaplanır.
5. Rating satırları güncellenir ve iki `rating_events` kaydı yazılır.
6. `matches.result.rating_applied` ve katılımcı bazlı `rating_deltas` aynı transaction içinde yazılır.

Transaction ortasında hata olursa maç sonucu ve rating değişikliği birlikte geri alınır. Aynı maç tekrar çağrılırsa UNIQUE event kontrolü ikinci puan yazımını engeller.

## 4. Doğrulama

- PostgreSQL migration: `ranking.0001_initial` başarıyla uygulandı.
- Django system check: başarılı.
- Backend pytest: **21 passed**.
- Frontend `vue-tsc --noEmit && vite build`: başarılı.
- OpenAPI `spectacular --validate`: 0 hata; mevcut choice enum adları için 8 uyarı devam ediyor.
- Ranking testleri:
  - eşit başlangıç rating'inde kazanan +24 / kaybeden -24,
  - aynı maçın ikinci rating işleme çağrısında iki event ile sınırlı kalma,
  - davet maçının rating'i değiştirmemesi,
  - iki hesabın Redis kuyruk simülasyonunda matchmaking maçı oluşturması,
  - maç bitiş motorunun rating event'lerini yazması,
  - hesap istatistikleri ve global leaderboard.

## 5. Faz sınırı

PostgreSQL yedekleme/geri yükleme tatbikatı, iki tarayıcı Playwright canlı maç senaryosu, yük ve erişilebilirlik ölçümleri Faz 6 kapsamındadır.
