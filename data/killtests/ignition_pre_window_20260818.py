#!/usr/bin/env python3
"""
IGNITION IN PREMARKET, 07:00-09:25 AND 08:00-09:25 (8/18)

Marcos: "there's no reason why ignition couldn't run at least 7:00-9:25, or at least 8:00-9:25.
Kev is always finding these big runs in pre"

WHY THE BOT'S OWN FUNCTION CANNOT ANSWER THIS
  ignition_10s_step refuses premarket by hand (:7945):
      if m < 570 or c <= 0: continue     # premarket / bad bar: not this machine's regime
  and caps itself at 570+IGNITION_WINDOW_MIN = 11:00. Replaying it over 551 name-days of
  premarket tape produced EXACTLY ZERO fires — the skip working, not evidence about the idea.
  So this study REIMPLEMENTS the detector condition-for-condition with the session frame
  re-anchored to premarket. That is a PARITY CAVEAT, stated up front: this is not the bot's
  function, it is a faithful copy of its conditions, and a positive result here is a reason to
  BUILD AND THEN RE-VERIFY against the real function, never a reason to ship directly.

CONDITIONS COPIED VERBATIM FROM THE LIVE DETECTOR (constants read from the source 8/18)
  base            = prior IGNITION_BASE_LOOKBACK(4) minutes of 10s bars, max CLOSE = base_hi
  volume surge    = v >= IGNITION_VOL_MULT(2.0) x base avg
  liquidity floor = v >= IGNITION_MIN_ABS_VOL(5000)/6 per 10s bar
  green bar       = c > o
  strong close    = (c-l)/range >= IGNITION_STRONG(0.5)
  breaks base     = c >= base_hi
  not extended    = IGNITION_MIN_EXT(-5%) <= (c-open)/open <= IGNITION_MAX_EXT(+15%)
  stop            = base_lo * (1 - ZONE_STOP_BUFFER(0.003))

THE ONE THING THAT CHANGES — THE SESSION FRAME
  `openp` in the live detector is "the first RTH 10s bar's open". Premarket has no such anchor,
  so each arm declares its own and the choice is part of the arm, not a hidden assumption:
    W0700  window 07:00-09:25, openp = first 10s bar at/after 07:00
    W0800  window 08:00-09:25, openp = first 10s bar at/after 08:00
    W0400  window 04:00-09:25, openp = first 10s bar at/after 04:00   (the widest reading)
  Extension is therefore measured from the window's own open, which is the closest premarket
  analogue to what the live rule means.

ADMISSION STACK — the SHIPPED one, applied identically to every arm:
  day-gain floor 3% (from the window open), relvol >= 2.0x (window baseline), VWAP tolerance
  band (>= premarket VWAP x (1-2%)), and the 9-over-20 stack once 22 3-min closes exist.

EXITS: stop-first INTRABAR, exit on a 1-min close back below premarket VWAP, and a HARD
FLATTEN AT 09:25 ET (the live premarket rule). Positions are NEVER carried into RTH, because
the live bot does not carry them. Entry slip -1%, exit slip -0.5%.

PRE-REGISTERED (before the run)
  * An arm is worth BUILDING only if hold-out $/trade > 0 AND hold-out n >= 40 AND green-day
    rate >= 40%.
  * Liquidity is the premarket hazard and is reported per arm (median fire-bar volume, median
    dollar volume). A positive $/trade on untradeable size is NOT an edge, and if the median
    fire bar cannot support the live clip this says so regardless of P&L.
  * PRE IS REPORTED ON ITS OWN LINE AND NEVER SUMMED WITH RTH (feedback_rth_official_pre_separate).
  * Chronological split: first 44 dates train, last 19 unseen. Both reported.

LIMITS: study reimplementation (parity caveat above), detector-only, no funnel — no premarket
scanner board, no chart gate, no slots/capital. The RTH slip model is applied to premarket
prints, which FLATTERS premarket, since real PRE spreads are wider. Read direction and the
liquidity columns. Nothing ships from this script.
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
VOL_MULT, MIN_ABS_VOL_10S, STRONG = 2.0, 5000 / 6.0, 0.5
BASE_MIN_10S, MIN_EXT, MAX_EXT, STOP_BUF = 4 * 6, -0.05, 0.15, 0.003
RELVOL_MIN, DAYGAIN_FLOOR, VWAP_TOL = 2.0, 3.0, 0.02
CLIP = 500.0


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
S, E = P.S, P.E
OUT = []


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


def scan(pre, start_hm):
    """The live ignition conditions, re-anchored to a premarket window. One fire per name-day
    (the live cap: cache[t]['ignition_fired'])."""
    idx = [n for n, b in enumerate(pre) if start_hm <= hm(b["t"]) < "09:25"]
    if len(idx) < BASE_MIN_10S + 12:
        return None
    lo, hi = idx[0], idx[-1]
    openp = pre[lo]["o"]
    if openp <= 0:
        return None
    cpv = cv = 0.0
    vw = {}
    for n in range(lo, hi + 1):
        b = pre[n]
        tp = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += tp * b["v"]; cv += b["v"]
        vw[n] = cpv / cv if cv else b["c"]
    c3 = []
    for n in range(lo, hi + 1):
        if (n - lo + 1) % 18 == 0:
            c3.append(pre[n]["c"])
        b = pre[n]
        base = pre[max(lo, n - BASE_MIN_10S):n]
        if len(base) < BASE_MIN_10S:
            continue
        o, h, l, c, v = b["o"], b["h"], b["l"], b["c"], b["v"]
        if c <= 0:
            continue
        base_hi = max(x["c"] for x in base)
        lows = [x["l"] for x in base if x["l"] > 0]
        if not lows:
            continue
        base_lo = min(lows)
        base_vol = (sum(x["v"] for x in base) / len(base)) or 1
        rng = (h - l) or 1e-9
        ext = (c - openp) / openp
        if not (v >= VOL_MULT * base_vol and v >= MIN_ABS_VOL_10S and c > o
                and (c - l) / rng >= STRONG and c >= base_hi
                and MIN_EXT <= ext <= MAX_EXT):
            continue
        # ---- shipped admission stack ----
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
        stop = base_lo * (1 - STOP_BUF)
        entry = c * (1 + SLIP)
        if stop >= entry or stop <= 0:
            continue
        sh = E.POS / entry
        pnl = None
        for k in range(n + 1, hi + 1):
            if hm(pre[k]["t"]) >= "09:25":
                break
            if pre[k]["l"] <= stop:
                pnl = sh * (stop * (1 - MKT) - entry); break
            if (k - n) % 6 == 0 and pre[k]["c"] < vw.get(k, 0):
                pnl = sh * (pre[k]["c"] * (1 - MKT) - entry); break
        if pnl is None:
            pnl = sh * (pre[hi]["c"] * (1 - MKT) - entry)   # 09:25 flatten
        return {"i": n, "hm": hm(b["t"]), "pnl": pnl, "vol": v, "dv": v * c, "px": c}
    return None


def main():
    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    ho = set(dates[44:])
    ARMS = {"W0700 (07:00-09:25)": "07:00",
            "W0800 (08:00-09:25)": "08:00",
            "W0400 (04:00-09:25)": "04:00"}
    rows = {k: [] for k in ARMS}
    nd = 0
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        full = S.FULL.get((sym, date))
        if not full:
            continue
        t0 = bars[0]["t"]
        pre = [b for b in full if b["t"] < t0]
        if len(pre) < 120:
            continue
        nd += 1
        for k, start in ARMS.items():
            r = scan(pre, start)
            if r:
                rows[k].append({**r, "sym": sym, "date": date})

    W("=" * 104)
    W('IGNITION IN PREMARKET — Marcos: "Kev is always finding these big runs in pre"')
    W("=" * 104)
    W(f"name-days with premarket tape: {nd}")
    W("STUDY REIMPLEMENTATION of the detector (the live one refuses premarket by hand, :7945).")
    W("PRE IS ITS OWN LINE — never summed with RTH.\n")

    def stat(rs):
        if not rs:
            return None
        p = [r["pnl"] for r in rs]
        d = defaultdict(float)
        for r in rs:
            d[r["date"]] += r["pnl"]
        vv = sorted(r["vol"] for r in rs)
        dv = sorted(r["dv"] for r in rs)
        return {"n": len(p), "tot": sum(p), "per": sum(p) / len(p),
                "win": 100.0 * sum(1 for x in p if x > 0) / len(p),
                "green": 100.0 * sum(1 for x in d.values() if x > 0) / max(len(d), 1),
                "mv": vv[len(vv) // 2], "mdv": dv[len(dv) // 2]}

    for lbl, sel in (("FULL SAMPLE", None), (f"HOLD-OUT (unseen {len(ho)})", ho)):
        W(lbl)
        for k in ARMS:
            s = stat([r for r in rows[k] if sel is None or r["date"] in sel])
            if not s:
                W(f"  {k:22s} n=0"); continue
            W(f"  {k:22s} n={s['n']:4d}  total=${s['tot']:+9.2f}  $/tr={s['per']:+7.2f}  "
              f"win={s['win']:4.0f}%  green={s['green']:3.0f}%  med bar vol={s['mv']:,.0f}  "
              f"med bar $vol=${s['mdv']:,.0f}")
        W("")

    W("FIRES BY ET HOUR (W0400 arm)")
    h = defaultdict(int)
    for r in rows["W0400 (04:00-09:25)"]:
        h[r["hm"][:2] + "h"] += 1
    W("  " + str(dict(sorted(h.items()))))

    W("\n" + "=" * 104)
    W("PRE-REGISTERED VERDICT")
    W("=" * 104)
    best, bs = None, None
    for k in ARMS:
        s = stat([r for r in rows[k] if r["date"] in ho])
        if s and (bs is None or s["per"] > bs["per"]):
            best, bs = k, s
    if not bs:
        W("  no hold-out fires — INCONCLUSIVE.")
    else:
        ok = bs["per"] > 0 and bs["n"] >= 40 and bs["green"] >= 40
        W(f"  best arm: {best}   ${bs['per']:+.2f}/tr  n={bs['n']}  green={bs['green']:.0f}%")
        W(f"  {'PASS' if ok else 'FAIL'}  $/tr>0 AND n>=40 AND green>=40%")
        liq = bs["mdv"] >= CLIP * 5
        W(f"  {'PASS' if liq else 'FAIL'}  liquidity: median fire-bar $vol ${bs['mdv']:,.0f} "
          f">= 5x a ${CLIP:,.0f} clip")
        W("")
        if ok and liq:
            W("  => PREMARKET IGNITION IS SUPPORTED on this bar. NEXT (not done here): change the")
            W("     detector's own m<570 skip + session-open anchor, then RE-VERIFY against the")
            W("     REAL function — this study is a reimplementation and cannot stand as the proof.")
        elif ok and not liq:
            W("  => P&L PASSES BUT LIQUIDITY FAILS. A positive $/trade on size we cannot fill is")
            W("     not an edge. Do not build on this alone.")
        else:
            W("  => NOT SUPPORTED on this bar. Kev's premarket runs are real; what this says is")
            W("     that IGNITION'S SPECIFIC CONDITIONS do not capture them profitably here —")
            W("     which is an argument for a premarket-native entry, not for unlocking this one.")
    W("\nLIMITS: study reimplementation, not the bot's function (parity caveat). Detector-only,")
    W("no premarket board/chart gate/slots. RTH slip model applied to premarket = FLATTERING.")
    json.dump({"out": OUT}, open(HERE + "/ignition_pre_window_20260818_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
