"""
Configuración general y lista de marcas.
Para ajustar una marca solo se edita su bloque en BRANDS.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / os.environ.get("CATALOGO_DATA_DIR", "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR = DATA_DIR / "imagenes"
DB_PATH = BASE_DIR / "catalogo.db"
OUTPUT_DIR = BASE_DIR / "salida"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
THEME_PATH = BASE_DIR / "theme.json"
MANUAL_URLS_FILE = BASE_DIR / "urls_manuales.txt"

# --- Comportamiento del extractor ------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
REQUEST_DELAY = 1.5          # segundos entre pedidos a una misma marca (ser amable con el sitio)
TIMEOUT = 25                 # segundos por pedido
RESPECT_ROBOTS = True        # respetar robots.txt
MAX_PRODUCTS_PER_BRAND = 400 # tope de seguridad por corrida

# --- Imágenes ---------------------------------------------------------------
MAX_IMAGES = 4               # imágenes por producto
MIN_IMAGE_SIDE = 250         # descarta íconos / miniaturas (px del lado menor)
MAX_IMAGE_SIDE = 1200        # redimensiona (px del lado mayor)
JPEG_QUALITY = 85

# --- Marcas -----------------------------------------------------------------
# mode:
#   "html"        -> recorre listados y lee cada ficha (JSON-LD / OpenGraph / selectores)
#   "shopify"     -> usa /products.json (si la tienda es Shopify)
#   "woocommerce" -> usa /wp-json/wc/store/v1/products (si la tienda es WooCommerce)
# js=True  -> usa Playwright (navegador real) para páginas que cargan con JavaScript.
# start_urls: listados a recorrer. Puede llevar pistas: {"url":..., "line":..., "gender":...}
# product_link_regex / product_link_selector: cómo reconocer links de fichas en los listados.
# page_param: nombre del parámetro de paginación (ej. "page"); None = una sola página.
# reference_regex: patrón del código de modelo (opcional, mejora la detección).
# selectors: opcional {"name","reference","price","description","images","specs"} (CSS).
#
# IMPORTANTE: las URLs y patrones de abajo son PUNTO DE PARTIDA y hay que
# validarlos marca por marca con:  python run_scrape.py --probar-url <URL> --brand <marca>
BRANDS = [
    {
        "key": "casio",
        "name": "Casio",
        "mode": "html",
        "js": False,
        "base_url": "https://www.casio.com",
        "start_urls": [
            {"url": "https://www.casio.com/latin/watches/gshock/", "line": "G-Shock"},
            {"url": "https://www.casio.com/latin/watches/baby-g/", "line": "Baby-G", "gender": "Dama"},
            {"url": "https://www.casio.com/latin/watches/edifice/", "line": "Edifice"},
            {"url": "https://www.casio.com/latin/watches/pro-trek/", "line": "Protrek"},
            {"url": "https://www.casio.com/latin/watches/classic/"},  # MTP, LTP, deportivos, etc.
        ],
        "product_link_regex": r"/watches/[^/]+/product\.[^/]+/?",
        "product_link_selector": None,
        "page_param": None,
        "max_pages": 1,
        "reference_regex": r"\b([A-Z]{1,5}-?\d{2,5}[A-Z]{0,4}\d{0,2}(?:-\d{1,2}[A-Z]{0,4}\d?)?(?:-[A-Z0-9]{1,4})?)\b",
        "selectors": {},
        "notes": "VERIFICAR rutas de /latin/. Si el sitio bloquea, cargar fichas con urls_manuales.txt",
    },
    {
        "key": "citizen",
        "name": "Citizen",
        "mode": "html",
        "js": False,
        "base_url": "https://www.citizenwatch.com",
        "start_urls": [
            {"url": "https://www.citizenwatch.com/us/en/mens-watches.html", "gender": "Hombre"},
            {"url": "https://www.citizenwatch.com/us/en/womens-watches.html", "gender": "Dama"},
        ],
        "product_link_regex": r"/us/en/[^?#]+\.html$",
        "product_link_selector": None,
        "page_param": "p",
        "max_pages": 10,
        "reference_regex": r"\b([A-Z]{1,3}\d{4}-\d{2}[A-Z]{1,2})\b",
        "selectors": {},
        "notes": "VERIFICAR: sitio de Citizen o de su distribuidor local",
    },
    {
        "key": "orient",
        "name": "Orient",
        "mode": "html",
        "js": False,
        "base_url": "https://www.orientwatchusa.com",
        "start_urls": [
            {"url": "https://www.orientwatchusa.com/collections/mens-watches", "gender": "Hombre"},
            {"url": "https://www.orientwatchusa.com/collections/womens-watches", "gender": "Dama"},
        ],
        "product_link_regex": r"/products/[^/?#]+",
        "product_link_selector": None,
        "page_param": "page",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "VERIFICAR. Si es Shopify se puede cambiar a mode='shopify'",
    },
    {
        "key": "tommy",
        "name": "Tommy Hilfiger",
        "mode": "html",
        "js": False,
        "base_url": "https://www.example.com",
        "start_urls": [],
        "product_link_regex": None,
        "product_link_selector": None,
        "page_param": "page",
        "max_pages": 10,
        "reference_regex": r"\b(\d{7})\b",
        "selectors": {},
        "notes": "COMPLETAR: pegar aquí el sitio del distribuidor o usar urls_manuales.txt",
    },
    {
        "key": "seiko",
        "name": "Seiko",
        "mode": "html",
        "js": False,
        "base_url": "https://www.seikowatches.com",
        "start_urls": [
            {"url": "https://www.seikowatches.com/us-en/products/seiko/", "line": "Seiko"},
        ],
        "product_link_regex": r"/us-en/products/[^/]+/[^/]+/[A-Za-z0-9]+/?$",
        "product_link_selector": None,
        "page_param": None,
        "max_pages": 1,
        "reference_regex": r"\b(S[A-Z]{2,4}\d{2,3}[A-Z]\d?)\b",
        "selectors": {},
        "notes": "VERIFICAR rutas",
    },
    {
        "key": "anneklein",
        "name": "Anne Klein",
        "mode": "html",
        "js": False,
        "base_url": "https://www.anneklein.com",
        "start_urls": [
            {"url": "https://www.anneklein.com/collections/watches", "gender": "Dama"},
        ],
        "product_link_regex": r"/products/[^/?#]+",
        "product_link_selector": None,
        "page_param": "page",
        "max_pages": 10,
        "reference_regex": r"\b(\d{4}[A-Z]{4,6})\b",
        "selectors": {},
        "notes": "VERIFICAR. Si es Shopify se puede cambiar a mode='shopify'",
    },
    {
        "key": "invicta",
        "name": "Invicta",
        "mode": "html",
        "js": False,
        "base_url": "https://www.invictawatch.com",
        "start_urls": [
            {"url": "https://www.invictawatch.com/mens-watches", "gender": "Hombre"},
            {"url": "https://www.invictawatch.com/womens-watches", "gender": "Dama"},
        ],
        "product_link_regex": r"\.html$",
        "product_link_selector": None,
        "page_param": "p",
        "max_pages": 10,
        "reference_regex": r"\b(\d{4,6})\b",
        "selectors": {},
        "notes": "VERIFICAR",
    },
    {
        "key": "qyq",
        "name": "Q&Q",
        "mode": "html",
        "js": False,
        "base_url": "https://www.example.com",
        "start_urls": [],
        "product_link_regex": None,
        "product_link_selector": None,
        "page_param": "page",
        "max_pages": 10,
        "reference_regex": r"\b([A-Z]{1,3}\d{2,3}[A-Z]\d{3}[A-Z])\b",
        "selectors": {},
        "notes": "COMPLETAR: sitio del distribuidor o urls_manuales.txt",
    },
    # --- Proveedores locales (Paraguay) ----------------------------------------
    {
        "key": "tdr_casio",
        "name": "Tiempo de Relojes (Casio)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/categorias/g-shock-3.html", "line": "G-Shock"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/baby-g-4.html", "line": "Baby-G", "gender": "Dama"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/edifice-5.html", "line": "Edifice"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/protrek-6.html", "line": "ProTrek"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/vintage-7.html", "line": "Vintage"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/regular-caballero-34.html", "line": "MTP Caballero", "gender": "Hombre"},
            {"url": "https://www.tiempoderelojes.com.py/categorias/regular-dama-35.html", "line": "LTP Dama", "gender": "Dama"},
        ],
        "product_link_regex": r"/productos/reloj-casio-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 15,
        "reference_regex": r"\b([A-Z]{1,5}-?\d{2,5}[A-Z]{0,4}\d{0,2}(?:-\d{1,2}[A-Z]{0,4}\d?)?(?:-[A-Z0-9]{1,4})?)\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. Tiene Casio G-Shock, Baby-G, Edifice, Protrek, Vintage.",
    },
    {
        "key": "tdr_tommy",
        "name": "Tiempo de Relojes (Tommy)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/tommy-hilfiger-1.html", "line": "Tommy Hilfiger"},
        ],
        "product_link_regex": r"/productos/reloj-tommy-hilfiger-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": r"\b(\d{7})\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. Tommy Hilfiger.",
    },
    {
        "key": "sosa_tissot",
        "name": "Joyería Sosa (Tissot)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.joyeriasosa.com.py",
        "start_urls": [
            {"url": "https://www.joyeriasosa.com.py/productos/hombres", "gender": "Hombre"},
            {"url": "https://www.joyeriasosa.com.py/productos/mujeres", "gender": "Dama"},
        ],
        "product_link_regex": r"/producto/\d+/[^/?#]+",
        "product_link_selector": "a[href*='/producto/']",
        "page_param": None,
        "max_pages": 1,
        "reference_regex": r"\b([A-Z]{2,6}[\s+][A-Z0-9-]{2,20})\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. Tissot, Michael Kors, Fossil.",
    },
    # --- Tiempo de Relojes: todas las marcas ---
    {
        "key": "tdr_armani",
        "name": "Tiempo de Relojes (Armani Exchange)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/armani-exchange-7.html", "line": "Armani Exchange"},
        ],
        "product_link_regex": r"/productos/reloj-armani-exchange-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": r"\b(AX\d{3,5})\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. Armani Exchange.",
    },
    {
        "key": "tdr_bulova",
        "name": "Tiempo de Relojes (Bulova)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/bulova-3.html", "line": "Bulova"},
        ],
        "product_link_regex": r"/productos/reloj-bulova-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Bulova.",
    },
    {
        "key": "tdr_calvinklein",
        "name": "Tiempo de Relojes (Calvin Klein)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/calvin-klein-16.html", "line": "Calvin Klein"},
        ],
        "product_link_regex": r"/productos/reloj-calvin-klein-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Calvin Klein.",
    },
    {
        "key": "tdr_caterpillar",
        "name": "Tiempo de Relojes (Caterpillar)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/caterpillar-11.html", "line": "Caterpillar", "gender": "Hombre"},
        ],
        "product_link_regex": r"/productos/reloj-caterpillar-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Caterpillar.",
    },
    {
        "key": "tdr_diesel",
        "name": "Tiempo de Relojes (Diesel)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/diesel-9.html", "line": "Diesel", "gender": "Hombre"},
        ],
        "product_link_regex": r"/productos/reloj-diesel-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Diesel.",
    },
    {
        "key": "tdr_fossil",
        "name": "Tiempo de Relojes (Fossil)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/fossil-8.html", "line": "Fossil"},
        ],
        "product_link_regex": r"/productos/reloj-fossil-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Fossil.",
    },
    {
        "key": "tdr_hugoboss",
        "name": "Tiempo de Relojes (Hugo Boss)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/hugo-boss-4.html", "line": "Hugo Boss", "gender": "Hombre"},
        ],
        "product_link_regex": r"/productos/reloj-hugo-boss-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Hugo Boss.",
    },
    {
        "key": "tdr_lacoste",
        "name": "Tiempo de Relojes (Lacoste)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/lacoste-2.html", "line": "Lacoste"},
        ],
        "product_link_regex": r"/productos/reloj-lacoste-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Lacoste.",
    },
    {
        "key": "tdr_michaelkors",
        "name": "Tiempo de Relojes (Michael Kors)",
        "mode": "html",
        "js": False,
        "base_url": "https://www.tiempoderelojes.com.py",
        "start_urls": [
            {"url": "https://www.tiempoderelojes.com.py/marcas/michael-kors-10.html", "line": "Michael Kors"},
        ],
        "product_link_regex": r"/productos/reloj-michael-kors-[^/?#]+\.html",
        "product_link_selector": None,
        "page_param": "path",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Michael Kors.",
    },
    # --- Joyería Domínguez (proveedor manual - Instagram) ---
    {
        "key": "dom_relojes",
        "name": "Joyería Domínguez (Relojes)",
        "mode": "html",
        "js": False,
        "base_url": "",
        "start_urls": [],
        "product_link_regex": None,
        "product_link_selector": None,
        "page_param": None,
        "max_pages": 1,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor manual. Joyería Domínguez - Instagram @joyeriadominguez. Cargar manualmente con fotos de Instagram.",
    },
    {
        "key": "dom_joyeria",
        "name": "Joyería Domínguez (Joyería)",
        "mode": "html",
        "js": False,
        "base_url": "",
        "start_urls": [],
        "product_link_regex": None,
        "product_link_selector": None,
        "page_param": None,
        "max_pages": 1,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor manual. Anillos Oro, Oro Blanco 18k, Platería, Alpaca, Dijes Plata 925, Medallas.",
    },
    {
        "key": "dom_accesorios",
        "name": "Joyería Domínguez (Accesorios)",
        "mode": "html",
        "js": False,
        "base_url": "",
        "start_urls": [],
        "product_link_regex": None,
        "product_link_selector": None,
        "page_param": None,
        "max_pages": 1,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor manual. Bolígrafos Parker, Aros para Bebé, Nombres personalizados.",
    },
    # --- Jean Vernier Paraguay (WooCommerce) ---
    {
        "key": "vernier",
        "name": "Jean Vernier Paraguay",
        "mode": "woocommerce",
        "js": False,
        "base_url": "https://www.vernier.com.py",
        "start_urls": [
            {"url": "https://www.vernier.com.py/product-category/accesorios/relojes/", "line": "Relojes"},
        ],
        "product_link_regex": r"/producto/[^/?#]+",
        "product_link_selector": "a.woocommerce-LoopProduct-link",
        "page_param": "paged",
        "max_pages": 10,
        "reference_regex": r"\b([A-Z]{1,5}-?\d{2,5}[A-Z]{0,4})\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. WooCommerce. Jean Vernier.",
    },
    # --- Zarate Watches ---
    {
        "key": "zarate",
        "name": "Zarate Watches",
        "mode": "html",
        "js": False,
        "base_url": "https://zaratewatches.com",
        "start_urls": [
            {"url": "https://zaratewatches.com/product-category/relojes-casio/", "line": "Casio"},
            {"url": "https://zaratewatches.com/product-category/relojes-casio-digitales/", "line": "Casio Digital"},
            {"url": "https://zaratewatches.com/product-category/relojes-casio-g-shock/", "line": "G-Shock"},
            {"url": "https://zaratewatches.com/product-category/relojes-casio-femeninos/", "line": "Casio Dama", "gender": "Dama"},
        ],
        "product_link_regex": r"/producto/[^/?#]+",
        "product_link_selector": "a.woocommerce-LoopProduct-link",
        "page_param": "paged",
        "max_pages": 10,
        "reference_regex": r"\b([A-Z]{1,5}-?\d{2,5}[A-Z]{0,4})\b",
        "selectors": {},
        "notes": "Proveedor local Paraguay. Casio, Skmei.",
    },
    # --- AM Relojes ---
    {
        "key": "amrelojes",
        "name": "AM Relojes",
        "mode": "html",
        "js": False,
        "base_url": "https://amrelojes.com.py",
        "start_urls": [
            {"url": "https://amrelojes.com.py/categoria-producto/casio/", "line": "Casio"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio-g-shock/", "line": "G-Shock"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio-edifice/", "line": "Edifice"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio/casio-damas/", "line": "Casio Dama", "gender": "Dama"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio/casio-deportivos/", "line": "Casio Deportivo"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio/casio-vintage/", "line": "Casio Vintage"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio/casio-para-caballeros-en-mallas-de-metal/", "line": "Casio Metal", "gender": "Hombre"},
            {"url": "https://amrelojes.com.py/categoria-producto/casio/casio-malla-de-cuero-para-caballeros/", "line": "Casio Cuero", "gender": "Hombre"},
            {"url": "https://amrelojes.com.py/categoria-producto/tommy-hilfiger/", "line": "Tommy Hilfiger"},
            {"url": "https://amrelojes.com.py/categoria-producto/seiko/", "line": "Seiko"},
            {"url": "https://amrelojes.com.py/categoria-producto/skmei-para-damas-unisex/", "line": "Skmei Dama", "gender": "Dama"},
            {"url": "https://amrelojes.com.py/categoria-producto/skmei-mallas-de-metal-caballeros/", "line": "Skmei Metal", "gender": "Hombre"},
            {"url": "https://amrelojes.com.py/categoria-producto/relojes-deportivos-skmei/", "line": "Skmei Deportivo"},
            {"url": "https://amrelojes.com.py/categoria-producto/relojes-qq-y-curren-para-damas/", "line": "Q&Q Dama", "gender": "Dama"},
            {"url": "https://amrelojes.com.py/categoria-producto/relojes-qq-para-caballeros/", "line": "Q&Q Caballero", "gender": "Hombre"},
            {"url": "https://amrelojes.com.py/categoria-producto/curren/", "line": "Curren"},
            {"url": "https://amrelojes.com.py/categoria-producto/naviforce/", "line": "NaviForce"},
            {"url": "https://amrelojes.com.py/categoria-producto/fossil/", "line": "Fossil"},
            {"url": "https://amrelojes.com.py/categoria-producto/hummer/", "line": "Hummer"},
        ],
        "product_link_regex": r"/producto/[^/?#]+",
        "product_link_selector": "a.woocommerce-LoopProduct-link",
        "page_param": "paged",
        "max_pages": 10,
        "reference_regex": None,
        "selectors": {},
        "notes": "Proveedor local Paraguay. Casio (212), Tommy, Seiko, Skmei, Q&Q, Curren, NaviForce, Fossil, Hummer.",
    },

    # --- Nuevas fuentes (agregadas manualmente) ---
    {
        "key": "caterpillar",
        "name": "Caterpillar",
        "mode": "html",
        "base_url": "https://shopcaterpillar.com",
        "start_urls": [
            {"url": "https://shopcaterpillar.com/es/collections/watches", "line": "Caterpillar"},
        ],
        "notes": "Caterpillar watches. Shopify store.",
    },
    {
        "key": "festina",
        "name": "Festina",
        "mode": "html",
        "base_url": "https://festina.com",
        "start_urls": [
            {"url": "https://festina.com/es-ES", "line": "Festina"},
        ],
        "notes": "Festina oficial. Relojes.",
    },
    {
        "key": "nissei_relojes",
        "name": "Nissei Relojes",
        "mode": "html",
        "base_url": "https://nissei.com",
        "start_urls": [
            {"url": "https://nissei.com/py/ropas-calzados-accesorios/unisex/relojes-y-accesorios", "line": "General"},
        ],
        "notes": "Nissei Paraguay. Relojes y accesorios.",
    },
    {
        "key": "cellshop",
        "name": "Cellshop",
        "mode": "html",
        "base_url": "https://cellshop.com.py",
        "start_urls": [
            {"url": "https://cellshop.com.py/catalogsearch/result/?q=reloj", "line": "General"},
        ],
        "notes": "Cellshop Paraguay. Busqueda de relojes.",
    },
    {
        "key": "adidas",
        "name": "Adidas",
        "mode": "html",
        "base_url": "https://www.adidas.com.py",
        "start_urls": [],
        "notes": "Adidas relojes. Completar URLs.",
    },
    {
        "key": "victorino",
        "name": "Victorino",
        "mode": "html",
        "base_url": "",
        "start_urls": [],
        "notes": "Victorino. Completar URLs.",
    },
    {
        "key": "lentes",
        "name": "Lentes",
        "mode": "html",
        "base_url": "",
        "start_urls": [],
        "notes": "Lentes / Armazon / Lentes recetados. Completar URLs.",
    },
    {
        "key": "perfumes",
        "name": "Perfumes",
        "mode": "html",
        "base_url": "",
        "start_urls": [],
        "notes": "Perfumes. Completar URLs.",
    },

    # --- Tiendas paraguayas de relojes (agregadas) ---
    {
        "key": "casa_joia",
        "product_link_regex": ".*/product\-page/.*",
        "name": "Casa Joia",
        "mode": "html",
        "base_url": "https://www.casajoia.com.py",
        "start_urls": [
            {"url": "https://www.casajoia.com.py/casio", "line": "Casio"},
            {"url": "https://www.casajoia.com.py/qyq", "line": "Q&Q"},
            {"url": "https://www.casajoia.com.py/curren", "line": "Curren"},
            {"url": "https://www.casajoia.com.py/navi-force", "line": "NaviForce"},
            {"url": "https://www.casajoia.com.py/invicta", "line": "Invicta"},
            {"url": "https://www.casajoia.com.py/relojes", "line": "General"},
        ],
        "notes": "Casa Joia Paraguay. Casio, Q&Q, Curren, NaviForce, Invicta, Skmei.",
    },
    {
        "key": "tupi",
        "js": True,
        "product_link_regex": ".*/producto/.*",
        "name": "TUPI",
        "mode": "html",
        "base_url": "https://www.tupi.com.py",
        "start_urls": [
            {"url": "https://www.tupi.com.py/marca/243/CASIO", "line": "Casio"},
            {"url": "https://www.tupi.com.py/marca/1265/Q&Q", "line": "Q&Q"},
        ],
        "notes": "TUPI S.A. Paraguay. Casio, Q&Q.",
    },
    {
        "key": "joyeria_gya",
        "product_link_regex": ".*/reloj\-.*",
        "name": "Joyería G&A",
        "mode": "html",
        "base_url": "https://joyeriagya.com",
        "start_urls": [
            {"url": "https://joyeriagya.com/relojes/", "line": "General"},
            {"url": "https://joyeriagya.com/relojes/page/2/", "line": "General"},
            {"url": "https://joyeriagya.com/relojes/page/3/", "line": "General"},
            {"url": "https://joyeriagya.com/relojes/page/4/", "line": "General"},
            {"url": "https://joyeriagya.com/relojes/page/5/", "line": "General"},
            {"url": "https://joyeriagya.com/marca/qyq/", "line": "Q&Q"},
            {"url": "https://joyeriagya.com/marca/casio/", "line": "Casio"},
            {"url": "https://joyeriagya.com/marca/seiko/", "line": "Seiko"},
        ],
        "notes": "Joyería G&A Paraguay. Casio, Seiko, Q&Q.",
    },
    {
        "key": "tienda_naranja",
        "product_link_regex": ".*\.html.*",
        "name": "Tienda Naranja",
        "mode": "html",
        "base_url": "https://tiendanaranja.com.py",
        "start_urls": [
            {"url": "https://tiendanaranja.com.py/moda/relojes.html", "line": "General"},
        ],
        "notes": "Tienda Naranja Paraguay. Casio, Tiempo de Relojes.",
    },
    {
        "key": "myshuzz",
        "product_link_regex": ".*/p.*",
        "name": "My Shuzz",
        "mode": "html",
        "base_url": "https://www.myshuzz.com.py",
        "start_urls": [
            {"url": "https://www.myshuzz.com.py/moda/relojes", "line": "General"},
            {"url": "https://www.myshuzz.com.py/moda/relojes/relojes-formales", "line": "Formales"},
        ],
        "notes": "My Shuzz Paraguay. Victorinox relojes.",
    },
    {
        "key": "asuncion_joyas",
        "product_link_regex": ".*/producto/.*",
        "name": "Asunción Joyas",
        "mode": "html",
        "base_url": "https://asuncionjoyas.com.py",
        "start_urls": [
            {"url": "https://asuncionjoyas.com.py/producto-categoria/relojes/", "line": "General"},
        ],
        "notes": "Asunción Joyas Paraguay. Q&Q relojes.",
    },
    {
        "key": "joyeria_sosa",
        "product_link_regex": ".*/producto/.*",
        "name": "Joyería Sosa",
        "mode": "html",
        "base_url": "https://www.joyeriasosa.com.py",
        "start_urls": [
            {"url": "https://www.joyeriasosa.com.py/product-category/relojes/", "line": "General"},
        ],
        "notes": "Joyería Sosa Paraguay. Victorinox, Tissot.",
    },
    # --- Lentes y Armazones ---
    {
        "key": "arar_optica",
        "product_link_regex": ".*/producto/.*",
        "name": "Arar Óptica",
        "mode": "html",
        "base_url": "https://www.araroptica.com.py",
        "start_urls": [
            {"url": "https://www.araroptica.com.py/categoria/8/armazones", "line": "Armazones"},
        ],
        "notes": "Arar Óptica Paraguay. Armazones y lentes.",
    },
    {
        "key": "optica_santalucia",
        "name": "Óptica Santa Lucía",
        "mode": "html",
        "base_url": "https://www.opticasantalucia.com.py",
        "start_urls": [
            {"url": "https://www.opticasantalucia.com.py/categoria/armazones", "line": "Armazones"},
        ],
        "notes": "Óptica Santa Lucía Paraguay. Lentes recetados.",
    },
    {
        "key": "optimovil",
        "product_link_regex": ".*/producto/.*",
        "name": "Optimovil",
        "mode": "html",
        "base_url": "https://www.optimovil.com.py",
        "start_urls": [
            {"url": "https://www.optimovil.com.py/categoria-producto/armazones/", "line": "Armazones"},
        ],
        "notes": "Optimovil Paraguay. Armazones.",
    },
    {
        "key": "infinite_eyewear",
        "name": "Infinite Eyewear",
        "mode": "html",
        "base_url": "https://infiniteyewear.com.py",
        "start_urls": [
            {"url": "https://infiniteyewear.com.py/collections/armazones", "line": "Armazones"},
        ],
        "notes": "Infinite Eyewear Paraguay. Armazones Shopify.",
    },
    {
        "key": "opticavision",
        "product_link_regex": ".*/producto/.*",
        "name": "Óptica Visión",
        "mode": "html",
        "base_url": "https://opticavision.com.py",
        "start_urls": [
            {"url": "https://opticavision.com.py/product-category/tipos/armazon/", "line": "Armazones"},
        ],
        "notes": "Óptica Visión Paraguay. Armazones.",
    },
    {
        "key": "ronan",
        "name": "Ronan Eyewear",
        "mode": "html",
        "base_url": "https://ronan.com.py",
        "start_urls": [
            {"url": "https://ronan.com.py/collections/todos", "line": "Lentes"},
        ],
        "notes": "Ronan Eyewear Paraguay. Lentes.",
    },
    {
        "key": "valemar",
        "name": "Valemar",
        "mode": "html",
        "base_url": "https://valemar.com.py",
        "start_urls": [
            {"url": "https://valemar.com.py/categoria-producto/mujeres/", "line": "Dama"},
            {"url": "https://valemar.com.py/categoria-producto/hombres/", "line": "Caballero"},
        ],
        "notes": "Valemar Paraguay. Armazones.",
    },
    # --- Perfumes ---
    {
        "key": "punto_tienda",
        "product_link_regex": ".*/producto/.*",
        "name": "Punto Tienda",
        "mode": "html",
        "base_url": "https://puntotienda.com.py",
        "start_urls": [
            {"url": "https://puntotienda.com.py/categoria-producto/perfumes/", "line": "Perfumes"},
        ],
        "notes": "Punto Tienda Paraguay. Perfumes originales.",
    },
    {
        "key": "shopping_china_perfumes",
        "name": "Shopping China Perfumes",
        "mode": "html",
        "base_url": "https://www.shoppingchina.com.py",
        "start_urls": [
            {"url": "https://www.shoppingchina.com.py/perfumeria", "line": "Perfumes"},
        ],
        "notes": "Shopping China Paraguay. Perfumería.",
    },
    {
        "key": "champs",
        "name": "Champs Elysees",
        "mode": "html",
        "base_url": "https://www.champs.com.py",
        "start_urls": [
            {"url": "https://www.champs.com.py/categoria/perfumes/", "line": "Perfumes"},
        ],
        "notes": "Champs Elysees Paraguay. Perfumes.",
    },
    {
        "key": "lual_perfumeria",
        "product_link_regex": ".*/producto/.*",
        "name": "Lual Perfumería",
        "mode": "html",
        "base_url": "https://lualperfumeria.com.py",
        "start_urls": [
            {"url": "https://lualperfumeria.com.py/product-category/perfumes/", "line": "Perfumes"},
        ],
        "notes": "Lual Perfumería Paraguay. Perfumes.",
    },
    {
        "key": "laperfumeria",
        "product_link_regex": ".*/producto/.*",
        "name": "La Perfumería",
        "mode": "html",
        "base_url": "https://laperfumeria.com.py",
        "start_urls": [
            {"url": "https://laperfumeria.com.py/tienda/", "line": "Perfumes"},
        ],
        "notes": "La Perfumería Paraguay. Perfumes.",
    },
]

BRAND_BY_KEY = {b["key"]: b for b in BRANDS}
BRAND_ORDER = [b["name"] for b in BRANDS]

# Orden de las líneas dentro de cada marca en el PDF (las no listadas van al final)
LINE_ORDER = ["G-Shock", "Baby-G", "Edifice", "MTP", "LTP", "Protrek", "Sheen", "Casio Dama", "Deportivo"]
