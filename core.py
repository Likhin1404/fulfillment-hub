"""Domain logic for the Fulfillment Hub. No Streamlit in here, so it is easy to test."""
import os
import random
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fulfillment.db")
FMT = "%Y-%m-%d %H:%M"

STAGES = ["NEW", "LABELLED", "PICKING", "PICKED", "PACKED", "STAGED", "SHIPPED"]
STAGE_NAME = {
    "NEW": "New",
    "LABELLED": "Ready to pick",
    "PICKING": "Picking",
    "PICKED": "Picked",
    "PACKED": "Packed",
    "STAGED": "In courier lane",
    "SHIPPED": "Shipped",
    "ON_HOLD": "On hold",
}
# Rough minutes of work still ahead of an order in each stage.
REMAINING = {"NEW": 75, "LABELLED": 60, "PICKING": 40, "PICKED": 20, "PACKED": 10, "STAGED": 0, "ON_HOLD": 90}
STAGE_BUFFER = 10      # boxes should be in the lane this many minutes before pickup
PROCESS_BUFFER = 60    # a label made now needs about an hour before it can make a pickup

PICKERS = ["Asha", "Ravi", "Meena"]
PACKERS = ["Kiran", "Divya"]
OFFICE = ["Priya", "Arun"]


# ---------- small helpers ----------
def parse(s):
    return datetime.strptime(s, FMT) if s else None


def fmt(d):
    return d.strftime(FMT) if d else None


