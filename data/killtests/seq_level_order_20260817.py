#!/usr/bin/env python3
"""LEVEL-INTERACTION SEQUENCE study — 8/17/26. ANALYSIS ONLY, no bot edits.

The chart-gate doctrine treats levels as static gates; the sequencing doctrine says the
ORDER of level interactions matters.  Levels available offline for EVERY universe name-day
(no Kev maps needed):
  V = session VWAP (computed on RTH 10s bars)
  W = whole dollars      F = half dollars (x.50)
  M = premarket high (day high before 09:30 ET — NOTE: in this cache the tape starts
      08:00Z/04:00 ET with no prior session, so "premarket high" and "day high before
      09:30" are the SAME level; collapsed into one class M, disclosed)
  O = 09:30 opening price (first RTH bar open)

Level-event alphabet on 10s RTH bars, per level class:
  t  first-touch   (first bar whose range contains the level; per level value)
  r  reclaim       (close through from below after >=5 min (30 bars) closing below)
  j  rejection     (touch the level from below, close away >=0.5% under it)
  h  hold          (3 consecutive closes at/above the level after a reclaim)

Fires = break-attack + grinder lanes from sequence_mining_pilot_20260817.py (engine chain
S->G->F->C->B->E unchanged, E3 live-parity $500 exits).  OOS protocol identical to
seq_gate_oos_wall_20260817.py: chronological split, MINE = earliest 44 dates, HOLD-OUT =
latest 18; measure on MINE (material = both sides N>=15), FREEZE the direction, verify on
HOLD-OUT, permutation null (5000x relabelings of the level-token feature across hold-out
fires within lane) for survivors.

PRE-REGISTERED HYPOTHESES:
  H1 LADDER-UP     : fires preceded (within 10 min) by VWAP-reclaim THEN whole-dollar-hold
                     (that order) outperform fires with the reverse order or missing rungs.
  H2 PMH-FIRST     : premarket high reclaimed BEFORE the fire vs after/never.
  H3 REJECTION-SCAR: whole-dollar rejection within 10 min BEFORE the fire hurts it.
  H4 CLEAN-LADDER  : count of distinct level classes reclaimed-and-held in the prior
                     30 min (0/1/2/3+) — monotone with $/tr?
VERDICT per hypothesis: ORDER-MATTERS / NO-SPLIT / UNDERPOWERED.
"""
import importlib.util, os, json, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

MIN_BELOW = 30      # 5 min of 10s bars closing below before a cross counts as reclaim
HOLD_BARS = 3
REJ_PCT = 0.005
W10 = 60            # 10-min lookback (bars)
W30 = 180           # 30-min lookback (bars)

# ---------------- level-event timeline per name-day ----------------
def bars_below_since(closes, k, L):
    """consecutive bars (ending at k-1) with close <= L; capped scan."""
    n = 0
    j = k - 1
    while j >= 0 and closes[j] <= L:
        n += 1; j -= 1
        if n >= MIN_BELOW: break
    return n

def dollar_levels(lo, hi, half):
    """whole-dollar (half=False) or half-dollar x.50 (half=True) levels in (lo, hi]."""
    out = []
    step = 1.0
    first = math.floor(lo) + (0.5 if half else 1.0)
    if half and first <= lo: first += 1.0
    L = first
    while L <= hi + 1e-9:
        if L > lo + 1e-9: out.append(round(L, 2))
        L += step
    return out

