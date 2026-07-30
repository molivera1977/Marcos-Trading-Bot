"""HONEST REPLAY HARNESS (7/29 night, Fable-approved spec P1-E — supersedes every flat-$30-R replay).

Why this exists: the old ad-hoc replays assumed (a) every trade risks exactly $30, (b) exits fill
exactly at the stop, (c) any share count fills. All three are false and all three flatter the
tight-stop/high-share trades that hurt us most (7/29: SKYQ really risked $7.58; slippage past the
stop is ~1.5% of entry, ~constant across widths; the volume guard cut RBNE 200→34 sh). Verdicts
produced on that harness are not verdicts.

What this one does, per trade:
  1. SIZING through the real chain: shares = min(RISK/rps, CAP/entry, VOLGUARD% of avg 1-min vol
     over the trailing window ending at entry). Every clamp is reported.
  2. EXITS through the real kev25 ladder: intrabar stop, 50%@1R, 25%@2R, BE floor after scale
     #BE_FLOOR_AFTER_SCALE (default 2 = live), 3-min-low runner trail after scale 2, 15:45 flat.
  3. SLIPPAGE on stopped exits: fill = stop − SLIP_PCT×entry. Calibrated 7/29 from 59 clean era
     stop-loss fills: median 1.477% of entry (mean 2.211% — tail-skew from halt-class gaps; use
     slip_pct=0.02211 for the pessimistic variant). Scale-outs/trails get NO slippage bonus or
     penalty (they were limit-ish in practice) — conservative on winners.
  4. DOLLARS ONLY. R is derived, never assumed.

ACCEPTANCE (Fable requirement): before grading anything hypothetical, `acceptance_run()` replays
the day's REAL trades from their recorded entries/stops/shares and must reproduce booked P&L within
tolerance. A harness that can't reproduce the day we watched cannot judge the days we didn't.

Known limits (stated, not hidden): prices come from the Alpaca 10s archive while live fills happen
on the Webull stream — the two materially diverged at least once (STFS 09:58, open investigation
#11), so bar-based stop timing is approximate; entry fills are assumed at the given entry price
(no entry-side slippage modeled, v1); halts are not modeled beyond what the slip tail captures.
"""
import json, urllib.request, urllib.parse, statistics
from datetime import datetime, timedelta, timezone

U  = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))

RISK        = 30.0
CAP         = 1000.0
VOLGUARD    = 0.05          # 5% of avg recent 1-min volume (MAX_POS_VOL_PCT live)
VOL_WIN_MIN = 5             # trailing minutes for the volume average (live uses "recent avg")
SLIP_PCT    = 0.01477       # median calibration 7/29 (59 clean era stop fills); 0.02211 = mean
BE_AFTER    = 2             # live BE_FLOOR_AFTER_SCALE (7/28 revert)
FLAT_HM     = "15:45:00"

_bars_cache = {}

def bars(tk, date):
    """Archived 10s bars for tk on date, ET-normalized: [(epoch,o,h,l,c,v,'HH:MM:SS'), ...]."""
    key = (tk, date)
    if key in _bars_cache:
        return _bars_cache[key]
    try:
        r = json.load(urllib.request.urlopen(
            f"{U}/api/bars?date={date}&ticker={urllib.parse.quote(tk + '~ALP10S')}", timeout=30))
        raw = r.get("bars") or []
    except Exception:
        raw = []
    out = []
    for x in raw:
        t = x.get("time") or x.get("t")
        if not t:
            continue
        try:
            dt = datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc).astimezone(ET)
        except Exception:
            continue
        out.append((int(dt.timestamp()), float(x.get("open") or x.get("o")),
                    float(x.get("high") or x.get("h")), float(x.get("low") or x.get("l")),
                    float(x.get("close") or x.get("c")), float(x.get("volume") or x.get("v") or 0),
                    dt.strftime("%H:%M:%S")))
    out.sort()
    _bars_cache[key] = out
    return out


def size(entry, stop, b, i0):
    """The REAL sizing chain. Returns (shares, clamp, detail). shares=0 => trade refused/unsizeable."""
    rps = entry - stop
    if rps <= 0:
        return 0, "invalid_ticket", {}                     # P0-A: stop at/above entry is never a trade
    sh_risk     = int(RISK / rps)
    sh_notional = int(CAP / entry)
    # volume guard: avg 1-min volume over the trailing window ending at the entry bar
    k0 = b[i0][0]
    win = [x for x in b[:i0 + 1] if x[0] > k0 - VOL_WIN_MIN * 60]
    vol_1m = (sum(x[5] for x in win) / max(VOL_WIN_MIN, 1)) if win else 0.0
    sh_vol = int(vol_1m * VOLGUARD) if vol_1m > 0 else 10 ** 9
    sh = min(sh_risk, sh_notional, sh_vol)
    clamp = {sh_risk: "risk", sh_notional: "notional_cap", sh_vol: "volume_guard"}[
        min(sh_risk, sh_notional, sh_vol)]
    if sh < 1:
        return 0, "sub_1_share", {"sh_risk": sh_risk, "sh_notional": sh_notional, "sh_vol": sh_vol}
    return sh, clamp, {"sh_risk": sh_risk, "sh_notional": sh_notional, "sh_vol": sh_vol,
                       "actual_risk": round(sh * rps, 2)}


