# Faz 6 QA

Bu testler çalışan Docker Compose servislerini kullanır. Ön koşullar:

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml exec -T backend python manage.py seed_phase3_content
cd qa
npm install
npx playwright install chromium
npm run test:e2e
```

`BASE_URL` ile staging veya başka bir web adresi verilebilir. İlk senaryo iki ayrı browser context'i kullanarak misafirlerin odaya katılmasını, maçın başlamasını ve aynı `round.start` sorusunu görmesini doğrular. İkinci senaryo klavye odağını, `aria-pressed` durumunu ve giriş alanlarının erişilebilir isimlerini kontrol eder.