def timeline(sym, date):
    """Return list of (bar_idx, class, kind) tokens for the RTH day. Classes V,W,F,M,O."""
    bars = E.DAYS[(sym, date)][0]
    closes = [b["c"] for b in bars]
    vwap = S.vwap_series(bars)
    full = S.FULL.get((sym, date), bars)
    pre = [b for b in full if E.hhmm_b(b) < "13:30:00"]
    pmh = max((b["h"] for b in pre), default=None)
    op = bars[0]["o"]
    toks = []
    touched = set()           # (cls, levelval) first-touch bookkeeping
    pending_hold = []         # (cls, L, reclaim_idx)
    static = [("M", pmh), ("O", op)] if pmh else [("O", op)]

    for k in range(1, len(bars)):
        b = bars[k]; pc = closes[k - 1]; c = closes[k]
        # ---- static classes + VWAP (single level per class at bar k) ----
        for cls, L in static + [("V", vwap[k])]:
            if L is None or L <= 0: continue
            key = (cls, 0)
            if key not in touched and b["l"] <= L <= b["h"]:
                touched.add(key); toks.append((k, cls, "t"))
            if pc <= L < c:
                below = bars_below_since(closes if cls != "V" else closes, k, L) if cls != "V" else _below_dyn(closes, vwap, k)
                if below >= MIN_BELOW:
                    toks.append((k, cls, "r")); pending_hold.append((cls, L if cls != "V" else None, k))
            if b["h"] >= L and c <= L * (1 - REJ_PCT) and pc < L:
                toks.append((k, cls, "j"))
        # ---- dollar classes: any level crossed/touched this bar ----
        for cls, half in (("W", False), ("F", True)):
            # reclaim: levels in (pc, c]
            if c > pc:
                for L in dollar_levels(pc, c, half):
                    if bars_below_since(closes, k, L) >= MIN_BELOW:
                        toks.append((k, cls, "r")); pending_hold.append((cls, L, k))
            # first-touch: levels in bar range
            for L in dollar_levels(b["l"] - 1.0, b["h"], half):
                if b["l"] <= L <= b["h"] and (cls, L) not in touched:
                    touched.add((cls, L)); toks.append((k, cls, "t"))
            # rejection: level in (c, h] with close >=0.5% away below
            for L in dollar_levels(c, b["h"], half):
                if c <= L * (1 - REJ_PCT):
                    toks.append((k, cls, "j")); break
        # ---- resolve pending holds ----
        still = []
        for cls, L, rk in pending_hold:
            Lv = vwap[k] if cls == "V" else L
            if c >= Lv - 1e-9:
                if k - rk >= HOLD_BARS:
                    toks.append((k, cls, "h"))
                else:
                    still.append((cls, L, rk))
            # close back below -> hold dead, drop
        pending_hold = still
    return toks

def _below_dyn(closes, vwap, k):
    n = 0; j = k - 1
    while j >= 0 and closes[j] <= vwap[j]:
        n += 1; j -= 1
        if n >= MIN_BELOW: break
    return n

TL_CACHE = {}
def get_tl(sym, date):
    if (sym, date) not in TL_CACHE:
        TL_CACHE[(sym, date)] = timeline(sym, date)
    return TL_CACHE[(sym, date)]

# ---------------- per-fire features ----------------
def features(r):
    toks = get_tl(r["sym"], r["date"])
    i = r["i"]
    w10 = [(k, c, kd) for k, c, kd in toks if i - W10 < k <= i]
    w30 = [(k, c, kd) for k, c, kd in toks if i - W30 < k <= i]
    # H1: VWAP-reclaim then whole-dollar-hold, in order, within 10 min
    v_r = [k for k, c, kd in w10 if c == "V" and kd == "r"]
    w_h = [k for k, c, kd in w10 if c == "W" and kd == "h"]
    ladder = any(a < b for a in v_r for b in w_h)
    reverse_or_missing = not ladder
    # H2: PMH reclaimed before the fire, anywhere in the day
    pmh_first = any(c == "M" and kd == "r" and k <= i for k, c, kd in toks)
    # H3: whole-dollar rejection within 10 min before fire
    scar = any(c == "W" and kd == "j" for k, c, kd in w10)
    # H4: distinct classes reclaimed-AND-held in prior 30 min
    held = set()
    for k, c, kd in w30:
        if kd == "h":
            # require the matching reclaim also inside the window
            if any(kk < k and cc == c and kdd == "r" for kk, cc, kdd in w30):
                held.add(c)
    nlad = len(held)
    return {"ladder": ladder, "pmh_first": pmh_first, "scar": scar,
            "nlad": min(nlad, 3)}

