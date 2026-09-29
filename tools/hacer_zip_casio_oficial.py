# -*- coding: utf-8 -*-
"""ZIP de TODAS las fotos oficiales de casio.com, organizadas por LÍNEA:

    Casio oficial/
        G-Shock/GA-2100-1A1.jpg
        Edifice/EFV-550D-2A.jpg
        Baby-G/...
        Pro Trek/...
        Oceanus/...
        Casio/...            (colección general / vintage)
        00_indice.csv        (línea, modelo, url oficial)
        _LEEME.txt

Portable (rutas relativas al repo). La línea y la url salen de la
base (`products.url` de casio.com); si algún archivo no está en la
base se usa el respaldo del scrapeo (`casio_rows.jsonl`) y, en el
último caso, la línea queda como "Casio".

Salida: un nivel arriba del repo -> Casio_Oficial_por_Linea.zip
"""
import csv
import io
import json
import os
import re
import sqlite3
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOTOS = os.path.join(REPO, "data", "imagenes", "casio_oficial")
OUT = os.path.join(os.path.dirname(REPO), "Casio_Oficial_por_Linea.zip")
SRC_JSONL = os.path.join(os.environ.get("TEMP", "/tmp"), "opencode",
                         "casio_rows.jsonl")

LINEAS = {"casio": "Casio", "gshock": "G-Shock", "babyg": "Baby-G",
          "edifice": "Edifice", "protrek": "Pro Trek", "oceanus": "Oceanus"}


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s or "x")


def linea_de_url(u):
    m = re.search(r"/watches/([^/]+)/", u or "")
    return LINEAS.get(m.group(1) if m else "",
                      (m.group(1).title() if m else "Casio"))


# --- modelo -> (linea, url) PRIMERO desde la base (portátil) ---
urls = {}
con = sqlite3.connect(os.path.join(REPO, "catalogo.db"))
for ref, line, images, url in con.execute(
        "SELECT reference, line, images, url FROM products "
        "WHERE status='active' AND url LIKE '%casio.com/%'"):
    fname = None
    try:
        for item in json.loads(images or "[]"):
            if item.startswith("casio_oficial/"):
                fname = os.path.basename(item)
                break
    except Exception:
        pass
    modelo = fname[:-4] if fname else ref
    if modelo:
        urls[modelo] = (line or linea_de_url(url), url)
con.close()
print(f"modelos en la base: {len(urls)}")

# --- respaldo del scrapeo para los que falten ---
if os.path.isfile(SRC_JSONL):
    for line in open(SRC_JSONL, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("url") and not r.get("err") and r.get("model"):
            urls.setdefault(r["model"], (linea_de_url(r["url"]), r["url"]))
print(f"modelos con datos (base + respaldo): {len(urls)}")

archivos = sorted(f for f in os.listdir(FOTOS) if f.endswith(".jpg"))
print(f"fotos en disco: {len(archivos)}")

# --- armado ---
por_linea = {}
sin_datos = []
faltantes = []
for fname in archivos:
    modelo = fname[:-4]
    info = urls.get(modelo)
    if info is None:
        # intento inverso: nombre saneado -> modelo original
        for m, (ln, u) in urls.items():
            if safe_name(m) == modelo:
                info = (ln, u)
                break
    if info is None:
        linea = "Casio"
        url = ""
        sin_datos.append(modelo)
    else:
        linea, url = info
    por_linea.setdefault(linea, []).append((modelo, url, fname))

# modelos con datos pero sin foto (no se excluyen, se informan)
con_datos = {safe_name(m) for m in urls}
faltantes = sorted(con_datos - {f[:-4] for f in archivos})

z = zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED)
indice = []
total = 0
print("\nPor línea:")
for linea in sorted(por_linea, key=str.casefold):
    items = sorted(por_linea[linea], key=lambda t: t[0].casefold())
    for modelo, url, fname in items:
        z.write(os.path.join(FOTOS, fname),
                f"Casio oficial/{linea}/{fname}")
        indice.append([linea, modelo, url])
        total += 1
    print(f"  {linea}: {len(items)}")

buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["linea", "modelo", "url_oficial"])
w.writerows(sorted(indice, key=lambda r: (r[0].casefold(), r[1].casefold())))
z.writestr("Casio oficial/00_indice.csv", "﻿" + buf.getvalue(),
           zipfile.ZIP_DEFLATED)

leeme = f"""FOTOS OFICIALES DE CASIO - POR LINEA
====================================
Generado: imagenes de casio.com (fotos oficiales, limpias, sin logos
de otras tiendas), descargadas a este servidor y servidas en local
(no redirigen a ninguna pagina).

Estructura:
  Casio oficial/
      G-Shock/Edifice/Baby-G/Pro Trek/Oceanus/Casio/
          <MODELO>.jpg     -> una foto oficial por modelo
      00_indice.csv        -> lista: linea, modelo, url oficial

Cantidad: {total} fotos de {len(por_linea)} lineas.
Abrir los .csv con Excel (UTF-8).
"""
z.writestr("Casio oficial/_LEEME.txt", leeme, zipfile.ZIP_DEFLATED)
z.close()

with zipfile.ZipFile(OUT) as zz:
    mal = zz.testzip()
    n_arch = len(zz.namelist())
mb = os.path.getsize(OUT) / 1048576
print(f"\nZIP: {OUT}")
print(f"Tamano: {mb:.1f} MB | archivos: {n_arch} | fotos: {total} | "
      f"integridad: {'OK' if mal is None else 'ERROR ' + str(mal)}")
if sin_datos:
    print(f"modelos sin url en el respaldo (puestos en 'Casio'): "
          f"{len(sin_datos)} -> {sin_datos[:8]}")
if faltantes:
    print(f"modelos con datos pero SIN foto ({len(faltantes)}): "
          f"{faltantes[:8]}")
