#!/usr/bin/env python3
"""ROCKET SLEEVE KILL-TEST 8/16 — H-VERT + H-HALT as ONE regime lane (Rocket Rider / Hidden Entry Architect).
Analysis only. Chain reused unchanged for data + parity: flatten_parity_20260816 (FP) -> S -> G -> F -> C -> B -> E
(RTH 10s bars, E.find_gaps = >=4-min zero-print gaps, S.vwap_series = session VWAP, E.agg3min = 3-min bars).
LIVE parity: +1% entry chase slip, 0.5% market exit slip, no new entries >= 15:30 ET, flatten 15:45 ET, $500 clip.

REGIME (evaluated on every 10s bar): day-gain from RTH open >= G (100% primary, 60% secondary); close > session VWAP;
NO 4x3-min base (4 consecutive completed 3-min bars with (h-l)/l <= 12%) ending inside the last 30 min; >= 1 halt gap
whose resumption is inside the last 60 min.
ENTRY while in-regime: pullback low 10-30% below the session high, then first bar with low > prior low AND
close > prior high. Entry = close (+1% slip). Stop = pullback low. Cooldown 20 min/name, cap 2/name-day.
HALT VARIANTS: 'exit' = resumption bar opens below stop -> fill open-0.5% (honest gap-through);
'hold' = ignore intrabar low on the resumption bar; exit only if the resumption bar CLOSES below stop (fill close-0.5%).
EXITS: E3 (bank 50% @+10%, then 10%-off-high trail), E4 (never-bank, 10%-off-high), E4W (20%-off-high),
STRUCT (sell 1/3 at the session high standing at entry, 1/3 at the next new high after a >=10% dip from the running
high, remainder trails on the resumption-low ratchet: stop = max(stop, each halt-resumption bar low)); EOD flatten always.
"""
import importlib.util, os, io, contextlib, json, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
S = FP.S; F = FP.F; E = FP.E; B = FP.B
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = fn(*a, **k)
    return r

POS = 500.0; SLIP = 0.01; MKT = 0.005
FLAT_T = FP.FLAT_T; CUTOFF_T = FP.CUTOFF_T
BIG = json.load(open(HERE + "/big_rides_reverse_20260816.json"))
TOPKEY = {(r["sym"], r["date"]) for r in BIG["top"]}
POST11 = "15:00:00"   # 11:00 ET in UTC bar stamps

# ---------------- regime ----------------
def base_windows(bars):
    """list of (end_secs, ...) for every 4x3-min base (range <=12%) -> return list of end-secs of the base's last 3-min bar."""
    m3 = E.agg3min(bars); ends = []
    for k in range(len(m3) - 3):
        w = m3[k:k + 4]; hh = max(x["h"] for x in w); ll = min(x["l"] for x in w)
        if ll > 0 and (hh - ll) / ll <= 0.12:
            e = w[-1]["end_t"][11:19]; ends.append(B.tsec(e))
    return ends

def regime_flags(bars, gaps, vw, gain_min):
    """per-bar dict of regime sub-flags + in_regime bool."""
    o = bars[0]["o"]; bends = base_windows(bars); resum = [E.secs(bars[post]) for pre, post, g in gaps]
    out = []; hi = 0.0
    for i, b in enumerate(bars):
        s = E.secs(b); hi = max(hi, b["h"])
        gain = b["c"] / o - 1 if o > 0 else 0
        f_gain = gain >= gain_min
        f_vwap = b["c"] > vw[i]
        # a base whose last 3-min bar completed inside the last 30 min (and completed before now)
        f_nobase = not any(s - 1800 <= e <= s for e in bends)
        f_halt = any(s - 3600 <= r <= s for r in resum)
        out.append(dict(gain=gain, f_gain=f_gain, f_vwap=f_vwap, f_nobase=f_nobase, f_halt=f_halt,
                        inreg=f_gain and f_vwap and f_nobase and f_halt, hi=hi))
    return out

