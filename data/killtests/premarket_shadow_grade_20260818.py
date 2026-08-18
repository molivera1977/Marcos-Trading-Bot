#!/usr/bin/env python3
"""
GRADE THE PREMARKET SHADOW BOOK — 8/18

Marcos: "what's the point if we dont collect any data."

We DO collect it. `premarket_shadow_entry` rows have been written every session since the
pre-open choke gate went in: 544 rows over the 10 sessions sampled (8/04-8/17), EVERY ONE
carrying ticker + entry price + stop + timestamp. Nobody has ever graded them. Collecting
without grading is the same as not collecting — this closes that.

WHAT A SHADOW ROW IS
  A lane fired in premarket, passed its own detector, and was then refused conversion PURELY
  because it is not in PRE_LANES. The row records the trade the bot WOULD have taken. It is a
  clean counterfactual: no gate opinion, no lookahead, just "this fired here with this stop."

METHOD
  Bars: the universe 10s SIP cache (data/universe/bars10s/<date>_<sym>.json) — the same cache
  the sequence studies use. Verified to carry premarket: 50,474 pre-09:30 bars across the
  Aug-10..19 files, 60 of 69 name-days with pre-09:30 coverage.

  Exits: E3, ported line-for-line from data/killtests/edge_stresstest_F_20260815.py::sim_var
  (VAR["E3"] = bank=0.50, tgt=0.10, trail="off10", be=None). This is a PORT, not an import —
  the F chain loads its own cache and date window, which would fight this one. The rules are
  reproduced exactly and listed here so the port is checkable:
    * entry filled at sig_px * (1 + 0.01)   — the -1% chase slip, against us
    * stop-first, INTRABAR: if bar low <= stop, exit at stop * (1 - 0.005)
    * bank 1/2 when bar HIGH >= entry*1.10, filled exactly at the target (resting limit)
    * after banking, trail the rest: exit when a bar CLOSE < run_high * 0.90, at close*(1-0.005)
    * run_high updated bar-by-bar FROM THE ENTRY FORWARD — no lookahead
    * no breakeven move (be=None for E3)
  Differences from F, both forced by the session and both stated rather than hidden:
    * FLATTEN AT 09:25 ET, not 19:59Z — the premarket session rule. A shadow trade that
      survives to the bell is closed at the 09:25 bar close with the same -0.5% market slip.
    * no halt-gap rule: the gaps table is an F-chain artifact this cache does not carry.
      Premarket halts exist, so this is a KNOWN OPTIMISM in the result. Flagged, not buried.

  Sizing: the REAL chain (feedback_dollars_not_r), not a flat clip —
    shares = RISK_PER_TRADE(30) / risk_per_share, then capped by
             MAX_TRADE_DOLLARS(1000) notional, then by MAX_POS_VOL_PCT(5%) of the
             trailing 1-minute volume at the entry bar.
  A row whose stop is >= its price is DISCARDED (not gradable), and counted.

PRE-REGISTERED FAILURE CONDITIONS (written before the run)
  * If total dollars are negative, premarket stays shut and this is the evidence.
  * If positive but driven by one name/day (>60% of the total), it is NOT a result — report
    it as concentrated and refuse the conclusion.
  * If N gradable < 100, underpowered; report as directional only.
  * This measures the SHADOWED lanes only (ma_pullback, flat_top, etc). It says nothing about
    hidden_entry/vwap_reclaim, the two lanes that ARE whitelisted for PRE but are switched off.

NO RECOMMENDATION IS MADE HERE. Numbers only; Marcos decides.
"""
import collections
import datetime
import glob
import json
import os
import sys
import urllib.request
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
# NOTE: this file lives at <repo>/data/killtests/, so ROOT needs THREE dirnames. The first
# version used two, silently pointed CACHE at data/data/universe/bars10s, and reported
# "no_bars_in_cache" for 543 of 544 rows — a path bug wearing the costume of a data gap.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
assert os.path.isdir(os.path.join(ROOT, "data", "universe", "bars10s")), \
    "bars cache not found at %s — refuse to report an empty result from a bad path" % ROOT
