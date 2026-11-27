#!/bin/sh
# Jalankan di STB, dari folder backend/:  sh scripts/deploy.sh
set -e
git pull --ff-only          # menarik backend/ DAN database/ (CSV)
docker compose --profile tunnel up -d --build
docker compose ps
sleep 5
curl -fsS "http://localhost:${GATEWAY_PORT:-8080}/api/health" && echo
docker compose logs phrase-service 2>&1 | grep '\[seed\]' | tail -3
docker stats --no-stream
free -h
