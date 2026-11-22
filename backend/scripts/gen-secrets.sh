#!/bin/sh
# Cetak nilai acak untuk .env (JANGAN commit hasilnya)
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo "API_KEYS=namakelompok1:$(openssl rand -hex 16),namakelompok2:$(openssl rand -hex 16)"
echo "ADMIN_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=')"
echo "DEMO_PASSWORD=$(openssl rand -base64 9 | tr -d '/+=')"
