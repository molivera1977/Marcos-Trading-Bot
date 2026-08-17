#!/usr/bin/env python3
"""IGNITION GUIDANCE KILL-TEST — 8/17/26 (Marcos: "ignition needs to have guidance",
after FIEE $5.70 vs VWAP $6.05 and DFSC $2.90 vs VWAP $3.21 fired below VWAP on morning fades).

Universe replica of the ignition-10s detector's SPIRIT on the bars10s cache (62 dates),
graded with the OOS wall discipline (MINE 05-18..07-21 / HOLD-OUT 07-22..08-14).

Detector (mirrors ignition_10s_step + IGNITION_CONVERT_MULT, marcos_trading_bot.py:6417/6316):
  RTH 10s bars, first 90 min; base = prior 24 x 10s bars (4 min); fire when
  v >= 4.5 x base avg (CONVERT threshold) AND v >= 5000/6 AND green AND close in top 50%
  of range AND c >= max(base closes) AND -5% <= (c-open)/open <= +15%.
  entry = fire close, stop = base_lo * (1 - 0.003)  [ZONE_STOP_BUFFER parity].
Exits: E3 live-parity via S.run (F.sim_var E3, halt_rule=True, dedup same-name<=5min).

GUIDANCE GATES (pre-registered):
  G1 price >= session VWAP at fire
  G2 structural seq suffix ends in T B (LIVE _seq_events port, marcos_trading_bot.py:9640 lockstep)
  G3 fire within 3% of session high (vs >5% below = bounce/fade ignition)
  G4 VETO: raw seq string ends in D or F (rolling over / flushing at fire)
  G5 Kev-level respect: ERA ROWS ONLY (separate era script; no maps in the universe cache)

Null: 5000 label shuffles on the HOLD-OUT $/tr split (when both sides N>=15).
D-guard fill model: seq_conditional_size_20260817.py machinery (full/half/skip at $500).
Analysis only. No bot edits."""
import importlib.util, os, math, json, random
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("S", HERE + "/sunday_afternoon_studies_20260816.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
E = S.E; F = S.F

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); OUT.append(s)

MINE_END = "2026-07-21"

# ---------- live _seq_events port (lockstep with marcos_trading_bot.py:9640) ----------
SEQ_MAX_EVENTS = 14; SEQ_LOOKBACK_S = 600; SEQ_FLUSH_PCT = 2.0
SEQ_TEST_BAND = 0.003; SEQ_Q_PCT = 0.01; SEQ_Q_BARS = 6; SEQ_HALT_GAP = 60

def seq_events(d10, vwap=0.0):
    if not d10 or len(d10) < 6: return ""
    ks = sorted(d10)
    k0 = ks[-1] - SEQ_LOOKBACK_S
    ks = [k for k in ks if k >= k0]
    if len(ks) < 6: return ""
    v = float(vwap or 0)
    evs = []
    sess_hi = None; last_break = None; prev_lo = None; prev_hi = None
    prev_k = None; hold_run = 0; closes = []
    for k in ks:
        b = d10[k]
        h = b["h"]; l = b["l"]; c = b["c"]
        if h <= 0 or l <= 0 or c <= 0: continue
        if prev_k is not None and (k - prev_k) >= SEQ_HALT_GAP:
            evs.append("L")
        ev = None
        new_break = sess_hi is not None and h > sess_hi
        flush = bool(closes) and max(closes[-3:]) > 0 and (c - max(closes[-3:])) / max(closes[-3:]) * 100 <= -SEQ_FLUSH_PCT
        wick = v > 0 and l <= v <= c
        test = sess_hi is not None and not new_break and h >= sess_hi * (1 - SEQ_TEST_BAND)
        retest = last_break is not None and abs(l - last_break) / last_break <= SEQ_TEST_BAND and c > last_break
        if last_break is not None and l > last_break: hold_run += 1
        else: hold_run = 0
        hold = hold_run == 3
        push = prev_hi is not None and h > prev_hi and not new_break
        lower = prev_lo is not None and l < prev_lo and (prev_hi is None or h < prev_hi)
        if new_break:   ev = "B"
        elif flush:     ev = "F"
        elif wick:      ev = "W"
        elif test:      ev = "T"
        elif retest:    ev = "R"
        elif hold:      ev = "H"
        elif push:      ev = "P"
        elif lower:     ev = "D"
        if new_break:
            last_break = sess_hi; hold_run = 0
        if sess_hi is None or h > sess_hi: sess_hi = h
        if ev: evs.append(ev)
        closes.append(c); prev_lo = l; prev_hi = h; prev_k = k
    tail = ks[-SEQ_Q_BARS:]
    if len(tail) >= SEQ_Q_BARS:
        his = [d10[k]["h"] for k in tail]; los = [d10[k]["l"] for k in tail if d10[k]["l"] > 0]
        if los and his:
            lo = min(los); hi = max(his)
            if lo > 0 and (hi - lo) / lo <= SEQ_Q_PCT:
                evs.append("Q")
    return " ".join(evs[-SEQ_MAX_EVENTS:])

