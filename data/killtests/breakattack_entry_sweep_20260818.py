#!/usr/bin/env python3
"""
BREAK-ATTACK ENTRY SWEEP — 8/18 (Marcos: "these entries need to be fixed with the new harness")

THE QUESTION
  Break-attack currently enters at the CLOSE OF THE BAR THAT BREAKS the base, and stops at the
  base low. Neither choice has ever been measured against an alternative. This sweeps the entry
  knobs — WHEN we get in and WHERE the stop goes — over the whole clean cache.

WHY THIS CAN RUN TONIGHT (and does not need tomorrow's rows)
  Two different inputs, and they are easy to confuse:
    * harness PARITY ("does the replay reproduce the live bot") needs 8/18's stamped rows.
    * an ENTRY SWEEP ("which entry rule makes more money") needs only clean TAPE.
  This uses the universe 10s SIP cache — 63 dates 2026-05-18..2026-08-17, 738 name-days — the
  same input the OOS wall used, and it never touches a decision row. That is exactly why the
  `T B` finding is the one entry result that is not contaminated.

ENGINE — imported UNCHANGED, nothing re-implemented
  S -> G -> F -> C -> B -> E via sequence_mining_pilot_20260817.py, the same chain the pilot and
  the OOS wall use. Exits are E3 live-parity: F.sim_var(..., "E3", det, halt_rule=True) — bank
  1/2 at +10%, trail the rest 10%-off-run-high on a close-through, stop-first intrabar, -1%
  chase entry, -0.5% market-exit slip. Window 09:30-10:30 ET, the break-attack cell.

BASELINE (what the bot does today, verbatim from G.det_flat_top_break)
  base   : last 4 completed 3-min bars, (hi-lo)/lo <= 0.12
  fire   : first 10s bar whose CLOSE > base high
  entry  : that bar's close
  stop   : base low
  cooldown 900s, one open trade at a time

VARIANTS SWEPT (one knob at a time — never two at once, so a win is attributable)
  ENTRY TIMING
    e_close     entry = breaking bar's close                       [BASELINE]
    e_level     entry = the base high itself (the level, not the print)
    e_retest_R  after the break, WAIT for a pullback to level*(1-R) within 15 min and enter
                there; no touch -> NO TRADE (the measured cost of patience is counted, not hidden)
                R in {0.5%, 1.0%, 2.0%}
  STOP ANCHOR
    s_baselo    stop = base low                                    [BASELINE]
    s_barlow    stop = the breaking bar's low
    s_level     stop = the level (break-even-ish, tightest)
    s_halfway   stop = midpoint of base low and level
  BASE TIGHTNESS
    w_12        (hi-lo)/lo <= 0.12                                 [BASELINE]
    w_08 / w_06 tighter bases only

PROTOCOL (pre-registered, written before the run)
  1. Full-sample sweep, all cells reported — winners AND losers, no cherry-picking.
  2. Any cell that beats the baseline goes to a CHRONOLOGICAL OOS WALL: re-rank on the earliest
     44 dates only, freeze, apply to the unseen 18. Same split the `T B` wall used.
  3. A cell is a CANDIDATE only if it beats baseline in-sample AND holds direction out-of-sample
     AND carries N >= 100 fires. Anything else is reported as NOT ESTABLISHED.
  4. No cell ships from this script. Numbers only; Marcos decides.

DOLLARS, not R (feedback_dollars_not_r): every figure below is E3 dollars at the engine's
position sizing, the same basis as the pilot and the wall, so the numbers are comparable to
what is already on the ledger.
"""
import importlib.util
import json
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PILOT)
S, G, F, C, B, E = PILOT.S, PILOT.G, PILOT.F, PILOT.C, PILOT.B, PILOT.E

OUT = []


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


WIN_LO, WIN_HI = "13:30:00", "14:30:00"   # 09:30-10:30 ET in the cache's Z stamps


def in_window(b):
    return WIN_LO <= E.hhmm_b(b) < WIN_HI


