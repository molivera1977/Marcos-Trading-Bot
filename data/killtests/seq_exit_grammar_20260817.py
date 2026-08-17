#!/usr/bin/env python3
"""EXIT-SIDE SEQUENCE GRAMMAR — 8/17/26.  Analysis only, no bot edits.

QUESTION: is there a DISTRIBUTION grammar — an event sequence AFTER entry that says
LEAVE — that beats mechanical E3 (bank 1/2 at +10%, 10%-off-run-high trail) on the
same champion-lane fires?  (EYES_MATRIX finding: E3 consults ZERO eyes at exit.)

PRE-REGISTERED exit triggers (pattern OR E3, whichever first; pattern = exit ALL
remaining at that 10s bar's close * (1-0.5%)):
  H1  X P D : volume climax (vol>=p90 of trade-so-far AND |c-to-c chg|<=0.3%), THEN a
      lower high (bar high < prior bar high), THEN a lower low (bar low < prior low).
  H2  climax bar itself: vol >= p95 of trade-so-far AND bar range >= 2x median range
      of trade-so-far -> exit into strength.
  H3  first lower low AFTER the bar that set the current run-high (aggressive).
  H4  two consecutive fade-volume pushes: push = bar high > prior bar high; two pushes
      in a row each on volume below the previous push's volume -> exit.
  H5  base E3 unchanged = control.
Warmup: no pattern may fire in the first 18 bars (3 min) after entry — percentiles of
"trade-so-far" need a population.  Per-bar order (F.sim_var parity): flatten -> haltgap
-> stop -> bank -> run-hi update -> PATTERN -> trail.

OOS protocol (seq_gate_oos_wall_20260817.py, unchanged): 62 dates, chronological split
MINE = earliest 44 (2026-05-18..07-21) / HOLD-OUT = latest 18 (07-22..08-14).  Grade all
variants on MINE; pick best by day-mean WITH worst-day guard (no variant wins if its
worst MINE day is >2x worse than E3's); FREEZE; grade winner on HOLD-OUT vs E3.
NULL: shuffle the winning variant's exit-trigger bar within each fired trade 1000x —
does a random early exit reproduce the lift?

Lanes/fires: PILOT.gen_lane("break_attack"/"grinder") + S.run baseline (E3 live-parity,
$500 clips, +1% chase entry, -0.5% exit slip, halt rule, grinder 19:59Z flatten, same-name
dedup <=5min).  Engine imported UNCHANGED.  Sanity: my E3 clone reproduces S.run to ~0.
"""
import importlib.util, os, json, random, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E
MKT = 0.005; SLIP = 0.01
WARMUP = 18  # 3 minutes of 10s bars

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

def pctile(vals, q):
    sv = sorted(vals); k = max(0, min(len(sv) - 1, int(q * (len(sv) - 1))))
    return sv[k]