def dur(minutes):
    minutes = int(abs(round(minutes)))
    d, rem = divmod(minutes, 1440)
    h, m = divmod(rem, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def when(dt, now):
    if dt is None:
        return "-"
    diff = (dt.date() - now.date()).days
    day = {0: "today", 1: "tomorrow", -1: "yesterday"}.get(diff, dt.strftime("%a %d %b"))
    return f"{day} {dt:%H:%M}"


def connect(path=DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def q(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()):
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE products(sku TEXT PRIMARY KEY, base TEXT, name TEXT, variant TEXT, location TEXT, overflow_loc TEXT);
CREATE TABLE inventory(sku TEXT PRIMARY KEY, main_qty INT, overflow_qty INT);
CREATE TABLE couriers(id INTEGER PRIMARY KEY, name TEXT, cost INT, days INT, pickup TEXT, lane TEXT);
CREATE TABLE orders(
  id TEXT PRIMARY KEY, channel TEXT, customer TEXT, city TEXT, priority INT, promised_days INT,
  created_at TEXT, ship_by TEXT, status TEXT, courier_id INT, label_no TEXT, pickup_at TEXT,
  picker TEXT, packer TEXT, staged_at TEXT, shipped_at TEXT, hold_reason TEXT);
CREATE TABLE lines(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, sku TEXT, qty INT,
  picked_qty INT DEFAULT 0, status TEXT DEFAULT 'pending', verified INT DEFAULT 0);
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, ts TEXT, text TEXT, actor TEXT);
CREATE TABLE issues(
  id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, order_id TEXT, sku TEXT, detail TEXT, severity TEXT,
  status TEXT DEFAULT 'open', owner TEXT, created_at TEXT, resolved_at TEXT, note TEXT);
CREATE TABLE transfers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, qty INT, status TEXT, order_id TEXT, created_at TEXT, done_at TEXT);
"""


def reset_schema(conn):
    for t in ["settings", "products", "inventory", "couriers", "orders", "lines", "events", "issues", "transfers"]:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.executescript(SCHEMA)
    conn.commit()


def get_setting(conn, key, default=None):
    r = one(conn, "SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    conn.commit()


def log(conn, oid, text, now, actor=""):
    conn.execute("INSERT INTO events(order_id,ts,text,actor) VALUES(?,?,?,?)", (oid, fmt(now), text, actor))


def add_issue(conn, type_, oid, sku, detail, severity, now, owner=None, status="open"):
    conn.execute(
        "INSERT INTO issues(type,order_id,sku,detail,severity,status,owner,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (type_, oid, sku, detail, severity, status, owner, fmt(now)),
    )


# ---------- couriers & deadlines ----------
def pickup_dt(courier, day):
    h, m = map(int, courier["pickup"].split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def next_pickup(courier, now, lead=PROCESS_BUFFER):
    t = pickup_dt(courier, now)
    if t - timedelta(minutes=lead) < now:
        t += timedelta(days=1)
    return t


def courier_options(couriers, order, now):
    ship_by = parse(order["ship_by"])
    out = []
    for c in couriers:
        p = next_pickup(c, now)
        out.append({"courier": c, "pickup": p, "speed_ok": c["days"] <= order["promised_days"], "time_ok": p <= ship_by})
    return out


def suggest_courier(couriers, order, now):
    """Cheapest courier that is fast enough AND makes the ship-by time. Returns (option, fully_ok)."""
    opts = courier_options(couriers, order, now)
    good = [o for o in opts if o["speed_ok"] and o["time_ok"]]
    if good:
        return min(good, key=lambda o: o["courier"]["cost"]), True
    fast = [o for o in opts if o["speed_ok"]] or opts
    return min(fast, key=lambda o: o["pickup"]), False


def order_risk(o, now):
    """Work backwards from the pickup (or ship-by) time to see whether an order will make it."""
    if o["status"] == "SHIPPED":
        return {"level": "done", "slack": None, "deadline": None, "text": "Shipped"}
    deadline = parse(o["pickup_at"]) or parse(o["ship_by"])
    if o["status"] == "STAGED":
        slack = (deadline - now).total_seconds() / 60
    else:
        rem = REMAINING.get(o["status"], 60)
        slack = (deadline - now).total_seconds() / 60 - STAGE_BUFFER - rem
    if now > deadline:
        level, text = "overdue", f"Overdue by {dur((now - deadline).total_seconds() / 60)}"
    elif slack < 0:
        level, text = "late", "Will miss cutoff"
    elif slack < 30:
        level, text = "tight", f"Tight: {dur(slack)} spare"
    else:
        level, text = "ok", "On track"
    return {"level": level, "slack": slack, "deadline": deadline, "text": text}


RISK_ORDER = {"overdue": 0, "late": 1, "tight": 2, "ok": 3, "done": 4}


def open_orders(conn, now):
    rows = q(
        conn,
        "SELECT o.*, c.name AS courier, c.lane AS lane FROM orders o "
        "LEFT JOIN couriers c ON c.id=o.courier_id WHERE o.status!='SHIPPED'",
    )
    for r in rows:
        r["risk"] = order_risk(r, now)
    rows.sort(key=lambda r: (r["risk"]["slack"], r["created_at"]))
    return rows


def order_items(conn, oid):
    return q(
        conn,
        "SELECT l.*, p.name, p.variant, p.location, p.overflow_loc, p.base FROM lines l "
        "JOIN products p ON p.sku=l.sku WHERE l.order_id=? ORDER BY p.location, l.id",
        (oid,),
    )


# ---------- stock ----------
def committed(conn, sku):
    r = one(
        conn,
        "SELECT COALESCE(SUM(l.qty-l.picked_qty),0) n FROM lines l JOIN orders o ON o.id=l.order_id "
        "WHERE l.sku=? AND o.status IN ('LABELLED','PICKING')",
        (sku,),
    )
    return r["n"]


def pending_transfer(conn, sku):
    return one(conn, "SELECT COALESCE(SUM(qty),0) n FROM transfers WHERE sku=? AND status='requested'", (sku,))["n"]


def plan_stock(conn, oid, now, actor=""):
    """After a label is made: check stock, request overflow transfers early, or hold the order if stock is short."""
    notes = []
    for l in order_items(conn, oid):
        inv = one(conn, "SELECT * FROM inventory WHERE sku=?", (l["sku"],))
        need = committed(conn, l["sku"])
        pend = pending_transfer(conn, l["sku"])
        if need <= inv["main_qty"] + pend:
            continue
        short = need - inv["main_qty"] - pend
        free_overflow = inv["overflow_qty"] - pend
        label = f"{l['name']} ({l['variant']})"
        if free_overflow >= short:
            qty = min(free_overflow, max(short, 10))
            conn.execute(
                "INSERT INTO transfers(sku,qty,status,order_id,created_at) VALUES(?,?,?,?,?)",
                (l["sku"], qty, "requested", oid, fmt(now)),
            )
            log(conn, oid, f"Stock move requested: {qty} x {label} from overflow warehouse", now, "System")
            notes.append(f"{oid}: move {qty} x {label} from the overflow warehouse")
        else:
            reason = f"Not enough stock of {l['sku']}: need {need}, have {inv['main_qty'] + inv['overflow_qty']} in total"
            conn.execute("UPDATE lines SET status='short' WHERE id=?", (l["id"],))
            conn.execute("UPDATE orders SET status='ON_HOLD', hold_reason=? WHERE id=?", (reason, oid))
            log(conn, oid, "Put on hold: " + reason, now, "System")
            add_issue(conn, "STOCK_SHORT", oid, l["sku"], reason, "high", now, owner="Priya")
            notes.append(f"{oid}: ON HOLD - {reason}")
            break
    return notes


def correct_stock(conn, sku, new_main, now, actor):
    old = one(conn, "SELECT main_qty FROM inventory WHERE sku=?", (sku,))["main_qty"]
    conn.execute("UPDATE inventory SET main_qty=? WHERE sku=?", (new_main, sku))
    add_issue(conn, "STOCK_ADJUST", None, sku, f"Main count corrected from {old} to {new_main} by {actor}", "low", now, owner=actor, status="resolved")
    conn.execute("UPDATE issues SET resolved_at=? WHERE id=last_insert_rowid()", (fmt(now),))
    conn.commit()


# ---------- office: labels ----------
def create_label(conn, oid, courier_id, now, actor):
    o = one(conn, "SELECT * FROM orders WHERE id=?", (oid,))
    if not o or o["status"] != "NEW":
        return False, [f"{oid}: already processed"]
    c = one(conn, "SELECT * FROM couriers WHERE id=?", (courier_id,))
    pickup = next_pickup(c, now)
    label = f"LBL-{random.randint(100000, 999999)}"
    conn.execute(
        "UPDATE orders SET status='LABELLED', courier_id=?, label_no=?, pickup_at=? WHERE id=?",
        (courier_id, label, fmt(pickup), oid),
    )
    log(conn, oid, f"Label {label} created: {c['name']}, pickup {when(pickup, now)}", now, actor)
    notes = plan_stock(conn, oid, now, actor)
    conn.commit()
    return True, notes


# ---------- picking ----------
def start_pick(conn, oid, picker, now):
    o = one(conn, "SELECT status FROM orders WHERE id=?", (oid,))
    if o["status"] == "LABELLED":
        log(conn, oid, "Picking started", now, picker)
    conn.execute("UPDATE orders SET status='PICKING', picker=? WHERE id=?", (picker, oid))
    conn.commit()


def park_order(conn, oid, picker, now):
    conn.execute("UPDATE orders SET picker=NULL WHERE id=?", (oid,))
    log(conn, oid, "Parked while waiting for stock", now, picker)
    conn.commit()


def pick_line(conn, line_id, picker, now):
    l = one(conn, "SELECT * FROM lines WHERE id=?", (line_id,))
    conn.execute("UPDATE inventory SET main_qty=MAX(main_qty-?,0) WHERE sku=?", (l["qty"] - l["picked_qty"], l["sku"]))
    conn.execute("UPDATE lines SET picked_qty=qty, status='picked' WHERE id=?", (line_id,))
    left = one(conn, "SELECT COUNT(*) n FROM lines WHERE order_id=? AND status!='picked'", (l["order_id"],))["n"]
    if left == 0:
        conn.execute("UPDATE orders SET status='PICKED' WHERE id=?", (l["order_id"],))
        log(conn, l["order_id"], "All items picked", now, picker)
    conn.commit()
    return left == 0


def cant_find(conn, line_id, picker, now):
    """Picker cannot find the item. Correct the count, look in the overflow warehouse, or hold the order."""
    l = one(conn, "SELECT l.*, p.name, p.variant FROM lines l JOIN products p ON p.sku=l.sku WHERE l.id=?", (line_id,))
    inv = one(conn, "SELECT * FROM inventory WHERE sku=?", (l["sku"],))
    need = l["qty"] - l["picked_qty"]
    label = f"{l['name']} ({l['variant']})"
    old = inv["main_qty"]
    conn.execute("UPDATE inventory SET main_qty=0 WHERE sku=?", (l["sku"],))
    add_issue(
        conn, "STOCK_NOT_FOUND", l["order_id"], l["sku"],
        f"{picker} could not find {label}. System said {old} on the main shelf; count reset to 0, please recount.",
        "medium", now, owner="Priya",
    )
    free_overflow = inv["overflow_qty"] - pending_transfer(conn, l["sku"])
    if free_overflow >= need:
        qty = min(free_overflow, max(need, 10))
        conn.execute(
            "INSERT INTO transfers(sku,qty,status,order_id,created_at) VALUES(?,?,?,?,?)",
            (l["sku"], qty, "requested", l["order_id"], fmt(now)),
        )
        conn.execute("UPDATE lines SET status='waiting' WHERE id=?", (line_id,))
        log(conn, l["order_id"], f"{label} not on shelf. Moving {qty} from overflow warehouse", now, picker)
        conn.commit()
        return "transfer", f"Not on the shelf. A stock move of {qty} from the overflow warehouse has been requested."
    reason = f"{label} not found on shelf and none in the overflow warehouse"
    conn.execute("UPDATE lines SET status='short' WHERE id=?", (line_id,))
    conn.execute("UPDATE orders SET status='ON_HOLD', hold_reason=?, picker=NULL WHERE id=?", (reason, l["order_id"]))
    log(conn, l["order_id"], "Put on hold: " + reason, now, picker)
    add_issue(conn, "STOCK_SHORT", l["order_id"], l["sku"], reason, "high", now, owner="Priya")
    conn.commit()
    return "hold", "Nothing in stock. The order is on hold and the office has been told."


def complete_transfer(conn, tid, picker, now):
    t = one(conn, "SELECT * FROM transfers WHERE id=?", (tid,))
    conn.execute("UPDATE inventory SET main_qty=main_qty+?, overflow_qty=MAX(overflow_qty-?,0) WHERE sku=?", (t["qty"], t["qty"], t["sku"]))
    conn.execute("UPDATE transfers SET status='done', done_at=? WHERE id=?", (fmt(now), tid))
    conn.execute(
        "UPDATE lines SET status='pending' WHERE sku=? AND status='waiting'",
        (t["sku"],),
    )
    if t["order_id"]:
        log(conn, t["order_id"], f"Stock moved to main warehouse ({t['qty']} x {t['sku']})", now, picker)
    conn.commit()


# ---------- packing ----------
def scan_item(conn, oid, code, packer, now):
    code = (code or "").strip().upper()
    lines = order_items(conn, oid)
    match = next((l for l in lines if l["sku"] == code and not l["verified"]), None)
    if match:
        conn.execute("UPDATE lines SET verified=1 WHERE id=?", (match["id"],))
        conn.commit()
        return "ok", f"Correct: {match['name']} ({match['variant']})"
    if any(l["sku"] == code for l in lines):
        return "dup", "You already checked this item."
    scanned = one(conn, "SELECT * FROM products WHERE sku=?", (code,))
    expected = [l for l in lines if not l["verified"]]
    exp_txt = " or ".join(f"{l['name']} ({l['variant']})" for l in expected)
    if scanned:
        detail = f"Scanned {scanned['name']} ({scanned['variant']}) but the order needs {exp_txt}."
    else:
        detail = f"Scanned code {code} is not a known item. The order needs {exp_txt}."
    add_issue(conn, "WRONG_ITEM", oid, code, detail, "high", now, owner=packer)
    log(conn, oid, "Wrong item caught at packing: " + detail, now, packer)
    conn.commit()
    return "bad", detail


def finish_pack(conn, oid, packer, now):
    left = one(conn, "SELECT COUNT(*) n FROM lines WHERE order_id=? AND verified=0", (oid,))["n"]
    if left:
        return False
    lane = one(conn, "SELECT c.lane FROM orders o JOIN couriers c ON c.id=o.courier_id WHERE o.id=?", (oid,))["lane"]
    conn.execute("UPDATE orders SET status='PACKED', packer=? WHERE id=?", (packer, oid))
    log(conn, oid, f"Packed and label attached. Take to {lane}", now, packer)
    conn.commit()
    return True


# ---------- staging & dispatch ----------
def check_in(conn, oid, actor, now):
    lane = one(conn, "SELECT c.lane FROM orders o JOIN couriers c ON c.id=o.courier_id WHERE o.id=?", (oid,))["lane"]
    conn.execute("UPDATE orders SET status='STAGED', staged_at=? WHERE id=?", (fmt(now), oid))
    log(conn, oid, f"Box checked into {lane}", now, actor)
    conn.commit()


def report_misplaced(conn, oid, actor, now):
    o = one(conn, "SELECT c.lane FROM orders o JOIN couriers c ON c.id=o.courier_id WHERE o.id=?", (oid,))
    conn.execute("UPDATE orders SET status='PACKED', staged_at=NULL WHERE id=?", (oid,))
    detail = f"Box for {oid} is not in {o['lane']}. Search the warehouse, or repack if it cannot be found."
    log(conn, oid, "Box missing from lane", now, actor)
    add_issue(conn, "MISPLACED_BOX", oid, None, detail, "high", now, owner=actor)
    conn.commit()


def handover(conn, order_ids, actor, now):
    for oid in order_ids:
        conn.execute("UPDATE orders SET status='SHIPPED', shipped_at=? WHERE id=?", (fmt(now), oid))
        log(conn, oid, "Handed to courier", now, actor)
    conn.commit()


def missed_pickup(conn, order_ids, actor, now):
    for oid in order_ids:
        o = one(conn, "SELECT o.*, c.pickup, c.name cname FROM orders o JOIN couriers c ON c.id=o.courier_id WHERE o.id=?", (oid,))
        c = {"pickup": o["pickup"]}
        newp = next_pickup(c, now, lead=15)
        conn.execute("UPDATE orders SET pickup_at=? WHERE id=?", (fmt(newp), oid))
        detail = f"{oid} was not ready when {o['cname']} collected. Moved to the next pickup: {when(newp, now)}."
        log(conn, oid, "Missed courier pickup. Rescheduled", now, actor)
        add_issue(conn, "MISSED_PICKUP", oid, None, detail, "high", now, owner="Priya")
    conn.commit()


def lane_groups(conn, now):
    """Per courier: the next pickup with boxes waiting, plus boxes whose pickup already passed (missed)."""
    out = []
    for c in q(conn, "SELECT * FROM couriers ORDER BY pickup"):
        rows = q(
            conn,
            "SELECT * FROM orders WHERE courier_id=? AND status NOT IN ('SHIPPED','NEW') ORDER BY pickup_at",
            (c["id"],),
        )
        missed = [r for r in rows if parse(r["pickup_at"]) < now - timedelta(minutes=30)]
        live = [r for r in rows if r not in missed]
        if live:
            first = live[0]["pickup_at"]
            group = [r for r in live if r["pickup_at"] == first]
            later = len(live) - len(group)
            pickup = parse(first)
        else:
            group, later, pickup = [], 0, next_pickup(c, now, lead=0)
        out.append({"courier": c, "pickup": pickup, "orders": group, "later": later, "missed": missed})
    return out


# ---------- issues ----------
def resolve_issue(conn, iid, note, owner, now):
    conn.execute(
        "UPDATE issues SET status='resolved', resolved_at=?, note=?, owner=? WHERE id=?",
        (fmt(now), note, owner, iid),
    )
    conn.commit()


def restock_and_release(conn, iid, qty, owner, now):
    i = one(conn, "SELECT * FROM issues WHERE id=?", (iid,))
    conn.execute("UPDATE inventory SET main_qty=main_qty+? WHERE sku=?", (qty, i["sku"]))
    oid = i["order_id"]
    conn.execute("UPDATE lines SET status='pending' WHERE order_id=? AND status='short'", (oid,))
    picked = one(conn, "SELECT COALESCE(SUM(picked_qty),0) n FROM lines WHERE order_id=?", (oid,))["n"]
    conn.execute(
        "UPDATE orders SET status=?, hold_reason=NULL, picker=NULL WHERE id=?",
        ("PICKING" if picked else "LABELLED", oid),
    )
    log(conn, oid, f"Hold released after adding {qty} x {i['sku']} to stock", now, owner)
    resolve_issue(conn, iid, f"Added {qty} to stock and released the order", owner, now)


# ---------- live alerts ----------
def live_alerts(conn, now):
    alerts = []
    orders = open_orders(conn, now)
    overdue = [o for o in orders if o["risk"]["level"] == "overdue"]
    late = [o for o in orders if o["risk"]["level"] == "late"]
    if overdue:
        alerts.append({"level": "high", "title": f"{len(overdue)} orders are past their ship-by time",
                       "detail": ", ".join(o["id"] for o in overdue[:6]), "page": "Office board"})
    if late:
        alerts.append({"level": "high", "title": f"{len(late)} orders will miss their cutoff at the current pace",
                       "detail": ", ".join(o["id"] for o in late[:6]), "page": "Office board"})
    for g in lane_groups(conn, now):
        if g["missed"]:
            alerts.append({"level": "high",
                           "title": f"{g['courier']['lane']}: {len(g['missed'])} box(es) missed an earlier {g['courier']['name']} pickup",
                           "detail": ", ".join(o["id"] for o in g["missed"][:6]), "page": "Staging & pickup"})
        mins = (g["pickup"] - now).total_seconds() / 60
        notready = [o for o in g["orders"] if o["status"] != "STAGED"]
        if notready and mins <= 90:
            lvl = "high" if mins <= 45 else "medium"
            when_txt = f"in {dur(mins)}" if mins >= 0 else f"{dur(mins)} ago"
            alerts.append({
                "level": lvl,
                "title": f"{g['courier']['lane']} ({g['courier']['name']}): {len(notready)} box(es) not in the lane, pickup {when_txt}",
                "detail": ", ".join(o["id"] for o in notready[:6]), "page": "Staging & pickup"})
    for t in q(conn, "SELECT * FROM transfers WHERE status='requested'"):
        age = (now - parse(t["created_at"])).total_seconds() / 60
        if age > 30:
            alerts.append({"level": "medium", "title": f"Stock move waiting {dur(age)}: {t['qty']} x {t['sku']}",
                           "detail": f"Order {t['order_id']}", "page": "Picking"})
    return alerts
