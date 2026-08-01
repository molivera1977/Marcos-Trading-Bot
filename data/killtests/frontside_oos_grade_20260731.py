"""THREE-ARM FRONT-SIDE HEAD-TO-HEAD — THE FROZEN FRIDAY GRADE (7/31 evening).

REGISTRATION (RESULTS_LEDGER 7/29, aef8a1e; thresholds FROZEN, no goalpost moves):
  ARM A: 3-min streak >= 6 AND defenses >= 2      (discovery: 13 fires, +$0.31/e)
  ARM B: 3-min Kev triple >= 2 (HH+HL+rising vol) (discovery:  5 fires, +$10.28/e)
  ARM C: 5-min streak >= 3 AND defenses >= 2      (discovery: 26 fires, +$1.72/e)
  Winner takes the live front-side gate. Min 8 qualified OOS fires. Robustness: the winning arm
  must show the SAME SIGN on the neighbouring clocks (2-min / 4-min) or the win is suspect.
  OOS WINDOW AS FROZEN: Wed 7/29 + Thu 7/30 fires. (7/31 exists and is reported as an EXTRA
  column, OUTSIDE the registration — never folded into the grade.)

FROZEN DEFINITIONS (ledger 7/29 00:25 / 03:00):
  health(bar)  = 3-min close >= EMA9 AND >= session VWAP  (both computed at that bar)
  streak       = consecutive healthy closes ending at the last completed bar before the fire
  defense      = a bar whose LOW touched session VWAP and which still closed healthy
  triple(bar)  = higher-high AND higher-low AND volume > prior bar; count consecutive at fire

RECOVERY NOTE: the original scoring script lived in /tmp and is GONE. This file reconstructs the
metrics from the ledger's frozen prose. FIDELITY GATE (mandatory, §F recovery clause): the
reconstruction must reproduce the SAVED 136-row discovery artifact (frontside_rows.json — columns
[date, ticker, streak, defenses, pnl, HH:MM]) with >= 95% exact (streak, defense) matches, else
ABORT and report the mismatch — no scoring on an unvalidated reimplementation. Ambiguities
(defense counted per-day vs per-streak; EMA seeding) are resolved by WHICHEVER VARIANT MATCHES
THE ARTIFACT, tried in a fixed order and reported.

G8 LAW: coverage asserts per day; non-degeneracy asserts per metric; the fidelity gate is the
control cell. Population rule: FIRST reclaim fire per (name, day) — matched against the archive's
reclaim_shadow_fire rows to recover entry price and stop for harness pricing.
"""
import json, urllib.request, collections, datetime, pathlib, sys
import harness

U = harness.U
ART = pathlib.Path(__file__).parent / "frontside_rows"

# ── PHASE 0: the saved artifact (ground truth for validation) ────────────────────────────────
disc = json.load(open(ART / "frontside_rows.json"))          # [date, tk, streak, def, pnl, "HH:MM"]
print(f"discovery artifact: {len(disc)} rows (7/27-28)")

# ── shared: bars + metrics ───────────────────────────────────────────────────────────────────
def bars3(tk, d, width_s):
    """session 10s tape -> width_s-second bars: [(end_epoch,o,h,l,c,v)], full session (pre incl.)."""
    b = harness.bars(tk, d)
    if not b:
        return []
    out = []
    cur = None
    for k, o, h, l, c, v, hm in b:
        bucket = k - (k % width_s)
        if cur is None or cur["b"] != bucket:
            if cur: out.append(cur)
            cur = {"b": bucket, "o": o, "h": h, "l": l, "c": c, "v": v}
        else:
            cur["h"] = max(cur["h"], h); cur["l"] = min(cur["l"], l)
            cur["c"] = c; cur["v"] += v
    if cur: out.append(cur)
    return out

def vwap_upto(tk, d):
    """cumulative session VWAP per 10s bar epoch -> dict epoch->vwap (carried into aggregation)."""
    b = harness.bars(tk, d)
    out = {}; pv = vv = 0.0
    for k, o, h, l, c, v, hm in b:
        pv += ((h + l + c) / 3.0) * v; vv += v
        out[k] = pv / vv if vv > 0 else c
    return out

