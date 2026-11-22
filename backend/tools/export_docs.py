#!/usr/bin/env python3
"""Gabungkan OpenAPI kedua service -> gateway/docs/openapi.yaml + docs/LingoGo.postman_collection.json

    python tools/export_docs.py [--base-url https://lingogo.stei.site]

Jalankan setiap kali endpoint berubah, lalu commit hasilnya.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "JWT_SECRET": "x" * 32, "DB_PATH": "/tmp/_export.db"}


def spec_of(service: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-c", "import json; from app.main import app; print(json.dumps(app.openapi()))"],
        cwd=ROOT / service, env=ENV, check=True, capture_output=True, text=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://lingogo.stei.site")
    a = ap.parse_args()

    phrase, user = spec_of("phrase-service"), spec_of("user-service")
    paths = {**phrase["paths"], **user["paths"]}
    paths.pop("/health", None)  # /health milik masing-masing service, diganti di bawah
    paths["/health"] = {"get": {
        "tags": ["system"], "summary": "Cek gateway hidup (tanpa auth)", "security": [],
        "responses": {"200": {"description": "OK", "content": {"application/json": {
            "example": {"gateway": "ok"}}}}}}}
    paths["/health/phrase-service"] = {"get": {
        "tags": ["system"], "summary": "Cek phrase-service (tanpa auth)", "security": [],
        "responses": {"200": {"description": "OK"}, "502": {"description": "Service mati"}}}}
    paths["/health/user-service"] = {"get": {
        "tags": ["system"], "summary": "Cek user-service (tanpa auth)", "security": [],
        "responses": {"200": {"description": "OK"}, "502": {"description": "Service mati"}}}}
    paths["/audio/{lang}/{file}"] = {"get": {
        "tags": ["pronunciation"], "summary": "File audio pengucapan (statis, tanpa auth)",
        "description": "Gunakan `target.audio_url` dari respons frasa. Berkas: `<key>.wav` (default, hasil Piper) "
                       "atau `<key>.mp3` bila audio dikonversi.",
        "security": [],
        "parameters": [
            {"name": "lang", "in": "path", "required": True, "schema": {"type": "string"}, "example": "de_DE"},
            {"name": "file", "in": "path", "required": True, "schema": {"type": "string"}, "example": "greet_hello.wav"}],
        "responses": {"200": {"description": "audio/wav atau audio/mpeg", "content": {
            "audio/wav": {"schema": {"type": "string", "format": "binary"}},
            "audio/mpeg": {"schema": {"type": "string", "format": "binary"}}}},
            "404": {"description": "Audio belum tersedia"}}}}

    # Pasang security hanya pada endpoint yang memang butuh auth (bawaan FastAPI sudah per-operasi)
    schemas = {**phrase["components"].get("schemas", {}), **user["components"].get("schemas", {})}
    sec = {**phrase["components"].get("securitySchemes", {}), **user["components"].get("securitySchemes", {})}
    merged = {
        "openapi": phrase["openapi"],
        "info": {
            "title": "LingoGo API", "version": "1.0.0",
            "description": (
                "API LingoGo (Tourism Language Assistance) — frasa, terjemahan, pelafalan & audio.\n\n"
                "**Autentikasi**\n- Pengguna aplikasi: `Authorization: Bearer <JWT>` dari `POST /auth/login`.\n"
                "- Kelompok lain (server ke server): header `X-API-Key` (minta ke kelompok lingogo).\n"
                "- Dibatasi rate limit per IP (HTTP 429 jika berlebihan).")},
        "servers": [{"url": a.base_url.rstrip("/") + "/api"}],
        "tags": [{"name": t} for t in ("system", "auth", "users", "destination-language",
                                       "phrasebook", "pronunciation", "admin")],
        "paths": dict(sorted(paths.items())),
        "components": {"schemas": schemas, "securitySchemes": sec},
    }
    (ROOT / "gateway/docs/openapi.yaml").write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print("tulis gateway/docs/openapi.yaml:", len(paths), "path")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/LingoGo.postman_collection.json").write_text(
        json.dumps(postman(a.base_url.rstrip("/")), indent=2, ensure_ascii=False), encoding="utf-8")
    print("tulis docs/LingoGo.postman_collection.json")


def req(name, method, path, *, auth="apikey", body=None, query=None, test=None):
    headers = [{"key": "Content-Type", "value": "application/json"}] if body else []
    if auth == "apikey":
        headers.append({"key": "X-API-Key", "value": "{{apiKey}}"})
    elif auth == "bearer":
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
    elif auth == "admin":
        headers.append({"key": "Authorization", "value": "Bearer {{adminToken}}"})
    url = {"raw": "{{baseUrl}}" + path + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else ""),
           "host": ["{{baseUrl}}"], "path": path.strip("/").split("/")}
    if query:
        url["query"] = [{"key": k, "value": v} for k, v in query.items()]
    item = {"name": name, "request": {"method": method, "header": headers, "url": url}}
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2, ensure_ascii=False)}
    if test:
        item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": test}}]
    return item


def postman(base):
    ok = lambda code: [f"pm.test('status {code}', () => pm.response.to.have.status({code}));"]
    save_token = ok(200) + ["pm.collectionVariables.set('token', pm.response.json().token);"]
    save_admin = ok(200) + ["pm.collectionVariables.set('adminToken', pm.response.json().token);"]
    folders = [
        ("System", [
            req("Health gateway", "GET", "/health", auth=None, test=ok(200)),
            req("Health phrase-service", "GET", "/health/phrase-service", auth=None, test=ok(200)),
            req("Health user-service", "GET", "/health/user-service", auth=None, test=ok(200))]),
        ("Auth & User", [
            req("Register", "POST", "/auth/register", auth=None,
                body={"name": "Penguji", "email": "penguji{{$timestamp}}@example.com", "password": "password123"},
                test=ok(201)),
            req("Login (akun demo) -> simpan token", "POST", "/auth/login", auth=None,
                body={"email": "{{demoEmail}}", "password": "{{demoPassword}}"}, test=save_token),
            req("Login admin -> simpan adminToken", "POST", "/auth/login", auth=None,
                body={"email": "{{adminEmail}}", "password": "{{adminPassword}}"}, test=save_admin),
            req("Me", "GET", "/auth/me", auth="bearer", test=ok(200)),
            req("Ubah preferensi", "PATCH", "/users/me/preferences", auth="bearer",
                body={"ui_language": "id", "pron_style": "id", "target_language": "de_DE"}, test=ok(200)),
            req("Lihat preferensi", "GET", "/users/me/preferences", auth="bearer", test=ok(200)),
            req("Logout (cabut token)", "POST", "/auth/logout", auth="bearer", test=ok(204))]),
        ("Destination & Language (X-API-Key)", [
            req("Daftar bahasa", "GET", "/languages", query={"ui": "id"}, test=ok(200)),
            req("Detail bahasa", "GET", "/languages/de_DE", test=ok(200)),
            req("Daftar destinasi", "GET", "/destinations", query={"ui": "id"}, test=ok(200)),
            req("Bahasa di destinasi", "GET", "/destinations/CH/languages", test=ok(200)),
            req("Nomor darurat satu destinasi", "GET", "/destinations/DE/emergency-numbers", test=ok(200)),
            req("Nomor darurat semua destinasi", "GET", "/emergency-numbers", query={"ui": "id"}, test=ok(200))]),
        ("Phrasebook (X-API-Key)", [
            req("Kategori", "GET", "/categories", query={"ui": "id"}, test=ok(200)),
            req("Daftar frasa (UI id, pelafalan id)", "GET", "/phrases", test=ok(200),
                query={"lang": "de_DE", "from": "id", "pron": "id", "category": "greeting"}),
            req("Cari frasa", "GET", "/phrases", query={"lang": "fr_FR", "q": "merci"}, test=ok(200)),
            req("Satu frasa", "GET", "/phrases/greet_hello", test=ok(200),
                query={"lang": "ja_JP", "from": "en", "pron": "en"})]),
        ("Admin (JWT admin)", [
            req("Ubah pelafalan", "PUT", "/phrases/basic_yes/translations/de_DE", auth="admin",
                body={"pronunciation_id": "YA"}, test=ok(200))]),
        ("Tanpa kunci (harus 401)", [
            req("Languages tanpa auth", "GET", "/languages", auth=None, test=ok(401))]),
    ]
    return {
        "info": {"name": "LingoGo API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                 "description": "Isi variabel apiKey (dari kelompok lingogo), demoEmail/demoPassword, adminEmail/adminPassword."},
        "variable": [
            {"key": "baseUrl", "value": base + "/api"},
            {"key": "apiKey", "value": ""}, {"key": "token", "value": ""}, {"key": "adminToken", "value": ""},
            {"key": "demoEmail", "value": "demo@lingogo.stei.site"}, {"key": "demoPassword", "value": ""},
            {"key": "adminEmail", "value": "admin@lingogo.stei.site"}, {"key": "adminPassword", "value": ""}],
        "item": [{"name": n, "item": items} for n, items in folders],
    }


if __name__ == "__main__":
    main()
