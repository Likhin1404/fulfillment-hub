"""Generates a realistic day of sample data (about 250 orders) with deliberate problems to catch.

Run directly to rebuild the database:  python seed.py
"""
import json
import random
import re
from datetime import datetime, timedelta

import core

CATALOG = [
    # base code, name, sizes, colours
    ("TEE", "Cotton Crew Tee", ["S", "M", "L", "XL"], ["Navy", "White", "Olive"]),
    ("HOO", "Fleece Hoodie", ["S", "M", "L", "XL"], ["Black", "Grey", "Maroon"]),
    ("BTL", "Steel Water Bottle", ["500ml", "750ml"], ["Silver", "Teal", "Black"]),
    ("MAT", "Yoga Mat", ["6mm", "8mm"], ["Purple", "Blue", "Grey"]),
    ("CAS", "Phone Case", ["iPhone 14", "iPhone 15", "Galaxy S23"], ["Clear", "Black"]),
    ("CBL", "USB-C Cable", ["1m", "2m"], ["White", "Black"]),
    ("MUG", "Ceramic Mug", ["300ml"], ["White", "Blue", "Green", "Red"]),
    ("BAG", "Canvas Tote Bag", ["Standard"], ["Natural", "Black"]),
]
GHOST_TRANSFER = "TEE-NAV-M"   # system says 4 on the shelf, but they are gone; 40 sit in the overflow warehouse
GHOST_HOLD = "HOO-GRE-L"       # system says 3 on the shelf, but they are gone; nothing anywhere else

COURIERS = [
    (1, "SwiftExpress", 140, 1, "14:00", "Lane A"),
    (2, "BlueLine Standard", 75, 3, "16:30", "Lane B"),
    (3, "EcoShip Economy", 48, 5, "18:00", "Lane C"),
]
NAMES = ["Aarav", "Diya", "Rohan", "Ananya", "Vikram", "Sneha", "Karthik", "Pooja", "Imran", "Lakshmi", "Arjun",
         "Neha", "Suresh", "Divya", "Manoj", "Kavya", "Rahul", "Ishita", "Naveen", "Shreya", "Faisal", "Meghana"]
SURNAMES = ["Rao", "Shetty", "Gowda", "Nair", "Iyer", "Sharma", "Reddy", "Khan", "Patel", "Kulkarni", "Menon", "Das"]
CITIES = ["Bengaluru", "Mysuru", "Chennai", "Hyderabad", "Mumbai", "Pune", "Kochi", "Delhi", "Kolkata", "Coimbatore"]
CHANNELS = ["Amazon", "Flipkart", "Own website"]


def build_products(conn, rng):
    skus = []
    for bi, (base, name, sizes, colours) in enumerate(CATALOG):
        for ci, col in enumerate(colours):
            for si, size in enumerate(sizes):
                sku = f"{base}-{col[:3].upper()}-{re.sub('[^A-Z0-9]', '', size.upper())}"
                loc = f"{chr(65 + bi)}-{ci + 1:02d}-{si + 1}"
                variant = f"{col}, {size}" if size != "Standard" else col
                conn.execute(
                    "INSERT INTO products VALUES(?,?,?,?,?,?)",
                    (sku, base, name, variant, loc, f"WH2-{chr(65 + bi)}{ci + 1}"),
                )
                main = rng.randint(18, 90)
                over = rng.choice([0, 0, 25, 40, 60, 90])
                if sku == GHOST_TRANSFER:
                    main, over = 4, 40
                if sku == GHOST_HOLD:
                    main, over = 3, 0
                conn.execute("INSERT INTO inventory VALUES(?,?,?)", (sku, main, over))
                skus.append(sku)
    return skus


