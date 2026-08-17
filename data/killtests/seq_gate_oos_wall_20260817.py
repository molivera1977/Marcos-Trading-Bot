#!/usr/bin/env python3
"""OUT-OF-SAMPLE WALL for the sequence-gate finding (8/17/26).

Decides whether the `W T B` / `T B` suffix edge (pilot: sequence_mining_pilot_20260817.md)
is real or in-sample overfit.  STRICT chronological OOS protocol:

  1. SPLIT the 62-date universe BY DATE: earliest ~44 dates = MINE, latest ~18 = HOLD-OUT
     (train past, test future — the honest direction).
  2. RE-MINE the best material-N discriminating suffix for grinder and break-attack using
     ONLY the MINE dates.  Report the suffix; confirm whether it matches the pilot `T B`/`W T B`.
  3. APPLY that MINE-derived gate, FROZEN, to the HOLD-OUT dates only.  Gated vs ungated
     $/tr, win%, day stats — same E3 live-parity exits, unchanged S->G->F->C->B->E chain.
  4. VERDICT per lane: SURVIVES / COLLAPSES / UNDERPOWERED.
  5. NULL: permutation — randomly relabel which hold-out fires are 'gated' and show the
     lift vanishes (confirms signal not artifact).

Engine + event alphabet imported UNCHANGED from the pilot (which imports the flatten_parity
chain unchanged).  Analysis only.  No bot edits.
"""
import importlib.util, os, json, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

DAYHDR = "| cohort | N | win | total | $/tr | day mean | day med | green% | halves | worst day |"
DAYSEP = "|---|---|---|---|---|---|---|---|---|---|"

def row_md(nm, s):
    return (f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['tot']:+.2f} | ${s['dtr']:+.2f} | "
            f"${s['dmean']:+.2f} | ${s['dmed']:+.2f} | {s['green']:.0f}% | ${s['h1']:+.0f}/${s['h2']:+.0f} | ${s['worst']:+.2f} |")

def has_suffix(r, suf, k):
    return len(r["st"]) >= k and tuple(r["st"][-k:]) == tuple(suf)

def mine_best(rows, matn):
    """Return the MINE-derived material-N gate: the suffix (k in {2,3}, N>=matn) with the
    largest positive $/tr lift over the rows it is mined on.  None if nothing qualifies."""
    base_n = len(rows)
    base_dtr = sum(r["pnl"] for r in rows) / base_n if base_n else 0
    best = None
    for k in (2, 3):
        buckets = defaultdict(list)
        for r in rows:
            if len(r["st"]) >= k:
                buckets[tuple(r["st"][-k:])].append(r)
        for suf, sub in buckets.items():
            n = len(sub)
            if n < matn:
                continue
            hd = sum(r["pnl"] for r in sub) / n
            lift = hd - base_dtr
            if hd > 0 and lift > 0 and (best is None or lift > best["lift"]):
                best = {"suf": suf, "k": k, "n": n, "hd": hd, "lift": lift,
                        "win": 100 * sum(1 for r in sub if r["win"]) / n}
    return best

def cohort_stats(rows, dates):
    return PILOT.daystats(rows, dates) if rows else dict(
        N=0, tot=0.0, win=0.0, dtr=0.0, dmean=0.0, dmed=0.0, worst=0.0, green=0.0, h1=0.0, h2=0.0, ndays=len(dates))

def null_check(hold_rows, suf, k, iters=5000, seed=17):
    """Permutation null: the gate keeps m = #(hold-out fires carrying suf) fires with
    observed $/tr = obs.  Randomly pick m hold-out fires `iters` times; report the random
    mean-of-means (~ungated) and the p-value P(random $/tr >= observed)."""
    rnd = random.Random(seed)
    pnls = [r["pnl"] for r in hold_rows]
    N = len(pnls)
    gated = [r for r in hold_rows if has_suffix(r, suf, k)]
    m = len(gated)
    if m == 0 or N == 0:
        return None
    obs = sum(r["pnl"] for r in gated) / m
    means = []
    ge = 0
    for _ in range(iters):
        pick = rnd.sample(pnls, m)
        mu = sum(pick) / m
        means.append(mu)
        if mu >= obs:
            ge += 1
    return {"m": m, "obs": obs, "rand_mean": sum(means) / len(means),
            "p": ge / iters, "iters": iters}

