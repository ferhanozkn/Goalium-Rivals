# Faz 1 — Çalışan ürün omurgası

**Durum:** Tamamlandı
**Kapsam:** Django API, PostgreSQL kalıcılığı, Redis/Channels gerçek zamanlı katmanı, Vue istemcisi ve yerel Docker Compose çalışma ortamı.

## 1. Teslim edilen kapsam

- Django 5.2 + Django REST Framework backend'i.
- PostgreSQL zorunlu veritabanı; SQLite yapılandırması yoktur.
- Redis tabanlı Django Channels katmanı ve Daphne ASGI sunucusu.
- Celery worker başlangıç yapılandırması.
- E-posta/parola hesabı ve 24 saatlik, hash'lenmiş misafir oturumu.
- JWT ve `X-Guest-Token` kimlik doğrulaması.
- Beş oyun modunu döndüren sürümlü REST uç noktası.
- Pratik oturum, canlı 1v1 maç oluşturma ve ikinci oyuncunun katılması.
- İki istemcinin aynı maç WebSocket grubuna bağlanması, durum yayını, ping ve yeniden bağlanma mesajları için temel protokol.
- Vue 3 + Vite + Pinia + Vue Router + vue-i18n istemcisi.
- Türkçe/İngilizce arayüz metinleri ve canlı API durum paneli.
- OpenAPI şeması: [`openapi.json`](openapi.json).

## 2. Yerel çalıştırma

Kök dizinde `.env.example` dosyasını `.env` olarak kopyalayıp yerel değerleri doldurun. `.env` depoya gönderilmez.

```bash
docker compose -f infra/docker-compose.yml up --build
```

Servisler:

| Servis | Adres | Amaç |
|---|---|---|
| Frontend | `http://localhost:5173` | Vue geliştirme sunucusu |
| API | `http://localhost:8000` | Django REST API |
| OpenAPI | `http://localhost:8000/api/v1/docs/` | Swagger arayüzü |
| Şema | `http://localhost:8000/api/v1/schema/` | OpenAPI JSON |
| WebSocket | `ws://localhost:8000/ws/v1/match/<match_id>/` | Canlı maç kanalı |

## 3. Temel API akışı

1. `POST /api/v1/guest/session` ile misafir token alınır.
2. `X-Guest-Token` başlığıyla `POST /api/v1/matches` çağrılır.
3. İkinci misafir aynı başlıkla `POST /api/v1/matches/<id>/join` çağrısı yapar.
4. İki istemci `ws/v1/match/<id>/?guest_token=<token>` adresine bağlanır.
5. Sunucu `match.state` mesajlarıyla katılımcı ve bağlantı durumunu yayınlar.

Tur soruları, cevap doğrulama, puanlama ve ranked motoru bu fazın dışındadır. Bu nedenle WebSocket'te `answer.submit` şu aşamada `ROUND_NOT_STARTED` ile kontrollü şekilde yanıtlanır; doğru cevap veya gizli içerik istemciye gönderilmez.

## 4. Kabul doğrulaması

Faz 1 kapanışında aşağıdaki kontroller başarıyla çalıştırılmıştır:

```bash
docker compose -f infra/docker-compose.yml exec -T backend pytest -q
docker compose -f infra/docker-compose.yml exec -T frontend npm run build
docker compose -f infra/docker-compose.yml exec -T backend python manage.py check
docker compose -f infra/docker-compose.yml exec -T backend python manage.py makemigrations --check --dry-run
```

Backend testleri hesap/misafir auth, mod sözleşmesi, canlı maç katılımı ve iki WebSocket istemcisinin aynı maç durumunu almasını kapsar.

## 5. Faz 2 sınırı

İçerik modelleri, onay akışı, soru import pipeline'ı, tur motoru, deadline/timeout hesaplama, cevap normalizasyonu, puanlama ve ranked işlemleri sonraki fazlarda uygulanacaktır. Faz 1'deki model ve endpoint'ler bu iş kurallarının altyapısını sağlar; iş kuralı REST view veya Vue bileşenine kopyalanmaz.
