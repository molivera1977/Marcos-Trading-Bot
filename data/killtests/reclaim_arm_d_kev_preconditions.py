"""ARM D — KEV'S PRECONDITIONS (7/28 night, Marcos: "what are we missing and doing wrong with it").

Hypothesis under test: our reclaim implements Kev's CONFIRMATION (step 3 of his checklist) while
skipping his PRECONDITIONS (steps 1-2). The three-arm test showed every mechanical policy on the
raw fire population loses (A -$959 / B -$306 / C -$980). Arm D asks: does the SAME detector, the
SAME ladder, become positive when a fire may only convert if Kev's steps 1-2 hold at fire time?

Preconditions applied AT THE FIRE (all knowable then, computed from the same tape):
  TREND      1-min EMA9 > EMA20 (his "9 EMA over 20") AND price >= session VWAP * 0.99
             (a "reclaim" fired 40% below VWAP is a dead-cat bounce, not a reclaim —
              FIEE $3.49 vs VWAP $6.52 and LGHL $1.03 vs $1.98 fired live on 7/27)
  FRONT SIDE price within 15% of the session high so far (his reclaim resumes a working trend
             near its highs; back side = "leave it alone")
  RANGE      the fire is NOT the session high itself (needs a prior high above = his "range" is
             approximated conservatively; sheet targets not available intraday here)

Same ladder as arms A-C (50%@1R, 25%@2R, BE after scale 1, 3-min-low runner trail, 15:45 flat,
stop-before-target, zero slippage), same $30/$1k sizing, one shot per name (arm-A slotting) so
the ONLY difference vs arm A is the precondition filter. Also reports the filtered-out cohort's
arm-A P&L so the filter's value = (kept P&L) vs (dropped P&L), not a story.
"""
import json, sys, urllib.request, urllib.parse, statistics as st
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
    m, order = {}, []
    for b in bars:
        key = b[0] // 60
        if key not in m:
            m[key] = [b[3], b[4]]
            order.append(key)
        else:
            m[key][0] = min(m[key][0], b[3])
            m[key][1] = b[4]
    return order, m


def ema_at(order, m, upto, span):
    k = 2.0 / (span + 1)
    e = None
    for key in order:
        if key > upto:
            break
        e = m[key][1] if e is None else m[key][1] * k + e * (1 - k)
    return e


def ladder(bars, i0, entry, stop, m1):
    rps = entry - stop
    if rps <= 0:
        return None
    sh = int(min(RISK / rps, CAP / entry))
    if sh < 1:
        return None
    t1, t2 = entry + rps, entry + 2 * rps
    rem, realized, cur = sh, 0.0, stop
    s1 = s2 = False
    for j in range(i0 + 1, len(bars)):
        k, o, h, l, c, v, hm = bars[j]
        if hm >= "15:45":
            return realized + rem * (c - entry)
        if l <= cur:
            return realized + rem * (cur - entry)
        if not s1 and h >= t1:
            sell = sh // 2; realized += sell * (t1 - entry); rem -= sell; s1 = True
            cur = max(cur, entry)
        if s1 and not s2 and h >= t2:
            sell = sh // 4; realized += sell * (t2 - entry); rem -= sell; s2 = True
        if s2:
            key = k // 60
            lows = [m1[x][0] for x in (key - 3, key - 2, key - 1) if x in m1]
            if lows:
                cur = max(cur, min(lows))
        if rem <= 0:
            return realized
    return realized + rem * (bars[-1][4] - entry)


def first_fire(sym, bars):
    """Arm-A slotting: the day's first fire, with fire-time context for the preconditions."""
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    hi_so_far = 0.0
    for i, (k, o, h, l, c, v, hm) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v; vol += v
        hi_so_far = max(hi_so_far, h)
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            return {"i": i, "px": f["px"], "stop": f["stop"], "hm": hm, "k": k,
                    "vwap": vwap, "hi": hi_so_far}
    return None


DATES = ["2026-07-27", "2026-07-28"]
kept, dropped = [], []
why = {"below_vwap": 0, "far_from_high": 0, "no_trend": 0}
for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names", flush=True)
    for tk in names:
        bars = norm(fetch(date, tk))
        if len(bars) < 120:
            continue
        f = first_fire(tk, bars)
        if not f:
            continue
        order, m1 = fold_1m(bars)
        pnl = ladder(bars, f["i"], f["px"], f["stop"], m1)
        if pnl is None:
            continue
        # ── Kev preconditions at fire time ──
        key = f["k"] // 60
        e9, e20 = ema_at(order, m1, key, 9), ema_at(order, m1, key, 20)
        trend = (e9 is not None and e20 is not None and e9 > e20 and f["px"] >= f["vwap"] * 0.99)
        front = (f["hi"] > 0 and f["px"] >= f["hi"] * 0.85)
        row = (date, tk, f["hm"], round(pnl, 2), round(f["px"] / f["vwap"] - 1, 3) if f["vwap"] else 0,
               round(f["px"] / f["hi"] - 1, 3) if f["hi"] else 0)
        if trend and front:
            kept.append(row)
        else:
            dropped.append(row)
            if f["px"] < f["vwap"] * 0.99:
                why["below_vwap"] += 1
            elif not front:
                why["far_from_high"] += 1
            else:
                why["no_trend"] += 1

print("\n" + "=" * 92)
for lbl, rows in [("ARM D KEPT (Kev preconditions pass)", kept),
                  ("DROPPED (preconditions fail) — what arm A was trading", dropped)]:
    pn = [r[3] for r in rows]
    if not pn:
        print(f"{lbl}: none"); continue
    w = sum(1 for p in pn if p > 0)
    print(f"{lbl}: n={len(rows)}  wins {w}/{len(rows)}  P&L {sum(pn):+9.2f}  "
          f"med {st.median(pn):+7.2f}  $/entry {sum(pn)/len(pn):+7.2f}")
print(f"\ndrop reasons: {why}")
print("\nKEPT detail:")
for r in sorted(kept, key=lambda x: x[3]):
    print(f"  {r[0][5:]} {r[2]} {r[1]:6} {r[3]:+9.2f}   vs VWAP {r[4]:+.1%}  vs sess-high {r[5]:+.1%}")
print("""
Same detector, same ladder, same one-shot slotting — the ONLY variable is Kev's steps 1-2.
Zero slippage; 2 days; ladder proxy. Compare $/entry KEPT vs DROPPED, not the totals.""")