def det_break_attack(bars, width, entry_mode, stop_mode, retest_pct=None):
    """G.det_flat_top_break with the entry knobs parameterised. Baseline =
    (width=0.12, entry_mode='close', stop_mode='baselo'). Structure otherwise VERBATIM."""
    trades = []
    m3 = E.agg3min(bars)
    state = "seek"
    level = base_lo = None
    open_until = -1
    cooldown_until = -1
    for i, b in enumerate(bars):
        if i <= open_until:
            continue
        done = [x for x in m3 if x["end_t"] < b["t"]]
        if state in ("seek", "armed") and len(done) >= 4:
            w = done[-4:]
            hi = max(x["h"] for x in w)
            lo = min(x["l"] for x in w)
            if lo > 0 and (hi - lo) / lo <= width:
                level, base_lo = hi, lo
                state = "armed"
            elif state == "seek":
                continue
        if state != "armed" or level is None:
            continue
        if b["c"] > level:
            if E.secs(b) < cooldown_until:
                state = "seek"; level = base_lo = None; continue
            if not in_window(b):
                state = "seek"; level = base_lo = None; continue

            fire_i, entry = i, None
            if entry_mode == "close":
                entry = b["c"]
            elif entry_mode == "level":
                entry = level
            elif entry_mode == "retest":
                # wait for a pullback to level*(1-retest_pct) within 15 min; no touch -> NO TRADE.
                tgt = level * (1 - retest_pct)
                deadline = E.secs(b) + 900
                hit = None
                for j in range(i + 1, len(bars)):
                    if E.secs(bars[j]) > deadline:
                        break
                    if bars[j]["l"] <= tgt:
                        hit = j; break
                if hit is None:
                    state = "seek"; level = base_lo = None
                    cooldown_until = E.secs(b) + 900
                    continue
                fire_i, entry = hit, tgt

            if stop_mode == "baselo":
                stop = base_lo
            elif stop_mode == "barlow":
                stop = bars[fire_i]["l"]
            elif stop_mode == "level":
                stop = level
            elif stop_mode == "halfway":
                stop = (base_lo + level) / 2.0
            else:
                stop = base_lo

            if stop < entry:
                pnl, ex, xi = F.sim_var(bars, EMAS[id(bars)], GAPS[id(bars)], fire_i,
                                        entry, stop, "E3", "flat_top", halt_rule=True)
                trades.append({"i": fire_i, "entry": entry, "stop": stop,
                               "level": level, "pnl": pnl, "exit": ex})
                open_until = xi
                cooldown_until = E.secs(b) + 900
            state = "seek"; level = base_lo = None
    return trades


EMAS, GAPS = {}, {}


def run_cell(width, entry_mode, stop_mode, retest_pct=None, dates=None):
    rows = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        if dates is not None and date not in dates:
            continue
        EMAS[id(bars)] = emas; GAPS[id(bars)] = gaps
        for t in det_break_attack(bars, width, entry_mode, stop_mode, retest_pct):
            t["sym"], t["date"] = sym, date
            rows.append(t)
    return rows


def summarize(rows):
    if not rows:
        return {"n": 0, "total": 0.0, "per": 0.0, "win": 0.0, "green": 0.0, "worst": 0.0}
    p = [r["pnl"] for r in rows]
    byday = defaultdict(float)
    for r in rows:
        byday[r["date"]] += r["pnl"]
    return {"n": len(p), "total": sum(p), "per": sum(p) / len(p),
            "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
            "green": 100.0 * sum(1 for v in byday.values() if v > 0) / len(byday),
            "worst": min(byday.values())}


def line(label, s, base=None):
    d = ""
    if base and s["n"]:
        d = f"   Δ/tr {s['per'] - base['per']:+7.2f}"
    P(f"  {label:24s} n={s['n']:5d}  total=${s['total']:+10.2f}  $/tr={s['per']:+7.2f}  "
      f"win={s['win']:4.0f}%  green={s['green']:3.0f}%  worst=${s['worst']:+8.2f}{d}")


