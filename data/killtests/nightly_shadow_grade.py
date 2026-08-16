#!/usr/bin/env python3
"""NIGHTLY SHADOW GRADER — the E3 OOS wall's daily brick (built 8/14, wall starts Mon 8/17).

Evidence chain: edge_stresstest_F_20260815.md — E3 (bank 1/2 at +10%, trail rest
10%-off-high closes-through) PASSED 5/5 and is NOMINATED for a >=5-day out-of-sample
shadow wall. This script runs nightly at 23:00 ET from launchd
(com.marcos.tradingbot.shadowgrade.plist, after the 22:45 book verifier): pulls the
day's shadow rows (grinder_shadow_fire + flat_top_observe_only + v2_shadow_fire) from
the decisions archive, pulls the day's 10s bars per name (union of both feeds, the
verified-book standard), simulates every fire through the E3 exit model bar-by-bar
with NO lookahead, and appends ONE line per day to data/history/OOS_WALL.md.

E3 model (per stress-F method notes): chase entry = signal price +1% (the -1% entry
slip), $500 fractional; bar order = EOD flatten -> stop -> bank(continue) -> run-high
update -> trail; stop-first on ties; bank 1/2 fills at the +10% limit EXACTLY; every
market exit (stop / trail / flatten) fills at -0.5%; run_high starts at ENTRY and
updates from post-entry bar highs only; trail fires on close < 0.90*run_high;
NO breakeven. E3 portfolio line = grinder + flat_top IN-WINDOW (9:30-10:30 ET), the
nominated config; v2 is graded as its own lane on the same page. Haltgap stage
omitted (no halt feed here) — disclosed, optimistic on halt days.
"""
import json, urllib.request, pathlib, datetime, sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = ZoneInfo("America/New_York")
DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(ET).strftime("%Y-%m-%d")
POS, CHASE, BANK_PCT, TRAIL, SLIP = 500.0, 1.01, 1.10, 0.90, 0.995
WALL = ROOT / "data/history/OOS_WALL.md"


def iso(s):
    return datetime.datetime.fromisoformat(
        str(s).replace("+0000", "+00:00").replace("Z", "+00:00")).astimezone(ET)


def get(url, t=90):
    return json.load(urllib.request.urlopen(url, timeout=t))


def bars(tk):
    """Union of both 10s feeds (verified-book standard), deduped by timestamp, time-ordered."""
    seen = {}
    for sfx in ("~10S", "~ALP10S"):
        try:
            for b in (get(f"{U}/api/bars?ticker={tk}{sfx}&date={DAY}", 30).get("bars") or []):
                if b.get("time") and b["time"] not in seen:
                    seen[b["time"]] = b
        except Exception:
            pass
    return sorted(seen.values(), key=lambda b: iso(b["time"]))


def sim_e3(B, t0, sig_px, stop, flatten_hm=959):
    """E3 exit sim, no lookahead: only bars strictly after the fire timestamp. Returns $ P&L
    (or None = ungradable: degenerate stop / no post-fire bars)."""
    entry = sig_px * CHASE
    if not (stop and 0 < stop < entry):
        return None
    sh = POS / entry
    rem, banked, pnl, run_hi, last_c = sh, False, 0.0, entry, None
    for b in B:
        if iso(b["time"]) <= t0:
            continue
        o, h, l, c = (float(b.get(k) or 0) for k in ("open", "high", "low", "close"))
        if c <= 0:
            continue
        last_c = c
        et = iso(b["time"])
        if et.hour * 60 + et.minute >= flatten_hm:      # 15:59 ET flatten (PRE fires: 09:25)
            return pnl + rem * (c * SLIP - entry)
        if l <= stop:                                   # stop-first, market exit slip
            return pnl + rem * (stop * SLIP - entry)
        if not banked and h >= entry * BANK_PCT:        # bank 1/2 at the limit exactly
            pnl += (sh / 2.0) * (entry * (BANK_PCT - 1.0))
            rem -= sh / 2.0
            banked = True
            continue                                    # bank consumes the bar (engine order)
        run_hi = max(run_hi, h)                         # post-entry highs only
        if c < TRAIL * run_hi:                          # closes-through off-high trail
            return pnl + rem * (c * SLIP - entry)
    if last_c is None:
        return None                                     # no post-fire bars = ungradable
    return pnl + rem * (last_c * SLIP - entry)          # tape ended: flatten at last close