def metrics_at(tk, d, hm_fire, width_s, defense_scope):
    """(streak, defenses, triple) at the last completed width_s bar before hm_fire.
    defense_scope: 'streak' counts defenses inside the current streak; 'day' counts all day."""
    b10 = harness.bars(tk, d)
    if not b10: return None
    fire_epoch = None
    for k, o, h, l, c, v, hm in b10:
        if hm[:5] >= hm_fire:
            fire_epoch = k; break
    if fire_epoch is None: return None
    vw = vwap_upto(tk, d)
    agg = bars3(tk, d, width_s)
    agg = [x for x in agg if x["b"] + width_s <= fire_epoch]      # completed before the fire
    if len(agg) < 4: return None
    # EMA9 over the aggregated closes (seeded on the first close)
    closes = [x["c"] for x in agg]
    e = closes[0]; emas = [e]
    for c in closes[1:]:
        e = c * (2 / 10) + e * (1 - 2 / 10); emas.append(e)
    # per-bar session vwap = vwap at the bar's last 10s tick
    vws = []
    for x in agg:
        ks = [k for k in vw if x["b"] <= k < x["b"] + width_s]
        vws.append(vw[max(ks)] if ks else None)
    healthy = [ (vws[i] is not None and closes[i] >= emas[i] and closes[i] >= vws[i])
                for i in range(len(agg)) ]
    streak = 0
    for i in range(len(agg) - 1, -1, -1):
        if healthy[i]: streak += 1
        else: break
    lo_scope = range(len(agg) - streak, len(agg)) if defense_scope == "streak" else range(len(agg))
    defenses = sum(1 for i in lo_scope
                   if healthy[i] and vws[i] is not None and agg[i]["l"] <= vws[i])
    triple = 0
    for i in range(len(agg) - 1, 0, -1):
        if (agg[i]["h"] > agg[i-1]["h"] and agg[i]["l"] > agg[i-1]["l"]
                and agg[i]["v"] > agg[i-1]["v"]):
            triple += 1
        else: break
    return streak, defenses, triple

# ── PHASE 1: FIDELITY — reproduce the 136 discovery rows ─────────────────────────────────────
print("\nPHASE 1 — fidelity against the saved artifact (variants tried in fixed order)")
best = None
for scope in ("streak", "day"):
    hits = n = 0
    miss = []
    for row in disc:
        d, tk, s_ref, def_ref, pnl, hm = row[0], row[1], row[2], row[3], row[4], row[5]
        m = metrics_at(tk, d, hm, 180, scope)
        if m is None: continue
        n += 1
        if m[0] == s_ref and m[1] == def_ref: hits += 1
        elif len(miss) < 5: miss.append((tk, d, hm, "ref", s_ref, def_ref, "got", m[0], m[1]))
    rate = hits / max(n, 1)
    print(f"  defense_scope={scope:<7} computable {n}/136, exact-match {hits} ({rate*100:.1f}%)")
    for x in miss: print("    miss:", x)
    if best is None or rate > best[1]:
        best = (scope, rate)
SCOPE, RATE = best
if RATE < 0.95:
    print(f"\nABORT — best variant ({SCOPE}) matches only {RATE*100:.1f}% (<95%).")
    print("The reconstruction is NOT the frozen metric. Report stands; no scoring performed.")
    sys.exit(1)
print(f"  FIDELITY PASSED with defense_scope={SCOPE} ({RATE*100:.1f}%) — scoring may proceed.")

