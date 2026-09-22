"""
Panel de revisión del catálogo.
   python app.py            -> abre http://127.0.0.1:5000
   python app.py --demo     -> usa datos de ejemplo (data_demo/), sin tocar tu base real
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
import tempfile

from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, session, url_for)

import config
import db
from pdf_catalog import build_pdf
from scraper import parse_price

app = Flask(__name__, 
            template_folder='.',
            static_folder='.',
            static_url_path='/static')
app.secret_key = "catalogo-relojes-2026"

def short_brand(name):
    """Acorta nombres largos: 'Tiempo de Relojes (Casio)' -> 'Casio'"""
    if not name:
        return name
    import re
    m = re.match(r'^Tiempo de Relojes\s*\((.+)\)$', name)
    if m:
        return m.group(1)
    return name

app.jinja_env.filters['short_brand'] = short_brand
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
db.init_db()

# --- Usuarios del sistema (editar con tus datos reales) ---
USUARIOS = {
    "admin@mitienda.com.py": {"password": "admin123", "nombre": "Admin", "rol": "admin"},
    "socio@mitienda.com.py": {"password": "socio123", "nombre": "Socio", "rol": "editor"},
}


def login_requerido(f):
    """Decorador: exige login para rutas protegidas."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def back():
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
def index():
    f = {k: request.args.get(k, "") for k in ("brand", "line", "gender", "q")}
    status = request.args.get("status", "active")
    page = request.args.get("page", 1, type=int)
    per_page = 50
    all_products = db.query_products(brand=f["brand"] or None, line=f["line"] or None,
                                     gender=f["gender"] or None, q=f["q"] or None, status=status)
    total = len(all_products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    products = all_products[(page - 1) * per_page : page * per_page]
    opt_status = status if status in ("active", "deleted") else "active"
    totals = db.stats()
    return render_template(
        "index.html", products=products, f=f, status=status,
        brands=db.distinct_values("brand", opt_status),
        lines=db.distinct_values("line", opt_status),
        genders=db.distinct_values("gender", opt_status),
        n_active=sum(v["active"] for v in totals.values()),
        n_deleted=sum(v["deleted"] for v in totals.values()),
        by_brand=totals, back=request.query_string.decode(),
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
    return send_from_directory(config.IMAGES_DIR, p)


@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory(".", p)


@app.post("/accion")
def accion():
    ids = request.form.getlist("ids", type=int)
    action = request.form.get("action")
    if not ids:
        flash("No seleccionaste ningún producto.", "warn")
    elif action == "delete":
        flash(f"{db.set_status(ids, 'deleted')} productos eliminados del catálogo (se pueden restaurar).", "ok")
    elif action == "restore":
        flash(f"{db.set_status(ids, 'active')} productos restaurados.", "ok")
    return back()


@app.post("/precios")
def precios():
    prices = {}
    for key, val in request.form.items():
        if key.startswith("price_"):
            prices[int(key[6:])] = parse_price(val) if val.strip() else None
    db.update_sell_prices(prices)
    flash("Precios de venta guardados.", "ok")
    return back()


@app.post("/stock")
def stock():
    refs = [r for r in re.split(r"[\s,;]+", request.form.get("refs", "")) if r]
    if not refs:
        flash("Pega al menos una referencia.", "warn")
        return back()
    removed = db.keep_only_references(refs, partial=bool(request.form.get("partial")),
                                      brand=request.form.get("brand") or None)
    flash(f"Listo: se quitaron {removed} productos que no están en tu stock.", "ok")
    return back()


@app.post("/eliminar_marca")
def eliminar_marca():
    brand = request.form.get("brand")
    if brand:
        flash(f"{db.delete_brand(brand)} productos de {brand} eliminados.", "ok")
    return back()


@app.route("/pdf", methods=["POST"])
def pdf():
    try:
        brands = request.form.getlist("brands")
        all_products = db.query_products(status="active")
        products = [p for p in all_products if not brands or p["brand"] in brands]
        if not products:
            flash("No hay productos activos para el PDF.", "warn")
            return back()
        path = build_pdf(products, show_prices=bool(request.form.get("show_prices")))
        if not path or not os.path.exists(str(path)):
            flash("Error: no se pudo generar el archivo PDF.", "error")
            return back()
        return send_file(str(path), mimetype="application/pdf",
                         as_attachment=request.form.get("mode") == "download")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error generando el PDF: {e}", "error")
        return back()


@app.route("/exportar.csv")
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


# =============================================================================
# Catálogo Online
# =============================================================================
@app.route("/catalogo")
def catalogo():
    brand = request.args.get("brand", "")
    page = request.args.get("page", 1, type=int)
    per_page = 60
    products = db.query_products(status="active")
    brands = db.distinct_values("brand", "active")
    if brand:
        products = [p for p in products if p["brand"] == brand]
    # Agrupar por marca
    by_brand = {}
    for p in products:
        by_brand.setdefault(p["brand"], []).append(p)
    # Si no hay marca seleccionada, paginar el total
    total = len(products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = products[(page - 1) * per_page : page * per_page]
    by_brand_page = {}
    for p in paginated:
        by_brand_page.setdefault(p["brand"], []).append(p)
    return render_template("catalogo.html", by_brand=by_brand_page, brands=brands,
                           selected_brand=brand, theme=json.loads(config.THEME_PATH.read_text(encoding="utf-8")),
                           usuario=session.get("usuario"),
                           page=page, total_pages=total_pages, total=total)


# =============================================================================
# Agregar producto manualmente
# =============================================================================
@app.route("/agregar", methods=["GET", "POST"])
@login_requerido
def agregar():
    brands = db.distinct_values("brand", "active")
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
        flash(f"✅ {brand} {reference} agregado correctamente.", "ok")
        return redirect(url_for("agregar"))

    return render_template("agregar.html", brands=brands, form={})


# =============================================================================
# API REST para gestionar productos desde el catálogo online
# =============================================================================
@app.route("/api/producto/<int:pid>", methods=["PUT"])
def api_update_producto(pid):
    data = request.get_json(force=True)
    allowed = {"name", "line", "gender", "description", "sell_price"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "Sin campos válidos para actualizar"}), 400
    with db.get_conn() as conn:
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [pid]
        cur = conn.execute(f"UPDATE products SET {sets} WHERE id=?", vals)
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"ok": True, "id": pid, "updated": list(updates.keys())})


@app.route("/api/producto/<int:pid>", methods=["DELETE"])
def api_delete_producto(pid):
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE products SET status='deleted' WHERE id=? AND status='active'", (pid,))
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o ya eliminado"}), 404
    return jsonify({"ok": True, "id": pid})


@app.route("/api/producto/<int:pid>/restaurar", methods=["POST"])
def api_restore_producto(pid):
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE products SET status='active' WHERE id=? AND status='deleted'", (pid,))
        if cur.rowcount == 0:
            return jsonify({"error": "Producto no encontrado o ya activo"}), 404
    return jsonify({"ok": True, "id": pid})


if __name__ == "__main__":
    import socket
    import os
    
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
