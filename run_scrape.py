"""
Uso:
  python run_scrape.py --list                                 lista de marcas
  python run_scrape.py --probar-url URL --brand casio         prueba UNA ficha (diagnóstico)
  python run_scrape.py --brand casio --limit 5                prueba corta (5 productos)
  python run_scrape.py --brand casio                          una marca completa
  python run_scrape.py --all                                  todas las marcas, una tras otra
  python run_scrape.py --manual                               fichas de urls_manuales.txt
Opciones: --sin-imagenes  --refrescar
"""
import argparse
import sys

import config
import db
import scraper


def read_manual_urls():
    """urls_manuales.txt: una por línea ->  marca  URL   (# para comentarios)"""
    by_brand = {}
    if not config.MANUAL_URLS_FILE.exists():
        print(f"No existe {config.MANUAL_URLS_FILE.name}")
        return by_brand
    for line in config.MANUAL_URLS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            print(f"Línea ignorada (formato 'marca URL'): {line}")
            continue
        by_brand.setdefault(parts[0].lower(), {})[parts[1].strip()] = {}
    return by_brand


def main():
    ap = argparse.ArgumentParser(description="Extractor de catálogo de relojes")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--brand")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--manual", action="store_true")
    ap.add_argument("--probar-url")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sin-imagenes", action="store_true")
    ap.add_argument("--refrescar", action="store_true", help="volver a leer fichas ya guardadas")
    a = ap.parse_args()
    db.init_db()

    if a.list:
        for b in config.BRANDS:
            n = len(b.get("start_urls", [])) + len(b.get("sitemaps", []))
            print(f"  {b['key']:10} {b['name']:16} modo={b.get('mode', 'html'):11} fuentes={n}  {b.get('notes', '')}")
        return

    if a.probar_url:
        cfg = config.BRAND_BY_KEY.get((a.brand or "").lower(), scraper.DEFAULT_CFG)
        scraper.probe_url(a.probar_url, cfg)
        return

    if a.manual:
        for key, urls in read_manual_urls().items():
            cfg = config.BRAND_BY_KEY.get(key)
            if not cfg:
                print(f"Marca desconocida en urls_manuales.txt: {key}")
                continue
            scraper.scrape_brand(cfg, limit=a.limit, download=not a.sin_imagenes,
                                 refresh=a.refrescar, urls=urls)
        return

    if a.all:
        targets = config.BRANDS
    elif a.brand:
        cfg = config.BRAND_BY_KEY.get(a.brand.lower())
        if not cfg:
            sys.exit(f"Marca '{a.brand}' no existe. Usar --list.")
        targets = [cfg]
    else:
        ap.print_help()
        return

    for cfg in targets:
        if cfg.get("mode", "html") == "html" and not cfg.get("start_urls") and not cfg.get("sitemaps"):
            print(f"\n=== {cfg['name']}: sin start_urls (completar en config.py o usar --manual) ===")
            continue
        scraper.scrape_brand(cfg, limit=a.limit, download=not a.sin_imagenes, refresh=a.refrescar)


if __name__ == "__main__":
    main()
