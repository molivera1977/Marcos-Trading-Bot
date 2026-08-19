#!/usr/bin/env python3
"""
THE LANE ORDER ON TRIAL — WHO GETS THE SLOT WHEN TWO LANES WANT THE SAME NAME? (8/18)

Marcos: "test the reorder."

THE DEFECT BEING TESTED (found 8/18 by reading the scan loop, not by any rig)
  All 12 detectors run in ONE nested block per ticker, marcos_trading_bot.py:9388-9836, at
  increasing indentation (20 -> 24 -> 28 -> 32):
      zone_flip -> reclaim -> hidden -> v2 -> ema9x90 -> grinder -> bandpass -> kevseq -> prevwap
  then, outdented, ignition -> dip_rip -> flat_top.
  Whichever detector sits HIGHER fires first and takes the name; the lanes below it are then
  looking at a ticker that is already filled. That order is not a decision anybody made — it is
  the order the lanes were WRITTEN IN, 2026-06 through 8/18. Specifically: `hidden` (wall FAILED,
  -$10.21/tr hold-out, hidden_wall_20260818) sits ABOVE `ema9x90` (wall PASSED, +$26.06/tr,
  permutation p=0.0005, ema9x90_wall_20260818). Where both fire, the losing lane takes the slot.

  This script does NOT assume that costs money. It measures it.

ARMS — identical detectors, identical stops, identical exits. ONLY the contention tiebreak moves.
  CODE       today's live nesting order                                    [CONTROL]
  EXPECT     lanes sorted by their TRAIN-ONLY $/trade, best first
  REVERSE    the code order flipped                                        (control)
  EARLIEST   no lane preference at all — whoever fired first wins          (control)
  RANDOM x200  a random lane order per draw -> a NULL DISTRIBUTION for "any order at all"

  NO LOOKAHEAD: the EXPECT order is computed on the first 44 dates ONLY and then applied,
  frozen, to the 19 unseen dates. The order is printed before the hold-out numbers so the
  ranking can be checked against the result.

ARBITRATION MODEL (what "fires" actually means)
  Per name-day, fires are walked in clock order. A fire is TAKEN only if that name is not
  already holding a position; the name frees at the taken trade's own exit bar (F.sim_var's
  exit index). Fires landing within CONTEND_SEC of each other on the same name are one
  CONTENTION EVENT and the arm's rule picks the winner. This reproduces the live behaviour
  where the first detector to fire takes the ticker and the rest of the block finds it busy.

MEASURED AS MONEY, AT CAPACITY: $/day taking the first N fires per day chronologically
(N=4/6/8; $3,000 with ~$500 clips is ~6 positions), plus $/trade and green-day rate.
Exits: E3 via F.sim_var (bank 1/2 at +10%, trail 10%-off-run-high, stop-first INTRABAR),
-1% entry slip, -0.5% exit slip. Each lane keeps its OWN stop.

PARITY IS A LIMIT, NOT A FOOTNOTE (data/killtests/harness_parity.json, threshold 90%)
  grinder 9.1% · kevseq 0.0% (stale artifact) · bandpass 44.4% · v2 51.2% · hidden 86.3% ·
  prevwap/flat_top/zone_flip 100% (N=3 each). A verdict resting on the sub-threshold lanes is
  measuring the HARNESS. So every arm is reported TWICE:
      FULL   every lane
      CLEAN  only lanes at/above 90% parity, plus ema9x90 (a study construction, not a bot
             extraction, so parity does not apply to it — disclosed, not hidden)
  The CLEAN block is the one a ship may cite. The FULL block is context.

PRE-REGISTERED (written before the run)
  * The reorder is WORTH SHIPPING only if EXPECT beats CODE on hold-out $/day at N=6 AND N=8,
    in the CLEAN block, AND lands above the 90th percentile of the RANDOM null. Beating CODE
    while sitting inside the random spread means "any order beats this one", which is a finding
    about CODE, not evidence for EXPECT.
  * If EARLIEST matches EXPECT within $10/day at N=6, the lane ranking is NOT what is doing the
    work and the honest recommendation is the simpler rule.
  * If CODE is already at or above the random median, the defect is cosmetic and this document
    says so plainly.

LIMITS: detector-only. The live funnel — scanner board membership, slot accounting, capital,
the chart gate, crowns, priority sort — sits UPSTREAM and is not modelled, so absolute fire
counts exceed what the live bot can take. Read the arms against each other, never the levels.
One name-day at a time per name. Nothing ships from this script.
"""
import importlib.util
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CONTEND_SEC = 60
N_RANDOM = 200
PARITY_MIN = 90.0