CACHE = os.path.join(ROOT, "data", "universe", "bars10s")
DASH = "https://zestful-intuition-production-b16a.up.railway.app"

ENTRY_SLIP = 0.01
MKT = 0.005
BANK_FRAC = 0.50
BANK_TGT = 0.10
TRAIL = 0.90
RISK_PER_TRADE = 30.0
MAX_TRADE_DOLLARS = 1000.0
MAX_POS_VOL_PCT = 0.05
PRE_FLATTEN = "09:25"

DAYS = ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10",
        "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17"]


def et_of(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)


def load_bars(date, sym):
    p = os.path.join(CACHE, f"{date}_{sym}.json")
    if not os.path.exists(p):
        return None
    try:
        b = json.load(open(p)).get("bars") or []
    except Exception:
        return None
    out = []
    for x in b:
        t = et_of(x["time"])
        out.append({"t": t, "hm": t.strftime("%H:%M"), "o": float(x["open"]),
                    "h": float(x["high"]), "l": float(x["low"]),
                    "c": float(x["close"]), "v": float(x.get("volume") or 0)})
    return out


def fetch_rows(day):
    u = f"{DASH}/api/decisions_archive?date={day}&status=premarket_shadow_entry&limit=50000"
    return json.load(urllib.request.urlopen(u, timeout=30)).get("rows") or []


def entry_index(bars, hhmm):
    """First bar at or after the fire's HH:MM. The fire happened DURING that minute, so the
    trade can only be taken from that bar forward — never before it."""
    for i, b in enumerate(bars):
        if b["hm"] >= hhmm:
            return i
    return None


def size_it(bars, i, entry_px, rps):
    shares = RISK_PER_TRADE / rps
    shares = min(shares, MAX_TRADE_DOLLARS / entry_px)
    # 5% of the trailing 1-minute volume (six 10s bars) at the entry
    vol1m = sum(b["v"] for b in bars[max(0, i - 6):i]) or 0.0
    if vol1m > 0:
        shares = min(shares, vol1m * MAX_POS_VOL_PCT)
    return max(0.0, shares)


