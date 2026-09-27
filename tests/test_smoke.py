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
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import app  # noqa: E402

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
check("/client ordena productos al azar (varía entre visitas)",
      C.get("/client").data != C.get("/client").data)
r = C.get("/catalogo")
check("/catalogo público -> 200", r.status_code == 200)
check("/catalogo usa el amarillo principal", b'#F2C544' in r.data)
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
r = C.get("/img/amrelojes/3983_1.jpg")
check("foto local /img -> 200 image/jpeg",
      r.status_code == 200 and (r.mimetype or "").startswith("image/"))

print("— login admin —")
r = login("admin@mitienda.com.py", "admin123")
check("login admin -> redirect", r.status_code == 302)
r = C.get("/")
check("panel admin con sesión -> 200", r.status_code == 200 and b"Panel Admin" in r.data)
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

print(f"\nRESULTADO: {ok} OK / {fail} FAIL")
sys.exit(1 if fail else 0)