def structural(evstr):
    s = [e for e in evstr.split() if e not in ("F", "D")]
    return [e for i, e in enumerate(s) if i == 0 or s[i - 1] != e]

def epoch_of(b):
    return int(datetime.strptime(b["t"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())

# ---------- ignition detector on the universe ----------
BASE_BARS = 24              # 4 min of 10s bars (IGNITION_BASE_LOOKBACK 4 x 6)
CONVERT_MULT = 4.5          # IGNITION_CONVERT_MULT — the live CONVERT threshold
MIN_ABS_VOL = 5000 / 6.0    # _IG10_MIN_ABS_VOL
STRONG = 0.5; MIN_EXT = -0.05; MAX_EXT = 0.15; STOPBUF = 0.003
WINDOW_END = "15:00:00"     # 13:30Z + 90 min

def gen_fires():
    fires = []
    for (sym, date), (bars, emas, gaps) in sorted(E.DAYS.items()):
        openp = bars[0]["o"] or bars[0]["c"]
        if openp <= 0: continue
        vw = S.vwap_series(bars)
        epochs = [epoch_of(b) for b in bars]
        sess_hi = 0.0
        for i, b in enumerate(bars):
            hh = E.hhmm_b(b)
            prev_hi = sess_hi
            sess_hi = max(sess_hi, b["h"])
            if i < BASE_BARS or hh > WINDOW_END: continue
            base = bars[i - BASE_BARS:i]
            base_hi_c = max(x["c"] for x in base)
            lows = [x["l"] for x in base if x["l"] > 0]
            if not lows: continue
            base_lo = min(lows)
            base_vol = (sum(x["v"] for x in base) / len(base)) or 1
            v, o, c, h, l = b["v"], b["o"], b["c"], b["h"], b["l"]
            if c <= 0: continue
            rng = (h - l) or 1e-9
            strong = (c - l) / rng
            ext = (c - openp) / openp
            if (v >= CONVERT_MULT * base_vol and v >= MIN_ABS_VOL and c > o
                    and strong >= STRONG and c >= base_hi_c and MIN_EXT <= ext <= MAX_EXT):
                d10 = {epochs[j]: bars[j] for j in range(max(1, i - 61), i + 1)}
                ev = seq_events(d10, vw[i])
                st = structural(ev)
                raw_last = ev.split()[-1] if ev else ""
                hi_before = max(prev_hi, h)   # session high including the fire bar
                fires.append(S.mk(sym, date, "ignition", i, c, round(base_lo * (1 - STOPBUF), 4),
                                  vwap=vw[i], volx=round(v / base_vol, 1), ext=round(ext * 100, 1),
                                  ev=ev, st=st, raw_last=raw_last,
                                  g1=c >= vw[i],
                                  g2=len(st) >= 2 and tuple(st[-2:]) == ("T", "B"),
                                  g3near=c >= hi_before * 0.97, g3far=c < hi_before * 0.95,
                                  g4veto=raw_last in ("D", "F"),
                                  dv=c * v))
    fires.sort(key=lambda s: (s["date"], s["t"], s["sym"]))
    return fires

def one_r_before_stop(sym, date, i, entry, stop):
    bars = E.DAYS[(sym, date)][0]
    risk = entry - stop
    if risk <= 0: return False
    tgt = entry + risk
    for x in bars[i + 1:]:
        if x["l"] <= stop: return False
        if x["h"] >= tgt: return True
    return False

# ---------- cohort stats ----------
def cstats(rows):
    n = len(rows)
    if not n: return dict(N=0, win=0, tot=0.0, dtr=0.0)
    return dict(N=n, win=100 * sum(1 for r in rows if r["win"]) / n,
                tot=sum(r["pnl"] for r in rows), dtr=sum(r["pnl"] for r in rows) / n)

def crow(nm, s):
    return f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['tot']:+.2f} | ${s['dtr']:+.2f} |"

def null_p(rows, passers, iters=5000, seed=17):
    """p = fraction of shuffles where a random subset of size n_pass has $/tr >= observed."""
    npass = len(passers)
    if npass < 15 or len(rows) - npass < 15: return None
    obs = sum(r["pnl"] for r in passers) / npass
    pnls = [r["pnl"] for r in rows]
    rng = random.Random(seed); ge = 0
    for _ in range(iters):
        samp = rng.sample(pnls, npass)
        if sum(samp) / npass >= obs: ge += 1
    return ge / iters

GHDR = "| cohort | N | win | total | $/tr |"
GSEP = "|---|---|---|---|---|"

def grade_gate(name, rows_m, rows_h, passfn, veto=False):
    """passfn(r) -> True = KEEP (for a veto gate, passfn returns True when NOT vetoed)."""
    P(f"### {name}")
    res = {}
    for tag, rows in (("MINE", rows_m), ("HOLD-OUT", rows_h)):
        keep = [r for r in rows if passfn(r)]; drop = [r for r in rows if not passfn(r)]
        sk, sd, sa = cstats(keep), cstats(drop), cstats(rows)
        P(f"**{tag}**"); P(GHDR); P(GSEP)
        P(crow("ALL", sa)); P(crow("KEEP", sk)); P(crow("DROP", sd))
        p = null_p(rows, keep) if tag == "HOLD-OUT" else None
        if tag == "HOLD-OUT":
            P(f"null p (5000 shuffles, KEEP $/tr vs random same-N): {p if p is not None else 'UNDERPOWERED (side N<15)'}")
        res[tag] = dict(keep=sk, drop=sd, all=sa, p=p)
        P("")
    return res

# ---------- D-guard fill model (seq_conditional_size_20260817 machinery) ----------
def slip_for(pos): return 0.010 + 0.005 * (pos - 500.0) / 500.0
_cache = {}
def resim(r, pos):
    key = (r["sym"], r["date"], r["i"], round(pos, 2))
    if key in _cache: return _cache[key]
    bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]
    old_pos, old_slip = E.POS, F.ENTRY_SLIP
    E.POS = pos; F.ENTRY_SLIP = slip_for(pos)
    try:
        pnl, exx, xi = F.sim_var(bars, emas, gaps, r["i"], r["entry"], r["stop"], "E3", r["det"], True)
    finally:
        E.POS = old_pos; F.ENTRY_SLIP = old_slip
    _cache[key] = pnl
    return pnl