def find_entries(bars, gaps, vw, gain_min, post11=False):
    """rocket-sleeve triggers with cooldown 20 min / cap 2 per name-day (cap applied by caller after sim)."""
    R = regime_flags(bars, gaps, vw, gain_min); sigs = []; hi = 0.0; hi_i = 0; plow = None; plow_i = None
    for i, b in enumerate(bars):
        if b["h"] >= hi: hi = b["h"]; hi_i = i; plow = None; plow_i = None; continue
        if plow is None or b["l"] < plow: plow = b["l"]; plow_i = i
        if i == 0: continue
        pb = bars[i - 1]
        if not R[i]["inreg"]: continue
        if post11 and E.hhmm_b(b) < POST11: continue
        if plow_i == i: continue                          # this bar IS the new low: no higher low yet
        if not (0.70 * hi <= plow <= 0.90 * hi): continue  # mid-range pullback only
        if b["l"] > pb["l"] and b["c"] > pb["h"]:
            sigs.append(dict(i=i, t=E.hhmm_b(b), entry=b["c"], stop=plow, sess_hi=hi, hi_i=hi_i,
                             from_hi=b["c"] / hi - 1, gain=R[i]["gain"], plow_i=plow_i))
    return sigs, R

# ---------------- exit engine ----------------
def sim_sleeve(bars, gaps, entry_i, sig_px, stop, exit_v, halt_mode, log=None):
    """returns dict(pnl, exit, xi, gapthru(bool), min_fill_vs_stop, halts_in_trade)."""
    entry_px = sig_px * (1 + SLIP); sh = POS / entry_px; rem = sh; pnl = 0.0
    run_hi = entry_px; scaled = False; halts = 0; gapthru = False
    sess_hi_at_entry = max(b["h"] for b in bars[:entry_i + 1])
    struct_lvls = []; struct_sold = 0; dip_seen = True; struct_next = sess_hi_at_entry
    prev_s = E.secs(bars[entry_i])
    def L(m):
        if log is not None: log.append(m)
    def close_all(px, tag, i):
        nonlocal pnl, rem
        pnl += rem * (px - entry_px); rem = 0.0
        return dict(pnl=pnl, exit=tag, xi=i, gapthru=gapthru, halts=halts)
    for i in range(entry_i + 1, len(bars)):
        b = bars[i]; hh = E.hhmm_b(b); s = E.secs(b); is_resume = (s - prev_s) >= 240; prev_s = s
        if hh >= FLAT_T:
            px = b["c"] * (1 - MKT); L(f"{hh} FLATTEN 15:45ET at {px:.4f} rem {rem/sh:.2f}"); return close_all(px, "eod1545", i)
        if is_resume:
            halts += 1
            L(f"{hh} HALT-RESUME (gap {s - E.secs(bars[i-1])}s) open {b['o']:.4f} close {b['c']:.4f} stop {stop:.4f}")
            if halt_mode == "exit":
                if b["o"] < stop:
                    gapthru = True; px = b["o"] * (1 - MKT)
                    L(f"{hh} GAP-THROUGH exit at open {px:.4f} (stop {stop:.4f}, {100*(px/stop-1):+.1f}% vs stop)")
                    return close_all(px, f"gapthru@{hh}", i)
                # else fall through to normal bar processing (intrabar stop applies)
            else:  # hold-through
                if b["c"] < stop:
                    gapthru = b["o"] < stop; px = b["c"] * (1 - MKT)
                    L(f"{hh} HOLD-THROUGH exit: resumption CLOSE {b['c']:.4f} < stop {stop:.4f} fill {px:.4f}")
                    return close_all(px, f"resumeclose@{hh}", i)
                # resumption bar closed >= stop: ignore intrabar low; ratchet (STRUCT)
                if exit_v == "STRUCT" and b["l"] > stop:
                    stop = b["l"]; L(f"{hh} RATCHET stop -> resumption low {stop:.4f}")
                run_hi = max(run_hi, b["h"]); continue
            if exit_v == "STRUCT" and b["l"] > stop:
                stop = b["l"]; L(f"{hh} RATCHET stop -> resumption low {stop:.4f}")
        if b["l"] <= stop:
            px = stop * (1 - MKT); L(f"{hh} STOP {stop:.4f} fill {px:.4f} (low {b['l']:.4f})")
            return close_all(px, f"stop@{hh}", i)
        if exit_v == "E3":
            target = entry_px * 1.10
            if not scaled and b["h"] >= target:
                pnl += 0.5 * sh * (target - entry_px); rem -= 0.5 * sh; scaled = True
                L(f"{hh} BANK 50% at +10% ({target:.4f})"); continue
            run_hi = max(run_hi, b["h"])
            if scaled and b["c"] < run_hi * 0.90:
                px = b["c"] * (1 - MKT); L(f"{hh} TRAIL off10 close {b['c']:.4f} fill {px:.4f} (hi {run_hi:.4f})")
                return close_all(px, f"trail@{hh}", i)
        elif exit_v in ("E4", "E4W"):
            run_hi = max(run_hi, b["h"]); k = 0.90 if exit_v == "E4" else 0.80
            if b["c"] < run_hi * k:
                px = b["c"] * (1 - MKT); L(f"{hh} TRAIL off{int(round((1-k)*100))} close {b['c']:.4f} fill {px:.4f} (hi {run_hi:.4f})")
                return close_all(px, f"trail@{hh}", i)
        elif exit_v == "STRUCT":
            # sell 1/3 into structure: level 1 = session high at entry; level 2 = next new high after a >=10% dip
            if struct_sold < 2 and struct_next is not None and b["h"] >= struct_next and struct_next > entry_px:
                px = struct_next; pnl += (sh / 3) * (px - entry_px); rem -= sh / 3; struct_sold += 1
                L(f"{hh} STRUCT sell 1/3 at {px:.4f} (level {struct_sold})")
                run_hi = max(run_hi, b["h"]); struct_next = None; continue
            run_hi = max(run_hi, b["h"])
            if struct_sold == 1 and struct_next is None and b["c"] < run_hi * 0.90:
                struct_next = run_hi   # after a >=10% dip, the next new session high = level 2
    b = bars[-1]; px = b["c"] * (1 - MKT); L(f"{E.hhmm_b(b)} EOD exit at {px:.4f}")
    return close_all(px, "eod", len(bars) - 1)

