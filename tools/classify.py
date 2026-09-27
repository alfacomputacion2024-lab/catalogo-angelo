"""
Clasificador simple de línea y género para relojes.
"""


def classify(brand_key, name, reference, url="", hint_line=None, hint_gender=None):
    """Retorna (line, gender) basado en el nombre/referencia."""
    text = f"{name} {reference} {url}".lower()

    # Género
    gender = hint_gender
    if not gender:
        if any(w in text for w in ["dama", "mujer", "femen", "ladies", "women", "ltp"]):
            gender = "Dama"
        elif any(w in text for w in ["caballero", "hombre", "men", "masculi", "mtp", "protrek"]):
            gender = "Hombre"
        else:
            gender = "Unisex"

    # Línea
    line = hint_line
    if not line:
        lines = [
            ("g-shock", "G-Shock"), ("baby-g", "Baby-G"), ("baby g", "Baby-G"),
            ("edifice", "Edifice"), ("protrek", "ProTrek"), ("pro trek", "ProTrek"),
            ("sheen", "Sheen"), ("vintage", "Vintage"),
            ("tommy", "Tommy Hilfiger"), ("tommy hilfiger", "Tommy Hilfiger"),
            ("armani", "Armani Exchange"), ("bulova", "Bulova"),
            ("calvin", "Calvin Klein"), ("calvin klein", "Calvin Klein"),
            ("diesel", "Diesel"), ("fossil", "Fossil"),
            ("hugo", "Hugo Boss"), ("hugo boss", "Hugo Boss"),
            ("lacoste", "Lacoste"), ("michael", "Michael Kors"),
            ("michael kors", "Michael Kors"), ("citizen", "Citizen"),
            ("seiko", "Seiko"), ("invicta", "Invicta"),
            ("q&q", "Q&Q"), ("qq", "Q&Q"),
            ("skmei", "Skmei"), ("curren", "Curren"),
            ("naviforce", "NaviForce"), ("hummer", "Hummer"),
            ("caterpillar", "Caterpillar"),
            ("casio", "Casio"),
        ]
        for keyword, line_name in lines:
            if keyword in text:
                line = line_name
                break
        if not line:
            line = "General"

    return line, gender
