"""DYNAMIC BREAK-SIDE KILL-TEST (7/31 night — Marcos: "if you trust #1 let's build it and test it").

THE FINDING (joint grade, n=56): entries ABOVE the marked break lose even with road open
(−$13.73/e, 33% win) while at/below wins (+$12.67/e, 64%). THE FLAW in a static gate: after a real
breakout the morning break goes stale — MGRX never traded ≤0.70 again after 09:30, so a static
gate blocks the whole day including the 10:54 winner. KEV RE-ANCHORS to each newly broken level
("stop trading this thing until it broke the next"; his 0.92 entry was off the just-broken
0.88-0.90 highs).

THE DYNAMIC RULE UNDER TEST: reference level at entry time = the HIGHEST INTRADAY SWING HIGH
(3-bar fractal on 1-min aggregated tape, completed before entry) that price has ALREADY BROKEN
(a later bar closed above it), unioned with the sheet break. gap = entry vs that reference.
PASS if entry <= reference * (1 + TOL). This is Kev's re-anchor made mechanical: after each
break, the newly broken high becomes the new "level you may pull back to."

PRE-REGISTERED, before any number:
  1. Same 56-trade population as the joint grade (7/29-31, runway+break stamped). No new cohort.
  2. SUCCESS = BOTH: (a) separation survives — dynamic-PASS cohort beats dynamic-BLOCK by a
     margin comparable to the static split; (b) the staleness fix works — day-runner entries that
     static wrongly blocked (named case: MGRX 10:54 +$29.99) re-anchor and PASS.
  3. Report static vs dynamic side by side. If dynamic degrades separation, that is the finding.
  4. TOL swept only as {0%, 2%, 5%} — the pullback-to-retest zone; no finer mining.
"""
import json, urllib.request, collections
import harness

U = harness.U

def swing_levels(b10, upto_epoch):
    """1-min aggregated fractal swing highs (3 each side) completed before upto_epoch,
    plus which are BROKEN (a later 1-min close above the swing high) by that time."""
    agg, cur = [], None
    for k, o, h, l, c, v, hm in b10:
        if k >= upto_epoch: break
        bkt = k - (k % 60)
        if cur is None or cur["b"] != bkt:
            if cur: agg.append(cur)
            cur = {"b": bkt, "h": h, "c": c}
        else:
            cur["h"] = max(cur["h"], h); cur["c"] = c
    if cur: agg.append(cur)
    if len(agg) < 7: return []
    out = []
    for i in range(3, len(agg) - 3):
        w = agg[i-3:i+4]
        if agg[i]["h"] == max(x["h"] for x in w) and agg[i]["h"] > agg[i-1]["h"]:
            lvl = agg[i]["h"]
            broken = any(x["c"] > lvl for x in agg[i+1:])
            out.append((lvl, broken))
    return out

rows = []
for d in ("2026-07-29", "2026-07-30", "2026-07-31"):
    T = json.load(urllib.request.urlopen(f"{U}/api/trades?date={d}&limit=500", timeout=30))
    LV = json.load(urllib.request.urlopen(f"{U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {}
    for t in (T.get("trades") or T.get("rows") or []):
        if t.get("date") != d: continue
        rw = t.get("marked_runway_rr")
        lv = LV.get(t["ticker"]) or {}
        try: brk = float(lv.get("break"))
        except (TypeError, ValueError): continue
        if not isinstance(rw, (int, float)): continue
        ts = t.get("entry_ts_utc")
        if not ts: continue
        import datetime
        ent = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        b10 = harness.bars(t["ticker"], d)
        if not b10: continue
        sw = swing_levels(b10, int(ent.timestamp()))
        broken_below = [l for l, br in sw if br and l < t["entry"]]
        ref = max(broken_below + [brk]) if (broken_below or brk) else None
        rows.append({"d": d, "tk": t["ticker"], "hm": ent.astimezone(harness.ET).strftime("%H:%M"),
                     "pnl": t["pnl"], "rw": rw, "entry": t["entry"],
                     "gap_static": (t["entry"] - brk) / brk * 100,
                     "gap_dyn": (t["entry"] - ref) / ref * 100 if ref else None})

print(f"population: {len(rows)} trades (same as the joint grade)\n")
def agg(g, lab):
    if not g: print(f"  {lab:<40} n=0"); return (0, 0, 0)
    p = sum(x["pnl"] for x in g)
    w = 100 * sum(1 for x in g if x["pnl"] > 0) / len(g)
    print(f"  {lab:<40} n={len(g):>2}  ${p:>8.2f}  mean ${p/len(g):>7.2f}  win {w:>4.0f}%")
    return (len(g), p, p / len(g))

print("STATIC (morning break, the joint-grade split):")
agg([r for r in rows if r["gap_static"] <= 0], "PASS  (at/below morning break)")
agg([r for r in rows if r["gap_static"] > 0],  "BLOCK (above morning break)")

for tol in (0.0, 2.0, 5.0):
    print(f"\nDYNAMIC re-anchor, TOL={tol:.0f}%:")
    P = [r for r in rows if r["gap_dyn"] is not None and r["gap_dyn"] <= tol]
    B = [r for r in rows if r["gap_dyn"] is not None and r["gap_dyn"] > tol]
    agg(P, f"PASS  (≤ ref*{1+tol/100:.2f})")
    agg(B, "BLOCK (chased above the re-anchor)")

print("\nTHE NAMED TEST CASE — MGRX 7/31 10:54 (+$29.99; static BLOCKED it):")
for r in rows:
    if r["tk"] == "MGRX" and r["d"] == "2026-07-31" and r["hm"] >= "10:5":
        print(f"  entry {r['entry']}  static gap {r['gap_static']:+.1f}%  "
              f"dynamic gap {r['gap_dyn']:+.1f}%  -> "
              f"{'PASSES at 2% tol' if r['gap_dyn'] is not None and r['gap_dyn'] <= 2 else 'still blocked'}")

print("\nALL disagreements (static BLOCK -> dynamic PASS at 2%):")
for r in rows:
    if r["gap_static"] > 0 and r["gap_dyn"] is not None and r["gap_dyn"] <= 2:
        print(f"  {r['d']} {r['tk']:<6}{r['hm']}  entry {r['entry']:<7} "
              f"static {r['gap_static']:+6.1f}% dyn {r['gap_dyn']:+5.1f}%  ${r['pnl']:>8.2f}")
json.dump(rows, open("breakside_dynamic_20260731.json", "w"), indent=1)
print("\nrows -> breakside_dynamic_20260731.json")
