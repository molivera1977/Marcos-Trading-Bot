"""8/12 ~00:50 BURST STUDY v1 (Marcos: "run the burst study on what we have so far").
HYPOTHESIS: >=10%-in-<=10s micro-bursts mark offer-side fragility and precede outsized moves.
DATA: all 1s series captured 8/10 + 8/11 (roster-capped — OBSERVATION IS PARTIAL; a name only
counts as a control if we actually watched it >=30 observed-minutes at 1s with no burst).
DESIGN: per name-day, detect first burst (time-aware rolling <=10s window, close-to-high move
>=10%); forward outcome measured on the FULLER 10s series: max high in the next 60 min and to
15:30, from the burst price. CONTROLS: observed-no-burst names, anchored at their median
observed second (crude; stated). Verdict bar: burst cohort must beat controls on forward move
to survive as a registry hypothesis; NOTHING ships either way (n is tiny, 2 days).
"""
import json, urllib.request, datetime, statistics

U = "https://zestful-intuition-production-b16a.up.railway.app"
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

results, controls = [], []
for day in ("2026-08-10", "2026-08-11"):
    names = set()
    for path in (f"/api/watching?date={day}", f"/api/kev_watchlist"):
        try:
            d = get(path)
            names.update(t.upper() for t in (d.get("tickers") or d.get(day) or []) if t)
        except Exception:
            pass
    print(f"{day}: probing {len(names)} names")
    for tk in sorted(names):
        s1 = series(tk, day, "~ALP1S")
        if len(s1) < 300:
            continue
        observed_s = len(s1)   # ~1 bar per observed second
        # burst detection: time-aware, close->max-high within <=10s span
        burst = None
        j = 0
        for i in range(len(s1)):
            if j < i + 1: j = i + 1
            while j < len(s1) and s1[j][0] - s1[i][0] <= 10: j += 1
            seg = s1[i:j]
            if len(seg) > 1:
                mv = (max(h for _, _, h in seg) / s1[i][1] - 1) * 100
                if mv >= 10:
                    burst = (s1[i][0], s1[i][1], round(mv, 1)); break
        s10 = series(tk, day, "~ALP10S")
        if not s10:
            continue
        def fwd(anchor_t, anchor_px):
            end_1530 = max(t for t, _, _ in s10)
            in60  = [h for t, _, h in s10 if anchor_t < t <= anchor_t + 3600]
            after = [h for t, _, h in s10 if t > anchor_t]
            return ((max(in60) / anchor_px - 1) * 100 if in60 else None,
                    (max(after) / anchor_px - 1) * 100 if after else None)
        if burst:
            bt, bpx, bmv = burst
            f60, feod = fwd(bt, bpx)
            hm = datetime.datetime.utcfromtimestamp(bt).strftime("%H:%M")
            results.append({"day": day, "tk": tk, "burst_pct": bmv, "utc": hm,
                            "fwd60": f60, "fwd_eod": feod, "obs_s": observed_s})
        elif observed_s >= 1800:
            mid_t = s1[len(s1)//2][0]; mid_px = s1[len(s1)//2][1]
            f60, feod = fwd(mid_t, mid_px)
            if feod is not None:
                controls.append({"day": day, "tk": tk, "fwd60": f60, "fwd_eod": feod,
                                 "obs_s": observed_s})

print(f"\nBURST name-days: {len(results)} | CONTROL (observed>=30min, no burst): {len(controls)}")
for r in sorted(results, key=lambda x: -(x["fwd_eod"] or -99)):
    print(f'  BURST {r["day"][-5:]} {r["tk"]:6s} +{r["burst_pct"]}% @{r["utc"]}UTC  '
          f'fwd60 {r["fwd60"] and round(r["fwd60"],1)}%  fwdEOD {r["fwd_eod"] and round(r["fwd_eod"],1)}%  obs {r["obs_s"]//60}m')
def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None
print(f'burst   median fwd60 {med([r["fwd60"] for r in results])}%  fwdEOD {med([r["fwd_eod"] for r in results])}%')
print(f'control median fwd60 {med([c["fwd60"] for c in controls])}%  fwdEOD {med([c["fwd_eod"] for c in controls])}%  (n={len(controls)})')
print("CAVEATS: partial observation (roster-capped), crude control anchor (median observed second), 2 days.")
