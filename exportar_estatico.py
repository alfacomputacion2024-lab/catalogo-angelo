"""
Exporta el catálogo público como "página normal" (HTML plano, sin Python).

Genera la carpeta `sitio_publico/` lista para subir a cualquier hosting
(Cloudflare Pages, Hostinger, etc.):

    sitio_publico/
      index.html            -> PORTADA liviana (buscador + 5 menús con 6 ejemplos + marcas)
      catalogo.html         -> catálogo completo con las tarjetas de productos
      marcas/<slug>.html    -> UNA página por marca (20; Armazones y Lentes, ocultas)
      tipos/<slug>.html     -> UNA página por tipo de producto (5, sólo relojes)
      assets/css/*.css      -> hojas de estilo (base · portada · catálogo)
      assets/js/*.js        -> scripts (tema · comunes · catálogo)
      api/ficha/<id>.json   -> fotos + ficha de cada producto (sin precios)
      img/...               -> solo las fotos que usa el catálogo
      static/...            -> favicon y logos
      robots.txt

El panel de administración NO se exporta: sigue siendo Python (Render).

IMPORTANTE: los enlaces son absolutos (/assets/..., /marcas/..., /img/...),
así que el sitio debe subirse en la RAÍZ del dominio o de la subcarpeta
pública (no dentro de otra subcarpeta).

Uso:
    python exportar_estatico.py                 # export completo (con fotos)
    python exportar_estatico.py --sin-fotos      # solo HTML/JSON (pruebas)
    python exportar_estatico.py --top 5          # primeros N productos
    python exportar_estatico.py --destino X      # otra carpeta destino
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import app as app_mod            # noqa: E402  (arranca Flask + base de datos)
import config                    # noqa: E402


def _ficha_json(p):
    """JSON exactamente igual al que sirve /api/ficha/<id> (nunca precios)."""
    return {
        "id": p["id"],
        "reference": p.get("reference") or "",
        "name": p.get("name") or "",
        "marca": app_mod.watch_brand(p.get("brand"), p.get("line"),
                                     p.get("name"), p.get("url")),
        "line": p.get("line") or "",
        "images": ["/img/" + img for img in (p.get("images") or [])],
        "specs": p.get("specs") or {},
    }


def exportar(destino=None, sin_fotos=False, top=0):
    """Escribe la página normal en `destino`. Devuelve un dict con el resumen."""
    dest = Path(destino or (_BASE / "sitio_publico"))
    dest.mkdir(parents=True, exist_ok=True)

    # 1) Páginas HTML:
    #    index.html  = PORTADA liviana (buscador + 5 menús con 6 ejemplos + marcas)
    #    catalogo.html = catálogo completo con las 2.935 tarjetas de reloj
    #    marcas/<slug>.html = UNA página por marca, sólo con sus productos
    #    tipos/<slug>.html  = UNA página por tipo, sólo con los suyos
    with app_mod.app.test_request_context("/"):
        portada = app_mod._portada_html(estatico=True)
        catalogo = app_mod._client_html(estatico=True)
        marcas, tipos, _ejemplos = app_mod._portada_datos()
        paginas_marca = {app_mod.slug(m): app_mod._client_html(estatico=True, solo_marca=m)
                         for m, _n in marcas}
        paginas_tipo = {app_mod.slug(clave): app_mod._client_html(estatico=True, solo_tipo=clave)
                        for clave, _n, _c in tipos}
    (dest / "index.html").write_text(portada, encoding="utf-8")
    (dest / "catalogo.html").write_text(catalogo, encoding="utf-8")
    for s, html in paginas_marca.items():
        (dest / "marcas").mkdir(exist_ok=True)
        (dest / "marcas" / (s + ".html")).write_text(html, encoding="utf-8")
    for s, html in paginas_tipo.items():
        (dest / "tipos").mkdir(exist_ok=True)
        (dest / "tipos" / (s + ".html")).write_text(html, encoding="utf-8")
    # 1c) Páginas que YA no se generan (marcas ocultas, tipos retirados) se
    #     borran: si no, quedarían en línea en la web vieja de la carpeta.
    for carpeta, esperadas in (("marcas", set(paginas_marca)),
                               ("tipos", set(paginas_tipo))):
        for viejo in (dest / carpeta).glob("*.html"):
            if viejo.stem not in esperadas:
                viejo.unlink()

    # 1b) CSS y JS del sitio (la página no lleva ni una línea de estilo ni de
    #     script pegada: todo vive en assets/)
    origen_assets = config.BASE_DIR / "assets"
    if origen_assets.is_dir():
        shutil.copytree(origen_assets, dest / "assets", dirs_exist_ok=True)

    # 2) Fichas JSON (una por producto activo) — de paso, reunimos sus fotos
    prods = app_mod.db.query_products(status="active", parse_specs=True)
    total = len(prods)
    if top:
        prods = prods[:top]
    fichas = dest / "api" / "ficha"
    fichas.mkdir(parents=True, exist_ok=True)
    fotos = set()
    for p in prods:
        fotos.update(p.get("images") or [])
        (fichas / (str(p["id"]) + ".json")).write_text(
            json.dumps(_ficha_json(p), ensure_ascii=False),
            encoding="utf-8")

    # 3) Fotos: solo las referenciadas; copia incremental (2da corrida = rápido)
    copiadas = 0
    if not sin_fotos:
        for nombre in sorted(fotos):
            origen = config.IMAGES_DIR / nombre
            if not origen.is_file():
                continue
            salida = dest / "img" / nombre
            salida.parent.mkdir(parents=True, exist_ok=True)
            try:
                if (not salida.exists()
                        or origen.stat().st_mtime != salida.stat().st_mtime):
                    shutil.copy2(origen, salida)
                    copiadas += 1
            except OSError:
                pass  # archivo raro: no frena la publicación

    # 4) Estáticos del panel de marca (favicon/logos) — la plantilla los pide
    #    en /static/... y el hosting normal también sirve esa carpeta
    for nombre in ("favicon_A.png", "logo.PNG", "logo_A.png"):
        origen = config.BASE_DIR / nombre
        if origen.is_file():
            (dest / "static").mkdir(exist_ok=True)
            shutil.copy2(origen, dest / "static" / nombre)

    # 5) robots.txt mínimo (los buscadores pueden indexar todo el catálogo)
    (dest / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    # 6) favicon.ico en la raíz: el navegador lo pide solo (pestaña nueva,
    #    historial). Es el mismo PNG del logo: se sirve sin dar 404.
    fav = dest / "static" / "favicon_A.png"
    if fav.is_file():
        shutil.copy2(fav, dest / "favicon.ico")

    return {
        "destino": str(dest),
        "productos": len(prods),
        "productos_total": total,
        "fichas": len(prods),
        "fotos_en_catalogo": len(fotos),
        "fotos_copiadas": copiadas,
        "index_bytes": (dest / "index.html").stat().st_size,
        "catalogo_bytes": (dest / "catalogo.html").stat().st_size,
        "paginas_marca": len(paginas_marca),
        "paginas_tipo": len(paginas_tipo),
        "assets": (dest / "assets").is_dir(),
    }


def main():
    ap = argparse.ArgumentParser(description="Exporta el catálogo como página normal")
    ap.add_argument("--destino", default=None, help="carpeta de salida")
    ap.add_argument("--sin-fotos", action="store_true", help="no copiar imágenes")
    ap.add_argument("--top", type=int, default=0, help="exportar solo N productos")
    args = ap.parse_args()
    r = exportar(destino=args.destino, sin_fotos=args.sin_fotos, top=args.top)
    print("Pagina normal generada [OK]")
    print("  destino:      {destino}".format(**r))
    print("  portada:      {index_bytes:,} bytes (index.html, liviana)".format(**r))
    print("  catalogo:     {catalogo_bytes:,} bytes (catalogo.html)".format(**r))
    print("  paginas:      {paginas_marca} de marca + {paginas_tipo} de tipo".format(**r))
    print("  assets:       " + ("si" if r["assets"] else "NO") + " (css/js aparte)")
    print("  productos:    {productos} fichas JSON".format(**r))
    print("  fotos:        {fotos_copiadas} copiadas de {fotos_en_catalogo}".format(**r))


if __name__ == "__main__":
    main()
