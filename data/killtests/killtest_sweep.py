"""KILL-TEST sweep — WHICH stop rule survives on real 10s tape?

The plain intrabar stop's positive result is carried entirely by LGHL, the trade that motivated it
(ex-LGHL it is negative under both fill conventions). So the question is no longer "ship it or not"
but "what shape of stop actually wins". Variants swept on the same cohort:

  CONFIRM s   the breach must persist s seconds before exiting   (INTRABAR_CONFIRM_SECS, already built)
  BUFFER b    exit only once price is b% BELOW the stop          (wick-immune by depth)
  CRATER only exit only at N×R below entry, stop otherwise close-based (the original 7/27 verdict)

Judged on: net dollars (both fill conventions) AND net EX-LGHL, because a rule that only works
because of its own motivating trade has not been shown to work at all.
"""
import json, pathlib, urllib.request, sys
from datetime import datetime, timezone, timedelta

S = pathlib.Path("/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
U = "https://zestful-intuition-production-b16a.up.railway.app"
DATES = ["2026-07-23", "2026-07-24", "2026-07-27"]


def load(tkr, DATE):
    for sfx in ("~ALP10S", "~10S"):
        p = S / f"bars_{DATE}_{tkr}{sfx}.json"
        if not p.exists():
            try:
                d = json.loads(urllib.request.urlopen(
                    f"{U}/api/bars?date={DATE}&ticker={tkr}{sfx}", timeout=60).read())
            except Exception:
                continue
            p.write_text(json.dumps(d))
        d = json.loads(p.read_text())
        out = []
        for b in d.get("bars") or []:
            try:
                t = datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                out.append((t, float(b["low"]), float(b["high"])))
            except Exception:
                pass
        if out:
            return sorted(out)
    return []


trades = json.loads((S / "trades.json").read_text())
trades = trades if isinstance(trades, list) else trades.get("trades", [])
trades = [t for t in trades if t.get("date") in DATES and (t.get("entry_session") or "") != "PRE"]
fills = []
for D in DATES:
    fn = S / ("dec27.json" if D == "2026-07-27" else f"dec_{D}.json")
    if fn.exists():
        dd = json.loads(fn.read_text()); dd = dd if isinstance(dd, list) else dd.get("rows", [])
        fills += [r for r in dd if r.get("status") == "filled"]

used, cohort = set(), []
for t in sorted(trades, key=lambda x: x.get("recorded_at") or ""):
    c = [(i, f) for i, f in enumerate(fills) if i not in used and f["ticker"] == t["ticker"]
         and abs(float(f.get("price") or 0) - float(t["entry"])) <= 0.011]
    if not c:
        continue
    i, f = min(c, key=lambda x: x[1]["recorded_at"]); used.add(i)
    t["_stamp"] = datetime.fromisoformat(f["recorded_at"]).astimezone(timezone.utc)
    t["_fpx"] = float(f["price"]); t["_bars"] = load(t["ticker"], t["date"])
    if t["_bars"]:
        cohort.append(t)


def run(t, confirm_s=0.0, buffer_pct=0.0, crater_r=None, conservative=False):
    """Return P&L under one stop rule, or None if the rule never triggered (outcome unchanged)."""
    entry = float(t["entry"]); stop0 = float(t.get("stop_loss") or 0); sh = int(t.get("shares") or 0)
    if not (entry > 0 and stop0 > 0 and sh > 0):
        return None
    cands = [b for b in t["_bars"] if b[0] <= t["_stamp"] and b[1] <= t["_fpx"] <= b[2]]
    t0 = cands[-1][0] if cands else t["_stamp"]
    t1 = datetime.fromisoformat(t["recorded_at"]).astimezone(timezone.utc)
    seq = [b for b in t["_bars"] if t0 <= b[0] <= t1]
    if not seq:
        return None
    pend = [(int(q), float(p)) for q, p in (t.get("partial_fills") or [])]
    banked, sold, stop, n, since = 0.0, 0, stop0, 0, None
    for ts, lo, hi in seq:
        while pend and hi >= pend[0][1]:
            q, px = pend.pop(0); banked += (px - entry) * q; sold += q; n += 1
            if n >= 2:                       # BE floor as it was that day
                stop = max(stop, entry)
        trigger = (entry - crater_r * (entry - stop0)) if crater_r else stop * (1.0 - buffer_pct)
        if lo <= trigger:
            if since is None:
                since = ts
            if (ts - since).total_seconds() >= confirm_s:
                px = min(lo, trigger) if conservative else trigger
                return banked + (px - entry) * (sh - sold), t["ticker"]
        else:
            since = None
    return None


def score(**kw):
    tot_o = tot_c = ex_o = ex_c = 0.0
    fired = 0
    for t in cohort:
        A = float(t.get("pnl") or 0)
        o = run(t, conservative=False, **kw); c = run(t, conservative=True, **kw)
        O = o[0] if o else A; C = c[0] if c else A
        fired += 1 if o else 0
        tot_o += O - A; tot_c += C - A
        if t["ticker"] != "LGHL":
            ex_o += O - A; ex_c += C - A
    return tot_o, tot_c, ex_o, ex_c, fired


print(f"cohort n = {len(cohort)}  (7/23, 7/24, 7/27 RTH — every trade with 10s tape AND a fill time)")
print(f"recorded total = {sum(float(t.get('pnl') or 0) for t in cohort):+.2f}\n")
print("Δ vs recorded, in dollars. 'ex-LGHL' removes the one trade the change was written for.")
print("=" * 92)
print(f"{'rule':34}{'Δ opt':>10}{'Δ cons':>10}{'ex-LGHL opt':>14}{'ex-LGHL cons':>14}{'fired':>7}")
print("=" * 92)

rows = []
for s in (0, 10, 20, 30, 60):
    r = score(confirm_s=float(s))
    rows.append((f"intrabar, confirm {s}s", r))
for b in (0.005, 0.01, 0.02, 0.03):
    r = score(buffer_pct=b)
    rows.append((f"intrabar, buffer {b*100:.1f}% below stop", r))
for cr in (1.5, 2.0, 2.5):
    r = score(crater_r=cr)
    rows.append((f"crater floor only, {cr}R below entry", r))

for name, (o, c, xo, xc, f) in rows:
    flag = "  <-- positive both ways, ex-LGHL" if xo > 0 and xc > 0 else ""
    print(f"{name:34}{o:+10.2f}{c:+10.2f}{xo:+14.2f}{xc:+14.2f}{f:7d}{flag}")
print("=" * 92)
