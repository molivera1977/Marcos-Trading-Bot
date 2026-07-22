"""
Vendor bake-off EOD grader (Phase 0, built 2026-07-22) — Numbers With Narrative: full per-row table.

WHAT: for one date, every name captured by BOTH feeds (TICKER~10S from the Webull recorder,
TICKER~ALP10S from alpaca_capture) gets its cumulative volume compared against the OFFICIAL
daily volume (/api/daily = the truth source). Completeness ratio per feed answers the ONLY
Phase-0 question: which vendor actually delivers the tape? Also verifies 10s bar counts per
name per feed (a feed can match volume yet deliver half the bars via blackout lumping).

USAGE: python vendor_test_grade.py [YYYY-MM-DD]   (default: today ET)
Read-only: GETs against the dashboard archive + /api/daily. No secrets needed. Gentle on
/api/daily per its stated contract (one ticker per call, client paces).
"""
import sys, time, statistics
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    EASTERN = ZoneInfo("America/New_York")
except Exception:
    EASTERN = timezone(timedelta(hours=-4))

import requests

BASE = "https://zestful-intuition-production-b16a.up.railway.app"

def get(path, timeout=25):
    try:
        r = requests.get(BASE + path, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("  fetch failed %s: %s" % (path, e))
    return None

def series_stats(date, name):
    """(cum_volume, bar_count) for one archived series; (None, 0) if absent."""
    d = get("/api/bars?date=%s&ticker=%s" % (date, name))
    bars = (d or {}).get("bars")
    if not isinstance(bars, list):
        return None, 0
    cum = 0.0
    for b in bars:
        try: cum += float(b.get("volume") or 0)
        except Exception: pass
    return cum, len(bars)

def official_daily(ticker, date):
    d = get("/api/daily?ticker=%s&count=10" % ticker)
    for b in (d or {}).get("bars", []):
        if b.get("date") == date:
            try: return float(b.get("volume") or 0)
            except Exception: return None
    return None

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(EASTERN).strftime("%Y-%m-%d")
    arch = get("/api/bars") or {}
    names = arch.get("archived", {}).get(date, [])
    # suffix split — note "X~ALP10S" does NOT endswith "~10S" (tilde guard), so no cross-match
    webull = {n[:-4].upper() for n in names if n.upper().endswith("~10S") and not n.upper().startswith("ZZ")}
    alpaca = {n[:-7].upper() for n in names if n.upper().endswith("~ALP10S")}
    both = sorted(webull & alpaca)
    print("vendor_test_grade %s — archive: %d webull(~10S) names, %d alpaca(~ALP10S) names, %d in BOTH"
          % (date, len(webull), len(alpaca), len(both)))
    if webull - alpaca: print("  webull-only: %s" % sorted(webull - alpaca))
    if alpaca - webull: print("  alpaca-only: %s" % sorted(alpaca - webull))
    if not both:
        print("nothing to grade — is alpaca_capture deployed and persisting?")
        sys.exit(0)

    rows = []
    for t in both:
        wcum, wbars = series_stats(date, "%s~10S" % t)
        acum, abars = series_stats(date, "%s~ALP10S" % t)
        off = official_daily(t, date)
        wp = (wcum / off * 100.0) if (off and wcum is not None) else None
        ap = (acum / off * 100.0) if (off and acum is not None) else None
        rows.append((t, wcum, acum, off, wp, ap, wbars, abars))
        time.sleep(0.3)                     # /api/daily contract: one ticker per call, paced

    fmt = "%-8s %14s %14s %14s %9s %9s %9s %9s"
    print()
    print(fmt % ("name", "webull_cum", "alpaca_cum", "official", "webull_%", "alpaca_%", "wb_bars", "alp_bars"))
    def n(x): return "%.0f" % x if x is not None else "-"
    def p(x): return "%.1f%%" % x if x is not None else "-"
    for t, wc, ac, off, wp, ap, wb, ab in rows:
        print(fmt % (t, n(wc), n(ac), n(off), p(wp), p(ap), wb, ab))

    wps = [wp for _, _, _, _, wp, _, _, _ in rows if wp is not None]
    aps = [ap for _, _, _, _, _, ap, _, _ in rows if ap is not None]
    print()
    if wps: print("webull completeness: median %.1f%%  mean %.1f%%  (n=%d)"
                  % (statistics.median(wps), statistics.mean(wps), len(wps)))
    if aps: print("alpaca completeness: median %.1f%%  mean %.1f%%  (n=%d)"
                  % (statistics.median(aps), statistics.mean(aps), len(aps)))
    low = [(t, ap) for t, _, _, _, _, ap, _, _ in rows if ap is not None and ap < 98.0]
    if low:
        print("alpaca <98%% (%d): %s" % (len(low), ", ".join("%s=%.1f%%" % (t, a) for t, a in low)))
    else:
        print("alpaca <98%: none")
    # bar-count sanity: same session, same 10s buckets — big deltas = blackouts, not volume math
    thin = [(t, wb, ab) for t, _, _, _, _, _, wb, ab in rows if wb and ab and min(wb, ab) < 0.5 * max(wb, ab)]
    if thin:
        print("bar-count mismatch >2x (%d): %s" % (len(thin), ", ".join("%s wb=%d alp=%d" % r for r in thin)))
    print("\nREMINDER: pull the day's disconnect counts from BOTH services' logs "
          "(grep 'ALP-health' for alpaca, kicks for recorder) — completeness without the "
          "kick count is half the evidence. IEX (free) is a SUBSET of the tape; expect "
          "alpaca_% well under 100 until the Phase-1 SIP test.")

if __name__ == "__main__":
    main()
