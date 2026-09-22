"""
Extractor de productos.
Orden de lectura en cada ficha: selectores propios > JSON-LD (schema.org) > OpenGraph > HTML.
"""
import gzip
import json
import re
import time
import urllib.robotparser
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

import config
import db
from classify import classify
from images import download_images

DEFAULT_CFG = {"key": "otra", "name": "Otra", "mode": "html", "js": False,
               "reference_regex": None, "selectors": {}}


# =============================================================================
# Descarga de páginas
# =============================================================================
class Fetcher:
    def __init__(self, js=False, delay=None):
        self.js = js
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        })
        self._robots = {}
        self._last = 0.0
        self._pw = self._browser = self._context = None

    # --- robots.txt ---------------------------------------------------------
    def allowed(self, url):
        if not config.RESPECT_ROBOTS:
            return True
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(root)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(root + "/robots.txt", timeout=config.TIMEOUT)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[root] = rp
        return rp.can_fetch(config.USER_AGENT, url)

    def _wait(self):
        gap = time.time() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.time()

    # --- pedidos --------------------------------------------------------------
    def get(self, url, as_json=False):
        if not self.allowed(url):
            print(f"   [robots.txt no permite] {url}")
            return None
        self._wait()
        if self.js and not as_json:
            return self._get_js(url)
        try:
            r = self.session.get(url, timeout=config.TIMEOUT)
        except requests.RequestException as e:
            print(f"   [error de red] {url}: {e}")
            return None
        if r.status_code != 200:
            print(f"   [HTTP {r.status_code}] {url}")
            return None
        if as_json:
            try:
                return r.json()
            except ValueError:
                return None
        return r.text

    def get_bytes(self, url):
        if not self.allowed(url):
            return None
        self._wait()
        try:
            r = self.session.get(url, timeout=config.TIMEOUT)
            return r.content if r.status_code == 200 else None
        except requests.RequestException:
            return None

    def _get_js(self, url):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise SystemExit(
                "Esta marca usa js=True. Instalar con:\n"
                "   pip install playwright\n   playwright install chromium")
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._context = self._browser.new_context(user_agent=config.USER_AGENT, locale="es-419")
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=config.TIMEOUT * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            last_h = 0
            for _ in range(10):                      # scroll para listados con carga progresiva
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(700)
                h = page.evaluate("document.body.scrollHeight")
                if h == last_h:
                    break
                last_h = h
            return page.content()
        except Exception as e:
            print(f"   [error navegador] {url}: {e}")
            return None
        finally:
            page.close()

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()


# =============================================================================
# Utilidades de lectura
# =============================================================================
def clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


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
    except ValueError:
        return None


def html_to_text(html, limit=1200):
    if not html:
        return ""
    text = BeautifulSoup(str(html), "lxml").get_text(" ", strip=True)
    return clean(text)[:limit]


def with_page(url, param, n):
    if not param or n <= 1:
        return url
    # TDR-style: path-based pagination (/categorias/g-shock-3/2)
    if param == "path":
        base = url.rstrip("/").replace(".html", "")
        return f"{base}/{n}"
    # Query parameter style (?page=2)
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query))
    q[param] = str(n)
    return urlunparse(parts._replace(query=urlencode(q)))


