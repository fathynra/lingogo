#!/bin/sh
# Backup konsisten kedua database SQLite ke ./backup-YYYYmmdd-HHMM/ (aman saat service jalan)
set -e
D="backup-$(date +%Y%m%d-%H%M)"
mkdir -p "$D"
for svc in phrase-service user-service; do
  db=$([ "$svc" = phrase-service ] && echo phrases.db || echo users.db)
  docker compose exec -T "$svc" python -c "
import sqlite3
s = sqlite3.connect('/data/$db'); d = sqlite3.connect('/data/_backup.db'); s.backup(d); d.close(); s.close()"
  docker compose cp "$svc:/data/_backup.db" "$D/$db"
  docker compose exec -T "$svc" rm -f /data/_backup.db
done
echo "backup di $D/"; ls -lh "$D"