# ---------------- split stats + permutation ----------------
def split_stats(rows, flag):
    a = [r for r in rows if r["feat"][flag]]
    b = [r for r in rows if not r["feat"][flag]]
    def s(x):
        n = len(x)
        return {"N": n, "dtr": sum(r["pnl"] for r in x) / n if n else 0.0,
                "win": 100 * sum(1 for r in x if r["win"]) / n if n else 0.0}
    return s(a), s(b)

def perm_p(rows, flag, direction, iters=5000, seed=17):
    """one-sided p for the frozen direction: direction=+1 means flag-true side better."""
    rnd = random.Random(seed)
    pnls = [r["pnl"] for r in rows]
    m = sum(1 for r in rows if r["feat"][flag])
    if m == 0 or m == len(rows): return None
    obs = (sum(r["pnl"] for r in rows if r["feat"][flag]) / m
           - sum(r["pnl"] for r in rows if not r["feat"][flag]) / (len(rows) - m)) * direction
    ge = 0
    idx = list(range(len(rows)))
    for _ in range(iters):
        pick = set(rnd.sample(idx, m))
        sa = sum(pnls[j] for j in pick) / m
        sb = (sum(pnls) - sa * m) / (len(rows) - m)
        if (sa - sb) * direction >= obs: ge += 1
    return ge / iters

def perm_p_spearman(rows, iters=5000, seed=17):
    """H4: permutation p for rank-corr between nlad bucket and pnl (frozen direction sign)."""
    rnd = random.Random(seed)
    xs = [r["feat"]["nlad"] for r in rows]
    ys = [r["pnl"] for r in rows]
    def corr(x, y):
        n = len(x)
        mx = sum(x) / n; my = sum(y) / n
        sx = math.sqrt(sum((a - mx) ** 2 for a in x)); sy = math.sqrt(sum((a - my) ** 2 for a in y))
        if sx == 0 or sy == 0: return 0.0
        return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
    obs = corr(xs, ys)
    ge = 0
    y2 = ys[:]
    for _ in range(iters):
        rnd.shuffle(y2)
        if abs(corr(xs, y2)) >= abs(obs): ge += 1
    return obs, ge / iters

def buckets(rows):
    out = {}
    for b in range(4):
        sub = [r for r in rows if r["feat"]["nlad"] == b]
        n = len(sub)
        out[b] = {"N": n, "dtr": sum(r["pnl"] for r in sub) / n if n else 0.0}
    return out

