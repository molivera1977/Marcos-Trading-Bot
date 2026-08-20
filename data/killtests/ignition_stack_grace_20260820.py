#!/usr/bin/env python3
"""
IGNITION STACK-GATE GRACE BAND (8/20, Marcos: "i think some grace should be built into it.
let's look into it")

THE SPECIMEN. ZSTK 8/20 09:31:16: ignition fired at $4.50 on 5.9x volume, 7.18% above VWAP,
and was refused `ema9_under_ema20` with ema9 4.0749 vs ema20 4.0817 — a gap of $0.0068
(0.167%). The same move re-fired 106s later and kevseq filled at $4.89, the high print.

THE ASYMMETRY. The gate's two arms are not written alike (marcos_trading_bot.py ~:11148):
    _ig_vwap_bad  = price < vwap * (1 - IGNITION_VWAP_TOL)   # 2% approach band
    _ig_stack_bad = _e9 < _e20                               # NO tolerance at all
One arm assumes live data is noisy; the other treats a sub-penny gap as final.

WHY THE STACK LAGS BY CONSTRUCTION. The EMAs are computed on 3-MIN bars (SETUP_TF_MIN),
seeded with today's premarket 3-min closes (IGNITION_STACK_WARMUP). EMA9 on 3-min = ~27 min
of memory, EMA20 = ~60 min. At 09:31 the first RTH 3-min bar is still incomplete and is
dropped by `[:-1]`, so the gate judges the open using PREMARKET CLOSES ONLY — structurally
blind to the opening move it is being asked to confirm.

WHY A NATURAL EXPERIMENT IS NEEDED. `ignition_kev_gate_reject` rows begin 8/19 (verified:
the status is absent from every archive 8/05-8/18 while other ignition statuses are present
— positive control run). Direct cohort = 7 rows (8/19) + ZSTK = 8. Too few. BUT before the
gate existed, ignition fires with ema9 < ema20 CONVERTED — so every historical
`triggered_ignition` row is a trade the gate would now block or allow, and we can rebuild
its stack from tape and grade the outcome.

METHOD (positive control passed before use): rebuild the bot's own closes list exactly —
premarket 3-min closes (dropped last, clock-aligned) + RTH 3-min closes up to the fire
(dropped last) — and run the bot's own `_calc_ema` (SMA seed + k=2/(p+1)). Verified against
ZSTK's stamped row: ema9 4.0749 vs 4.0749 stamped, ema20 4.0818 vs 4.0817, seed n=90 vs 90.

READING (pre-registered): the grace band is interesting iff the admitted cohort (fires with
0 <= margin <= T) is POSITIVE in dollars AND holds sign across both date-parity halves. A
band that only works in one half is a lucky slice — the prevwap lesson.

LIMITS: 1-min SIP bars (not 10s); exits = house E3 walk (bank 1/2 @+10% -> BE -> 10% off
run-high trail, stop-first, 15:45 flat) applied uniformly to every cohort so comparisons are
like-for-like — ignition's live sizing multiplier is NOT modeled; slips -1%/-0.5%. Fires that
died at OTHER gates are included (this measures the STACK question in isolation, holding
everything else constant). Nothing ships from this file.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

SP = os.environ.get("ARCH_DIR", "")
AK, AS = os.environ.get("AK", ""), os.environ.get("AS", "")
RISK = 30.0
_barcache = {}


def calc_ema(cl, p):
    """the bot's _calc_ema, verbatim."""
    if len(cl) < p:
        return 0.0
    k = 2 / (p + 1)
    e = sum(cl[:p]) / p
    for c in cl[p:]:
        e = c * k + e * (1 - k)
    return e


def et(b):
    return dt.datetime.fromisoformat(b["t"][:19]) - dt.timedelta(hours=4)


