"""THREE-ARM GRADE, VERDICT-STABILITY FORM (7/31 late).

The original scoring script is lost; reconstruction matches the 136-row artifact at 85% best and
refinement was CHURNING (a second pass scored lower than the first — uncontrolled boundary details
between runs). STOP-THE-CHURN RULE: instead of pretending one variant is THE frozen metric, score
the arms under EVERY top-matching variant. If the verdicts (sign of mean, n>=8) AGREE across all
variants, the ruling is defensible despite the unrecovered 15%. If they FLIP, the grade is blocked
and says so.

VARIANTS (the >=80% club from the search, all: health=both, defscope=streak, tol=0):
  V1 scope=rth  vanchor=same align=epoch seed=first   (85.0%)
  V2 scope=rth  vanchor=rth  align=epoch seed=first   (85.0%)
  V3 scope=rth  vanchor=same align=epoch seed=sma     (84.2%)
  V4 scope=full vanchor=rth  align=epoch seed=first   (80.0%)
Arms as FROZEN: A 3min streak>=6&def>=2 · B 3min triple>=2 · C 5min streak>=3&def>=2.
Registered OOS: 7/29+7/30 first-fires. 7/31 = extra column, outside the grade.
"""
import json, urllib.request, pathlib, sys
import harness

U = harness.U

