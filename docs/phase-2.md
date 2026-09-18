# Faz 2 — İçerik yönetimi ve veri hattı

**Durum:** Tamamlandı
**Kapsam:** Futbol referans verilerinin PostgreSQL modelleri, provider-bağımsız import pipeline'ı, kaynak/lisans kapısı ve editör onay-yayın akışı.

## 1. Teslim edilen kapsam

- `content` uygulamasında şu referans modelleri:
  - Competition, Season, Team, Player
  - PlayerCareerEntry
  - FootballMatch
  - MatchLineup, LineupSlot
- `Question`, `QuestionPayload`, `QuestionTranslation` ve `AnswerAlias` modelleri.
- Her soruda kaynak URL'si, sağlayıcı ve lisans durumu tutulabilen `SourceReference` modeli.
- Soru durum akışı:

  ```text
  draft → in_review → approved → published → retired
  ```

- Yayın kapısı:
  - Türkçe ve İngilizce çeviri zorunlu.
  - `QuestionPayload` zorunlu.
  - En az bir kaynak zorunlu.
  - Tüm kaynakların lisans durumu `verified` olmalı.
- Yayınlanmış soru API'si yalnız `public_payload` ve seçilen dilin çevirisini döndürür; `answer_data` istemciye hiç serialize edilmez.
- Django admin üzerinden referans veri, soru, kaynak ve import kayıtlarının editör yönetimi.
- `imports` uygulamasında ham `ImportJob`/`ImportRecord` kayıtları ve provider-bağımsız eşleme servisi.
- Wikidata, openfootball ve manuel veri sağlayıcıları için ortak JSON kayıt formatı.

## 2. API uç noktaları

| Uç nokta | Yetki | Amaç |
|---|---|---|
| `GET /api/v1/content/questions?language=tr` | Herkese açık | Yalnız yayınlanmış soruları döndürür |
| `GET /api/v1/content/questions/<id>?language=en` | Herkese açık | Yayınlanmış soru detayı |
| `POST /api/v1/content/editor/sources` | Staff | Kaynak/lisans kaydı oluşturur |
| `POST /api/v1/content/editor/questions` | Staff | Soru, payload ve çevirileri oluşturur |
| `GET /api/v1/content/editor/questions/<id>` | Staff | Editör detay görünümü; cevap verisi yalnız staff'a görünür |
| `POST /api/v1/content/editor/questions/<id>/transition` | Staff | Durum geçişi yapar |
| `POST /api/v1/content/imports` | Staff | Ham kayıtları import eder |
| `GET /api/v1/content/imports/<id>` | Staff | Import işinin durumunu verir |

Editor uç noktaları JWT veya Django session auth ile çalışır ve `is_staff` olmayan kullanıcıları kabul etmez.

## 3. Import formatı

`POST /api/v1/content/imports` gövdesi:

```json
{
  "provider": "openfootball",
  "source_url": "https://github.com/openfootball/football.json",
  "license_name": "CC0",
  "license_status": "verified",
  "records": [
    {
      "record_type": "team",
      "external_id": "openfootball:france",
      "name": "France",
      "country_code": "FRA"
    }
  ]
}
```

Desteklenen `record_type` değerleri: `competition`, `season`, `team`, `player`, `career_entry`, `match`, `lineup`.

Aynı sağlayıcı kimliği tekrar gönderildiğinde PostgreSQL'deki `external_id` benzersizliği sayesinde kayıt güncellenir; yeni kopya oluşmaz. Ham veri ve sonuç durumu `ImportRecord` içinde korunur. Lisansı `blocked` olan import API ve management command tarafından reddedilir; `pending` kayıtlar katalogda tutulsa da soru yayınlama kapısından geçemez.

Dosya tabanlı kullanım:

```bash
docker compose -f infra/docker-compose.yml exec -T backend \
  python manage.py import_catalog /app/data/catalog.json \
  --provider openfootball \
  --source-url https://github.com/openfootball/football.json \
  --license-name CC0 \
  --license-status verified
```

## 4. Faz sınırı

Bu faz içerik üretimi ve yayınlanmasıyla sınırlıdır. Soru seçimi, deadline, timeout, cevap normalizasyonu, puanlama, pratik ekranları ve ranked işlemleri Faz 3 veya sonraki fazlara bırakılmıştır. Import katmanı doğrudan oyun oturumu oluşturmaz ve doğrulanmamış içeriği oyuncuya açmaz.

## 5. Doğrulama

Faz 2 için doğrulananlar:

- PostgreSQL migration'ları başarıyla uygulandı.
- Toplam backend testleri: hesap/misafir + WebSocket + içerik yayın kapısı + import idempotency.
- Yayınlanmamış soruların public endpoint'ten görünmediği test edildi.
- Yayınlanmış soruda `answer_data` ve canonical cevap alanının görünmediği test edildi.
- Eksik dil veya doğrulanmamış lisansla yayın geçişi engellendi.
- OpenAPI şeması hatasız üretildi.
