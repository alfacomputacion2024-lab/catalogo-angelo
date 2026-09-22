#!/usr/bin/env python3
"""Verificar marcas en la base de datos"""
import db

db.init_db()

with db.get_conn() as conn:
    # Obtener todas las marcas y conteo
    rows = conn.execute("""
        SELECT brand, COUNT(*) as cnt 
        FROM products 
        WHERE status='active' 
        GROUP BY brand 
        ORDER BY cnt DESC
    """).fetchall()

    print("=== Productos por marca ===")
    total = 0
    for r in rows:
        print(f"  {r['brand']:35s} {r['cnt']:4d}")
        total += r['cnt']
    print(f"\n  TOTAL: {total}")

    # Verificar modelos por marca completa
    print("\n=== Modelos por marca ===")
    for r in rows:
        brand = r['brand']
        refs = conn.execute("""
            SELECT reference, name FROM products 
            WHERE brand=? AND status='active' 
            ORDER BY reference
        """, (brand,)).fetchall()
        print(f"\n  {brand} ({len(refs)} productos):")
        for ref in refs[:5]:
            print(f"    - {ref['reference']} | {ref['name']}")
        if len(refs) > 5:
            print(f"    ... y {len(refs)-5} más")
