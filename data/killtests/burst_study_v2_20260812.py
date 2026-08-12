"""BURST STUDY v2 (8/12 evening, task #51). Corrections over v1:
  - EXCLUDE session-open gap artifacts (any burst whose window starts before 04:05 ET)
  - Continuation measured BEYOND THE BURST HIGH (kills v1's mechanical coupling)
  - Controls anchored at a TIME-MATCHED point (each control borrows a burst's anchor time)
  - THE COUNT: monsters (>=40% day range) that ran WITHOUT any prior burst
Days: 8/10, 8/11, 8/12 (8/12 = first crown-pinned capture day).
"""
import json, urllib.request, datetime, statistics

U = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-08-10", "2026-08-11", "2026-08-12"]

def get(path):
    return json.loads(urllib.request.urlopen(U + path, timeout=30).read())

def ts(b):
    t = str(b.get("time") or b.get("t")).replace("+0000", "+00:00").replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(t).timestamp()

def series(tk, day, suf):
    try:
        return sorted(((ts(b), float(b.get("close") or b.get("c")),
                        float(b.get("high") or b.get("h"))) for b in
                       get(f"/api/bars?date={day}&ticker={tk}{suf}").get("bars") or []))
    except Exception:
        return []

def et_hm(t):
    return (datetime.datetime.utcfromtimestamp(t) - datetime.timedelta(hours=4)).strftime("%H:%M")

bursts, controls, monsters = [], [], []
for day in DAYS:
    names = set()
    for path in (f"/api/watching?date={day}",):
        try:
            names.update(t.upper() for t in (get(path).get("tickers") or []) if t)
        except Exception:
            pass
    try:
        kev = get("/api/kev_watchlist").get(day) or []
        names.update(t.upper() for t in kev)
    except Exception:
        pass
    print(f"{day}: {len(names)} names")
    day_anchor_times = []
    day_rows = []
    for tk in sorted(names):
        s1 = series(tk, day, "~ALP1S")
        s10 = series(tk, day, "~ALP10S")
        if not s10:
            continue
        # monster check from 10s (fuller): day range
        lo10 = min(c for _, c, _ in s10); hi10 = max(h for _, _, h in s10)
        is_monster = lo10 > 0 and (hi10 / lo10 - 1) >= 0.40
        burst = None
        if len(s1) >= 300:
            j = 0
            for i in range(len(s1)):
                if j < i + 1: j = i + 1
                while j < len(s1) and s1[j][0] - s1[i][0] <= 10: j += 1
                seg = s1[i:j]
                if len(seg) > 1:
                    hm = et_hm(s1[i][0])
                    if hm < "04:05":       # v2: open gap artifact exclusion
                        continue
                    mv = (max(h for _, _, h in seg) / s1[i][1] - 1) * 100
                    if mv >= 10:
                        bhigh = max(h for _, _, h in seg)
                        burst = (s1[i][0], bhigh, round(mv, 1)); break
        day_rows.append((tk, s1, s10, burst, is_monster, lo10))
        if burst:
            day_anchor_times.append(burst[0])
    for tk, s1, s10, burst, is_monster, lo10 in day_rows:
        if burst:
            bt, bhigh, bmv = burst
            aft = [h for t, _, h in s10 if bt < t and et_hm(t) <= "15:30"]
            cont = (max(aft) / bhigh - 1) * 100 if aft else None   # beyond burst HIGH
            bursts.append({"day": day, "tk": tk, "bmv": bmv, "t": et_hm(bt),
                           "cont": None if cont is None else round(cont, 1),
                           "monster": is_monster})
            if is_monster:
                monsters.append({"day": day, "tk": tk, "burst": True})
        else:
            if is_monster:
                monsters.append({"day": day, "tk": tk, "burst": False,
                                 "observed_1s": len(s1)})
            if len(s1) >= 1800 and day_anchor_times:
                at = day_anchor_times[hash(tk) % len(day_anchor_times)]   # time-matched anchor
                ref = [c for t, c, _ in s10 if t <= at]
                aft = [h for t, _, h in s10 if t > at and et_hm(t) <= "15:30"]
                if ref and aft:
                    controls.append({"day": day, "tk": tk,
                                     "cont": round((max(aft) / ref[-1] - 1) * 100, 1)})

print(f"\nBURSTS (intraday, artifact-excluded): {len(bursts)} | controls {len(controls)}")
for b in sorted(bursts, key=lambda x: -(x["cont"] if x["cont"] is not None else -99))[:15]:
    print(f'  {b["day"][-5:]} {b["tk"]:6s} burst +{b["bmv"]}% @{b["t"]}ET  cont-beyond-high {b["cont"]}%  monster={b["monster"]}')
def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None
print(f'burst   median continuation-beyond-burst-high: {med([b["cont"] for b in bursts])}%  '
      f'(tail: {sum(1 for b in bursts if (b["cont"] or 0) >= 15)}/{len(bursts)} >= +15%)')
print(f'control median continuation from time-matched anchor: {med([c["cont"] for c in controls])}%  '
      f'(tail: {sum(1 for c in controls if c["cont"] >= 15)}/{len(controls)} >= +15%)')
mb = [m for m in monsters if m["burst"]]; mnb = [m for m in monsters if not m["burst"]]
print(f"\nMONSTERS (>=40% day range, 10s-verified): {len(monsters)} total — "
      f"{len(mb)} burst first, {len(mnb)} did NOT:")
for m in mnb:
    print(f'  NO-BURST monster: {m["day"][-5:]} {m["tk"]} (1s bars observed: {m.get("observed_1s")}'
          f' — sparse observation may hide a burst)')