def _flatten_ld(node):
    if isinstance(node, list):
        for n in node:
            yield from _flatten_ld(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement", "item"):
            if key in node:
                yield from _flatten_ld(node[key])


def find_jsonld_product(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
            except ValueError:
                continue
        for node in _flatten_ld(data):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Product" in types or "ProductGroup" in types:
                return node
    return None


def _ld_images(prod):
    img = (prod or {}).get("image")
    out = []
    if isinstance(img, str):
        out.append(img)
    elif isinstance(img, dict):
        out.append(img.get("url") or img.get("contentUrl"))
    elif isinstance(img, list):
        for i in img:
            out.append(i if isinstance(i, str) else (i.get("url") or i.get("contentUrl")))
    return [i for i in out if i]


def _ld_offer(prod):
    offers = (prod or {}).get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None, None
    price = offers.get("price") or offers.get("lowPrice")
    if price is None and isinstance(offers.get("priceSpecification"), dict):
        price = offers["priceSpecification"].get("price")
    return parse_price(price), offers.get("priceCurrency")


def _meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return clean(tag["content"])
    return None


def _img_url(tag, base):
    """URL de imagen más grande de un <img> (maneja lazy-load y srcset)."""
    if tag.name == "a":
        href = tag.get("href", "")
        return urljoin(base, href) if re.search(r"\.(jpe?g|png|webp)(\?|$)", href, re.I) else None
    for attr in ("data-zoom-image", "data-large", "data-original", "data-src", "data-lazy-src"):
        if tag.get(attr):
            return urljoin(base, tag[attr].split()[0])
    srcset = tag.get("srcset") or tag.get("data-srcset")
    if srcset:
        best, best_w = None, -1
        for part in srcset.split(","):
            bits = part.strip().split()
            if not bits:
                continue
            w = 0
            if len(bits) > 1:
                m = re.match(r"(\d+(?:\.\d+)?)", bits[1])
                w = float(m.group(1)) if m else 0
            if w >= best_w:
                best, best_w = bits[0], w
        if best:
            return urljoin(base, best)
    if tag.get("src"):
        return urljoin(base, tag["src"])
    return None


BAD_IMG = re.compile(r"(logo|icon|sprite|placeholder|loading|banner|flag|badge|\.svg|\.gif|data:image)", re.I)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def collect_images(soup, base, sel, ld, reference):
    urls = []
    if sel:
        for el in soup.select(sel):
            nodes = [el] if el.name in ("img", "a") else el.find_all("img")
            urls += [_img_url(n, base) for n in nodes]
    urls += [urljoin(base, u) for u in _ld_images(ld)]
    ref_n = norm(reference)
    if ref_n:
        for img in soup.find_all("img"):
            u = _img_url(img, base)
            if u and ref_n in norm(u):
                urls.append(u)
    og = _meta(soup, "og:image", "twitter:image")
    if og:
        urls.append(urljoin(base, og))
    out, seen = [], set()
    for u in urls:
        if not u or BAD_IMG.search(u):
            continue
        key = u.split("?")[0]
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def extract_specs(soup, selector=None):
    specs = {}

    def add(k, v):
        k, v = clean(k).rstrip(":"), clean(v)
        if 1 < len(k) <= 40 and 0 < len(v) <= 140 and k not in specs and len(specs) < 25:
            specs[k] = v

    scopes = soup.select(selector) if selector else [soup]
    for sc in scopes:
        for tr in sc.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) == 2:
                add(cells[0].get_text(" "), cells[1].get_text(" "))
        for dl in sc.find_all("dl"):
            for dt in dl.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    add(dt.get_text(" "), dd.get_text(" "))
        for li in sc.find_all("li"):
            holder = " ".join(" ".join(p.get("class", [])) + " " + (p.get("id") or "")
                              for p in li.parents if hasattr(p, "get"))
            if selector or re.search(r"spec|feature|detail|caracter|ficha|attribute", holder, re.I):
                txt = li.get_text(" ")
                if ":" in txt:
                    k, _, v = txt.partition(":")
                    add(k, v)
    return specs


LABEL_REF = re.compile(r"^(ref(erencia)?\.?|modelo|model|sku|c[oó]digo|code|item|style|part number)\b", re.I)


def generic_reference(text):
    for tok in re.findall(r"[A-Z0-9][A-Z0-9\-/.]{3,}", text or ""):
        if re.search(r"\d", tok):
            return tok.strip("-/.")
    return None


def find_reference(cfg, sel_val, ld, name, title, specs, url):
    if sel_val:
        return clean(sel_val).upper()
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"^product\.", "", slug)
    sku = str((ld or {}).get("sku") or "")
    mpn = str((ld or {}).get("mpn") or "")
    rx = cfg.get("reference_regex")
    if rx:
        for cand in (sku, mpn, name, title, slug):
            m = re.search(rx, (cand or "").upper())
            if m:
                return (m.group(1) if m.groups() else m.group(0)).upper()
    for cand in (mpn, sku):
        if cand and len(cand) <= 30:
            return cand.strip().upper()
    for k, v in specs.items():
        if LABEL_REF.match(k) and len(v) <= 30:
            return v.upper()
    ref = generic_reference(name) or generic_reference(title)
    if ref:
        return ref.upper()
    return slug.upper() if slug else None


