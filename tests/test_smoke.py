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
from app import _entrar_cache  # noqa: E402
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
check("/client usa el amarillo principal (base.css)",
      b'#F2C544' in C.get("/assets/css/base.css").data)
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
check("/client menu enlaza la portada y anclas reales (Inicio/Catálogo)",
      b'href="/portada"' in r.data and b'href="#catalogo"' in r.data)
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
r = C.get("/static/favicon_A.png")
check("favicon ligero /static/favicon_A.png -> 200 (< 50 KB)",
      r.status_code == 200 and len(r.data) < 50 * 1024)

print("— robots.txt y favicon.ico (lo que piden los buscadores) —")
r = C.get("/robots.txt")
check("/robots.txt -> 200 y permite indexar el catálogo",
      r.status_code == 200 and (r.mimetype or "").startswith("text/plain")
      and b"User-agent" in r.data and b"Allow: /" in r.data)
check("/robots.txt deja fuera el respaldo de la base",
      b"Disallow: /backup.db" in r.data)
r = C.get("/favicon.ico")
check("/favicon.ico -> 302 al favicon real (sin 404)",
      r.status_code == 302 and "/static/favicon_A.png" in (r.headers.get("Location") or ""))

print("— fotos —")
r = C.get("/img/casio_oficial/A158WA-1.jpg")
check("foto oficial local /img -> 200 image/jpeg",
      r.status_code == 200 and (r.mimetype or "").startswith("image/"))
check("foto local en caché (Cache-Control public max-age=3600)",
      "public" in (r.headers.get("Cache-Control") or "")
      and "max-age=3600" in (r.headers.get("Cache-Control") or ""))

_n = [0]


def _calc():
    _n[0] += 1
    return _n[0]


check("caché de páginas memoriza el primer cálculo",
      _entrar_cache("test_smoke", _calc) == 1
      and _entrar_cache("test_smoke", _calc) == 1
      and _n[0] == 1)

print("— galería del modelo (visor de fotos) —")
html_client = C.get("/client").data.decode("utf-8")
check("/client incluye el visor de fotos", 'id="visor"' in html_client)
check("/client tarjetas con data-id (para abrir la ficha)", 'data-id="' in html_client)
check("/client avisa cuando un modelo tiene fotos extra", "foto-badge" in html_client)
m_id = re.search(r'data-id="(\d+)"', html_client)
check("/client alguna tarjeta trae id real", bool(m_id))
if m_id:
    r = C.get(f"/api/ficha/{m_id.group(1)}")
    j = r.get_json(silent=True) or {}
    check("api/ficha -> 200 JSON", r.status_code == 200 and isinstance(j, dict))
    check("api/ficha trae fotos por /img/ local",
          isinstance(j.get("images"), list) and len(j["images"]) >= 1
          and all(u.startswith("/img/") for u in j["images"]))
    check("api/ficha trae specs (dict)", isinstance(j.get("specs"), dict))
    check("api/ficha NO filtra el precio de venta",
          "sell_price" not in j and "price" not in j)
    check("api/ficha NO filtra la url de origen de otras tiendas",
          "url" not in j)
check("api/ficha id inexistente -> 404",
      C.get("/api/ficha/999999999").status_code == 404)
html_col = C.get("/catalogo").data.decode("utf-8")
check("/catalogo también tiene el visor", 'id="visor"' in html_col)
check("/catalogo el clic de Editar/Eliminar NO abre la galería",
      "closest('button')" in html_col)

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
check("API PUT admite corregir la referencia (404 = id inexistente)",
      C.put("/api/producto/99999999", json={"reference": "T"}).status_code == 404)
check("API PUT rechaza referencia vacía -> 400",
      C.put("/api/producto/99999999", json={"reference": "   "}).status_code == 400)
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

print("— portada en blanco (buscador + 6 menús con ejemplos + marcas) —")
_js_catalogo = C.get("/assets/js/catalogo.js").data.decode("utf-8")
r = C.get("/portada")
s_port = r.data.decode("utf-8")
check("/portada -> 200", r.status_code == 200)
check("/portada NO trae productos (ni fotos ni nombres)",
      'class="card"' not in s_port and 'data-id="' not in s_port)
check("/portada tiene los 6 tipos de producto", s_port.count('class="tipo-tile"') == 6)
check("/portada muestra 3 ejemplos por menú (guía de 18)",
      s_port.count('class="ej"') == 18)
n_marcas_port = len(re.findall(r'class="pill" data-marca="', s_port))
n_marcas_client = html_client.count('class="pill" data-marca="')
check("/portada lista TODAS las marcas del catálogo",
      n_marcas_port == n_marcas_client and n_marcas_port >= 20)
check("/portada es liviana (< 60 KB)", len(r.data) < 60 * 1024)
check("/client recibe los filtros de la portada (?q/?marca/?tipo)",
      "URLSearchParams(location.search)" in _js_catalogo)
check("/client enlaza de vuelta a la portada",
      'href="/portada"' in html_client)

print("— código separado: HTML sin CSS ni JS pegados —")
check("/portada sin <style> ni <script> pegados",
      "<style" not in s_port and "<script>" not in s_port)
check("/client sin <style> ni <script> pegados",
      "<style" not in html_client and "<script>" not in html_client)
check("/portada carga base.css + portada.css",
      '/assets/css/base.css' in s_port and '/assets/css/portada.css' in s_port)
check("/client carga base.css + catalogo.css",
      '/assets/css/base.css' in html_client and '/assets/css/catalogo.css' in html_client)