# ---------------- run ----------------
def run_variant(SIGS, exit_v, halt_mode):
    trades = []
    for key, sigs in SIGS.items():
        bars, emas, gaps = E.DAYS[key]; last_t = None; n = 0; busy_until = -1
        for s in sigs:
            if s["t"] >= CUTOFF_T: continue
            if s["i"] <= busy_until: continue                        # one position per name at a time
            if last_t is not None and B.tsec(s["t"]) - last_t < 1200: continue
            if n >= 2: break
            r = sim_sleeve(bars, gaps, s["i"], s["entry"], s["stop"], exit_v, halt_mode)
            trades.append(dict(sym=key[0], date=key[1], **s, **r, big=key in TOPKEY,
                               risk=POS * (1 - s["stop"] / (s["entry"] * (1 + SLIP)))))
            last_t = B.tsec(s["t"]); n += 1; busy_until = r["xi"]
    return sorted(trades, key=lambda x: (x["date"], x["t"], x["sym"]))

def scorecard(tr, dates):
    d = {dt: 0.0 for dt in dates}
    for x in tr: d[x["date"]] += x["pnl"]
    tot = sum(x["pnl"] for x in tr); mid = dates[31]
    a = sum(d[k] for k in dates if k < mid); bb = sum(d[k] for k in dates if k >= mid)
    hr = sum(1 for x in tr if x["pnl"] >= 250); worst = min((x["pnl"] for x in tr), default=0.0)
    eq = 0.0; pk = 0.0; mdd = 0.0
    for x in tr:
        eq += x["pnl"]; pk = max(pk, eq); mdd = max(mdd, pk - eq)
    prem = []
    for k in range(0, len(dates), 21):
        w = set(dates[k:k + 21]); prem.append(sum(x["pnl"] for x in tr if x["date"] in w and x["pnl"] < 0))
    med_day = statistics.median([d[k] for k in dates]) if dates else 0
    tdays = sorted({x["date"] for x in tr}); green = sum(1 for k in tdays if d[k] > 0)
    wins = sum(1 for x in tr if x["pnl"] > 0)
    return dict(n=len(tr), wins=wins, tot=tot, a=a, b=bb, hr=hr, worst=worst, mdd=mdd, prem=prem, med_day=med_day,
                green=green, tdays=len(tdays), gapthru=sum(1 for x in tr if x["gapthru"]),
                big_n=sum(1 for x in tr if x["big"]), big_pnl=sum(x["pnl"] for x in tr if x["big"]),
                nb_n=sum(1 for x in tr if not x["big"]), nb_pnl=sum(x["pnl"] for x in tr if not x["big"]),
                mean_risk=statistics.mean([x["risk"] for x in tr]) if tr else 0,
                pass_=(a > 0 and bb > 0, hr >= 5, worst > -150, mdd < 1000))

