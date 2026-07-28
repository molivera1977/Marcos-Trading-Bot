"""ZONE_FLIP + HIDDEN_ENTRY THREE-ARM TEST (7/28) — the same harness that shadowed vwap_reclaim.

Why: these two lanes are exempt from EVERY selection gate (chart, momentum, vel5, day-gain,
min-stop) and their live record is n=4 (zone_flip 1 fill −$2.29; hidden_entry 0/3 −$100.51) —
too small to judge. Tonight's reclaim replay found tight stops were that lane's defect; both
of these are on MIN_STOP_EXEMPT for the same "tape lanes are tight-by-design" reasoning.
HYPOTHESIS UNDER TEST: the same disease, hidden by tiny n.

Identical method to reclaim_three_arm_killtest.py so the numbers are comparable:
  A  AS BUILT     detector stop, one fire per name per day (the live slot rule)
  B  FLOORED      stop widened to >=6% of entry (what removing the exemption would do)
  C  CAMPAIGN     detector stop, re-enter on later fires while 1-min EMA9>EMA20, max 3/name
Ladder (same for all arms): 50%@1R, 25%@2R, BE after scale 1, 3-min-low runner trail after
scale 2, 15:45 force-flat, stop-before-target on every bar (conservative), zero slippage.
Sizing: shares = int(min($30/(entry-stop), $1000/entry)).

zone_flip needs its 9:00-9:29 premarket shelf, which it reads through _curl_feed() — so the
replay SERVES that feed from the captured tape (premarket + RTH) rather than the live store.
Per-symbol detector state (_zf_st/_zf_zone/_he_st) is cleared before each name.
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


def norm(bars, rth_only=True):
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
        if hm >= "16:00":
            continue
        if rth_only and hm < "09:30":
            continue
        out.append((int(dt.timestamp()), float(x.get("open") or x.get("o")),
                    float(x.get("high") or x.get("h")), float(x.get("low") or x.get("l")),
                    float(x.get("close") or x.get("c")), float(x.get("volume") or x.get("v") or 0), hm))
    return sorted(out)


def serve_feed(allbars):
    """Patch _curl_feed so zone_flip's premarket-shelf lookup reads THIS tape."""
    d = {b[0]: {"o": b[1], "h": b[2], "l": b[3], "c": b[4], "v0": 0.0, "v1": b[5]} for b in allbars}
    bot._curl_feed = lambda sym, n=None: (d, "replay")


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


def ladder(bars, i0, entry, stop, order, m1):
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
            return realized + rem * (c - entry), j, "flat345"
        if l <= cur:
            return realized + rem * (cur - entry), j, ("stop" if not s1 else "stop_after_scale")
        if not s1 and h >= t1:
            sell = sh // 2
            realized += sell * (t1 - entry); rem -= sell; s1 = True
            cur = max(cur, entry)
        if s1 and not s2 and h >= t2:
            sell = sh // 4
            realized += sell * (t2 - entry); rem -= sell; s2 = True
        if s2:
            key = k // 60
            lows = [m1[x][0] for x in (key - 3, key - 2, key - 1) if x in m1]
            if lows:
                cur = max(cur, min(lows))
        if rem <= 0:
            return realized, j, "scaled_out"
    return realized + rem * (bars[-1][4] - entry), len(bars) - 1, "eod"


def fires_zone_flip(sym, rth, allb):
    serve_feed(allb)
    bot._zf_st.pop(sym, None)
    for d in (getattr(bot, "_zf_zone", {}),):
        for k in [k for k in d if k[1] == sym]:
            d.pop(k, None)
    out = []
    for i, (k, o, h, l, c, v, hm) in enumerate(rth):
        f = bot.kev_zoneflip_step(sym, [(k, o, h, l, c, v)])
        if f:
            out.append({"i": i, "px": f.get("px") or c, "stop": f["stop"], "hm": hm, "k": k})
    return out


