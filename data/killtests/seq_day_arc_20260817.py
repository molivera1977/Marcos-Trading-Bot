#!/usr/bin/env python3
"""DAY-ARC SEQUENCE study (8/17/26) — the day as one string.

Does the MORNING's arc predict which fires pay later — the setup-not-clock version of the
windows finding (expansion morning / survival afternoon)?

DAY-STRING per name-day from the FULL 10s universe bars: one letter per 15-min phase,
07:00-16:00 ET (11:00-20:00Z; ET=UTC-4 all summer), 36 phases:
  B  breakout phase   — a new SESSION high (session starts 07:00 ET) is made in the phase
  F  flush phase      — a new post-09:30 session low is made in the phase (phases >= 09:30 only)
  V  volatile chop    — phase range >= 4%, |net| < 1%
  U  uptrend          — phase close > phase open by > 1%
  D  downtrend        — phase close < phase open by > 1%
  R  range            — |net| < 1% and range < 2%
  r  (fallback)       — none of the above (reported as R in strings; kept distinct internally NO —
                        folded into R: coarse pre-registered alphabet, R = 'nothing decisive')
Precedence: B > F > V > U > D > R.

PRE-REGISTERED HYPOTHESES (fires = break-attack + grinder + v2 pilot generators, E3 $500,
graded UNCHANGED via sequence_mining_pilot_20260817.py grade()):
  H1 coil-then-break: fires on days whose pre-10:30 arc contains B-immediately-after-R
     OUTPERFORM fires on B-immediately days (first RTH phase 09:30-09:45 is B, no prior R->B).
  H2 afternoon fires (>=12:00 ET) pay ONLY when the morning arc (07:00-12:00) held above
     session VWAP in >= 75% of phases (phase 'above' = phase-end close > session VWAP there).
  H3 opening flush-then-rip: an F phase before 10:00 followed by a later B phase — its days'
     fires OUTPERFORM the no-pre-10:00-flush days.
  H4 quiet open: first two phases (07:00-07:30 ET) are R R = the grinder's best days
     (ties to joint_door_20260816.md quiet-premarket-tape selection lift).

PROTOCOL: OOS wall split (seq_gate_oos_wall_20260817.py): MINE = dates 2026-05-18..07-21
(first 44), HOLD-OUT = 07-22..08-14 (last 18). Split each lane's fires by each condition on
MINE; keep cells with both sides N>=15 and $/tr gap >= $10 in the hypothesized direction;
FREEZE; verify on HOLD-OUT. NULL: permute the day-condition labels across DATES 5000x per
surviving cell (one-sided p in the hypothesized direction). VERDICT per hypothesis:
ARC-PREDICTS / NO-SPLIT / UNDERPOWERED. Analysis only — no bot edits.
"""
import importlib.util, os, json, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

