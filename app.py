"""
Catálogo Angelo — servidor Flask: catálogo online + panel de administración.

Rutas principales
    /             Panel admin (requiere login)
    /catalogo     Catálogo online con edición (login para editar/eliminar)
    /client       Catálogo SOLO-LECTURA para clientes y revendedores (público)
    /portada      Portada liviana: buscador + 6 menús + marcas (pública)
    /marca/<slug> Página de UNA marca (pública, sólo sus productos)
    /tipo/<slug>  Página de UN tipo de producto (pública)
    /assets/<r>   CSS y JS del sitio (sólo .css y .js)
    /login        Acceso (roles: admin y socio)
    /agregar      Alta manual de productos con fotos (login)
    /pdf          Generación de PDFs por marca (login)
    /img/<ruta>   Fotos del catálogo desde data/imagenes (proxy para URL remotas)
    /static/<r>   Solo imágenes de marca (logos/favicon); NUNCA sirve código ni base

Uso local
    python app.py            -> http://127.0.0.1:5000
    python app.py --demo     -> datos de ejemplo (data_demo/), sin tocar la base real

Variables de entorno opcionales (producción): SECRET_KEY, ADMIN_PASSWORD, SOCIO_PASSWORD.
"""
import json
import os
import sys

if "--demo" in sys.argv:
    os.environ["CATALOGO_DATA_DIR"] = "data_demo"
    sys.argv.remove("--demo")

import csv
import io
import re
import sqlite3
import tempfile
import time
import unicodedata
from functools import wraps
from urllib.parse import urlencode

from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, send_file, send_from_directory,
                   session, url_for)

import config
import db
import respaldo
from marcas import short_brand, watch_brand
from pdf_catalog import build_pdf

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def slug(texto):
    """Nombre apto para URL y archivo: 'Q&Q' -> 'q-q', 'Pro Trek' -> 'pro-trek'.

    Cada marca y cada tipo de producto tienen su propia página:
        Flask     /marca/casio      /tipo/g-shock
        estático  marcas/casio.html tipos/g-shock.html
    El mismo slug se usa para el nombre del archivo, así que sirve en ambos modos.
    """
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "sin-nombre"