def fires_hidden(sym, rth, allb):
    bot._he_st.pop(sym, None)
    pv = vol = 0.0
    out = []
    for i, (k, o, h, l, c, v, hm) in enumerate(rth):
        tp = (h + l + c) / 3.0
        pv += tp * v; vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.hidden_entry_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            out.append({"i": i, "px": f.get("px") or c, "stop": f["stop"], "hm": hm, "k": k})
    return out


DATES = ["2026-07-27", "2026-07-28"]
LANES = {"zone_flip": fires_zone_flip, "hidden_entry": fires_hidden}
res = {ln: {a: [] for a in "ABC"} for ln in LANES}
detail = {ln: [] for ln in LANES}

for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names", flush=True)
    for tk in names:
        raw = fetch(date, tk)
        rth = norm(raw, rth_only=True)
        allb = norm(raw, rth_only=False)
        if len(rth) < 120:
            continue
        order, m1 = fold_1m(rth)
        for ln, fn in LANES.items():
            try:
                fs = fn(tk, rth, allb)
            except Exception:
                continue
            if not fs:
                continue
            f = fs[0]
            r = ladder(rth, f["i"], f["px"], f["stop"], order, m1)
            if r:
                res[ln]["A"].append((date, tk, r[0], r[2]))
            r = ladder(rth, f["i"], f["px"], min(f["stop"], f["px"] * 0.94), order, m1)
            if r:
                res[ln]["B"].append((date, tk, r[0], r[2]))
            att, tot, busy, log = 0, 0.0, -1, []
            for g in fs:
                if att >= 3 or g["i"] <= busy:
                    continue
                key = g["k"] // 60
                e9, e20 = ema_at(order, m1, key, 9), ema_at(order, m1, key, 20)
                if e9 is None or e20 is None or e9 <= e20:
                    continue
                r = ladder(rth, g["i"], g["px"], g["stop"], order, m1)
                if not r:
                    continue
                att += 1; tot += r[0]; busy = r[1]; log.append((g["hm"], round(r[0], 2), r[2]))
            if att:
                res[ln]["C"].append((date, tk, tot, f"{att}att"))
                detail[ln].append((date, tk, tot, log))

print("\n" + "=" * 100)
for ln in LANES:
    print(f"\n### {ln.upper()}")
    if not res[ln]["A"]:
        print("   NO FIRES on this tape — nothing to judge.")
        continue
    print(f"  {'arm':26}{'entries':>8}{'names':>7}{'wins':>7}{'P&L $':>11}{'med $':>9}{'$/entry':>9}")
    for a, lbl in [("A", "A as built, one shot"), ("B", "B 6%-floored, one shot"),
                   ("C", "C campaign (<=3 att)")]:
        rows = res[ln][a]
        if not rows:
            continue
        n = sum(int(x[3][0]) if a == "C" else 1 for x in rows)
        pn = [x[2] for x in rows]
        print(f"  {lbl:24}{n:>8}{len(rows):>7}{sum(1 for p in pn if p > 0):>7}"
              f"{sum(pn):>11.2f}{st.median(pn):>9.2f}{sum(pn)/n:>9.2f}")
    for a in "ABC":
        for d in DATES:
            pn = [x[2] for x in res[ln][a] if x[0] == d]
            if pn:
                print(f"     {a} {d}: {sum(pn):+9.2f} ({len(pn)} names)")
    if detail[ln]:
        print("   best / worst campaigns:")
        for d, tk, tot, log in sorted(detail[ln], key=lambda x: -x[2])[:3]:
            print(f"     {d[5:]} {tk:6} {tot:+9.2f} {log}")
        for d, tk, tot, log in sorted(detail[ln], key=lambda x: x[2])[:3]:
            print(f"     {d[5:]} {tk:6} {tot:+9.2f} {log}")

print("""
SAME MODEL LIMITS as the reclaim run: zero slippage, stop-before-target, 3-min-low trail (not the
live health-fold), detector population not the live watchlist. Compares POLICIES on identical
ground; does not predict book P&L. zone_flip additionally depends on the replay-served premarket
feed for its shelf — a name whose premarket tape is missing simply produces no zone (idles).""")
json.dump({ln: res[ln] for ln in LANES}, open("/tmp/tape_lanes_three_arm.json", "w"))