# =============================================================================
# Lectura de una ficha de producto (HTML)
# =============================================================================
def parse_product_page(html, url, cfg):
    soup = BeautifulSoup(html, "lxml")
    sels = cfg.get("selectors") or {}

    def sel_text(key):
        if sels.get(key):
            el = soup.select_one(sels[key])
            return clean(el.get_text(" ")) if el else None
        return None

    ld = find_jsonld_product(soup)
    og_title = _meta(soup, "og:title")
    h1 = soup.find("h1")

    name = (sel_text("name") or (clean(ld.get("name")) if ld and ld.get("name") else None)
            or og_title or (clean(h1.get_text(" ")) if h1 else None))
    title_tag = clean(soup.title.get_text()) if soup.title else ""
    specs = extract_specs(soup, sels.get("specs"))
    reference = find_reference(cfg, sel_text("reference"), ld, name, title_tag, specs, url)

    price, currency = _ld_offer(ld)
    if sels.get("price"):
        price = parse_price(sel_text("price")) or price
    if price is None:
        price = parse_price(_meta(soup, "product:price:amount", "og:price:amount"))
        currency = currency or _meta(soup, "product:price:currency", "og:price:currency")

    desc = sel_text("description") or (html_to_text(ld.get("description")) if ld and ld.get("description") else None) \
        or _meta(soup, "og:description", "description") or ""

    images = collect_images(soup, url, sels.get("images"), ld, reference)

    if not name or not reference or not (images or price is not None):
        return None
    return {
        "name": name, "reference": reference, "description": desc[:1200], "specs": specs,
        "price": price, "currency": currency, "image_urls": images, "url": url,
        "fuentes": {"json_ld": bool(ld), "og": bool(og_title)},
    }


# =============================================================================
# Descubrir fichas
# =============================================================================
def extract_links(soup, page_url, rx, selector):
    host = urlparse(page_url).netloc.replace("www.", "")
    els = soup.select(selector) if selector else soup.find_all("a", href=True)
    out = []
    for el in els:
        href = el.get("href")
        if not href or href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        absolute = urljoin(page_url, href).split("#")[0]
        if urlparse(absolute).netloc.replace("www.", "") != host:
            continue
        if rx and not rx.search(absolute):
            continue
        out.append(absolute)
    return list(dict.fromkeys(out))


def sitemap_urls(fetcher, url, rx, depth=0):
    raw = fetcher.get_bytes(url)
    if not raw:
        return []
    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", raw.decode("utf-8", "ignore"))
    out = []
    for loc in locs:
        if loc.endswith((".xml", ".xml.gz")) and depth < 2:
            out += sitemap_urls(fetcher, loc, rx, depth + 1)
        elif not rx or rx.search(loc):
            out.append(loc)
    return out


def discover_urls(cfg, fetcher, limit):
    """Devuelve {url_ficha: {'line':..., 'gender':...}}"""
    rx = re.compile(cfg["product_link_regex"]) if cfg.get("product_link_regex") else None
    sel = cfg.get("product_link_selector")
    found = {}

    for sm in cfg.get("sitemaps", []):
        print(f"   sitemap: {sm}")
        for u in sitemap_urls(fetcher, sm, rx):
            found.setdefault(u, {})

    for start in cfg.get("start_urls", []):
        s = {"url": start} if isinstance(start, str) else start
        hints = {"line": s.get("line"), "gender": s.get("gender")}
        seen = set()
        for page in range(1, (cfg.get("max_pages") or 1) + 1):
            page_url = with_page(s["url"], cfg.get("page_param"), page)
            html = fetcher.get(page_url)
            if not html:
                break
            links = extract_links(BeautifulSoup(html, "lxml"), page_url, rx, sel)
            new = [l for l in links if l not in seen]
            print(f"   {page_url} -> {len(links)} enlaces ({len(new)} nuevos)")
            if not new:
                break
            for l in new:
                seen.add(l)
                found.setdefault(l, hints)
            if not cfg.get("page_param") or len(found) >= limit:
                break
    return found


# =============================================================================
# Modos API (Shopify / WooCommerce)
# =============================================================================
def iter_shopify(cfg, fetcher, limit):
    base = cfg["base_url"].rstrip("/")
    coll = cfg.get("collection")
    path = f"/collections/{coll}/products.json" if coll else "/products.json"
    page, count = 1, 0
    while count < limit:
        data = fetcher.get(f"{base}{path}?limit=250&page={page}", as_json=True)
        items = (data or {}).get("products") or []
        if not items:
            break
        for it in items:
            v = (it.get("variants") or [{}])[0]
            tags = it.get("tags") or ""
            tags = ", ".join(tags) if isinstance(tags, list) else tags
            yield {
                "name": clean(it.get("title")),
                "reference": (v.get("sku") or it.get("handle") or "").upper(),
                "description": html_to_text(it.get("body_html")),
                "price": parse_price(v.get("price")), "currency": None,
                "image_urls": [urljoin(base, i["src"]) for i in it.get("images", []) if i.get("src")],
                "specs": {"Tipo": it["product_type"]} if it.get("product_type") else {},
                "url": f"{base}/products/{it.get('handle')}", "extra": tags,
            }
            count += 1
            if count >= limit:
                return
        page += 1