def seed(conn, today=None):
    rng = random.Random(7)
    core.reset_schema(conn)
    today = (today or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    now = today.replace(hour=12, minute=30)
    yesterday = today - timedelta(days=1)
    two_days = today - timedelta(days=2)

    for c in COURIERS:
        conn.execute("INSERT INTO couriers VALUES(?,?,?,?,?,?)", c)
    couriers = core.q(conn, "SELECT * FROM couriers")
    skus = build_products(conn, rng)
    normal = [s for s in skus if s not in (GHOST_TRANSFER, GHOST_HOLD)]

    def t(day, h, m=0):
        return day.replace(hour=h, minute=m)

    def rand_time(day, h1, h2):
        return day.replace(hour=0) + timedelta(minutes=rng.randint(h1 * 60, h2 * 60 - 1))

    def rand_lines(n=None):
        n = n or rng.choices([1, 2, 3], [60, 30, 10])[0]
        return [(s, rng.choices([1, 2, 3], [80, 15, 5])[0]) for s in rng.sample(normal, n)]

    specs = []

    def add(created, status, priority, promised=None, lines=None, tag=None, picker=None, **kw):
        if promised is None:
            promised = rng.choices([1, 3], [35, 65])[0] if priority else rng.choices([5, 3, 1], [70, 20, 10])[0]
        specs.append(dict(created=created, status=status, priority=priority, promised=promised,
                          lines=lines or rand_lines(), tag=tag, picker=picker, **kw))

    # 1. Yesterday's orders, all shipped
    for _ in range(130):
        add(rand_time(yesterday, 7, 17), "SHIPPED", int(rng.random() < 0.2))
    # 2. Backlog nobody noticed: created two days ago, past their ship-by time
    add(rand_time(two_days, 9, 12), "LABELLED", 0, promised=5, tag="backlog_unpicked")
    add(rand_time(two_days, 9, 12), "PICKING", 0, promised=5, picker="Ravi", tag="backlog_partial", lines=rand_lines(2))
    add(rand_time(two_days, 12, 15), "ON_HOLD", 0, promised=5, tag="backlog_hold")
    add(rand_time(two_days, 12, 15), "PACKED", 0, promised=5, tag="backlog_packed_lost")
    # 3. Yesterday's leftovers, still open and due today
    for st in ["NEW"] * 4 + ["LABELLED"] * 5 + ["PICKING"] * 3:
        add(rand_time(yesterday, 14, 20), st, 0, promised=rng.choice([5, 5, 3]), picker=rng.choice(["Ravi", "Meena"]) if st == "PICKING" else None)
    # 4. Today, in flight
    for st, n, lo, hi in [("STAGED", 14, 6.5, 9.5), ("PACKED", 8, 6.5, 9.5), ("PICKED", 10, 6.5, 9.5),
                          ("PICKING", 8, 7, 10), ("LABELLED", 28, 8, 10.5), ("NEW", 38, 10, 12.3)]:
        for _ in range(n):
            created = today + timedelta(minutes=rng.randint(int(lo * 60), int(hi * 60)))
            add(created, st, int(rng.random() < 0.25),
                picker=rng.choice(["Ravi", "Meena"]) if st == "PICKING" else (rng.choice(core.PICKERS) if st in ("PICKED", "PACKED", "STAGED") else None))
    # 5. Crafted demo orders
    add(t(today, 6, 5), "LABELLED", 1, promised=1, tag="ghost_transfer", lines=[(GHOST_TRANSFER, 2)] + rand_lines(1))
    add(t(today, 6, 10), "LABELLED", 1, promised=3, tag="ghost_hold", lines=[(GHOST_HOLD, 1)])
    add(t(today, 6, 20), "PICKED", 1, promised=3, tag="pack_demo", picker="Asha", lines=rand_lines(2))
    for i in range(3):
        add(t(today, 8, 30 + i * 10), "PICKING" if i == 2 else "LABELLED", 1, promised=1, tag=f"swift_late_{i}",
            picker="Meena" if i == 2 else None, lines=rand_lines(2))

    specs.sort(key=lambda s: s["created"])
    notes = {}
    for i, s in enumerate(specs):
        s["id"] = f"XYZ-{24001 + i}"
        if s["tag"]:
            notes[s["tag"]] = s["id"]

    for s in specs:
        _materialize(conn, rng, s, couriers, now, today)

    # inventory / issue history that make the demo feel lived-in
    hold = next(s for s in specs if s["tag"] == "backlog_hold")
    hold_sku = core.order_items(conn, hold["id"])[0]["sku"]
    conn.execute("UPDATE inventory SET main_qty=0, overflow_qty=0 WHERE sku=?", (hold_sku,))
    conn.execute("UPDATE lines SET status='short' WHERE order_id=? AND sku=?", (hold["id"], hold_sku))
    reason = f"Not enough stock of {hold_sku}: need 1, have 0 in total"
    conn.execute("UPDATE orders SET hold_reason=? WHERE id=?", (reason, hold["id"]))
    core.add_issue(conn, "STOCK_SHORT", hold["id"], hold_sku, reason, "high", two_days.replace(hour=14), owner="Priya")
    lost = next(s for s in specs if s["tag"] == "backlog_packed_lost")
    core.add_issue(conn, "MISPLACED_BOX", lost["id"], None,
                   f"Box for {lost['id']} was packed but never reached its courier lane. Find it or repack.",
                   "high", yesterday.replace(hour=17), owner="Kiran")
    core.add_issue(conn, "WRONG_ITEM", None, "TEE-OLI-L", "Scanned Olive, L but the order needed Olive, M. Caught before shipping.",
                   "high", yesterday.replace(hour=11, minute=20), owner="Divya", status="resolved")
    conn.execute("UPDATE issues SET resolved_at=?, note='Swapped to the right size and repacked' WHERE status='resolved'",
                 (core.fmt(yesterday.replace(hour=11, minute=40)),))

    core.set_setting(conn, "demo_date", today.strftime("%Y-%m-%d"))
    core.set_setting(conn, "demo_notes", json.dumps(notes))
    conn.commit()
    return notes


def _materialize(conn, rng, s, couriers, now, today):
    created = s["created"]
    prio = s["priority"]
    ship_by = created.replace(hour=18, minute=0) + (timedelta(0) if prio else timedelta(days=1))
    status = s["status"]
    order = dict(ship_by=core.fmt(ship_by), promised_days=s["promised"])
    courier_id = label_no = pickup_at = None
    label_time = None
    if status != "NEW":
        if s["tag"] and s["tag"].startswith("backlog"):
            label_time = created + timedelta(minutes=15)
        else:
            label_time = max(created, today.replace(hour=6, minute=30)) + timedelta(minutes=rng.randint(5, 25))
        label_time = min(label_time, now - timedelta(minutes=15))
        opt, _ = core.suggest_courier(couriers, order, label_time)
        c = opt["courier"]
        courier_id, label_no, pickup_at = c["id"], f"LBL-{rng.randint(100000, 999999)}", opt["pickup"]
    row_status = status
    picker = s["picker"]
    packer = rng.choice(core.PACKERS) if status in ("PACKED", "STAGED", "SHIPPED") else None
    staged_at = shipped_at = None
    channel = rng.choice(CHANNELS)
    ev = [(created, f"Order received from {channel}", "Marketplace")]
    if label_time:
        ev.append((label_time, f"Label {label_no} created: {c['name']}, pickup {core.when(pickup_at, now)}", rng.choice(core.OFFICE)))
    cur = label_time
    if status in ("PICKING", "PICKED", "PACKED", "STAGED", "ON_HOLD", "SHIPPED"):
        picker = picker or rng.choice(core.PICKERS)
        cur = min(cur + timedelta(minutes=rng.randint(10, 40)), now - timedelta(minutes=10))
        ev.append((cur, "Picking started", picker))
    if status in ("PICKED", "PACKED", "STAGED", "SHIPPED"):
        cur = min(cur + timedelta(minutes=rng.randint(10, 25)), now - timedelta(minutes=8))
        ev.append((cur, "All items picked", picker))
    if status in ("PACKED", "STAGED", "SHIPPED"):
        cur = min(cur + timedelta(minutes=rng.randint(5, 15)), now - timedelta(minutes=5))
        ev.append((cur, f"Packed and label attached. Take to {c['lane']}", packer))
    if status in ("STAGED", "SHIPPED"):
        cur = min(cur + timedelta(minutes=rng.randint(3, 10)), now - timedelta(minutes=2))
        staged_at = cur
        ev.append((cur, f"Box checked into {c['lane']}", packer))
    if status == "SHIPPED":
        shipped_at = pickup_at
        ev.append((pickup_at, "Handed to courier", "Dispatch"))
    if s["tag"] == "backlog_packed_lost":
        staged_at = None
    if status in ("LABELLED", "NEW"):
        picker = None
    if s["tag"] in ("backlog_hold",):
        picker = None
        row_status = "ON_HOLD"
    if s["tag"] == "backlog_unpicked":
        picker = None

    conn.execute(
        "INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (s["id"], channel, f"{rng.choice(NAMES)} {rng.choice(SURNAMES)}", rng.choice(CITIES), prio, s["promised"],
         core.fmt(created), core.fmt(ship_by), row_status, courier_id, label_no, core.fmt(pickup_at), picker, packer,
         core.fmt(staged_at), core.fmt(shipped_at), None),
    )
    for sku, qty in s["lines"]:
        picked, lstatus, verified = 0, "pending", 0
        if status in ("PICKED", "PACKED", "STAGED", "SHIPPED"):
            picked, lstatus = qty, "picked"
        verified = 1 if status in ("PACKED", "STAGED", "SHIPPED") else 0
        conn.execute("INSERT INTO lines(order_id,sku,qty,picked_qty,status,verified) VALUES(?,?,?,?,?,?)",
                     (s["id"], sku, qty, picked, lstatus, verified))
    if status == "PICKING":
        first = core.q(conn, "SELECT id, qty FROM lines WHERE order_id=? ORDER BY id LIMIT 1", (s["id"],))[0]
        conn.execute("UPDATE lines SET picked_qty=qty, status='picked' WHERE id=?", (first["id"],))
    for ts, text, actor in ev:
        core.log(conn, s["id"], text, ts, actor)


if __name__ == "__main__":
    c = core.connect()
    notes = seed(c)
    n = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"Seeded {n} orders. Demo order ids: {notes}")