def get_fires(days):
    out = []
    for d in days:
        rows = json.load(urllib.request.urlopen(
            f"{U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or []
        seen = set()
        for r in rows:
            if r.get("status") != "reclaim_shadow_fire": continue
            tk = r.get("ticker")
            if tk in seen: continue
            seen.add(tk)
            e, s, hm = r.get("price"), r.get("stop"), (r.get("time_hm") or "")[:5]
            if e and s and e > s and hm:
                out.append({"d": d, "tk": tk, "e": e, "s": s, "hm": hm})
    return out

OOS = get_fires(["2026-07-29", "2026-07-30"])
EX  = get_fires(["2026-07-31"])
print(f"OOS first-fires: {len(OOS)} | extra 7/31: {len(EX)}")

tapes = {}
def tape(tk, d):
    if (tk, d) not in tapes:
        tapes[(tk, d)] = harness.bars(tk, d)
    return tapes[(tk, d)]

def metrics(tk, d, hm_fire, width, scope, vanchor, seed):
    b_all = tape(tk, d)
    if not b_all: return None
    b10 = [x for x in b_all if x[6] >= "09:30:00"] if scope == "rth" else b_all
    if not b10: return None
    fire = next((x[0] for x in b10 if x[6][:5] >= hm_fire), None)
    if fire is None: return None
    src = b_all if vanchor == "same" else [x for x in b_all if x[6] >= "09:30:00"]
    pv = vv = 0.0; vw = {}
    for k, o, h, l, c, v, hm in src:
        pv += ((h + l + c) / 3) * v; vv += v; vw[k] = pv / vv if vv > 0 else c
    agg = []; cur = None
    for k, o, h, l, c, v, hm in b10:
        bkt = k - (k % width)
        if cur is None or cur["b"] != bkt:
            if cur: agg.append(cur)
            cur = {"b": bkt, "k": k, "h": h, "l": l, "c": c, "v": v}
        else:
            cur["h"] = max(cur["h"], h); cur["l"] = min(cur["l"], l)
            cur["c"] = c; cur["v"] += v; cur["k"] = k
    if cur: agg.append(cur)
    agg = [x for x in agg if x["k"] < fire]
    if len(agg) < 3: return None
    closes = [x["c"] for x in agg]
    if seed == "sma" and len(closes) >= 9:
        e = sum(closes[:9]) / 9; emas = [e] * 9
        for c in closes[9:]: e = c * 0.2 + e * 0.8; emas.append(e)
    else:
        e = closes[0]; emas = [e]
        for c in closes[1:]: e = c * 0.2 + e * 0.8; emas.append(e)
    vws = [vw.get(x["k"]) for x in agg]
    healthy = [(vws[i] is not None and closes[i] >= emas[i] and closes[i] >= vws[i])
               for i in range(len(agg))]
    streak = 0
    for i in range(len(agg) - 1, -1, -1):
        if healthy[i]: streak += 1
        else: break
    rng = range(len(agg) - streak, len(agg))
    defenses = sum(1 for i in rng if healthy[i] and vws[i] is not None and agg[i]["l"] <= vws[i])
    triple = 0
    for i in range(len(agg) - 1, 0, -1):
        if (agg[i]["h"] > agg[i-1]["h"] and agg[i]["l"] > agg[i-1]["l"]
                and agg[i]["v"] > agg[i-1]["v"]): triple += 1
        else: break
    return streak, defenses, triple

# price once (variant-independent)
priced = []
for f in OOS + EX:
    rep = harness.replay(f["tk"], f["d"], f["e"], f["s"], entry_hm=f["hm"] + ":00")
    if rep and rep.get("shares"):
        priced.append({**f, "pnl": rep["pnl"], "oos": f["d"] != "2026-07-31"})
print(f"priced: {len(priced)} ({sum(1 for p in priced if p['oos'])} OOS)")

VARIANTS = [("V1", "rth", "same", "first"), ("V2", "rth", "rth", "first"),
            ("V3", "rth", "same", "sma"), ("V4", "full", "rth", "first")]
verdicts = {}
for name, scope, vanchor, seed in VARIANTS:
    for p in priced:
        m3 = metrics(p["tk"], p["d"], p["hm"], 180, scope, vanchor, seed)
        m5 = metrics(p["tk"], p["d"], p["hm"], 300, scope, vanchor, seed)
        p["m3"], p["m5"] = m3, m5
    oos = [p for p in priced if p["oos"] and p["m3"] and p["m5"]]
    ex  = [p for p in priced if not p["oos"] and p["m3"] and p["m5"]]
    def cell(rows, sel):
        g = [r for r in rows if sel(r)]
        n = len(g); t = sum(x["pnl"] for x in g)
        return n, t, (t / n if n else 0)
    A = cell(oos, lambda r: r["m3"][0] >= 6 and r["m3"][1] >= 2)
    B = cell(oos, lambda r: r["m3"][2] >= 2)
    C = cell(oos, lambda r: r["m5"][0] >= 3 and r["m5"][1] >= 2)
    U_ = cell(oos, lambda r: True)
    print(f"\n{name} (scope={scope} vanchor={vanchor} seed={seed})  ungated: n={U_[0]} ${U_[1]:.2f} (${U_[2]:.2f}/e)")
    for lab, (n, t, m) in (("A", A), ("B", B), ("C", C)):
        v = "PASS" if (m > 0 and n >= 8) else ("n<8" if n < 8 else "neg")
        print(f"   ARM {lab}: n={n:>3}  ${t:>8.2f}  mean ${m:>7.2f}   -> {v}")
        verdicts.setdefault(lab, []).append(v)
    eA = cell(ex, lambda r: r["m3"][0] >= 6 and r["m3"][1] >= 2)
    eB = cell(ex, lambda r: r["m3"][2] >= 2)
    eC = cell(ex, lambda r: r["m5"][0] >= 3 and r["m5"][1] >= 2)
    eU = cell(ex, lambda r: True)
    print(f"   [7/31 extra] ungated n={eU[0]} ${eU[1]:.2f} | A n={eA[0]} ${eA[1]:.2f} | "
          f"B n={eB[0]} ${eB[1]:.2f} | C n={eC[0]} ${eC[1]:.2f}")

print("\n" + "=" * 78)
print("VERDICT STABILITY ACROSS VARIANTS")
print("=" * 78)
for lab, vs in verdicts.items():
    stable = len(set(vs)) == 1
    print(f"  ARM {lab}: {vs}  -> {'STABLE: ' + vs[0] if stable else 'UNSTABLE — grade blocked for this arm'}")
json.dump(verdicts, open(pathlib.Path(__file__).with_name("frontside_verdicts_20260731.json"), "w"))