# today's live nesting order, read off marcos_trading_bot.py:9388-9836 on 8/18
CODE_ORDER = ["zone_flip", "reclaim", "hidden", "v2", "ema9x90", "grinder",
              "bandpass", "kevseq", "prevwap", "ignition", "flat_top"]


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
H = _load("H", HERE + "/live_harness.py")
S, E, F = P.S, P.E, P.F
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def ema(v, n):
    k = 2.0 / (n + 1)
    e = None
    o = []
    for x in v:
        e = x if e is None else (x - e) * k + e
        o.append(e)
    return o


def parity_clean():
    """Lanes at/above the 90% threshold, + ema9x90 (study construction, parity N/A)."""
    try:
        d = json.load(open(HERE + "/harness_parity.json"))["lanes"]
    except Exception:
        return set(CODE_ORDER)
    ok = {k for k, v in d.items() if float(v.get("parity_pct", 0)) >= PARITY_MIN
          and not v.get("stale_artifact")}
    ok.add("ema9x90")
    return ok


def x9_fires(bars):
    """The 9/90 lane, same construction as ema9x90_wall_20260818 (which PASSED its wall)."""
    c1, i1 = [], []
    for a in range(0, len(bars) - 5, 6):
        c1.append(bars[a + 5]["c"]); i1.append(a + 5)
    e9, e90 = ema(c1, 9), ema(c1, 90)
    cpv = cv = 0.0
    vw = []
    for b in bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw.append(cpv / cv if cv else b["c"])
    out = []
    for a in range(1, len(i1)):
        i = i1[a]
        if i < 95 or i >= len(bars) - 3:
            continue
        if not (e9[a - 1] <= e90[a - 1] and e9[a] > e90[a] and bars[i]["c"] >= vw[i]):
            continue
        out.append((i, bars[i]["c"], min(b["l"] for b in bars[max(0, i - 30):i + 1])))
    return out


def collect():
    """Every lane's fires on every name-day, each graded through E3 with its own stop."""
    rows = []
    errs = defaultdict(int)
    # kevseq is EXCLUDED, not guessed: top3/blue_sky are live registry flags with no tape
    # equivalent, and inventing them would grade my reconstruction instead of the bot. It is
    # also at 0.0% parity (stale artifact), so it could not enter the CLEAN block anyway.
    harness_lanes = [l for l in CODE_ORDER if l not in ("ema9x90", "kevseq")]
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        # SESSION VWAP FROM THE TAPE — the exact same accumulation the live bot's session line
        # uses, computed off these bars. 8/18: the first run of this script passed NO
        # vwap_provider and every VWAP-gated lane correctly REFUSED to run (live_harness:701,
        # "a replay that omits it silently changes the gate"), which zeroed 9 of 11 lanes and
        # made the first verdict void. This is a computation, not a reconstruction.
        _cpv = _cv = 0.0
        _vwl = []
        for _b in bars:
            _tp = (_b["h"] + _b["l"] + _b["c"]) / 3.0
            _cpv += _tp * _b["v"]; _cv += _b["v"]
            _vwl.append(_cpv / _cv if _cv else _b["c"])

        def _vwp(_s, _i, _bar, _ln, _v=_vwl):
            return _v[min(max(int(_i), 0), len(_v) - 1)]

        cand = []
        for lane in harness_lanes:
            key = "ignition10s" if lane == "ignition" else lane
            try:
                if key == "flat_top":
                    # own driver: 3-min/whole-session lane; replay() refuses to feed it 10s slices
                    fs = H.replay_flat_top(sym, raw, date, _vwp, None)
                else:
                    fs = H.replay(sym, raw, [key], day=date, batch_secs=60,
                                  vwap_provider=_vwp)
            except Exception as e:
                errs[f"{lane}:{type(e).__name__}"] += 1
                continue
            for f in fs or []:
                i = f.get("i")
                px = f.get("px") or f.get("price")
                st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
                if i is None or not px or not st:
                    continue
                cand.append((int(i), lane, float(px), float(st)))
        for i, px, st in x9_fires(bars):
            cand.append((i, "ema9x90", px, st))
        for i, lane, px, st in cand:
            if i >= len(bars) - 2 or st >= px:
                continue
            try:
                pnl, _ex, xi = F.sim_var(bars, emas, gaps, i, px, st, "E3", lane, halt_rule=True)
            except Exception:
                errs["sim"] += 1
                continue
            rows.append({"sym": sym, "date": date, "i": i, "lane": lane,
                         "pnl": pnl, "xi": xi if xi else len(bars) - 1})
    return rows, errs


