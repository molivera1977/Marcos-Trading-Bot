#!/usr/bin/env python3
"""LIQUIDITY-CONDITIONAL SIZE-UP KILL-TEST for `T B` fires (8/17/26).

Established before this test: `T B` survives the OOS wall as a LABEL
(seq_gate_oos_wall_20260817); blanket $500->$750 REFUTED on the gated cohorts
(seq_sizeup_capacity_20260817: grinder DEGRADES-AT-750; break-attack UNMEASURABLE,
56-63% of gated fires on <$10k bars).

This test, Marcos-authorized, two questions:
 1. THE MISSING CELL: does the `T B` lift itself survive the D-guard at $500?
    Re-run the FULL ungated hold-out books (187 BA / 142 grinder) under the same
    guard model at $500 and compare gated-under-guard vs ungated-under-guard
    $/fire, plus a 5000-relabel permutation null computed UNDER THE GUARD.
 2. CONDITIONAL SIZING: clip = UP when fire-bar dv >= FLOOR else $500 (each clip
    still subject to the D guard's skip/half rules at its own size). Base policy
    FLOOR=$15k, UP=$750; sweep FLOOR in {10k,15k,20k,30k} x UP in {750,1000}.

Machinery = seq_sizeup_capacity_20260817's EXACTLY: pilot chain unchanged,
E3 live-parity exits via F.sim_var, D guard (dv>=20C full / >=10C half / else
skip $0), slip(P) = 0.010 + 0.005*(P-500)/500 -- [CALIBRATION UNKNOWN] above
$500, extrapolated not measured, exactly as D flagged.
Analysis only. No bot edits.
"""
import importlib.util, os, json, statistics, random

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; F = S.F; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

def slip_for(pos):
    return 0.010 + 0.005 * (pos - 500.0) / 500.0

def has_tb(r):
    return len(r["st"]) >= 2 and tuple(r["st"][-2:]) == ("T", "B")

def dollar_vol(bars, i):
    b = bars[i]
    return b["c"] * b["v"]

_cache = {}
def resim(r, pos):
    key = (r["sym"], r["date"], r["i"], round(pos, 2))
    if key in _cache:
        return _cache[key]
    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]
    old_pos, old_slip = E.POS, F.ENTRY_SLIP
    E.POS = pos; F.ENTRY_SLIP = slip_for(pos)
    try:
        pnl, exx, xi = F.sim_var(bars, emas, gaps, r["i"], r["entry"], r["stop"], "E3", r["det"], True)
    finally:
        E.POS = old_pos; F.ENTRY_SLIP = old_slip
    _cache[key] = pnl
    return pnl

def guarded_pnl(r, C):
    """D-guard applied at clip C: full / half / skip. Returns (pnl, tier)."""
    if r["dv"] >= 20 * C:
        return resim(r, C), "full"
    if r["dv"] >= 10 * C:
        return resim(r, C / 2), "half"
    return 0.0, "skip"

def conditional_book(gated, floor, up):
    """Per-fire clip = up if dv>=floor else 500; guard applied at that clip."""
    tot = 0.0; n_up = n_base = 0; tiers = {"full": 0, "half": 0, "skip": 0}
    worst = 0.0; up_tot = 0.0
    for r in gated:
        C = up if r["dv"] >= floor else 500.0
        pnl, tier = guarded_pnl(r, C)
        tot += pnl; tiers[tier] += 1
        if r["dv"] >= floor:
            n_up += 1; up_tot += pnl
        else:
            n_base += 1
        worst = min(worst, pnl)
    return {"total": tot, "per_fire": tot / len(gated), "n_up": n_up, "n_base": n_base,
            "tiers": tiers, "worst_fire": worst, "up_total": up_tot}

def flat_book(gated, C):
    tot = 0.0; worst = 0.0; tiers = {"full": 0, "half": 0, "skip": 0}
    for r in gated:
        pnl, tier = guarded_pnl(r, C)
        tot += pnl; tiers[tier] += 1; worst = min(worst, pnl)
    return {"total": tot, "per_fire": tot / len(gated), "tiers": tiers, "worst_fire": worst}