def main():
    nf, nd, dates = S.load_all()
    dates = sorted(set(d for (_, d) in E.DAYS.keys()))
    P("=" * 100)
    P("BREAK-ATTACK ENTRY SWEEP — 8/18   (engine S->G->F->C->B->E unchanged; exits E3 live-parity)")
    P("=" * 100)
    P(f"universe: {len(E.DAYS)} name-days over {len(dates)} dates  {dates[0]} .. {dates[-1]}")
    P("window 09:30-10:30 ET. Baseline = entry at the BREAKING BAR'S CLOSE, stop at the BASE LOW,")
    P("base width <= 12%. One knob at a time; a win is attributable or it is not reported.\n")

    base = summarize(run_cell(0.12, "close", "baselo"))
    P("BASELINE (what the bot does today)")
    line("e_close / s_baselo / 12%", base)

    P("\nENTRY TIMING (stop + width held at baseline)")
    cells = {}
    for lbl, em, rp in [("e_level", "level", None), ("e_retest 0.5%", "retest", 0.005),
                        ("e_retest 1.0%", "retest", 0.010), ("e_retest 2.0%", "retest", 0.020)]:
        s = summarize(run_cell(0.12, em, "baselo", rp)); cells[lbl] = s
        line(lbl, s, base)

    P("\nSTOP ANCHOR (entry + width held at baseline)")
    for lbl, sm in [("s_barlow", "barlow"), ("s_halfway", "halfway"), ("s_level", "level")]:
        s = summarize(run_cell(0.12, "close", sm)); cells[lbl] = s
        line(lbl, s, base)

    P("\nBASE TIGHTNESS (entry + stop held at baseline)")
    for lbl, w in [("w_08", 0.08), ("w_06", 0.06)]:
        s = summarize(run_cell(w, "close", "baselo")); cells[lbl] = s
        line(lbl, s, base)

    # ---- OOS wall on anything that beat baseline ----
    P("\n" + "=" * 100)
    P("CHRONOLOGICAL OOS WALL — re-rank on the earliest 44 dates, freeze, apply to the unseen 18")
    P("=" * 100)
    tr, ho = set(dates[:44]), set(dates[44:])
    P(f"TRAIN {min(tr)}..{max(tr)} ({len(tr)})   HOLD-OUT {min(ho)}..{max(ho)} ({len(ho)})\n")

    winners = [k for k, v in cells.items() if v["n"] >= 100 and v["per"] > base["per"]]
    if not winners:
        P("  NO cell beat the baseline with N>=100 in-sample. Nothing to wall.")
        P("  VERDICT: the current entry (break print + base-low stop) is NOT BEATEN by any knob")
        P("           tested here. That is a real result: the entry is not the broken part.")
    else:
        b_tr = summarize(run_cell(0.12, "close", "baselo", None, tr))
        b_ho = summarize(run_cell(0.12, "close", "baselo", None, ho))
        P(f"  baseline  TRAIN $/tr {b_tr['per']:+7.2f} (n={b_tr['n']})   "
          f"HOLD-OUT $/tr {b_ho['per']:+7.2f} (n={b_ho['n']})\n")
        SPEC = {"e_level": (0.12, "level", "baselo", None),
                "e_retest 0.5%": (0.12, "retest", "baselo", 0.005),
                "e_retest 1.0%": (0.12, "retest", "baselo", 0.010),
                "e_retest 2.0%": (0.12, "retest", "baselo", 0.020),
                "s_barlow": (0.12, "close", "barlow", None),
                "s_halfway": (0.12, "close", "halfway", None),
                "s_level": (0.12, "close", "level", None),
                "w_08": (0.08, "close", "baselo", None),
                "w_06": (0.06, "close", "baselo", None)}
        for k in winners:
            w, em, sm, rp = SPEC[k]
            s_tr = summarize(run_cell(w, em, sm, rp, tr))
            s_ho = summarize(run_cell(w, em, sm, rp, ho))
            lift_tr = s_tr["per"] - b_tr["per"]
            lift_ho = s_ho["per"] - b_ho["per"]
            ok = (lift_tr > 0 and lift_ho > 0 and s_ho["n"] >= 30)
            P(f"  {k:16s} TRAIN Δ/tr {lift_tr:+7.2f} (n={s_tr['n']:4d})   "
              f"HOLD-OUT Δ/tr {lift_ho:+7.2f} (n={s_ho['n']:4d})   "
              f"{'CANDIDATE' if ok else 'NOT ESTABLISHED (direction flipped or N too small)'}")

    P("\n" + "=" * 100)
    P("LIMITS")
    P("  * Detector-only. The live FUNNEL (scanner board membership, slot limits, found_entry")
    P("    suppression, an existing retest arm) sits UPSTREAM and is NOT modelled — the harness")
    P("    grades the detector, never the funnel. Fire counts here exceed live fire counts.")
    P("  * flat_top harness parity is 100% but on N=3 live fires (8/17). That is the ABSENCE of")
    P("    a disagreement, not a strong claim.")
    P("  * Base levels come off the 10s SIP roll; the live bot's M1 base can differ by cents")
    P("    (IPST 8/17: 8.1399/7.49 vs 8.09/7.46), which moves the stop ~3c. Feed difference,")
    P("    not a detector difference, and not attributable from this data.")
    P("  * retest cells count the COST OF PATIENCE: a break with no pullback inside 15 min is NO")
    P("    TRADE, and those forgone fires are simply absent from n. Compare $/tr AND n together.")
    P("  * No cell ships from this script.")
    json.dump({"out": OUT}, open(HERE + "/breakattack_entry_sweep_20260818_out.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