def sim_e3(bars, i0, sig_px, stop):
    """E3, ported from edge_stresstest_F::sim_var. Returns (pnl_per_share_weighted, why, i)."""
    entry_px = sig_px * (1 + ENTRY_SLIP)
    if stop >= entry_px:
        return None
    sh = 1.0                      # per-share; caller scales by size
    rem = sh
    pnl = 0.0
    scaled = False
    bank_sh = sh * BANK_FRAC
    target = entry_px * (1 + BANK_TGT)
    run_hi = entry_px
    for i in range(i0 + 1, len(bars)):
        b = bars[i]
        if b["hm"] >= PRE_FLATTEN:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            return pnl, "flatten_0925", i
        if b["l"] <= stop:                       # stop first — tie against the trade
            px = stop * (1 - MKT); pnl += rem * (px - entry_px)
            return pnl, "stop", i
        if not scaled and b["h"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            continue
        run_hi = max(run_hi, b["h"])
        if scaled and b["c"] < run_hi * TRAIL:
            px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
            return pnl, "trail", i
    b = bars[-1]
    px = b["c"] * (1 - MKT); pnl += rem * (px - entry_px)
    return pnl, "eod", len(bars) - 1


def main():
    rows = []
    for d in DAYS:
        try:
            rows += fetch_rows(d)
        except Exception as e:
            print(f"  {d}: FETCH FAILED {e}")
    print(f"shadow rows fetched: {len(rows)} over {len(DAYS)} sessions\n")

    res = []
    skipped = collections.Counter()
    for r in rows:
        sym = str(r.get("ticker") or "").upper()
        day = str(r.get("date") or "")
        px = r.get("price"); stop = r.get("stop")
        hm = str(r.get("time_hm") or "")[:5]
        if not (sym and day and px and stop and hm):
            skipped["missing_field"] += 1; continue
        px = float(px); stop = float(stop)
        if stop >= px:
            skipped["stop_above_entry"] += 1; continue
        bars = load_bars(day, sym)
        if not bars:
            skipped["no_bars_in_cache"] += 1; continue
        i0 = entry_index(bars, hm)
        if i0 is None or i0 >= len(bars) - 2:
            skipped["fire_after_last_bar"] += 1; continue
        if bars[i0]["hm"] >= PRE_FLATTEN:
            skipped["fired_after_0925"] += 1; continue
        out = sim_e3(bars, i0, px, stop)
        if out is None:
            skipped["stop_above_filled_entry"] += 1; continue
        pps, why, xi = out
        entry_px = px * (1 + ENTRY_SLIP)
        shares = size_it(bars, i0, entry_px, entry_px - stop)
        if shares <= 0:
            skipped["zero_size"] += 1; continue
        res.append({"sym": sym, "date": day, "lane": r.get("entry_type"), "hm": hm,
                    "pnl": pps * shares, "why": why, "shares": shares,
                    "entry": entry_px, "stop": stop})

    print("SKIPPED:", dict(skipped) or "none")
    if not res:
        print("\nNOTHING GRADABLE — cannot report a result."); return 1

    tot = sum(x["pnl"] for x in res)
    wins = [x for x in res if x["pnl"] > 0]
    print(f"\n{'='*72}\nPREMARKET SHADOW BOOK — E3 exits, real sizing, 09:25 flatten\n{'='*72}")
    print(f"  gradable trades : {len(res)}")
    print(f"  TOTAL           : ${tot:+,.2f}")
    print(f"  per trade       : ${tot/len(res):+,.2f}")
    print(f"  win rate        : {len(wins)}/{len(res)} ({len(wins)/len(res)*100:.0f}%)")

    byday = collections.defaultdict(float)
    bylane = collections.defaultdict(lambda: [0, 0.0])
    byname = collections.defaultdict(float)
    for x in res:
        byday[x["date"]] += x["pnl"]
        bylane[x["lane"]][0] += 1; bylane[x["lane"]][1] += x["pnl"]
        byname[(x["date"], x["sym"])] += x["pnl"]
    green = sum(1 for v in byday.values() if v > 0)
    print(f"  green days      : {green}/{len(byday)}")
    print(f"\n  by day:")
    for d in sorted(byday):
        print(f"    {d}  ${byday[d]:+9.2f}")
    print(f"\n  by lane:")
    for l, (n, p) in sorted(bylane.items(), key=lambda x: -x[1][1]):
        print(f"    {str(l):16s} n={n:4d}  ${p:+9.2f}  (${p/n:+7.2f}/tr)")
    print(f"\n  exits: {dict(collections.Counter(x['why'] for x in res))}")

    top = sorted(byname.items(), key=lambda x: -abs(x[1]))[:5]
    print(f"\n  biggest single name-days:")
    for (d, s), p in top:
        print(f"    {d} {s:6s} ${p:+9.2f}  ({abs(p)/abs(tot)*100 if tot else 0:.0f}% of |total|)")

    # PRE-REGISTERED FAILURE CONDITIONS
    print(f"\n{'='*72}\nPRE-REGISTERED CHECKS\n{'='*72}")
    conc = abs(top[0][1]) / abs(tot) if tot else 1.0
    print(f"  N >= 100                     : {'PASS' if len(res)>=100 else 'FAIL — underpowered, directional only'} (n={len(res)})")
    print(f"  total dollars positive       : {'PASS' if tot>0 else 'FAIL — premarket stays shut on this evidence'} (${tot:+,.2f})")
    print(f"  not concentrated (<60% one)  : {'PASS' if conc<0.60 else 'FAIL — one name-day carries it; NO conclusion'} ({conc*100:.0f}%)")
    print("\n  KNOWN OPTIMISM: no halt-gap rule (this cache carries no gaps table), so a "
          "premarket halt that gapped through a stop is modelled as a clean stop fill.")
    print("  SCOPE: shadowed lanes only. Says NOTHING about hidden_entry / vwap_reclaim, the "
          "two lanes whitelisted for PRE but currently switched off.")
    print("\nNo recommendation. Numbers only.")

    json.dump(res, open(os.path.join(ROOT, "data", "killtests",
              "premarket_shadow_grade_20260818_out.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
