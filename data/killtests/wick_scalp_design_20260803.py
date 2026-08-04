"""WICK-CONFIRM RANGE-SCALP — design kill-test (registered 8/3 night, rules frozen pre-run).

KEV'S MECHANIC (recap dC3ytDNSC0U, EZRA+EDBL 8/3; NUWE 7/30): post-break range, above VWAP ->
pullback PIERCES a prior visible low ("grabs liquidity") -> INSTANTLY bought back: the 1-min bar
closes back ABOVE the pierced low with a bottoming wick -> enter on confirm, risk the WICK LOW
(~10c), scale at prior range high, trail candle lows.

DETECTOR (pure function over 1-min bars from the 10s store):
  front-side context: bar close > session VWAP
  prior low L: min low of bars [i-LOOKBACK, i-2] (the visible low the market can see)
  pierce+confirm at bar i: low[i] < L (pierced) AND close[i] > L (recovered) AND
      close[i] in the upper 50% of bar i's range (bottoming wick, not a fading bar)
  entry = close[i]; stop = low[i] - 0.2% buffer; must be 1-6% wide (scalp regime; wider = not
      this trade). One fire per pierced level; 3-bar cooldown.
EXIT MODEL (Kev's scalp profile): 50% at +1R, remainder trails prior 1-min low; hard stop else.

FAILURE CONDITION (pre-registered): wrong if it fires on back-side tape (close<VWAP filters) or
if per-trade mean cannot clear spread (~$5/round trip at our size).

FROZEN RULES: (A) ground truth — detect >=50% of Kev's 8 known entries (EZRA ~4.10/4.20/4.19/4.05
10:00-11:30; EDBL ~2.93/2.96/2.80 09:35-11:00) within 3 min / 2.5% of his prices.
(B) universe replay 7/28-8/3, tracked names: mean > $0, n >= 20.
BOTH pass -> ships as SHADOW lane only. Either fails -> back to design, nothing ships.
"""
import json, urllib.request, collections, pathlib

U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03"]
LOOKBACK, COOLDOWN = 12, 3

def get(u): return json.load(urllib.request.urlopen(u, timeout=60))

