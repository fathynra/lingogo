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
check "tanpa auth ditolak"    401 "$(code "$BASE/api/provinces")"
if [ -n "$API_KEY" ]; then
  check "api key valid"   200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/provinces")"
  check "api key salah"   401 "$(code -H "X-API-Key: salah" "$BASE/api/provinces")"
  check "cari kota ada"   200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/cities?q=surabaya&ui=id")"
  check "cari kota tidak ada (pesan maaf)" 404 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/cities?q=atlantis&ui=id")"
  check "phrasebook kota" 200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/cities/3578/phrasebook?ui=id&pron=id")"
  check "nomor darurat" 200 "$(code -H "X-API-Key: $API_KEY" "$BASE/api/emergency-numbers")"
fi
if [ -n "$DEMO_EMAIL" ] && [ -n "$DEMO_PASSWORD" ]; then
  R=$(curl -s -X POST "$BASE/api/auth/login" -H 'content-type: application/json' \
      -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\"}")
  TOK=$(echo "$R" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
  check "login demo" 1 "$([ -n "$TOK" ] && echo 1 || echo 0)"
  check "JWT dipakai di phrase-service" 200 "$(code -H "Authorization: Bearer $TOK" "$BASE/api/provinces")"
  check "admin-only ditolak untuk user" 403 "$(code -X PUT -H "Authorization: Bearer $TOK" -H 'content-type: application/json' -d '{"text":"x"}' "$BASE/api/phrases/basic_yes/translations/jv_ID")"
fi
[ $fail -eq 0 ] && echo "SEMUA LULUS" || { echo "ADA YANG GAGAL"; exit 1; }
