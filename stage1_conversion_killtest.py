#!/usr/bin/env python3
"""#88 STAGE-1 CONVERSION KILL-TEST — why 542/813 arms time out (the 0.7% ride leak).

The verified 7/22 finding: 813 pullback arms -> ~86 triggers (~11%). 542 timeouts die
waiting for a pullback confirmation. This test decomposes each timeout into WHY, from the
1m tape, so the fix targets the real cause instead of a guess.

For every *_pullback_timeout row we pair it with the most recent preceding arm (same ticker),
pull that name's 1m bars for [arm_time, timeout_time] (date-filtered, UTC->ET), and classify:

  (a) NO PULLBACK        window_low stayed > level*(1+EPS): price broke and RAN, never
                         offered the retest. -> pullback-entry is the WRONG LANE here;
                         these want a breakout-continuation entry.
  (b1) PULLBACK + CURL    window low reached level AND a later bar made a higher-low and
       (gate missed)      reclaimed back over level: the retest happened, curled up, and the
                         confirm gate never green-lit it. -> the ACTIONABLE leak (loosen/speed
                         the confirmation).
  (b2) PULLBACK, NO CURL  window low reached level but price kept falling / never reclaimed:
       (correct skip)     no buyers stepped in. NOT a leak — the machine correctly stood aside.

Verdict the test produces: the (a):(b1):(b2) split. Only (b1) is money left on the table by
our own gate. (a) is a missing lane. (b2) is the system working.

CONFOUND (report, do not correct): #81 amnesia (fixed tonight, live Thu) inflated the timeout
count — an arm wiped mid-retest logs as a timeout. Re-run Thursday; the timeout N should drop
and the (b1) share is the honest post-#81 leak.

Run:  python3 stage1_conversion_killtest.py [YYYY-MM-DD]   (default 2026-07-22)
Read-only: pulls dashboard decisions + bars. Writes results to data/killtests/.
"""
import sys, json, urllib.request, collections, datetime, os

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-07-22"
BASE = "https://zestful-intuition-production-b16a.up.railway.app"
EPS = 0.005          # 0.5%: "price reached the level" tolerance
CURL_LOOKAHEAD = 6   # bars after the window-low to look for a higher-low + reclaim

def _get(url, timeout=30):
    return json.load(urllib.request.urlopen(url, timeout=timeout))

def _et_hhmm(iso_or_time):
    """recorded_at is ISO with a -04:00 ET offset already -> take HH:MM directly."""
    s = str(iso_or_time)
    if "T" in s:
        return s[11:16]
    return None

def _bar_et(t):
    """bar 'time' is UTC (…+0000). EDT = UTC-4 in July."""
    hh = int(str(t)[11:13]); mm = str(t)[14:16]
    return "%02d:%s" % ((hh - 4) % 24, mm)

def load_bars(tk):
    try:
        d = _get("%s/api/bars?date=%s&ticker=%s" % (BASE, DAY, tk))
    except Exception as e:
        return None
    b = [x for x in (d.get("bars") or []) if str(x.get("time", "")).startswith(DAY)]
    b.sort(key=lambda x: x.get("time"))
    # attach ET label
    for x in b:
        x["_et"] = _bar_et(x.get("time"))
    return b

def window(bars, t0, t1):
    return [x for x in bars if t0 <= x["_et"] <= t1]

def classify(timeout_row, arm_et, bars):
    level = float(timeout_row.get("level") or 0)
    if level <= 0 or not bars:
        return ("skip_nolevel", {})
    t1 = _et_hhmm(timeout_row.get("recorded_at"))
    t0 = arm_et or ("%02d:%02d" % (max(0, int(t1[:2]) * 60 + int(t1[3:]) - 20) // 60,
                                   (int(t1[:2]) * 60 + int(t1[3:]) - 20) % 60)) if t1 else None
    if not t1:
        return ("skip_notime", {})
    w = window(bars, t0, t1)
    if len(w) < 2:
        return ("skip_nobars", {"n": len(w)})
    lows = [float(x.get("low") or 0) for x in w]
    wlow = min(lows)
    if wlow > level * (1 + EPS):
        return ("a_no_pullback", {"wlow": round(wlow, 4), "level": level})
    # pullback reached the level — did it curl back over with a higher low?
    li = lows.index(wlow)
    reclaim = False
    hl = False
    for j in range(li + 1, min(len(w), li + 1 + CURL_LOOKAHEAD)):
        if float(w[j].get("low") or 0) > wlow:      # a higher low formed
            hl = True
        if float(w[j].get("high") or 0) > level and float(w[j].get("close") or 0) >= level:
            reclaim = True
    if hl and reclaim:
        return ("b1_curl_gate_missed", {"wlow": round(wlow, 4), "level": level})
    return ("b2_no_curl_correct_skip", {"wlow": round(wlow, 4), "level": level})

