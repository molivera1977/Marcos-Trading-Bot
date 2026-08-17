#!/usr/bin/env python3
"""MULTI-DAY SEQUENCE STUDY — day-1 character vs day-2 fires (8/17/26).

Question: does day-1's character predict day-2's fires?  Pairs = (ticker, d1, d2) where
d2 is the NEXT trading date in the universe and BOTH (sym,d1),(sym,d2) exist in
data/universe/bars10s (post-RTH-filter, same load as every study: E.DAYS).

Hypotheses (pre-registered in the tasking):
  H1 CONTINUATION : day-1 closed top 25% of its RTH range -> day-2 fires outperform weak-close.
  H2 DAY-2 FADE   : day-1 halt-ladder (>=2 zero-trade gaps >=60s in the 10s tape) -> two-sided.
  H3 GAP-HOLD     : day-2 opens above day-1 RTH high AND holds it first 15 min -> outperform gap-fail.
  H4 QUIET->LOUD  : day-1 median 10s bar range < universe median -> day-2 fires outperform.

Fires = break-attack + grinder (PILOT.gen_lane/grade, E3 $500 live-parity, unchanged chain).
OOS split BY DAY-2 DATE: MINE 2026-05-18..2026-07-21, HOLD-OUT 2026-07-22..2026-08-14
(protocol of seq_gate_oos_wall_20260817.py).  Mine direction on MINE, freeze, verify HOLD-OUT.
Null for survivors: permute day-1 labels across PAIRS 5000x (fires inherit the permuted label).
If total pairs < 30 -> whole study UNDERPOWERED: inventory + descriptive stats only, STOP.
Analysis only.  No bot edits.
"""
import importlib.util, os, json, random, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

MINE_END = "2026-07-21"   # pair belongs to the split of its DAY-2 date

