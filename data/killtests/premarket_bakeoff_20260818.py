#!/usr/bin/env python3
"""
THE PREMARKET BAKE-OFF — WHO SHOULD LEAD THE 07:00-09:25 PACK? (8/18)

Marcos: "our pre roster sucks. we have never made real money in pre. so i want ignition and
9/90 running in pre and i want them leading the pack unless you can tell me a better choice
or choices"

HE IS RIGHT ABOUT THE BOOK (live rows, era 7/13+, verified before this script):
  PRE fills n=41, total -$696.53, 12 days traded, 42% green
     vwap_reclaim   15 fills   -$648.24     <- nearly the entire loss
     hidden_entry   25 fills    -$35.00
     v2conv          1 fill     -$13.29
  and `prevwap` — Kev's 07:00-09:25 lane, the one actually BUILT for premarket — has ZERO fills.

THE QUESTION THIS ANSWERS: across every lane we can honestly grade on premarket tape, which
ones pay between 07:00 and 09:25? Marcos's proposal (ignition + 9/90 leading) is one arm among
them, not the assumed answer.

ENTRANTS
  ign_pre    ignition's conditions, re-anchored to the 07:00 window (STUDY REIMPLEMENTATION —
             the live detector refuses premarket at :7945; see ignition_pre_window_20260818)
  x9_pre     the 1-min 9/90 up-cross at/above premarket VWAP, premarket-warmed EMAs
  prevwap    the bot's OWN premarket lane (bandpass_step, window 420-565) via live_harness
  hidden     hidden_entry_step via live_harness
  v2         v2_pullback_step via live_harness
  grinder    grinder_shadow_step via live_harness
  reclaim    kev_reclaim_step via live_harness   <- the lane that lost -$648.24 live

IDENTICAL TREATMENT FOR ALL: window 07:00-09:25 ET, entry slip -1%, exit slip -0.5%,
stop-first INTRABAR, exit on a 1-min close below premarket VWAP, HARD FLATTEN 09:25 (the live
premarket rule — nothing is carried into RTH, because the live bot does not carry it). Each
lane keeps its OWN stop. One position per name-day per lane.

PRE IS ITS OWN LINE AND IS NEVER SUMMED WITH RTH (feedback_rth_official_pre_separate).

PRE-REGISTERED (before the run)
  * A lane EARNS a premarket seat only with hold-out $/trade > 0, n >= 30, green >= 40%.
  * "Leading the pack" is decided by hold-out $/day at N=2 and N=4 (premarket capital is the
    same $3,000; realistic premarket concurrency is low), NOT by $/trade alone.
  * If a lane Marcos did NOT name outranks ignition/9-90 on those bars, SAY SO — the brief was
    explicitly "unless you can tell me a better choice".
  * Liquidity is reported per lane (median fire-bar $vol). Positive P&L on unfillable size is
    not a seat.
  * Chronological split: first 44 dates train, last 19 unseen. Both reported.

PARITY, STATED NOT BURIED (harness_parity.json): grinder 9.1%, v2 51.2%, bandpass/prevwap
44.4%, hidden 86.3%, reclaim/zone_flip measured on N=3. Sub-threshold lanes are marked with (!)
in the output and MAY NOT be given a seat on this evidence alone. ign_pre and x9_pre are study
constructions, not bot functions — also marked.

LIMITS: detector-only; no premarket scanner board, no chart gate, no slots/capital. The RTH
slip model is applied to premarket prints, which FLATTERS every arm equally. Nothing ships.
"""
import importlib.util
import json
import os
import sys
import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ET = datetime.timezone(datetime.timedelta(hours=-4))
MKT, SLIP = 0.005, 0.01
OPEN_HM, CLOSE_HM = "07:00", "09:25"
VOL_MULT, MIN_ABS_VOL_10S, STRONG = 2.0, 5000 / 6.0, 0.5
BASE_10S, MIN_EXT, MAX_EXT, STOP_BUF = 24, -0.05, 0.15, 0.003
RELVOL_MIN, DAYGAIN_FLOOR, VWAP_TOL = 2.0, 3.0, 0.02


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
H = _load("H", HERE + "/live_harness.py")
S, E = P.S, P.E
OUT = []
PARITY = {}
try:
    PARITY = {k: v.get("parity_pct") for k, v in
              json.load(open(HERE + "/harness_parity.json"))["lanes"].items()}
except Exception:
    pass


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def hm(t):
    d = datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc)
    return d.astimezone(ET).strftime("%H:%M")


def ema_last(v, n):
    k = 2.0 / (n + 1)
    e = None
    for x in v:
        e = x if e is None else (x - e) * k + e
    return e


def window(pre):
    idx = [n for n, b in enumerate(pre) if OPEN_HM <= hm(b["t"]) < CLOSE_HM]
    return (idx[0], idx[-1]) if len(idx) > 60 else (None, None)


def vwap_series(pre, lo, hi):
    cpv = cv = 0.0
    vw = {}
    for n in range(lo, hi + 1):
        b = pre[n]
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw[n] = cpv / cv if cv else b["c"]
    return vw