def main():
    rows = _get("%s/api/decisions_archive?date=%s&limit=8000" % (BASE, DAY)).get("rows") or []
    arms = [r for r in rows if (r.get("status") or "") in ("orb_break_armed", "break_armed")]
    tos  = [r for r in rows if (r.get("status") or "") in ("orb_pullback_timeout", "pullback_timeout")]
    print("arms=%d  timeouts=%d  (day %s)" % (len(arms), len(tos), DAY))

    # index arms by ticker, sorted by time, to find the most-recent-preceding arm
    by_tk = collections.defaultdict(list)
    for a in arms:
        et = _et_hhmm(a.get("recorded_at"))
        if et:
            by_tk[a.get("ticker")].append(et)
    for tk in by_tk:
        by_tk[tk].sort()

    def preceding_arm(tk, t1):
        cand = [e for e in by_tk.get(tk, []) if e <= t1]
        return cand[-1] if cand else None

    bars_cache = {}
    verdict = collections.Counter()
    detail = collections.defaultdict(list)
    for r in tos:
        tk = r.get("ticker"); t1 = _et_hhmm(r.get("recorded_at"))
        if tk not in bars_cache:
            bars_cache[tk] = load_bars(tk)
        arm_et = preceding_arm(tk, t1)
        cls, info = classify(r, arm_et, bars_cache[tk] or [])
        verdict[cls] += 1
        if cls in ("a_no_pullback", "b1_curl_gate_missed", "b2_no_curl_correct_skip"):
            detail[cls].append((tk, t1, info.get("wlow"), info.get("level")))

    print("\n=== STAGE-1 TIMEOUT DECOMPOSITION (n=%d) ===" % len(tos))
    order = ["a_no_pullback", "b1_curl_gate_missed", "b2_no_curl_correct_skip",
             "skip_nolevel", "skip_notime", "skip_nobars"]
    scored = sum(verdict[k] for k in ("a_no_pullback", "b1_curl_gate_missed", "b2_no_curl_correct_skip"))
    for k in order:
        if verdict[k]:
            pct = (100.0 * verdict[k] / scored) if (scored and k.startswith(("a_", "b"))) else None
            print("  %-26s %4d%s" % (k, verdict[k], ("  (%.0f%% of scored)" % pct) if pct is not None else ""))
    print("\n--- b1 (gate missed a real curl — THE actionable leak) sample ---")
    for tk, t1, wl, lv in detail["b1_curl_gate_missed"][:20]:
        print("  %-6s timeout %s  low %s  level %s" % (tk, t1, wl, lv))
    print("\n--- a (no pullback — wanted a continuation lane) sample ---")
    for tk, t1, wl, lv in detail["a_no_pullback"][:12]:
        print("  %-6s timeout %s  low %s  level %s" % (tk, t1, wl, lv))

    os.makedirs("data/killtests", exist_ok=True)
    out = "data/killtests/stage1_conversion_%s.txt" % DAY.replace("-", "")
    with open(out, "w") as f:
        f.write("#88 STAGE-1 CONVERSION KILL-TEST — %s\n" % DAY)
        f.write("arms=%d timeouts=%d scored=%d\n\n" % (len(arms), len(tos), scored))
        for k in order:
            if verdict[k]:
                f.write("%-26s %4d\n" % (k, verdict[k]))
        f.write("\nb1 (actionable — gate missed a curl):\n")
        for tk, t1, wl, lv in detail["b1_curl_gate_missed"]:
            f.write("  %s %s low %s level %s\n" % (tk, t1, wl, lv))
        f.write("\na (no pullback — continuation lane):\n")
        for tk, t1, wl, lv in detail["a_no_pullback"]:
            f.write("  %s %s low %s level %s\n" % (tk, t1, wl, lv))
    print("\nwrote %s" % out)

if __name__ == "__main__":
    main()
