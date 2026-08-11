"""AMBIENT LIQUIDITY KILL TEST (8/6 ~11:3x, rules frozen pre-run; Marcos: "this volume gate
ignorance must be fixed. run whatever you need to fix it.").
DEFECT: both live floors measure the FIRE (ignition bar >=5k — a spike by definition; 10k
avg dragged over the line by the spike itself). Neither measures the RESTING tape (FVN 810/bar,
SUGP 2.4k/bar entered; read-list correctly said "entry would refuse it").
METRIC: ambient = MEDIAN completed 1-min bar volume over the 10 bars BEFORE the entry minute
(median = spike-proof; pre-entry = resting tape). Also ambient DOLLAR volume (median vol x
median close) because shares don't compare across prices.
COHORT: all era RTH trades 7/14+ (dip_rip included — exit liquidity matters everywhere).
FROZEN VERDICT: the floor is the highest bucket boundary B such that the cohort BELOW B has
mean P&L < 0 with n >= 8 under BOTH metrics' own bucketing; ship as a HARD conversion floor
(median-of-prior-10) with env kill. If no bucket qualifies -> no floor change, Friday table.
"""
import json, urllib.request, time, datetime, statistics, pathlib
V = json.load(open("/tmp/rrp.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
def sip(u):
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=HDR), timeout=30)); time.sleep(0.12); return r
_m = {}
def min1(tk, d):
    if (tk, d) in _m: return _m[(tk, d)]
    try:
        b = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={d}T04:00:00-04:00&end={d}T16:00:00-04:00&limit=1000&feed=sip").get("bars") or []
    except Exception:
        b = []
    _m[(tk, d)] = [((int(x["t"][11:13]) - 4) * 60 + int(x["t"][14:16]), float(x["v"]), float(x["c"])) for x in b]
    return _m[(tk, d)]
trades = [t for t in json.load(urllib.request.urlopen(U + "/api/trades", timeout=60))["trades"]
          if str(t.get("date") or "") >= "2026-07-14" and t.get("entry_ts_utc") and t.get("entry_session") != "PRE"]
rows = []
for t in trades:
    d = t["date"]; tk = t["ticker"]; pnl = float(t.get("pnl") or 0)
    dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
    em = (dt_.hour - 4) * 60 + dt_.minute
    if em < 570: continue
    B = min1(tk, d)
    prior = [(v, c) for m, v, c in B if m < em][-10:]
    if len(prior) < 5: continue
    mv = statistics.median(v for v, _ in prior)
    mdv = statistics.median(v * c for v, c in prior)
    rows.append({"d": d, "tk": tk, "pnl": pnl, "med_vol": int(mv), "med_dvol": int(mdv)})
print(f"era RTH trades graded: {len(rows)}\n")
def buckets(key, edges, unit):
    print(f"by {key} ({unit}):")
    prev = 0
    for e in edges + [float("inf")]:
        v = [r["pnl"] for r in rows if prev <= r[key] < e]
        lbl = f"{prev:,}-{'inf' if e == float('inf') else format(int(e), ',')}"
        if v: print(f"  {lbl:<18} n={len(v):>3} total ${sum(v):+9.2f} mean ${sum(v)/len(v):+7.2f}")
        prev = e
buckets("med_vol", [1000, 3000, 5000, 10000], "shares/min median-of-prior-10")
print()
buckets("med_dvol", [2000, 5000, 10000, 25000, 50000], "$/min median-of-prior-10")
print("\nthinnest specimens:", sorted(rows, key=lambda r: r["med_dvol"])[:8])
json.dump(rows, open(pathlib.Path(__file__).with_name("ambient_liquidity_rows_20260806.json"), "w"), indent=1)