def guarded_pnl(r, C=500.0):
    if r["dv"] >= 20 * C: return resim(r, C), "full"
    if r["dv"] >= 10 * C: return resim(r, C / 2), "half"
    return 0.0, "skip"
def guard_book(rows, C=500.0):
    tot = 0.0; tiers = {"full": 0, "half": 0, "skip": 0}
    for r in rows:
        pnl, tier = guarded_pnl(r, C); tot += pnl; tiers[tier] += 1
    return dict(total=tot, per_fire=tot / len(rows) if rows else 0.0, tiers=tiers)

def main():
    P("# IGNITION GUIDANCE — universe sim (8/17)")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    fires = gen_fires()
    P(f"raw ignition-replica fires (volx>=4.5 convert, pre-dedup): {len(fires)}")
    tr = S.run(fires)
    for x in tr:
        x["win"] = (x["pnl"] > 0) or one_r_before_stop(x["sym"], x["date"], x["i"], x["entry"], x["stop"])
    P(f"post-dedup graded fires: {len(tr)}")
    rows_m = [r for r in tr if r["date"] <= MINE_END]
    rows_h = [r for r in tr if r["date"] > MINE_END]
    P(f"MINE (<= {MINE_END}): {len(rows_m)} fires · HOLD-OUT: {len(rows_h)} fires\n")
    P(GHDR); GSEPP = GSEP; P(GSEPP)
    P(crow("MINE ALL", cstats(rows_m))); P(crow("HOLD-OUT ALL", cstats(rows_h))); P("")

    res = {}
    res["G1"] = grade_gate("G1 TAPE-SIDE: price >= session VWAP at fire", rows_m, rows_h, lambda r: r["g1"])
    res["G2"] = grade_gate("G2 SEQUENCE PRIORITY: structural suffix ends T B", rows_m, rows_h, lambda r: r["g2"])
    res["G3"] = grade_gate("G3 FRESH-HIGH: fire within 3% of session high", rows_m, rows_h, lambda r: r["g3near"])
    P("G3 aux — the FAR side (>5% below session high) on its own:")
    for tag, rows in (("MINE", rows_m), ("HOLD-OUT", rows_h)):
        far = [r for r in rows if r["g3far"]]
        P(f"  {tag} far-side: " + crow("FAR", cstats(far)))
    P("")
    res["G4"] = grade_gate("G4 SUFFIX VETO: raw seq ends D or F (KEEP = not vetoed)", rows_m, rows_h, lambda r: not r["g4veto"])

    # ---------- stacks ----------
    P("## STACKS (MINE-chosen, frozen on HOLD-OUT)")
    stacks = {
        "G1 only": lambda r: r["g1"],
        "G3 only": lambda r: r["g3near"],
        "G1+G3": lambda r: r["g1"] and r["g3near"],
        "G1+G4": lambda r: r["g1"] and not r["g4veto"],
        "G3+G4": lambda r: r["g3near"] and not r["g4veto"],
        "G1+G3+G4": lambda r: r["g1"] and r["g3near"] and not r["g4veto"],
        "G1+G2": lambda r: r["g1"] and r["g2"],
    }
    P("| stack | MINE N | MINE $/tr | HOLD N | HOLD $/tr | HOLD win | null p | winners forfeited (HOLD) |")
    P("|---|---|---|---|---|---|---|---|")
    stack_res = {}
    for nm, fn in stacks.items():
        km = [r for r in rows_m if fn(r)]; kh = [r for r in rows_h if fn(r)]
        sm, sh = cstats(km), cstats(kh)
        p = null_p(rows_h, kh)
        wins_all = [r for r in rows_h if r["pnl"] > 0]
        forf = sum(1 for r in wins_all if not fn(r))
        forf_d = sum(r["pnl"] for r in wins_all if not fn(r))
        P(f"| {nm} | {sm['N']} | ${sm['dtr']:+.2f} | {sh['N']} | ${sh['dtr']:+.2f} | {sh['win']:.0f}% | "
          f"{p if p is not None else 'n/a'} | {forf}/{len(wins_all)} (${forf_d:+.0f}) |")
        stack_res[nm] = dict(mine=sm, hold=sh, p=p, forfeit_n=forf, forfeit_d=forf_d)
    P("")

    # D-guard on the champion stack + ungated, hold-out
    P("## D-GUARD FILL MODEL (hold-out, $500 clip; full/half/skip)")
    for nm in ("UNGATED", "G1 only", "G1+G3", "G1+G4", "G1+G3+G4"):
        rows = rows_h if nm == "UNGATED" else [r for r in rows_h if stacks[nm](r)]
        g = guard_book(rows)
        P(f"  {nm}: N={len(rows)} guarded total ${g['total']:+.2f} (${g['per_fire']:+.2f}/fire) tiers {g['tiers']}")
    P("")

    json.dump({"n_fires": len(tr), "mine": len(rows_m), "hold": len(rows_h),
               "gates": {k: {t: {kk: v[t][kk] for kk in ("keep", "drop", "all", "p")} for t in v} for k, v in res.items()},
               "stacks": stack_res,
               "rows": [{k: r[k] for k in ("sym", "date", "t", "entry", "stop", "pnl", "win",
                                            "vwap", "volx", "ext", "ev", "g1", "g2", "g3near", "g3far", "g4veto", "dv")}
                        for r in tr]},
              open(HERE + "/ignition_guidance_20260817_out.json", "w"), indent=1, default=str)
    open(HERE + "/ignition_guidance_20260817_run.txt", "w").write("\n".join(OUT))

if __name__ == "__main__":
    main()
