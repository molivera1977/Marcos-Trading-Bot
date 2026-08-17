#!/usr/bin/env python3
"""CROSS-TICKER SEQUENCE study 8/17 — the BOARD as the instrument.

Kev watches the BOARD: does the ORDER of events ACROSS names carry signal?
Pre-registered hypotheses, all graded on break-attack + grinder fires, E3 $500
(engine chain imported UNCHANGED via sequence_mining_pilot_20260817.py):

  H1 LEADER-FOLLOWER : on dates with >=3 universe names, LEADER = first name to print a
                       new session high after 09:30 on BURST volume. Fires on OTHER names
                       within 30 min AFTER the leader's break (sympathy window) vs fires
                       outside it.
  H2 SECOND-MOVER    : second name to burst-break within 30 min of the leader — its fires
                       vs the leader's own fires.
  H3 BOARD-HEAT      : count of OTHER universe names printing new session highs in the
                       trailing 15 min at fire time (0/1/2+). 2+ vs 0-1.
  H4 SOLE-RUNNER     : fires when NO other universe name has burst-broken in the prior
                       60 min vs crowded fires.

Definitions (pre-registered):
  * session high baseline = max premarket high from the FULL file (bars before 13:30Z);
    a NEW SESSION HIGH = RTH bar whose high exceeds the running session high.
  * BURST volume = bar volume >= 3x the mean volume of the prior 30 bars (>=12 prior
    bars required).
  * All times UTC from the bars; 09:30 ET = 13:30:00Z.

OOS protocol (same wall as seq_gate_oos_wall_20260817.py): chronological split, earliest
44 dates = MINE, latest 18 = HOLD-OUT. Splits mined on MINE only (material = both sides
N>=15, else UNDERPOWERED); winning condition FROZEN; verified on HOLD-OUT. NULL for
surviving hypotheses: within each date, shuffle the (sym,time) board-context across that
date's hold-out fires 5000x (pnl stays with the fire), p = P(random gated $/tr >= observed).

CAVEAT (honest): the universe is gain>=40% runners ONLY, not the full live board —
leader/heat/sole definitions are within-universe proxies.

VERDICT per hypothesis: BOARD-SIGNAL / NO-SPLIT / UNDERPOWERED. Analysis only. No bot edits.
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

def sec(hh):  # "HH:MM:SS" -> seconds
    return int(hh[0:2]) * 3600 + int(hh[3:5]) * 60 + int(hh[6:8])

# ---------------- per-date board structures ----------------
def build_board():
    """per date: new-high event times per sym (any volume), burst-break times per sym."""
    highs = defaultdict(lambda: defaultdict(list))   # date -> sym -> [sec,...] new session highs
    bursts = defaultdict(lambda: defaultdict(list))  # date -> sym -> [sec,...] burst new highs
    nsyms = defaultdict(int)
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        nsyms[date] += 1
        # premarket baseline from the FULL file
        full = S.FULL.get((sym, date), [])
        pre = [b for b in full if E.hhmm_b(b) < "13:30:00"]
        sess_hi = max((b["h"] for b in pre), default=bars[0]["h"])
        vols = [b["v"] for b in bars]
        for i, b in enumerate(bars):
            if b["h"] > sess_hi:
                t = sec(E.hhmm_b(b))
                highs[date][sym].append(t)
                if i >= 12:
                    prior = vols[max(0, i - 30):i]
                    if b["v"] >= 3.0 * (sum(prior) / len(prior)):
                        bursts[date][sym].append(t)
                sess_hi = b["h"]
    board = {}
    for date in nsyms:
        ev = sorted((t, sym) for sym, ts in bursts[date].items() for t in ts)
        leader = leader_t = second = second_t = None
        if ev:
            leader_t, leader = ev[0]
            for t, sym in ev[1:]:
                if sym != leader and t <= leader_t + 1800:
                    second, second_t = sym, t
                    break
        board[date] = dict(n=nsyms[date], highs=dict(highs[date]), bursts=dict(bursts[date]),
                           leader=leader, leader_t=leader_t, second=second, second_t=second_t)
    return board

# ---------------- condition flags (functions of sym + fire time + date board) ----------------
def flag_h1(bd, sym, t):   # sympathy-window fire (qualifying dates handled by caller)
    return (bd["leader"] is not None and sym != bd["leader"]
            and bd["leader_t"] <= t <= bd["leader_t"] + 1800)

def flag_h2(bd, sym, t):   # on the second-mover name (vs leader name, caller restricts)
    return sym == bd["second"]

def heat(bd, sym, t):      # OTHER names with a new session high in [t-900, t]
    return sum(1 for s2, ts in bd["highs"].items()
               if s2 != sym and any(t - 900 <= x <= t for x in ts))

def flag_h3(bd, sym, t):   # board-heat 2+
    return heat(bd, sym, t) >= 2

def flag_h4(bd, sym, t):   # sole runner: no OTHER burst break in prior 60 min
    return not any(s2 != sym and any(t - 3600 <= x < t for x in ts)
                   for s2, ts in bd["bursts"].items())

def mstat(rows):
    n = len(rows)
    if n == 0: return dict(N=0, dtr=0.0, win=0.0, tot=0.0)
    tot = sum(r["pnl"] for r in rows)
    return dict(N=n, dtr=tot / n, win=100 * sum(1 for r in rows if r["win"]) / n, tot=tot)

def fmt(nm, s):
    return f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['dtr']:+.2f} | ${s['tot']:+.2f} |"

HDR = "| side | N | win | $/tr | total |"
SEP = "|---|---|---|---|---|"

# ---------------- permutation null (board-context shuffle within date) ----------------
def null_shuffle(fires, board, flagfn, qualifies, obs_gated_mean, gate_side_true, iters=5000, seed=17):
    """within each date, shuffle the (sym,time) pairs across that date's fires; recompute
    the flag; gated mean distribution. p = P(random gated $/tr >= observed)."""
    rnd = random.Random(seed)
    bydate = defaultdict(list)
    for r in fires: bydate[r["date"]].append(r)
    ge = 0; means = []
    for _ in range(iters):
        gp = [];
        for date, rs in bydate.items():
            bd = board[date]
            pairs = [(r["sym"], r["tsec"]) for r in rs]
            rnd.shuffle(pairs)
            for r, (sym, t) in zip(rs, pairs):
                if not qualifies(bd, sym): continue
                f = flagfn(bd, sym, t)
                if f == gate_side_true: gp.append(r["pnl"])
        mu = sum(gp) / len(gp) if gp else 0.0
        means.append(mu)
        if mu >= obs_gated_mean: ge += 1
    return dict(p=ge / iters, rand_mean=sum(means) / len(means), iters=iters)

# ---------------- main ----------------
def main():
    P("# CROSS-TICKER SEQUENCE STUDY — 8/17/26 (the board as the instrument)")
    P("Engine chain UNCHANGED via sequence_mining_pilot_20260817.py (E3 live-parity exits).")
    P("Fires = break-attack + grinder (pooled, lane-tagged). Analysis only, no bot edits.")
    P("")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    n_hold = 18
    mine_dates = set(dates[:-n_hold]); hold_dates = set(dates[-n_hold:])
    P(f"OOS split: MINE {len(mine_dates)} dates ..{sorted(mine_dates)[-1]} | HOLD-OUT {len(hold_dates)} dates {sorted(hold_dates)[0]}..")
    P("")
    P("**CAVEAT (stated up front): the universe is gain>=40% runners only — NOT the full live")
    P("board. LEADER / SECOND-MOVER / BOARD-HEAT / SOLE-RUNNER are within-universe proxies for")
    P("what Kev's board would show; a name leading this cohort may have been a follower of a")
    P("non-universe mover. Findings are conditional on that proxy.**")
    P("")

    board = build_board()
    n3 = sum(1 for d in dates if board[d]["n"] >= 3)
    nl = sum(1 for d in dates if board[d]["leader"] is not None)
    ns = sum(1 for d in dates if board[d]["second"] is not None)
    P(f"Board: {n3}/{len(dates)} dates have >=3 universe names; {nl} dates have a burst LEADER; "
      f"{ns} dates have a SECOND-MOVER within 30 min.")

    rows = []
    for key in ("break_attack", "grinder"):
        for r in PILOT.grade(PILOT.gen_lane(key)):
            r["lane"] = key; r["tsec"] = sec(r["t"])
            rows.append(r)
    P(f"Fires: {len(rows)} total (break-attack + grinder, E3-graded, deduped).")
    P("")

    HYPS = [
        ("H1 LEADER-FOLLOWER", flag_h1,
         lambda bd, sym: bd["n"] >= 3 and bd["leader"] is not None,
         "sympathy-window fire (other name, <=30min after leader burst)", "outside window"),
        ("H2 SECOND-MOVER", flag_h2,
         lambda bd, sym: bd["second"] is not None and sym in (bd["leader"], bd["second"]),
         "fire on SECOND-MOVER name", "fire on LEADER name"),
        ("H3 BOARD-HEAT", flag_h3,
         lambda bd, sym: True,
         "heat 2+ (>=2 other names new-high in trailing 15min)", "heat 0-1"),
        ("H4 SOLE-RUNNER", flag_h4,
         lambda bd, sym: True,
         "SOLE runner (no other burst break in 60min)", "crowded"),
    ]

    verdicts = {}
    for nm, flagfn, qual, lblT, lblF in HYPS:
        P(f"\n---\n\n## {nm}")
        P(f"- TRUE side: {lblT}\n- FALSE side: {lblF}")
        qrows = [r for r in rows if qual(board[r["date"]], r["sym"])]
        for r in qrows:
            r["_f"] = flagfn(board[r["date"]], r["sym"], r["tsec"])
        mT = [r for r in qrows if r["date"] in mine_dates and r["_f"]]
        mF = [r for r in qrows if r["date"] in mine_dates and not r["_f"]]
        hT = [r for r in qrows if r["date"] in hold_dates and r["_f"]]
        hF = [r for r in qrows if r["date"] in hold_dates and not r["_f"]]
        sT, sF = mstat(mT), mstat(mF)
        P(f"\n### MINE ({len(mT)+len(mF)} qualifying fires)")
        P(HDR); P(SEP); P(fmt("TRUE  " + lblT, sT)); P(fmt("FALSE " + lblF, sF))
        mine_lift = sT["dtr"] - sF["dtr"]
        P(f"MINE split: TRUE-FALSE $/tr lift ${mine_lift:+.2f}.")
        # H3 extra transparency: full heat histogram on MINE
        if nm.startswith("H3"):
            hb = defaultdict(list)
            for r in qrows:
                if r["date"] in mine_dates:
                    hb[min(heat(board[r["date"]], r["sym"], r["tsec"]), 2)].append(r)
            for k in (0, 1, 2):
                s = mstat(hb.get(k, []))
                P(f"  heat={k if k<2 else '2+'}: N={s['N']} win {s['win']:.0f}% $/tr ${s['dtr']:+.2f}")

        if sT["N"] < 15 or sF["N"] < 15:
            P(f"\n**VERDICT: UNDERPOWERED** — MINE sides N={sT['N']}/{sF['N']} (need both >=15).")
            verdicts[nm] = dict(verdict="UNDERPOWERED",
                                mine=(sT["N"], sF["N"], mine_lift), hold=None, p=None)
            continue

        # freeze the MINE-better side as the gate
        gate_true = mine_lift > 0
        gside = lblT if gate_true else lblF
        P(f"\nFROZEN gate = keep the MINE-better side: **{gside}**.")
        hS, hO = mstat(hT), mstat(hF)
        P(f"\n### HOLD-OUT ({len(hT)+len(hF)} qualifying fires) — frozen gate applied")
        P(HDR); P(SEP); P(fmt("TRUE  " + lblT, hS)); P(fmt("FALSE " + lblF, hO))
        hold_lift = (hS["dtr"] - hO["dtr"]) if gate_true else (hO["dtr"] - hS["dtr"])
        gN = hS["N"] if gate_true else hO["N"]
        gmean = hS["dtr"] if gate_true else hO["dtr"]
        P(f"HOLD-OUT: frozen-side N={gN}, $/tr ${gmean:+.2f}; gate lift ${hold_lift:+.2f} "
          f"(MINE direction {'HELD' if hold_lift > 0 else 'REVERSED/VANISHED'}).")

        pv = None
        if gN >= 10 and hold_lift > 0:
            hq = hT + hF
            nr = null_shuffle(hq, board, flagfn, qual, gmean, gate_true)
            pv = nr["p"]
            P(f"\nNULL (board-context shuffle within date, {nr['iters']}x on hold-out): "
              f"observed gated $/tr ${gmean:+.2f} vs random-mean ${nr['rand_mean']:+.2f}, p={pv:.3f}.")

        if gN < 10:
            verdict = "UNDERPOWERED"; why = f"frozen side carries only {gN} hold-out fires"
        elif abs(mine_lift) <= 5:
            verdict = "NO-SPLIT"; why = f"MINE lift ${mine_lift:+.2f} immaterial (<=$5/tr)"
        elif hold_lift <= 0:
            verdict = "NO-SPLIT"; why = f"hold-out lift ${hold_lift:+.2f} — MINE direction did not survive"
        elif pv is not None and pv < 0.05:
            verdict = "BOARD-SIGNAL"; why = f"hold-out lift ${hold_lift:+.2f}, null p={pv:.3f}"
        else:
            verdict = "NO-SPLIT"; why = f"hold-out lift ${hold_lift:+.2f} but null p={pv} — not separable from chance"
        P(f"\n**VERDICT: {verdict}** — {why}.")
        verdicts[nm] = dict(verdict=verdict, mine=(sT["N"], sF["N"], mine_lift),
                            hold=(hS["N"], hF and hO["N"] or 0, hold_lift), p=pv,
                            mine_true_dtr=sT["dtr"], mine_false_dtr=sF["dtr"],
                            hold_true_dtr=hS["dtr"], hold_false_dtr=hO["dtr"])

    P("\n---\n\n## SUMMARY")
    P("| hypothesis | MINE N(T/F) | MINE lift | HOLD-OUT lift | p | verdict |")
    P("|---|---|---|---|---|---|")
    for nm, v in verdicts.items():
        mN = f"{v['mine'][0]}/{v['mine'][1]}"
        ml = f"${v['mine'][2]:+.2f}"
        hl = f"${v['hold'][2]:+.2f}" if v.get("hold") else "-"
        pp = f"{v['p']:.3f}" if v.get("p") is not None else "-"
        P(f"| {nm} | {mN} | {ml} | {hl} | {pp} | {v['verdict']} |")

    open(HERE + "/seq_cross_ticker_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump(verdicts, open(HERE + "/seq_cross_ticker_20260817_out.json", "w"), indent=1, default=str)
    return verdicts

if __name__ == "__main__":
    main()
