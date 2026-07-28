"""WIDENED-STOP COUNTERFACTUAL (7/28, Fable) — the decisive fork on vwap_reclaim.

Two live readings of the same facts:
  A) "the 6% floor is RIGHT to kill these" — sub-6%-stop trades measured −$614 era-wide (p=0.0047)
  B) "the SETUPS are real, the STOP construction is the defect" — median 2.11% stop inside the noise

This distinguishes them: SAME 234 fires, same entries, stop floored at 6% below entry
(stop' = min(wick_stop, entry*0.94)), tape re-walked forward, stop checked on every bar BEFORE
crediting the high. Dollars through the real sizing chain ($30 risk / rps, $1k notional cap).
Exit model: conservative ladder proxy — 50% off at +1R, remainder rides to peak/2 credit? NO:
we do NOT invent an exit. We report the two things that decide the fork without an exit model:
  1. stop-survival: how many fires now LIVE long enough to reach +1R (= +6%)
  2. terminal accounting at the extremes: full loss −$30 if stopped before +6%;
     if +6% reached first, credit the LADDER FLOOR = +1R on half the position and breakeven on
     the rest (the BE floor after scale #1, shipped 7/27) = +$15 GUARANTEED, plus unmodeled upside.
This is a LOWER BOUND on the widened-stop policy (winners credited $15 min, tails ignored) vs an
EXACT loss on losers. If the lower bound beats the tight-stop reality (−$256 era / 89% swept),
reading B wins. If even the lower bound is negative, reading A wins and the floor stands.
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
RISK, CAP = 30.0, 1000.0
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
FLOOR = 0.06


def fetch(date, tk):
    try:
        r = json.load(urllib.request.urlopen(
            f"{U}/api/bars?date={date}&ticker={urllib.parse.quote(tk + '~ALP10S')}", timeout=25))
        return r.get("bars") or []
    except Exception:
        return []


def norm(bars):
    out = []
    for x in bars:
        t = x.get("time") or x.get("t")
        if not t:
            continue
        try:
            dt = datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc).astimezone(ET)
        except Exception:
            continue
        hm = dt.strftime("%H:%M")
        if hm < "09:30" or hm >= "16:00":
            continue
        out.append((int(dt.timestamp()), float(x.get("open") or x.get("o")),
                    float(x.get("high") or x.get("h")), float(x.get("low") or x.get("l")),
                    float(x.get("close") or x.get("c")), float(x.get("volume") or x.get("v") or 0)))
    return sorted(out)


def replay_fires(sym, bars):
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    out = []
    for i, (k, o, h, l, c, v) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v
        vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            out.append((i, f["px"], f["stop"]))
    return out


def judge(bars, i0, entry, stop):
    """Forward walk. Returns ('win', bars_to_1R) if +6% prints before the stop, ('loss',) if the
    stop prints first, ('flat',) if neither by EOD. Stop checked before the high on every bar."""
    tgt = entry * 1.06
    for j in range(i0 + 1, len(bars)):
        if bars[j][3] <= stop:
            return "loss"
        if bars[j][2] >= tgt:
            return "win"
    return "flat"


DATES = ["2026-07-27", "2026-07-28"]
res = {"tight": {"win": 0, "loss": 0, "flat": 0}, "wide": {"win": 0, "loss": 0, "flat": 0}}
wide_detail = []
n_fires = 0
for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names", flush=True)
    for tk in names:
        bars = norm(fetch(date, tk))
        if len(bars) < 120:
            continue
        for i0, px, wick_stop in replay_fires(tk, bars):
            n_fires += 1
            res["tight"][judge(bars, i0, px, wick_stop)] += 1
            wstop = min(wick_stop, px * (1 - FLOOR))
            v = judge(bars, i0, px, wstop)
            res["wide"][v] += 1
            wide_detail.append((date, tk, px, wstop, v))

print(f"\nfires: {n_fires}")
print(f"{'':14}{'reach +6% FIRST':>17}{'stop FIRST':>12}{'neither (flat)':>16}")
for k, lbl in [("tight", "tight (as built)"), ("wide", "6%-floored stop")]:
    r = res[k]
    print(f"  {lbl:12}{r['win']:>15} {r['loss']:>12} {r['flat']:>15}")

# Lower-bound dollars for the widened policy:
#   win  = +$15 (ladder floor: 1R on half, BE on rest; tails IGNORED)
#   loss = −$30 (full 1R, exact)
#   flat = $0   (scratch at EOD flat — optimistic by up to the overnight, but 3:45 force-flat is real;
#                flats are counted at 0 both ways so they cancel in the comparison)
w = res["wide"]
lb = w["win"] * 15 - w["loss"] * 30
print(f"\nwidened-stop LOWER BOUND: {w['win']}×(+$15) + {w['loss']}×(−$30) = ${lb:+.2f}"
      f"   across {n_fires} fires (~{n_fires/2:.0f}/day is NOT tradeable volume — see caveat)")
t = res["tight"]
lb_t = t["win"] * 15 - t["loss"] * 30
print(f"tight-stop same accounting:  {t['win']}×(+$15) + {t['loss']}×(−$30) = ${lb_t:+.2f}")
print("""
CAVEATS: (1) 234 fires/2 days is the DETECTOR population, not a tradeable book — the live bot
takes ~1 per name per day; per-fire EXPECTANCY is the comparable number, not the total.
(2) +$15 win credit ignores every tail (DFNS +133% would book $15 here) — true lower bound.
(3) No slippage/spread. (4) Two days, one market regime.""")
print(f"\nper-fire expectancy lower bound: tight ${lb_t/n_fires:+.2f}   wide ${lb/n_fires:+.2f}")
json.dump(wide_detail, open("/tmp/reclaim_widestop.json", "w"))