def main():
    E.DAYS.clear(); nf, nd, dates = quiet(S.load_all)
    P("# ROCKET SLEEVE KILL-TEST — 2026-08-16 (H-VERT + H-HALT as one regime lane)")
    P(f"universe: {nf} files, {nd} RTH day-files, {len(dates)} dates {dates[0]}..{dates[-1]}; RTH bars only; chain FP->S->G->F->C->B->E "
      f"(data/gaps/VWAP/3-min agg reused unchanged); LIVE parity: +1% chase, 0.5% mkt exit, 15:30 no-entry, 15:45 flatten, $500 clip")
    P("regime: day-gain from RTH open >= G, close > session VWAP, no 4x3-min base (<=12% range) completing in last 30 min, >=1 halt "
      "resumption (>=4-min zero-print gap) in last 60 min. entry: pullback low 10-30% under session high, first bar HL + close > prior high; "
      "stop = pullback low; cooldown 20 min; cap 2/name-day; one open position per name.")
    VW = {}; CENSUS = {}
    for key, (bars, emas, gaps) in E.DAYS.items(): VW[key] = S.vwap_series(bars)
    # census
    P("\n## 1. REGIME CENSUS")
    P("| gain bar | window | name-days ever in-regime | in-regime bar-minutes (sum) | name-days w/ >=1 trigger | raw triggers | of which big-ride (top-60) name-days |")
    P("|---|---|---|---|---|---|---|")
    ALLSIGS = {}
    for gmin in (1.0, 0.6):
        for post11 in (False, True):
            SIGS = {}; nreg = 0; mins = 0; nsig = 0; nbigsig = 0
            for key, (bars, emas, gaps) in E.DAYS.items():
                sigs, R = find_entries(bars, gaps, VW[key], gmin, post11)
                inb = [i for i, r in enumerate(R) if r["inreg"] and (not post11 or E.hhmm_b(bars[i]) >= POST11)]
                if inb: nreg += 1; mins += len(inb) / 6.0
                if sigs:
                    SIGS[key] = sigs; nsig += len(sigs); nbigsig += int(key in TOPKEY)
            ALLSIGS[(gmin, post11)] = SIGS
            P(f"| >= +{int(gmin*100)}% | {'post-11:00' if post11 else 'all-day'} | {nreg} | {mins:.0f} | {len(SIGS)} | {nsig} | {nbigsig} |")
    # single-flag census (all-day, 100%)
    cnt = dict(f_gain=0, f_vwap=0, f_nobase=0, f_halt=0, gain_vwap=0, gain_vwap_halt=0)
    for key, (bars, emas, gaps) in E.DAYS.items():
        R = regime_flags(bars, gaps, VW[key], 1.0)
        if any(r["f_gain"] for r in R): cnt["f_gain"] += 1
        if any(r["f_halt"] for r in R): cnt["f_halt"] += 1
        if any(r["f_gain"] and r["f_vwap"] for r in R): cnt["gain_vwap"] += 1
        if any(r["f_gain"] and r["f_vwap"] and r["f_halt"] for r in R): cnt["gain_vwap_halt"] += 1
    P(f"flag funnel (all-day, +100%): name-days with day-gain>=+100% at some bar: {cnt['f_gain']}; with a halt: {cnt['f_halt']}; "
      f"gain&VWAP: {cnt['gain_vwap']}; gain&VWAP&halt-in-60: {cnt['gain_vwap_halt']}")

    # variant tables
    P("\n## 2. VARIANT TABLES (entry variant x exit variant), all trades sequential (no slot cap), $500 clip")
    HDR = ("| entry variant | exit | halt | N | wins | total $ | first-31 / last-31 dates | home runs >=+$250 | worst trade | max DD | "
           "premium per 21-day window (sum of losers) | median day | trade-days green | gap-through fills | big-ride tr (N/$) | non-big tr (N/$) | mean $risk |")
    P(HDR); P("|" + "---|" * 17)
    RES = {}
    for (gmin, post11), SIGS in ALLSIGS.items():
        for exit_v in ("E3", "E4", "E4W", "STRUCT"):
            for hm in ("exit", "hold"):
                tr = run_variant(SIGS, exit_v, hm); sc = scorecard(tr, dates)
                RES[(gmin, post11, exit_v, hm)] = (tr, sc)
                if not tr: P(f"| +{int(gmin*100)}% {'post11' if post11 else 'all'} | {exit_v} | {hm} | 0 |" + " - |" * 13); continue
                P(f"| +{int(gmin*100)}% {'post11' if post11 else 'all'} | {exit_v} | {hm} | {sc['n']} | {sc['wins']} ({100*sc['wins']/sc['n']:.0f}%) | "
                  f"${sc['tot']:+.0f} | ${sc['a']:+.0f} / ${sc['b']:+.0f} | {sc['hr']} | ${sc['worst']:+.0f} | ${sc['mdd']:.0f} | "
                  f"{' / '.join(f'${p:+.0f}' for p in sc['prem'])} | ${sc['med_day']:+.0f} | {sc['green']}/{sc['tdays']} | {sc['gapthru']} | "
                  f"{sc['big_n']}/${sc['big_pnl']:+.0f} | {sc['nb_n']}/${sc['nb_pnl']:+.0f} | ${sc['mean_risk']:.0f} |")
    # best variant = most convexity-bar items passed, tie -> total $
    def rank(k):
        sc = RES[k][1]; return (sum(sc["pass_"]), sc["tot"])
    best = max(RES, key=rank); trb, scb = RES[best]
    P(f"\n## 3. CONVEXITY BAR — best variant: entry +{int(best[0]*100)}% {'post-11' if best[1] else 'all-day'}, exit {best[2]}, halt-{best[3]}")
    P("| # | criterion | value | pass |"); P("|---|---|---|---|")
    P(f"| 1 | total P&L positive in BOTH halves (first-31 / last-31 dates) | ${scb['a']:+.0f} / ${scb['b']:+.0f} | {'PASS' if scb['pass_'][0] else 'FAIL'} |")
    P(f"| 2 | >= 5 trades >= +$250 | {scb['hr']} | {'PASS' if scb['pass_'][1] else 'FAIL'} |")
    P(f"| 3 | worst single trade > -$150 | ${scb['worst']:+.2f} | {'PASS' if scb['pass_'][2] else 'FAIL'} |")
    P(f"| 4 | max drawdown of lane equity < $1,000 | ${scb['mdd']:.0f} | {'PASS' if scb['pass_'][3] else 'FAIL'} |")
    P(f"| 5 | PREMIUM: sum of losing trades per 21-day window (no pass/fail) | {' / '.join(f'${p:+.0f}' for p in scb['prem'])} | (priced by Marcos) |")
    P(f"| info | median day (not a criterion) | ${scb['med_day']:+.2f} | - |")
    P(f"| info | N {scb['n']}, wins {scb['wins']}, total ${scb['tot']:+.0f}, mean ${scb['tot']/max(1,scb['n']):+.0f}/trade |  |  |")
    P(f"passed {sum(scb['pass_'])}/4 graded items")
    P("\n### best-variant trade list (all)")
    P("| date | sym | t(UTC) | entry | stop | risk$ | day-gain@entry | %from hi | exit | pnl | halts in trade | gap-thru | big-ride? |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in trb:
        P(f"| {x['date']} | {x['sym']} | {x['t']} | {x['entry']:.4f} | {x['stop']:.4f} | {x['risk']:.0f} | {100*x['gain']:+.0f}% | {100*x['from_hi']:+.0f}% | "
          f"{x['exit']} | ${x['pnl']:+.2f} | {x['halts']} | {'Y' if x['gapthru'] else ''} | {'Y' if x['big'] else ''} |")
    # base-rate honesty across all variants for best entry set
    P("\n### base-rate honesty (best variant): entries on name-days that are NOT top-60 big rides")
    nb = [x for x in trb if not x["big"]]; bg = [x for x in trb if x["big"]]
    P(f"non-big: N={len(nb)} total ${sum(x['pnl'] for x in nb):+.0f} mean ${sum(x['pnl'] for x in nb)/max(1,len(nb)):+.0f} wins {sum(1 for x in nb if x['pnl']>0)}; "
      f"big-ride name-days: N={len(bg)} total ${sum(x['pnl'] for x in bg):+.0f} mean ${sum(x['pnl'] for x in bg)/max(1,len(bg)):+.0f} wins {sum(1 for x in bg if x['pnl']>0)}")
    P("across ALL variants (non-big N / $  ||  big N / $):")
    for k, (tr, sc) in RES.items():
        P(f"- +{int(k[0]*100)}% {'post11' if k[1] else 'all'} {k[2]} {k[3]}: {sc['nb_n']}/${sc['nb_pnl']:+.0f} || {sc['big_n']}/${sc['big_pnl']:+.0f}")

    # gauntlet
    P("\n## 4. HOSTILE-HALT GAUNTLET — 10 name-days with the most halt gaps (best variant, plus exit-vs-hold twin)")
    worst_days = sorted(E.DAYS.items(), key=lambda kv: -len(kv[1][2]))[:10]
    P("| name-day | halts | lane trades | lane P&L (best) | worst trade | its exit | gap-through mechanics | twin (other halt mode) P&L | whole-date lane P&L |")
    P("|---|---|---|---|---|---|---|---|---|")
    other = "hold" if best[3] == "exit" else "exit"
    tro = RES[(best[0], best[1], best[2], other)][0]
    for key, (bars, emas, gaps) in worst_days:
        tt = [x for x in trb if (x["sym"], x["date"]) == key]; tw = [x for x in tro if (x["sym"], x["date"]) == key]
        dayp = sum(x["pnl"] for x in trb if x["date"] == key[1])
        if tt:
            w = min(tt, key=lambda x: x["pnl"]); log = []
            sim_sleeve(bars, gaps, w["i"], w["entry"], w["stop"], best[2], best[3], log)
            mech = " ; ".join(m for m in log if "HALT" in m or "GAP" in m or "HOLD" in m)[:300] or "no halt in trade"
            P(f"| {key[0]} {key[1]} | {len(gaps)} | {len(tt)} | ${sum(x['pnl'] for x in tt):+.0f} | ${w['pnl']:+.0f} | {w['exit']} | {mech} | ${sum(x['pnl'] for x in tw):+.0f} | ${dayp:+.0f} |")
        else:
            P(f"| {key[0]} {key[1]} | {len(gaps)} | 0 | $0 | - | - | no lane entry | ${sum(x['pnl'] for x in tw):+.0f} | ${dayp:+.0f} |")

    # hand traces
    P("\n## 5. HAND-TRACES (C3 specimens) — best variant; every trigger on the name-day (cap/cooldown noted)")
    for sym, date in (("INHD", "2026-06-08"), ("PAVS", "2026-06-09"), ("ZYBT", "2026-07-20")):
        key = (sym, date)
        if key not in E.DAYS: P(f"### {sym} {date}: NOT IN CACHE"); continue
        bars, emas, gaps = E.DAYS[key]; vw = VW[key]
        sigs, R = find_entries(bars, gaps, vw, best[0], best[1])
        inb = [i for i, r in enumerate(R) if r["inreg"]]
        P(f"### {sym} {date}: RTH open {bars[0]['o']:.4f}, session high {max(b['h'] for b in bars):.4f}, close {bars[-1]['c']:.4f}, "
          f"halt gaps {len(gaps)} at {[E.hhmm_b(bars[post]) for pre,post,g in gaps][:12]}")
        if inb: P(f"in-regime bars: {len(inb)} ({len(inb)/6:.0f} min), first {E.hhmm_b(bars[inb[0]])} last {E.hhmm_b(bars[inb[-1]])} (UTC)")
        else:
            # why not: flag census at 13:00-16:00
            fg = sum(1 for r in R if r["f_gain"]); fv = sum(1 for r in R if r["f_gain"] and r["f_vwap"]); fb = sum(1 for r in R if r["f_gain"] and r["f_vwap"] and r["f_nobase"])
            fh = sum(1 for r in R if r["f_gain"] and r["f_vwap"] and r["f_halt"])
            P(f"NEVER in-regime. bars with gain>=bar: {fg}; +VWAP: {fv}; +no-base: {fb}; gain+VWAP+halt: {fh}")
        tt = [x for x in trb if (x["sym"], x["date"]) == key]
        P(f"raw triggers: {len(sigs)} at {[s['t'] for s in sigs][:10]}; trades taken: {len(tt)}")
        for x in tt:
            log = []; sim_sleeve(bars, gaps, x["i"], x["entry"], x["stop"], best[2], best[3], log)
            P(f"- TRADE {x['t']} entry {x['entry']:.4f} (+1% fill {x['entry']*1.01:.4f}) stop {x['stop']:.4f} risk ${x['risk']:.0f} "
              f"day-gain {100*x['gain']:+.0f}% {100*x['from_hi']:+.0f}% from hi {x['sess_hi']:.4f} -> exit {x['exit']} pnl ${x['pnl']:+.2f}")
            for m in log[:25]: P(f"    {m}")
        # C3 ride start context
        rs = next((r for r in BIG["top"] if r["sym"] == sym and r["date"] == date), None)
        if rs:
            i0 = next((i for i, b in enumerate(bars) if E.hhmm_b(b) >= rs["t0"]), None)
            if i0 is not None:
                r = R[i0]
                P(f"  C3 ride start {rs['t0']} @ {rs['start_px']}: gain {100*r['gain']:+.0f}% vwap-above {r['f_vwap']} no-base {r['f_nobase']} halt-60 {r['f_halt']} -> in-regime {r['inreg']}")

    # verdict
    P("\n## 6. VERDICT")
    npass = sum(scb["pass_"])
    if scb["n"] < 15: verdict = "NEEDS-DATA"
    elif npass == 4: verdict = "SHADOW-CANDIDATE"
    elif npass >= 3 and scb["tot"] > 0: verdict = "SHADOW-CANDIDATE (conditional: see failed item)"
    else: verdict = "REFUTED (as specified)"
    P(f"best variant passes {npass}/4 graded convexity items on N={scb['n']} trades; total ${scb['tot']:+.0f}; VERDICT: {verdict}")
    json.dump({"best": list(best), "score": {k: v for k, v in scb.items()}, "trades": trb},
              open(HERE + "/rocket_sleeve_killtest_20260816_trades.json", "w"), default=str)
    open(HERE + "/rocket_sleeve_killtest_20260816_out.md", "w").write("\n".join(OUT))
    return verdict

if __name__ == "__main__":
    main()
