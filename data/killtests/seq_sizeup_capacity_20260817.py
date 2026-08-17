#!/usr/bin/env python3
"""CAPACITY CHECK for the `T B` sequence size-up (8/17/26).

Question: Marcos wants to size `T B` fires $500 -> $750. The 8/14 sizing test
(edge_stresstest_D_20260815) refuted sizing on the F config at $1,000; nobody has
checked whether $750+ inverts on the SPECIFIC gated cohorts that survived the OOS
wall (seq_gate_oos_wall_20260817: break-attack `T B` hold-out N=18, grinder `T B`
hold-out N=27).

METHOD = round D's EXACT sizing model, generalized per clip C (consistency with
the standing refutation outranks a new model):
  * liquidity guard on the SIGNAL BAR's dollar volume (close x volume, one 10s bar):
      dv >= 20*C  -> full clip C      (clip <= 5% of the bar's traded dollars)
      dv >= 10*C  -> half clip C/2
      else        -> skipped-for-size (counted, $0)
  * chase entry slip as a function of the EFFECTIVE clip P, anchored to D's two
    points (P=$500 -> -1.0%, P=$1,000 -> -1.5%) and linearly interpolated /
    extrapolated: slip(P) = 0.010 + 0.005*(P-500)/500.
    [CALIBRATION UNKNOWN] above $500 — exactly as D flagged; $750/$1,500 slips are
    EXTRAPOLATED assumptions, not measurements.
  * exits: the SAME E3 live-parity path the wall graded (F.sim_var, halt_rule=True)
    with E.POS set to the effective clip and F.ENTRY_SLIP set per trade.

HONESTY NOTE ON THE FILL MODEL: F.sim_var's fills do NOT degrade with size — shares
= POS/entry_px, stop/trail fills at model price minus a fixed -0.5% market slip,
no partial fills, no participation-driven price impact beyond the guard + slip
step-up above. This check can therefore only BOUND the size-up (selection effect of
the guard + assumed slip), not prove live capacity.

Cohort = the wall's HOLD-OUT gated fires ONLY (latest 18 dates, structural suffix
`T B`), rebuilt with the pilot's machinery unchanged.  Analysis only. No bot edits.
"""
import importlib.util, os, json, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; F = S.F; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

CLIPS = [500.0, 750.0, 1000.0, 1500.0]

def slip_for(pos):
    return 0.010 + 0.005 * (pos - 500.0) / 500.0

def has_tb(r):
    return len(r["st"]) >= 2 and tuple(r["st"][-2:]) == ("T", "B")

def dollar_vol(bars, i):
    b = bars[i]
    return b["c"] * b["v"]

def resim(r, pos):
    """Re-exit one gated fire at effective clip pos via the SAME E3 path (F.sim_var)."""
    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]
    old_pos, old_slip = E.POS, F.ENTRY_SLIP
    E.POS = pos; F.ENTRY_SLIP = slip_for(pos)
    try:
        pnl, exx, xi = F.sim_var(bars, emas, gaps, r["i"], r["entry"], r["stop"], "E3", r["det"], True)
    finally:
        E.POS = old_pos; F.ENTRY_SLIP = old_slip
    return pnl

def main():
    P("# SEQ `T B` SIZE-UP CAPACITY CHECK — 8/17/26")
    P("Method = edge_stresstest_D's sizing model generalized per clip (signal-bar dv guard,")
    P("5% participation, slip anchored to D's $500/-1.0% and $1,000/-1.5% and linearly")
    P("extended). Exits = same E3 live-parity path the OOS wall graded. Cohort = the wall's")
    P("HOLD-OUT gated `T B` fires only.")
    P("")
    nf, nd, dates = S.load_all()
    n_hold = 18
    hold_dates = set(dates[-n_hold:])
    P(f"Universe {nf} files / {nd} name-days / {len(dates)} dates; HOLD-OUT = latest {n_hold} "
      f"dates {min(hold_dates)}..{max(hold_dates)} (wall parity).")

    results = {}
    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder")):
        rows = PILOT.grade(PILOT.gen_lane(key))
        gated = [r for r in rows if r["date"] in hold_dates and has_tb(r)]
        P(f"\n---\n## LANE: {nm} — hold-out gated `T B` cohort N={len(gated)}")

        # ---- tape context ----
        dvs, dv3s = [], []
        for r in gated:
            bars = E.DAYS[(r["sym"], r["date"])][0]
            dv = dollar_vol(bars, r["i"])
            nxt = [dollar_vol(bars, j) for j in range(r["i"] + 1, min(r["i"] + 4, len(bars)))]
            r["dv"] = dv; r["dv3"] = sum(nxt)
            dvs.append(dv); dv3s.append(sum(nxt))
        thin = sum(1 for x in dvs if x < 10000)
        med_dv = statistics.median(dvs); min_dv = min(dvs)
        P(f"\n### TAPE CONTEXT (fire-bar 10s dollar volume)")
        P(f"- fire-bar dv: median ${med_dv:,.0f} · min ${min_dv:,.0f} · max ${max(dvs):,.0f}")
        P(f"- next-3-bar dv sum: median ${statistics.median(dv3s):,.0f} · min ${min(dv3s):,.0f}")
        P(f"- fires on THIN (<$10k) fire bars: {thin}/{len(gated)} = {100*thin/len(gated):.0f}%")
        P(f"- $750 clip as % of fire-bar dv: median {100*750/med_dv:.1f}% · worst {100*750/min_dv:.0f}%")

        # ---- per-clip sized re-sims (D method) ----
        P(f"\n### SIZED RE-SIM (D-parity guard + slip)")
        P("| clip | full/half/skip | filled N | total $ | $/fire (skips=$0) | $/filled | slip full/half |")
        P("|---|---|---|---|---|---|---|")
        results[key] = {"N": len(gated), "thin": thin, "med_dv": med_dv, "min_dv": min_dv, "clips": {}}
        for C in CLIPS:
            tot = 0.0; nfull = nhalf = nskip = 0
            for r in gated:
                if r["dv"] >= 20 * C:
                    tot += resim(r, C); nfull += 1
                elif r["dv"] >= 10 * C:
                    tot += resim(r, C / 2); nhalf += 1
                else:
                    nskip += 1
            filled = nfull + nhalf
            per_fire = tot / len(gated) if gated else 0.0
            per_fill = tot / filled if filled else 0.0
            P(f"| ${C:,.0f} | {nfull}/{nhalf}/{nskip} | {filled} | ${tot:+.2f} | ${per_fire:+.2f} | "
              f"${per_fill:+.2f} | -{slip_for(C)*100:.2f}%/-{slip_for(C/2)*100:.2f}% |")
            results[key]["clips"][int(C)] = {"full": nfull, "half": nhalf, "skip": nskip,
                                             "total": tot, "per_fire": per_fire, "per_filled": per_fill}
        # unguarded reference: what the wall's number was (flat $500, no guard)
        ref = sum(r["pnl"] for r in gated) / len(gated) if gated else 0.0
        P(f"\nReference (wall's own book, flat $500 chase NO guard): $/fire ${ref:+.2f}.")
        results[key]["wall_ref"] = ref

    json.dump(results, open(HERE + "/seq_sizeup_capacity_20260817_out.json", "w"), indent=1)
    open(HERE + "/seq_sizeup_capacity_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    return results

if __name__ == "__main__":
    main()
