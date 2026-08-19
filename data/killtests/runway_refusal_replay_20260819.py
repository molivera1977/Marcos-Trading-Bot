#!/usr/bin/env python3
"""
RUNWAY REFUSAL REPLAY — what did the runway gate's refusals actually cost/save? (8/19, Marcos: "test it")

THE QUESTION (from the TNON/SKK split): the runway math is verified correct; the hypothesis is
that it is BLIND TO WALL STRENGTH — it refused TNON @12.36 (ran to 17.00) and SKK @8.42 (fell
to 5.45) with the same arithmetic. Does a strength term separate them?

ARMS (pre-registered before the run):
  A REFUSE-ALL   — the live gate: every refusal = $0. Baseline.
  B TAKE-ALL     — ignore runway entirely on these fires: entry at the refusal price, E3 exits.
  C TAKE-STRONG  — take ONLY refusals whose paired fire context shows wall-strength:
                   volx >= 4.0 OR crown at fire OR day_gain >= 50%. Fixed BEFORE grading;
                   chosen from the TNON specimen's visible fields, NOT tuned after.

EXITS: E3 as documented on the lanes — entry slip -1%; stop-first intrabar on 10s lows; bank 1/2
at +10%; then trail 10% off run-high; 15:45 force-flat; exit slip -0.5% on non-stop exits.
SIZING (DOLLARS law): risk-based shares = $29.50 / (entry-stop), capped at $500 notional and
5%-of-entry-bar-volume, min 1 share — the documented sim chain, stated here as the assumption.

STOP RECOVERY: refusal rows carry (price, runway_rr, target) but not the stop; rps is recovered
as (target-price)/runway_rr — exact algebra of the gate's own formula, verified on TNON
(12.75-12.3586)/0.21 = 1.86 ≈ the 12.36-10.52 the log printed (rounding in rr to 2dp).

PRE-REGISTERED READING: descriptive only — n will be small; NO threshold ships from this file.
The gate "earns its keep" on this cohort iff A >= B. The strength hypothesis "separates" iff
C > A AND C > B. Anything else is reported as-is. One name-day is hand-traced (TNON 09:35).

LIMITS: single config epoch not guaranteed (spans 8/12-8/19 detector changes); refusal prices
are fire prices, not fills (no queue/spread model beyond the slips); bars for <=8/18 come from
the local 10s SIP cache, 8/19 from the dashboard capture (~ALP10S) — two sources, same 10s
grid; refusals on names with NO tape available are listed and EXCLUDED, not silently dropped.
"""
import json
import os
import sys
import datetime
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
D = "https://zestful-intuition-production-b16a.up.railway.app"
H = {"X-Dashboard-Secret": "marcos2026"}
ET = datetime.timezone(datetime.timedelta(hours=-4))
DATES = ["2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18", "2026-08-19"]
RISK, NOTIONAL_CAP, VOL_CAP = 29.50, 500.0, 0.05


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=180))


def bars_for(sym, date):
    p = os.path.join(BARS, f"{date}_{sym}.json")
    if os.path.exists(p):
        b = json.load(open(p)); b = b.get("bars", b) if isinstance(b, dict) else b
        return [{"t": x["time"], "h": float(x["high"]), "l": float(x["low"]),
                 "c": float(x["close"]), "v": float(x["volume"])} for x in b]
    try:  # 8/19: dashboard capture
        r = get(f"{D}/api/bars?date={date}&ticker={sym}~ALP10S")
        return [{"t": x.get("time") or x.get("t"), "h": float(x.get("high") or x.get("h") or 0),
                 "l": float(x.get("low") or x.get("l") or 0), "c": float(x.get("close") or x.get("c") or 0),
                 "v": float(x.get("volume") or x.get("v") or 0)} for x in (r.get("bars") or [])]
    except Exception:
        return []


def hms(t):
    return datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).astimezone(ET).strftime("%H:%M:%S")


def e3(bars, i0, entry, stop, trace=False):
    """E3 walk from bar i0. Returns (pnl_$, shares, exit_reason, exit_hms)."""
    px = entry * 0.99                                     # -1% entry slip
    rps = px - stop
    if rps <= 0:
        return None
    sh = int(min(RISK / rps, NOTIONAL_CAP / px, max(bars[i0]["v"], 20) * VOL_CAP))
    sh = max(sh, 1)
    rem, banked, runhi, tier_done = sh, 0.0, px, False
    for i in range(i0 + 1, len(bars)):
        b = bars[i]
        t = hms(b["t"])
        if b["l"] <= stop:                                # stop-first intrabar
            pnl = banked + rem * (stop - px)
            if trace: print(f"      {t} STOP {stop}")
            return pnl, sh, "stop", t
        runhi = max(runhi, b["h"])
        if not tier_done and b["h"] >= px * 1.10:         # bank 1/2 at +10%
            half = rem // 2 or rem
            banked += half * (px * 1.10 * 0.995 - px)
            rem -= half; tier_done = True
            if trace: print(f"      {t} BANK {half}sh @ +10%")
            if rem == 0:
                return banked, sh, "tier_out", t
            stop = px                                     # breakeven after the bank (documented E3)
        if tier_done and b["c"] <= runhi * 0.90:          # trail 10% off run-high
            pnl = banked + rem * (b["c"] * 0.995 - px)
            if trace: print(f"      {t} TRAIL exit {b['c']} (runhi {runhi})")
            return pnl, sh, "trail", t
        if t >= "15:45:00":
            pnl = banked + rem * (b["c"] * 0.995 - px)
            return pnl, sh, "flat_1545", t
    b = bars[-1]
    return banked + rem * (b["c"] * 0.995 - px), sh, "eod", hms(b["t"])


