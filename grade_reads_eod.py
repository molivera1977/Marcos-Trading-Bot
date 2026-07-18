#!/usr/bin/env python3
"""EOD READING SCORECARD (Marcos 7/18: "grade out our reading capabilities").

Grades the day's stored levels against what actually traded:
  1. THE KEV EXAM — sheet names carry Kev's level (canonical) + our 'vision_shadow' read of the
     same chart. Compare: level distance, and how EACH level would have graded on the day
     (break-and-hold, from-the-level returns). Kev is the Bible; the distance IS our grade.
  2. NEWCOMER FORWARD GRADE — every vision-posted newcomer level graded on the day's outcome
     (the standing bake-off, accumulating daily).
Appends one JSON line per run to the iCloud track record so capability accrues over weeks.

USAGE:  python3 grade_reads_eod.py [YYYY-MM-DD]     (default: today ET)
"""
import os, sys, json, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
U = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")
TRACK = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/read_grades.jsonl")

def _get(url, timeout=45):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())

def day_bar(ticker, day, cache={}):
    if ticker in cache: return cache[ticker]
    try:
        bars = _get(f"{U}/api/daily?ticker={ticker}&count=30").get("bars") or []
        row = next((b for b in bars if b.get("date") == day), None)
        cache[ticker] = row and {"o": float(row["open"]), "h": float(row["high"]), "c": float(row["close"])}
    except Exception as e:
        print(f"  [bars] {ticker}: {e}"); cache[ticker] = None
    time.sleep(1.0)
    return cache[ticker]

def classify(level, b):
    """Break-and-hold grade of one level on one day's bar (same rules as grade_bakeoff)."""
    if not b or not level: return "-", None
    try: level = float(level)
    except (TypeError, ValueError): return "-", None
    if level <= 0: return "-", None
    ret = (b["c"] - level) / level * 100
    if b["h"] < level:  return "no-trade (never reached)", ret
    if b["c"] < level:  return "no-trade (tag+reject)", ret
    if ret >= 8:        return f"CATCH +{ret:.0f}%", ret
    if ret <= -4:       return f"BAD broke+held {ret:.0f}%", ret
    return f"scratch {ret:+.0f}%", ret

def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.now(ET).strftime("%Y-%m-%d")
    lv = _get(f"{U}/api/kev_watchlist?date={day}").get("levels") or {}
    sheet   = {t: d for t, d in lv.items() if isinstance(d, dict) and not t.startswith("_") and d.get("src") != "vision"}
    vision  = {t: d for t, d in lv.items() if isinstance(d, dict) and d.get("src") == "vision"}

    print(f"===== THE KEV EXAM — {day} ({len(sheet)} sheet names) =====")
    exam = []
    for tk, d in sorted(sheet.items()):
        kev = d.get("break"); sh = (d.get("vision_shadow") or {}).get("break")
        b = day_bar(tk, day)
        kg, _ = classify(kev, b); og, _ = classify(sh, b)
        dist = None
        try: dist = round(abs(float(sh) - float(kev)) / float(kev) * 100, 1)
        except (TypeError, ValueError, ZeroDivisionError): pass
        agree = dist is not None and dist <= 2.0
        exam.append({"ticker": tk, "kev": kev, "ours": sh, "dist_pct": dist,
                     "kev_grade": kg, "our_grade": og, "agree2pct": agree})
        print(f"  {tk:<6} Kev={str(kev):<8} ours={str(sh):<8} Δ{str(dist)+'%' if dist is not None else ' n/a':<7}"
              f" | Kev: {kg:<26} | ours: {og}")
    n_sh = sum(1 for e in exam if e["ours"] is not None)
    n_ag = sum(1 for e in exam if e["agree2pct"])
    same = sum(1 for e in exam if e["ours"] is not None and e["kev_grade"].split()[0] == e["our_grade"].split()[0])
    print(f"  EXAM: {n_sh}/{len(exam)} shadow-read | within-2% of Kev: {n_ag}/{n_sh or 1} | same outcome-class: {same}/{n_sh or 1}")

    print(f"\n===== NEWCOMER FORWARD GRADE — {len(vision)} vision levels =====")
    tal = {"CATCH": 0, "BAD": 0, "scratch": 0, "no-trade": 0, "veto": 0}
    for tk, d in sorted(vision.items()):
        note = str(d.get("note") or "")
        if "do-not-trade" in note.lower():
            tal["veto"] += 1
            print(f"  {tk:<6} vetoed (parabolic)"); continue
        g, _ = classify(d.get("break"), day_bar(tk, day))
        key = g.split()[0].rstrip("-").replace("no-trade", "no-trade")
        for k in tal:
            if g.startswith(k) or (k == "no-trade" and g.startswith("no-trade")): tal[k] += 1; break
        print(f"  {tk:<6} lvl={str(d.get('break')):<8} {g}")
    print(f"  TALLY: {tal}")

    rec = {"day": day, "exam": exam, "exam_summary": {"shadow_read": n_sh, "sheet": len(exam),
           "within2pct": n_ag, "same_class": same}, "newcomer_tally": tal,
           "graded_at": dt.datetime.now(ET).isoformat()}
    try:
        with open(TRACK, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"\nappended → {TRACK.split('/')[-1]}")
    except Exception as e:
        print(f"\n[track] append failed: {e}")

if __name__ == "__main__":
    main()