# ---------------- day-string construction ----------------
def phase_bounds():
    """36 phases 11:00Z..20:00Z, 15 min each, as ('HH:MM:SS','HH:MM:SS') half-open."""
    out = []
    for m in range(11 * 60, 20 * 60, 15):
        out.append(("%02d:%02d:00" % (m // 60, m % 60), "%02d:%02d:00" % ((m + 15) // 60, (m + 15) % 60)))
    return out

PHASES = phase_bounds()
RTH0 = "13:30:00"          # 09:30 ET
NOON = "16:00:00"          # 12:00 ET
T1030 = "14:30:00"         # 10:30 ET
T1000 = "14:00:00"         # 10:00 ET

def day_arc(full_bars):
    """Return (arc list of 36 letters or '.' for empty phase, above_vwap list of bool-or-None)."""
    # session vwap over the full file (premarket-anchored, settled doctrine)
    cv = cpv = 0.0; vw = []
    for b in full_bars:
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cv += b["v"]; cpv += tp * b["v"]
        vw.append(cpv / cv if cv else b["c"])
    hh = lambda b: b["t"][11:19]
    arc = []; above = []
    sess_hi = None; post_lo = None
    for lo, hi in PHASES:
        idx = [i for i, b in enumerate(full_bars) if lo <= hh(b) < hi]
        if not idx:
            arc.append("."); above.append(None)
            # session extremes still advance only on bars, so nothing to do
            continue
        pb = [full_bars[i] for i in idx]
        p_open = pb[0]["o"]; p_close = pb[-1]["c"]
        p_hi = max(b["h"] for b in pb); p_lo = min(b["l"] for b in pb)
        net = (p_close - p_open) / p_open if p_open else 0.0
        rng = (p_hi - p_lo) / p_lo if p_lo else 0.0
        # session-high / post-9:30-low updates + phase flags
        newB = sess_hi is not None and p_hi > sess_hi
        if sess_hi is None: sess_hi = p_hi          # first phase seeds, no B
        else: sess_hi = max(sess_hi, p_hi)
        newF = False
        if lo >= RTH0:
            if post_lo is None:
                post_lo = p_lo
            else:
                newF = p_lo < post_lo
                post_lo = min(post_lo, p_lo)
        if newB: L = "B"
        elif newF: L = "F"
        elif rng >= 0.04 and abs(net) < 0.01: L = "V"
        elif net > 0.01: L = "U"
        elif net < -0.01: L = "D"
        else: L = "R"                                # |net|<1%; coarse fallback folds in
        arc.append(L)
        above.append(p_close > vw[idx[-1]])
    return arc, above

# phase index helpers
IDX = {lo: i for i, (lo, hi) in enumerate(PHASES)}
I_RTH0 = IDX[RTH0]; I_NOON = IDX[NOON]; I_1030 = IDX[T1030]; I_1000 = IDX[T1000]

def conds(arc, above):
    """Return dict of day-level condition labels for H1..H4 (None = day not in either side)."""
    pre1030 = arc[:I_1030]
    # H1: coil-then-break vs gap-and-go (exclusive)
    coil = any(pre1030[i] == "B" and pre1030[i - 1] == "R" for i in range(1, len(pre1030)))
    gapgo = arc[I_RTH0] == "B" and not coil
    h1 = True if coil and not gapgo else (False if gapgo else None)
    # H2: morning (07:00-12:00) above-VWAP fraction >= 75% (phases with data only)
    morn = [a for a in above[:I_NOON] if a is not None]
    h2 = (sum(morn) / len(morn) >= 0.75) if morn else None
    # H3: F before 10:00 then a later B, vs NO pre-10:00 F at all
    f_pre10 = [i for i in range(I_RTH0, I_1000) if arc[i] == "F"]
    if f_pre10:
        h3 = any(arc[j] == "B" for j in range(f_pre10[0] + 1, len(arc)))
        h3 = True if h3 else None                    # flush w/o rip = neither side
    else:
        h3 = False                                   # no-flush day
    # H4: first two phases R R (quiet open)
    first2 = arc[:2]
    h4 = (first2 == ["R", "R"]) if "." not in first2 else None
    return {"H1": h1, "H2": h2, "H3": h3, "H4": h4}

def stats(rows):
    n = len(rows)
    if not n: return {"N": 0, "dtr": 0.0, "tot": 0.0, "win": 0.0}
    tot = sum(r["pnl"] for r in rows)
    return {"N": n, "dtr": tot / n, "tot": tot,
            "win": 100 * sum(1 for r in rows if r["win"]) / n}

def fmt(nm, s):
    return f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['tot']:+.2f} | ${s['dtr']:+.2f} |"

HDR = "| cohort | N | win | total | $/tr |"
SEP = "|---|---|---|---|---|"

def null_perm(rows_t, rows_f, daycond, iters=5000, seed=17):
    """Permute the day-level condition across DATES: reassign which dates are condition-TRUE
    (keeping the count of TRUE dates), recompute the $/tr gap, one-sided p(perm gap >= obs)."""
    rows = rows_t + rows_f
    dates = sorted({r["date"] for r in rows})
    true_dates = {d for d in dates if daycond.get(d)}
    k = len(true_dates)
    if k == 0 or k == len(dates): return None
    obs = (sum(r["pnl"] for r in rows_t) / len(rows_t)) - (sum(r["pnl"] for r in rows_f) / len(rows_f))
    by_date = defaultdict(list)
    for r in rows: by_date[r["date"]].append(r["pnl"])
    rnd = random.Random(seed); ge = 0; valid = 0
    for _ in range(iters):
        pick = set(rnd.sample(dates, k))
        t = [p for d in pick for p in by_date[d]]
        f = [p for d in dates if d not in pick for p in by_date[d]]
        if not t or not f: continue
        valid += 1
        if (sum(t) / len(t) - sum(f) / len(f)) >= obs: ge += 1
    return {"obs": obs, "p": ge / valid if valid else None, "iters": valid}

def main():
    P("# DAY-ARC SEQUENCE STUDY — 8/17/26 (morning arc -> which fires pay later)")
    P("Phases: 36 x 15min 07:00-16:00 ET; letters B>F>V>U>D>R. Fires/exits: pilot generators,")
    P("E3 $500 live-parity, UNCHANGED. Split: MINE 05-18..07-21 / HOLD-OUT 07-22..08-14.")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    n_hold = 18
    mine_dates = set(dates[:-n_hold]); hold_dates = set(dates[-n_hold:])
    P(f"MINE {len(mine_dates)} dates ..{sorted(mine_dates)[-1]} | HOLD-OUT {len(hold_dates)} dates {sorted(hold_dates)[0]}..")

    # ---- per name-day arcs (FULL bars incl. premarket) ----
    ARC = {}
    for key, bars in S.FULL.items():
        if key not in E.DAYS: continue               # same population the fires come from
        arc, above = day_arc(bars)
        ARC[key] = conds(arc, above)
        ARC[key]["_arc"] = "".join(arc)
    P(f"Arcs built for {len(ARC)} name-days.")

    # ---- fires ----
    LANES = {}
    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder"), ("v2", "v2")):
        LANES[key] = (nm, PILOT.grade(PILOT.gen_lane(key)))
        P(f"Lane {nm}: {len(LANES[key][1])} fires graded (E3).")

    HYPS = ["H1", "H2", "H3", "H4"]
    HNAME = {"H1": "coil-then-break (R->B pre-10:30) vs gap-and-go",
             "H2": "afternoon fires: morning >=75% phases above VWAP",
             "H3": "pre-10:00 flush-then-rip vs no-flush days",
             "H4": "quiet open (first two phases R R)"}
    results = {}
    for H in HYPS:
        P(f"\n---\n\n## {H}: {HNAME[H]}")
        results[H] = {}
        for key in ("break_attack", "grinder", "v2"):
            nm, rows = LANES[key]
            if H == "H2":
                rows = [r for r in rows if r["t"] >= NOON]        # afternoon fires only
            if H == "H4" and key != "grinder":
                pass                                              # still report, H4 verdict = grinder
            def side(r):
                c = ARC.get((r["sym"], r["date"]))
                return None if c is None else c[H]
            m_t = [r for r in rows if r["date"] in mine_dates and side(r) is True]
            m_f = [r for r in rows if r["date"] in mine_dates and side(r) is False]
            st, sf = stats(m_t), stats(m_f)
            gap = st["dtr"] - sf["dtr"]
            P(f"\n### lane {nm}" + (" (afternoon fires only)" if H == "H2" else ""))
            P(HDR); P(SEP)
            P(fmt("MINE cond-TRUE", st)); P(fmt("MINE cond-FALSE", sf))
            P(f"MINE gap ${gap:+.2f}/tr (TRUE - FALSE).")
            keep = st["N"] >= 15 and sf["N"] >= 15 and gap >= 10
            cell = {"mine_t": st, "mine_f": sf, "mine_gap": gap, "kept": keep}
            if not keep:
                why = "underpowered" if (st["N"] < 15 or sf["N"] < 15) else "gap < $10"
                P(f"-> NOT FROZEN ({why}: N {st['N']}/{sf['N']}, gap ${gap:+.2f}).")
            else:
                P(f"-> FROZEN (N {st['N']}/{sf['N']}, gap ${gap:+.2f}) — verify on HOLD-OUT.")
                h_t = [r for r in rows if r["date"] in hold_dates and side(r) is True]
                h_f = [r for r in rows if r["date"] in hold_dates and side(r) is False]
                ht, hf = stats(h_t), stats(h_f)
                hgap = ht["dtr"] - hf["dtr"]
                P(HDR); P(SEP)
                P(fmt("HOLD cond-TRUE", ht)); P(fmt("HOLD cond-FALSE", hf))
                P(f"HOLD-OUT gap ${hgap:+.2f}/tr, N {ht['N']}/{hf['N']}.")
                cell.update({"hold_t": ht, "hold_f": hf, "hold_gap": hgap})
                if h_t and h_f:
                    daycond = {}
                    for r in h_t: daycond.setdefault(r["date"], True)
                    # a date can carry both TRUE and FALSE name-days -> permute name-day condition
                    # across NAME-DAYS' dates is ill-posed; permute at the name-day level instead:
                    nulld = null_perm_nameday(h_t, h_f)
                    if nulld:
                        P(f"NULL (5000x name-day label permutation): p(perm gap >= obs) = {nulld['p']:.3f}.")
                        cell["p"] = nulld["p"]
            results[H][key] = cell
    # verdicts
    P("\n---\n\n## VERDICTS")
    verd = {}
    for H in HYPS:
        lanes = results[H]
        judge = ["grinder"] if H == "H4" else ["break_attack", "grinder", "v2"]
        frozen = [(k, lanes[k]) for k in judge if lanes[k].get("kept")]
        if not frozen:
            anyu = any(lanes[k]["mine_t"]["N"] < 15 or lanes[k]["mine_f"]["N"] < 15 for k in judge)
            v = "UNDERPOWERED" if anyu and not any(abs(lanes[k]["mine_gap"]) >= 10 and
                lanes[k]["mine_t"]["N"] >= 15 and lanes[k]["mine_f"]["N"] >= 15 for k in judge) else "NO-SPLIT"
            # if every judged lane had power but gap<10 -> NO-SPLIT; if the only signal-sized
            # cells lacked N -> UNDERPOWERED
            powered = [k for k in judge if lanes[k]["mine_t"]["N"] >= 15 and lanes[k]["mine_f"]["N"] >= 15]
            v = "NO-SPLIT" if powered else "UNDERPOWERED"
        else:
            ok = [(k, c) for k, c in frozen if c.get("hold_gap", -1e9) >= 10 and
                  c.get("hold_t", {}).get("N", 0) >= 15 and c.get("hold_f", {}).get("N", 0) >= 15 and
                  (c.get("p") is None or c["p"] <= 0.05)]
            thin = [(k, c) for k, c in frozen if c.get("hold_t", {}).get("N", 0) < 15 or
                    c.get("hold_f", {}).get("N", 0) < 15]
            if ok: v = "ARC-PREDICTS"
            elif thin and len(thin) == len(frozen): v = "UNDERPOWERED"
            else: v = "NO-SPLIT"
        verd[H] = v
        P(f"**{H} ({HNAME[H]}): {v}**")

    open(HERE + "/seq_day_arc_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump({"verdicts": verd,
               "cells": {H: {k: {kk: vv for kk, vv in c.items() if kk != '_arc'}
                             for k, c in results[H].items()} for H in HYPS}},
              open(HERE + "/seq_day_arc_20260817_out.json", "w"), indent=1, default=str)
    return verd, results

def null_perm_nameday(rows_t, rows_f, iters=5000, seed=17):
    """Permute the condition label across NAME-DAYS (a day-level attribute): pool the
    name-days on each side, reassign TRUE to a random same-size set of name-days, recompute
    the fire-level $/tr gap. One-sided p(perm gap >= obs)."""
    key = lambda r: (r["sym"], r["date"])
    nd_t = sorted({key(r) for r in rows_t}); nd_f = sorted({key(r) for r in rows_f})
    all_nd = nd_t + nd_f
    by = defaultdict(list)
    for r in rows_t + rows_f: by[key(r)].append(r["pnl"])
    obs = (sum(r["pnl"] for r in rows_t) / len(rows_t)) - (sum(r["pnl"] for r in rows_f) / len(rows_f))
    rnd = random.Random(seed); ge = 0; valid = 0
    k = len(nd_t)
    for _ in range(iters):
        pick = set(rnd.sample(all_nd, k))
        t = [p for nd in all_nd if nd in pick for p in by[nd]]
        f = [p for nd in all_nd if nd not in pick for p in by[nd]]
        if not t or not f: continue
        valid += 1
        if (sum(t) / len(t) - sum(f) / len(f)) >= obs: ge += 1
    return {"obs": obs, "p": ge / valid if valid else None, "iters": valid}

if __name__ == "__main__":
    main()