def main():
    d = get(f"{U}/api/decisions_archive?date={DAY}"
            "&status=grinder_shadow_fire,flat_top_observe_only,v2_shadow_fire,"
            "bandpass_shadow_fire,prevwap_shadow_fire&limit=50000")
    rows = d.get("rows") or []
    lanes = {"grinder": [], "flat_top": [], "flat_top_oow": [], "v2": [], "bandpass": [], "bandpass_oow": [], "prevwap": []}
    for r in rows:
        st = r.get("status")
        try:
            t0 = iso(r["recorded_at"])
        except Exception:
            continue
        hm = t0.hour * 60 + t0.minute
        stop = r.get("would_stop") if st != "flat_top_observe_only" else r.get("stop")
        rec = (r.get("ticker"), t0, float(r.get("price") or 0), float(stop or 0))
        if st == "grinder_shadow_fire":
            lanes["grinder"].append(rec)
        elif st == "flat_top_observe_only":
            lanes["flat_top" if 570 <= hm < 630 else "flat_top_oow"].append(rec)
        elif st == "v2_shadow_fire":
            lanes["v2"].append(rec)
        elif st == "bandpass_shadow_fire":              # 8/16 RTH band-pass (in-window = paying cell)
            lanes["bandpass" if 570 <= hm < 630 else "bandpass_oow"].append(rec)
        elif st == "prevwap_shadow_fire":               # 8/16 Kev 8AM PRE lane — flatten 09:25
            lanes["prevwap"].append(rec)
    cache, res = {}, {}
    for lane, fires in lanes.items():
        n, tot, skip = 0, 0.0, 0
        for tk, t0, px, stop in fires:
            if px <= 0:
                skip += 1
                continue
            if tk not in cache:
                cache[tk] = bars(tk)
            p = sim_e3(cache[tk], t0, px, stop, flatten_hm=(565 if lane == "prevwap" else 959))
            if p is None:
                skip += 1
                continue
            n += 1
            tot += p
        res[lane] = (n, tot, skip)
    port = res["grinder"][1] + res["flat_top"][1]        # E3 nominated config: grinder + in-window flat_top
    if not WALL.exists():
        WALL.write_text(
            "# E3 OOS WALL — grinder-1030 + flat_top(9:30-10:30) through E3 exits "
            "(bank 1/2 +10%, 10%-off-high trail)\n"
            "Nominated by edge_stresstest_F_20260815.md (PASS 5/5). >=5 forward days before any "
            "live talk; 8/8 law: smaller + later, never launch-anyway. One line per day, appended "
            "by nightly_shadow_grade.py at 23:00 ET. flat_top graded from observe rows "
            "(chase +1% modeled); v2 = separate lane, NOT in the portfolio number. Sim is "
            "haltgap-free and -0.5%-slip flat — optimistic on halted/fast tape.\n\n")
    prior = sum(1 for ln in WALL.read_text().splitlines() if ln.startswith("- ")) if WALL.exists() else 0
    line = (f"- {DAY} | grinder N={res['grinder'][0]} ${res['grinder'][1]:+.2f}"
            f" | flat_top(in-win) N={res['flat_top'][0]} ${res['flat_top'][1]:+.2f}"
            f" (oow N={res['flat_top_oow'][0]} ${res['flat_top_oow'][1]:+.2f})"
            f" | v2 N={res['v2'][0]} ${res['v2'][1]:+.2f}"
            f" | bandpass(in-win) N={res['bandpass'][0]} ${res['bandpass'][1]:+.2f}"
            f" (oow N={res['bandpass_oow'][0]} ${res['bandpass_oow'][1]:+.2f})"
            f" | prevwap(PRE,flat 09:25) N={res['prevwap'][0]} ${res['prevwap'][1]:+.2f}"
            f" | E3 PORTFOLIO ${port:+.2f} | wall day {prior + 1}"
            f" | skipped {sum(v[2] for v in res.values())}\n")
    with WALL.open("a") as f:
        f.write(line)
    print(line.strip())


if __name__ == "__main__":
    main()