def main():
    print("=" * 100)
    print("RUNWAY REFUSAL REPLAY — A refuse-all vs B take-all vs C take-strong   (E3, real tape)")
    print("=" * 100)
    rej, ctx = [], defaultdict(dict)
    for dt in DATES:
        rows = (get(f"{D}/api/decisions_archive?date={dt}&limit=50000").get("rows") or [])
        for r in rows:
            if r.get("status") == "runway_reject" and r.get("price") and r.get("target") and r.get("runway_rr"):
                rej.append((dt, r))
            if str(r.get("status", "")).startswith("triggered_"):
                ctx[(dt, r.get("ticker"), str(r.get("time"))[:8])] = r
    print(f"runway_reject rows with (price,target,rr): {len(rej)} across {len(DATES)} sessions\n")

    graded, skipped = [], []
    for dt, r in rej:
        sym, t = r["ticker"], str(r.get("time"))[:8]
        px, tgt, rr = float(r["price"]), float(r["target"]), float(r["runway_rr"])
        if rr <= 0 or tgt <= px:
            skipped.append((dt, sym, t, "degenerate rr/tgt")); continue
        stop = px - (tgt - px) / rr                       # recover the gate's own rps
        if stop <= 0 or stop >= px:
            skipped.append((dt, sym, t, "bad recovered stop")); continue
        bars = bars_for(sym, dt)
        if not bars:
            skipped.append((dt, sym, t, "NO TAPE")); continue
        i0 = next((i for i, b in enumerate(bars) if hms(b["t"]) >= t), None)
        if i0 is None or i0 >= len(bars) - 2:
            skipped.append((dt, sym, t, "fire after tape end")); continue
        # strength from the paired trigger row (same ticker, same second; fall back +-5s)
        tr = None
        base = datetime.datetime.strptime(t, "%H:%M:%S")
        for off in range(-5, 6):
            tr = ctx.get((dt, sym, (base + datetime.timedelta(seconds=off)).strftime("%H:%M:%S")))
            if tr: break
        volx = float((tr or {}).get("volx") or 0)
        dg = float((tr or {}).get("day_gain") or (tr or {}).get("day_n") or 0) if tr else 0.0
        crown = bool((tr or {}).get("crown") or (tr or {}).get("entry_crown"))
        strong = (volx >= 4.0) or crown or (dg >= 50.0)
        res = e3(bars, i0, px, stop)
        if not res:
            skipped.append((dt, sym, t, "rps<=0 after slip")); continue
        pnl, sh, why, xt = res
        graded.append({"dt": dt, "sym": sym, "t": t, "px": px, "stop": round(stop, 4),
                       "tgt": tgt, "rr": rr, "volx": volx, "dg": dg, "crown": crown,
                       "strong": strong, "pnl": round(pnl, 2), "sh": sh, "exit": why, "xt": xt})

    print(f"graded: {len(graded)}   excluded: {len(skipped)}")
    for s in skipped: print("   excluded:", s)
    print()
    print(f"{'date':11s}{'sym':6s}{'fire':9s}{'lane $px':>9s}{'stop':>8s}{'rr':>6s}{'volx':>6s}"
          f"{'dg%':>7s}{'str':>4s}{'E3 $':>9s}{'exit':>10s}")
    for g in sorted(graded, key=lambda z: (z["dt"], z["t"])):
        print(f"{g['dt']:11s}{g['sym']:6s}{g['t']:9s}{g['px']:9.2f}{g['stop']:8.2f}{g['rr']:6.2f}"
              f"{g['volx']:6.1f}{g['dg']:7.1f}{'  Y' if g['strong'] else '  .':>4s}{g['pnl']:9.2f}{g['exit']:>10s}")
    A = 0.0
    B = sum(g["pnl"] for g in graded)
    C = sum(g["pnl"] for g in graded if g["strong"])
    nC = sum(1 for g in graded if g["strong"])
    print()
    print("=" * 100)
    print(f"A REFUSE-ALL  : $0.00           (the live gate, n={len(graded)} refusals)")
    print(f"B TAKE-ALL    : ${B:+.2f}       (every refusal taken, E3)")
    print(f"C TAKE-STRONG : ${C:+.2f}       (n={nC} strength-qualified: volx>=4 | crown | dg>=50)")
    print(f"  weak-only     ${B - C:+.2f}     (what C correctly leaves behind)" )
    print()
    print("PRE-REGISTERED READING (descriptive; nothing ships from this file):")
    print(f"  gate earns its keep on this cohort: {'YES' if 0 >= B else 'NO'} (A >= B)")
    print(f"  strength separates:                 {'YES' if (C > 0 and C > B) else 'NO'} (C > A and C > B)")
    print()
    print("HAND-TRACE (sim-integrity law) — TNON 2026-08-19 09:35:28:")
    for dt, r in rej:
        if r.get("ticker") == "TNON" and str(r.get("time")).startswith("09:35"):
            b = bars_for("TNON", dt)
            i0 = next((i for i, x in enumerate(b) if hms(x["t"]) >= "09:35:28"), None)
            if i0 is not None:
                px = float(r["price"]); tgt = float(r["target"]); rr = float(r["runway_rr"])
                stop = px - (tgt - px) / rr
                print(f"   entry {px} (slip-> {px*0.99:.4f}) stop {stop:.4f}")
                e3(b, i0, px, stop, trace=True)
            break
    out = os.path.join(HERE, "runway_refusal_replay_20260819_out.json")
    json.dump(graded, open(out, "w"), indent=1)
    print(f"\nper-row results saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
