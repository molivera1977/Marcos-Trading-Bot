"""PYRAMID ADD-ON-CONFIRM KILL-TEST (registered 8/4 ~02:00, rules frozen pre-run; I5 graduated
from the docket after the 8/3 size-inversion autopsy: runners get caught at $37-145, dull
scratches at $500).

MECHANIC UNDER TEST (Kev's starter->risk-free->add): for every live trade that reached +1R
(starter risk-free under the existing BE ratchet), find the FIRST wick-confirm pullback on SIP
1-min tape AFTER the +1R bar (bar pierces prior bar's low, closes back above it, close in the
upper half), and ADD: notional <= $400, add-risk <= $25 to the wick low - 0.2%. Manage the add
alone: 50% off at the add's +1R, remainder trails prior-bar low (floor = add entry after scale),
hard stop else, EOD close at 15:45. Base trade keeps its ACTUAL recorded P&L — this measures the
ADD's marginal dollars only.

FROZEN VERDICT (ship-candidate for the 8/8 table iff ALL):
  adds total > $0 · mean >= +$3 per QUALIFYING trade · worst single add >= -$30 · n_adds >= 10
FAILURE CONDITION (pre-registered): wrong if adds bleed on chop days (the I3 repeat class in
disguise) — TRAIN 7/28-31 vs TEST 8/3 reported separately; a sign flip between them = not shipped.
"""
import json, urllib.request, datetime, time, pathlib

V = json.load(open("/tmp/rv8.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03"]

def sip1(day, tk):
    url = (f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={day}T08:00:00-04:00"
           f"&end={day}T16:00:00-04:00&limit=1000&feed=sip")
    try:
        rows = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30)).get("bars") or []
    except Exception:
        return []
    time.sleep(0.3)
    out = []
    for r in rows:
        hh = int(r["t"][11:13]) - 4
        out.append((f"{hh:02d}:{r['t'][14:16]}", float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"])))
    return out

trades = [t for t in json.load(urllib.request.urlopen(f"{U}/api/trades", timeout=60))["trades"] if t.get("date") in DAYS]
adds, no_add, skipped = [], 0, 0
for t in trades:
    e = float(t.get("entry") or 0); s = float(t.get("stop_loss") or 0); hi = float(t.get("highest") or 0)
    if not (e > s > 0 and hi > 0): skipped += 1; continue
    R = e - s
    if hi < e + R: continue                                     # never reached +1R -> no pyramid
    try:
        dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
        ehm = (dt_ - datetime.timedelta(hours=4)).strftime("%H:%M")
    except Exception: skipped += 1; continue
    bars = sip1(t["date"], t["ticker"])
    idx = [i for i, b in enumerate(bars) if b[0] >= ehm]
    if not idx: skipped += 1; continue
    i0 = idx[0]
    # find the +1R bar, then the first wick-confirm after it
    i1r = next((j for j in range(i0, len(bars)) if bars[j][2] >= e + R), None)
    if i1r is None: continue
    add = None
    for j in range(i1r + 1, min(i1r + 90, len(bars))):
        tme, o, h, l, c = bars[j]
        pl = bars[j-1][3]                                        # prior bar low
        if l < pl and c > pl and (h - l) > 0 and (c - l) / (h - l) >= 0.5:
            astop = round(l * 0.998, 4)
            if c <= astop: continue
            sh = min(int(400 / c), int(25 / (c - astop))) or 0
            if sh < 1: continue
            add = {"j": j, "hm": tme, "px": c, "stop": astop, "sh": sh}
            break
    if add is None: no_add += 1; continue
    # manage the add
    px, st, sh = add["px"], add["stop"], add["sh"]
    aR = px - st; pnl = 0.0; rem = sh; scaled = False; trail = st
    exit_reason = "eod"
    for j in range(add["j"] + 1, len(bars)):
        tme, o, h, l, c = bars[j]
        if tme >= "15:45": break
        if not scaled and h >= px + aR:
            half = rem // 2
            pnl += half * aR; rem -= half; scaled = True; trail = px
            if rem == 0: exit_reason = "scaled_out"; break
        lvl = trail if scaled else st
        if l <= lvl:
            pnl += rem * (lvl - px); rem = 0
            exit_reason = "trail" if scaled else "stop"; break
        if scaled:
            trail = max(trail, bars[j-1][3])
    if rem > 0:
        pnl += rem * (bars[min(len(bars)-1, j)][4] - px)
    adds.append({"d": t["date"], "tk": t["ticker"], "lane": t.get("entry_type"),
                 "base_pnl": float(t.get("pnl") or 0), "add_hm": add["hm"], "add_px": px,
                 "add_stop": st, "sh": sh, "add_pnl": round(pnl, 2), "why": exit_reason})

q = len(adds) + no_add
print(f"qualifying (+1R reached): {q}   adds fired: {len(adds)}   no wick-confirm found: {no_add}   skipped: {skipped}\n")
for a in sorted(adds, key=lambda x: (x["d"], x["add_hm"])):
    print(f"  {a['d']} {a['tk']:<6} {a['lane']:<13} base ${a['base_pnl']:>+7.2f} | add {a['add_hm']} "
          f"@{a['add_px']:<7.4g} stop {a['add_stop']:<7.4g} {a['sh']:>3}sh -> ${a['add_pnl']:>+7.2f} ({a['why']})")
tot = sum(a["add_pnl"] for a in adds)
def rep(g, lab):
    n = len(g)
    if not n: print(f"{lab}: n=0"); return
    p = sum(x["add_pnl"] for x in g); w = sum(1 for x in g if x["add_pnl"] > 0)
    print(f"{lab}: n={n}  ${p:+.2f}  mean ${p/n:+.2f}  win {100*w/n:.0f}%  worst ${min(x['add_pnl'] for x in g):.2f}")
print()
rep(adds, "ALL adds")
rep([a for a in adds if a["d"] != "2026-08-03"], "TRAIN 7/28-31")
rep([a for a in adds if a["d"] == "2026-08-03"], "TEST 8/3")
mean_per_q = tot / q if q else 0
worst = min((a["add_pnl"] for a in adds), default=0)
verdict = tot > 0 and mean_per_q >= 3 and worst >= -30 and len(adds) >= 10
print(f"\nFROZEN VERDICT: total>{0}: {tot>0} · mean/qualifying>=+$3: {mean_per_q:+.2f} · worst>=-$30: {worst:.2f} · n>=10: {len(adds)}")
print("=>", "SHIP-CANDIDATE for the 8/8 table" if verdict else "PARKED — rules not met")
json.dump(adds, open(pathlib.Path(__file__).with_name("pyramid_add_rows_20260804.json"), "w"), indent=1)