def parse_price(value):
    """'$1,234.50' / '1.234,50' / 'Gs. 1.500.000' / 1299 -> float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.,]", "", str(value))
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        parts = s.split(sep)
        s = "".join(parts) if (len(parts) > 2 or len(parts[-1]) == 3) else ".".join(parts)
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

# Plantillas: en producción (repo plano) están en la raíz; en desarrollo local
# viven en templates/. Detectamos cuál de las dos exista.
_TPL_DIR = 'templates' if os.path.isdir(os.path.join(_BASE_DIR, 'templates')) else '.'

# static_folder=None apaga la ruta /static automática de Flask: los archivos se
# sirven con la allowlist estricta de static_files() (solo imágenes, nunca
# código ni la base .db).
app = Flask(__name__,
            template_folder=_TPL_DIR,
            static_folder=None,
            static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", "catalogo-relojes-2026")

app.jinja_env.filters['short_brand'] = short_brand

# La marca real por producto (MARCAS_RELOJ, TIENDAS_*, CLAVES_MARCA y
# watch_brand) vive en marcas.py: módulo compartido con db.py.


def header_pills():
    """Conteo de productos activos agrupados por marca visible (orden desc)."""
    counts = {}
    for p in db.query_products(status="active", parse_specs=False):
        lbl = watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url"))
        counts[lbl] = counts.get(lbl, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


# --- Caché de las páginas públicas -------------------------------------------
# /client y /catalogo listan los 3.000+ productos: calcularlos en cada visita
# cuesta ~1,5 s en producción. Se guarda el resultado y solo se recalcula si
# cambió la base (mtime del catalogo.db) o venció el tiempo máximo (TTL).
_CACHE: dict = {}
_CACHE_TTL = 300  # segundos


def _db_fresca():
    """mtime de la base; si no se puede leer, devuelve 0 (fuerza recálculo)."""
    try:
        return os.path.getmtime(config.DB_PATH)
    except OSError:
        return 0.0


def _entrar_cache(clave, calcular, firmas=None):
    """Valor cacheado en `clave`; lo recalcula si la base cambió o venció el TTL.

    El mtime se toma ANTES de calcular: si alguien escribe mientras se calcula,
    la próxima petición ve un mtime distinto y vuelve a calcular. Así un cambio
    del panel se ve al instante en las páginas públicas.

    `firmas` agrega valores extra también invalidantes (p. ej. el mtime de la
    plantilla: un rediseño de /client se ve al instante, sin reiniciar nada).
    """
    f = (_db_fresca(),) + tuple(firmas or ())
    ent = _CACHE.get(clave)
    if ent is not None and ent[0] == f and (time.time() - ent[1]) < _CACHE_TTL:
        return ent[2]
    _CACHE[clave] = (f, time.time(), calcular())
    return _CACHE[clave][2]


def _client_html(estatico=False, solo_marca=None, solo_tipo=None):
    """HTML del catálogo público: sin sesión ni precios (cacheable tal cual).

    solo_marca / solo_tipo precargan el filtro EN EL SERVIDOR: la página de una
    marca (o de un tipo) sólo trae SUS productos, así se pinta al instante y el
    HTML no se repite 28 veces con los 3.084 productos. Lo usa /marca/<slug>,
    /tipo/<slug> y exportar_estatico.py; el panel no.

    `estatico=True` prepara la plantilla para vivir como "página normal"
    (archivos planos, sin Python): la ficha se pide a /api/ficha/<id>.json
    en vez de la ruta dinámica.
    """
    products = db.query_products(status="active", parse_specs=False)
    # Agrupar por MARCA REAL (nunca la tienda de origen) y ordenar cada grupo
    # por modelo (nombre -> referencia); las marcas, en orden alfabético.
    grupos = {}
    conteo_m = {}          # todas las marcas, aunque la página esté filtrada:
    for p in products:     # las píldoras de arriba siguen mostrando el catálogo
        marca = watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url"))
        conteo_m[marca] = conteo_m.get(marca, 0) + 1
        if solo_marca and marca != solo_marca:
            continue
        if solo_tipo and not _coincide_tipo(p, solo_tipo, marca):
            continue
        grupos.setdefault(marca, []).append(p)
    for items in grupos.values():
        items.sort(key=lambda p: ((p.get("name") or "").lower(), p.get("reference") or ""))
    grupos = {m: grupos[m] for m in sorted(grupos)}
    marcas = [m for m, _n in sorted(conteo_m.items())]
    # Tiles de "Colecciones": las 8 marcas con más modelos (sólo en la vista total)
    destacadas = sorted(grupos.items(), key=lambda kv: -len(kv[1]))[:8]
    # Título del navegador distinto en cada página de marca / tipo
    if solo_marca:
        pag, titulo = "marca", solo_marca
    elif solo_tipo:
        pag, titulo = "tipo", _nombre_tipo(solo_tipo)
    else:
        pag, titulo = "total", ""
    return render_template("client_catalog.html", grupos=grupos, marcas=marcas,
                           destacadas=destacadas, estatico=estatico,
                           pag=pag, pag_titulo=titulo,
                           marca_actual=solo_marca or "", tipo_actual=solo_tipo or "",
                           # Número para el carrito de interés (vacío = botón oculto)
                           whatsapp=os.environ.get("WHATSAPP_NUMERO", "").strip(),
                           theme=json.loads(config.THEME_PATH.read_text(encoding="utf-8")),
                           **_rutas(estatico, marcas))


# --- Portada:6 tipos de producto (mixto colección + público, pedido 07/10) ---
TIPOS_PORTADA = [
    ("G-Shock", "G-Shock"),
    ("Baby-G", "Baby-G"),
    ("Edifice", "Edifice"),
    ("Pro Trek", "Pro Trek"),
    ("Dama", "Dama"),
    ("Lentes", "Lentes y armazones"),
]


def _nombre_tipo(clave):
    """Nombre para mostrar ('Lentes' -> 'Lentes y armazones')."""
    for c, n in TIPOS_PORTADA:
        if c == clave:
            return n
    return clave


def _coincide_tipo(p, clave, marca):
    """Criterio del tipo de producto. DEBE coincidir con coincideTipo() de
    assets/js/catalogo.js (el conteo de la portada, las páginas /tipo/<slug>
    y el filtro del catálogo tienen que dar el mismo número)."""
    linea = (p.get("line") or "").lower().replace(" ", "")
    gen = (p.get("gender") or "").lower()
    if clave == "G-Shock":
        return "g-shock" in linea
    if clave == "Baby-G":
        return "baby-g" in linea
    if clave == "Edifice":
        return "edifice" in linea
    if clave == "Pro Trek":
        return "protrek" in linea
    if clave == "Dama":
        return gen == "dama" or "dama" in linea
    if clave == "Lentes":
        return marca in ("Lentes", "Armazones")
    return False


def _rutas(estatico, marcas=None):
    """Enlaces entre páginas, según el modo de funcionamiento.

    Cada marca y cada tipo de producto tienen SU página (así el sitio se arma
    con páginas y pestañas distintas, no con un único HTML gigante):

        Flask      /marca/casio · /tipo/g-shock
        estático   marcas/casio.html · tipos/g-shock.html · / y catalogo.html

    Devuelve también los diccionarios link_marca / link_tipo, que usan las
    plantillas para armar los href (una palabra por página, sin lógica en el HTML).
    """
    if estatico:
        ruta_catalogo, ruta_portada = "/catalogo.html", "/"
        pfx_m, pfx_t, suf = "/marcas/", "/tipos/", ".html"
    else:
        ruta_catalogo, ruta_portada = url_for("client_catalog"), url_for("portada")
        pfx_m, pfx_t, suf = "/marca/", "/tipo/", ""
    if marcas is None:
        marcas = [m for m, _n in header_pills()]
    return {
        "ruta_catalogo": ruta_catalogo,
        "ruta_portada": ruta_portada,
        "link_marca": {m: pfx_m + slug(m) + suf for m in marcas},
        "link_tipo": {clave: pfx_t + slug(clave) + suf for clave, _n in TIPOS_PORTADA},
    }


def _elegir_ejemplos(candidatos, limite=3):
    """3 modelos de ejemplo (con foto) para el menú de la portada.

    Prefiere referencias con forma de código de modelo (GA-2100, RB3025…)
    y marcas/líneas variadas, para que la guía muestre distinta gama.
    Devuelve dicts con id, marca, referencia y foto (/img/...).
    """
    con_foto = [p for p in candidatos if p.get("images")]

    def _clave(p):
        return (watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url")),
                (p.get("line") or "").lower())

    def _buena(p):
        ref = p.get("reference") or ""
        letras = sum(1 for ch in ref if ch.isalpha())
        return 2 <= letras and len(ref) <= 18   # p. ej. GA-2100-1A1, no "1292"

    elegidos, claves = [], set()

    def _pasada(filtro, por_clave):
        """Suma candidatos hasta `limite` sin repetir clave ni producto."""
        for p in con_foto:
            if len(elegidos) >= limite:
                break
            if p in elegidos or not filtro(p):
                continue
            k = _clave(p)
            if por_clave:
                if k in claves:
                    continue
                claves.add(k)
            elegidos.append(p)

    _pasada(_buena, True)           # 1ª: códigos de modelo, combinaciones distintas
    _pasada(_buena, False)          # 2ª: más códigos de modelo
    _pasada(lambda p: True, True)   # 3ª: otras combinaciones (marcas variadas)
    _pasada(lambda p: True, False)  # 4ª: completa si aún faltan

    return [{"id": p["id"],
             "marca": watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url")),
             "ref": p.get("reference") or p.get("name") or "",
             "img": "/img/" + p["images"][0]}
            for p in elegidos]


def _portada_datos():
    """(marcas con conteo alfabético, tipos con conteo, 3 ejemplos por tipo)."""
    products = db.query_products(status="active", parse_specs=False)
    conteo_m = {}
    conteo_t = {clave: 0 for clave, _ in TIPOS_PORTADA}
    candidatos = {clave: [] for clave, _ in TIPOS_PORTADA}
    for p in products:
        marca = watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url"))
        conteo_m[marca] = conteo_m.get(marca, 0) + 1
        for clave, _n in TIPOS_PORTADA:
            if _coincide_tipo(p, clave, marca):
                conteo_t[clave] += 1
                candidatos[clave].append(p)
    marcas = sorted(conteo_m.items())
    tipos = [(clave, nombre, conteo_t[clave]) for clave, nombre in TIPOS_PORTADA]
    ejemplos = {clave: _elegir_ejemplos(candidatos[clave]) for clave, _n in TIPOS_PORTADA}
    return marcas, tipos, ejemplos


def _portada_html(estatico=False):
    """Portada liviana: buscador + 6 menús (con 3 ejemplos c/u) + todas las
    marcas. SIN listado de productos: la primera página no carga nada pesado."""
    marcas, tipos, ejemplos = _portada_datos()
    return render_template("portada.html", marcas_conteo=marcas, tipos=tipos,
                           ejemplos=ejemplos, estatico=estatico,
                           whatsapp=os.environ.get("WHATSAPP_NUMERO", "").strip(),
                           **_rutas(estatico, [m for m, _n in marcas]))


def _catalogo_datos():
    """(productos ordenados por marca->modelo, pills con conteos) de /catalogo.

    El HTML de /catalogo sí depende del login (muestra Salir/Editar), por eso
    se cachea este cálculo y no la página final.
    """
    products = db.query_products(status="active", parse_specs=False)
    for p in products:
        p["_marca"] = watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url"))
    products.sort(key=lambda p: (p["_marca"], (p.get("name") or "").lower(),
                                 p.get("reference") or ""))
    conteos = {}
    for p in products:
        conteos[p["_marca"]] = conteos.get(p["_marca"], 0) + 1
    pills = sorted(conteos.items(), key=lambda kv: (-kv[1], kv[0]))
    return products, pills


app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
db.init_db()
respaldo.restaurar()   # si GitHub tiene un respaldo más nuevo, restaurar (Render borra al dormir)

# --- Usuarios del sistema (contraseñas por variable de entorno en producción) ---
USUARIOS = {
    "admin@mitienda.com.py": {"password": os.environ.get("ADMIN_PASSWORD", "admin123"),
                              "nombre": "Admin", "rol": "admin"},
    "socio@mitienda.com.py": {"password": os.environ.get("SOCIO_PASSWORD", "socio123"),
                              "nombre": "Socio", "rol": "editor"},
}


def login_requerido(f):
    """Decorador: exige login para rutas protegidas (panel y acciones)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def api_login_requerido(f):
    """Decorador de API: responde 401 JSON (nunca redirect) si no hay sesión."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return jsonify({"error": "login requerido"}), 401
        return f(*args, **kwargs)
    return decorated


def back():
    """Vuelve a la página anterior del panel (query string en 'back')."""
    qs = request.form.get("back", "")
    return redirect(url_for("index") + (("?" + qs) if qs else ""))


# =============================================================================
# Login / Logout
# =============================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        user = USUARIOS.get(email)
        if user and user["password"] == pwd:
            session["usuario"] = {"email": email, "nombre": user["nombre"], "rol": user["rol"]}
            nxt = request.args.get("next", url_for("catalogo"))
            return redirect(nxt)
        error = "Email o contraseña incorrectos"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("catalogo"))


@app.route("/")
@login_requerido
def index():
    """Panel admin (protegido). Los visitantes sin sesión caen en /login."""
    f = {k: request.args.get(k, "") for k in ("brand", "line", "gender", "q")}
    status = request.args.get("status", "active")
    page = request.args.get("page", 1, type=int)
    per_page = 50
    # Filtrar por MARCA REAL (watch_brand): la columna brand guarda también
    # la tienda de origen, que nunca se muestra en los menús.
    all_products = db.query_products(line=f["line"] or None, gender=f["gender"] or None,
                                     q=f["q"] or None, status=status,
                                     marca=f["brand"] or None)
    total = len(all_products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    products = all_products[(page - 1) * per_page : page * per_page]
    for p in products:
        p["_marca"] = watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url"))
    opt_status = status if status in ("active", "deleted") else "active"
    totals = db.stats()
    pills = header_pills()
    qs = urlencode({k: v for k, v in request.args.items() if k != "page" and v})
    return render_template(
        "index.html", products=products, f=f, status=status,
        brands=[lbl for lbl, _ in pills],
        lines=db.distinct_values("line", opt_status),
        genders=db.distinct_values("gender", opt_status),
        n_active=sum(v["active"] for v in totals.values()),
        n_deleted=sum(v["deleted"] for v in totals.values()),
        by_brand=totals, pills=pills, qs=qs, back=request.query_string.decode(),
        page=page, total_pages=total_pages, total=total,
    )


@app.route("/img/<path:p>")
def img(p):
    # Si es URL remota, hacer proxy (para Wix que bloquea hotlink)
    if p.startswith("http"):
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(p, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return Response(data, content_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            abort(404)
    # Si el archivo local existe, servirlo (cache 1 h: las fotos pesan ~47 KB y
    # casi nunca cambian; si reemplazás una, el navegador la toma en ≤1 hora)
    local = config.IMAGES_DIR / p
    if local.exists():
        resp = send_from_directory(config.IMAGES_DIR, p)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    # Si no existe (ej: en Render), devolver 1x1 pixel transparente
    import base64
    PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return Response(PIXEL, content_type="image/gif", headers={"Cache-Control": "public, max-age=86400"})


@app.route("/static/<path:p>")
def static_files(p):
    """Solo sirve archivos de IMAGEN (logos, favicon). El resto del repo —
    base catalogo.db, código .py, etc.— jamás sale por HTTP."""
    if ".." in p or not re.search(r"\.(png|jpe?g|gif|webp|svg|ico)$", p, re.I):
        abort(404)
    if not os.path.isfile(os.path.join(_BASE_DIR, p)):
        abort(404)
    resp = send_from_directory(_BASE_DIR, p)
    resp.headers["Cache-Control"] = "public, max-age=86400"   # logos/favicon: 1 día
    return resp


# =============================================================================
# Acciones masivas del panel (todas requieren login)
# =============================================================================
@app.post("/accion")
@login_requerido
def accion():
    ids = request.form.getlist("ids", type=int)
    action = request.form.get("action")
    if not ids:
        flash("No seleccionaste ningún producto.", "warn")
    elif action == "delete":
        n = db.set_status(ids, 'deleted')
        respaldo.respaldar()
        flash(f"{n} productos eliminados del catálogo (se pueden restaurar).", "ok")
    elif action == "restore":
        n = db.set_status(ids, 'active')
        respaldo.respaldar()
        flash(f"{n} productos restaurados.", "ok")
    return back()


@app.post("/precios")
@login_requerido
def precios():
    prices = {}
    for key, val in request.form.items():
        if key.startswith("price_"):
            prices[int(key[6:])] = parse_price(val) if val.strip() else None
    db.update_sell_prices(prices)
    respaldo.respaldar()
    flash("Precios de venta guardados.", "ok")
    return back()


@app.post("/stock")
@login_requerido
def stock():
    refs = [r for r in re.split(r"[\s,;]+", request.form.get("refs", "")) if r]
    if not refs:
        flash("Pega al menos una referencia.", "warn")
        return back()
    removed = db.keep_only_references(refs, partial=bool(request.form.get("partial")),
                                      marca=request.form.get("brand") or None)
    if removed:
        respaldo.respaldar()
    flash(f"Listo: se quitaron {removed} productos que no están en tu stock.", "ok")
    return back()


@app.post("/eliminar_marca")
@login_requerido
def eliminar_marca():
    brand = request.form.get("brand")
    if brand:
        n = db.delete_brand(marca=brand)
        if n:
            respaldo.respaldar()
        flash(f"{n} productos de {brand} eliminados.", "ok")
    return back()


@app.route("/pdf", methods=["GET", "POST"])
@login_requerido
def pdf():
    if request.method == "GET":
        return redirect(url_for("index"))
    try:
        brands = request.form.getlist("brands")
        all_products = db.query_products(status="active")
        products = [p for p in all_products if not brands
                    or watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url")) in brands]
        if not products:
            flash("No hay productos activos para el PDF.", "warn")
            return back()
        
        # Limitar productos para evitar crash en Render
        from pdf_catalog import MAX_PRODUCTS_FOR_PDF
        if len(products) > MAX_PRODUCTS_FOR_PDF:
            flash(f"⚠️ Limitado a {MAX_PRODUCTS_FOR_PDF} productos para evitar timeout. Seleccioná marcas específicas.", "warn")
            products = products[:MAX_PRODUCTS_FOR_PDF]
        
        print(f"[PDF] Generando PDF con {len(products)} productos...")
        path = build_pdf(products, show_prices=bool(request.form.get("show_prices")))
        print(f"[PDF] PDF generado: {path}")
        
        if not path or not os.path.exists(str(path)):
            return Response("<h1>Error</h1><p>No se pudo generar el PDF.</p><a href='/'>Volver</a>", mimetype="text/html")
        return send_file(str(path), mimetype="application/pdf",
                         as_attachment=request.form.get("mode") == "download")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(f"<h1>Error generando PDF</h1><pre>{e}</pre><a href='/'>Volver</a>", mimetype="text/html")


@app.route("/exportar.csv")
@login_requerido
def exportar():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["marca", "referencia", "nombre", "linea", "genero", "precio_venta",
                "precio_origen", "descripcion", "imagen_principal", "url_origen"])
    for p in db.query_products(status="active"):
        w.writerow([p["brand"], p["reference"], p["name"], p["line"], p["gender"], p["sell_price"],
                    p["price"], p["description"], (p["images"] or [""])[0], p["url"]])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=catalogo.csv"})


@app.route("/backup.db")
@login_requerido
def backup_db():
    """Copia íntegra de catalogo.db (precios, ediciones, bajas y estados).
    La usa tools/rescatar_produccion.py ANTES de cada despliegue: en Render el
    servidor se restaura desde el repositorio en cada deploy."""
    buf = io.BytesIO()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        src = sqlite3.connect(config.DB_PATH)
        dst = sqlite3.connect(tmp.name)
        src.backup(dst)          # instantánea consistente de la base
        dst.close()
        src.close()
        with open(tmp.name, "rb") as f:
            buf.write(f.read())
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    buf.seek(0)
    return send_file(buf, mimetype="application/x-sqlite3",
                     as_attachment=True, download_name="catalogo_backup.db")


# =============================================================================
# Catálogo Online
# =============================================================================
@app.route("/catalogo")
def catalogo():
    brand = request.args.get("brand", "")
    page = request.args.get("page", 1, type=int)
    per_page = 60
    # Productos ordenados + pills desde la caché (calcularlos cuesta ~1,5 s);
    # el HTML final sí se pinta por visita porque varía con el login.
    products, pills = _entrar_cache("catalogo", _catalogo_datos)
    if brand:
        products = [p for p in products if p["_marca"] == brand]
    pill_counts = dict(pills)
    total_all = sum(pill_counts.values())
    # Paginar sobre la lista ya ordenada
    total = len(products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = products[(page - 1) * per_page : page * per_page]
    by_brand_page = {}
    for p in paginated:
        by_brand_page.setdefault(p["_marca"], []).append(p)
    return render_template("catalogo.html", by_brand=by_brand_page,
                           brands=[lbl for lbl, _ in pills], pill_counts=pill_counts,
                           total_all=total_all,
                           selected_brand=brand, theme=json.loads(config.THEME_PATH.read_text(encoding="utf-8")),
                           usuario=session.get("usuario"),
                           page=page, total_pages=total_pages, total=total)


# =============================================================================
# Catálogo para clientes (solo visual, sin admin, sin precios)
# =============================================================================
def _tpl_mtime(nombre):
    """mtime de una plantilla; 0 si no existe (fuerza el recálculo)."""
    try:
        return os.path.getmtime(os.path.join(_BASE_DIR, _TPL_DIR, nombre))
    except OSError:
        return 0.0


def _mapa_slugs():
    """{'casio': 'Casio', 'q-q': 'Q&Q', ...} — cacheado, depende de la base."""
    return {slug(m): m for m, _n in header_pills()}


@app.route("/client")
def client_catalog():
    # HTML calculado una vez y cacheado (idéntico para todos: sin sesión ni
    # precios). El cálculo vive en _client_html(); la invalidez, en _entrar_cache().
    # firmas: el mtime de la plantilla invalida la caché si cambia el diseño.
    html = _entrar_cache("client", _client_html,
                         firmas=(_tpl_mtime("client_catalog.html"),))
    return Response(html, content_type="text/html; charset=utf-8")


@app.route("/portada")
def portada():
    """Portada pública liviana: buscador + 6 menús + marcas, sin listado."""
    html = _entrar_cache("portada", _portada_html,
                         firmas=(_tpl_mtime("portada.html"),))
    return Response(html, content_type="text/html; charset=utf-8")


@app.route("/marca/<s>")
def marca_pagina(s):
    """Página de UNA marca: sólo sus productos, con su URL propia
    (el HTML sale más liviano y cada marca se puede compartir por separado)."""
    nombre = _entrar_cache("slugs_marcas", _mapa_slugs).get(slug(s))
    if not nombre:
        abort(404)
    html = _entrar_cache("marca:" + slug(s),
                         lambda: _client_html(solo_marca=nombre),
                         firmas=(_tpl_mtime("client_catalog.html"),))
    return Response(html, content_type="text/html; charset=utf-8")


@app.route("/tipo/<s>")
def tipo_pagina(s):
    """Página de UN tipo de producto (los 6 menús de la portada)."""
    clave = next((c for c, _n in TIPOS_PORTADA if slug(c) == slug(s)), None)
    if not clave:
        abort(404)
    html = _entrar_cache("tipo:" + slug(s),
                         lambda: _client_html(solo_tipo=clave),
                         firmas=(_tpl_mtime("client_catalog.html"),))
    return Response(html, content_type="text/html; charset=utf-8")


@app.route("/assets/<path:archivo>")
def assets(archivo):
    """CSS y JS del sitio. Allowlist estricta: sólo *.css y *.js dentro de
    assets/ — nunca otras carpetas ni el código Python del panel."""
    if ".." in archivo or not re.search(r"\.(css|js)$", archivo):
        abort(404)
    base = os.path.join(_BASE_DIR, "assets")
    if not os.path.isfile(os.path.join(base, archivo)):
        abort(404)
    resp = send_from_directory(base, archivo)
    resp.headers["Cache-Control"] = "public, max-age=1800"
    return resp


@app.route("/robots.txt")
def robots_txt():
    """Indica a los buscadores que todo el catálogo es indexable (antes devolvía
    404). El /backup.db queda fuera: es para respaldo, no para la web."""
    return Response("User-agent: *\nAllow: /\nDisallow: /backup.db\n",
                    content_type="text/plain; charset=utf-8")


@app.route("/favicon.ico")
def favicon_ico():
    """El navegador pide /favicon.ico directo (pestaña nueva, historial):
    lo mandamos al favicon real en vez de responder 404."""
    return redirect("/static/favicon_A.png", code=302)


# =============================================================================
# Agregar producto manualmente
# =============================================================================
@app.route("/agregar", methods=["GET", "POST"])
@login_requerido
def agregar():
    brands = [lbl for lbl, _ in header_pills()]   # marcas reales (nunca tiendas)
    if request.method == "POST":
        # Obtener datos del formulario
        brand = request.form.get("brand", "").strip()
        reference = request.form.get("reference", "").strip()
        name = request.form.get("name", "").strip()
        line = request.form.get("line", "").strip()
        gender = request.form.get("gender", "").strip()
        description = request.form.get("description", "").strip()
        price = parse_price(request.form.get("price", ""))
        sell_price = parse_price(request.form.get("sell_price", ""))
        url_origen = request.form.get("url", "").strip()

        if not brand or not reference:
            flash("Marca y referencia son obligatorios.", "warn")
            return render_template("agregar.html", brands=brands, form=request.form)

        # Procesar imágenes subidas
        images = []
        files = request.files.getlist("images")
        for f in files:
            if f and f.filename:
                from images import save_image
                rel = save_image(f, brand, reference, len(images))
                if rel:
                    images.append(rel)

        # Guardar en la base
        db.upsert_product({
            "brand": brand, "reference": reference, "name": name,
            "line": line, "gender": gender, "description": description,
            "specs": {}, "price": price, "sell_price": sell_price,
            "currency": "USD", "url": url_origen, "images": images,
        })
        respaldo.respaldar(imagenes=images)
        flash(f"✅ {brand} {reference} agregado correctamente.", "ok")
        return redirect(url_for("agregar"))

    return render_template("agregar.html", brands=brands, form={})


# =============================================================================
# Ficha pública (galería al tocar un modelo) — SOLO lectura, sin login
# =============================================================================
@app.route("/api/ficha/<int:pid>")
def api_ficha(pid):
    """Devuelve las fotos extras y las especificaciones de un producto.

    No incluye precios ni url de origen: sirve igual en /client (sin precios)
    que en /catalogo (el precio ya se muestra en la tarjeta).
    """
    rows = db.query_products(status="active", ids=[pid])
    if not rows:
        return jsonify({"error": "Producto no encontrado"}), 404
    p = rows[0]
    return jsonify({
        "id": p["id"],
        "reference": p.get("reference") or "",
        "name": p.get("name") or "",
        "marca": watch_brand(p.get("brand"), p.get("line"), p.get("name"), p.get("url")),
        "line": p.get("line") or "",
        "images": [url_for("img", p=img) for img in (p.get("images") or [])],
        "specs": p.get("specs") or {},
    })


# =============================================================================
# API REST para gestionar productos desde el catálogo online (requiere login)
# =============================================================================
@app.route("/api/producto/<int:pid>", methods=["PUT"])
@api_login_requerido
def api_update_producto(pid):
    data = request.get_json(force=True)
    allowed = {"name", "line", "gender", "description", "sell_price", "reference"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "Sin campos válidos para actualizar"}), 400
    if "reference" in updates:
        # La referencia es parte de la clave única: se limpia y no se permite vacía.
        ref = " ".join(str(updates["reference"] or "").split())
        if not ref:
            return jsonify({"error": "La referencia no puede quedar vacía"}), 400
        updates["reference"] = ref
    with db.get_conn() as conn:
        if "reference" in updates:
            choque = conn.execute(
                "SELECT 1 FROM products WHERE reference=? AND id<>? "
                "AND brand=(SELECT brand FROM products WHERE id=?)",
                (updates["reference"], pid, pid),
            ).fetchone()
            if choque:
                return jsonify({"error": "Ya existe otro producto con esa referencia"}), 409
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [pid]
        cur = conn.execute(f"UPDATE products SET {sets} WHERE id=?", vals)
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado"}), 404
    respaldo.respaldar()
    return jsonify({"ok": True, "id": pid, "updated": list(updates.keys())})


@app.route("/api/producto/<int:pid>", methods=["DELETE"])
@api_login_requerido
def api_delete_producto(pid):
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE products SET status='deleted' WHERE id=? AND status='active'", (pid,))
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o ya eliminado"}), 404
    respaldo.respaldar()
    return jsonify({"ok": True, "id": pid})


@app.route("/api/producto/<int:pid>/restaurar", methods=["POST"])
@api_login_requerido
def api_restore_producto(pid):
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE products SET status='active' WHERE id=? AND status='deleted'", (pid,))
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o ya activo"}), 404
    respaldo.respaldar()
    return jsonify({"ok": True, "id": pid})


if __name__ == "__main__":
    import socket

    port = int(os.environ.get("PORT", 5000))
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    
    # Detectar si estamos en la nube
    is_cloud = os.environ.get("RENDER") or os.environ.get("PYTHONANYWHERE_DOMAIN")
    
    if is_cloud:
        print("Servidor iniciado en la nube")
    else:
        print("=" * 50)
        print("  CATÁLOGO DE RELOJES")
        print("=" * 50)
        print(f"  Panel admin:    http://127.0.0.1:{port}")
        print(f"  Catálogo:       http://127.0.0.1:{port}/catalogo")
        print(f"  Agregar:        http://127.0.0.1:{port}/agregar (requiere login)")
        print()
        print(f"  Desde tu celular (misma WiFi):")
        print(f"     http://{local_ip}:{port}/catalogo")
        print()
        print(f"  Login: admin@mitienda.com.py / admin123")
        print(f"  Login: socio@mitienda.com.py / socio123")
        print("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=not is_cloud)
