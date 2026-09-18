# PostgreSQL yedekleme ve geri yükleme

Üretimde günlük `pg_dump` + sürekli WAL arşivi kullanılmalıdır. Bu dizindeki smoke script, canlı veritabanını değiştirmeden:

1. PostgreSQL'den custom-format dump alır.
2. `goalium_restore_verify` adlı geçici bir veritabanına restore eder.
3. Kullanıcı, maç, soru ve rating satır sayılarının kaynakla aynı olduğunu doğrular.
4. Yalnız doğrulama için oluşturduğu geçici veritabanını siler.

Yerel çalıştırma:

```bash
./infra/backup/pg_backup_restore_smoke.sh
```

Başka bir restore veritabanı adı gerekiyorsa yalnız geçici ve açık bir ad kullanın:

```bash
RESTORE_DB=goalium_restore_verify_20260918 ./infra/backup/pg_backup_restore_smoke.sh
```

Dump dosyaları `.artifacts/backups/` altında üretilir ve depo dışında tutulmalıdır. Production sırları `.env` veya DigitalOcean secret/env yapılandırmasından gelir; dosyaya yazılmaz.
