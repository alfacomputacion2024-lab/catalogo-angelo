# -*- coding: utf-8 -*-
"""ZIP del catálogo organizado por MARCA REAL (misma lógica que /client).

Portable: las rutas salen de la ubicación de este archivo (funciona en
esta PC, en Render y en Hostinger). Solo productos activos.

    python tools/hacer_zip_por_marca.py

Salida: un nivel arriba de la carpeta del sitio, llamado
`Catalogo_Angelo_por_Marca.zip`, con:

    Catalogo Angelo/<Marca real>/<Modelo [referencia]>/NN.jpg
    Catalogo Angelo/<Marca>/00_indice_<marca>.csv
    Catalogo Angelo/00_indice_general.csv
    Catalogo Angelo/_LEEME.txt

CSV en UTF-8 con BOM (se abren bien en Excel).
"""
import csv
import io
import json
import os
import re
import sys
import time
import zipfile

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(REPO), "Catalogo_Angelo_por_Marca.zip")
sys.path.insert(0, REPO)
from marcas import watch_brand  # noqa: E402

import sqlite3  # noqa: E402

RESERVADAS = {"con", "prn", "aux", "nul",
              *(f"com{i}" for i in range(1, 10)),
              *(f"lpt{i}" for i in range(1, 10))}


def limpiar(texto, maxl=70):
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", texto or "")
    t = re.sub(r"\s+", " ", t).strip(" .")
    if not t:
        t = "Sin nombre"
    if t.lower().split(" ")[0] in RESERVADAS:
        t = "_" + t
    return t[:maxl].strip(" .") or "Sin nombre"


con = sqlite3.connect(os.path.join(REPO, "catalogo.db"))
con.row_factory = sqlite3.Row
filas = con.execute(
    "SELECT id, brand, reference, name, line, gender, sell_price, url, images "
    "FROM products WHERE status='active'").fetchall()
con.close()

# --- agrupar por marca real (igual que /client) ---
grupos = {}
for p in filas:
    marca = watch_brand(p["brand"] or "", p["line"] or "",
                        p["name"] or "", p["url"] or "")
    grupos.setdefault(marca, []).append(p)

print(f"Productos activos: {len(filas)} | carpetas de marca: {len(grupos)}")

CACHE = {}
ses = requests.Session()
stats = {"local": 0, "remota": 0, "remota_fail": 0, "local_fail": 0}


def leer_imagen(ruta_local, url):
    if url:
        if url in CACHE:
            return CACHE[url]
        for _ in range(2):
            try:
                r = ses.get(url, timeout=15)
                if r.status_code == 200 and r.content:
                    CACHE[url] = r.content
                    return r.content
            except Exception:
                time.sleep(1)
        stats["remota_fail"] += 1
        return None
    ruta = os.path.join(REPO, "data", "imagenes", ruta_local)
    try:
        with open(ruta, "rb") as fh:
            stats["local"] += 1
            return fh.read()
    except OSError:
        stats["local_fail"] += 1
        return None


def ext_de(item, data):
    base = item.split("?")[0]
    ext = os.path.splitext(base)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ".jpg" if ext == ".jpeg" else ext
    return ".jpg" if not data else (
        ".png" if data[:4] == b"\x89PNG" else
        ".webp" if data[:4] == b"RIFF" else ".jpg")


z = zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED)
indice_rows = []
resumen = []
procesados = 0

for marca in sorted(grupos, key=str.casefold):
    prods = sorted(grupos[marca],
                   key=lambda p: ((p["name"] or "").casefold(),
                                  (p["reference"] or "").casefold()))
    mcarp = limpiar(marca, 40)
    csv_buf = io.StringIO()
    w = csv.writer(csv_buf)
    w.writerow(["marca", "modelo", "referencia", "linea", "genero",
                "precio_venta_gs", "fotos", "url"])
    usadas = {}
    n_ok = 0
    for p in prods:
        base = limpiar(
            f"{p['name'] or 'Producto'}"
            + (f" [{p['reference']}]" if p["reference"] else ""))
        carp = usadas.get(base)
        if carp is None:
            carp = base
            i = 2
            while carp in usadas.values():
                carp = f"{base} ({i})"
                i += 1
            usadas[base] = carp
        try:
            imgs = json.loads(p["images"] or "[]")
        except Exception:
            imgs = []
        guardadas = 0
        for k, item in enumerate(imgs, 1):
            url = item if item.startswith("http") else None
            data = leer_imagen(None if url else item, url)
            if not data:
                continue
            ext = ext_de(item, data)
            destino = f"Catalogo Angelo/{mcarp}/{carp}/{k:02d}{ext}"
            if url:
                stats["remota"] += 1
            z.writestr(destino, data, zipfile.ZIP_STORED)
            guardadas += 1
        if guardadas == 0:
            z.writestr(f"Catalogo Angelo/{mcarp}/{carp}/SIN FOTO.txt",
                       "Este producto no tiene fotos disponibles.\n",
                       zipfile.ZIP_DEFLATED)
        fila = [marca, p["name"] or "", p["reference"] or "",
                p["line"] or "", p["gender"] or "",
                p["sell_price"] or "", guardadas, p["url"] or ""]
        w.writerow(fila)
        indice_rows.append([marca] + fila[1:] + [f"{mcarp}/{carp}"])
        n_ok += 1
        procesados += 1
        if procesados % 250 == 0:
            print(f"  ...{procesados}/{len(filas)} productos")
    z.writestr(f"Catalogo Angelo/{mcarp}/00_indice_{mcarp}.csv",
               "﻿" + csv_buf.getvalue(), zipfile.ZIP_DEFLATED)
    resumen.append((marca, n_ok))

# indice general
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["marca", "modelo", "referencia", "linea", "genero",
            "precio_venta_gs", "fotos", "url", "carpeta"])
w.writerows(indice_rows)
z.writestr("Catalogo Angelo/00_indice_general.csv",
           "﻿" + buf.getvalue(), zipfile.ZIP_DEFLATED)

leeme = """CATALOGO ANGELO - CONTENIDO POR MARCA
=====================================

Carpeta por cada MARCA REAL (igual que el sitio), y dentro:

  Nombre del modelo [referencia]/
      01.jpg, 02.jpg ...   -> fotos del producto

  00_indice_<marca>.csv    -> lista de modelos de esa marca
  00_indice_general.csv    -> lista completa (todos los productos)

Los archivos .csv se abren con Excel y traen: marca, modelo, referencia,
linea, genero, precio de venta, cantidad de fotos y url.
Solo incluye productos ACTIVOS del catalogo.
"""
z.writestr("Catalogo Angelo/_LEEME.txt", leeme, zipfile.ZIP_DEFLATED)
z.close()

# --- verificacion ---
zz = zipfile.ZipFile(OUT)
mal = zz.testzip()
nombres = zz.namelist()
zz.close()
tamanio = os.path.getsize(OUT) / 1048576

print("\n=== RESULTADO ===")
print(f"ZIP: {OUT}")
print(f"Tamano: {tamanio:.1f} MB | integridad: {'OK' if mal is None else 'ERROR ' + str(mal)}")
print(f"Marcas (carpetas): {len(resumen)} | productos: {procesados}")
print(f"Fotos locales: {stats['local']} | remotas descargadas: {stats['remota']}")
print(f"Fallos -> local: {stats['local_fail']} | remota: {stats['remota_fail']}")
print("\nPor marca:")
for m, n in resumen:
    print(f"  {m}: {n}")
print(f"Archivos totales en zip: {len(nombres)}")
