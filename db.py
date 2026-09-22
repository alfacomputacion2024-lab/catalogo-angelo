"""Base de datos SQLite del catálogo."""
import json
import re
import sqlite3

from config import DATA_DIR, DB_PATH, IMAGES_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    brand       TEXT NOT NULL,
    reference   TEXT NOT NULL,
    name        TEXT,
    line        TEXT,
    gender      TEXT,
    description TEXT,
    specs       TEXT,           -- JSON {"Etiqueta": "valor"}
    price       REAL,           -- precio encontrado en la web de origen
    sell_price  REAL,           -- TU precio de venta (editable en el panel)
    currency    TEXT,
    url         TEXT,
    images      TEXT,           -- JSON lista de rutas relativas a data/imagenes
    status      TEXT DEFAULT 'active',   -- active | deleted
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(brand, reference)
);
"""


def get_conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def norm_ref(ref: str) -> str:
    """'GA-2100-1A' -> 'GA21001A' (para comparar referencias sin importar guiones/espacios)."""
    return re.sub(r"[^A-Z0-9]", "", (ref or "").upper())


def upsert_product(p: dict):
    """Inserta o actualiza. Nunca reactiva un producto eliminado ni pisa tu precio de venta."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO products (brand, reference, name, line, gender, description,
                                  specs, price, sell_price, currency, url, images)
            VALUES (:brand, :reference, :name, :line, :gender, :description,
                    :specs, :price, :sell_price, :currency, :url, :images)
            ON CONFLICT(brand, reference) DO UPDATE SET
                name=excluded.name, line=excluded.line, gender=excluded.gender,
                description=excluded.description, specs=excluded.specs,
                price=excluded.price, sell_price=COALESCE(excluded.sell_price, products.sell_price),
                currency=excluded.currency, url=excluded.url, images=excluded.images
            """,
            {
                "brand": p["brand"],
                "reference": p["reference"],
                "name": p.get("name"),
                "line": p.get("line"),
                "gender": p.get("gender"),
                "description": p.get("description"),
                "specs": json.dumps(p.get("specs") or {}, ensure_ascii=False),
                "price": p.get("price"),
                "sell_price": p.get("sell_price"),
                "currency": p.get("currency"),
                "url": p.get("url"),
                "images": json.dumps(p.get("images") or [], ensure_ascii=False),
            },
        )


def url_exists(url: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM products WHERE url=?", (url,)).fetchone() is not None


def row_to_dict(row) -> dict:
    d = dict(row)
    d["specs"] = json.loads(d.get("specs") or "{}")
    d["images"] = json.loads(d.get("images") or "[]")
    return d


def query_products(brand=None, line=None, gender=None, q=None, status="active", ids=None):
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if status and status != "all":
        sql += " AND status=?"
        args.append(status)
    if brand:
        sql += " AND brand=?"
        args.append(brand)
    if line:
        sql += " AND line=?"
        args.append(line)
    if gender:
        sql += " AND gender=?"
        args.append(gender)
    if q:
        sql += " AND (reference LIKE ? OR name LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if ids:
        sql += f" AND id IN ({','.join('?' * len(ids))})"
        args += list(ids)
    sql += " ORDER BY brand, line, reference"
    with get_conn() as conn:
        return [row_to_dict(r) for r in conn.execute(sql, args).fetchall()]


def distinct_values(column: str, status="active"):
    assert column in ("brand", "line", "gender")
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM products WHERE status=? AND {column} IS NOT NULL "
            f"AND {column}!='' ORDER BY {column}", (status,)
        ).fetchall()
    return [r[0] for r in rows]


def set_status(ids, status):
    if not ids:
        return 0
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE products SET status=? WHERE id IN ({','.join('?' * len(ids))})",
            [status, *ids],
        )
        return cur.rowcount


def delete_brand(brand: str):
    with get_conn() as conn:
        cur = conn.execute("UPDATE products SET status='deleted' WHERE brand=? AND status='active'", (brand,))
        return cur.rowcount


def update_sell_prices(prices: dict):
    """prices = {id: float|None}"""
    with get_conn() as conn:
        for pid, val in prices.items():
            conn.execute("UPDATE products SET sell_price=? WHERE id=?", (val, pid))


def keep_only_references(refs, partial=False, brand=None):
    """Deja activos solo los productos cuya referencia esté en `refs` (tu stock).
    partial=True: 'GA-2100' conserva todas sus variantes (GA-2100-1A, GA-2100-4A...)."""
    wanted = {norm_ref(r) for r in refs if norm_ref(r)}
    if not wanted:
        return 0
    removed = 0
    with get_conn() as conn:
        sql = "SELECT id, reference FROM products WHERE status='active'"
        args = []
        if brand:
            sql += " AND brand=?"
            args.append(brand)
        for row in conn.execute(sql, args).fetchall():
            ref = norm_ref(row["reference"])
            ok = ref in wanted or (partial and any(ref.startswith(w) for w in wanted))
            if not ok:
                conn.execute("UPDATE products SET status='deleted' WHERE id=?", (row["id"],))
                removed += 1
    return removed


def stats():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT brand, status, COUNT(*) c FROM products GROUP BY brand, status"
        ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["brand"], {"active": 0, "deleted": 0})[r["status"]] = r["c"]
    return out
