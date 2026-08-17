#!/usr/bin/env python3
"""ENRICHED-ALPHABET SEQUENCE MINING (8/17/26).

Marcos: "types of sequences that haven't been considered -- velocity, volume."
The base alphabet (kev_rosetta / sequence_mining_pilot_20260817) is PRICE-STRUCTURE only.
Question: does enriching each event with VOLUME STATE and VELOCITY split the proven
`T B` suffix (and others) into a good half and a bad half?

THREE NEW CHANNELS on the 10s bars (window = same 60 bars ending at the fire bar):
 1. VOLUME CASE on price events: bar volume vs p75 of prior 30 bars ->
    burst = UPPERCASE+'!' (B!, T!, P!, W!, H!, R!), fade/normal = lowercase (b, t, p, w, h, r).
    Pure-volume events: U = pullback dry-up (3 consecutive down/sideways bars, monotonically
    shrinking volume); X = volume climax w/o progress (vol >= p90, |close chg| <= 0.3%).
 2. VELOCITY: '>' pace expansion (mean bar range last 3 >= 1.5x prior 6), '<' compression
    (<= 0.6x). SEQUENCE VELOCITY: bars between the last T and the terminal B of every
    base-`T B` fire; FAST (<=6 bars) vs SLOW (>6) as separate gates.
 3. EFFORT/RESULT: A = absorption (vol >= p75, |close chg| <= 0.2%); V = vacuum
    (close chg >= +1% on vol <= p25).

PROTOCOL (lanes: break-attack + grinder, pilot generators, E3 live-parity):
 a. Enriched string per fire (base string kept too -- PILOT.event_string verbatim).
 b. MINE on MINE dates ONLY (2026-05-18..07-21, wall's exact split n_hold=18): rank last-2/
    last-3 enriched suffixes by $/tr lift, material-N = max(15, 6% of MINE fires); PLUS the
    pre-registered splits (t B! vs T! b vs other T B subtypes; FAST vs SLOW T->B;
    U-before-B; A-before-B; '>'-into-B), each computed WITHIN the base `T B` parent cohort.
 c. FREEZE top finding(s), apply to HOLD-OUT (07-22..08-14); grade raw-E3-$500 AND under the
    D-guard (dv>=20C full / >=10C half / else skip, slip model of seq_conditional_size).
    Permutation null (5000) WITHIN the hold-out T B parent cohort (the null is the subtype
    question, not the already-proven T B question).
 d. VERDICT per finding: ENRICHMENT-PAYS / NO-SPLIT / UNDERPOWERED. Full pre-registered
    list reported, nulls included -- 'velocity doesn't matter' is a finding.

Engine chain imported UNCHANGED from the pilot. Analysis only. No bot edits.
"""
import importlib.util, os, json, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E; F = S.F

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

def q(vals, frac):
    if not vals: return 0.0
    sv = sorted(vals)
    return sv[min(len(sv) - 1, int(frac * (len(sv) - 1)))]