def arbitrate(rows, rule, order=None):
    """Walk each name-day in clock order; a fire is taken only if the name is free.
    Fires within CONTEND_SEC on the same name are one contention event, resolved by `rule`."""
    rank = {l: n for n, l in enumerate(order or [])}
    by = defaultdict(list)
    for r in rows:
        by[(r["sym"], r["date"])].append(r)
    taken = []
    for _k, v in by.items():
        v = sorted(v, key=lambda z: z["i"])
        free_at = -1
        n = 0
        while n < len(v):
            if v[n]["i"] <= free_at:
                n += 1
                continue
            grp = [v[n]]
            m = n + 1
            while m < len(v) and (v[m]["i"] - v[n]["i"]) * 10 <= CONTEND_SEC:
                grp.append(v[m]); m += 1
            if rule == "EARLIEST":
                win = grp[0]
            else:
                win = min(grp, key=lambda z: (rank.get(z["lane"], 99), z["i"]))
            taken.append(win)
            free_at = win["xi"]
            n += 1
    return taken


def stat(rs):
    if not rs:
        return None
    p = [r["pnl"] for r in rs]
    d = defaultdict(float)
    for r in rs:
        d[r["date"]] += r["pnl"]
    return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
            "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
            "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1)}


def perday(rs, ho, n):
    byday = defaultdict(list)
    for r in sorted([r for r in rs if r["date"] in ho], key=lambda z: (z["date"], z["i"])):
        byday[r["date"]].append(r)
    return sum(sum(x["pnl"] for x in v[:n]) for v in byday.values()) / max(len(ho), 1)


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    tr, ho = set(dates[:44]), set(dates[44:])
    W("=" * 102)
    W("THE LANE ORDER ON TRIAL — contention tiebreak swapped, detectors held fixed")
    W("=" * 102)
    rows, errs = collect()
    W(f"universe {len(E.DAYS)} name-days / {len(dates)} dates.  fires graded: {len(rows)}")
    if errs:
        W(f"  skipped: {dict(errs)}")
    if not rows:
        W("NO FIRES — cannot report."); return 1

    per_lane = defaultdict(list)
    for r in rows:
        per_lane[r["lane"]].append(r)
    W("\nPER-LANE (raw detector output, before any arbitration)")
    W(f"  {'lane':11s} {'fires':>6s} {'TRAIN $/tr':>12s} {'HOLD-OUT $/tr':>14s}  parity")
    par = {}
    try:
        par = {k: v.get("parity_pct") for k, v in
               json.load(open(HERE + "/harness_parity.json"))["lanes"].items()}
    except Exception:
        pass
    for l in CODE_ORDER:
        v = per_lane.get(l) or []
        if not v:
            W(f"  {l:11s} {0:>6d}"); continue
        st = stat([r for r in v if r["date"] in tr])
        sh = stat([r for r in v if r["date"] in ho])
        pv = "n/a (study)" if l == "ema9x90" else (
            f"{par[l]:.1f}%" if par.get(l) is not None else "unmeasured")
        _t = ("$%+.2f" % st["per"]) if st else "-"
        _h = ("$%+.2f" % sh["per"]) if sh else "-"
        W(f"  {l:11s} {len(v):>6d} {_t:>12s} {_h:>14s}  {pv}")

    # EXPECT order: TRAIN ONLY. Frozen here, applied blind to the hold-out.
    tr_per = {}
    for l, v in per_lane.items():
        s = stat([r for r in v if r["date"] in tr])
        tr_per[l] = s["per"] if s else -9e9
    EXPECT_ORDER = sorted(per_lane.keys(), key=lambda l: -tr_per[l])
    W("\nEXPECT order, derived from the 44 TRAIN dates ONLY (frozen before hold-out is touched):")
    W("  " + " > ".join(f"{l}({tr_per[l]:+.0f})" for l in EXPECT_ORDER))

    clean = parity_clean()
    W(f"\nPARITY-CLEAN lane set (>={PARITY_MIN:.0f}% + ema9x90): "
      f"{sorted(clean & set(per_lane))}")

    rnd = random.Random(20260818)
    for blk, keep in (("FULL (every lane — context only)", set(per_lane)),
                      ("CLEAN (parity-qualified lanes — the citable block)", clean)):
        sub = [r for r in rows if r["lane"] in keep]
        if not sub:
            continue
        W("\n" + "=" * 102)
        W(blk)
        W("=" * 102)
        ARMS = {
            "CODE (live)": arbitrate(sub, "ORDER", CODE_ORDER),
            "EXPECT":      arbitrate(sub, "ORDER", EXPECT_ORDER),
            "REVERSE":     arbitrate(sub, "ORDER", list(reversed(CODE_ORDER))),
            "EARLIEST":    arbitrate(sub, "EARLIEST"),
            # MARCOS'S CALL (8/18): "put ignition and 9/90 as the first two." The two lanes
            # that cleared their own walls go to the top; everything else keeps code order.
            "MARCOS ign+9/90": arbitrate(sub, "ORDER", ["ignition", "ema9x90"] +
                                         [l for l in CODE_ORDER
                                          if l not in ("ignition", "ema9x90")]),
        }
        W(f"  {'arm':14s}{'N=4':>12s}{'N=6':>12s}{'N=8':>12s}{'$/tr':>10s}{'green':>8s}")
        pd_ = {}
        for k, v in ARMS.items():
            s = stat([r for r in v if r["date"] in ho])
            pd_[k] = {n: perday(v, ho, n) for n in (4, 6, 8)}
            W(f"  {k:14s}" + "".join(f"${pd_[k][n]:>11.2f}" for n in (4, 6, 8)) +
              (f"{s['per']:>10.2f}{s['green']:>7.0f}%" if s else ""))
        nulls = {4: [], 6: [], 8: []}
        lanes = list(keep & set(per_lane))
        for _ in range(N_RANDOM):
            o = lanes[:]
            rnd.shuffle(o)
            t = arbitrate(sub, "ORDER", o)
            for n in (4, 6, 8):
                nulls[n].append(perday(t, ho, n))
        def pct(n, val):
            v = sorted(nulls[n])
            return 100.0 * sum(1 for x in v if x < val) / len(v)
        W(f"\n  RANDOM null ({N_RANDOM} shuffled orders), hold-out $/day:")
        for n in (4, 6, 8):
            v = sorted(nulls[n])
            W(f"    N={n}: median ${v[len(v)//2]:+8.2f}   5th ${v[int(.05*len(v))]:+8.2f}   "
              f"95th ${v[int(.95*len(v))]:+8.2f}    CODE is p{pct(n, pd_['CODE (live)'][n]):.0f} "
              f"| EXPECT is p{pct(n, pd_['EXPECT'][n]):.0f}")
        if "CLEAN" in blk:
            W("\n" + "=" * 102)
            W("PRE-REGISTERED VERDICT  (CLEAN block only)")
            W("=" * 102)
            c6, c8 = pd_["CODE (live)"][6], pd_["CODE (live)"][8]
            e6, e8 = pd_["EXPECT"][6], pd_["EXPECT"][8]
            beats = e6 > c6 and e8 > c8
            above = pct(6, e6) >= 90
            W(f"  EXPECT ${e6:+.2f}/day vs CODE ${c6:+.2f} at N=6  (Δ ${e6-c6:+.2f});  "
              f"N=8 ${e8:+.2f} vs ${c8:+.2f} (Δ ${e8-c8:+.2f})")
            W(f"  {'PASS' if beats else 'FAIL'}  EXPECT beats CODE at N=6 AND N=8")
            W(f"  {'PASS' if above else 'FAIL'}  EXPECT above the 90th pct of the random null "
              f"(it is p{pct(6, e6):.0f})")
            d_e = abs(pd_["EARLIEST"][6] - e6)
            W(f"  {'FAIL' if d_e <= 10 else 'PASS'}  the lane RANKING is what works, not just "
              f"'take the first fire' (EARLIEST is ${d_e:.2f}/day from EXPECT)")
            W("")
            if beats and above and d_e > 10:
                W("  => THE REORDER IS SUPPORTED on this bar. It is still a change to every lane")
                W("     at once: gauntlet + kill switch + Marcos's priced call before any ship.")
            else:
                W("  => THE REORDER IS NOT SUPPORTED on this bar. The code order stays. The")
                W("     defect (an unchosen order) is REAL; the tape does not pay to fix it, and")
                W("     a principled argument is not a reason to ship.")
            W(f"\n  where CODE sits in the null: p{pct(6, c6):.0f} at N=6 — "
              f"{'at/above the median, so the ordering is cosmetic' if pct(6, c6) >= 50 else 'BELOW the median: most random orders beat the live one'}")

    W("\nLIMITS: detector-only; no funnel (board, slots, capital, chart gate, crowns, priority")
    W("sort) — absolute levels overstate live. Sub-90% parity lanes appear ONLY in the FULL")
    W("block: grinder 9.1%, kevseq 0.0% (stale), bandpass 44.4%, v2 51.2%. Nothing ships here.")
    json.dump({"out": OUT}, open(HERE + "/lane_reorder_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
