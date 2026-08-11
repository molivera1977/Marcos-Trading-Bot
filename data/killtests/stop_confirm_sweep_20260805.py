"""STOP-CONFIRM SWEEP (registered 8/5 ~11:3x ET, rules frozen pre-run; Marcos: "three minutes
is way too long" + "run the sweep now"). Question: how long must price sit at/below the stop
before we exit? Sweep INTRABAR_CONFIRM_SECS equivalents on 10s bars:
  T0   = touch (live behavior, exit on first 10s bar whose low tags the stop)
  T15/T30/T60 = breach must PERSIST: exit on the first 10s bar >= N secs after breach start
                whose close is still <= stop (a close back above stop resets the clock)
  C60/C180 = 1-min / 3-min bar CLOSE below the stop (Kev's close-based school)
EXIT PRICE MODEL (honest slippage): touch exits at max(stop, bar low) — the live intrabar
model; persist/close variants exit at that bar's CLOSE (waiting = you get the later, usually
worse, print — never better than the stop).
COHORT: every closed trade since 7/27 whose exit_reason is a stop class AND whose (ticker,day)
has 10s coverage in the warehouse. Engine: entry->+1R half (stop->BE)->prev-10s-min trail off
1-min lows approximated by 60s rolling low; variant applies to EVERY stop decision incl. BE.
FROZEN VERDICT: a setting ships-candidate iff it beats T0 by >= +$40 total AND wins/ties on
>= 60% of trades AND its worst single-trade degradation vs T0 <= $20. Else -> Friday table.
"""
import json, urllib.request, time, datetime, pathlib
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-27","2026-07-28","2026-07-29","2026-07-30","2026-07-31",
        "2026-08-03","2026-08-04","2026-08-05"]
def get(u):
    return json.load(urllib.request.urlopen(u, timeout=60))
_b = {}
def bars10(tk, d):
    if (tk,d) in _b: return _b[(tk,d)]
    try:
        rows = get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(str(tk))}~ALP10S").get("bars") or []
    except Exception:
        rows = []
    out = []
    for r in rows:
        try:
            ts = str(r.get("time"))[11:19]
            sec = int(ts[:2])*3600 + int(ts[3:5])*60 + int(ts[6:8])   # UTC secs
            out.append((sec, float(r.get("open") or 0), float(r.get("high") or 0),
                        float(r.get("low") or 0), float(r.get("close") or 0)))
        except Exception:
            continue
    _b[(tk,d)] = out
    return out

def sim(bars, i0, e, s0, mode):
    """mode: ('touch',0) ('persist',N) ('close',60|180). Returns pnl per 1 share-unit scaled later."""
    kind, N = mode
    pnl = 0.0; rem = 1.0; sc = False; stop = s0; breach = None
    lows60 = []
    for j in range(i0, len(bars)):
        sec,o,h,l,c = bars[j]
        if not sc and h >= e + (e - s0):
            pnl += 0.5*(e - s0); rem = 0.5; sc = True; stop = e; breach = None; continue
        if sc:
            lows60.append(l)
            if len(lows60) > 6: lows60.pop(0)
            if len(lows60) == 6: stop = max(stop, min(lows60[:6]))   # rolling prev-minute low trail
        hit = False; px = stop
        if kind == "touch":
            if l <= stop: hit = True; px = max(stop, l)
        elif kind == "persist":
            if l <= stop and breach is None: breach = sec
            if c > stop: breach = None
            if breach is not None and sec - breach >= N and c <= stop: hit = True; px = c
        else:  # close-based on N-sec boundaries
            if c <= stop and sec % N >= N - 10:   # last 10s bucket of the 1-min/3-min bar
                hit = True; px = c
        if hit:
            return pnl + rem*(px - e)
    return pnl + (rem*(bars[-1][4] - e) if bars else 0)

trades = [t for t in get(U + "/api/trades")["trades"]
          if t.get("date") in DAYS and t.get("entry_ts_utc")
          and any(k in str(t.get("exit_reason") or "") for k in ("Stop", "Trailing", "stop"))]
MODES = [("touch",0),("persist",15),("persist",30),("persist",60),("close",60),("close",180)]
rows = []
for t in trades:
    d = t["date"]; tk = t["ticker"]
    e = float(t.get("entry") or 0); s = float(t.get("stop_loss") or 0)
    sh = int(t.get("shares") or 0)
    if not (e > s > 0 and sh > 0): continue
    b = bars10(tk, d)
    if len(b) < 30: continue
    dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z","+00:00"))
    esec = dt_.hour*3600 + dt_.minute*60 + dt_.second        # UTC
    i0 = next((j for j,x in enumerate(b) if x[0] >= esec), None)
    if i0 is None: continue
    res = {m: round(sim(b, i0, e, s, m)*sh, 2) for m in MODES}
    rows.append({"d": d, "tk": tk, "sh": sh, "actual": float(t.get("pnl") or 0), **{f"{k}{n}": v for (k,n),v in res.items()}})
print(f"stop-class trades with 10s coverage: {len(rows)} of {len(trades)} candidates\n")
hdr = ["touch0","persist15","persist30","persist60","close60","close180"]
print(f"{'day':<11}{'tk':<7}" + "".join(f"{h:>11}" for h in hdr))
for x in sorted(rows, key=lambda z:(z["d"],z["tk"])):
    print(f"{x['d']:<11}{x['tk']:<7}" + "".join(f"{x[h]:>+11.2f}" for h in hdr))
tot = {h: sum(x[h] for x in rows) for h in hdr}
print("\nTOTALS:  " + "  ".join(f"{h} ${tot[h]:+.2f}" for h in hdr))
base = tot["touch0"]
print("\nvs live (touch):")
best = None
for h in hdr[1:]:
    wins = sum(1 for x in rows if x[h] >= x["touch0"] - 0.01)
    worst = max((x["touch0"] - x[h] for x in rows), default=0)
    ok = (tot[h] - base) >= 40 and rows and wins/len(rows) >= 0.6 and worst <= 20
    print(f"  {h:<10} delta ${tot[h]-base:+8.2f}  wins/ties {wins}/{len(rows)}  worst-degradation ${worst:.2f}  {'SHIP-CANDIDATE' if ok else ''}")
    if ok and (best is None or tot[h] > tot[best]): best = h
print(f"\nFROZEN VERDICT: {best or 'NOT MET — touch stands; to the Friday table'}")
json.dump(rows, open(pathlib.Path(__file__).with_name("stop_confirm_rows_20260805.json"), "w"), indent=1)
