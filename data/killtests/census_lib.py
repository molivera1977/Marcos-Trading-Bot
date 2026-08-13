"""Shared helpers for row censuses — 8/13 (the 12-hour clock bug: decision-store times are
'02:54:01 PM' strings; naive 24h string compares silently match nothing / mis-window).
EVERY census imports these; no census hand-rolls time handling again."""
import json, urllib.request
from datetime import datetime

BASE = "https://zestful-intuition-production-b16a.up.railway.app"

def to24(t):
    """'02:54:01 PM' -> '14:54:01'; passes through 24h strings; '' on garbage."""
    t = str(t or "").strip()
    for f in ("%I:%M:%S %p", "%H:%M:%S", "%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(t, f).strftime("%H:%M:%S")
        except ValueError:
            pass
    return ""

def rows_for(date, limit=50000):
    d = json.load(urllib.request.urlopen(f"{BASE}/api/decisions_archive?date={date}&limit={limit}", timeout=90))
    rows = d.get("decisions") or d.get("rows") or []
    for r in rows:
        r["_t24"] = to24(r.get("time") or r.get("time_hm"))
    return rows

def trades(since=None):
    tr = json.load(urllib.request.urlopen(BASE + "/api/trades", timeout=60)).get("trades") or []
    return [t for t in tr if (t.get("date") or "") >= since] if since else tr

def px_of(r):
    v = r.get("price") or r.get("px")
    try: return float(v)
    except (TypeError, ValueError): return None
