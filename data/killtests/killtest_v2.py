"""KILL-TEST v2 — the true intrabar stop, on REAL 10s tape (7/27 RTH).

Two corrections to v1, both forced by checks that ran first:

1. PRE ROWS EXCLUDED (5, named below). All five blind-stop exits priced BELOW the day's low on
   BOTH independent 10s feeds — they are off-tape, so their recorded P&L cannot be differenced
   against tape. They are quarantined as a data-integrity incident, not graded as strategy.
2. ENTRY ANCHORED TO THE TAPE, not to the decision row's clock. LGHL's `filled` row is stamped
   04:14:11 but its fill price 1.4903 is the 04:13:00 bar — the stamp lags the acted-on price by
   ~70s. Anchoring on the stamp put the window ~60s late and silently changed the answer. The
   anchor is now the latest bar at/before the stamp whose range contains the fill price.

Fill-price convention is BRACKETED rather than assumed:
   OPTIMISTIC   fill exactly at the stop (what a resting stop would get on calm tape)
   CONSERVATIVE fill at the LOW of the 10s bar that touched (worst case inside that bar)
The truth is between them. Reporting one number alone would be a claim the data can't support.

Arms:  A recorded · B intrabar (stop schedule as it was, BE after scale #2) · C intrabar + BE@1.
C − B is review finding F1, the open decision.
"""
import json, pathlib, urllib.request
from datetime import datetime, timezone, timedelta

S = pathlib.Path("/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
import sys
DATES = sys.argv[1:] or ["2026-07-27"]


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
            return sorted(out), sfx
    return [], None


trades = json.loads((S / "trades.json").read_text())
trades = trades if isinstance(trades, list) else trades.get("trades", [])
trades = [t for t in trades if t.get("date") in DATES]
fills = []
for D in DATES:
    fn = S / ("dec27.json" if D == "2026-07-27" else f"dec_{D}.json")
    if not fn.exists(): continue
    dd = json.loads(fn.read_text()); dd = dd if isinstance(dd, list) else dd.get("rows", [])
    fills += [r for r in dd if r.get("status") == "filled"]

used, cohort, excluded = set(), [], []
for t in sorted(trades, key=lambda x: x.get("recorded_at") or ""):
    if (t.get("entry_session") or "") == "PRE":
        excluded.append((t["ticker"], "PRE quarantine — off-tape blind-stop exit", t.get("pnl")))
        continue
    c = [(i, f) for i, f in enumerate(fills) if i not in used and f["ticker"] == t["ticker"]
         and abs(float(f.get("price") or 0) - float(t["entry"])) <= 0.011]
    if not c:
        excluded.append((t["ticker"], "no decision-log fill row", t.get("pnl"))); continue
    i, f = min(c, key=lambda x: x[1]["recorded_at"])
    used.add(i)
    t["_stamp"] = datetime.fromisoformat(f["recorded_at"]).astimezone(timezone.utc)
    t["_fpx"] = float(f["price"])
    cohort.append(t)

print(f"COHORT {DATES} RTH: {len(cohort)} graded, {len(excluded)} excluded (each named):")
for tk, why, p in excluded:
    print(f"    {tk:6} {why:44} recorded {float(p or 0):+.2f}")


def anchor(t, bars):
    """Latest bar at/before the fill stamp whose range contains the fill price."""
    cands = [b for b in bars if b[0] <= t["_stamp"] and b[1] <= t["_fpx"] <= b[2]]
    return cands[-1][0] if cands else t["_stamp"]


def sim(t, bars, be_after, conservative):
    entry = float(t["entry"]); stop0 = float(t.get("stop_loss") or 0); sh = int(t.get("shares") or 0)
    if not (entry > 0 and stop0 > 0 and sh > 0):
        return None
    t0 = anchor(t, bars); t1 = datetime.fromisoformat(t["recorded_at"]).astimezone(timezone.utc)
    seq = [b for b in bars if t0 <= b[0] <= t1]
    if not seq:
        return None
    pend = [(int(q), float(p)) for q, p in (t.get("partial_fills") or [])]
    banked, sold, stop, n = 0.0, 0, stop0, 0
    for ts, lo, hi in seq:
        while pend and hi >= pend[0][1]:
            q, px = pend.pop(0); banked += (px - entry) * q; sold += q; n += 1
            if n >= be_after:
                stop = max(stop, entry)
        if lo <= stop:
            px = min(lo, stop) if conservative else stop
            return banked + (px - entry) * (sh - sold), px, ts
    return None


print("\n" + "=" * 100)
print(f"{'ticker':7}{'lane':13}{'A rec':>9}{'B opt':>9}{'B cons':>9}{'B−A opt':>9}{'B−A con':>9}"
      f"{'C opt':>9}{'C−B opt':>9}")
print("=" * 100)
T = dict(A=0.0, Bo=0.0, Bc=0.0, Co=0.0, Cc=0.0)
helped = hurt = same = 0
for t in sorted(cohort, key=lambda x: x["ticker"]):
    bars, src = load(t["ticker"], t["date"])
    A = float(t.get("pnl") or 0)
    if not bars:
        print(f"{t['ticker']:7}{(t.get('entry_type') or '?'):13}{A:9.2f}   no 10s bars"); continue
    bo = sim(t, bars, 2, False); bc = sim(t, bars, 2, True)
    co = sim(t, bars, 1, False); cc = sim(t, bars, 1, True)
    Bo = bo[0] if bo else A; Bc = bc[0] if bc else A
    Co = co[0] if co else A; Cc = cc[0] if cc else A
    T["A"] += A; T["Bo"] += Bo; T["Bc"] += Bc; T["Co"] += Co; T["Cc"] += Cc
    d = Bo - A
    helped += d > 0.005; hurt += d < -0.005; same += abs(d) <= 0.005
    print(f"{t['ticker']:7}{(t.get('entry_type') or '?'):13}{A:9.2f}{Bo:9.2f}{Bc:9.2f}"
          f"{Bo-A:+9.2f}{Bc-A:+9.2f}{Co:9.2f}{Co-Bo:+9.2f}")
print("=" * 100)
print(f"{'TOTAL':7}{'':13}{T['A']:9.2f}{T['Bo']:9.2f}{T['Bc']:9.2f}"
      f"{T['Bo']-T['A']:+9.2f}{T['Bc']-T['A']:+9.2f}{T['Co']:9.2f}{T['Co']-T['Bo']:+9.2f}")
print(f"\nINTRABAR STOP (arm B vs recorded): helped {helped} · hurt {hurt} · unchanged {same}")
print(f"  net, optimistic fill : {T['Bo']-T['A']:+.2f}")
print(f"  net, conservative fill: {T['Bc']-T['A']:+.2f}   <- the honest floor")
print(f"\nF1 — BE floor at scale #1 ON TOP of the intrabar stop (C vs B):")
print(f"  optimistic  {T['Co']-T['Bo']:+.2f}   conservative {T['Cc']-T['Bc']:+.2f}")
