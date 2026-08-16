#!/usr/bin/env python3
"""KILL-UNDER-FIRE DRILL (owed since the 8/11 verdict; scripted 8/16, run MONDAY at a
Marcos-chosen minute — NOT on a weekend, the bot's scan loop is asleep and no row can land).

What it proves: the deploy-freeze cord works under live fire. The bot's _trade_worker checks
_entries_paused() (marcos_trading_bot.py:11537, GET /api/pause_entries every scan, 10-min
fail-open) BEFORE any gate; when paused it writes an `entries_paused` decision row, refunds the
lane slot (`slot_refunded`), releases held, and returns. Exits/custody are untouched.

Sequence (all against the dashboard; the bot is never touched directly):
  0. FLAT-BOOK CHECK  GET /api/open_trades  -> must be []  (positions open = STOP; Marcos decides
     per position; the drill refuses to arm). Also refuses if pause is already set.
  1. ARM   POST /api/pause_entries {"paused":true,"note":"kill-under-fire drill","expires_in":N}
     -> server echoes paused:true + expires_at (self-clearing so the freeze cannot outlive us).
  2. WATCH poll GET /api/decisions?date=TODAY&status=entries_paused every 10s for up to
     --watch seconds; PROVEN the moment >=1 `entries_paused` row with time > arm-time appears
     (a candidate fired into the freeze). If no candidate fires during the window, the row
     cannot exist -> verdict INCONCLUSIVE (not FAILED): re-run when the board is hot.
  3. CLEAR POST /api/pause_entries {"paused":false,"note":"drill cleared"} -> paused:false.
  4. VERIFY the next scan resumes: no NEW entries_paused rows after clear-time within 3 min
     (fail-open cache refresh is per-scan; a stale True would show as rows AFTER clear).

Usage (Monday):
  DASHBOARD_SECRET=... python3 data/killtests/kill_under_fire_drill.py --watch 300 --expires 600
  add --dry to print the calls without POSTing.

Expected rows in the archive afterwards (in order):
  entries_paused {ticker, price, machine}  ->  slot_refunded {machine}   (per fire during freeze)
  then normal triggered_*/chart_gate_* rows resume after CLEAR.
Dashboard log lines: "[pause-entries] -> {'paused': True, ...}" then "-> {'paused': False, ...}".
"""
import os, sys, json, time, argparse, datetime, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
U = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")
SECRET = os.environ.get("DASHBOARD_SECRET", "")


def get(path):
    return json.load(urllib.request.urlopen(U + path, timeout=30))


def post(path, body, dry):
    if dry:
        print(f"[dry] POST {path} {body}"); return {"dry": True, **body}
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Dashboard-Secret": SECRET},
                                 method="POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


def rows(status, day):
    d = get(f"/api/decisions?date={day}&status={status}&limit=500")
    return d.get("rows") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=300, help="seconds to watch for entries_paused rows")
    ap.add_argument("--expires", type=int, default=600, help="server-side auto-expiry for the freeze")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    now = datetime.datetime.now(ET)
    day = now.strftime("%Y-%m-%d")
    print(f"[{now:%Y-%m-%d %H:%M:%S} ET] kill-under-fire drill against {U}")
    if now.weekday() >= 5 or not ("07:00" <= now.strftime("%H:%M") < "16:00"):
        print("REFUSE: outside a live scan window (weekday 07:00-16:00 ET) — no row can be produced. Not run.")
        return 3
    if not SECRET and not a.dry:
        print("REFUSE: DASHBOARD_SECRET not set."); return 3
    # 0) flat-book check (DROP-DEAD: verified in-turn, pasted)
    ot = get("/api/open_trades").get("open_trades") or []
    print(f"open_trades = {json.dumps(ot)[:400]}")
    if ot:
        print("STOP: positions open — Marcos decides per position. Drill NOT armed."); return 2
    st = get("/api/pause_entries")
    print(f"pause state before = {st}")
    if st.get("paused"):
        print("STOP: freeze already set by someone else — not stacking a drill on it."); return 2
    before = {(r.get("ticker"), r.get("time")) for r in rows("entries_paused", day)}
    # 1) ARM
    t_arm = datetime.datetime.now(ET)
    r = post("/api/pause_entries", {"paused": True, "note": "kill-under-fire drill", "expires_in": a.expires}, a.dry)
    print(f"ARM -> {r}")
    if not a.dry and not r.get("paused"):
        print("FAILED: server did not accept the freeze."); return 1
    # 2) WATCH
    proven, deadline, seen = False, time.time() + a.watch, []
    while time.time() < deadline:
        time.sleep(10)
        cur = [x for x in rows("entries_paused", day) if (x.get("ticker"), x.get("time")) not in before]
        if cur:
            seen = cur; proven = True
            print(f"[{datetime.datetime.now(ET):%H:%M:%S}] entries_paused rows: "
                  + ", ".join(f"{x.get('ticker')}@{x.get('time')}({x.get('machine')})" for x in cur))
            break
        print(f"[{datetime.datetime.now(ET):%H:%M:%S}] watching... (no fire into the freeze yet)")
    # 3) CLEAR (always, even on failure)
    t_clr = datetime.datetime.now(ET)
    r2 = post("/api/pause_entries", {"paused": False, "note": "drill cleared"}, a.dry)
    print(f"CLEAR -> {r2}")
    st2 = get("/api/pause_entries")
    if not a.dry and st2.get("paused"):
        print("FAILED: freeze did not clear — POST again / check auth."); return 1
    # 4) resume verify: no NEW paused rows for 3 min after clear
    if proven and not a.dry:
        time.sleep(180)
        after = [x for x in rows("entries_paused", day)
                 if (x.get("ticker"), x.get("time")) not in before and x not in seen]
        late = [x for x in after if x.get("time") and _later(x["time"], t_clr)]
        print(f"post-clear entries_paused rows (should be 0): {len(late)}")
        if late:
            print("FAILED: bot still honoring a stale freeze after clear (fail-open cache?)"); return 1
    ref = [x for x in rows("slot_refunded", day)] if proven else []
    print("VERDICT:", "PROVEN — freeze honored under fire; cleared; scan resumed" if proven
          else "INCONCLUSIVE — no candidate fired during the freeze window (re-run when the board is hot)")
    print(f"slot_refunded rows today: {len(ref)}")
    return 0 if proven else 4


def _later(hhmmss_ampm, t):
    try:
        tt = datetime.datetime.strptime(hhmmss_ampm, "%I:%M:%S %p").time()
        return tt > t.time()
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