# ---------------- enriched event string ----------------
# Price-event walk mirrors PILOT.event_string bar-for-bar (B/T/P/W/H/R/L/Q/F/D logic
# copied verbatim); each price event additionally carries its bar's volume case, and the
# U/X/A/V/>/< channels are interleaved at the emitting bar.  Every token records its bar
# index so sequence-velocity (T->B bar distance) is measurable.
def enriched_string(bars, i, halt_idx, lookback=60):
    ev = []  # list of (token, bar_idx)
    sess_hi = max(x["h"] for x in bars[:max(1, i - lookback)])
    q_run = 0
    for k in range(max(1, i - lookback), i + 1):
        b = bars[k]; p = bars[k - 1]; e = []
        vols = [x["v"] for x in bars[max(0, k - 30):k]]
        p75 = q(vols, 0.75); p90 = q(vols, 0.90); p25 = q(vols, 0.25)
        burst = b["v"] >= p75 and p75 > 0
        chg = (b["c"] - p["c"]) / p["c"] if p["c"] else 0.0
        def vc(tok):  # volume-case a price event
            return tok + "!" if burst else tok.lower()
        if k in halt_idx: e.append("L")
        loc_hi = max(x["h"] for x in bars[max(0, k - 30):k])
        if b["h"] > sess_hi: e.append(vc("B")); sess_hi = b["h"]
        elif b["h"] >= sess_hi * 0.997: e.append(vc("T"))
        elif b["h"] > loc_hi: e.append(vc("P"))
        h3 = max(x["h"] for x in bars[max(0, k - 3):k + 1])
        if b["l"] <= h3 * 0.98: e.append(vc("F"))
        conf = max(b["vwap"], b["e9"])
        got_w = got_h = False
        if b["l"] <= conf * 1.005 and b["c"] > conf and b["c"] > b["o"] and b["h"] < loc_hi:
            e.append(vc("W")); got_w = True
        elif PILOT.is_level_hold(bars, k) is not None:
            e.append(vc("H")); got_h = True
        else:
            step = 1.0 if b["c"] >= 1 else 0.10; got = False
            for L in (math.floor(b["c"] / step) * step, math.floor(b["c"] / (step / 2)) * (step / 2)):
                if L <= 0: continue
                if abs(b["l"] - L) / L <= 0.003 and b["c"] > L and any(
                        bars[j - 1]["c"] <= L < bars[j]["c"] for j in range(max(1, k - 30), k - 1)):
                    got = True; break
            if got: e.append(vc("R"))
        if not got_w and not got_h and b["l"] < min(x["l"] for x in bars[max(0, k - 6):k]):
            e.append(vc("D"))
        # ---- pure-volume events ----
        # U: 3 consecutive down/sideways bars with monotonically shrinking volume
        if k >= 3:
            w3 = bars[k - 2:k + 1]
            if all(x["c"] <= x["o"] * 1.0005 for x in w3) and w3[0]["v"] > w3[1]["v"] > w3[2]["v"]:
                e.append("U")
        # X: climax without progress
        if p90 > 0 and b["v"] >= p90 and abs(chg) <= 0.003:
            e.append("X")
        # ---- effort/result ----
        if p75 > 0 and b["v"] >= p75 and abs(chg) <= 0.002:
            e.append("A")
        if p25 > 0 and chg >= 0.01 and b["v"] <= p25:
            e.append("V")
        # ---- velocity (pace) ----
        if k >= 9:
            r3 = [x["h"] - x["l"] for x in bars[k - 2:k + 1]]
            r6 = [x["h"] - x["l"] for x in bars[k - 8:k - 2]]
            m3 = sum(r3) / 3.0; m6 = sum(r6) / 6.0
            if m6 > 0:
                if m3 >= 1.5 * m6: e.append(">")
                elif m3 <= 0.6 * m6: e.append("<")
        # ---- Q run (pilot convention) ----
        w = bars[max(0, k - 5):k + 1]
        if len(w) == 6 and max(x["h"] for x in w) / min(x["l"] for x in w) - 1 <= 0.01:
            q_run += 1
        else:
            if q_run >= 1 and (not ev or ev[-1][0] != "Q"): ev.append(("Q", k))
            q_run = 0
        for x in e:
            if not ev or ev[-1][0] != x: ev.append((x, k))
    if q_run >= 1 and (not ev or ev[-1][0] != "Q"): ev.append(("Q", i))
    return ev

def estruct(ev):
    """enriched STRUCTURAL: drop F/D variants (f, F!, d, D!), collapse consecutive dups."""
    s = [(t, k) for (t, k) in ev if t.rstrip("!").upper() not in ("F", "D")]
    return [(t, k) for j, (t, k) in enumerate(s) if j == 0 or s[j - 1][0] != t]

def base_letter(tok):
    return tok.rstrip("!").upper()

# ---------------- T->B anatomy on the enriched structural stream ----------------
def tb_anatomy(erows):
    """For a fire whose BASE structural string ends `T B`: locate the terminal B-token and
    the nearest preceding T-token in the enriched structural stream. Returns dict or None."""
    st = erows
    bi = None
    for j in range(len(st) - 1, -1, -1):
        if base_letter(st[j][0]) == "B":
            bi = j; break
    if bi is None: return None
    ti = None
    for j in range(bi - 1, -1, -1):
        if base_letter(st[j][0]) == "T":
            ti = j; break
    if ti is None: return None
    btok, bbar = st[bi]; ttok, tbar = st[ti]
    pre = st[:bi]  # everything before the terminal B
    toks_pre = [t for t, _ in pre]
    return {
        "t_burst": ttok.endswith("!"), "b_burst": btok.endswith("!"),
        "gap_bars": bbar - tbar,
        "u_before": "U" in toks_pre, "a_before": "A" in toks_pre,
        "x_before": "X" in toks_pre, "v_before": "V" in toks_pre,
        "pace_into_b": any(t == ">" and bbar - k <= 6 for t, k in pre),
        "compress_into_b": any(t == "<" and bbar - k <= 6 for t, k in pre),
    }

