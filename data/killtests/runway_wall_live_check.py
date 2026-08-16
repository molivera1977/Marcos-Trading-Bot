#!/usr/bin/env python3
"""RUNWAY-WALL LIVE PROOF — one command (D4, scripted 8/16; Monday 8/17 = first post-fix full day).

The wall (marcos_trading_bot.py _marked_runway, RUNWAY_WALL=1) writes NO distinct row: it (a) drops
map targets the session already traded above ("spent rungs demoted") and (b) inserts the session
high itself as the nearest road end when it stands >0.5% above entry. Its only production trace
is the `target` stamped on runway_pass / runway_reject rows. This check reconstructs, per row,
the session high at row-time from the archived bars (~ALP10S -> ~10S -> 1-min) and classifies:

  WALL_TARGET   target == session-high (|d|<=0.05%) -> the wall was inserted as the road end
  DEMOTED       a stored map target sits in (entry, session-high] but was NOT the stamped target
                -> a spent rung was skipped
  NO_EFFECT     target above the session high and no map target was skipped (wall had nothing to do)
  NO_BARS       no archived bars for the name at that time (ungradable)
PROVEN for the day = >=1 WALL_TARGET or DEMOTED row (post-fix). Session-high = the wall's own window (last 720 10s bars ~2h). Map = /api/kev_watchlist levels
(sheet + vision_shadow targets; the bot's _effective_map may also carry auto-map targets — a
DEMOTED miss is possible, a DEMOTED hit is real). Also flags SUSPECT rows: target <= session high
(the wall failed to cap — the 8/7 "150.1R to a ghost" class), the failure condition.

Usage: python3 data/killtests/runway_wall_live_check.py 2026-08-17 [HH:MM since]
"""
import json, sys, datetime, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(ET).strftime("%Y-%m-%d")
SINCE = sys.argv[2] if len(sys.argv) > 2 else "00:00"   # HH:MM ET — skip pre-deploy rows (8/14: fix live ~12:45)


def get(url, t=90):
    try:
        return json.load(urllib.request.urlopen(url, timeout=t))
    except Exception:
        return {}


def iso(s):
    return datetime.datetime.fromisoformat(str(s).replace("+0000", "+00:00").replace("Z", "+00:00")).astimezone(ET)


def bars(tk):
    for sfx in ("~ALP10S", "~10S", ""):
        d = get(f"{U}/api/bars?date={DAY}&ticker={tk}{sfx}")
        b = d.get("bars") or []
        b = [x for x in b if isinstance(x, dict) and x.get("time")]
        if b:
            return sfx or "1min", b
    return None, []


def sess_high(B, until, n=720):
    """The wall's own high: _curl_feed(ticker, n=720) = the LAST 720 10s bars (~2h) before row time
    (NOT the full-session high — a rung spent 3h ago is outside the wall's window by design/limit).
    Falls back to the same count on 1-min bars if no 10s feed (coarser; noted in the src column)."""
    todays = [x for x in B if iso(x["time"]).strftime("%Y-%m-%d") == DAY and iso(x["time"]) <= until]
    hi = 0.0
    for x in todays[-n:]:
        try:
            hi = max(hi, float(x.get("high") or x.get("h") or 0))
        except (TypeError, ValueError):
            pass
    return hi


def main():
    d = get(f"{U}/api/decisions_archive?date={DAY}&status=runway_pass,runway_reject&limit=5000")
    rows = d.get("rows") or []
    if not rows:
        d = get(f"{U}/api/decisions?date={DAY}&status=runway_pass&limit=500")
        rows = (d.get("rows") or []) + (get(f"{U}/api/decisions?date={DAY}&status=runway_reject&limit=500").get("rows") or [])
    lv = get(f"{U}/api/kev_watchlist?date={DAY}").get("levels") or {}
    print(f"{DAY}: {len(rows)} runway rows")
    cache, tally = {}, {"WALL_TARGET": 0, "DEMOTED": 0, "NO_EFFECT": 0, "NO_BARS": 0, "SUSPECT": 0}
    rows = [r for r in rows if not r.get("recorded_at") or iso(r["recorded_at"]).strftime("%H:%M") >= SINCE]
    print(f"rows since {SINCE} ET: {len(rows)}")
    for r in rows:
        tk = r.get("ticker"); px = float(r.get("price") or 0); tgt = r.get("target")
        if tk not in cache:
            cache[tk] = bars(tk)
        src, B = cache[tk]
        when = iso(r["recorded_at"]) if r.get("recorded_at") else None
        if not B or not when or not tgt:
            tally["NO_BARS"] += 1
            print(f"  {r['time']} {tk:6} {r['status']:14} tgt={tgt} NO_BARS/NO_TS"); continue
        whi = sess_high(B, when)
        rec = lv.get(tk) or {}
        mt = set()
        for src_t in (rec.get("targets") or []), ((rec.get("vision_shadow") or {}).get("targets") or []):
            for x in src_t:
                try: mt.add(float(x))
                except (TypeError, ValueError): pass
        skipped = sorted(t for t in mt if px < t <= whi and t < float(tgt))
        cls = ("WALL_TARGET" if whi > 0 and abs(float(tgt) - whi) / whi <= 0.0005
               else "DEMOTED" if skipped else "NO_EFFECT")
        sus = whi > 0 and float(tgt) < whi * 0.9995 and cls != "WALL_TARGET"
        if sus: tally["SUSPECT"] += 1
        tally[cls] += 1
        print(f"  {r['time']} {tk:6} {r['status']:14} px={px} tgt={tgt} sess_hi@t={whi:.4f} ({src}) "
              f"map_tgts={sorted(mt)[:6]} -> {cls}{'  !!SUSPECT target<=session high' if sus else ''}"
              f"{'  skipped=' + str(skipped) if skipped else ''}")
    print("TALLY:", tally)
    proven = tally["WALL_TARGET"] + tally["DEMOTED"] > 0
    print("VERDICT:", ("PROVEN — wall shaped >=1 live runway target" if proven else
                       "NOT YET — no wall-shaped target today (needs a name whose session high sits above entry / above a rung)")
          + ("; SUSPECT rows present = wall FAILED to cap (investigate)" if tally["SUSPECT"] else ""))
    return 0 if proven and not tally["SUSPECT"] else 1


if __name__ == "__main__":
    sys.exit(main())
