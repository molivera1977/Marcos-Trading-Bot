"""BOARD-LEADER EXEMPTION KILL-TEST (registered 8/4 ~10:55 ET, rules frozen pre-run;
Marcos: "do a kill test now").

HYPOTHESIS: break-side + runway gates are right about ordinary names and wrong about the day's
LEADERS (AMIX 8/4: 4 of the day's 6 misses across two gates; on a leader, above-the-break is
continuation and a short mapped road means the map is behind the move).

COHORT: every breakside_reject + runway_reject with a full ticket (price+stop) since the gates
shipped (7/31-8/4). LEADER (frozen): day gain at fire >= 50% vs SIP previous close.
SIM per reject: taken as refused — width-band risk ($20/<5%, $25/5-6%, $30/>=6%), half off at
+1R, remainder trails prior 1-min low (floor entry after scale), hard stop else, 15:45 close.
VERDICT (frozen): ship-candidate iff LEADER cohort net>$0 AND mean>=+$5 AND n>=8, AND
NON-LEADER cohort net<=$0. Else -> 8/8 table with more data.
"""
import json, urllib.request, time, datetime, collections, pathlib

V = json.load(open("/tmp/rl.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-31", "2026-08-01", "2026-08-03", "2026-08-04"]

def sip(url):
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30))
    time.sleep(0.25)
    return r

_prev = {}
def prev_close(tk, day):
    if (tk, day) in _prev: return _prev[(tk, day)]
    try:
        bars = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Day&start=2026-07-20"
                   f"&end={day}T23:59:00-04:00&limit=20&feed=sip").get("bars") or []
        # STRICTLY BEFORE the test day (v1 bug: the day's own live bar slipped in as "prev close",
        # making every gain@fire ~0 and voiding the leader labels — caught via AMIX +61% reading -14%)
        prior = [b for b in bars if b["t"][:10] < day]
        v = float(prior[-1]["c"]) if prior else None
    except Exception:
        v = None
    _prev[(tk, day)] = v
    return v

_m1 = {}
def min1(tk, day):
    if (tk, day) in _m1: return _m1[(tk, day)]
    try:
        bars = sip(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={day}T04:00:00-04:00"
                   f"&end={day}T16:00:00-04:00&limit=1000&feed=sip").get("bars") or []
    except Exception:
        bars = []
    out = [((int(b["t"][11:13]) - 4) * 60 + int(b["t"][14:16]), float(b["o"]), float(b["h"]),
            float(b["l"]), float(b["c"])) for b in bars]
    _m1[(tk, day)] = out
    return out

def replay(bars, i0, e, s):
    risk = 20 if 100*(e-s)/e < 5 else (25 if 100*(e-s)/e < 6 else 30)
    sh = risk / (e - s)
    pnl = 0.0; rem = 1.0; scaled = False; trail = s
    for j in range(i0, len(bars)):
        m, o, h, l, c = bars[j]
        if m >= 15*60+45: break
        if not scaled and h >= e + (e - s):
            pnl += 0.5 * sh * (e - s); rem = 0.5; scaled = True; trail = e
            continue
        lvl = trail if scaled else s
        if l <= lvl:
            return pnl + rem * sh * (lvl - e)
        if scaled and j > i0:
            trail = max(trail, bars[j-1][3])
    return pnl + rem * sh * (bars[-1][4] - e) if bars else pnl

rows_out = []
for d in DAYS:
    try:
        rows = json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or []
    except Exception:
        continue
    for r in rows:
        if r.get("status") not in ("breakside_reject", "runway_reject"): continue
        tk = r["ticker"]; e = float(r.get("price") or 0); s = float(r.get("stop") or 0)
        if not (e > s > 0): continue
        t = str(r.get("time"))
        try:
            dt_ = datetime.datetime.strptime(t[:8], "%I:%M:%S")
            hh = dt_.hour % 12 + (12 if t.endswith("PM") else 0)
            fmin = hh * 60 + dt_.minute
        except Exception:
            continue
        pc = prev_close(tk, d)
        if not pc: continue
        gain = 100 * (e / pc - 1)
        bars = min1(tk, d)
        idx = next((j for j, b in enumerate(bars) if b[0] >= fmin), None)
        if idx is None: continue
        pnl = replay(bars, idx, e, s)
        rows_out.append({"d": d, "t": f"{hh:02d}:{dt_.minute:02d}", "tk": tk, "gate": r["status"][:-7],
                         "gain": round(gain, 1), "leader": gain >= 50.0, "pnl": round(pnl, 2)})

def rep(g, lab):
    n = len(g)
    if not n: print(f"  {lab:<24} n=0"); return (0, 0)
    p = sum(x["pnl"] for x in g); w = sum(1 for x in g if x["pnl"] > 0)
    print(f"  {lab:<24} n={n:>2}  ${p:>8.2f}  mean ${p/n:>7.2f}  win {100*w/n:.0f}%")
    return (n, p)

print(f"structural rejects priced: {len(rows_out)}\n")
for x in sorted(rows_out, key=lambda z: (z["d"], z["t"])):
    print(f"  {x['d']} {x['t']} {x['tk']:<6} {x['gate']:<9} gain@fire {x['gain']:>6.1f}% "
          f"{'LEADER' if x['leader'] else '      '} ${x['pnl']:>+8.2f}")
print()
nl, pl = rep([x for x in rows_out if x["leader"]], "LEADERS (>=50% gain)")
nn, pn = rep([x for x in rows_out if not x["leader"]], "non-leaders")
rep([x for x in rows_out if x["gate"] == "breakside"], "  breakside all")
rep([x for x in rows_out if x["gate"] == "runway"], "  runway all")
ok = pl > 0 and nl >= 8 and (pl / nl if nl else 0) >= 5 and pn <= 0
print(f"\nFROZEN VERDICT: leader net>0:{pl>0} mean>=+$5:{(pl/nl if nl else 0):+.2f} n>=8:{nl} "
      f"non-leader net<=0:{pn<=0} ({pn:+.2f})")
print("=>", "SHIP-CANDIDATE (leader carve-out)" if ok else "NOT MET — to the 8/8 table")
json.dump(rows_out, open(pathlib.Path(__file__).with_name("leader_exemption_rows_20260804.json"), "w"), indent=1)