def main():
    P("# LIQUIDITY-CONDITIONAL SIZE-UP KILL-TEST — `T B` — 8/17/26")
    P("")
    nf, nd, dates = S.load_all()
    n_hold = 18
    hold_dates = set(dates[-n_hold:])
    P(f"Universe {nf} files / {nd} name-days / {len(dates)} dates; HOLD-OUT = latest {n_hold} "
      f"dates {min(hold_dates)}..{max(hold_dates)} (wall parity).")
    rng = random.Random(20260817)
    results = {}

    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder")):
        rows = PILOT.grade(PILOT.gen_lane(key))
        allhold = [r for r in rows if r["date"] in hold_dates]
        for r in allhold:
            bars = E.DAYS[(r["sym"], r["date"])][0]
            r["dv"] = dollar_vol(bars, r["i"])
        gated = [r for r in allhold if has_tb(r)]
        ungated = allhold  # FULL book incl. the gated fires (wall convention)
        P(f"\n---\n## LANE: {nm} — hold-out N={len(allhold)} total, gated `T B` N={len(gated)}")

        # ---- 1) LIFT UNDER GUARD ----
        g500 = [guarded_pnl(r, 500.0)[0] for r in ungated]
        by_id = {id(r): p for r, p in zip(ungated, g500)}
        ung_mean = sum(g500) / len(g500)
        gat_pnls = [by_id[id(r)] for r in gated]
        gat_mean = sum(gat_pnls) / len(gat_pnls)
        lift = gat_mean - ung_mean
        # permutation null UNDER THE GUARD
        m = len(gated); NPERM = 5000
        ge = 0
        for _ in range(NPERM):
            samp = rng.sample(g500, m)
            if sum(samp) / m >= gat_mean:
                ge += 1
        pval = ge / NPERM
        P(f"\n### 1) LIFT UNDER GUARD (D-guard @ $500, skips=$0 counted)")
        P(f"- UNGATED book under guard: N={len(ungated)}, $/fire ${ung_mean:+.2f}, total ${sum(g500):+.2f}")
        P(f"- GATED `T B` under guard:  N={m}, $/fire ${gat_mean:+.2f}, total ${sum(gat_pnls):+.2f}")
        P(f"- LIFT under guard: ${lift:+.2f}/fire  (no-guard wall lift was +$29.49 BA / +$23.74 gr)")
        P(f"- permutation null (5000 relabels of {m} under guard): p(random >= observed) = {pval:.3f}")
        results[key] = {"N_all": len(allhold), "N_gated": m,
                        "ungated_guard_perfire": ung_mean, "gated_guard_perfire": gat_mean,
                        "lift_under_guard": lift, "perm_p": pval}

        # ---- 2) conditional policy base cell + 3) sweep ----
        P(f"\n### 2) CONDITIONAL SIZING on gated cohort (clip=UP when dv>=FLOOR else $500; guard at own clip)")
        base = flat_book(gated, 500.0)
        P(f"- FLAT $500 baseline: total ${base['total']:+.2f}, $/fire ${base['per_fire']:+.2f}, "
          f"full/half/skip {base['tiers']['full']}/{base['tiers']['half']}/{base['tiers']['skip']}, "
          f"worst fire ${base['worst_fire']:+.2f}")
        results[key]["flat500"] = base
        P(f"\n| FLOOR | UP | N up / base | full/half/skip | total $ | $/fire | worst fire | vs flat$500 |")
        P(f"|---|---|---|---|---|---|---|---|")
        grid = {}
        for floor in (10000, 15000, 20000, 30000):
            for up in (750.0, 1000.0):
                cb = conditional_book(gated, floor, up)
                delta = cb["total"] - base["total"]
                t = cb["tiers"]
                tag = ""
                if delta > 0 and cb["worst_fire"] >= base["worst_fire"]:
                    tag = " **BEATS-FLAT**"
                    if cb["n_up"] < 5:
                        tag += " (UNDERPOWERED: <5 upsized)"
                P(f"| ${floor/1000:.0f}k | ${up:,.0f} | {cb['n_up']} / {cb['n_base']} | "
                  f"{t['full']}/{t['half']}/{t['skip']} | ${cb['total']:+.2f} | ${cb['per_fire']:+.2f} | "
                  f"${cb['worst_fire']:+.2f} | ${delta:+.2f}{tag} |")
                grid[f"{floor}_{int(up)}"] = {**cb, "delta_vs_flat": delta}
        results[key]["grid"] = grid
        P("[CALIBRATION UNKNOWN]: all $750/$1,000 fills use D's extrapolated slip anchors; no live fills above $500 exist.")

    json.dump(results, open(HERE + "/seq_conditional_size_20260817_out.json", "w"), indent=1)
    open(HERE + "/seq_conditional_size_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    return results

if __name__ == "__main__":
    main()
