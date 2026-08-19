#!/usr/bin/env python3
"""
VWAP WATCHDOG — every stamped session VWAP, re-derived from the SIP tape (8/18)

Marcos: "is there a program that can run to block these wrong vwap from coming back?"

TWO DIFFERENT JOBS, AND THIS IS THE SECOND ONE
  The 8/18 coverage guard (VWAP_COVERAGE_GUARD, rig gate 15) stops an untrustworthy bar line
  from GATING a trade. It does not notice when a wrong value is still STAMPED on a row — and a
  wrong stamp silently poisons every study, autopsy and refusal audit that reads it afterwards.
  This is the detector: it re-derives the session VWAP from the raw 10s SIP tape at each trade's
  own entry timestamp and compares it to what the bot recorded.

WHY THE TAPE IS THE RIGHT REFEREE
  The CDTG failure was two internal sources disagreeing (bar 7.11 vs tick 4.6719) with nothing
  able to say which was right, because both were compared only to each other and to price. The
  harvested SIP tape is the independent third party. It settled that case in one command:
  4.6719 matched to 4 decimals; 7.11 matched no anchor at all.

WHAT IT CHECKS, per trade row that has tape available:
    session VWAP, PRE+RTH anchor (04:00)  -- the live default (ENTRY_VWAP_PREMARKET=True)
    session VWAP, RTH-only anchor (09:30) -- the documented alternative
  A stamp PASSES if it matches EITHER anchor within TOL (default 3%). Matching neither is a
  BREACH: the number came from somewhere that is not a session VWAP.

EXIT CODE: 0 clean, 1 if any breach. Safe to run as a nightly job or a ship gate.

USAGE
  python3 data/killtests/vwap_audit.py                 # every date with tape
  python3 data/killtests/vwap_audit.py 2026-08-18      # one date
  TOL=0.05 python3 data/killtests/vwap_audit.py        # looser band

LIMITS: only grades rows whose (date, ticker) exists in data/universe/bars10s. That cache is NOT
maintained automatically (harvester.py is a one-shot backfill; see harvest_day.py), so COVERAGE
IS REPORTED EXPLICITLY and a clean run over 3 rows means nothing. It grades the STAMP, not the
value any individual lane's gate consumed — a lane may read the tick line while the row records
the bar line, which is exactly how the CDTG defect hid.
"""
import datetime
import json
import os
import sys
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
TOL = float(os.environ.get("TOL", "0.03"))
DASH = "https://zestful-intuition-production-b16a.up.railway.app"
SECRET = os.environ.get("DASHBOARD_SECRET", "marcos2026")
ET = datetime.timezone(datetime.timedelta(hours=-4))


def et(ts):
    return datetime.datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).astimezone(ET)


def trades(date=None):
    u = f"{DASH}/api/trades" + (f"?date={date}" if date else "")
    r = urllib.request.Request(u, headers={"X-Dashboard-Secret": SECRET})
    d = json.load(urllib.request.urlopen(r, timeout=120))
    return d if isinstance(d, list) else (d.get("trades") or d.get("data") or [])


def session_vwaps(sym, date, at_et):
    """(pre_rth_anchor, rth_only_anchor) session VWAP at `at_et`, from raw SIP 10s bars."""
    p = os.path.join(BARS, f"{date}_{sym}.json")
    if not os.path.exists(p):
        return None, None
    b = json.load(open(p))
    b = b.get("bars", b) if isinstance(b, dict) else b
    acc = {"pre": [0.0, 0.0, None], "rth": [0.0, 0.0, None]}
    for x in b:
        e = et(x["time"])
        if e > at_et:
            break
        tp = (x["high"] + x["low"] + x["close"]) / 3.0
        for k, start in (("pre", "04:00"), ("rth", "09:30")):
            if e.strftime("%H:%M") < start:
                continue
            a = acc[k]
            a[0] += tp * x["volume"]; a[1] += x["volume"]
            a[2] = a[0] / a[1] if a[1] else x["close"]
    return acc["pre"][2], acc["rth"][2]


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    rows = [r for r in trades(date) if (r.get("date") or "") >= "2026-07-13"]
    graded = breaches = 0
    no_tape = 0
    by_lane = defaultdict(lambda: [0, 0])
    out = []
    for r in rows:
        stamp = r.get("entry_session_vwap")
        ts = r.get("entry_ts_utc")
        sym, d = r.get("ticker"), r.get("date")
        if not (stamp and ts and sym and d):
            continue
        pre, rth = session_vwaps(sym, d, et(ts))
        if pre is None and rth is None:
            no_tape += 1
            continue
        graded += 1
        lane = r.get("entry_type") or "?"
        by_lane[lane][0] += 1
        ok = any(v and abs(float(stamp) - v) / v <= TOL for v in (pre, rth) if v)
        if not ok:
            breaches += 1
            by_lane[lane][1] += 1
            best = min([v for v in (pre, rth) if v], key=lambda v: abs(float(stamp) - v))
            out.append((d, sym, et(ts).strftime("%H:%M:%S"), lane, float(stamp), pre, rth,
                        abs(float(stamp) - best) / best * 100.0, r.get("pnl") or 0.0))

    print("=" * 104)
    print("VWAP WATCHDOG — every stamped session VWAP re-derived from raw SIP tape")
    print("=" * 104)
    print(f"rows considered: {len(rows)}   GRADED (tape available): {graded}   "
          f"skipped, no tape: {no_tape}   tolerance: {TOL:.0%}")
    if graded and no_tape:
        print(f"  COVERAGE: {100.0*graded/(graded+no_tape):.0f}% of stampable rows had tape. The 10s "
              f"cache is NOT auto-maintained — a clean run over few rows proves little.")
    print()
    if out:
        print(f"{'date':11s} {'sym':7s} {'time':9s} {'lane':13s} {'STAMPED':>9s} "
              f"{'pre+rth':>9s} {'rth-only':>9s} {'off by':>8s} {'P&L':>9s}")
        for d, s, t, ln, st, pre, rth, off, pnl in sorted(out):
            print(f"{d:11s} {s:7s} {t:9s} {ln:13s} {st:9.4f} "
                  f"{(pre or 0):9.4f} {(rth or 0):9.4f} {off:7.1f}% {pnl:+9.2f}")
        print()
    print(f"BREACHES: {breaches} / {graded} graded")
    if by_lane:
        print("  by lane (breaches/graded):")
        for ln, (n, b) in sorted(by_lane.items(), key=lambda z: -z[1][1]):
            if n:
                print(f"    {ln:15s} {b:3d}/{n:3d}" + ("   <== " if b else ""))
    print()
    if breaches:
        print("VERDICT: RED — at least one stamped VWAP matches NEITHER session anchor. That value")
        print("did not come from a session VWAP, and every study reading those rows inherits it.")
        return 1
    print("VERDICT: GREEN — every graded stamp matches a session anchor within tolerance.")
    print("(Read the COVERAGE line before trusting this: ungraded rows are unaudited, not clean.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
