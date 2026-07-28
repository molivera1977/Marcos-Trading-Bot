"""RECLAIM THREE-ARM SHIP/KILL (7/28 night, run early per Marcos "run the test now").

Same tape (7/27+7/28 ALP10S, every captured name), same detector (the bot's own kev_reclaim_step),
same exit ladder, dollars through the real sizing chain. Three policies:

  A  AS BUILT       tight wick stop, ONE live fire per name per day (the current slot rule)
  B  FLOORED        stop widened to >=6% of entry (stop'=min(wick, entry*0.94)), one fire/day
  C  KEV-FAITHFUL   tight wick stop, RE-ENTER on the next reclaim fire while the trend gate holds
                    (1-min EMA9 > EMA20 at the fire — Kev's front-side spec), max 3 attempts/name/day.
                    "Keep attacking front side; stop on the flip."

EXIT LADDER (identical for every arm — fairness over perfect fidelity, model stated in full):
  scale 50% at +1R, 25% at +2R (kev25 tiers); stop -> breakeven after the FIRST scale
  (BE_FLOOR_AFTER_SCALE=1, shipped 7/27); runner (25%) trails the rolling 3-minute low once +2R
  has scaled; hard stop before that. Intrabar on 10s lows/highs, stop/target priority: on any bar
  where both stop and target are inside the range, the STOP is assumed hit first (conservative).
  15:45 force-flat prices every open position at that bar's close (the real 3:45 rule).
  Slippage/spread: ZERO modeled — stated, not hidden; per-attempt friction hurts C most, noted.
  Sizing per attempt: shares = int(min($30 / (entry-stop), $1000 / entry)).

Output: signed P&L per arm, per day, per name; campaign detail for C. This is the decision input
pre-registered in the ledger (Fable ruling 10e9e0d + arm C addendum 27a1f1e).
"""
import json, os, sys, urllib.request, urllib.parse, statistics as st
from datetime import datetime, timedelta, timezone
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
RISK, CAP = 30.0, 1000.0
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9


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
                    float(x.get("close") or x.get("c")), float(x.get("volume") or x.get("v") or 0), hm))
    return sorted(out)


def fold_1m(bars):
    """10s -> 1-min closes for EMA computation (trend gate + runner trail)."""
    m, order = {}, []
    for b in bars:
        key = b[0] // 60
        if key not in m:
            m[key] = [b[3], b[4]]      # [low, close]
            order.append(key)
        else:
            m[key][0] = min(m[key][0], b[3])
            m[key][1] = b[4]
    return order, m


def emas_at(order, m, upto_key, span):
    k = 2.0 / (span + 1)
    e = None
    for key in order:
        if key > upto_key:
            break
        c = m[key][1]
        e = c if e is None else c * k + e * (1 - k)
    return e


def fires_for(sym, bars):
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    out = []
    for i, (k, o, h, l, c, v, hm) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v
        vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            out.append({"i": i, "px": f["px"], "stop": f["stop"], "hm": hm, "k": k})
    return out


def ladder(bars, i0, entry, stop, order, m1):
    """Run the exit ladder forward from bar i0+1. Returns (pnl_$, exit_i, tag)."""
    rps = entry - stop
    if rps <= 0:
        return None
    sh = int(min(RISK / rps, CAP / entry))
    if sh < 1:
        return None
    t1, t2 = entry + rps, entry + 2 * rps
    remaining = sh
    realized = 0.0
    cur_stop = stop
    scaled1 = scaled2 = False
    for j in range(i0 + 1, len(bars)):
        k, o, h, l, c, v, hm = bars[j]
        if hm >= "15:45":
            realized += remaining * (c - entry)
            return realized, j, "flat345"
        # conservative ordering: stop checked before targets on every bar
        if l <= cur_stop:
            realized += remaining * (cur_stop - entry)
            return realized, j, ("stop" if not scaled1 else "stop_after_scale")
        if not scaled1 and h >= t1:
            sell = sh // 2
            realized += sell * (t1 - entry)
            remaining -= sell
            scaled1 = True
            cur_stop = max(cur_stop, entry)          # BE floor after scale #1 (shipped 7/27)
        if scaled1 and not scaled2 and h >= t2:
            sell = sh // 4
            realized += sell * (t2 - entry)
            remaining -= sell
            scaled2 = True
        if scaled2:
            # runner trails the rolling 3-minute low
            key = k // 60
            lows = [m1[x][0] for x in (key - 3, key - 2, key - 1) if x in m1]
            if lows:
                cur_stop = max(cur_stop, min(lows))
        if remaining <= 0:
            return realized, j, "scaled_out"
    realized += remaining * (bars[-1][4] - entry)
    return realized, len(bars) - 1, "eod"


