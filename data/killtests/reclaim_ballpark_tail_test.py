"""BALLPARK x TAIL 2x2 (7/28 night) — the combined hypothesis, scored on 7/27-7/28.

HYPOTHESIS (pre-registered this evening): the reclaim trigger only has edge AT A MARKED LEVEL,
and its winners pay through the TAIL. Prediction: ballpark fires (within +-10% of any sheet
level on that name) beat non-ballpark fires, and a loose-runner exit beats the bank-early
ladder ON THE BALLPARK COHORT specifically. If ballpark does not separate, the hypothesis dies.

Method: same detector, first fire per name per day (arm-A slotting), same $30/$1k sizing.
  BALLPARK  min distance from fire px to {break, confirm, targets[], next_supply} <= 10%
            (names with NO sheet entry form their own 'no sheet' cohort — reported, not hidden)
  EXIT 1    the live ladder (50%@1R, 25%@2R, BE after scale 1, 3-min-low runner trail, 15:45)
  EXIT 2    KEV-LOOSE: 50%@1R -> stop to BE; runner holds until 1-min EMA9 < EMA20 (front->back
            flip proxy, his kill-switch) or 15:45. No 2R trim, no tight trail — the tail rides.
Zero slippage, 2 days, ladder proxies — a DIRECTION test, not a P&L forecast.
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


def emas_series(order, m):
    """1-min EMA9/EMA20 by minute-key (progressive, no lookahead)."""
    out = {}
    e9 = e20 = None
    k9, k20 = 2 / 10, 2 / 21
    for key in order:
        c = m[key][1]
        e9 = c if e9 is None else c * k9 + e9 * (1 - k9)
        e20 = c if e20 is None else c * k20 + e20 * (1 - k20)
        out[key] = (e9, e20)
    return out


def exit_ladder(bars, i0, entry, stop, m1):
    rps = entry - stop
    sh = int(min(RISK / rps, CAP / entry)) if rps > 0 else 0
    if sh < 1:
        return None
    t1, t2 = entry + rps, entry + 2 * rps
    rem, real, cur = sh, 0.0, stop
    s1 = s2 = False
    for j in range(i0 + 1, len(bars)):
        k, o, h, l, c, v, hm = bars[j]
        if hm >= "15:45":
            return real + rem * (c - entry)
        if l <= cur:
            return real + rem * (cur - entry)
        if not s1 and h >= t1:
            q = sh // 2; real += q * (t1 - entry); rem -= q; s1 = True; cur = max(cur, entry)
        if s1 and not s2 and h >= t2:
            q = sh // 4; real += q * (t2 - entry); rem -= q; s2 = True
        if s2:
            key = k // 60
            lows = [m1[x][0] for x in (key - 3, key - 2, key - 1) if x in m1]
            if lows:
                cur = max(cur, min(lows))
        if rem <= 0:
            return real
    return real + rem * (bars[-1][4] - entry)


def exit_loose(bars, i0, entry, stop, emas):
    """Kev-loose: 50%@1R -> BE; runner rides until 1m EMA9<EMA20 (close-confirmed) or 15:45."""
    rps = entry - stop
    sh = int(min(RISK / rps, CAP / entry)) if rps > 0 else 0
    if sh < 1:
        return None
    t1 = entry + rps
    rem, real, cur = sh, 0.0, stop
    s1 = False
    for j in range(i0 + 1, len(bars)):
        k, o, h, l, c, v, hm = bars[j]
        if hm >= "15:45":
            return real + rem * (c - entry)
        if l <= cur:
            return real + rem * (cur - entry)
        if not s1 and h >= t1:
            q = sh // 2; real += q * (t1 - entry); rem -= q; s1 = True; cur = max(cur, entry)
        if s1:
            e = emas.get(k // 60 - 1)          # last COMPLETED minute — no lookahead
            if e and e[0] < e[1]:
                return real + rem * (c - entry)   # front->back flip: runner exits here
    return real + rem * (bars[-1][4] - entry)


def first_fire(sym, bars):
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    for i, (k, o, h, l, c, v, hm) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v; vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            return {"i": i, "px": f["px"], "stop": f["stop"], "hm": hm}
    return None


DATES = ["2026-07-27", "2026-07-28"]
sheets = {}
for d in DATES:
    try:
        sheets[d] = json.load(urllib.request.urlopen(
            f"{U}/api/kev_watchlist?date={d}")).get("levels") or {}
    except Exception:
        sheets[d] = {}

rows = []
for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names (sheet: {len(sheets[date])})", flush=True)
    for tk in names:
        bars = norm(fetch(date, tk))
        if len(bars) < 120:
            continue
        f = first_fire(tk, bars)
        if not f:
            continue
        order, m1 = fold_1m(bars)
        emas = emas_series(order, m1)
        pl_l = exit_ladder(bars, f["i"], f["px"], f["stop"], m1)
        pl_k = exit_loose(bars, f["i"], f["px"], f["stop"], emas)
        if pl_l is None or pl_k is None:
            continue
        L = sheets[date].get(tk)
        if L:
            lv = [L.get("break"), L.get("confirm"), L.get("next_supply")] + list(L.get("targets") or [])
            lv = [float(x) for x in lv if x]
            gap = min(abs(f["px"] - x) / x for x in lv) if lv else None
        else:
            gap = None
        cohort = ("no_sheet" if gap is None else ("ballpark" if gap <= 0.10 else "far"))
        rows.append((date, tk, f["hm"], cohort, round(gap * 100, 1) if gap is not None else None,
                     round(pl_l, 2), round(pl_k, 2)))

print("\n" + "=" * 96)
print(f"{'cohort':10}{'n':>5}{'LADDER P&L':>13}{'$/entry':>9}{'LOOSE P&L':>12}{'$/entry':>9}{'loose wins n':>13}")
for c in ("ballpark", "far", "no_sheet"):
    g = [r for r in rows if r[3] == c]
    if not g:
        continue
    ll = sum(r[5] for r in g); kk = sum(r[6] for r in g)
    print(f"  {c:8}{len(g):5}{ll:13.2f}{ll/len(g):9.2f}{kk:12.2f}{kk/len(g):9.2f}"
          f"{sum(1 for r in g if r[6] > 0):>10}/{len(g)}")

bp = [r for r in rows if r[3] == "ballpark"]
print("\nBALLPARK fires in detail (the hypothesis cell):")
for r in sorted(bp, key=lambda x: x[6]):
    print(f"  {r[0][5:]} {r[2]} {r[1]:6} gap {r[4]:4.1f}%   ladder {r[5]:+9.2f}   loose {r[6]:+9.2f}")

# permutation on the ballpark-vs-far split, loose exit (the hypothesis' own terms)
import random
random.seed(11)
lab = [(r[3] == "ballpark") for r in rows if r[3] != "no_sheet"]
pn = [r[6] for r in rows if r[3] != "no_sheet"]
if any(lab) and not all(lab):
    obs = sum(p for p, m in zip(pn, lab) if m) / max(sum(lab), 1)
    cnt = 0; N = 20000
    for _ in range(N):
        random.shuffle(pn)
        if sum(p for p, m in zip(pn, lab) if m) / max(sum(lab), 1) >= obs:
            cnt += 1
    print(f"\npermutation (loose exit): P(ballpark $/entry >= {obs:+.2f} by chance) = {cnt/N:.4f}")
print("\n2 days, zero slippage, exit proxies. DIRECTION test for the pre-registered hypothesis;")
print("Friday's live-stamp cut is the confirmation pass either way.")
