# -*- coding: utf-8 -*-
"""Rescate completo de PRODUCCIÓN — correr ANTES de CADA despliegue.

En Render el servidor se restaura desde el repositorio en cada deploy: todo lo
cargado en el panel (precios, nombres, bajas) y las fotos subidas desde
/agregar viven SOLO hasta el próximo despliegue. Este script baja la base
íntegra de producción (ruta /backup.db) + las fotos que falten en el repo, y
los deja listos para commitear junto con el cambio de código.

Uso (desde la raíz del repo):
    python tools/rescatar_produccion.py             rescate completo
    python tools/rescatar_produccion.py --solo-db   solo la base (sin fotos)

Después: python tests/test_smoke.py  ->  commit  ->  push  ->  deploy hook.
"""
import json
import os
import sqlite3
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://catalogo-angelo.onrender.com"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REPO = os.path.join(RAIZ, "catalogo.db")
IMG_REPO = os.path.join(RAIZ, "data", "imagenes")
SOLO_DB = "--solo-db" in sys.argv

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
r = s.post(BASE + "/login",
           data={"email": "admin@mitienda.com.py", "password": "admin123"},
           allow_redirects=False, timeout=120)
if r.status_code != 302:
    sys.exit(f"login falló: {r.status_code}")

# 1) base íntegra
r = s.get(BASE + "/backup.db", timeout=180)
if r.status_code != 200 or not r.content.startswith(b"SQLite format 3"):
    sys.exit(f"backup falló: status={r.status_code} inicio={r.content[:20]!r}")
with open(DB_REPO, "wb") as f:
    f.write(r.content)
print(f"base rescatada: {len(r.content)} bytes -> catalogo.db")

if SOLO_DB:
    sys.exit(0)

# 2) fotos que falten en el repo
con = sqlite3.connect(DB_REPO)
filas = con.execute("SELECT images FROM products").fetchall()
con.close()

faltantes, listas, remotas, malas = set(), 0, 0, 0
for (imgs,) in filas:
    for p in json.loads(imgs or "[]"):
        if p.startswith("http"):
            remotas += 1
        elif ".." in p or p.startswith("/") or ":" in p:
            malas += 1
        else:
            faltantes.add(p.replace("\\", "/"))

descargadas = 0
for p in sorted(faltantes):
    destino = os.path.join(IMG_REPO, *p.split("/"))
    if os.path.exists(destino):
        listas += 1
        continue
    r = s.get(BASE + "/img/" + p, timeout=90)
    if r.status_code == 200 and (r.headers.get("Content-Type") or "").startswith("image/"):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(r.content)
        descargadas += 1
    else:
        print(f"  ⚠ foto no recuperable: {p} (status={r.status_code})")

print(f"fotos: {listas} ya estaban | {descargadas} descargadas | "
      f"{remotas} remotas (ignoradas) | {malas} rutas inválidas")
print("listo: revisar con `python tests/test_smoke.py` y commitear catalogo.db + data/")