def replay(tk, date, entry, stop, i0=None, entry_hm=None, shares=None, slip_pct=SLIP_PCT,
           be_after=BE_AFTER):
    """Walk one trade through the real ladder on the real tape. Provide i0 (bar index) or entry_hm.
    shares=None => size through the real chain; pass recorded shares for acceptance runs.
    Returns dict with pnl, shares, clamp, events — or None when untradeable/no tape."""
    b = bars(tk, date)
    if not b:
        return None
    if i0 is None:
        if entry_hm is None:
            return None
        i0 = next((i for i, x in enumerate(b) if x[6] >= entry_hm), None)
        if i0 is None:
            return None
    if shares is None:
        sh, clamp, det = size(entry, stop, b, i0)
        if sh == 0:
            return {"tk": tk, "date": date, "pnl": 0.0, "shares": 0, "clamp": clamp,
                    "events": [("-", clamp)], "refused": True, **det}
    else:
        sh, clamp, det = int(shares), "recorded", {}
    rps = entry - stop
    t1, t2 = entry + rps, entry + 2 * rps
    rem, real, cur = sh, 0.0, stop
    scales = 0
    m1, events = {}, []
    for j in range(i0 + 1, len(b)):
        k, o, h, l, c, v, hm = b[j]
        key = k // 60
        d = m1.setdefault(key, [l, c]); d[0] = min(d[0], l); d[1] = c
        if hm >= FLAT_HM:
            events.append((hm, f"15:45 flat @ {c:.4f}"))
            return {"tk": tk, "date": date, "pnl": round(real + rem * (c - entry), 2), "shares": sh,
                    "clamp": clamp, "events": events, "refused": False, **det}
        if l <= cur:
            fill = cur - (slip_pct * entry if cur <= stop + 1e-9 else 0.0)   # slip only on the ORIGINAL stop
            events.append((hm, f"stop {cur:.4f} -> fill {fill:.4f}"))
            return {"tk": tk, "date": date, "pnl": round(real + rem * (fill - entry), 2), "shares": sh,
                    "clamp": clamp, "events": events, "refused": False, **det}
        if scales == 0 and h >= t1:
            q = int(sh * 0.50); real += q * (t1 - entry); rem -= q; scales = 1
            events.append((hm, f"scale1 {q}@{t1:.4f}"))
            if be_after <= 1: cur = max(cur, entry)
        if scales == 1 and h >= t2:
            q = int(sh * 0.25); real += q * (t2 - entry); rem -= q; scales = 2
            events.append((hm, f"scale2 {q}@{t2:.4f}"))
            if be_after <= 2: cur = max(cur, entry)
        if scales >= 2:
            lows = [m1[x][0] for x in (key - 3, key - 2, key - 1) if x in m1]
            if lows:
                cur = max(cur, min(lows))
        if rem <= 0:
            return {"tk": tk, "date": date, "pnl": round(real, 2), "shares": sh, "clamp": clamp,
                    "events": events, "refused": False, **det}
    c = b[-1][4]
    events.append((b[-1][6], f"tape end @ {c:.4f}"))
    return {"tk": tk, "date": date, "pnl": round(real + rem * (c - entry), 2), "shares": sh,
            "clamp": clamp, "events": events, "refused": False, **det}


def acceptance_run(date, exclude=(), tol_per_trade=12.0, verbose=True):
    """Fable's gate: replay the day's REAL trades (recorded entry/stop/shares, entry_ts_utc) and
    compare to booked P&L. Excludes the excision list (defect trades cannot anchor a simulator).
    PASS = median |delta| within tolerance AND sign agreement on >=70% of trades."""
    rows = [r for r in (json.load(urllib.request.urlopen(f"{U}/api/trades")).get("trades") or [])
            if isinstance(r, dict) and str(r.get("date")) == date]
    out = []
    for r in rows:
        tk = r.get("ticker")
        ts = r.get("entry_ts_utc")
        e, s, sh, p = r.get("entry"), r.get("stop_loss"), r.get("shares"), r.get("pnl")
        if not (tk and ts and e and s and sh) or p is None:
            continue
        hm = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).strftime("%H:%M:%S")
        if (tk, hm[:5]) in exclude:
            continue
        rep = replay(tk, date, e, s, entry_hm=hm, shares=sh)
        if rep is None:
            continue
        out.append((tk, hm, p, rep["pnl"], rep["pnl"] - p))
    if verbose:
        print(f"ACCEPTANCE {date}: {len(out)} real trades replayed")
        for tk, hm, act, sim, d in out:
            print(f"  {hm} {tk:6} booked {act:+8.2f}  replay {sim:+8.2f}  delta {d:+7.2f}")
    if not out:
        return False, out
    deltas = [abs(x[4]) for x in out]
    signs = sum(1 for x in out if (x[2] > 0) == (x[3] > 0) or abs(x[2]) < 5)
    ok = statistics.median(deltas) <= tol_per_trade and signs >= 0.7 * len(out)
    if verbose:
        print(f"  median |delta| ${statistics.median(deltas):.2f} (tol {tol_per_trade})  "
              f"sign-agree {signs}/{len(out)}  ->  {'PASS' if ok else 'FAIL'}")
    return ok, out