def grade(pre, lo, hi, vw, n, entry_px, stop):
    entry = entry_px * (1 + SLIP)
    if stop >= entry or stop <= 0:
        return None
    sh = E.POS / entry
    for k in range(n + 1, hi + 1):
        if pre[k]["l"] <= stop:
            return sh * (stop * (1 - MKT) - entry)
        if (k - n) % 6 == 0 and pre[k]["c"] < vw.get(k, 0):
            return sh * (pre[k]["c"] * (1 - MKT) - entry)
    return sh * (pre[hi]["c"] * (1 - MKT) - entry)      # 09:25 flatten


def ign_pre(pre, lo, hi, vw):
    openp = pre[lo]["o"]
    if openp <= 0:
        return None
    c3 = []
    for n in range(lo, hi + 1):
        if (n - lo + 1) % 18 == 0:
            c3.append(pre[n]["c"])
        base = pre[max(lo, n - BASE_10S):n]
        if len(base) < BASE_10S:
            continue
        b = pre[n]
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        if c <= 0:
            continue
        bh = max(x["c"] for x in base)
        lows = [x["l"] for x in base if x["l"] > 0]
        if not lows:
            continue
        bl = min(lows)
        bv = (sum(x["v"] for x in base) / len(base)) or 1
        rng = (h - l) or 1e-9
        ext = (c - openp) / openp
        if not (v >= VOL_MULT * bv and v >= MIN_ABS_VOL_10S and c > o
                and (c - l) / rng >= STRONG and c >= bh and MIN_EXT <= ext <= MAX_EXT):
            continue
        if (c / openp - 1) * 100.0 < DAYGAIN_FLOOR:
            continue
        v1 = sum(x["v"] for x in pre[max(lo, n - 5):n + 1])
        span = max(n - lo, 1)
        avg = sum(x["v"] for x in pre[lo:n]) / max(span / 6.0, 1) if span > 12 else 0
        if avg > 0 and (v1 / avg) < RELVOL_MIN:
            continue
        if vw[n] > 0 and c < vw[n] * (1 - VWAP_TOL):
            continue
        if len(c3) >= 22 and ema_last(c3, 9) < ema_last(c3, 20):
            continue
        p = grade(pre, lo, hi, vw, n, c, bl * (1 - STOP_BUF))
        if p is not None:
            return {"i": n, "pnl": p, "dv": v * c}
    return None


def x9_pre(pre, lo, hi, vw):
    """1-min 9/90 up-cross at/above premarket VWAP. EMAs warmed from ALL bars before the
    window (04:00 onward), so the 90-EMA is seated when the window opens."""
    e9 = e90 = None
    m1 = 0
    prev = None
    for n in range(0, hi + 1):
        if n % 6 != 5:
            continue
        c = pre[n]["c"]
        m1 += 1
        e9 = c if e9 is None else (c - e9) * (2 / 10.0) + e9
        e90 = c if e90 is None else (c - e90) * (2 / 91.0) + e90
        if m1 < 90:
            prev = e9 > e90
            continue
        ab = e9 > e90
        cross = (prev is False) and ab
        prev = ab
        if not cross or n < lo or n > hi - 3:
            continue
        if c < vw.get(n, 0):
            continue
        stop = min(x["l"] for x in pre[max(lo, n - 30):n + 1])
        p = grade(pre, lo, hi, vw, n, c, stop)
        if p is not None:
            return {"i": n, "pnl": p, "dv": pre[n]["v"] * c}
    return None


