"""Conteo rápido de productos por marca (catálogo activo)."""
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # raíz del repo

import db
db.init_db()
prods = db.query_products(status="active")
print(f"Total: {len(prods)} productos")
brands = db.distinct_values("brand", "active")
for b in brands:
    count = len([p for p in prods if p["brand"] == b])
    print(f"  {b}: {count}")