def main():
    P("# MULTI-DAY SEQUENCE STUDY — day-1 character vs day-2 fires (8/17/26)")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    didx = {d: i for i, d in enumerate(dates)}
    nxt = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}

    # ---------------- PAIR INVENTORY ----------------
    by_sym = defaultdict(set)
    for (sym, d) in E.DAYS:
        by_sym[sym].add(d)
    pairs = []
    for sym, ds in sorted(by_sym.items()):
        for d1 in sorted(ds):
            d2 = nxt.get(d1)
            if d2 and d2 in ds:
                pairs.append((sym, d1, d2))
    P(f"\n## PAIR INVENTORY")
    P(f"- **{len(pairs)} pairs** (same ticker on consecutive universe trading dates, both days loaded).")
    P(f"- Distinct tickers with >=1 pair: {len({p[0] for p in pairs})}.")
    mine_pairs = [p for p in pairs if p[2] <= MINE_END]
    hold_pairs = [p for p in pairs if p[2] > MINE_END]
    P(f"- Split by DAY-2 date: MINE (d2<= {MINE_END}) {len(mine_pairs)} | HOLD-OUT {len(hold_pairs)}.")

    underpowered = len(pairs) < 30
    if underpowered:
        P("\n**TOTAL PAIRS < 30 -> STUDY UNDERPOWERED. Descriptive inventory only, no verdicts.**")

    # ---------------- day-1 / day-2 labels per pair ----------------
    # universe median of per-day median 10s bar range (for H4), over ALL name-days
    day_med_rng = {}
    for (sym, d), (bars, emas, gaps) in E.DAYS.items():
        day_med_rng[(sym, d)] = statistics.median((b["h"] - b["l"]) / b["l"] if b["l"] else 0 for b in bars)
    uni_med = statistics.median(day_med_rng.values())
    P(f"- Universe median of per-day median 10s ranges: {uni_med*100:.3f}% (H4 threshold).")

    def gaps60(bars):
        n = 0
        for i in range(1, len(bars)):
            if E.secs(bars[i]) - E.secs(bars[i - 1]) >= 60:
                n += 1
        return n

    lab = {}   # (sym,d2) -> dict of labels
    for sym, d1, d2 in pairs:
        b1, _, _ = E.DAYS[(sym, d1)]
        b2, _, _ = E.DAYS[(sym, d2)]
        hi1 = max(b["h"] for b in b1); lo1 = min(b["l"] for b in b1); c1 = b1[-1]["c"]
        h1_strong = (c1 - lo1) / (hi1 - lo1) >= 0.75 if hi1 > lo1 else False
        h2_halt = gaps60(b1) >= 2
        first15 = [b for b in b2 if E.hhmm_b(b) <= "13:45:00"]
        gap_up = b2[0]["o"] > hi1
        h3_gaphold = gap_up and all(b["l"] > hi1 for b in first15)
        h3_gapfail = gap_up and not h3_gaphold
        h4_quiet = day_med_rng[(sym, d1)] < uni_med
        lab[(sym, d2)] = dict(h1=h1_strong, h2=h2_halt, h3h=h3_gaphold, h3f=h3_gapfail,
                              gap=gap_up, h4=h4_quiet, d1=d1)

    def frac(k):
        return sum(1 for v in lab.values() if v[k])
    P(f"\n### Label prevalence across {len(pairs)} pairs")
    P(f"- H1 strong-close (top 25% of range): {frac('h1')} pairs")
    P(f"- H2 halt-ladder day-1 (>=2 gaps >=60s): {frac('h2')} pairs")
    P(f"- day-2 gapped above day-1 high: {frac('gap')} (held 15 min: {frac('h3h')}, failed: {frac('h3f')})")
    P(f"- H4 quiet day-1 tape: {frac('h4')} pairs")

    # ---------------- fires on day-2 tapes ----------------
    P("\n## FIRES (break-attack + grinder, E3 $500 live-parity)")
    rows = []
    for k in ("break_attack", "grinder"):
        rs = PILOT.grade(PILOT.gen_lane(k))
        for r in rs: r["lane"] = k
        rows += rs
    fires = [r for r in rows if (r["sym"], r["date"]) in lab]
    P(f"Total fires {len(rows)}; on a PAIR's day-2 tape: {len(fires)} "
      f"({sum(1 for r in fires if r['lane']=='break_attack')} BA / {sum(1 for r in fires if r['lane']=='grinder')} grinder).")
    for r in fires:
        r["lab"] = lab[(r["sym"], r["date"])]
    mine_f = [r for r in fires if r["date"] <= MINE_END]
    hold_f = [r for r in fires if r["date"] > MINE_END]
    P(f"MINE fires {len(mine_f)} | HOLD-OUT fires {len(hold_f)}.")

    def coh(rs):
        n = len(rs)
        if not n: return dict(N=0, dtr=0.0, win=0.0, tot=0.0)
        return dict(N=n, tot=sum(r["pnl"] for r in rs), dtr=sum(r["pnl"] for r in rs) / n,
                    win=100 * sum(1 for r in rs if r["win"]) / n)

    def show(nm, a, b, la, lb):
        ca, cb = coh(a), coh(b)
        P(f"| {nm} | {la} N={ca['N']} win {ca['win']:.0f}% ${ca['dtr']:+.2f}/tr (tot ${ca['tot']:+.0f}) "
          f"| {lb} N={cb['N']} win {cb['win']:.0f}% ${cb['dtr']:+.2f}/tr (tot ${cb['tot']:+.0f}) "
          f"| diff ${ca['dtr']-cb['dtr']:+.2f} |")
        return ca, cb

    def perm_null(rs, key, obs_diff, iters=5000, seed=17, cond=None):
        """Permute day-1 labels across PAIRS; fires inherit. Two-sided p on $/tr diff."""
        rnd = random.Random(seed)
        pkeys = [pk for pk in lab if (cond is None or cond(lab[pk]))]
        vals = [lab[pk][key] for pk in pkeys]
        by_pair = defaultdict(list)
        for r in rs: by_pair[(r["sym"], r["date"])].append(r["pnl"])
        by_pair = {pk: v for pk, v in by_pair.items() if pk in set(pkeys)}
        cnt = 0; used = 0
        for _ in range(iters):
            rnd.shuffle(vals)
            g1 = []; g0 = []
            for pk, v in zip(pkeys, vals):
                (g1 if v else g0).extend(by_pair.get(pk, []))
            if not g1 or not g0: continue
            used += 1
            d = sum(g1)/len(g1) - sum(g0)/len(g0)
            if abs(d) >= abs(obs_diff): cnt += 1
        return cnt / used if used else None

    HYPS = [
        ("H1 CONTINUATION", "h1", None, "strong-close d1", "weak-close d1", "one-sided(+)"),
        ("H2 DAY-2 FADE", "h2", None, "halt-ladder d1", "no-ladder d1", "two-sided"),
        ("H3 GAP-HOLD", "h3h", lambda L: L["gap"], "gap-hold", "gap-fail", "one-sided(+)"),
        ("H4 QUIET-THEN-LOUD", "h4", None, "quiet d1", "loud d1", "one-sided(+)"),
    ]

    verdicts = {}
    for nm, key, cond, la, lb, side in HYPS:
        P(f"\n---\n## {nm} ({side})")
        def split(rs):
            if cond:
                rs = [r for r in rs if cond(r["lab"])]
                a = [r for r in rs if r["lab"][key]]
                b = [r for r in rs if not r["lab"][key]]
            else:
                a = [r for r in rs if r["lab"][key]]
                b = [r for r in rs if not r["lab"][key]]
            return a, b
        ma, mb = split(mine_f); ha, hb = split(hold_f)
        P("| cohort | A | B | $/tr diff |"); P("|---|---|---|---|")
        cma, cmb = show("MINE", ma, mb, la, lb)
        cha, chb = show("HOLD-OUT", ha, hb, la, lb)
        if underpowered:
            verdicts[nm] = ("UNDERPOWERED", "pair inventory < 30 — descriptive only")
            P("**Descriptive only (study underpowered).**"); continue
        if min(cma["N"], cmb["N"]) < 15 or min(cha["N"], chb["N"]) < 15:
            verdicts[nm] = ("UNDERPOWERED",
                            f"cell too thin (MINE {cma['N']}/{cmb['N']}, HOLD {cha['N']}/{chb['N']})")
            P(f"**VERDICT: UNDERPOWERED** — {verdicts[nm][1]}."); continue
        mdiff = cma["dtr"] - cmb["dtr"]; hdiff = cha["dtr"] - chb["dtr"]
        # mine the direction on MINE, freeze, require same sign + material on HOLD-OUT
        same_sign = (mdiff > 0) == (hdiff > 0)
        material = abs(mdiff) > 5 and abs(hdiff) > 5
        if same_sign and material:
            allf = [r for r in fires if (cond is None or cond(r["lab"]))]
            p = perm_null(allf, key, coh(split(fires)[0])["dtr"] - coh(split(fires)[1])["dtr"],
                          cond=cond)
            P(f"NULL: permute day-1 labels across pairs 5000x -> two-sided p = "
              f"{p:.3f}" if p is not None else "NULL: degenerate")
            if p is not None and p < 0.05:
                verdicts[nm] = ("DAY1-PREDICTS",
                                f"MINE diff ${mdiff:+.2f}, HOLD-OUT diff ${hdiff:+.2f} same sign, perm p={p:.3f}")
            else:
                verdicts[nm] = ("NO-SPLIT",
                                f"direction repeats (MINE ${mdiff:+.2f} / HOLD ${hdiff:+.2f}) but null not rejected (p={p if p is None else round(p,3)})")
        else:
            verdicts[nm] = ("NO-SPLIT",
                            f"MINE diff ${mdiff:+.2f} vs HOLD-OUT diff ${hdiff:+.2f} — "
                            + ("sign flips OOS" if not same_sign else "immaterial (<$5/tr)"))
        P(f"**VERDICT: {verdicts[nm][0]}** — {verdicts[nm][1]}.")

    P("\n---\n## SUMMARY")
    P("| hypothesis | verdict | why |"); P("|---|---|---|")
    for nm, (v, why) in verdicts.items():
        P(f"| {nm} | {v} | {why} |")

    open(HERE + "/seq_multiday_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump({"pairs": len(pairs), "mine_pairs": len(mine_pairs), "hold_pairs": len(hold_pairs),
               "verdicts": {k: v[0] for k, v in verdicts.items()},
               "why": {k: v[1] for k, v in verdicts.items()}},
              open(HERE + "/seq_multiday_20260817_out.json", "w"), indent=1)
    return verdicts

if __name__ == "__main__":
    main()