def sim(bars, emas, gaps, entry_i, sig_px, stop, det, variant, force_i=None):
    """E3 live-parity clone + pattern overlay.  variant in {"E3","H1","H2","H3","H4","FORCE"}.
    Returns dict(pnl, exit, xi, fired(bool), fire_off(rel bar idx of pattern exit), peak)."""
    entry_px = sig_px * (1 + SLIP); sh = E.POS / entry_px
    rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * 0.5; target = entry_px * 1.10; run_hi = entry_px
    flatten = (det == "grinder"); e_s = E.secs(bars[entry_i])
    my_gaps = {post: pre for pre, post, g in gaps
               if entry_i <= pre and 0 <= E.secs(bars[pre]) - e_s <= 120}
    # pattern state
    vols = [bars[entry_i]["v"]]; rngs = [bars[entry_i]["h"] - bars[entry_i]["l"]]
    h1_state = 0            # 0 need X, 1 need lower-high, 2 need lower-low
    runhi_i = entry_i
    fade_count = 0; last_push_vol = None
    peak = 0.0

    def finish(i, tag, px, fired, fire_off):
        nonlocal pnl
        pnl += rem * (px - entry_px)
        return dict(pnl=pnl, exit=tag, xi=i, fired=fired, fire_off=fire_off, peak=peak,
                    hold_s=E.secs(bars[i]) - e_s)

    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; p = bars[i - 1]; hh = E.hhmm_b(b)
        if flatten and hh >= "19:59:00":
            return finish(i, "eod", b["c"] * (1 - MKT), False, None)
        if i in my_gaps and b["o"] < stop:
            return finish(i, f"haltgap@{hh}", b["o"] * (1 - MKT), False, None)
        if b["l"] <= stop:
            return finish(i, f"stop@{hh}", stop * (1 - MKT), False, None)
        if not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            vols.append(b["v"]); rngs.append(b["h"] - b["l"])
            continue
        if b["h"] > run_hi:
            run_hi = b["h"]; runhi_i = i
        peak = max(peak, pnl + rem * (run_hi - entry_px))
        # ---- pattern check (after warmup) ----
        off = i - entry_i
        fire = False
        if variant == "FORCE":
            fire = (force_i is not None and i >= force_i)
        elif off >= WARMUP:
            if variant == "H1":
                if h1_state == 0:
                    chg = abs(b["c"] / p["c"] - 1) if p["c"] else 0
                    if b["v"] >= pctile(vols, 0.90) and chg <= 0.003: h1_state = 1
                elif h1_state == 1:
                    if b["h"] < p["h"]: h1_state = 2
                elif h1_state == 2:
                    if b["l"] < p["l"]: fire = True
            elif variant == "H2":
                med = statistics.median(rngs)
                if b["v"] >= pctile(vols, 0.95) and med > 0 and (b["h"] - b["l"]) >= 2 * med:
                    fire = True
            elif variant == "H3":
                if runhi_i < i and b["l"] < p["l"]: fire = True
            elif variant == "H4":
                if b["h"] > p["h"]:                       # a push
                    if last_push_vol is not None and b["v"] < last_push_vol:
                        fade_count += 1
                    else:
                        fade_count = 0
                    last_push_vol = b["v"]
                    if fade_count >= 2: fire = True
        vols.append(b["v"]); rngs.append(b["h"] - b["l"])
        if fire:
            return finish(i, f"pat@{hh}", b["c"] * (1 - MKT), True, off)
        if scaled and b["c"] < run_hi * 0.90:
            return finish(i, f"trail@{hh}", b["c"] * (1 - MKT), False, None)
    b = bars[-1]
    return finish(len(bars) - 1, "eod", b["c"] * (1 - MKT), False, None)

def daystats(rows, dates, pnl_key="pnl"):
    d = {dt: 0.0 for dt in dates}
    for r in rows: d[r["date"]] += r[pnl_key]
    vals = [d[k] for k in dates]; n = len(vals)
    sv = sorted(vals); med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
    tot = sum(vals)
    return dict(N=len(rows), tot=tot, dtr=tot / len(rows) if rows else 0,
                dmean=tot / n, dmed=med, worst=min(vals),
                green=100 * sum(1 for v in vals if v > 0) / n)

