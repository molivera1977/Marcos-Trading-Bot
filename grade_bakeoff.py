#!/usr/bin/env python3
"""Grade newcomer_vision_reader --dry --out files against a day's REAL outcomes (levels-only,
break-and-hold — same grading as the validated 30/31 blind tests). Compare models side-by-side.

USAGE:
  python3 grade_bakeoff.py 2026-07-17 /tmp/reads_s46.json [/tmp/reads_s5.json ...]

Each reads file = {TICKER: read-json} from `newcomer_vision_reader.py --dry --out <file>`
run with NEWCOMER_DAY=<day> (charts rendered through the PRIOR day; graded on <day>'s bars).

GRADING (daily-bar proxy, matches grade_batch3):
  level not reached (H < break)          -> no trade          (costs nothing)
  broke, close < level (tag+reject)      -> no trade          (hold filter rejected it)
  broke + held (C >= level):
      ret_close >= +8%                   -> CATCH win
      ret_close <= -4%                   -> BAD (knife broke+held)
      else                               -> scratch (flat)
  parabolic / rejected read              -> vetoed / unarmed  (no trade)
ret_close is measured FROM THE LEVEL (entry proxy), not from open.
"""
import os, sys, json, time, urllib.request

U = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")

def _get(url, timeout=45):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())

def day_bar(ticker, day, cache={}):
    if ticker in cache: return cache[ticker]
    for attempt in range(3):                   # /api/daily is Webull-LIVE → 429s need retry+backoff
        try:
            bars = _get(f"{U}/api/daily?ticker={ticker}&count=30").get("bars") or []
            row = next((b for b in bars if b.get("date") == day), None)
            cache[ticker] = row and {"o": float(row["open"]), "h": float(row["high"]), "c": float(row["close"])}
            break
        except Exception as e:
            if attempt == 2:
                print(f"  [bars] {ticker}: {e} (3 attempts)"); cache[ticker] = None
            else:
                time.sleep(6.0)
    time.sleep(1.5)                                    # pace the shared quota
    return cache[ticker]

def grade_file(path, day):
    reads = json.load(open(path))
    rows, tally = [], {"CATCH": 0, "BAD": 0, "scratch": 0, "no_trade": 0, "vetoed": 0, "no_bar": 0}
    for tk, rd in sorted(reads.items()):
        setup = str(rd.get("setup", "")).lower()
        accepted = rd.get("_accepted", True)
        brk = rd.get("break_level")
        if setup == "parabolic" or not accepted or not brk:
            tally["vetoed"] += 1
            rows.append((tk, "-", "vetoed/unarmed", None)); continue
        brk = float(brk)
        b = day_bar(tk, day)
        if not b:
            tally["no_bar"] += 1
            rows.append((tk, brk, "no bar data", None)); continue
        ret = (b["c"] - brk) / brk * 100
        if b["h"] < brk:
            g = "no trade (level not reached)"; tally["no_trade"] += 1
        elif b["c"] < brk:
            g = "no trade (tag+reject)"; tally["no_trade"] += 1
        elif ret >= 8:
            g = f"CATCH win  ({ret:+.0f}%)"; tally["CATCH"] += 1
        elif ret <= -4:
            g = f"BAD broke+held ({ret:+.0f}%)"; tally["BAD"] += 1
        else:
            g = f"scratch(flat) ({ret:+.0f}%)"; tally["scratch"] += 1
        rows.append((tk, brk, g, b))
    return rows, tally

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    day, files = sys.argv[1], sys.argv[2:]
    results = {}
    for f in files:
        name = os.path.basename(f)
        print(f"\n===== {name}  (graded on {day}) =====")
        rows, tally = grade_file(f, day)
        for tk, brk, g, b in rows:
            ohc = f"{b['o']:.2f}/{b['h']:.2f}/{b['c']:.2f}" if b else "-"
            print(f"  {tk:<6} lvl={str(brk):<8} {ohc:<20} {g}")
        print(f"  TOTALS: {tally}")
        results[name] = tally
    if len(results) > 1:
        print("\n===== SIDE-BY-SIDE =====")
        print(f"  {'file':<24} CATCH  BAD  scratch  no_trade  vetoed")
        for n, t in results.items():
            print(f"  {n:<24} {t['CATCH']:>5} {t['BAD']:>4} {t['scratch']:>8} {t['no_trade']:>9} {t['vetoed']:>7}")
        print("  Pick the model with the most CATCH wins and fewest BAD broke+held.")

if __name__ == "__main__":
    main()
