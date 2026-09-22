"""
Generador del PDF del catálogo (ReportLab).
Todo el diseño (colores, textos, columnas, fuentes, logo) sale de theme.json.
"""
import datetime
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import config

# Especificaciones que se prefieren mostrar en cada tarjeta (por orden de importancia)
SPEC_PRIORITY = ["resistencia", "water", "agua", "diametro", "diámetro", "caja", "case", "size",
                 "tamaño", "material", "cristal", "crystal", "movimiento", "movement",
                 "correa", "strap", "band", "funciones", "function"]


def load_theme():
    theme = json.loads(config.THEME_PATH.read_text(encoding="utf-8"))
    return theme


def safe(text) -> str:
    """Quita caracteres que las fuentes estándar de PDF no pueden dibujar."""
    return str(text or "").encode("cp1252", errors="ignore").decode("cp1252")


def fmt_price(value, theme):
    if value is None:
        return ""
    dec = int(theme.get("price_decimals", 0))
    txt = f"{value:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{theme.get('currency_symbol', '')} {txt}".strip()


def pick_specs(specs: dict, n: int):
    def score(item):
        key = item[0].lower()
        for i, word in enumerate(SPEC_PRIORITY):
            if word in key:
                return i
        return 999
    return sorted(specs.items(), key=score)[:n]


def fit_text(c, text, font, size, max_w, conv=safe):
    text = conv(text)
    if c.stringWidth(text, font, size) <= max_w:
        return text
    while text and c.stringWidth(text + "...", font, size) > max_w:
        text = text[:-1]
    return text + "..."