DATES = ["2026-07-27", "2026-07-28"]
MAX_ATTEMPTS = 3
res = {a: [] for a in "ABC"}
camp_detail = []
for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names", flush=True)
    for tk in names:
        bars = norm(fetch(date, tk))
        if len(bars) < 120:
            continue
        fs = fires_for(tk, bars)
        if not fs:
            continue
        order, m1 = fold_1m(bars)
        # A: first fire, wick stop
        f = fs[0]
        r = ladder(bars, f["i"], f["px"], f["stop"], order, m1)
        if r:
            res["A"].append((date, tk, r[0], r[2]))
        # B: first fire, floored stop
        wstop = min(f["stop"], f["px"] * 0.94)
        r = ladder(bars, f["i"], f["px"], wstop, order, m1)
        if r:
            res["B"].append((date, tk, r[0], r[2]))
        # C: campaign — attempt fires in order, trend gate at each, next attempt only after the
        # prior one has EXITED (no overlap), max 3
        attempts, tot, busy_until, log = 0, 0.0, -1, []
        for f in fs:
            if attempts >= MAX_ATTEMPTS:
                break
            if f["i"] <= busy_until:
                continue
            key = f["k"] // 60
            e9, e20 = emas_at(order, m1, key, 9), emas_at(order, m1, key, 20)
            if e9 is None or e20 is None or e9 <= e20:
                continue                              # back side — Kev: leave it alone
            r = ladder(bars, f["i"], f["px"], f["stop"], order, m1)
            if not r:
                continue
            attempts += 1
            tot += r[0]
            busy_until = r[1]
            log.append((f["hm"], round(r[0], 2), r[2]))
        if attempts:
            res["C"].append((date, tk, tot, f"{attempts}att"))
            camp_detail.append((date, tk, tot, log))

print("\n" + "=" * 96)
print(f"{'arm':28}{'entries':>8}{'names':>7}{'wins':>7}{'P&L $':>11}{'med $':>9}{'$/entry':>9}")
labels = {"A": "A tight stop, one shot", "B": "B 6%-floored, one shot", "C": "C Kev campaign (<=3 att)"}
for a in "ABC":
    rows = res[a]
    n_entries = sum(int(x[3][0]) if a == "C" else 1 for x in rows)
    pn = [x[2] for x in rows]
    if not pn:
        continue
    print(f"  {labels[a]:26}{n_entries:>8}{len(rows):>7}{sum(1 for p in pn if p > 0):>7}"
          f"{sum(pn):>11.2f}{st.median(pn):>9.2f}{sum(pn)/n_entries:>9.2f}")
for a in "ABC":
    for d in DATES:
        pn = [x[2] for x in res[a] if x[0] == d]
        if pn:
            print(f"    {labels[a][:1]} {d}: {sum(pn):+9.2f}  ({len(pn)} names)")

print("\nC campaign detail — biggest winners and losers:")
for d, tk, tot, log in sorted(camp_detail, key=lambda x: -x[2])[:6]:
    print(f"  {d[5:]} {tk:6} {tot:+9.2f}  {log}")
for d, tk, tot, log in sorted(camp_detail, key=lambda x: x[2])[:6]:
    print(f"  {d[5:]} {tk:6} {tot:+9.2f}  {log}")

print("""
MODEL LIMITS (identical across arms unless noted): zero slippage/spread (hurts C most — more
attempts, more friction); stop-before-target on every bar (conservative); runner trail = 3-min
rolling low, not the live health-fold; detector population (~all captured names), not the live
bot's watchlist — LEVEL: this compares POLICIES on identical ground, it does not predict book P&L.""")
json.dump({a: res[a] for a in "ABC"}, open("/tmp/reclaim_three_arm.json", "w"))
print("rows -> /tmp/reclaim_three_arm.json")