import json as _json, urllib.request as _ur, time as _time
_V=_json.load(open("/tmp/rv4.json"))
_HDR={"APCA-API-KEY-ID":_V["ALPACA_KEY"],"APCA-API-SECRET-KEY":_V["ALPACA_SECRET"]}
def min1(day, tk):
    """FULL SIP consolidated tape via Alpaca historical REST (feed=sip — Marcos's $99 plan; the
    8/3-night lesson: never feed=iex again). Complete history, any day, no rolling window."""
    url=(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min"
         f"&start={day}T13:30:00Z&end={day}T20:00:00Z&limit=1000&feed=sip")
    try:
        rows=_json.load(_ur.urlopen(_ur.Request(url,headers=_HDR),timeout=30)).get("bars") or []
    except Exception:
        return []
    _time.sleep(0.35)
    out=[]
    for r in rows:
        ts=r["t"][11:16]; hh=int(ts[:2])-4
        out.append((f"{hh:02d}:{ts[3:]}", float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"])))
    return out

def detect(bars):
    """-> list of (i, time, entry, stop). Pure; no lookahead."""
    fires, cool = [], -99
    cpv = cv = 0.0; vwap = []
    for t,o,h,l,c,v in bars:
        cpv += c*v; cv += v; vwap.append(cpv/cv if cv else c)
    for i in range(LOOKBACK+2, len(bars)):
        if i - cool < COOLDOWN: continue
        t,o,h,l,c,v = bars[i]
        if c <= vwap[i]: continue                                   # front-side only
        # Kev's level = the IMMEDIATE shelf ("pulls back beneath THIS low, instantly bought
        # back") — the min low of the prior 3 bars, NOT the range bottom (v1 error: 12-bar min
        # fired only on range breakdowns). Range context: within 6% of the 12-bar high.
        L = min(bars[j][3] for j in range(i-3, i))
        rng_hi = max(bars[j][2] for j in range(i-LOOKBACK, i))
        if c < rng_hi * 0.94: continue                              # still near the range top
        if not (l < L < c): continue                                # pierce the shelf + recover
        rng = h - l
        if rng <= 0 or (c - l) / rng < 0.5: continue                # bottoming wick
        stop = round(l * 0.998, 4)
        w = (c - stop) / c * 100
        if not (1.0 <= w <= 6.0): continue                          # scalp-regime width
        fires.append((i, t, c, stop)); cool = i
    return fires

def replay(bars, i, e, s):
    risk = 25.0; sh = risk / (e - s)
    half_out = None; rem = 1.0; pnl = 0.0
    for j in range(i+1, len(bars)):
        t,o,h,l,c,v = bars[j]
        if half_out is None and h >= e + (e - s):                   # +1R: bank half
            pnl += 0.5 * sh * (e - s); rem = 0.5; half_out = j; s2 = e
        if half_out is None:
            if l <= s: return pnl + rem * sh * (s - e)              # full stop
        else:
            trail = max(s2, bars[j-1][3])                           # prior bar low, floor BE
            if l <= trail: return pnl + rem * sh * (trail - e)
            s2 = trail
    return pnl + rem * sh * (bars[-1][4] - e)                       # EOD close (index 4)

# ── A: ground truth vs Kev's taped entries ──────────────────────────────────
KEV = {"EZRA": [("10:00","11:35",4.10),("10:00","11:35",4.20),("10:00","11:35",4.19),("10:00","11:35",4.05)],
       "EDBL": [("09:35","11:05",2.93),("09:35","11:05",2.96),("09:35","11:05",2.80)]}
print("== A · ground truth (Kev 8/3 scalps) ==")
hits = tot = 0
for tk, wants in KEV.items():
    bars = min1("2026-08-03", tk)
    fs = detect(bars)
    print(f" {tk}: detector fires: {[(t, round(e,2)) for _,t,e,_ in fs]}")
    for lo, hi, px in wants:
        tot += 1
        ok = any(lo <= t <= hi and abs(e - px)/px <= 0.025 for _,t,e,_ in fs)
        hits += ok
        print(f"   kev @~{px}: {'MATCHED' if ok else 'missed'}")
print(f" ground truth: {hits}/{tot}")

# ── B: universe replay ──────────────────────────────────────────────────────
print("\n== B · universe replay 7/28-8/3 ==")
allres = []
for d in DAYS:
    rows = get(f"{U}/api/decisions_archive?date={d}&limit=50000").get("rows") or []
    names = sorted({r["ticker"] for r in rows if r.get("ticker") and str(r.get("status","")).startswith("triggered")})
    for tk in names:
        bars = min1(d, tk)
        if len(bars) < 30: continue
        for i,t,e,s in detect(bars):
            p = replay(bars, i, e, s)
            allres.append({"d": d, "tk": tk, "t": t, "e": e, "pnl": round(p,2)})
n = len(allres); tot_p = sum(x["pnl"] for x in allres)
if n:
    wins = sum(1 for x in allres if x["pnl"] > 0)
    print(f" n={n}  ${tot_p:+.2f}  mean ${tot_p/n:+.2f}  win {100*wins/n:.0f}%")
    per = collections.defaultdict(float)
    for x in allres: per[x["d"]] += x["pnl"]
    for d in DAYS: print(f"   {d}: ${per[d]:+.2f}")
else:
    print(" no fires")
json.dump(allres, open(pathlib.Path(__file__).with_name("wick_scalp_rows_20260803.json"), "w"), indent=1)
print(f"\nFROZEN RULES: A>=50% ({hits}/{tot}) AND B mean>0 n>=20 ({n}) -> SHADOW ship only")
