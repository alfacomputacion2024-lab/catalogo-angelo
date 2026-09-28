# -*- coding: utf-8 -*-
"""Clasificación de productos por MARCA REAL (nunca la tienda de origen).

Compartido por app.py (menús, /client, /catalogo, PDF) y db.py (filtros y
eliminaciones por marca). La columna `brand` en la base guarda el valor crudo
(del scrapeo o del alta manual); el nombre VISIBLE y con el que se agrupa,
filtra y borra es el que devuelve `watch_brand()`.

Cómo sumar cosas nuevas (ver README §8):
  * Marca nueva de relojes que ya se guarda como brand -> MARCAS_RELOJ.
  * Marca que aparece en línea/nombre/url -> CLAVES_MARCA (palabra clave).
  * Tienda de origen nueva -> el set TIENDAS_* que corresponda.
"""
import re

__all__ = ["short_brand", "watch_brand", "MARCAS_RELOJ", "TIENDAS_RELOJES",
           "TIENDAS_LENTES", "TIENDAS_PERFUMES", "CLAVES_MARCA"]


def short_brand(name):
    """Acorta nombres largos: 'Tiempo de Relojes (Casio)' -> 'Casio'"""
    if not name:
        return name
    m = re.match(r'^Tiempo de Relojes\s*\((.+)\)$', name)
    if m:
        return m.group(1)
    return name


# --- Menú superior: mostrar solo marcas de relojes (nunca la tienda de origen) ---
MARCAS_RELOJ = {
    "Casio", "Bulova", "Tommy Hilfiger", "Calvin Klein", "Michael Kors", "Lacoste",
    "Fossil", "Armani Exchange", "Hugo Boss", "Diesel", "Jean Vernier", "Q&Q",
    "Curren", "Skmei", "Invicta", "NaviForce", "Hummer", "Seiko", "Tissot",
    "Victorinox", "Citizen", "Orient", "Anne Klein", "Adidas", "G-Shock",
    "Edifice", "Baby-G", "ProTrek", "Casper", "Winner", "Skagen", "Obaku",
    "Guess", "Emporio Armani", "Dkny", "Coach", "Kate Spade",
    "Versace", "Valentino", "Calvin", "Replay", "Scuderia", "Lotus", "Ice",
    "Qaza", "Alexandre", "Tissot PRX",
}

# Tiendas cuyos productos son relojes (la marca real está en línea/nombre/url)
TIENDAS_RELOJES = {
    "AM Relojes", "Casa Joia", "TUPI", "Joyería G&A", "Joyería Sosa",
    "Asunción Joyas", "My Shuzz", "Joyería Domínguez", "Joyería Espínola",
}

# Tiendas de lentes / perfumes -> categoría visible
TIENDAS_LENTES = {
    "Arar Óptica", "Óptica Santa Lucía", "Óptica Visión",
    "Infinite Eyewear", "Valemar", "Ronan Eyewear",
}
TIENDAS_PERFUMES = {
    "La Perfumería", "Lual Perfumería", "Punto Tienda",
    "Shopping China Perfumes", "Perfumes",
}

# Palabra clave (buscada en línea + nombre + url, en minúsculas) -> marca visible
CLAVES_MARCA = [
    ("g-shock", "Casio"), ("gshock", "Casio"), ("baby-g", "Casio"), ("babyg", "Casio"),
    ("edifice", "Casio"), ("protrek", "Casio"), ("casio", "Casio"),
    ("q&q", "Q&Q"), ("qyq", "Q&Q"), ("relojes-qq", "Q&Q"),
    ("naviforce", "NaviForce"), ("invicta", "Invicta"), ("curren", "Curren"),
    ("skmei", "Skmei"), ("hummer", "Hummer"), ("tommy", "Tommy Hilfiger"),
    ("victorinox", "Victorinox"), ("tissot", "Tissot"), ("seiko", "Seiko"),
    ("citizen", "Citizen"), ("orient", "Orient"), ("bulova", "Bulova"),
    ("fossil", "Fossil"), ("calvin", "Calvin Klein"), ("michael kors", "Michael Kors"),
    ("lacoste", "Lacoste"), ("armani", "Armani Exchange"), ("hugo", "Hugo Boss"),
    ("boss", "Hugo Boss"), ("diesel", "Diesel"), ("vernier", "Jean Vernier"),
    ("anne klein", "Anne Klein"), ("anna klein", "Anne Klein"), ("adidas", "Adidas"),
    ("jean vernier", "Jean Vernier"), ("guess", "Guess"), ("versace", "Versace"),
    ("casper", "Casper"), ("skagen", "Skagen"), ("obaku", "Obaku"),
    ("emporio", "Emporio Armani"), ("dkny", "DKNY"), ("coach", "Coach"),
    ("i.n.o.x", "Victorinox"), ("air pro", "Victorinox"), ("vip", "ViP"),
]


def watch_brand(brand, line="", name="", url=""):
    """Nombre visible para el menú y para agrupar: la marca real del producto,
    nunca la tienda de la que se scrapeó."""
    brand = short_brand(brand) if brand else ""
    if brand in MARCAS_RELOJ:
        return brand
    if brand in TIENDAS_LENTES:
        return line if line in ("Lentes", "Armazones", "Lentes recetados") else "Lentes"
    if brand in TIENDAS_PERFUMES:
        return line if line == "Perfumes" else "Perfumes"
    text = f"{line or ''} {name or ''} {url or ''}".lower()
    for kw, marca in CLAVES_MARCA:
        if kw in text:
            return marca
    if brand in TIENDAS_RELOJES:
        return "Varios"
    return brand or "Varios"