check("/assets/css/base.css -> 200 con el amarillo principal",
      b'#F2C544' in C.get("/assets/css/base.css").data)
check("/assets/js/tema.js y comun.js -> 200",
      C.get("/assets/js/tema.js").status_code == 200
      and C.get("/assets/js/comun.js").status_code == 200)
check("/assets sólo sirve css y js (nunca Python ni la base)",
      C.get("/assets/app.py").status_code == 404
      and C.get("/assets/../app.py").status_code == 404
      and C.get("/assets/css/../../app.py").status_code == 404)
check("ninguna página esconde contenido con estilos escritos en el HTML",
      "style=" not in s_port and 'style="display:none"' not in html_client
      and "onerror=" not in html_client)

print("— páginas por marca y por tipo (una por pestaña) —")
r = C.get("/marca/casio")
s_casio = r.data.decode("utf-8")
check("/marca/casio -> 200 y trae sólo productos Casio",
      r.status_code == 200 and s_casio.count('class="card"') > 2000
      and 'data-brand="Tissot"' not in s_casio)
check("/marca/casio titula la página con la marca",
      "<title>Casio" in s_casio)
check("/marca/q-q (Q&Q, carácter raro) -> 200",
      C.get("/marca/q-q").status_code == 200)
check("/marca inexistente -> 404", C.get("/marca/no-existe").status_code == 404)
_m = re.search(r'href="/tipo/g-shock"[^>]*>.*?<i>([\d.]+) modelos', s_port, re.S)
_n_gs = int(_m.group(1).replace(".", "")) if _m else -1
r = C.get("/tipo/g-shock")
check("/tipo/g-shock -> 200 con los MISMOS modelos que cuenta la portada",
      r.status_code == 200 and _n_gs > 0
      and r.data.decode("utf-8").count('class="card"') == _n_gs)
check("/tipo inexistente -> 404", C.get("/tipo/cualquiera").status_code == 404)

print("— división: página normal (HTML plano, sin Python) —")
check("/client dinámico se queda en fichas /api/ficha/<id> (sin .json)",
      'data-estatico="0"' in html_client)
check("/client incluye el carrito de interés (botón header + cajón)",
      'id="cartNav"' in html_client and 'id="carrito"' in html_client)
check("/client botón de WhatsApp oculto hasta que haya número",
      'id="carWa" hidden' in html_client)
check("el número de WhatsApp llega por data-wa (sin JS pegado)",
      'data-wa="' in html_client)
import tempfile                                     # noqa: E402
import json as _json                                # noqa: E402
from pathlib import Path                            # noqa: E402
import exportar_estatico                            # noqa: E402
with tempfile.TemporaryDirectory() as td:
    resumen = exportar_estatico.exportar(destino=td, sin_fotos=True, top=3)
    _idx = (Path(td) / "index.html").read_text(encoding="utf-8")
    _col = (Path(td) / "catalogo.html").read_text(encoding="utf-8")
    check("export: index.html = portada liviana (tipos, sin tarjetas)",
          'class="tipo-tile"' in _idx and 'class="card"' not in _idx)
    check("export: catalogo.html en modo estático (fichas en .json)",
          'data-estatico="1"' in _col and 'class="card"' in _col)
    check("export: una página por marca y una por tipo",
          (Path(td) / "marcas" / "casio.html").is_file()
          and (Path(td) / "marcas" / "q-q.html").is_file()
          and (Path(td) / "tipos" / "g-shock.html").is_file()
          and (Path(td) / "tipos" / "lentes.html").is_file()
          and resumen["paginas_marca"] >= 20 and resumen["paginas_tipo"] == 6)
    check("export: la página de una marca sólo trae SUS productos",
          'data-brand="Tissot"' not in
          (Path(td) / "marcas" / "casio.html").read_text(encoding="utf-8"))
    check("export: css y js copiados aparte (assets/)",
          (Path(td) / "assets" / "css" / "base.css").is_file()
          and (Path(td) / "assets" / "css" / "portada.css").is_file()
          and (Path(td) / "assets" / "css" / "catalogo.css").is_file()
          and (Path(td) / "assets" / "js" / "tema.js").is_file()
          and (Path(td) / "assets" / "js" / "comun.js").is_file()
          and (Path(td) / "assets" / "js" / "catalogo.js").is_file())
    check("export: las páginas apuntan a /assets/... y a /marcas/...",
          '/assets/css/base.css' in _col and '/marcas/casio.html' in _idx)
    _fichas = sorted((Path(td) / "api" / "ficha").glob("*.json"))
    _datos = [_json.loads(f.read_text(encoding="utf-8")) for f in _fichas]
    check("export: 3 fichas JSON con fotos por /img/ local",
          len(_datos) == 3
          and all(d["images"] and d["images"][0].startswith("/img/") for d in _datos))
    check("export: las fichas NUNCA llevan precio ni url de origen",
          all(("sell_price" not in d and "price" not in d and "url" not in d)
              for d in _datos))
    check("export: robots.txt permite indexar el catálogo",
          (Path(td) / "robots.txt").read_text(encoding="utf-8").startswith("User-agent"))
    check("export: favicon.ico en la raíz (lo pide el navegador solo)",
          (Path(td) / "favicon.ico").is_file()
          and (Path(td) / "favicon.ico").stat().st_size < 50 * 1024)
    check("export: favicon y logo copiados (carpeta static)",
          (Path(td) / "static" / "favicon_A.png").is_file()
          and (Path(td) / "static" / "logo.PNG").is_file())

print(f"\nRESULTADO: {ok} OK / {fail} FAIL")
sys.exit(1 if fail else 0)
