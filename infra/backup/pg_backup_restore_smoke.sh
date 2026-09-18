#!/usr/bin/env bash
set -euo pipefail

compose_file="${COMPOSE_FILE:-infra/docker-compose.yml}"
backup_dir="${BACKUP_DIR:-.artifacts/backups}"
restore_db="${RESTORE_DB:-goalium_restore_verify}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="${backup_dir}/goalium-${timestamp}.dump"

if [[ ! "${restore_db}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "RESTORE_DB yalnızca harf, sayı ve alt çizgi içerebilir." >&2
  exit 2
fi

mkdir -p "${backup_dir}"

compose() {
  docker compose -f "${compose_file}" "$@"
}

source_fingerprint="$(compose exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT '\''users='\'' || count(*) FROM accounts_user UNION ALL SELECT '\''matches='\'' || count(*) FROM quiz_match UNION ALL SELECT '\''questions='\'' || count(*) FROM content_question UNION ALL SELECT '\''ratings='\'' || count(*) FROM ranking_rating ORDER BY 1"')"

compose exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -Fc --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "${backup_path}"

cleanup() {
  compose exec -T postgres sh -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" dropdb --if-exists -U \"\$POSTGRES_USER\" ${restore_db}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

compose exec -T postgres sh -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" dropdb --if-exists -U \"\$POSTGRES_USER\" ${restore_db}"
compose exec -T postgres sh -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" createdb -U \"\$POSTGRES_USER\" ${restore_db}"
compose exec -T postgres sh -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" pg_restore --exit-on-error --no-owner -U \"\$POSTGRES_USER\" -d ${restore_db}" < "${backup_path}"

restore_fingerprint="$(compose exec -T postgres sh -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -At -U \"\$POSTGRES_USER\" -d ${restore_db} -c \"SELECT 'users=' || count(*) FROM accounts_user UNION ALL SELECT 'matches=' || count(*) FROM quiz_match UNION ALL SELECT 'questions=' || count(*) FROM content_question UNION ALL SELECT 'ratings=' || count(*) FROM ranking_rating ORDER BY 1\"")"

if [[ "${source_fingerprint}" != "${restore_fingerprint}" ]]; then
  echo "Backup restore fingerprint mismatch." >&2
  diff <(printf '%s\n' "${source_fingerprint}") <(printf '%s\n' "${restore_fingerprint}") || true
  exit 1
fi

echo "Backup restore passed: ${backup_path}"
printf '%s\n' "${restore_fingerprint}"
