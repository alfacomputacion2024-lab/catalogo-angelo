# -*- coding: utf-8 -*-
"""Rescata precios cargados en PRODUCCIÓN y los guarda en catalogo.db (repo).

En Render el servidor se restaura desde el repositorio en CADA despliegue, así
que todo lo que el cliente cargue en el panel vive SOLO hasta el próximo
deploy. Este script baja el CSV del servidor y sincroniza `sell_price` en la
base del repo ANTES de subir los cambios.

Uso (desde la raíz del repo):
    python tools/rescatar_precios.py             diagnóstico, no toca nada
    python tools/rescatar_precios.py --aplicar   copia precios prod -> repo
"""
import csv
import io
import os
import sqlite3
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://catalogo-angelo.onrender.com"
DB_REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "catalogo.db")
APLICAR = "--aplicar" in sys.argv

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
r = s.post(BASE + "/login",
           data={"email": "admin@mitienda.com.py", "password": "admin123"},
           allow_redirects=False, timeout=90)
if r.status_code != 302:
    sys.exit(f"login falló: {r.status_code}")

r = s.get(BASE + "/exportar.csv", timeout=120)
filas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
prod_con_precio = [f for f in filas if f.get("precio_venta") not in ("", "None", None)]
print(f"productos en produccion: {len(filas)} | con precio en produccion: {len(prod_con_precio)}")

con = sqlite3.connect(DB_REPO)
cur = con.cursor()
locales = {ref: (sp or 0) for ref, sp in cur.execute(
    "select reference, sell_price from products where status='active'")}

difiere = rescatados = 0
for f in prod_con_precio:
    ref = f["referencia"]
    try:
        precio_prod = float(f["precio_venta"])
    except ValueError:
        continue
    precio_local = float(locales.get(ref) or 0)
    if precio_local != precio_prod:
        difiere += 1
        if APLICAR:
            cur.execute("update products set sell_price=? where reference=? and status='active'",
                        (precio_prod, ref))
            rescatados += 1

print(f"precios distintos prod vs repo: {difiere}")
if APLICAR:
    con.commit()
    print(f"precios rescatados al repo: {rescatados} (sumalos al commit)")
elif difiere:
    print("  -> corré con --aplicar para copiarlos ANTES de desplegar")
con.close()
