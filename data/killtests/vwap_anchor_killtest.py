"""VWAP ANCHOR KILL-TEST (Marcos 7/22): premarket-anchored vs RTH-anchored — who's right
IN THE DISAGREEMENT BAND? For every archived name-day with premarket data (plain + __ext pair):
walk RTH minutes computing BOTH anchors cumulatively; classify each sampled minute:
  above-both / IN-BAND (above PM-anchor, below RTH-anchor) / inv-band (below PM, above RTH) / below-both
(band counted only when |anchors| differ >=1%); forward return = close 30 min later.
If IN-BAND forward returns resemble above-both -> the PM anchor's "front-side" call is right where
it matters; if they resemble below-both -> RTH anchor challenged our doctrine. Sampling: every 5th
RTH minute (autocorrelation guard). Days 7/14-7/17 (most recent 4 archived pair-days, 490 pairs)."""
import json, urllib.request, urllib.parse, time, statistics as st

U = "https://zestful-intuition-production-b16a.up.railway.app"
def get(p, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(U + p, timeout=25) as r: return json.load(r)
        except Exception:
            time.sleep(2 + 2 * i)
    return {}
def F(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

arch = (get("/api/bars") or {}).get("archived") or {}
DAYS = ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]
cohorts = {"above_both": [], "IN_BAND (PM says front, RTH says back)": [],
           "inv_band (PM back, RTH front)": [], "below_both": []}
pairs_done = skipped = 0
for d in DAYS:
    fs = set(arch.get(d) or [])
    names = [f for f in fs if not f.endswith("__ext") and "~" not in f and f + "__ext" in fs]
    for t in names:
        rth_all = (get(f"/api/bars?date={d}&ticker={urllib.parse.quote(t)}") or {}).get("bars") or []
        ext_all = (get(f"/api/bars?date={d}&ticker={urllib.parse.quote(t)}&ext=1") or {}).get("bars") or []
        # archive files hold MULTI-DAY rolling windows (harness bug #2) — filter to target day;
        # times are UTC: RTH = 13:30-19:59, premarket < 13:30
        rth = [b for b in rth_all if str(b.get("time","")).startswith(d)
               and "13:30" <= str(b.get("time",""))[11:16] < "20:00"]
        if len(rth) < 90: skipped += 1; continue
        rth.sort(key=lambda x: str(x.get("time", "")))
        pre = [b for b in ext_all if str(b.get("time","")).startswith(d)
               and str(b.get("time", ""))[11:16] < "13:30"]
        if len(pre) < 10: skipped += 1; continue   # need real PM tape for the anchors to differ
        pv_pm = vol_pm = 0.0
        for b in pre:
            v = F(b.get("volume")); tp = (F(b.get("high")) + F(b.get("low")) + F(b.get("close"))) / 3
            if v > 0 and tp > 0: pv_pm += tp * v; vol_pm += v
        if vol_pm <= 0: skipped += 1; continue
        pv_r = vol_r = 0.0
        closes = [F(b.get("close")) for b in rth]
        n = len(rth)
        for i, b in enumerate(rth):
            v = F(b.get("volume")); tp = (F(b.get("high")) + F(b.get("low")) + F(b.get("close"))) / 3
            if v > 0 and tp > 0: pv_r += tp * v; vol_r += v
            if vol_r <= 0: continue
            vw_rth = pv_r / vol_r
            vw_pm = (pv_pm + pv_r) / (vol_pm + vol_r)
            px = closes[i]
            if px <= 0 or i % 5 or i + 30 >= n: continue   # sample every 5th minute w/ 30m ahead
            fwd = (closes[i + 30] - px) / px * 100
            band = abs(vw_rth - vw_pm) / px
            above_pm, above_rth = px > vw_pm, px > vw_rth
            if above_pm and above_rth: cohorts["above_both"].append(fwd)
            elif not above_pm and not above_rth: cohorts["below_both"].append(fwd)
            elif band >= 0.01:
                if above_pm: cohorts["IN_BAND (PM says front, RTH says back)"].append(fwd)
                else: cohorts["inv_band (PM back, RTH front)"].append(fwd)
        pairs_done += 1
print(f"pairs analyzed {pairs_done}, skipped {skipped} (thin RTH or no PM tape) — days {DAYS}")
print(f"{'cohort':42s} {'n':>6s} {'mean fwd30%':>11s} {'median':>8s} {'win%':>5s}")
for k, v in cohorts.items():
    if not v: print(f"{k:42s}  none"); continue
    w = sum(1 for x in v if x > 0)
    print(f"{k:42s} {len(v):6d} {sum(v)/len(v):+11.3f} {st.median(v):+8.3f} {100*w/len(v):5.1f}")
print("""
READ: if IN_BAND mean/median tracks above_both -> premarket anchor correct in the fight zone
(doctrine holds); if it tracks below_both -> RTH anchor wins and doctrine needs revisit.
inv_band (price above RTH line but below PM line) is the mirror check.""")
