#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Prueba de humo (smoke test): seguridad + rutas críticas del catálogo.

Verifica que:
  * el panel y sus acciones estén DETRÁS del login,
  * las APIs respondan 401 sin sesión,
  * /static jamás entregue la base .db ni código .py,
  * las fotos y los logos sí se sirvan,
  * login admin y socio funcionen (y la contraseña mala falle).

Uso:  python tests/test_smoke.py        (sale con código 1 si algo falla)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import app  # noqa: E402
from app import watch_brand  # noqa: E402
import respaldo  # noqa: E402

C = app.test_client()
ok = fail = 0


def check(nombre, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [OK]   {nombre}")
    else:
        fail += 1
        print(f"  [FAIL] {nombre}")


def login(email, pwd):
    return C.post("/login", data={"email": email, "password": pwd})


print("— públicos —")
r = C.get("/client")
check("/client público -> 200", r.status_code == 200)
check("/client no muestra el panel admin", b"Panel Admin" not in r.data)
check("/client pide las fotos por /img/ (ruta que existe)", b'src="/img/' in r.data)
check("/client incluye selector de fondo (data-tema)", b'data-tema' in r.data)
check("/client usa el amarillo principal", b'#F2C544' in r.data)
check("/client orden estable por marca y modelo (2 visitas idénticas)",
      C.get("/client").data == C.get("/client").data)
r = C.get("/client")
check("/client tiene buscador y filtro de marcas",
      b'id="buscador"' in r.data and b'data-marca=' in r.data)
check("/client agrupa por marca real, nunca por tienda de origen",
      b'data-marca="Casio"' in r.data
      and b'data-marca="AM Relojes"' not in r.data
      and b'data-brand="AM Relojes"' not in r.data)
secciones = re.findall(rb'brand-header">([^<]+)<', r.data)
check("/client secciones de marca en orden alfabético",
      len(secciones) >= 20 and secciones == sorted(secciones))
check("/client menu con anclas reales (Inicio/Catálogo)",
      b'href="#top"' in r.data and b'href="#catalogo"' in r.data)
r = C.get("/catalogo")
check("/catalogo público -> 200", r.status_code == 200)
check("/catalogo usa el amarillo principal", b'#F2C544' in r.data)
check("/catalogo pestañas por marca real (sin tiendas de origen)",
      b'>AM Relojes<' not in r.data and b'>Casio<span' in r.data)
r = C.get("/catalogo?brand=Casio")
check("/catalogo ?brand=Casio -> única sección Casio",
      re.findall(rb'brand-header">\s*<h2>([^<]+)</h2>', r.data) == [b"Casio"])
check("watch_brand: la tienda de origen se traduce a marca real",
      watch_brand("AM Relojes", "", "Casio GA-2100-1A", "") == "Casio")
r = C.get("/")
check("/ sin sesión -> redirect a /login",
      r.status_code == 302 and "/login" in r.headers.get("Location", ""))

print("— acciones y APIs sin sesión (deben estar bloqueadas) —")
check("/exportar.csv sin sesión -> bloqueado", C.get("/exportar.csv").status_code == 302)
check("/accion POST sin sesión -> bloqueado",
      C.post("/accion", data={"action": "delete"}).status_code == 302)
check("/precios POST sin sesión -> bloqueado",
      C.post("/precios", data={"price_1": "1"}).status_code == 302)
check("/pdf POST sin sesión -> bloqueado", C.post("/pdf", data={}).status_code == 302)
check("/backup.db sin sesión -> bloqueado", C.get("/backup.db").status_code == 302)
check("API PUT sin sesión -> 401",
      C.put("/api/producto/1", json={"name": "x"}).status_code == 401)
check("API DELETE sin sesión -> 401",
      C.delete("/api/producto/1").status_code == 401)

print("— /static: nunca código ni base —")
check("/static/catalogo.db -> 404", C.get("/static/catalogo.db").status_code == 404)
check("/static/app.py -> 404", C.get("/static/app.py").status_code == 404)
check("/static/../app.py -> 404", C.get("/static/../app.py").status_code == 404)
r = C.get("/static/logo_A.png")
check("favicon /static/logo_A.png -> 200", r.status_code == 200)

print("— fotos —")
r = C.get("/img/casio_oficial/A158WA-1.jpg")
check("foto oficial local /img -> 200 image/jpeg",
      r.status_code == 200 and (r.mimetype or "").startswith("image/"))

print("— login admin —")
r = login("admin@mitienda.com.py", "admin123")
check("login admin -> redirect", r.status_code == 302)
r = C.get("/")
panel = r.data
s_panel = panel.decode("utf-8")
check("panel admin con sesión -> 200", r.status_code == 200 and b"Panel Admin" in panel)
check("panel: menús solo con marcas reales (sin tiendas de origen)",
      b">AM Relojes</option>" not in panel and b">Casio</option>" in panel)
check("panel: las tarjetas muestran la marca real",
      b'class="brand">AM Relojes<' not in panel)
import db as _db  # noqa: E402
n_casio = sum(1 for p in _db.query_products(status="active")
              if watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url")) == "Casio")
m = re.search(rb"\((\d+) total\)", C.get("/?brand=Casio").data)
check("panel: ?brand=Casio filtra por marca real (incluye las de tiendas)",
      bool(m) and int(m.group(1)) == n_casio)
r = C.get("/agregar")
s_agr = r.data.decode("utf-8")
check("/agregar: datalist de marcas sin nombres de tienda",
      r.status_code == 200 and "Joyería Domínguez" not in s_panel
      and "Joyería Domínguez" not in s_agr and "Casio" in s_agr)
r = C.get("/backup.db")
check("/backup.db con sesión -> SQLite íntegro (rescate)",
      r.status_code == 200 and r.data[:16] == b"SQLite format 3\x00")
check("API PUT con sesión pasa la auth (404 = id inexistente)",
      C.put("/api/producto/99999999", json={"name": "x"}).status_code == 404)
C.get("/logout")

print("— login socio (revendedor) —")
r = login("socio@mitienda.com.py", "socio123")
check("login socio -> redirect", r.status_code == 302)
check("socio ve el panel -> 200", C.get("/").status_code == 200)
C.get("/logout")

print("— credenciales incorrectas —")
r = login("admin@mitienda.com.py", "esta-no-es")
check("contraseña incorrecta rechazada", b"incorrect" in r.data.lower())

print("— respaldo automático (inerte sin token) —")
check("respaldo.restaurar() no rompe sin token", respaldo.restaurar() is None)
check("respaldo.respaldar() no rompe sin token", respaldo.respaldar() is None)

print(f"\nRESULTADO: {ok} OK / {fail} FAIL")
sys.exit(1 if fail else 0)
