"""RS-AT-OPEN RANKER — first data pass (Handicapper #69), 7/20+7/21 cached days.
Kev's method (7/20 short): among the open's gainers, the one that curls FIRST while
peers fade is the horse. Computable form scored at 9:40 ET on bars 9:30-9:39:
  ret10       = close@9:39 vs open@9:30
  rel         = ret10 - basket mean          (peer-relative strength = the ranking key)
  vwap_hold   = close@9:39 > session VWAP (PRE+RTH so far)
  curl_min    = first minute 9:31-9:39 with close > prior high AND vol > prior vol
Outcome (from 9:40): maxhigh-to-close potential and close-to-close hold.
Baseline comparison: gap-rank proxy = open@9:30 vs prior-day close (where cached).
DECLARED LIMITS: n=2 days (directional, not verdict); basket = names with >=8 of the
first 10 RTH minutes cached (late subscribes like BIYA/SKYQ unscoreable — coverage bias);
mid-day launchers (CPHI 10:18, DFNS 11:05) are OUT OF SCOPE for an OPEN ranker by design."""
import json, hashlib, pathlib, urllib.parse

U = "https://zestful-intuition-production-b16a.up.railway.app"
def get(u):
    k = pathlib.Path("mcache") / (hashlib.md5(u.encode()).hexdigest() + ".json")
    return json.load(open(k)) if k.exists() else {}
def roster(d):
    names = set(get(f"{U}/api/watching?date={d}").get("tickers") or [])
    for r in (get(f"{U}/api/decisions_archive?date={d}&limit=12000").get("rows") or []):
        names.add((r.get("ticker") or "").upper())
    return sorted(n for n in names if n and n != "N/A")
def F(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

for d in ["2026-07-20", "2026-07-21"]:
    rows = []
    for t in roster(d):
        allb = get(f"{U}/api/minute_ext?ticker={urllib.parse.quote(t)}&count=1200").get("bars") or []
        allb.sort(key=lambda x: str(x.get("time", "")))
        today = [x for x in allb if str(x.get("time", "")).startswith(d) and x.get("session") == "RTH"]
        pre   = [x for x in allb if str(x.get("time", "")).startswith(d) and x.get("session") == "PRE"]
        prior = [x for x in allb if str(x.get("time", ""))[:10] < d and x.get("session") == "RTH"]
        if len(today) < 60: continue
        mins = {str(x["time"])[11:16]: x for x in today}
        first10 = [mins.get(f"13:{m:02d}") for m in range(30, 40)]
        have = [b for b in first10 if b]
        if len(have) < 8: continue                    # can't score the open — excluded, counted
        o = F(have[0].get("open")) or F(have[0].get("close"))
        c940 = F(have[-1].get("close"))
        if o <= 0 or c940 <= 0: continue
        ret10 = (c940 - o) / o * 100
        pv = vol = 0.0
        for b in pre + have:
            v = F(b.get("volume")); pv += (F(b.get("high")) + F(b.get("low")) + F(b.get("close"))) / 3 * v; vol += v
        vwap = pv / vol if vol > 0 else 0
        curl = None
        for i in range(1, len(have)):
            if (F(have[i].get("close")) > F(have[i-1].get("high")) > 0
                    and F(have[i].get("volume")) > F(have[i-1].get("volume"))):
                curl = str(have[i]["time"])[14:16]; break
        rest = [x for x in today if str(x["time"])[11:16] >= "13:40"]
        pot = (max(F(x.get("high")) for x in rest) - c940) / c940 * 100 if rest else 0
        hold = (F(rest[-1].get("close")) - c940) / c940 * 100 if rest else 0
        gap = (o - F(prior[-1].get("close"))) / F(prior[-1].get("close")) * 100 if prior and F(prior[-1].get("close")) > 0 else None
        rows.append({"t": t, "ret10": ret10, "vwap_hold": c940 > vwap > 0, "curl": curl,
                     "pot": pot, "hold": hold, "gap": gap, "c940": c940})
    if not rows: continue
    mean10 = sum(r["ret10"] for r in rows) / len(rows)
    for r in rows: r["rel"] = r["ret10"] - mean10
    rows.sort(key=lambda r: -r["rel"])
    print(f"\n════ {d} — basket {len(rows)} scoreable at 9:40 (basket mean ret10 {mean10:+.1f}%) ════")
    print(f"{'rk':>3s} {'ticker':7s} {'ret10%':>7s} {'rel%':>7s} {'vwapH':>5s} {'curl@':>5s} {'gap%':>7s} | {'pot%':>7s} {'hold%':>7s}")
    for i, r in enumerate(rows):
        print(f"{i+1:3d} {r['t']:7s} {r['ret10']:+7.1f} {r['rel']:+7.1f} {'Y' if r['vwap_hold'] else '.':>5s} "
              f"{(':'+r['curl']) if r['curl'] else '  - ':>5s} "
              f"{('%+7.1f' % r['gap']) if r['gap'] is not None else '    n/a':>7s} | {r['pot']:+7.1f} {r['hold']:+7.1f}")
    top3 = rows[:3]; restrows = rows[3:]
    def avg(xs): return sum(xs) / len(xs) if xs else 0
    print(f"  RS top-3   : avg potential {avg([r['pot'] for r in top3]):+7.1f}%  avg hold {avg([r['hold'] for r in top3]):+7.1f}%   ({', '.join(r['t'] for r in top3)})")
    print(f"  rest       : avg potential {avg([r['pot'] for r in restrows]):+7.1f}%  avg hold {avg([r['hold'] for r in restrows]):+7.1f}%")
    g = [r for r in rows if r["gap"] is not None]
    if len(g) >= 6:
        g.sort(key=lambda r: -r["gap"]); gt3 = g[:3]
        print(f"  gap top-3  : avg potential {avg([r['pot'] for r in gt3]):+7.1f}%  avg hold {avg([r['hold'] for r in gt3]):+7.1f}%   ({', '.join(r['t'] for r in gt3)})")