def main():
    P("# EXIT-SIDE SEQUENCE GRAMMAR — 8/17/26 (H1-H4 vs mechanical E3)")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    n_hold = 18
    mine_dates = sorted(dates[:-n_hold]); hold_dates = sorted(dates[-n_hold:])
    P(f"MINE {mine_dates[0]}..{mine_dates[-1]} ({len(mine_dates)}) | "
      f"HOLD-OUT {hold_dates[0]}..{hold_dates[-1]} ({len(hold_dates)})")
    VARIANTS = ["H1", "H2", "H3", "H4"]
    results = {}
    for key, nm in (("break_attack", "flat_top BREAK-ATTACK"), ("grinder", "GRINDER")):
        P(f"\n---\n## LANE: {nm}")
        fires = PILOT.gen_lane(key)
        base = S.run(fires)                      # E3 control, deduped — the fire set of record
        # sanity: my sim(E3) == S.run pnl
        mx = 0.0
        sims = {}
        for v in ["E3"] + VARIANTS:
            rows = []
            for x in base:
                bars, emas, gaps = E.DAYS[(x["sym"], x["date"])]
                r = sim(bars, emas, gaps, x["i"], x["entry"], x["stop"], x["det"],
                        v if v != "E3" else "E3")
                rows.append({**x, "vpnl": r["pnl"], "vexit": r["exit"], "fired": r["fired"],
                             "fire_i": (x["i"] + r["fire_off"]) if r["fire_off"] else None,
                             "hold_s": r["hold_s"], "peak": r["peak"], "e3_pnl": x["pnl"]})
                if v == "E3": mx = max(mx, abs(r["pnl"] - x["pnl"]))
            sims[v] = rows
        P(f"Fires (deduped): {len(base)}. Sanity |my-E3 - S.run| max = {mx:.6f}")
        mine = {v: [r for r in sims[v] if r["date"] in set(mine_dates)] for v in sims}
        hold = {v: [r for r in sims[v] if r["date"] in set(hold_dates)] for v in sims}
        m_act = sorted({r["date"] for r in mine["E3"]})
        h_act = sorted({r["date"] for r in hold["E3"]})

        def block(tag, cohort, act):
            P(f"\n### {tag} ({len(cohort['E3'])} fires, {len(act)} active dates)")
            P("| variant | total | $/tr | day mean | day med | worst | green% | fired | avg hold | giveback | recov% |")
            P("|---|---|---|---|---|---|---|---|---|---|---|")
            st = {}
            gv_e3 = sum(r["peak"] - r["vpnl"] for r in cohort["E3"])
            for v in ["E3"] + VARIANTS:
                rows = cohort[v]; s = daystats(rows, act, "vpnl")
                fired = sum(1 for r in rows if r["fired"])
                hold_m = sum(r["hold_s"] for r in rows) / len(rows) / 60 if rows else 0
                gv = sum(r["peak"] - r["vpnl"] for r in rows)
                rec = 100 * (1 - gv / gv_e3) if gv_e3 else 0
                P(f"| {v} | ${s['tot']:+.2f} | ${s['dtr']:+.2f} | ${s['dmean']:+.2f} | "
                  f"${s['dmed']:+.2f} | ${s['worst']:+.2f} | {s['green']:.0f}% | {fired} | "
                  f"{hold_m:.0f}m | ${gv:+.0f} | {rec:+.0f}% |")
                st[v] = s
            return st

        m_st = block("MINE", mine, m_act)
        # pick winner on MINE: best day-mean beating E3, with worst-day guard
        e3w = m_st["E3"]["worst"]
        cand = []
        for v in VARIANTS:
            s = m_st[v]
            guard_ok = s["worst"] >= 2 * e3w if e3w < 0 else s["worst"] >= e3w - abs(e3w)
            if s["dmean"] > m_st["E3"]["dmean"] and guard_ok:
                cand.append((s["dmean"], v))
            elif s["dmean"] > m_st["E3"]["dmean"]:
                P(f"NOTE: {v} beats E3 day-mean on MINE but FAILS worst-day guard "
                  f"(worst ${s['worst']:+.2f} vs 2x E3 ${2*e3w:+.2f}) — disqualified.")
        h_st = block("HOLD-OUT (all variants shown for transparency; only the FROZEN winner counts)",
                     hold, h_act)
        if not cand:
            P(f"\n**No variant beat E3 on MINE (day-mean) with the worst-day guard.**")
            best_mine = max((m_st[v]["dmean"], v) for v in VARIANTS)
            verdict = "NO-LIFT"
            why = (f"best pattern on MINE ({best_mine[1]}) day-mean ${best_mine[0]:+.2f} vs "
                   f"E3 ${m_st['E3']['dmean']:+.2f} — nothing to freeze")
            winner = None
        else:
            cand.sort(reverse=True)
            winner = cand[0][1]
            P(f"\n**FROZEN winner from MINE: {winner}** (day-mean ${m_st[winner]['dmean']:+.2f} "
              f"vs E3 ${m_st['E3']['dmean']:+.2f}).")
            hs = h_st[winner]; he = h_st["E3"]
            lift = hs["dmean"] - he["dmean"]
            n_fired_hold = sum(1 for r in hold[winner] if r["fired"])
            # NULL: shuffle exit-trigger bar within each fired trade, 1000x
            rnd = random.Random(17)
            fired_rows = [r for r in hold[winner] if r["fired"]]
            base_pnl_hold = {id(r): r["vpnl"] for r in hold[winner]}
            null_means = []
            for _ in range(1000):
                tot_shift = 0.0
                for r in fired_rows:
                    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]
                    e3_xi = r["xi"]  # E3-of-record exit bar (from S.run row)
                    lo = r["i"] + WARMUP
                    hi_b = max(lo, e3_xi - 1)
                    j = rnd.randint(lo, hi_b)
                    rr = sim(bars, emas, gaps, r["i"], r["entry"], r["stop"], r["det"],
                             "FORCE", force_i=j)
                    tot_shift += rr["pnl"] - r["vpnl"]
                null_means.append(hs["dmean"] + tot_shift / len(h_act))
            p_ge = sum(1 for m in null_means if m >= hs["dmean"] + 0) / len(null_means)
            # compare: does random early exit achieve the WINNER's lift over E3?
            p_null_beats = sum(1 for m in null_means if m - he["dmean"] >= lift) / len(null_means)
            P(f"\nHOLD-OUT: {winner} day-mean ${hs['dmean']:+.2f} vs E3 ${he['dmean']:+.2f} "
              f"(lift ${lift:+.2f}); fired on {n_fired_hold}/{len(hold[winner])} trades.")
            P(f"NULL (1000 shuffles of the trigger bar within each fired trade): "
              f"random-early-exit day-mean mean ${sum(null_means)/len(null_means):+.2f}, "
              f"P(random >= {winner}) = {p_ge:.3f}, P(random lift >= observed lift) = {p_null_beats:.3f}")
            if n_fired_hold < 15:
                verdict = "UNDERPOWERED"; why = f"{winner} fired on only {n_fired_hold} hold-out trades"
            elif lift > 5 and hs["worst"] >= 2 * he["worst"]:
                if p_null_beats < 0.10:
                    verdict = "EXIT-GRAMMAR-BEATS-E3"
                    why = f"{winner} hold-out day-mean lift ${lift:+.2f}, null p={p_null_beats:.3f}"
                else:
                    verdict = "NO-LIFT"
                    why = f"{winner} lift ${lift:+.2f} but random early-exit reproduces it (p={p_null_beats:.3f})"
            else:
                verdict = "NO-LIFT"
                why = f"{winner} froze on MINE but hold-out lift ${lift:+.2f} (worst ${hs['worst']:+.2f} vs E3 ${he['worst']:+.2f})"
        P(f"\n**VERDICT [{nm}]: {verdict}** — {why}.")
        results[key] = dict(verdict=verdict, why=why, winner=winner,
                            mine={v: m_st[v] for v in m_st},
                            hold={v: h_st[v] for v in h_st})
    P("\n---\n## SUMMARY")
    P("| lane | winner | MINE day-mean (win vs E3) | HOLD-OUT day-mean (win vs E3) | verdict |")
    P("|---|---|---|---|---|")
    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder")):
        r = results[key]; w = r["winner"]
        ms = (f"${r['mine'][w]['dmean']:+.2f} vs ${r['mine']['E3']['dmean']:+.2f}" if w else
              f"— vs ${r['mine']['E3']['dmean']:+.2f}")
        hs = (f"${r['hold'][w]['dmean']:+.2f} vs ${r['hold']['E3']['dmean']:+.2f}" if w else
              f"— vs ${r['hold']['E3']['dmean']:+.2f}")
        P(f"| {nm} | {w or '-'} | {ms} | {hs} | {r['verdict']} |")
    open(HERE + "/seq_exit_grammar_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump(results, open(HERE + "/seq_exit_grammar_20260817_out.json", "w"),
              indent=1, default=str)
    return results

if __name__ == "__main__":
    main()
