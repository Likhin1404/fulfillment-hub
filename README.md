# XYZ Fulfillment Hub
Live app: https://fulfillment-appgit-karmicseed.streamlit.app/

A small Streamlit app that gives XYZ one place to see every order, work backwards from courier cutoffs,
and catch stock, packing and pickup problems before they reach a customer.

## Run it

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

The sample database (about 260 orders, 52 products, 3 couriers, 2 warehouses) is created automatically on
first run. Use **Reset demo data** in the sidebar to start over, or `python seed.py` to rebuild from the terminal.

To host it free: push this folder to GitHub and deploy `app.py` on Streamlit Community Cloud.

## The idea

Every order has a **ship-by time**, and every label has a **courier pickup time**. The app works backwards from
that deadline, estimates the work left in the order's current stage, and ranks everything by how close it is to
missing the cutoff. One idea drives prioritisation, delay visibility and missed pickups.

| XYZ problem | What the app does |
|---|---|
| Can't see order status | Office board with a stage strip and a risk ranking. Order lookup shows a tracker and full history. |
| Delays go unnoticed | Red / amber / green risk on every order, plus "Needs action now" alerts. |
| Priority orders get mixed in | Priority is a deadline, not a tag. Ranking and the pick queue sort by time left. |
| Stock missing or can't be found | "Can't find it" button: corrects the count, looks in the overflow warehouse, requests a move, or puts the order on hold. Labels also trigger moves early. |
| Wrong product or variant shipped | Packing screen requires a scan of each item. A wrong size or colour stops the packer and logs an issue. |
| Boxes misplaced, pickup missed | One lane per courier with a countdown. Boxes count as ready only when checked into the lane. Handover is a checklist. Unready boxes are logged and moved to the next pickup. |
| Problems handled informally | Issues inbox with owner, status and resolution note. Most issues are created automatically. |

## Screens

- **Office:** Office board, New orders (bulk labels), Issues, Stock, Order lookup
- **Warehouse (large buttons, one task at a time):** Picking, Packing, Staging & pickup

## Demo clock

The sidebar has a **Demo time** slider (starts at 12:30). Move it forward to watch orders turn amber and red and
lane pickups approach. Turn on **Use the real clock** to run live.

## Demo script

1. **Office board:** note the backlog orders from two days ago that nobody noticed.
2. **New orders:** create labels in bulk. The app picks the cheapest courier that still makes each cutoff.
3. **Picking** (as Asha): start the order marked in the in-app *Demo guide*, tap *Can't find it*, then complete the stock move in the *Stock moves* tab.
4. **Picking:** repeat with the second ghost-stock order. It goes on hold. Fix it in **Issues**.
5. **Packing:** open the demo order and scan the wrong size.
6. **Staging & pickup:** move the clock to 13:45, then confirm a handover at 14:15.

## Files

- `app.py` UI. `core.py` all business rules (no UI code). `seed.py` sample data generator.

## Scope choices

Left out on purpose: real courier and marketplace integrations, inbound receiving, invoicing, analytics,
user login, and weekends or holidays in pickup schedules. Each is valuable, but none is the cause of XYZ's
daily missed deadlines.
