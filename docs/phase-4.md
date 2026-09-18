# Faz 4 — Derecesiz çok oyunculu oyun

**Durum:** Tamamlandı
**Kapsam:** Hesaplı kullanıcılar için 48 saatlik asenkron düello, misafir/hesap destekli 2–8 kişilik özel oda, canlı WebSocket tur state’i ve derecesiz çok oyunculu arayüz.

## 1. Teslim edilen kapsam

- `ParticipantRoundState` modeli ile her katılımcının aynı sabit `Round` kaydı üzerindeki deadline, ara cevap durumu ve tamamlanma durumu ayrıştırıldı.
- Oyun seti başlangıçta PostgreSQL `Round` kayıtlarına yazılır; oyuncular soru seçimini istemciye bırakamaz.
- Asenkron düello:
  - yalnız hesaplı kullanıcı oluşturabilir ve katılabilir,
  - iki oyuncu aynı soru/round kayıtlarını farklı zamanlarda oynar,
  - her katılımcının mod deadline’ı ayrıdır,
  - toplam davet penceresi 48 saattir,
  - süre dolduğunda davet sahibi lehine `forfeit` sonucu yazılır,
  - ranked puanına dokunulmaz.
- Özel oda:
  - misafir veya hesaplı kullanıcı oluşturabilir/katılabilir,
  - oda kodu 6 karakterdir,
  - kapasite 2–8 oyuncudur,
  - karışık oda beş modu birer tur kullanır; tek modlu oda seçilen modu tekrarlar,
  - oda sahibi başlatır ve tüm oyuncular aynı turu tamamlayana kadar sonraki tura geçilmez,
  - oda sonucu yalnız oda içi skor olarak tutulur; ranked puanına dokunulmaz.
- WebSocket `/ws/v1/match/{match_id}/` artık:
  - `round.start`, `match.state`, `answer.result` ve `pong` mesajlarını,
  - bağlantı sonrası aktif katılımcı turunu,
  - canlı odada tur ilerlemesini ve skor state’ini taşır.
- REST fallback answer endpoint’leri bağlantı kopması ve mobil istemci için korunur.
- Vue çok oyunculu ekranı:
  - özel oda oluşturma/katılma/başlatma,
  - oyuncu rail’i, gerçek bağlantı ve skor state’i,
  - beş moda özel canlı cevap alanları,
  - hesaplı asenkron düello oluşturma/katılma,
  - Türkçe/İngilizce metin kaynakları.

## 2. API sözleşmesi

| Uç nokta | Yetki | Amaç |
|---|---|---|
| `POST /api/v1/duels` | Hesap | Sabit soru setli asenkron düello oluşturur. |
| `GET /api/v1/duels/<id>` | Düello katılımcısı | Kendi aktif turunu ve rakip state’ini getirir. |
| `POST /api/v1/duels/<id>/join` | Hesap | Düelloya ikinci hesabı ekler. |
| `POST /api/v1/duels/<id>/play` | Düello katılımcısı | Katılımcının kendi deadline’ı ile cevap işler. |
| `POST /api/v1/rooms` | Misafir/hesap | 2–8 kişilik bekleme odası oluşturur. |
| `GET /api/v1/rooms/<code>` | Oda katılımcısı | Oda ve aktif tur state’ini getirir. |
| `POST /api/v1/rooms/<code>/join` | Misafir/hesap | Odaya katılır. |
| `POST /api/v1/rooms/<code>/start` | Oda sahibi | En az iki oyuncuyla sabit seti başlatır. |
| `POST /api/v1/rooms/<code>/answers` | Oda katılımcısı | WebSocket kullanılamadığında cevap işler. |

`round.start` yükünde `answer_data`, canonical cevap veya kabul edilen alias listesi bulunmaz. Katılımcıya özel ara state yalnız ilgili katılımcıya döndürülür.

## 3. WebSocket mesajları

İstemci → sunucu:

```json
{"type":"answer.submit","round_id":"<uuid>","answer":{"choice_index":0}}
{"type":"ping"}
{"type":"rejoin"}
```

Sunucu → istemci:

```json
{"type":"round.start","id":"<uuid>","mode":"timed_trivia","deadline":"<utc>"}
{"type":"answer.result","phase":"waiting","result":"correct","points":18,"score":18}
{"type":"match.state","status":"live","participants":[]}
```

Örnek yükler yalnız sözleşme alanlarını gösterir; doğru cevap hiçbir mesajda yer almaz.

## 4. Doğrulama

- PostgreSQL migration: `quiz.0004_match_result_match_room_code_match_settings_and_more` başarıyla uygulandı.
- Django system check: başarılı.
- Backend pytest: **16 passed**.
- Frontend `vue-tsc --noEmit && vite build`: başarılı.
- Faz 4 API testleri:
  - 2 misafirli tek modlu oda oluşturma, katılma, başlatma ve iki taraflı sonuç,
  - aynı soru ID’si/prompt’u kullanan hesaplı asenkron düello,
  - misafirin asenkron düello oluşturmasının reddi.

## 5. Faz sınırı

Ranked matchmaking, Elo/rating event yazımı ve liderlik tablosu Faz 5’tedir. Faz 4 oda ve düello sonuçlarını ranked puanına bağlamaz.
