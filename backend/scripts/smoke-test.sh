#!/bin/sh
# Uji cepat API publik/lokal.
#   BASE=https://lingogo.stei.site API_KEY=xxx DEMO_EMAIL=... DEMO_PASSWORD=... sh scripts/smoke-test.sh
BASE="${BASE:-http://localhost:8080}"
fail=0
check() {  # nama, status_diharapkan, status_asli
  if [ "$2" = "$3" ]; then echo "OK    $1 ($3)"; else echo "GAGAL $1 (harap $2, dapat $3)"; fail=1; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

check "health gateway"        200 "$(code "$BASE/api/health")"
check "health phrase-service" 200 "$(code "$BASE/api/health/phrase-service")"
check "health user-service"   200 "$(code "$BASE/api/health/user-service")"
check "tanpa auth ditolak"    401 "$(code "$BASE/api/languages")"
if [ -n "$API_KEY" ]; then
  check "api key valid"   200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/languages")"
  check "api key salah"   401 "$(code -H "X-API-Key: salah" "$BASE/api/languages")"
  check "nomor darurat" 200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/destinations/DE/emergency-numbers")"
  check "frasa + pelafalan" 200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/phrases?lang=de_DE&from=id&pron=id&category=greeting")"
fi
if [ -n "$DEMO_EMAIL" ] && [ -n "$DEMO_PASSWORD" ]; then
  R=$(curl -s -X POST "$BASE/api/auth/login" -H 'content-type: application/json' \
      -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\"}")
  TOK=$(echo "$R" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
  check "login demo" 1 "$([ -n "$TOK" ] && echo 1 || echo 0)"
  check "JWT dipakai di phrase-service" 200 "$(code -H "Authorization: Bearer $TOK" "$BASE/api/destinations")"
  check "admin-only ditolak untuk user" 403 "$(code -X PUT -H "Authorization: Bearer $TOK" -H 'content-type: application/json' -d '{"text":"x"}' "$BASE/api/phrases/basic_yes/translations/de_DE")"
fi
[ $fail -eq 0 ] && echo "SEMUA LULUS" || { echo "ADA YANG GAGAL"; exit 1; }
