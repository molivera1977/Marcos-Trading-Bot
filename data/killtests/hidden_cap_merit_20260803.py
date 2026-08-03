"""HIDDEN CAP MERIT-EXCEPTION KILL-TEST (registered 8/3 pre-run; Marcos: "If a ticker shows
quality we should not be ignoring it.")

QUESTION: when hidden's daily cap blocked a fire that (a) had an EMPTY BOOK SLOT, (b) passed the
live gate stack (break-side + runway, both fail-open), and (c) was ballpark=in vs the marked level
(the 54%-win cell, 135-fire study), would taking it have paid?

COHORT: hidden_capped fires 7/28-8/3 paired to their hidden_shadow_fire row (price/stop/ballpark).
CONDITIONS applied per fire, from the row + day sheet + book reconstruction:
  slots: <3 concurrent positions at fire time (from live trade entry/exit times)
  gates: break-side (brk>0 and px>brk -> reject; fail-open) · runway >=1R to next marked
         target above px (fail-open when no target) · min-stop N/A (hidden exempt)
  merit: ballpark == "in"
PRICING: 10s-bar walk from fire bar: first bar low <= stop -> exit AT stop (perfect fill,
optimistic; spreads unmodeled - POSITIVE results are upper bounds); else flat at 15:44:50 close
(RTH) / 09:25 (PRE fires). Sizing: width bands $20/<5% $25/5-6% $30/>=6%.
SPLIT: TRAIN 7/28-7/31 · TEST 8/3 (today, the day that raised the question), read once.

VERDICT RULE (frozen): mean >= +$5/trade on n>=10 overall with cost/fail no worse than -$32
AND non-negative on the 8/3 slice => HIDDEN_CAP_MERIT ships tonight (env-revertible, gauntlet
first). Else -> Friday table with I3.
"""
import json, urllib.request, datetime, pathlib, collections

U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03"]

def get(url):
    return json.load(urllib.request.urlopen(url, timeout=60))

def to_sec(hhmmss_ampm):
    t = datetime.datetime.strptime(hhmmss_ampm, "%I:%M:%S %p")
    return t.hour*3600 + t.minute*60 + t.second

# book occupancy per day from live trades
trades = get(f"{U}/api/trades")["trades"]
occ = collections.defaultdict(list)
for t in trades:
    d = t.get("date")
    if d not in DAYS: continue
    try:
        e = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z","+00:00"))
        es = e.hour*3600 + e.minute*60 + e.second - 4*3600
        xs = str(t.get("recorded_at"))[11:19]
        h,m,s = map(int, xs.split(":"))
        occ[d].append((es, h*3600+m*60+s))
    except Exception:
        continue

def slots_free(d, sec):
    return sum(1 for a,b in occ[d] if a <= sec <= b) < 3

results, skipped = [], collections.Counter()
for d in DAYS:
    rows = get(f"{U}/api/decisions_archive?date={d}&limit=50000").get("rows") or []
    lv = get(f"{U}/api/kev_watchlist?date={d}").get("levels") or {}
    shadows = {(r.get("ticker"), r.get("time")): r for r in rows if r.get("status")=="hidden_shadow_fire"}
    capped  = [r for r in rows if r.get("status")=="hidden_capped"]
    barcache = {}
    for c in capped:
        key = (c.get("ticker"), c.get("time"))
        sh = shadows.get(key)
        if not sh: skipped["no_shadow_pair"] += 1; continue
        if sh.get("ballpark") != "in": skipped["ballpark_not_in"] += 1; continue
        tk = c["ticker"]; px = float(sh.get("price") or 0); st = float(sh.get("stop") or 0)
        if not (px > st > 0): skipped["bad_ticket"] += 1; continue
        sec = to_sec(c["time"])
        if not slots_free(d, sec): skipped["book_full"] += 1; continue
        rec = lv.get(tk) or {}
        try: brk = float(rec.get("break") or 0)
        except Exception: brk = 0.0
        if brk > 0 and px > brk: skipped["breakside"] += 1; continue
        tgts = sorted(float(x) for x in (rec.get("targets") or []) if float(x) > px)
        ns = float(rec.get("next_supply") or 0)
        t1 = tgts[0] if tgts else (ns if ns > px else None)
        if t1 is not None and (t1 - px)/(px - st) < 1.0: skipped["runway"] += 1; continue
        if tk not in barcache:
            try: barcache[tk] = get(f"{U}/api/bars?date={d}&ticker={tk}~ALP10S").get("bars") or []
            except Exception: barcache[tk] = []
        bars = barcache[tk]
        hm = c["time"]  # "HH:MM:SS AM"
        t24 = datetime.datetime.strptime(hm, "%I:%M:%S %p").strftime("%H:%M:%S")
        pre = t24 < "09:30:00"
        end = "09:25:00" if pre else "15:44:50"
        walk = [b for b in bars if t24 <= str(b.get("time","") )[11:19] < end] or \
               [b for b in bars if t24 <= str(b.get("t","") )[11:19] < end]
        def lo(b): return float(b.get("low") or b.get("l") or 0)
        def cl(b): return float(b.get("close") or b.get("c") or 0)
        if len(walk) < 3: skipped["no_bars"] += 1; continue
        w = 100*(px-st)/px
        risk = 20 if w < 5 else (25 if w < 6 else 30)
        sh_n = int(risk/(px-st)) or 1
        exit_px, why = None, "flat"
        for b in walk[1:]:
            if lo(b) <= st: exit_px, why = st, "stop"; break
        if exit_px is None: exit_px = cl(walk[-1])
        pnl = round((exit_px - px)*sh_n, 2)
        results.append({"d": d, "tk": tk, "t": t24, "px": px, "st": st, "w": round(w,2),
                        "pnl": pnl, "why": why})

print(f"qualifying merit fires: {len(results)}   skipped: {dict(skipped)}\n")
def agg(g, lab):
    n=len(g)
    if not n: print(f"  {lab:<22} n=0"); return
    p=sum(x["pnl"] for x in g); losers=[x["pnl"] for x in g if x["pnl"]<0]
    cfa=sum(losers)/len(losers) if losers else 0.0
    print(f"  {lab:<22} n={n:>3}  ${p:>8.2f}  mean ${p/n:>7.2f}  win {100*sum(1 for x in g if x['pnl']>0)/n:>3.0f}%  cost/fail ${cfa:>7.2f}")
agg(results, "ALL merit fires")
agg([x for x in results if x["d"] != "2026-08-03"], "TRAIN 7/28-31")
agg([x for x in results if x["d"] == "2026-08-03"], "TEST 8/3 (today)")
for d in DAYS:
    agg([x for x in results if x["d"]==d], f"  {d}")
print()
for x in sorted(results, key=lambda z:(z["d"],z["t"])):
    print(f"  {x['d']} {x['t']} {x['tk']:<5} px={x['px']:<8.4g} w={x['w']:>5.2f}% {x['why']:<5} ${x['pnl']:>+8.2f}")
json.dump(results, open(pathlib.Path(__file__).with_name("hidden_cap_merit_rows_20260803.json"),"w"), indent=1)