def harness_lane(sym, date, pre, lo, hi, vw, lane):
    raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
            "low": b["l"], "close": b["c"], "volume": b["v"]} for b in pre]

    def _vwp(_s, _i, _b, _l):
        return vw.get(min(max(int(_i), lo), hi), pre[min(max(int(_i), 0), len(pre) - 1)]["c"])
    try:
        fs = H.replay(sym, raw, [lane], day=date, batch_secs=60, vwap_provider=_vwp)
    except Exception:
        return None
    for f in fs or []:
        i, px = f.get("i"), (f.get("px") or f.get("price"))
        st = f.get("stop") or f.get("zone_stop") or f.get("would_stop")
        if i is None or not px or not st:
            continue
        i = int(i)
        if not (lo <= i <= hi - 3):
            continue
        p = grade(pre, lo, hi, vw, i, float(px), float(st))
        if p is not None:
            return {"i": i, "pnl": p, "dv": pre[i]["v"] * float(px)}
    return None


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    ho = set(dates[44:])
    HARNESS = ["prevwap", "hidden", "v2", "grinder", "reclaim"]
    rows = defaultdict(list)
    nd = 0
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        full = S.FULL.get((sym, date))
        if not full:
            continue
        t0 = bars[0]["t"]
        pre = [b for b in full if b["t"] < t0]
        if len(pre) < 150:
            continue
        lo, hi = window(pre)
        if lo is None:
            continue
        nd += 1
        vw = vwap_series(pre, lo, hi)
        for nm, fn in (("ign_pre", ign_pre), ("x9_pre", x9_pre)):
            r = fn(pre, lo, hi, vw)
            if r:
                rows[nm].append({**r, "sym": sym, "date": date})
        for lane in HARNESS:
            r = harness_lane(sym, date, pre, lo, hi, vw, lane)
            if r:
                rows[lane].append({**r, "sym": sym, "date": date})

    W("=" * 108)
    W("THE PREMARKET BAKE-OFF — 07:00-09:25 ET, who deserves the seat?")
    W("=" * 108)
    W(f"name-days with a usable 07:00-09:25 window: {nd}")
    W("LIVE PRE BOOK, era 7/13+: 41 fills, -$696.53 (vwap_reclaim -$648.24 of it); "
      "prevwap has ZERO live fills.")
    W("PRE IS ITS OWN LINE — never summed with RTH.\n")

    def stat(rs):
        if not rs:
            return None
        p = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        dv = sorted(r["dv"] for r in rs)
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1),
                "mdv": dv[len(dv) // 2]}

    def perday(rs, n):
        byday = defaultdict(list)
        for r in sorted([x for x in rs if x["date"] in ho], key=lambda z: (z["date"], z["i"])):
            byday[r["date"]].append(r)
        return sum(sum(x["pnl"] for x in v[:n]) for v in byday.values()) / max(len(ho), 1)

    def tag(nm):
        if nm in ("ign_pre", "x9_pre"):
            return "(!) study"
        p = PARITY.get({"prevwap": "prevwap"}.get(nm, nm))
        return f"(!) parity {p:.0f}%" if (p is not None and p < 90) else ""

    order = ["ign_pre", "x9_pre", "prevwap", "hidden", "v2", "grinder", "reclaim"]
    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)})", ho)):
        W(lbl)
        for nm in order:
            s = stat([r for r in rows[nm] if sel is None or r["date"] in sel])
            if not s:
                W(f"  {nm:9s} n=0                                                    {tag(nm)}")
                continue
            W(f"  {nm:9s} n={s['n']:4d}  total=${s['tot']:+9.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:3.0f}%  green={s['green']:3.0f}%  med $vol=${s['mdv']:>9,.0f}  {tag(nm)}")
        W("")

    W("CAPACITY — hold-out $/day (premarket concurrency is low; N=2 and N=4)")
    W(f"  {'lane':9s}{'N=2':>12s}{'N=4':>12s}")
    pd_ = {}
    for nm in order:
        if not rows[nm]:
            continue
        pd_[nm] = {n: perday(rows[nm], n) for n in (2, 4)}
        W(f"  {nm:9s}{pd_[nm][2]:>12.2f}{pd_[nm][4]:>12.2f}")

    W("\n" + "=" * 108)
    W("PRE-REGISTERED VERDICT")
    W("=" * 108)
    seats = []
    for nm in order:
        s = stat([r for r in rows[nm] if r["date"] in ho])
        if s and s["per"] > 0 and s["n"] >= 30 and s["green"] >= 40:
            seats.append((nm, s, pd_.get(nm, {}).get(2, 0.0), pd_.get(nm, {}).get(4, 0.0)))
    if not seats:
        W("  NO LANE EARNS A PREMARKET SEAT on this bar ($/tr>0, n>=30, green>=40%).")
        W("  That includes ignition and the 9/90. The honest answer to 'who leads the pack' is")
        W("  NOBODY, and the current PRE roster's -$696.53 is not fixed by reordering it.")
    else:
        seats.sort(key=lambda z: -z[3])
        W("  LANES THAT EARN A SEAT (hold-out $/tr>0, n>=30, green>=40%), ranked by $/day @N=4:")
        for nm, s, p2, p4 in seats:
            W(f"    {nm:9s} ${p4:+7.2f}/day @N=4  ${p2:+7.2f} @N=2   ${s['per']:+6.2f}/tr  "
              f"n={s['n']:3d}  green {s['green']:3.0f}%  {tag(nm)}")
        lead = seats[0][0]
        W(f"\n  LEADS THE PACK ON THIS EVIDENCE: {lead}")
        if lead not in ("ign_pre", "x9_pre"):
            W(f"  NOTE FOR MARCOS: {lead} is NOT one of the two you named. That is the "
              "'better choice' the brief asked for.")
        named = [n for n, *_ in seats if n in ("ign_pre", "x9_pre")]
        W(f"  of the two you named, these earned a seat: {named or 'NEITHER'}")
    W("\n  ANY lane marked (!) cannot take a live seat on this evidence alone: study")
    W("  reimplementations need re-verification against the real function; sub-90% parity lanes")
    W("  are measuring the harness as much as the lane.")
    W("\nLIMITS: detector-only, no premarket board/chart gate/slots/capital. RTH slip model on")
    W("premarket prints FLATTERS every arm equally. One position per name-day per lane.")
    json.dump({"out": OUT}, open(HERE + "/premarket_bakeoff_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
