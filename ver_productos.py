import db
db.init_db()
prods = db.query_products(status="active")
print(f"Total: {len(prods)} productos")
brands = db.distinct_values("brand", "active")
for b in brands:
    count = len([p for p in prods if p["brand"] == b])
    print(f"  {b}: {count}")
