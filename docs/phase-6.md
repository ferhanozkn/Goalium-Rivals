# Faz 6 — Kalite ve kapalı beta

Faz 6, kritik oyun/API akışlarını kapalı beta öncesi doğrulama, içerik kataloğu kontrolü, erişilebilirlik iyileştirmeleri, temel yük ölçümü ve PostgreSQL veri kurtarma tatbikatını kapsar.

## Tamamlanan işler

- `GET /api/v1/health` eklendi; PostgreSQL ve Redis bağlantılarını birlikte kontrol eder, hata durumunda `503` döner.
- `validate_catalog` yönetim komutu yayınlanmış soruların iki dil çevirisini, public payload'ını ve doğrulanmış kaynaklarını denetler.
- WebSocket `round.start` ve `answer.result` yüklerinde tarih alanları JSON uyumlu biçimde serileştirilir; doğru cevap ve `answer_data` istemciye gönderilmez.
- Klavye odağı, `:focus-visible`, ekran okuyucu etiketleri, `aria-pressed`, canlı timer bölgeleri ve reduced-motion desteği eklendi.
- İki ayrı browser context ile özel oda canlı maç senaryosu ve erişilebilirlik smoke testleri eklendi.
- `infra/load_smoke.py` ile bağımlılıksız temel HTTP yük testi, `infra/backup/pg_backup_restore_smoke.sh` ile pg_dump/pg_restore kurtarma tatbikatı eklendi.
- DigitalOcean üretim/staging hedefi korunarak yerel doğrulama Docker Compose üzerinde yapıldı.

## Doğrulama sonuçları

Çalıştırılan komutlar ve sonuçları:

| Kontrol | Sonuç |
|---|---|
| Django `check` | Başarılı |
| `makemigrations --check` | Değişiklik yok |
| Backend pytest | **24 geçti** |
| Frontend production build | Başarılı |
| Katalog doğrulama | **6 yayınlanmış soru geçti** |
| Health endpoint | `{"status":"ok","database":"ok","redis":"ok"}` |
| Health yük smoke testi | **80/80 başarılı**, eşzamanlılık 8, median 56.5 ms, p95 83.12 ms, max 89.62 ms |
| OpenAPI validate | **0 hata**, mevcut choice-enum adlandırma uyarıları 8 |
| PostgreSQL backup/restore | Başarılı; `users=0`, `matches=0`, `questions=6`, `ratings=0` parmak izleri eşleşti |
| Playwright | **2 geçti**; iki browser context canlı maç + erişilebilirlik |

## Çalıştırma

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml exec -T backend python manage.py seed_phase3_content
docker compose -f infra/docker-compose.yml exec -T backend python manage.py validate_catalog
python3 infra/load_smoke.py --url http://localhost:8000/api/v1/health
bash infra/backup/pg_backup_restore_smoke.sh

cd qa
npm install
npx playwright install chromium
BASE_URL=http://localhost:5173 npm run test:e2e
```

## Faz sınırı

Web sürümü kapalı beta için kalite kapısından geçti. Sonraki iş paketi Faz 7'de REST ve WebSocket sözleşmelerini mobil istemci hazırlığı için sürümlemektir.