# ---------------- D-guard machinery (seq_conditional_size verbatim) ----------------
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
    if r["dv"] >= 20 * C: return resim(r, C)
    if r["dv"] >= 10 * C: return resim(r, C / 2)
    return 0.0

# ---------------- stats helpers ----------------
def mstat(rows):
    n = len(rows)
    if n == 0: return {"N": 0, "dtr": 0.0, "win": 0.0, "tot": 0.0}
    return {"N": n, "dtr": sum(r["pnl"] for r in rows) / n,
            "win": 100 * sum(1 for r in rows if r["win"]) / n,
            "tot": sum(r["pnl"] for r in rows)}

def gstat(rows):
    n = len(rows)
    if n == 0: return {"N": 0, "dtr": 0.0, "tot": 0.0}
    tot = sum(r["gpnl"] for r in rows)
    return {"N": n, "dtr": tot / n, "tot": tot}

def null_within(cohort_pnls, sub_pnls, iters=5000, seed=20260817):
    """Does the subtype beat a random same-size split OF THE COHORT?  p(random >= obs)."""
    m = len(sub_pnls)
    if m == 0 or m >= len(cohort_pnls): return None
    obs = sum(sub_pnls) / m
    rnd = random.Random(seed)
    ge = 0
    for _ in range(iters):
        if sum(rnd.sample(cohort_pnls, m)) / m >= obs: ge += 1
    return {"obs": obs, "p": ge / iters, "m": m, "iters": iters}

MIN_N = 10  # minimum fires on BOTH sides of a split (hold-out) to judge