class CatalogBuilder:
    def __init__(self, out_path, theme, products, show_prices=None, title=None):
        self.theme = theme
        self.products = products
        self.out_path = str(out_path)
        self.show_prices = theme.get("show_prices", True) if show_prices is None else show_prices
        self.title = title or theme.get("tagline", "Catálogo")
        self.col = {k: HexColor(v) for k, v in theme["colors"].items()}
        self.size = LETTER if str(theme.get("page_size", "A4")).upper() == "LETTER" else A4
        self.W, self.H = self.size
        self.page_no = 0
        self._setup_fonts()
        self.c = canvas.Canvas(self.out_path, pagesize=self.size)
        self.c.setTitle(safe(f"{theme.get('store_name', '')} - {self.title}"))

    # --- fuentes ------------------------------------------------------------
    def _setup_fonts(self):
        t = self.theme
        self.font, self.bold = t.get("font", "Helvetica"), t.get("font_bold", "Helvetica-Bold")
        for key, name in (("font_file", "CatalogFont"), ("font_bold_file", "CatalogFont-Bold")):
            path = t.get(key)
            if path and Path(path).exists():
                pdfmetrics.registerFont(TTFont(name, path))
                if key == "font_file":
                    self.font = name
                else:
                    self.bold = name
        self.unicode_font = self.font not in ("Helvetica", "Times-Roman", "Courier")

    def fit(self, text, font, size, max_w):
        return fit_text(self.c, text, font, size, max_w, self.s)

    def s(self, text):
        return str(text or "") if self.unicode_font else safe(text)

    # --- páginas --------------------------------------------------------------
    def cover(self):
        c, t = self.c, self.theme
        c.setFillColor(self.col["primary"])
        c.rect(0, 0, self.W, self.H, stroke=0, fill=1)

        # Logo centrado arriba
        logo = t.get("logo")
        if logo and Path(logo).exists():
            logo_w, logo_h = 200, 100
            self._image(logo, (self.W - logo_w) / 2, self.H * 0.72, logo_w, logo_h, align="center")

        # Linea decorativa centrada
        c.setFillColor(self.col["accent"])
        c.rect((self.W - 60) / 2, self.H * 0.70, 60, 4, stroke=0, fill=1)

        # Nombre centrado
        c.setFillColor(self.col["cover_text"])
        c.setFont(self.bold, 30)
        store_name = self.s(t.get("store_name", ""))
        y = self.H * 0.60
        for line in simpleSplit(store_name, self.bold, 30, self.W * 0.76):
            c.drawCentredString(self.W / 2, y, line)
            y -= 36

        # Tagline centrado
        c.setFont(self.font, 15)
        c.setFillColor(self.col["accent"])
        c.drawCentredString(self.W / 2, y - 6, self.s(t.get("tagline", "")))

        # Nota centrada
        c.setFillColor(self.col["cover_text"])
        c.setFont(self.font, 11)
        c.drawCentredString(self.W / 2, y - 30, self.s(t.get("cover_note", "")))

        # Contacto centrado
        c.setFont(self.font, 10)
        yy = self.H * 0.18
        for line in t.get("contact_lines", []):
            c.drawCentredString(self.W / 2, yy, self.s(line))
            yy -= 14

        # Fecha abajo derecha
        c.drawRightString(self.W * 0.88, self.H * 0.06,
                          datetime.date.today().strftime("%d/%m/%Y"))
        c.showPage()
        self.page_no += 1

    def divider(self, brand, count):
        c = self.c
        c.setFillColor(self.col["primary"])
        c.rect(0, 0, self.W, self.H, stroke=0, fill=1)

        # Logo centrado arriba
        logo = self.theme.get("logo")
        if logo and Path(logo).exists():
            self._image(logo, (self.W - 140) / 2, self.H * 0.65, 140, 70, align="center")

        # Linea decorativa centrada
        c.setFillColor(self.col["accent"])
        c.rect((self.W - 60) / 2, self.H * 0.62, 60, 4, stroke=0, fill=1)

        # Marca centrada
        c.setFillColor(self.col["cover_text"])
        c.setFont(self.bold, 38)
        c.drawCentredString(self.W / 2, self.H * 0.50, self.s(brand.upper()))

        # Cantidad centrada
        c.setFont(self.font, 14)
        c.setFillColor(self.col["accent"])
        c.drawCentredString(self.W / 2, self.H * 0.45, f"{count} modelos")
        c.showPage()
        self.page_no += 1

    def header_footer(self, brand):
        c, m = self.c, 34
        c.setFillColor(self.col["background"])
        c.rect(0, 0, self.W, self.H, stroke=0, fill=1)
        c.setFillColor(self.col["primary"])
        c.rect(0, self.H - 42, self.W, 42, stroke=0, fill=1)
        c.setFillColor(self.col["cover_text"])
        c.setFont(self.bold, 11)
        c.drawString(m, self.H - 26, self.s(brand.upper()))
        c.setFont(self.font, 9)
        c.drawRightString(self.W - m, self.H - 26, self.s(self.theme.get("store_name", "")))
        c.setFillColor(self.col["accent"])
        c.rect(0, self.H - 45, self.W, 3, stroke=0, fill=1)
        c.setFillColor(self.col["muted"])
        c.setFont(self.font, 7.5)
        note = self.theme.get("price_note", "") if self.show_prices else ""
        c.drawString(m, 20, self.s(note))
        c.drawRightString(self.W - m, 20, f"{self.page_no + 1}")

    def _image(self, path, x, y, w, h, align="center"):
        try:
            img = ImageReader(str(path))
            iw, ih = img.getSize()
            ratio = min(w / iw, h / ih)
            dw, dh = iw * ratio, ih * ratio
            dx = x + (w - dw) / 2 if align == "center" else x
            self.c.drawImage(img, dx, y + (h - dh) / 2, dw, dh, mask="auto")
            return True
        except Exception:
            return False

    # --- tarjeta de producto -----------------------------------------------------
    def card(self, x, y, w, h, p):
        c, pad = self.c, 10
        c.setFillColor(self.col["card"])
        c.roundRect(x, y, w, h, 8, stroke=0, fill=1)

        img_h = h * 0.46
        drawn = False
        for rel in p["images"][:1]:
            path = config.IMAGES_DIR / rel
            if path.exists():
                drawn = self._image(path, x + pad, y + h - pad - img_h, w - 2 * pad, img_h)
        if not drawn:
            c.setFillColor(self.col["muted"])
            c.setFont(self.font, 8)
            c.drawCentredString(x + w / 2, y + h - pad - img_h / 2, "Sin imagen")

        inner = w - 2 * pad
        ty = y + h - pad - img_h - 14
        c.setFillColor(self.col["accent"])
        c.setFont(self.bold, 7.5)
        c.drawString(x + pad, ty, self.fit((p["line"] or p["brand"]).upper(), self.bold, 7.5, inner))
        ty -= 13
        c.setFillColor(self.col["text"])
        c.setFont(self.bold, 11)
        c.drawString(x + pad, ty, self.fit(p["reference"], self.bold, 11, inner))
        ty -= 11
        c.setFont(self.font, 7.5)
        c.setFillColor(self.col["muted"])
        for ln in simpleSplit(self.s(p["name"]), self.font, 7.5, inner)[:2]:
            c.drawString(x + pad, ty, ln)
            ty -= 9
        if p.get("gender") and p["gender"] != "Sin definir":
            c.drawString(x + pad, ty, self.fit(p["gender"], self.font, 7.5, inner))
            ty -= 9
        ty -= 2
        c.setFillColor(self.col["text"])
        c.setFont(self.font, 7)
        for k, v in pick_specs(p["specs"], int(self.theme.get("specs_per_card", 3))):
            if ty < y + pad + 24:
                break
            c.drawString(x + pad, ty, self.fit(f"{k}: {v}", self.font, 7, inner))
            ty -= 8.5

        if self.show_prices:
            field = self.theme.get("price_field", "sell_price")
            price = p.get(field) if p.get(field) is not None else (p.get("sell_price") or None)
            if price is not None:
                c.setFillColor(self.col["primary"])
                c.setFont(self.bold, 12)
                c.drawString(x + pad, y + pad, self.s(fmt_price(price, self.theme)))

    @staticmethod
    def _sort_key(p):
        ln = p["line"] or ""
        idx = config.LINE_ORDER.index(ln) if ln in config.LINE_ORDER else 99
        return (idx, ln, p["gender"] or "", p["reference"])

    # --- armado -------------------------------------------------------------------
    def build(self):
        t = self.theme
        cols, rows = int(t.get("columns", 2)), int(t.get("rows", 3))
        m, gap, top, bottom = 34, 12, 62, 38
        cw = (self.W - 2 * m - gap * (cols - 1)) / cols
        ch = (self.H - top - bottom - gap * (rows - 1)) / rows
        per_page = cols * rows

        self.cover()
        groups = {}
        for p in self.products:
            groups.setdefault(p["brand"], []).append(p)
        order = [b for b in config.BRAND_ORDER if b in groups] + [b for b in groups if b not in config.BRAND_ORDER]

        for brand in order:
            items = sorted(groups[brand], key=self._sort_key)
            if t.get("brand_dividers", True):
                self.divider(brand, len(items))
            for start in range(0, len(items), per_page):
                self.header_footer(brand)
                for i, p in enumerate(items[start:start + per_page]):
                    r, cidx = divmod(i, cols)
                    x = m + cidx * (cw + gap)
                    y = self.H - top - (r + 1) * ch - r * gap
                    self.card(x, y, cw, ch, p)
                self.c.showPage()
                self.page_no += 1
        self.c.save()
        return self.out_path


def build_pdf(products, out_path=None, show_prices=None, title=None):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        out_path = config.OUTPUT_DIR / f"catalogo_{stamp}.pdf"
    return CatalogBuilder(out_path, load_theme(), products, show_prices, title).build()


if __name__ == "__main__":
    import db
    prods = db.query_products(status="active")
    print(build_pdf(prods), f"({len(prods)} productos)")