# ---------------- main ----------------
def main():
    P("# LEVEL-INTERACTION SEQUENCE STUDY — 8/17/26 (analysis only, no bot edits)")
    P("Fires + E3 exits from sequence_mining_pilot chain UNCHANGED; OOS split identical to")
    P("seq_gate_oos_wall (MINE = earliest 44 dates, HOLD-OUT = latest 18).")
    nf, nd, dates = S.load_all()
    P(f"Universe: {nf} files, {nd} name-days, {len(dates)} dates {dates[0]}..{dates[-1]}.")
    n_hold = 18
    mine_dates = set(dates[:-n_hold]); hold_dates = set(dates[-n_hold:])
    P(f"MINE {sorted(mine_dates)[0]}..{sorted(mine_dates)[-1]} ({len(mine_dates)}d) | "
      f"HOLD-OUT {sorted(hold_dates)[0]}..{sorted(hold_dates)[-1]} ({len(hold_dates)}d)")
    P("NOTE: cache tape starts 08:00Z (04:00 ET) with no prior session — 'premarket high'")
    P("and 'day high before 09:30' are the SAME level here; collapsed into class M.\n")

    lanes = {}
    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder")):
        rows = PILOT.grade(PILOT.gen_lane(key))
        for r in rows:
            r["feat"] = features(r)
        lanes[key] = {"nm": nm,
                      "mine": [r for r in rows if r["date"] in mine_dates],
                      "hold": [r for r in rows if r["date"] in hold_dates]}
        P(f"LANE {nm}: {len(rows)} fires ({len(lanes[key]['mine'])} MINE / {len(lanes[key]['hold'])} HOLD-OUT)")
    P("")

    results = {}
    HYPS = [("H1", "ladder", "LADDER-UP (VWAP-reclaim then $-hold, 10 min)", +1),
            ("H2", "pmh_first", "PMH-FIRST (PMH reclaimed before fire)", +1),
            ("H3", "scar", "REJECTION-SCAR ($-rejection 10 min pre-fire)", -1)]
    for hid, flag, desc, hyp_dir in HYPS:
        P(f"\n## {hid} {desc}")
        results[hid] = {}
        for key in ("break_attack", "grinder"):
            L = lanes[key]
            ma, mb = split_stats(L["mine"], flag)
            P(f"### {L['nm']}")
            P(f"MINE : with N={ma['N']} ${ma['dtr']:+.2f}/tr {ma['win']:.0f}%w  |  "
              f"without N={mb['N']} ${mb['dtr']:+.2f}/tr {mb['win']:.0f}%w  |  "
              f"diff ${ma['dtr']-mb['dtr']:+.2f}")
            if ma["N"] < 15 or mb["N"] < 15:
                P(f"**UNDERPOWERED on MINE** (need both sides N>=15).")
                results[hid][key] = {"verdict": "UNDERPOWERED", "mine": (ma, mb)}
                continue
            mine_dir = 1 if ma["dtr"] > mb["dtr"] else -1
            agrees = "agrees with" if mine_dir == hyp_dir else "OPPOSES"
            P(f"MINE direction {'with-side better' if mine_dir>0 else 'with-side WORSE'} — {agrees} the pre-registered hypothesis. FROZEN.")
            ha, hb = split_stats(L["hold"], flag)
            P(f"HOLD : with N={ha['N']} ${ha['dtr']:+.2f}/tr {ha['win']:.0f}%w  |  "
              f"without N={hb['N']} ${hb['dtr']:+.2f}/tr {hb['win']:.0f}%w  |  "
              f"diff ${ha['dtr']-hb['dtr']:+.2f}")
            if ha["N"] < 15 or hb["N"] < 15:
                P(f"**UNDERPOWERED on HOLD-OUT** (with={ha['N']}, without={hb['N']}).")
                results[hid][key] = {"verdict": "UNDERPOWERED", "mine": (ma, mb), "hold": (ha, hb)}
                continue
            hold_dir = 1 if ha["dtr"] > hb["dtr"] else -1
            survives = hold_dir == mine_dir and abs(ha["dtr"] - hb["dtr"]) > 5
            p = perm_p(L["hold"], flag, mine_dir) if survives else None
            if p is not None:
                P(f"NULL : permutation 5000x, one-sided p (frozen direction) = {p:.3f}")
            if survives and p is not None and p < 0.05:
                v = "ORDER-MATTERS"
            elif survives and p is not None:
                v = "NO-SPLIT"  # direction held but not beyond chance
                P("Direction held but does not beat the permutation null -> not distinguishable from chance.")
            else:
                v = "NO-SPLIT"
                P("Hold-out split vanished or reversed vs MINE.")
            P(f"**VERDICT [{L['nm']}]: {v}**")
            results[hid][key] = {"verdict": v, "mine": (ma, mb), "hold": (ha, hb), "p": p,
                                 "mine_dir": mine_dir}

    # ---- H4 ----
    P(f"\n## H4 CLEAN-LADDER (distinct classes reclaimed-and-held, prior 30 min: 0/1/2/3+)")
    results["H4"] = {}
    for key in ("break_attack", "grinder"):
        L = lanes[key]
        P(f"### {L['nm']}")
        mb_ = buckets(L["mine"]); hb_ = buckets(L["hold"])
        P("| bucket | MINE N | MINE $/tr | HOLD N | HOLD $/tr |")
        P("|---|---|---|---|---|")
        for b in range(4):
            lbl = str(b) if b < 3 else "3+"
            P(f"| {lbl} | {mb_[b]['N']} | ${mb_[b]['dtr']:+.2f} | {hb_[b]['N']} | ${hb_[b]['dtr']:+.2f} |")
        mat = [b for b in range(4) if mb_[b]["N"] >= 15]
        if len(mat) < 2:
            P("**UNDERPOWERED** — fewer than 2 material buckets on MINE.")
            results["H4"][key] = {"verdict": "UNDERPOWERED"}
            continue
        vals = [mb_[b]["dtr"] for b in mat]
        inc = all(vals[j] < vals[j + 1] for j in range(len(vals) - 1))
        dec = all(vals[j] > vals[j + 1] for j in range(len(vals) - 1))
        if not (inc or dec):
            P(f"MINE not monotone across material buckets {mat} -> **NO-SPLIT** (no monotone relationship).")
            results["H4"][key] = {"verdict": "NO-SPLIT", "mine": mb_, "hold": hb_}
            continue
        d = "increasing" if inc else "decreasing"
        P(f"MINE monotone {d} across material buckets {mat}. FROZEN.")
        hmat = [b for b in mat if hb_[b]["N"] >= 15]
        if len(hmat) < 2:
            P(f"**UNDERPOWERED on HOLD-OUT** (material hold-out buckets: {hmat}).")
            results["H4"][key] = {"verdict": "UNDERPOWERED", "mine": mb_, "hold": hb_}
            continue
        hv = [hb_[b]["dtr"] for b in hmat]
        hinc = all(hv[j] < hv[j + 1] for j in range(len(hv) - 1))
        hdec = all(hv[j] > hv[j + 1] for j in range(len(hv) - 1))
        same = (inc and hinc) or (dec and hdec)
        rho, p = perm_p_spearman(L["hold"]) if same else (None, None)
        if p is not None:
            P(f"HOLD-OUT monotone same direction; corr(bucket,pnl)={rho:+.3f}, permutation p={p:.3f}")
        v = "ORDER-MATTERS" if same and p is not None and p < 0.05 else ("NO-SPLIT" if not same or p is None else "NO-SPLIT")
        if not same:
            P("HOLD-OUT does not reproduce the monotone direction.")
        elif p is not None and p >= 0.05:
            P("Monotone direction reproduced but within permutation noise.")
        P(f"**VERDICT [{L['nm']}]: {v}**")
        results["H4"][key] = {"verdict": v, "mine": mb_, "hold": hb_, "p": p}

    # ---- summary ----
    P("\n---\n\n## SUMMARY (per hypothesis x lane)")
    P("| hyp | lane | MINE with/without $/tr | HOLD with/without $/tr | p | verdict |")
    P("|---|---|---|---|---|---|")
    for hid in ("H1", "H2", "H3"):
        for key in ("break_attack", "grinder"):
            z = results[hid][key]
            m = z.get("mine"); h = z.get("hold"); p = z.get("p")
            ms = f"${m[0]['dtr']:+.2f} / ${m[1]['dtr']:+.2f}" if m else "-"
            hs = f"${h[0]['dtr']:+.2f} / ${h[1]['dtr']:+.2f}" if h else "-"
            P(f"| {hid} | {lanes[key]['nm']} | {ms} | {hs} | {f'{p:.3f}' if p is not None else '-'} | {z['verdict']} |")
    for key in ("break_attack", "grinder"):
        z = results["H4"][key]
        p = z.get("p")
        P(f"| H4 | {lanes[key]['nm']} | (buckets above) | (buckets above) | {f'{p:.3f}' if p is not None else '-'} | {z['verdict']} |")

    open(HERE + "/seq_level_order_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    json.dump(results, open(HERE + "/seq_level_order_20260817_out.json", "w"),
              indent=1, default=str)
    return results

if __name__ == "__main__":
    main()