def main():
    P("# ENRICHED-ALPHABET SEQUENCE MINING — 8/17/26")
    P("Volume-case + velocity + effort/result channels on the base price-structure alphabet.")
    P("Engine: pilot chain unchanged (E3 live-parity, $500). Analysis only.")
    P("")
    nf, nd, dates = S.load_all()
    n_hold = 18
    mine_dates = set(dates[:-n_hold]); hold_dates = set(dates[-n_hold:])
    P(f"Universe {nf} files / {nd} name-days / {len(dates)} dates.")
    P(f"SPLIT (wall parity): MINE {min(mine_dates)}..{max(mine_dates)} ({len(mine_dates)}d) | "
      f"HOLD-OUT {min(hold_dates)}..{max(hold_dates)} ({len(hold_dates)}d)")
    assert max(mine_dates) == "2026-07-21" and min(hold_dates) == "2026-07-22", "split violated"

    results = {}
    for key, nm in (("break_attack", "break-attack"), ("grinder", "grinder")):
        P(f"\n---\n\n## LANE: {nm}")
        rows = PILOT.grade(PILOT.gen_lane(key))
        for r in rows:
            bars, emas, gaps = E.DAYS[(r["sym"], r["date"])]
            halt_idx = {post for pre, post, g in gaps}
            er = estruct(enriched_string(bars, r["i"], halt_idx))
            r["est"] = [t for t, _ in er]; r["erows"] = er
            r["dv"] = bars[r["i"]]["c"] * bars[r["i"]]["v"]
            r["tb"] = (len(r["st"]) >= 2 and tuple(r["st"][-2:]) == ("T", "B"))
            r["anat"] = tb_anatomy(er) if r["tb"] else None
        mine = [r for r in rows if r["date"] in mine_dates]
        hold = [r for r in rows if r["date"] in hold_dates]
        mine_tb = [r for r in mine if r["tb"] and r["anat"]]
        hold_tb = [r for r in hold if r["tb"] and r["anat"]]
        P(f"Fires: total {len(rows)} | MINE {len(mine)} (T B parent {len(mine_tb)}) | "
          f"HOLD-OUT {len(hold)} (T B parent {len(hold_tb)})")

        # guard pnl for hold-out (both cohorts)
        for r in hold: r["gpnl"] = guarded_pnl(r)

        lane_res = {"N_mine": len(mine), "N_hold": len(hold),
                    "N_mine_tb": len(mine_tb), "N_hold_tb": len(hold_tb), "hyps": {}}

        # ---------- b. pre-registered splits (within T B parent) ----------
        def split(rows_tb, pred): return [r for r in rows_tb if pred(r["anat"])], [r for r in rows_tb if not pred(r["anat"])]
        HYPS = [
            ("H1 t->B! (quiet test, burst break)", lambda a: (not a["t_burst"]) and a["b_burst"]),
            ("H2 T!->b (burst test, fade break)",  lambda a: a["t_burst"] and (not a["b_burst"])),
            ("H3 T!->B! (both burst)",             lambda a: a["t_burst"] and a["b_burst"]),
            ("H4 t->b (both quiet)",               lambda a: (not a["t_burst"]) and (not a["b_burst"])),
            ("H5 FAST T->B (<=6 bars)",            lambda a: a["gap_bars"] <= 6),
            ("H6 U dry-up before B",               lambda a: a["u_before"]),
            ("H7 A absorption before B",           lambda a: a["a_before"]),
            ("H8 '>' pace-expansion into B (<=6 bars)", lambda a: a["pace_into_b"]),
            ("H9 X climax before B",               lambda a: a["x_before"]),
            ("H10 V vacuum before B",              lambda a: a["v_before"]),
        ]
        mine_coh = mstat(mine_tb)
        P(f"\n### Pre-registered splits WITHIN the `T B` parent cohort")
        P(f"MINE `T B` cohort: N={mine_coh['N']}, $/tr ${mine_coh['dtr']:+.2f}, win {mine_coh['win']:.0f}%")
        P("")
        P("| hypothesis | MINE N(has/not) | MINE $/tr has vs not | MINE lift | HOLD N(has/not) | HOLD $/tr has vs not | HOLD lift | HOLD guard lift | null p | verdict |")
        P("|---|---|---|---|---|---|---|---|---|---|")
        hold_coh = mstat(hold_tb)
        hold_pnls = [r["pnl"] for r in hold_tb]
        for hname, pred in HYPS:
            mh, mn_ = split(mine_tb, pred)
            hh, hn_ = split(hold_tb, pred)
            ms_h, ms_n = mstat(mh), mstat(mn_)
            hs_h, hs_n = mstat(hh), mstat(hn_)
            m_lift = ms_h["dtr"] - ms_n["dtr"] if ms_h["N"] and ms_n["N"] else 0.0
            h_lift = hs_h["dtr"] - hs_n["dtr"] if hs_h["N"] and hs_n["N"] else 0.0
            # guard lift on hold-out
            gs_h, gs_n = gstat(hh), gstat(hn_)
            g_lift = gs_h["dtr"] - gs_n["dtr"] if gs_h["N"] and gs_n["N"] else 0.0
            nr = null_within(hold_pnls, [r["pnl"] for r in hh]) if hh and hn_ else None
            mine_ok = ms_h["N"] >= MIN_N and ms_n["N"] >= MIN_N
            hold_ok = hs_h["N"] >= MIN_N and hs_n["N"] >= MIN_N
            if not mine_ok or not hold_ok:
                verdict = "UNDERPOWERED"
            elif m_lift * h_lift > 0 and abs(h_lift) > 5 and (nr is None or (nr["p"] <= 0.10 if h_lift > 0 else nr["p"] >= 0.90)):
                verdict = "ENRICHMENT-PAYS" if h_lift > 0 else "ENRICHMENT-PAYS (inverse: subtype is the BAD half)"
            else:
                verdict = "NO-SPLIT"
            p_s = f"{nr['p']:.3f}" if nr else "-"
            P(f"| {hname} | {ms_h['N']}/{ms_n['N']} | ${ms_h['dtr']:+.2f} vs ${ms_n['dtr']:+.2f} | ${m_lift:+.2f} | "
              f"{hs_h['N']}/{hs_n['N']} | ${hs_h['dtr']:+.2f} vs ${hs_n['dtr']:+.2f} | ${h_lift:+.2f} | ${g_lift:+.2f} | {p_s} | {verdict} |")
            lane_res["hyps"][hname] = {
                "mine_n": [ms_h["N"], ms_n["N"]], "mine_dtr": [ms_h["dtr"], ms_n["dtr"]], "mine_lift": m_lift,
                "hold_n": [hs_h["N"], hs_n["N"]], "hold_dtr": [hs_h["dtr"], hs_n["dtr"]], "hold_lift": h_lift,
                "guard_lift": g_lift, "null_p": nr["p"] if nr else None, "verdict": verdict}
        P(f"\nHOLD-OUT `T B` cohort raw: N={hold_coh['N']}, $/tr ${hold_coh['dtr']:+.2f}, win {hold_coh['win']:.0f}% | "
          f"under guard: $/tr ${gstat(hold_tb)['dtr']:+.2f}")

        # ---------- b2. open enriched-suffix mining (MINE only) ----------
        matn = max(15, int(0.06 * len(mine)))
        base_dtr = mstat(mine)["dtr"]
        best = None
        table = []
        for kk in (2, 3):
            buckets = defaultdict(list)
            for r in mine:
                if len(r["est"]) >= kk:
                    buckets[tuple(r["est"][-kk:])].append(r)
            for suf, sub in buckets.items():
                n = len(sub)
                if n < matn: continue
                st_ = mstat(sub)
                lift = st_["dtr"] - base_dtr
                table.append({"suf": " ".join(suf), "k": kk, "n": n, "dtr": st_["dtr"], "win": st_["win"], "lift": lift})
                if lift > 0 and st_["dtr"] > 0 and (best is None or lift > best["lift"]):
                    best = {"suf": suf, "k": kk, "n": n, "dtr": st_["dtr"], "lift": lift}
        table.sort(key=lambda z: -z["lift"])
        P(f"\n### Open enriched-suffix mining on MINE (material-N >= {matn} = max(15, 6% of {len(mine)}))")
        P(f"MINE base $/tr ${base_dtr:+.2f}. Top/bottom material enriched suffixes:")
        P("| suffix | N | win% | $/tr | lift |")
        P("|---|---|---|---|---|")
        for z in table[:6] + ([{"suf": "...", "n": "", "win": 0, "dtr": 0, "lift": 0}] if len(table) > 9 else []) + table[-3:]:
            if z["suf"] == "...": P("| ... | | | | |"); continue
            P(f"| `{z['suf']}` | {z['n']} | {z['win']:.0f}% | ${z['dtr']:+.2f} | ${z['lift']:+.2f} |")
        if best:
            suf = best["suf"]; kk = best["k"]
            hh = [r for r in hold if len(r["est"]) >= kk and tuple(r["est"][-kk:]) == suf]
            hs = mstat(hh); hold_all = mstat(hold)
            ghs = gstat(hh); ghold = gstat(hold)
            nr = null_within([r["pnl"] for r in hold], [r["pnl"] for r in hh]) if hh else None
            P(f"\n**FROZEN best MINE enriched suffix `{' '.join(suf)}`** (N={best['n']}, MINE $/tr ${best['dtr']:+.2f}, lift ${best['lift']:+.2f}) applied to HOLD-OUT:")
            P(f"- raw $500: gated N={hs['N']}, $/tr ${hs['dtr']:+.2f} vs ungated ${hold_all['dtr']:+.2f} (lift ${hs['dtr']-hold_all['dtr']:+.2f})")
            P(f"- under D-guard: gated $/tr ${ghs['dtr']:+.2f} vs ungated ${ghold['dtr']:+.2f}")
            if nr: P(f"- null (5000, vs whole hold-out book): p={nr['p']:.3f}, N={nr['m']}")
            lane_res["open_best"] = {"suf": " ".join(suf), "mine_n": best["n"], "mine_dtr": best["dtr"],
                                     "mine_lift": best["lift"], "hold_n": hs["N"], "hold_dtr": hs["dtr"],
                                     "hold_ungated_dtr": hold_all["dtr"], "hold_guard_dtr": ghs["dtr"],
                                     "null_p": nr["p"] if nr else None}
        else:
            P(f"\nOpen mining: NO material-N enriched suffix with positive lift on MINE.")
            lane_res["open_best"] = None
        results[key] = lane_res

    json.dump(results, open(HERE + "/seq_enriched_alphabet_20260817_out.json", "w"), indent=1, default=str)
    open(HERE + "/seq_enriched_alphabet_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    return results

if __name__ == "__main__":
    main()
