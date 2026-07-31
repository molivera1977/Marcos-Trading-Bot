"""HIDDEN QUALITY IN DOLLARS (7/30). Same 190 fires, but each one run through the HONEST HARNESS:
real sizing chain (risk/cap/volume guard), real ladder, calibrated slippage. Then cut by the
extension bands the hit-rate study surfaced. Hit rate is not dollars — this is the test that counts.

Ladder used = hidden's LIVE percentage tiers (33%@1R, x1.50, x2.00) so the cells describe the lane
as it actually trades. A second pass uses the best exit config from the sweep (F: stop -> scale-bar
low after the first scale) to see whether the entry finding survives a fixed exit."""
import json, urllib.request, collections
from datetime import datetime, timedelta, timezone
import harness
ET = timezone(timedelta(hours=-4))
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")
BANDS = [(-99, 0, "<0"), (0, 1, "0-1%"), (1, 2, "1-2%"), (2, 3, "2-3%"),
         (3, 5, "3-5%"), (5, 10, "5-10%"), (10, 999, "10%+")]

def hidden_walk(b, i0, e, s, prot):
    """Hidden's live ladder: 33% at 1R (intrabar), then x1.50 (55% cum), x2.00 (75% cum).
    prot: None = live (no protection until the x1.50 rung) | 'bar' = stop to scale-bar low."""
    R = e - s
    tiers = [(e + R, 0.33), (e * 1.50, 0.55), (e * 2.00, 0.75)]
    rem, real, cur, cum = 1.0, 0.0, s, 0.0
    for j in range(i0, len(b)):
        k, o, h, l, c, v, hm = b[j]
        if hm >= "15:45:00":
            return real + rem * (c - e)
        if l <= cur:
            fill = cur - (harness.SLIP_PCT * e if cur <= s + 1e-9 else 0.0)
            return real + rem * (fill - e)
        for tp, tc in tiers:
            if h >= tp and tc > cum:
                q = tc - cum; real += q * (tp - e); rem -= q; cum = tc
                if prot == "bar" and cum >= 0.33:
                    cur = max(cur, l)
        if rem <= 1e-9:
            return real
    return real + rem * (b[-1][4] - e)

fires = []
for d in DAYS:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") != "hidden_shadow_fire": continue
        px, stop = r.get("price"), r.get("stop")
        if not (px and stop and px > stop): continue
        fires.append({"d": d, "tk": r.get("ticker"), "t": str(r.get("recorded_at"))[11:19],
                      "px": float(px), "stop": float(stop), "ext": r.get("ext_vwap")})

res = []
for f in fires:
    b = harness.bars(f["tk"], f["d"])
    i0 = next((i for i, x in enumerate(b) if x[6] >= f["t"]), None)
    if i0 is None: continue
    sh, clamp, det = harness.size(f["px"], f["stop"], b, i0)
    if sh == 0: continue
    f["sh"] = sh
    f["live"] = hidden_walk(b, i0, f["px"], f["stop"], None) * sh
    f["fixed"] = hidden_walk(b, i0, f["px"], f["stop"], "bar") * sh
    res.append(f)

print(f"fires priced through the honest harness: {len(res)}\n")
for label, key in (("LIVE ladder (33%@1R, x1.50, x2.00 — no protection until x1.50)", "live"),
                   ("FIXED exit (same + stop -> scale-bar low after the first scale)", "fixed")):
    print(f"== {label}")
    print(f"   {'band':10}{'n':>5}{'total $':>11}{'$/fire':>9}{'wins':>7}")
    tot = 0.0
    for lo, hi, name in BANDS:
        g = [f for f in res if f.get("ext") is not None and lo <= f["ext"] < hi]
        if len(g) < 5: continue
        s = sum(f[key] for f in g); tot += s
        print(f"   {name:10}{len(g):5}{s:11.2f}{s/len(g):9.2f}{sum(1 for f in g if f[key]>0):7}")
    all_s = sum(f[key] for f in res)
    print(f"   {'ALL':10}{len(res):5}{all_s:11.2f}{all_s/len(res):9.2f}{sum(1 for f in res if f[key]>0):7}")
    # the proposed gate: drop the 3-10% dead zone
    keep = [f for f in res if not (f.get("ext") is not None and 3 <= f["ext"] < 10)]
    ks = sum(f[key] for f in keep)
    print(f"   {'GATED':10}{len(keep):5}{ks:11.2f}{ks/max(len(keep),1):9.2f}{sum(1 for f in keep if f[key]>0):7}   (refuse 3-10% extension)")
    print()
