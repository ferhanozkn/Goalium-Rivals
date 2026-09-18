# Goalium Rivals — Codex çalışma kuralları

Bu dosya, projede çalışan kod ajanları için operasyonel başlangıç notudur. Ürün ve mimari açısından tek referans [PROJECT.MD](PROJECT.MD)'dir; bu dosya onun yerine geçmez.

## Başlamadan önce

- `PROJECT.MD` dosyasını tamamen oku.
- Aktif fazı ve ilgili kabul ölçütlerini kontrol et.
- Faz 0 kararları ve örnekleri için [`docs/phase-0.md`](docs/phase-0.md) dosyasını oku.
- Belirsiz bir ürün kararı varsa varsayım yapma; `PROJECT.MD` içindeki açık kararlar bölümüne taşı ve sor.

## Değişmez teknik kurallar

- Kalıcı veritabanı yalnız PostgreSQL'dir. SQLite fallback'i, test veritabanı veya geçici kalıcı kayıt çözümü ekleme.
- Redis yalnız Channels katmanı, kuyruk, kilit ve önbellek içindir; tek doğruluk kaynağı değildir.
- Oyun kuralları `backend/apps/quiz/engine/` altında, ranked kuralları `backend/apps/ranking/` altında tutulur. REST view'larına, WebSocket consumer'larına veya Vue bileşenlerine kural kopyalama.
- Doğru cevap istemciye gönderilmez. `round.start` yükleri bu açıdan test edilmeden özellik tamamlanmış sayılmaz.
- Ranked uygunluğu yalnız `is_ranked_eligible(match)` ile belirlenir.
- Model değişiklikleri migration dosyasıyla birlikte yapılır; elle SQL ile şema değiştirilmez.
- Kullanıcıya görünen tüm metinler Türkçe ve İngilizce çeviri kaynaklarında tutulur; bileşenlere sabit metin gömme.
- Sırlar, API anahtarları ve parolalar depoya yazılmaz; ortam değişkenlerinden okunur.
- Tüm zaman damgaları UTC'dir; süre ve deadline kararını sunucu verir.
- Harici içerik yalnız lisansı doğrulanmış kaynaklardan alınır. Lisans belirsizse içerik yayınlanmaz.

## Çalışma ve teslim standardı

- Önce küçük ve gözden geçirilebilir değişiklikler yap; mevcut kullanıcı değişikliklerini silme veya ezme.
- Her fazın kodu, testi, migration'ı, iki dilli metni ve ilgili doküman güncellemesi birlikte tamamlanır.
- Test çalıştırmadan “tamamlandı” deme. Çalışmayan bağımlılık veya altyapı varsa komutu ve engeli açıkça raporla.
- Faz sınırını aşan özellikleri uygulama. Bu proje için Faz 0 tamamlanmadan Django/Vue altyapısına başlanmaz.
- Git geçmişinde anlamlı, küçük commitler kullan; sırları ve yerel ortam dosyalarını commit etme.

## Mevcut durum

- Faz 0: tamamlandı.
- Faz 1: tamamlandı. Teslim kapsamı ve yerel doğrulama sonuçları [`docs/phase-1.md`](docs/phase-1.md) içindedir.
- Faz 2: tamamlandı. Teslim kapsamı ve doğrulama sonuçları [`docs/phase-2.md`](docs/phase-2.md) içindedir.
- Faz 3: tamamlandı. Teslim kapsamı ve doğrulama sonuçları [`docs/phase-3.md`](docs/phase-3.md) içindedir.
- Faz 4: tamamlandı. Teslim kapsamı ve doğrulama sonuçları [`docs/phase-4.md`](docs/phase-4.md) içindedir.
- Faz 5: tamamlandı. Teslim kapsamı ve doğrulama sonuçları [`docs/phase-5.md`](docs/phase-5.md) içindedir.
- Faz 6: tamamlandı. Teslim kapsamı ve doğrulama sonuçları [`docs/phase-6.md`](docs/phase-6.md) içindedir.
- Sonraki faz: kullanıcı açıkça istemeden Faz 7 kapsamına geçilmez.
