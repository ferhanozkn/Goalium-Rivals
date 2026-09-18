# Faz 3 — Oyun motoru ve pratik

**Durum:** Tamamlandı
**Kapsam:** Sunucu otoriteli soru seçimi, deadline/timeout yönetimi, beş modun cevap doğrulaması ve puanlaması, misafir destekli pratik API'si ve iki dilli Vue pratik ekranı.

## 1. Teslim edilen kapsam

- `backend/apps/quiz/engine/` altında framework'ten bağımsız pratik motoru:
  - published soru havuzundan dil ve mod bazlı seçim,
  - aynı pratik oturumunda soru tekrarını önleme,
  - UTC deadline ve server clock doğrulaması,
  - cevap normalizasyonu ve Türkçe karakter eşdeğerliği,
  - beş modun puanlama ve timeout kuralları,
  - timed trivia yanlış cevap deadline cezası,
  - tur ilerlemesi, `Answer` kaydı ve PostgreSQL transaction kilitleri.
- `Round.private_state` ile ara oyun durumu sunucuda tutulur; `QuestionPayload.answer_data` ve private state REST yüklerine girmez.
- Faz 3 için migration'lar:
  - `content.0002_question_seed_key_questiontranslation_public_data`
  - `quiz.0003_gamesession_deadline_round_private_state_and_more`
- `seed_phase3_content` management command ile doğrulanmış kaynaklara bağlı Türkçe/İngilizce örnek içerik:
  - çöp adam,
  - kariyer yolu,
  - süreli genel kültür,
  - tarihi maç skoru,
  - eksik oyuncu.
- Vue pratik ekranı:
  - tek mod veya beş modu sırayla seçme,
  - gerçek deadline'dan kalan süre rail'i,
  - her moda özel cevap alanı,
  - puan/sonuç geri bildirimi,
  - Türkçe ve İngilizce çeviri kaynakları,
  - klavye ile cevap gönderme ve erişilebilir etiketler.

## 2. API sözleşmesi

| Uç nokta | Yetki | Amaç |
|---|---|---|
| `POST /api/v1/practice/sessions` | Misafir veya hesap | Seçilen modlarla tek oyunculu pratik başlatır ve ilk public turu döndürür. |
| `GET /api/v1/practice/sessions/<id>` | Oturum sahibi | Aktif turu ve PostgreSQL'deki skoru yeniden yükler. |
| `POST /api/v1/practice/sessions/<id>/answers` | Oturum sahibi | `round_id` ve moda özgü cevabı doğrular; sonuç, puan ve sonraki turu döndürür. |

Pratik turu public yükünde `id`, `mode`, `deadline`, `server_now`, prompt, şıklar, ipuçları ve moda özgü public data bulunur. Canonical cevap, doğru şık, kabul edilen cevap listesi ve private ilerleme bulunmaz.

## 3. İçerik seed'i

Yerel doğrulama için:

```bash
docker compose -f infra/docker-compose.yml exec -T backend \
  python manage.py seed_phase3_content
```

Komut yalnız referans olarak kullanılan doğrulanmış kaynak kayıtlarına bağlanan yayınlanabilir içerik üretir; soruların cevap verisi `QuestionPayload.answer_data` içinde kalır.

## 4. Doğrulama

- Django system check: başarılı.
- Backend pytest: **12 passed**.
- Frontend `vue-tsc --noEmit && vite build`: başarılı.
- Public content smoke test: 6 yayınlanmış Faz 3 sorusu döndü; cevap verisi dönmedi.
- OpenAPI `spectacular --validate`: 0 hata. Mevcut choice enum isimleri için 5 uyarı devam ediyor.
- PostgreSQL migration ve seed komutu Docker Compose servisleri üzerinde çalıştırıldı.

## 5. Faz sınırı

Bu faz tek oyunculu pratikle sınırlıdır. Asenkron düello, özel oda, canlı çok oyunculu tur orchestration'ı, matchmaking ve ranked puanlama Faz 4/5 kapsamındadır.
