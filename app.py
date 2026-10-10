"""XYZ Fulfillment Hub. Run with:  streamlit run app.py"""
import html
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

import core
import seed

st.set_page_config(page_title="XYZ Fulfillment Hub", page_icon="📦", layout="wide")


@st.cache_resource
def get_conn():
    conn = core.connect()
    has_data = conn.execute("SELECT name FROM sqlite_master WHERE name='orders'").fetchone()
    if not has_data or not conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]:
        seed.seed(conn)
    return conn


conn = get_conn()

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap');
html, body, .stApp, .stApp * { font-family: 'Atkinson Hyperlegible', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; }
.block-container { padding-top: 1.6rem; max-width: 1280px; }
h1 { font-weight: 700; letter-spacing: -0.01em; margin-bottom: .2rem; }
.sub { color: #4C6169; margin: 0 0 1rem 0; }
.pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-weight: 700; font-size: .85rem; white-space: nowrap; }
.pill-ok { background: #D7EEDF; color: #0F4D2A; }
.pill-tight { background: #FBE7A8; color: #5F4100; }
.pill-late { background: #F6C7C1; color: #7D1409; }
.pill-overdue { background: #8E1B12; color: #fff; }
.pill-done { background: #E1E6E5; color: #36474D; }
.pill-prio { background: #14262B; color: #fff; }
.pill-hold { background: #E6D5F5; color: #3F1D66; }
.stages { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin: .4rem 0 1.2rem 0; }
.stage { background: #fff; border: 1px solid #D5DEDB; border-left: 6px solid #9DB0AA; border-radius: 6px; padding: 8px 10px; }
.stage.s-ok { border-left-color: #2E7D4F; }
.stage.s-tight { border-left-color: #D9A400; }
.stage.s-late { border-left-color: #C9372C; }
.stage.s-overdue { border-left-color: #8E1B12; background: #FFF3F1; }
.stage .n { font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
.stage .l { font-size: .9rem; color: #36474D; }
.stage .r { font-size: .8rem; color: #8E1B12; font-weight: 700; min-height: 1.1em; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 1rem; }
.kpi { background: #fff; border: 1px solid #D5DEDB; border-radius: 6px; padding: 10px 12px; }
.kpi .n { font-size: 1.6rem; font-weight: 700; }
.kpi .l { font-size: .9rem; color: #36474D; }
table.tbl { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #D5DEDB; border-radius: 6px; font-size: .95rem; }
table.tbl th { text-align: left; background: #E8EEEC; padding: 7px 10px; font-weight: 700; }
table.tbl td { padding: 7px 10px; border-top: 1px solid #E3EAE8; vertical-align: top; }
.alert { border-left: 6px solid #C9372C; background: #FFF3F1; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; }
.alert.medium { border-left-color: #D9A400; background: #FFF9E6; }
.alert b { display: block; }
.alert span { color: #4C6169; font-size: .9rem; }
.card { background: #fff; border: 1px solid #D5DEDB; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; }
.loc { background: #14262B; color: #fff; font-size: 4.2rem; font-weight: 700; letter-spacing: .06em; text-align: center; border-radius: 10px; padding: 8px 0; margin: 6px 0 10px 0; }
.item-name { font-size: 2rem; font-weight: 700; line-height: 1.15; }
.variant { display: inline-block; background: #FBE7A8; color: #3B2A00; font-size: 1.6rem; font-weight: 700; padding: 2px 14px; border-radius: 8px; margin-top: 4px; }
.qty { font-size: 2.4rem; font-weight: 700; }
.label { background: #fff; border: 2px dashed #14262B; border-radius: 6px; padding: 12px 16px; font-size: 1.05rem; line-height: 1.5; }
.label .big { font-size: 1.7rem; font-weight: 700; }
.tracker { display: flex; gap: 4px; margin: .5rem 0 1rem 0; }
.tracker div { flex: 1; text-align: center; padding: 6px 2px; background: #E3EAE8; color: #4C6169; border-radius: 4px; font-size: .85rem; }
.tracker div.done { background: #2E7D4F; color: #fff; }
.tracker div.now { background: #14262B; color: #fff; font-weight: 700; }
[data-testid="stSidebar"] { background: #E8EEEC; }
:focus-visible { outline: 3px solid #0B6E4F !important; outline-offset: 2px; }
@media (max-width: 900px) { .stages { grid-template-columns: repeat(4, 1fr); } .kpis { grid-template-columns: repeat(2, 1fr); } .loc { font-size: 3rem; } }
</style>
"""
BIG_BUTTONS = """
<style>
.stButton > button, .stFormSubmitButton > button { min-height: 3.4rem; font-size: 1.25rem; font-weight: 700; width: 100%; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def big_buttons():
    st.markdown(BIG_BUTTONS, unsafe_allow_html=True)


# ---------- demo clock ----------
demo_date = datetime.strptime(core.get_setting(conn, "demo_date"), "%Y-%m-%d")
times = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 15, 30, 45)]
with st.sidebar:
    st.markdown("### 📦 XYZ Fulfillment Hub")
    use_real = st.toggle("Use the real clock", value=False, help="Off: you control the time to see how the day unfolds.")
    if use_real:
        NOW = datetime.now().replace(second=0, microsecond=0)
        st.caption(f"Now: {NOW:%a %H:%M}")
    else:
        t = st.select_slider("Demo time", options=times, value="12:30", key="demo_time")
        h, m = map(int, t.split(":"))
        NOW = demo_date.replace(hour=h, minute=m)
        st.caption(f"Demo day: {NOW:%A %d %b}. Move the slider to jump forward in the day.")

OPEN = core.open_orders(conn, NOW)
n_new = sum(o["status"] == "NEW" for o in OPEN)
n_pick = sum(o["status"] == "LABELLED" or (o["status"] == "PICKING" and not o["picker"]) for o in OPEN)
n_pack = sum(o["status"] == "PICKED" for o in OPEN)
n_issues = core.one(conn, "SELECT COUNT(*) n FROM issues WHERE status='open'")["n"]
PAGES = ["Office board", "New orders", "Picking", "Packing", "Staging & pickup", "Issues", "Stock", "Order lookup"]
COUNTS = {"New orders": n_new, "Picking": n_pick, "Packing": n_pack, "Issues": n_issues}


def pill(level, text):
    return f'<span class="pill pill-{level}">{html.escape(text)}</span>'


def flash(kind, msg):
    st.session_state["flash"] = (kind, msg)


def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        {"ok": st.success, "warn": st.warning, "err": st.error, "info": st.info}[f[0]](f[1])


def item_text(oid):
    return ", ".join(f"{l['qty']} x {l['name']} ({l['variant']})" for l in core.order_items(conn, oid))


with st.sidebar:
    page = st.radio("Go to", PAGES, format_func=lambda p: f"{p} ({COUNTS[p]})" if COUNTS.get(p) else p, key="page")
    with st.expander("Demo guide"):
        notes = json.loads(core.get_setting(conn, "demo_notes", "{}"))
        st.markdown(
            f"""
**Try these stories** (clock starts at 12:30)

- **Stock that is not there.** *Picking* (as Asha), choose `{notes.get('ghost_transfer')}` under *Or start a specific order*. The shelf is empty, tap *Can't find it*. The app finds stock in the overflow warehouse and asks for a move.
- **No stock anywhere.** Start `{notes.get('ghost_hold')}` the same way and tap *Can't find it*. The order goes on hold and the office is told. Fix it in *Issues*.
- **Wrong variant.** *Packing*, open `{notes.get('pack_demo')}`. Use the demo scanner to scan the wrong size.
- **Missed pickup.** Move the clock to 13:45. *Staging & pickup* shows Lane A boxes still not ready.
- **Unnoticed delays.** *Office board* already shows backlog orders from two days ago.
- **Label in bulk.** *New orders*: one click makes labels with the cheapest courier that still makes the cutoff.
"""
        )
    if st.button("Reset demo data"):
        seed.seed(conn)
        st.session_state.clear()
        st.rerun()


# =====================================================================
# Office board
# =====================================================================
def page_board():
    st.title("Office board")
    st.markdown(f'<p class="sub">Everything that is not shipped yet, ranked by how close it is to missing its courier cutoff. It is {NOW:%A %H:%M}.</p>', unsafe_allow_html=True)
    show_flash()

    shipped_today = core.one(conn, "SELECT COUNT(*) n FROM orders WHERE shipped_at LIKE ?", (f"{NOW:%Y-%m-%d}%",))["n"]
    tiles = []
    for key in ["NEW", "LABELLED", "PICKING", "PICKED", "PACKED", "STAGED", "ON_HOLD"]:
        group = [o for o in OPEN if o["status"] == key]
        worst = min((o["risk"]["level"] for o in group), key=lambda l: core.RISK_ORDER[l], default="")
        bad = sum(o["risk"]["level"] in ("overdue", "late") for o in group)
        tiles.append(f'<div class="stage s-{worst}"><div class="n">{len(group)}</div><div class="l">{core.STAGE_NAME[key]}</div><div class="r">{f"{bad} at risk" if bad else ""}</div></div>')
    tiles.append(f'<div class="stage s-ok"><div class="n">{shipped_today}</div><div class="l">Shipped today</div><div class="r"></div></div>')
    st.markdown('<div class="stages">' + "".join(tiles) + "</div>", unsafe_allow_html=True)

    overdue = sum(o["risk"]["level"] == "overdue" for o in OPEN)
    late = sum(o["risk"]["level"] == "late" for o in OPEN)
    prio_open = sum(bool(o["priority"]) for o in OPEN)
    st.markdown(
        '<div class="kpis">'
        f'<div class="kpi"><div class="n">{overdue}</div><div class="l">Past their ship-by time</div></div>'
        f'<div class="kpi"><div class="n">{late}</div><div class="l">Will miss cutoff at this pace</div></div>'
        f'<div class="kpi"><div class="n">{prio_open}</div><div class="l">Priority orders still open</div></div>'
        f'<div class="kpi"><div class="n">{n_issues}</div><div class="l">Open issues</div></div></div>',
        unsafe_allow_html=True,
    )

    alerts = core.live_alerts(conn, NOW)
    if alerts:
        st.subheader("Needs action now")
        for a in alerts:
            st.markdown(f'<div class="alert {a["level"]}"><b>{html.escape(a["title"])}</b><span>{html.escape(a["detail"])}. Go to {a["page"]}.</span></div>', unsafe_allow_html=True)

    st.subheader("Most urgent orders")
    why = {
        "NEW": "No label yet", "LABELLED": "Waiting to be picked", "PICKING": "Being picked",
        "PICKED": "Waiting for a packer", "PACKED": "Packed, not in the courier lane yet", "STAGED": "In lane, waiting for courier",
    }
    rows = []
    for o in OPEN[:12]:
        reason = o["hold_reason"] if o["status"] == "ON_HOLD" else why.get(o["status"], "")
        if o["status"] == "PICKING" and o["picker"]:
            reason = f"Being picked by {o['picker']}"
        r = o["risk"]
        rows.append(
            "<tr>"
            f"<td><b>{o['id']}</b> {pill('prio', 'Priority') if o['priority'] else ''}</td>"
            f"<td>{core.STAGE_NAME[o['status']]}</td>"
            f"<td>{html.escape(reason or '')}</td>"
            f"<td>{html.escape(o['courier'] or '-')}</td>"
            f"<td>{core.when(r['deadline'], NOW)}</td>"
            f"<td>{pill(r['level'], r['text'])}</td></tr>"
        )
    st.markdown(
        '<table class="tbl"><tr><th>Order</th><th>Stage</th><th>What is holding it</th><th>Courier</th><th>Due</th><th>Status</th></tr>' + "".join(rows) + "</table>",
        unsafe_allow_html=True,
    )

    with st.expander(f"All {len(OPEN)} open orders"):
        c1, c2, c3 = st.columns(3)
        stage_f = c1.multiselect("Stage", [core.STAGE_NAME[s] for s in core.STAGES[:-1]] + ["On hold"])
        prio_f = c2.toggle("Priority only")
        risk_f = c3.toggle("At risk only")
        inv_stage = {v: k for k, v in core.STAGE_NAME.items()}
        data = []
        for o in OPEN:
            if stage_f and o["status"] not in [inv_stage[s] for s in stage_f]:
                continue
            if prio_f and not o["priority"]:
                continue
            if risk_f and o["risk"]["level"] not in ("overdue", "late", "tight"):
                continue
            data.append({
                "Order": o["id"], "Priority": "Yes" if o["priority"] else "", "Stage": core.STAGE_NAME[o["status"]],
                "Courier": o["courier"] or "", "Due": core.when(o["risk"]["deadline"], NOW), "Risk": o["risk"]["text"],
                "Channel": o["channel"], "City": o["city"],
            })
        st.dataframe(pd.DataFrame(data), hide_index=True)


# =====================================================================
# Office: new orders -> labels
# =====================================================================
def page_new():
    st.title("New orders")
    st.markdown('<p class="sub">Create labels in bulk. Each row starts with the cheapest courier that is fast enough and still makes the cutoff. Change it if you know better.</p>', unsafe_allow_html=True)
    show_flash()
    couriers = core.q(conn, "SELECT * FROM couriers")
    by_name = {c["name"]: c for c in couriers}
    only_prio = st.toggle("Priority orders only", value=False)
    orders = [o for o in OPEN if o["status"] == "NEW" and (o["priority"] or not only_prio)]
    if not orders:
        st.success("No new orders waiting. Everything has a label.")
        return
    rows = []
    for o in orders:
        opt, ok = core.suggest_courier(couriers, o, NOW)
        rows.append({
            "Create": True, "Order": o["id"], "Priority": "Priority" if o["priority"] else "",
            "Items": item_text(o["id"]), "Ship by": core.when(core.parse(o["ship_by"]), NOW),
            "Courier": opt["courier"]["name"], "Pickup": core.when(opt["pickup"], NOW),
            "Cost": opt["courier"]["cost"], "Heads up": "" if ok else "No courier makes the cutoff",
        })
    edited = st.data_editor(
        pd.DataFrame(rows), hide_index=True, key=f"new_{only_prio}_{len(rows)}",
        disabled=["Order", "Priority", "Items", "Ship by", "Pickup", "Cost", "Heads up"],
        column_config={
            "Create": st.column_config.CheckboxColumn(width="small"),
            "Courier": st.column_config.SelectboxColumn(options=list(by_name), required=True),
            "Cost": st.column_config.NumberColumn(format="₹%d", width="small"),
        },
    )
    chosen = edited[edited["Create"]]
    order_map = {o["id"]: o for o in orders}
    warnings = []
    for _, r in chosen.iterrows():
        o, c = order_map[r["Order"]], by_name[r["Courier"]]
        p = core.next_pickup(c, NOW)
        if p > core.parse(o["ship_by"]):
            warnings.append(f"{o['id']}: {c['name']} picks up {core.when(p, NOW)}, after the ship-by time ({core.when(core.parse(o['ship_by']), NOW)}).")
        if c["days"] > o["promised_days"]:
            warnings.append(f"{o['id']}: {c['name']} takes {c['days']} days but the customer was promised {o['promised_days']}.")
    for w in warnings[:8]:
        st.warning(w)
    if len(warnings) > 8:
        st.warning(f"...and {len(warnings) - 8} more warnings.")
    cost = int(chosen["Cost"].sum()) if len(chosen) else 0
    if st.button(f"Create {len(chosen)} labels (shipping ₹{cost})", type="primary", disabled=len(chosen) == 0):
        msgs = []
        for _, r in chosen.iterrows():
            ok, notes_ = core.create_label(conn, r["Order"], by_name[r["Courier"]]["id"], NOW, "Priya")
            msgs += notes_
        flash("warn" if msgs else "ok", f"Created {len(chosen)} labels." + ("  Stock actions: " + "; ".join(msgs[:5]) if msgs else " Stock looks fine for all of them."))
        st.rerun()


# =====================================================================
# Warehouse: picking
# =====================================================================
def page_pick():
    big_buttons()
    st.title("Picking")
    show_flash()
    me = st.radio("Who is picking?", core.PICKERS, horizontal=True, key="picker")
    transfers = core.q(
        conn,
        "SELECT t.*, p.name, p.variant, p.location, p.overflow_loc FROM transfers t JOIN products p ON p.sku=t.sku "
        "WHERE t.status='requested' ORDER BY t.created_at",
    )
    tab_pick, tab_moves = st.tabs(["Pick list", f"Stock moves ({len(transfers)})"])

    with tab_pick:
        active = next((o for o in OPEN if o["status"] == "PICKING" and o["picker"] == me), None)
        if active:
            items = core.order_items(conn, active["id"])
            todo = [l for l in items if l["status"] == "pending"]
            waiting = [l for l in items if l["status"] == "waiting"]
            done = sum(l["status"] == "picked" for l in items)
            r = active["risk"]
            st.markdown(f'### Order {active["id"]} {pill("prio", "Priority") if active["priority"] else ""} {pill(r["level"], r["text"])}', unsafe_allow_html=True)
            st.progress(done / len(items), text=f"{done} of {len(items)} items picked")
            if todo:
                l = todo[0]
                st.markdown(
                    f'<div class="card"><div class="loc">{l["location"]}</div>'
                    f'<div class="item-name">{html.escape(l["name"])}</div>'
                    f'<div class="variant">{html.escape(l["variant"])}</div>'
                    f'<div class="qty">Take {l["qty"] - l["picked_qty"]}</div></div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                if c1.button("✔ Picked", type="primary", key=f"pk_{l['id']}"):
                    finished = core.pick_line(conn, l["id"], me, NOW)
                    if finished:
                        flash("ok", f"Order {active['id']} is fully picked. Take the basket to Packing.")
                    st.rerun()
                if c2.button("✖ Can't find it", key=f"cf_{l['id']}"):
                    kind, msg = core.cant_find(conn, l["id"], me, NOW)
                    flash("warn" if kind == "transfer" else "err", msg)
                    st.rerun()
            elif waiting:
                st.info("The rest of this order is waiting for a stock move. Park it and start another order.")
                for l in waiting:
                    st.write(f"Waiting: {l['name']} ({l['variant']})")
                if st.button("Park this order and pick something else"):
                    core.park_order(conn, active["id"], me, NOW)
                    st.rerun()
            if len(todo) > 1:
                with st.expander(f"Still to pick in this order ({len(todo) - 1})"):
                    for l in todo[1:]:
                        st.write(f"{l['location']}: {l['qty']} x {l['name']} ({l['variant']})")
        else:
            queue = [o for o in OPEN if o["status"] == "LABELLED" or (o["status"] == "PICKING" and not o["picker"])]
            if not queue:
                st.success("Nothing waiting to be picked. Well done.")
            else:
                st.markdown("Most urgent first. Start at the top unless you have a good reason.")
                for i, o in enumerate(queue[:6]):
                    r = o["risk"]
                    with st.container(border=True):
                        a, b = st.columns([4, 1])
                        a.markdown(
                            f'**{o["id"]}** {pill("prio", "Priority") if o["priority"] else ""} {pill(r["level"], r["text"])}'
                            f'<br>{html.escape(item_text(o["id"]))}<br><small>{o["courier"]} pickup {core.when(r["deadline"], NOW)}</small>',
                            unsafe_allow_html=True,
                        )
                        if b.button("Start" if i else "Start first", type="primary" if i == 0 else "secondary", key=f"st_{o['id']}"):
                            core.start_pick(conn, o["id"], me, NOW)
                            st.rerun()
                if len(queue) > 6:
                    st.caption(f"{len(queue) - 6} more orders in the queue.")
                specific = st.selectbox("Or start a specific order", [""] + [o["id"] for o in queue], key="pick_specific")
                if specific and st.button(f"Start {specific}", key="start_specific", type="primary"):
                    core.start_pick(conn, specific, me, NOW)
                    st.rerun()

    with tab_moves:
        if not transfers:
            st.success("No stock moves needed right now.")
        for t in transfers:
            with st.container(border=True):
                st.markdown(
                    f"**Move {t['qty']} x {t['name']} ({t['variant']})**<br>From overflow warehouse shelf **{t['overflow_loc']}** to main shelf **{t['location']}**"
                    f"<br><small>For order {t['order_id']}, requested {core.when(core.parse(t['created_at']), NOW)}</small>",
                    unsafe_allow_html=True,
                )
                if st.button("Done moving", key=f"tr_{t['id']}", type="primary"):
                    core.complete_transfer(conn, t["id"], me, NOW)
                    flash("ok", "Stock is on the main shelf. The waiting order is back in the pick queue.")
                    st.rerun()


# =====================================================================
# Warehouse: packing
# =====================================================================
def page_pack():
    big_buttons()
    st.title("Packing")
    show_flash()
    me = st.radio("Who is packing?", core.PACKERS, horizontal=True, key="packer")
    queue = [o for o in OPEN if o["status"] == "PICKED"]
    if not queue:
        st.success("Nothing waiting to be packed.")
        return
    ids = [o["id"] for o in queue]
    sel = st.selectbox(
        "Order to pack (most urgent first)", ids,
        format_func=lambda i: f"{i}{'  PRIORITY' if next(o for o in queue if o['id'] == i)['priority'] else ''}",
    )
    o = next(x for x in queue if x["id"] == sel)
    items = core.order_items(conn, sel)
    r = o["risk"]
    st.markdown(f'### Order {sel} {pill("prio", "Priority") if o["priority"] else ""} {pill(r["level"], r["text"])}', unsafe_allow_html=True)

    msg = st.session_state.pop("scan_msg", None)
    if msg:
        {"ok": st.success, "dup": st.info, "bad": st.error}[msg[0]](("STOP. " if msg[0] == "bad" else "") + msg[1])
        if msg[0] == "bad":
            st.caption("Put the wrong item back and fetch the right one. The issue was logged for the office.")

    st.markdown("**Check every item before it goes in the box**")
    for l in items:
        mark = "✅" if l["verified"] else "⬜"
        st.markdown(
            f'<div class="card" style="{"opacity:.55" if l["verified"] else ""}">{mark} <span class="item-name" style="font-size:1.4rem">{l["qty"]} x {html.escape(l["name"])}</span> '
            f'<span class="variant" style="font-size:1.2rem">{html.escape(l["variant"])}</span></div>',
            unsafe_allow_html=True,
        )

    with st.form("scan_form", clear_on_submit=True):
        code = st.text_input("Scan the barcode on the item", placeholder="Scan here")
        if st.form_submit_button("Check item", type="primary"):
            st.session_state["scan_msg"] = core.scan_item(conn, sel, code, me, NOW)
            st.rerun()
    with st.expander("Demo: simulate the barcode scanner"):
        pending = [l for l in items if not l["verified"]]
        c1, c2 = st.columns(2)
        if pending:
            if c1.button("Scan the correct item", key="demo_ok"):
                st.session_state["scan_msg"] = core.scan_item(conn, sel, pending[0]["sku"], me, NOW)
                st.rerun()
            if c2.button("Scan the wrong size or colour", key="demo_bad"):
                sib = core.one(
                    conn,
                    "SELECT sku FROM products WHERE base=? AND sku NOT IN (SELECT sku FROM lines WHERE order_id=?) ORDER BY sku LIMIT 1",
                    (pending[0]["base"], sel),
                )
                st.session_state["scan_msg"] = core.scan_item(conn, sel, sib["sku"], me, NOW)
                st.rerun()
        else:
            st.caption("All items are checked.")

    if all(l["verified"] for l in items):
        c = core.one(conn, "SELECT * FROM couriers WHERE id=?", (o["courier_id"],))
        st.markdown(
            f'<div class="label"><span class="big">{c["name"]}</span><br>Tracking: <b>{o["label_no"]}</b><br>'
            f'{html.escape(o["customer"])}, {o["city"]}<br>{"<b>PRIORITY</b> " if o["priority"] else ""}Pickup {core.when(core.parse(o["pickup_at"]), NOW)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"#### After packing, take the box to **{c['lane']}**")
        if st.button("Box is packed and the label is on", type="primary"):
            core.finish_pack(conn, sel, me, NOW)
            flash("ok", f"Order {sel} packed. Put it in {c['lane']} and check it in on the Staging screen.")
            st.rerun()


# =====================================================================
# Warehouse: staging and pickup
# =====================================================================
def page_staging():
    big_buttons()
    st.title("Staging & pickup")
    st.markdown('<p class="sub">One lane per courier. A box only counts as ready once it is checked into its lane.</p>', unsafe_allow_html=True)
    show_flash()
    who = st.radio("Who is working the lanes?", core.PACKERS + core.PICKERS, horizontal=True, key="lane_user")
    groups = core.lane_groups(conn, NOW)
    cols = st.columns(len(groups))
    for col, g in zip(cols, groups):
        c = g["courier"]
        with col:
            mins = (g["pickup"] - NOW).total_seconds() / 60
            staged = [o for o in g["orders"] if o["status"] == "STAGED"]
            packed = [o for o in g["orders"] if o["status"] == "PACKED"]
            other = [o for o in g["orders"] if o["status"] not in ("STAGED", "PACKED")]
            cd = f"in {core.dur(mins)}" if mins >= 0 else f"was due {core.dur(mins)} ago"
            lvl = "ok" if mins > 60 else ("tight" if mins > 20 else "late")
            st.markdown(
                f'<div class="card"><span class="item-name" style="font-size:1.6rem">{c["lane"]}</span><br><b>{c["name"]}</b><br>'
                f'Pickup {core.when(g["pickup"], NOW)} {pill(lvl, cd)}<br>'
                f'<span class="qty" style="font-size:1.6rem">{len(staged)}</span> ready, '
                f'<b>{len(packed) + len(other)}</b> not ready</div>',
                unsafe_allow_html=True,
            )
            if g["missed"]:
                st.error(f"{len(g['missed'])} box(es) missed an earlier pickup: {', '.join(o['id'] for o in g['missed'][:4])}")
                if st.button(f"Move {len(g['missed'])} to next pickup", key=f"mv_{c['id']}"):
                    core.missed_pickup(conn, [o["id"] for o in g["missed"]], who, NOW)
                    flash("warn", f"Moved {len(g['missed'])} boxes to the next {c['name']} pickup and logged an issue.")
                    st.rerun()
            for o in packed:
                st.markdown(f"**{o['id']}** is packed. Put it in {c['lane']}.")
                if st.button("Checked into lane", key=f"ci_{o['id']}", type="primary"):
                    core.check_in(conn, o["id"], who, NOW)
                    st.rerun()
            if other:
                with st.expander(f"Still being prepared ({len(other)})"):
                    for o in other:
                        st.write(f"{o['id']}: {core.STAGE_NAME[o['status']]}")
            if g["later"]:
                st.caption(f"{g['later']} more box(es) for later pickups.")
            if staged:
                with st.expander(f"Courier is here: hand over ({len(staged)} ready)"):
                    sel = st.multiselect("Tick the boxes the courier takes", [o["id"] for o in staged],
                                         default=[o["id"] for o in staged], key=f"ho_{c['id']}")
                    lost = [o for o in staged if o["id"] not in sel]
                    unready = [o for o in g["orders"] if o["status"] != "STAGED"]
                    if unready and mins <= 0:
                        st.warning(f"{len(unready)} box(es) are not ready and will be logged as missed.")
                    if lost:
                        st.warning(f"{len(lost)} box(es) not handed over will be logged as missing from the lane.")
                    if st.button(f"Confirm handover of {len(sel)} boxes", key=f"hc_{c['id']}", type="primary"):
                        core.handover(conn, sel, who, NOW)
                        for o in lost:
                            core.report_misplaced(conn, o["id"], who, NOW)
                        if unready and mins <= 0:
                            core.missed_pickup(conn, [o["id"] for o in unready], who, NOW)
                        flash("ok", f"{len(sel)} boxes handed to {c['name']}.")
                        st.rerun()
            elif not packed and not other and not g["missed"]:
                st.caption("Lane is empty.")


# =====================================================================
# Issues
# =====================================================================
ISSUE_NAME = {
    "STOCK_NOT_FOUND": "Stock not found on shelf", "STOCK_SHORT": "Not enough stock", "WRONG_ITEM": "Wrong item caught",
    "MISPLACED_BOX": "Box missing", "MISSED_PICKUP": "Missed pickup", "STOCK_ADJUST": "Stock corrected", "OTHER": "Other problem",
}


def page_issues():
    st.title("Issues")
    st.markdown('<p class="sub">Every problem gets an owner and stays here until someone resolves it, so nothing is lost in a chat message.</p>', unsafe_allow_html=True)
    show_flash()
    alerts = core.live_alerts(conn, NOW)
    if alerts:
        st.subheader("Happening now")
        for a in alerts:
            st.markdown(f'<div class="alert {a["level"]}"><b>{html.escape(a["title"])}</b><span>{html.escape(a["detail"])}. Go to {a["page"]}.</span></div>', unsafe_allow_html=True)

    st.subheader("Open issues")
    everyone = core.OFFICE + core.PICKERS + core.PACKERS
    issues = core.q(conn, "SELECT * FROM issues WHERE status='open' ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at")
    if not issues:
        st.success("No open issues.")
    for i in issues:
        with st.container(border=True):
            a, b = st.columns([3, 2])
            sev = {"high": "late", "medium": "tight", "low": "ok"}[i["severity"]]
            a.markdown(
                f'{pill(sev, ISSUE_NAME.get(i["type"], i["type"]))} &nbsp; **{i["order_id"] or ""}** <small>opened {core.when(core.parse(i["created_at"]), NOW)}</small>'
                f'<br>{html.escape(i["detail"])}',
                unsafe_allow_html=True,
            )
            owner = b.selectbox("Owner", everyone, index=everyone.index(i["owner"]) if i["owner"] in everyone else 0, key=f"ow_{i['id']}")
            held = i["type"] == "STOCK_SHORT" and i["order_id"] and core.one(conn, "SELECT status FROM orders WHERE id=?", (i["order_id"],))["status"] == "ON_HOLD"
            if held:
                qty = b.number_input("Units found or received", min_value=1, value=5, key=f"qt_{i['id']}")
                if b.button("Add stock and release the order", key=f"rl_{i['id']}", type="primary"):
                    core.restock_and_release(conn, i["id"], int(qty), owner, NOW)
                    flash("ok", f"Order {i['order_id']} is back in the pick queue.")
                    st.rerun()
            else:
                note = b.text_input("What was done?", key=f"nt_{i['id']}")
                if b.button("Mark resolved", key=f"rs_{i['id']}", type="primary"):
                    core.resolve_issue(conn, i["id"], note or "Resolved", owner, NOW)
                    st.rerun()

    with st.expander("Log a new problem"):
        with st.form("new_issue", clear_on_submit=True):
            c1, c2 = st.columns(2)
            kind = c1.selectbox("What kind of problem?", ["Damaged item", "Customer address problem", "Courier problem", "Other"])
            oid = c2.text_input("Order number (optional)", placeholder="XYZ-24150")
            detail = st.text_input("What happened?")
            who = st.selectbox("Who is logging this?", everyone)
            if st.form_submit_button("Log problem", type="primary") and detail:
                core.add_issue(conn, "OTHER", oid.strip().upper() or None, None, f"{kind}: {detail}", "medium", NOW, owner=who)
                conn.commit()
                st.rerun()

    with st.expander("Resolved issues"):
        res = core.q(conn, "SELECT created_at, resolved_at, type, order_id, detail, owner, note FROM issues WHERE status='resolved' ORDER BY resolved_at DESC")
        if res:
            df = pd.DataFrame(res)
            df["type"] = df["type"].map(lambda t: ISSUE_NAME.get(t, t))
            st.dataframe(df, hide_index=True)
        else:
            st.caption("Nothing resolved yet.")


# =====================================================================
# Stock
# =====================================================================
def page_stock():
    st.title("Stock")
    st.markdown('<p class="sub">What the system believes is on each shelf, against what open orders still need. Fix a count here after a recount.</p>', unsafe_allow_html=True)
    show_flash()
    rows = core.q(
        conn,
        """SELECT p.sku, p.name, p.variant, p.location, p.overflow_loc, i.main_qty, i.overflow_qty,
        COALESCE((SELECT SUM(l.qty-l.picked_qty) FROM lines l JOIN orders o ON o.id=l.order_id
                  WHERE l.sku=p.sku AND o.status IN ('LABELLED','PICKING','NEW')),0) AS needed
        FROM products p JOIN inventory i ON i.sku=p.sku ORDER BY p.location""",
    )
    for r in rows:
        total = r["main_qty"] + r["overflow_qty"]
        r["Flag"] = "Short" if total < r["needed"] else ("Move from overflow" if r["main_qty"] < r["needed"] else ("Low" if total - r["needed"] < 8 else ""))
    df = pd.DataFrame(rows).rename(columns={
        "sku": "Code", "name": "Product", "variant": "Variant", "location": "Main shelf", "overflow_loc": "Overflow shelf",
        "main_qty": "Main", "overflow_qty": "Overflow", "needed": "Needed by open orders"})
    c1, c2 = st.columns([2, 1])
    text = c1.text_input("Search", placeholder="Product, variant or code")
    only_flag = c2.toggle("Only show problems", value=False)
    if text:
        mask = df.apply(lambda r: text.lower() in " ".join(map(str, r.values)).lower(), axis=1)
        df = df[mask]
    if only_flag:
        df = df[df["Flag"] != ""]
    st.dataframe(df, hide_index=True)
    with st.expander("Correct a count after recounting a shelf"):
        with st.form("fix_stock"):
            sku = st.selectbox("Item", [r["sku"] for r in rows], format_func=lambda s: next(f"{r['name']} ({r['variant']}) - {s}" for r in rows if r["sku"] == s))
            new = st.number_input("Counted on the main shelf", min_value=0, value=0)
            who = st.selectbox("Counted by", core.OFFICE + core.PICKERS)
            if st.form_submit_button("Save the new count", type="primary"):
                core.correct_stock(conn, sku, int(new), NOW, who)
                flash("ok", f"Count for {sku} updated to {int(new)}.")
                st.rerun()


# =====================================================================
# Order lookup
# =====================================================================
def page_lookup():
    st.title("Order lookup")
    st.markdown('<p class="sub">Type an order number to see where it is, who touched it and what is holding it up.</p>', unsafe_allow_html=True)
    oid = st.text_input("Order number", placeholder="XYZ-24150").strip().upper()
    if not oid:
        st.caption("Orders that need attention: " + ", ".join(o["id"] for o in OPEN[:6]))
        return
    o = core.one(conn, "SELECT o.*, c.name AS courier, c.lane FROM orders o LEFT JOIN couriers c ON c.id=o.courier_id WHERE o.id=?", (oid,))
    if not o:
        st.error(f"No order called {oid}. Check the number and try again.")
        return
    o["risk"] = core.order_risk(o, NOW)
    r = o["risk"]
    st.markdown(f'### {oid} {pill("prio", "Priority") if o["priority"] else ""} {pill(r["level"], r["text"])}', unsafe_allow_html=True)
    cur = o["status"]
    stage_idx = core.STAGES.index(cur) if cur in core.STAGES else 1
    html_t = "".join(f'<div class="{"done" if i < stage_idx else ("now" if i == stage_idx else "")}">{core.STAGE_NAME[s]}</div>' for i, s in enumerate(core.STAGES))
    st.markdown(f'<div class="tracker">{html_t}</div>', unsafe_allow_html=True)
    if o["status"] == "ON_HOLD":
        st.error(f"On hold: {o['hold_reason']}")
    a, b = st.columns(2)
    a.markdown(
        f"**Customer:** {o['customer']}, {o['city']}<br>**Channel:** {o['channel']}<br>**Received:** {core.when(core.parse(o['created_at']), NOW)}"
        f"<br>**Ship by:** {core.when(core.parse(o['ship_by']), NOW)}",
        unsafe_allow_html=True,
    )
    b.markdown(
        f"**Courier:** {o['courier'] or 'Not chosen yet'}<br>**Label:** {o['label_no'] or '-'}<br>**Pickup:** {core.when(core.parse(o['pickup_at']), NOW)}"
        f"<br>**Lane:** {o['lane'] or '-'}",
        unsafe_allow_html=True,
    )
    st.markdown("**Items**")
    st.dataframe(pd.DataFrame([{"Qty": l["qty"], "Product": l["name"], "Variant": l["variant"], "Shelf": l["location"], "Picked": l["status"] == "picked", "Checked at packing": bool(l["verified"])} for l in core.order_items(conn, oid)]), hide_index=True)
    st.markdown("**History**")
    ev = core.q(conn, "SELECT ts, text, actor FROM events WHERE order_id=? ORDER BY ts, id", (oid,))
    st.dataframe(pd.DataFrame([{"When": core.when(core.parse(e["ts"]), NOW), "What happened": e["text"], "Who": e["actor"]} for e in ev]), hide_index=True)
    iss = core.q(conn, "SELECT type, detail, status FROM issues WHERE order_id=?", (oid,))
    if iss:
        st.markdown("**Issues**")
        for i in iss:
            st.write(f"{'Open' if i['status'] == 'open' else 'Resolved'} - {ISSUE_NAME.get(i['type'], i['type'])}: {i['detail']}")


{
    "Office board": page_board, "New orders": page_new, "Picking": page_pick, "Packing": page_pack,
    "Staging & pickup": page_staging, "Issues": page_issues, "Stock": page_stock, "Order lookup": page_lookup,
}[page]()
