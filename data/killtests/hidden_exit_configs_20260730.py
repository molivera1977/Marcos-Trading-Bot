"""HIDDEN EXIT CONFIG SWEEP (7/30, Marcos: "why dont we try different configurations before
implementing BE and losing on those wiggles"). Walks the REAL tape bar-by-bar — no arithmetic
shortcuts — so the shake-out cost of each protection level is MEASURED, not assumed.

Same entries, same stops, same names. Only the post-first-scale protection differs.
Also reports SHAKEOUTS: trades stopped by the new protection that later traded higher (the cost
of protecting), and how much higher they went."""
import json, urllib.request
from datetime import datetime, timedelta, timezone
import harness
ET = timezone(timedelta(hours=-4))

TRIM = 0.33          # first scale fraction (hidden's live tier-1 size)
CONFIGS = [
    ("A none (live)",      None),   # no protection until the unreachable x1.50 rung
    ("B BE at entry",       0.00),   # stop -> entry
    ("C entry -0.25R",     -0.25),
    ("D entry -0.50R",     -0.50),
    ("E entry -0.75R",     -0.75),
    ("F scale-bar low",    "bar"),   # stop -> the low of the bar that filled the scale
]

rows = [r for r in (json.load(urllib.request.urlopen(f"{harness.U}/api/trades")).get("trades") or [])
        if isinstance(r, dict) and r.get("entry_type") == "hidden_entry" and str(r.get("date")) >= "2026-07-13"]

def walk(b, i0, e, s, prot):
    """Walk bars from entry. Sell TRIM at 1R (resting limit = intrabar touch), then apply `prot`
    to the remainder's stop. Returns (pnl_per_share_total, shaken, high_after_exit)."""
    R = e - s
    t1 = e + R
    rem, real, cur = 1.0, 0.0, s
    scaled_i = None
    for j in range(i0, len(b)):
        k, o, h, l, c, v, hm = b[j]
        if hm >= "15:45:00":
            return real + rem * (c - e), False, 0.0
        if rem < 1.0 and l <= cur:                       # protection (or stop) hit after the scale
            after = max((x[2] for x in b[j + 1:]), default=0)
            return real + rem * (cur - e), (after > cur * 1.005), after
        if rem == 1.0 and l <= cur:                      # stopped before ever scaling
            return real + rem * (cur - e), False, 0.0
        if scaled_i is None and h >= t1:
            real += TRIM * R; rem -= TRIM; scaled_i = j
            if prot is None:      pass                    # live: stop unchanged
            elif prot == "bar":   cur = max(cur, l)
            else:                 cur = max(cur, e + prot * R)
    return real + rem * (b[-1][4] - e), False, 0.0

print(f"{'config':18}{'n':>4}{'total $':>11}{'$/trade':>9}{'wins':>6}{'shaken':>8}{'left on table':>15}")
for label, prot in CONFIGS:
    tot = n = wins = shaken = 0; left = 0.0
    for r in rows:
        e, s, sh, d = r.get("entry"), r.get("stop_loss"), r.get("shares"), str(r.get("date"))
        if not (e and s and sh and e > s): continue
        try: t0 = datetime.fromisoformat(str(r.get("entry_ts_utc")).replace("Z", "+00:00")).astimezone(ET).strftime("%H:%M:%S")
        except Exception: continue
        b = harness.bars(r["ticker"], d)
        i0 = next((i for i, x in enumerate(b) if x[6] >= t0), None)
        if i0 is None: continue
        pps, shk, after = walk(b, i0, e, s, prot)
        pnl = pps * sh
        tot += pnl; n += 1; wins += (pnl > 0); shaken += shk
        if shk: left += (after - e) * sh * (1 - TRIM)
    print(f"{label:18}{n:4}{tot:11.2f}{tot/max(n,1):9.2f}{wins:6}{shaken:8}{left:15.2f}")
print("\n'shaken' = protection stopped the runner and price later traded >0.5% higher")
print("'left on table' = what that remainder would have been worth at the later high (upper bound)")