def bars1m(sym, day):
    key = (sym, day)
    if key in _barcache:
        return _barcache[key]
    url = (f"https://data.alpaca.markets/v2/stocks/{sym}/bars?timeframe=1Min"
           f"&start={day}T08:00:00Z&end={day}T20:00:00Z&limit=10000&feed=sip")
    rq = urllib.request.Request(url, headers={"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS})
    try:
        b = json.load(urllib.request.urlopen(rq, timeout=30)).get("bars") or []
    except Exception:
        b = []
    _barcache[key] = b
    return b


def agg3_closes(bars):
    """clock-aligned 3-min slots -> [(slot_start_et, close)] (last close wins in slot)."""
    out = {}
    for b in bars:
        e = et(b)
        out[e.replace(minute=(e.minute // 3) * 3, second=0, microsecond=0)] = b["c"]
    return sorted(out.items())


def stack_at(sym, day, hhmm):
    """(ema9, ema20, n_closes) exactly as the live gate would have computed at hhmm ET."""
    B = bars1m(sym, day)
    if not B:
        return None
    pm = [b for b in B if et(b).strftime("%H:%M") < "09:30"]
    rth = [b for b in B if "09:30" <= et(b).strftime("%H:%M") <= hhmm]
    cl = [c for _, c in agg3_closes(pm)[:-1] if c > 0] + \
         [c for _, c in agg3_closes(rth)[:-1] if c > 0]
    if len(cl) < 22:
        return None
    return calc_ema(cl, 9), calc_ema(cl, 20), len(cl)


def walk_e3(sym, day, hhmm, entry, stop):
    """house E3 on 1-min tape from the bar AFTER the fire; 15:45 flat."""
    B = bars1m(sym, day)
    px = entry * 0.99
    rps = px - stop
    if rps <= 0 or not B:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for b in B:
        e = et(b)
        if e.strftime("%H:%M") <= hhmm:
            continue
        if e.strftime("%H:%M") >= "15:45":
            return banked + rem * (b["c"] * 0.995 - px)
        if b["l"] <= stop:
            return banked + rem * (stop - px)
        runhi = max(runhi, b["h"])
        if not tiered and b["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n
            tiered = True
            stop = px
            if rem == 0:
                return banked
        if tiered and b["c"] <= runhi * 0.90:
            return banked + rem * (b["c"] * 0.995 - px)
    return banked + rem * (B[-1]["c"] * 0.995 - px)


def main():
    rows = []
    for f in sorted(os.listdir(SP)):
        if not f.startswith("kg_"):
            continue
        try:
            j = json.load(open(os.path.join(SP, f)))
        except Exception:
            continue
        day = j.get("date")
        for r in (j.get("rows") or []):
            if r.get("status") != "triggered_ignition":
                continue
            t = r.get("time")
            px = r.get("price")
            st = r.get("stop") or r.get("zone_stop")
            if not (t and px and st):
                continue
            try:
                hhmm = dt.datetime.strptime(t, "%I:%M:%S %p").strftime("%H:%M")
            except Exception:
                continue
            rows.append({"d": day, "sym": r.get("ticker"), "hhmm": hhmm,
                         "px": float(px), "stop": float(st)})
    print(f"triggered_ignition rows with price+stop: {len(rows)}")
    out = []
    for r in rows:
        s = stack_at(r["sym"], r["d"], r["hhmm"])
        if not s:
            continue
        e9, e20, n = s
        if e20 <= 0:
            continue
        margin = (e20 - e9) / e20 * 100          # >0 = stack DOWN = gate would block
        pnl = walk_e3(r["sym"], r["d"], r["hhmm"], r["px"], r["stop"])
        if pnl is None:
            continue
        out.append({**r, "e9": round(e9, 4), "e20": round(e20, 4),
                    "margin": round(margin, 3), "pnl": round(pnl, 2), "n": n})
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "ignition_stack_grace_20260820_out.json"), "w"))
    print(f"graded: {len(out)}\n")

    def rep(lab, sel):
        v = [x["pnl"] for x in sel]
        if not v:
            print(f"  {lab:34s} n=0")
            return
        tr = [x["pnl"] for x in sel if int(x["d"][-2:]) % 2 == 0]
        oo = [x["pnl"] for x in sel if int(x["d"][-2:]) % 2 == 1]
        print(f"  {lab:34s} n={len(v):4d}  ${sum(v):+9.2f}  ${sum(v)/len(v):+7.2f}/tr  "
              f"green {100*sum(1 for x in v if x>0)/len(v):3.0f}%   "
              f"train {(sum(tr)/len(tr) if tr else 0):+7.2f} / oos {(sum(oo)/len(oo) if oo else 0):+7.2f}")

    passed = [x for x in out if x["margin"] <= 0]
    blocked = [x for x in out if x["margin"] > 0]
    print("BASELINE (what the gate does today):")
    rep("stack UP  -> gate ALLOWS", passed)
    rep("stack DOWN -> gate BLOCKS", blocked)
    print("\nGRACE LADDER (admit blocked fires whose margin <= T):")
    for T in (0.1, 0.167, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        rep(f"admit margin <= {T}%", [x for x in blocked if x["margin"] <= T])
    print("\n  (residual still blocked at each T is the complement of the row above)")
    for T in (0.25, 0.5, 1.0):
        rep(f"  still blocked > {T}%", [x for x in blocked if x["margin"] > T])
    print("\nPRE-REGISTERED: a band is interesting iff the admitted cohort is POSITIVE and")
    print("holds sign in BOTH date-parity halves. Nothing ships from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