# ── PHASE 2: OOS population (first reclaim fire per name/day) + pricing ──────────────────────
def fires_for(days):
    out = []
    for d in days:
        rows = json.load(urllib.request.urlopen(
            f"{U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or []
        seen = set()
        n_day = 0
        for r in rows:
            if r.get("status") != "reclaim_shadow_fire": continue
            tk = r.get("ticker")
            if tk in seen: continue
            seen.add(tk)
            e, s, hm = r.get("price"), r.get("stop"), (r.get("time_hm") or "")[:5]
            if not (e and s and e > s and hm): continue
            out.append({"d": d, "tk": tk, "e": e, "s": s, "hm": hm})
            n_day += 1
        print(f"  {d}: {n_day} first-fires")
        assert n_day > 0, f"coverage collapse on {d} (G8) — abort"
    return out

print("\nPHASE 2 — OOS fires (REGISTERED window: 7/29 + 7/30) and EXTRA (7/31, outside registration)")
oos  = fires_for(["2026-07-29", "2026-07-30"])
extra = fires_for(["2026-07-31"])

def score(fires, width_s):
    rows = []
    for f in fires:
        m = metrics_at(f["tk"], f["d"], f["hm"], width_s, SCOPE)
        if m is None: continue
        rep = harness.replay(f["tk"], f["d"], f["e"], f["s"], entry_hm=f["hm"] + ":00")
        if not (rep and rep.get("shares")): continue
        rows.append({**f, "streak": m[0], "def": m[1], "triple": m[2], "pnl": rep["pnl"]})
    return rows

print("\nscoring (this fetches a lot of tape — patience)...")
r3  = {tuple(sorted(f.items())): None for f in []}  # noop
oos3, oos5 = score(oos, 180), score(oos, 300)
ex3, ex5   = score(extra, 180), score(extra, 300)
oos2, oos4 = score(oos, 120), score(oos, 240)       # robustness clocks

def agg(rows, sel, lab, need_n=None):
    g = [r for r in rows if sel(r)]
    n = len(g); p = sum(x["pnl"] for x in g)
    w = 100 * sum(1 for x in g if x["pnl"] > 0) / n if n else 0
    q = "" if (need_n is None or n >= need_n) else f"  ⚠️ n<{need_n}"
    print(f"    {lab:<34} n={n:>3}  ${p:>9.2f}  mean ${p/n if n else 0:>7.2f}  win {w:>5.1f}%{q}")
    return n, p, (p / n if n else 0)

# non-degeneracy (G8)
for name, rows in (("3-min", oos3), ("5-min", oos5)):
    ss = {r["streak"] for r in rows}; ds = {r["def"] for r in rows}
    assert len(ss) > 1 and len(ds) > 1, f"degenerate metrics on {name} — abort"

print("\n" + "=" * 96)
print(f"THE GRADE — REGISTERED OOS (7/29+7/30), {len(oos3)} priced first-fires, defense_scope={SCOPE}")
print("=" * 96)
nU, pU, mU = agg(oos3, lambda r: True, "UNGATED baseline")
print()
nA, pA, mA = agg(oos3, lambda r: r["streak"] >= 6 and r["def"] >= 2, "ARM A  3-min streak>=6 & def>=2", 8)
nB, pB, mB = agg(oos3, lambda r: r["triple"] >= 2,                  "ARM B  3-min Kev triple >=2", 8)
nC, pC, mC = agg(oos5, lambda r: r["streak"] >= 3 and r["def"] >= 2, "ARM C  5-min streak>=3 & def>=2", 8)

print("\nROBUSTNESS COLUMNS (same defs, neighbouring clocks; sign must agree for the winner):")
agg(oos2, lambda r: r["streak"] >= 6 and r["def"] >= 2, "  A on 2-min")
agg(oos4, lambda r: r["streak"] >= 6 and r["def"] >= 2, "  A on 4-min")
agg(oos2, lambda r: r["triple"] >= 2, "  B on 2-min")
agg(oos4, lambda r: r["triple"] >= 2, "  B on 4-min")
agg(oos4, lambda r: r["streak"] >= 3 and r["def"] >= 2, "  C on 4-min (near clock)")

print("\nEXTRA COLUMN — 7/31 (OUTSIDE the registration, never folded into the grade):")
agg(ex3, lambda r: True, "ungated 7/31")
agg(ex3, lambda r: r["streak"] >= 6 and r["def"] >= 2, "A on 7/31")
agg(ex3, lambda r: r["triple"] >= 2, "B on 7/31")
agg(ex5, lambda r: r["streak"] >= 3 and r["def"] >= 2, "C on 7/31")

json.dump({"oos3": oos3, "oos5": oos5, "ex3": ex3, "ex5": ex5, "scope": SCOPE},
          open(pathlib.Path(__file__).with_name("frontside_oos_grade_20260731.json"), "w"), indent=1)
print("\nrows -> frontside_oos_grade_20260731.json")
print("\nVERDICT RULES (frozen): an arm WINS if mean>0 at n>=8 on the registered window AND its")
print("robustness clocks agree in sign. If none: reclaim -> shadow per the registration.")