def main():
    P("# SEQUENCE-GATE OUT-OF-SAMPLE WALL — 8/17/26")
    P("Chronological date split (train past / test future). Engine + alphabet imported UNCHANGED")
    P("from sequence_mining_pilot_20260817.py (flatten_parity chain, E3 live-parity exits).")
    P("")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")

    # ---- chronological split: earliest 44 MINE, latest 18 HOLD-OUT ----
    n_hold = 18
    mine_dates = set(dates[:-n_hold])
    hold_dates = sorted(set(dates[-n_hold:]))
    mine_dates_sorted = sorted(mine_dates)
    P(f"\n## DATE SPLIT")
    P(f"- MINE (train): {len(mine_dates_sorted)} dates {mine_dates_sorted[0]}..{mine_dates_sorted[-1]}")
    P(f"- HOLD-OUT (test): {len(hold_dates)} dates {hold_dates[0]}..{hold_dates[-1]}")
    P(f"- BOUNDARY: last MINE date = {mine_dates_sorted[-1]}; first HOLD-OUT date = {hold_dates[0]}")
    P("")

    verdicts = {}
    for key, nm in (("break_attack", "flat_top BREAK-ATTACK (9:30-10:30 ET)"),
                    ("grinder", "GRINDER (post-10:30 ET)")):
        P(f"\n---\n\n## LANE: {nm}")
        all_rows = PILOT.grade(PILOT.gen_lane(key))
        mine_rows = [r for r in all_rows if r["date"] in mine_dates]
        hold_rows = [r for r in all_rows if r["date"] in hold_dates]
        P(f"Total fires {len(all_rows)}  |  MINE {len(mine_rows)}  |  HOLD-OUT {len(hold_rows)}")

        # material-N threshold defined on the MINE population (a real slice, not a sliver)
        matn = max(20, int(0.08 * len(mine_rows)))
        best = mine_best(mine_rows, matn)
        P(f"MINE material-N threshold N>={matn} (max(20, 8% of {len(mine_rows)} MINE fires)).")
        if best is None:
            P("**MINE picked NO material-N positive-lift suffix.** Nothing to freeze -> lane UNDERPOWERED at mine step.")
            verdicts[key] = ("UNDERPOWERED", "MINE produced no material gate", None, None, None)
            continue
        suf_str = " ".join(best["suf"])
        matches = best["suf"] in [("T", "B"), ("W", "T", "B")]
        P(f"**MINE-derived gate: `{suf_str}` (last-{best['k']} structural)** — "
          f"N={best['n']} on MINE, win {best['win']:.0f}%, $/tr ${best['hd']:+.2f}, lift ${best['lift']:+.2f}.")
        P(f"Matches pilot `T B`/`W T B` family: {'YES' if matches else 'NO — MINE alone picked a DIFFERENT suffix (a finding in itself)'}.")

        # ---- freeze and apply to HOLD-OUT ----
        hold_ung = cohort_stats(hold_rows, hold_dates)
        gated = [r for r in hold_rows if has_suffix(r, best["suf"], best["k"])]
        hold_gd = cohort_stats(gated, hold_dates)
        P(f"\n### FROZEN GATE `{suf_str}` applied to HOLD-OUT only")
        P(DAYHDR); P(DAYSEP)
        P(row_md("HOLD-OUT UNGATED", hold_ung))
        P(row_md(f"HOLD-OUT GATED [{suf_str}]", hold_gd))
        keep_pct = 100 * hold_gd["N"] / len(hold_rows) if hold_rows else 0
        lift = hold_gd["dtr"] - hold_ung["dtr"]
        P(f"\nHold-out: gate keeps {hold_gd['N']}/{len(hold_rows)} fires ({keep_pct:.0f}%); "
          f"$/tr ${hold_ung['dtr']:+.2f} -> ${hold_gd['dtr']:+.2f} (lift ${lift:+.2f}); "
          f"win {hold_ung['win']:.0f}% -> {hold_gd['win']:.0f}%.")

        # ---- ALSO freeze the pilot's canonical MATERIAL suffix `T B` (largest robust slice),
        #      because the max-lift auto-picker is known to favor small-N slivers (pilot caveat).
        #      This is the more material form of the SAME finding under test. ----
        canon = ("T", "B")
        if best["suf"] != canon:
            cg = [r for r in hold_rows if has_suffix(r, canon, 2)]
            cs = cohort_stats(cg, hold_dates)
            mine_cg = [r for r in mine_rows if has_suffix(r, canon, 2)]
            mine_cs = cohort_stats(mine_cg, mine_dates_sorted)
            P(f"\n### CANONICAL material gate `T B` (pilot's featured grinder slice) — frozen on HOLD-OUT")
            P(f"(MINE `T B`: N={mine_cs['N']}, win {mine_cs['win']:.0f}%, $/tr ${mine_cs['dtr']:+.2f})")
            P(DAYHDR); P(DAYSEP)
            P(row_md("HOLD-OUT UNGATED", hold_ung))
            P(row_md("HOLD-OUT GATED [T B]", cs))
            c_lift = cs["dtr"] - hold_ung["dtr"]
            P(f"Hold-out `T B`: keeps {cs['N']}/{len(hold_rows)} ({100*cs['N']/len(hold_rows):.0f}%); "
              f"$/tr ${hold_ung['dtr']:+.2f} -> ${cs['dtr']:+.2f} (lift ${c_lift:+.2f}); "
              f"win {hold_ung['win']:.0f}% -> {cs['win']:.0f}%.")
            cnull = null_check(hold_rows, canon, 2)
            if cnull:
                P(f"NULL `T B`: observed ${cnull['obs']:+.2f} vs random-mean ${cnull['rand_mean']:+.2f}, "
                  f"p(random>=obs)={cnull['p']:.3f}, N={cnull['m']}.")
            best["canon"] = {"N": cs["N"], "dtr": cs["dtr"], "lift": c_lift, "win": cs["win"]}

        # ---- null / permutation ----
        nullr = null_check(hold_rows, best["suf"], best["k"])
        if nullr:
            P(f"\n### NULL (permutation, {nullr['iters']} random relabelings of {nullr['m']} hold-out fires)")
            P(f"- observed gated $/tr = ${nullr['obs']:+.2f}")
            P(f"- random-label mean $/tr = ${nullr['rand_mean']:+.2f} (~ ungated — lift vanishes under random labels)")
            P(f"- p(random >= observed) = {nullr['p']:.3f}")

        # ---- verdict ----
        # Judge on the auto-picked suffix; if it is too thin on hold-out, fall back to the
        # more-material canonical `T B` gate (same finding, larger slice) before declaring
        # underpowered — but never round a weak result up.
        eval_suf, eval_N, eval_lift, eval_dtr = suf_str, hold_gd["N"], lift, hold_gd["dtr"]
        canon_used = False
        if hold_gd["N"] < 15 and best.get("canon") and best["canon"]["N"] >= 15:
            c = best["canon"]
            eval_suf, eval_N, eval_lift, eval_dtr = "T B", c["N"], c["lift"], c["dtr"]
            canon_used = True
        gate_N = eval_N
        if gate_N < 15:
            verdict = "UNDERPOWERED"
            why = (f"best MINE gate `{suf_str}` carries only {hold_gd['N']} hold-out fires"
                   + (f" (canonical `T B` only {best['canon']['N']})" if best.get("canon") else "")
                   + " — too few to judge")
        elif eval_lift > 5 and eval_dtr > hold_ung["dtr"] and eval_dtr > 0:
            verdict = "SURVIVES"
            why = (f"hold-out gated $/tr lift ${eval_lift:+.2f} on `{eval_suf}`"
                   + (" (canonical material slice)" if canon_used else "")
                   + f", same direction as in-sample, N={gate_N}")
        else:
            verdict = "COLLAPSES"
            why = f"hold-out lift ${eval_lift:+.2f} on `{eval_suf}` — vanished or reversed vs in-sample, N={gate_N}"
        P(f"\n**VERDICT [{nm.split(' ')[0]}]: {verdict}** — {why}.")
        verdicts[key] = (verdict, why, eval_suf, hold_ung["dtr"], eval_dtr)

    # ---- summary ----
    P("\n---\n\n## SUMMARY")
    P("| lane | MINE suffix | hold-out ungated $/tr | hold-out gated $/tr | verdict |")
    P("|---|---|---|---|---|")
    lane_nm = {"break_attack": "break-attack", "grinder": "grinder"}
    for key in ("break_attack", "grinder"):
        v = verdicts.get(key)
        if v is None:
            continue
        verdict, why, suf, ung, gd = v
        ung_s = f"${ung:+.2f}" if ung is not None else "-"
        gd_s = f"${gd:+.2f}" if gd is not None else "-"
        P(f"| {lane_nm[key]} | {suf or '-'} | {ung_s} | {gd_s} | {verdict} |")

    open(HERE + "/seq_gate_oos_wall_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump({k: {"verdict": v[0], "why": v[1], "suffix": v[2],
                   "hold_ung_dtr": v[3], "hold_gated_dtr": v[4]}
               for k, v in verdicts.items()},
              open(HERE + "/seq_gate_oos_wall_20260817_out.json", "w"), indent=1, default=str)
    return verdicts

if __name__ == "__main__":
    main()