def iter_woocommerce(cfg, fetcher, limit):
    base = cfg["base_url"].rstrip("/")
    page, count = 1, 0
    while count < limit:
        data = fetcher.get(f"{base}/wp-json/wc/store/v1/products?per_page=100&page={page}", as_json=True)
        if not data or not isinstance(data, list):
            break
        for it in data:
            pr = it.get("prices") or {}
            minor = int(pr.get("currency_minor_unit", 2) or 0)
            price = float(pr["price"]) / (10 ** minor) if pr.get("price") else None
            specs = {a["name"]: ", ".join(t["name"] for t in a.get("terms", []))
                     for a in it.get("attributes", []) if a.get("name")}
            cats = ", ".join(c["name"] for c in it.get("categories", []))
            yield {
                "name": html_to_text(it.get("name")),
                "reference": (it.get("sku") or it.get("slug") or "").upper(),
                "description": html_to_text(it.get("short_description") or it.get("description")),
                "price": price, "currency": pr.get("currency_code"),
                "image_urls": [urljoin(base, i["src"]) for i in it.get("images", []) if i.get("src")],
                "specs": specs, "url": it.get("permalink"), "extra": cats,
            }
            count += 1
            if count >= limit:
                return
        page += 1


# =============================================================================
# Flujo principal por marca
# =============================================================================
def iter_html_records(cfg, fetcher, urls, refresh):
    for i, (url, hints) in enumerate(urls.items(), 1):
        if not refresh and db.url_exists(url):
            print(f"   [{i}/{len(urls)}] ya existe, se omite: {url}")
            continue
        html = fetcher.get(url)
        rec = parse_product_page(html, url, cfg) if html else None
        if not rec:
            print(f"   [{i}/{len(urls)}] sin datos de producto: {url}")
            continue
        rec["hint_line"], rec["hint_gender"] = hints.get("line"), hints.get("gender")
        yield rec


def save_record(cfg, rec, download=True):
    if not rec.get("reference") or not rec.get("name"):
        return False
    line, gender = classify(cfg["key"], f"{rec['name']} {rec.get('extra', '')}", rec["reference"],
                            rec.get("url", ""), rec.get("hint_line"), rec.get("hint_gender"))
    images = download_images(cfg["key"], rec["reference"], rec.get("image_urls", []),
                             referer=rec.get("url")) if download else []
    db.upsert_product({
        "brand": cfg["name"], "reference": rec["reference"], "name": rec["name"],
        "line": line, "gender": gender, "description": rec.get("description"),
        "specs": rec.get("specs"), "price": rec.get("price"), "currency": rec.get("currency"),
        "url": rec.get("url"), "images": images,
    })
    print(f"      OK  {cfg['name']} | {rec['reference']} | {line} | {gender} | {len(images)} img")
    return True


def scrape_brand(cfg, limit=None, download=True, refresh=False, urls=None):
    """Extrae una marca completa. `urls` = dict de fichas para saltar el descubrimiento."""
    db.init_db()
    limit = limit or config.MAX_PRODUCTS_PER_BRAND
    mode = cfg.get("mode", "html")
    fetcher = Fetcher(js=bool(cfg.get("js")) and mode == "html")
    saved = 0
    print(f"\n=== {cfg['name']} ({mode}) ===")
    try:
        if mode == "shopify":
            records = iter_shopify(cfg, fetcher, limit)
        elif mode == "woocommerce":
            records = iter_woocommerce(cfg, fetcher, limit)
        else:
            found = urls if urls is not None else discover_urls(cfg, fetcher, limit)
            found = dict(list(found.items())[:limit])
            print(f"   {len(found)} fichas para leer")
            records = iter_html_records(cfg, fetcher, found, refresh)
        for rec in records:
            saved += save_record(cfg, rec, download)
    finally:
        fetcher.close()
    print(f"=== {cfg['name']}: {saved} productos guardados ===")
    return saved


def probe_url(url, cfg):
    """Diagnóstico de UNA ficha: muestra qué logra leer el extractor."""
    fetcher = Fetcher(js=bool(cfg.get("js")))
    try:
        html = fetcher.get(url)
    finally:
        fetcher.close()
    if not html:
        print("No se pudo descargar la página.")
        return None
    rec = parse_product_page(html, url, cfg)
    if not rec:
        print("La página se descargó pero no se detectó un producto.\n"
              "Pistas: probar js=True, revisar selectores, o cargar la ficha en urls_manuales.txt.")
        return None
    rec["image_urls"] = rec["image_urls"][:6]
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec
