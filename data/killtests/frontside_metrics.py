"""FRONT-SIDE MATURITY METRICS — FROZEN v2, IN-REPO (7/31).

The 7/29 discovery script lived in /tmp and is gone; reconstruction reached 85% agreement with its
saved artifact and verdict-stability across the top variants showed the 8/1 grade INCONCLUSIVE
(underpowered: best arm qualified 2 OOS fires vs the 8 required). Per Marcos ("status quo but
shadowing"), these definitions are DECLARED v2 AND FROZEN HERE — in code, versioned, never /tmp.
Next Friday's grade (frontside_grade_NEXT.py) computes from the ferried ALP10S archive using THIS
module. Any future change to these definitions is a new version with a ledger entry, not an edit.

v2 DEFINITIONS (= reconstruction variant V1, the top artifact-matcher at 85.0%):
  bars      : RTH-only 10s tape, aggregated to width_s buckets on epoch alignment
  VWAP      : cumulative session VWAP from the FULL tape (premarket included), read at each
              bucket's last 10s tick
  EMA9      : over aggregated closes, seeded on the first close (k = 0.2)
  health(i) : close_i >= EMA9_i AND close_i >= VWAP_i
  streak    : consecutive healthy buckets ending at the last completed bucket before the fire
  defense   : within the current streak, a bucket whose LOW touched VWAP (low <= vwap) and which
              still closed healthy
  triple    : consecutive buckets with higher-high AND higher-low AND rising volume, at the fire
ARMS (thresholds unchanged from the 7/29 registration):
  A: metrics(180).streak >= 6 and defenses >= 2
  B: metrics(180).triple >= 2
  C: metrics(300).streak >= 3 and defenses >= 2
"""

def metrics_at(b10_full, hm_fire, width_s):
    """b10_full: harness-format 10s bars [(epoch,o,h,l,c,v,'HH:MM:SS'),...] for the whole session.
    hm_fire: 'HH:MM' of the fire. Returns (streak, defenses, triple) or None."""
    if not b10_full:
        return None
    b10 = [x for x in b10_full if x[6] >= "09:30:00"]
    if not b10:
        return None
    fire = next((x[0] for x in b10 if x[6][:5] >= hm_fire), None)
    if fire is None:
        return None
    pv = vv = 0.0
    vw = {}
    for k, o, h, l, c, v, hm in b10_full:                 # session VWAP, premarket included
        pv += ((h + l + c) / 3.0) * v
        vv += v
        vw[k] = pv / vv if vv > 0 else c
    agg, cur = [], None
    for k, o, h, l, c, v, hm in b10:
        bkt = k - (k % width_s)
        if cur is None or cur["b"] != bkt:
            if cur:
                agg.append(cur)
            cur = {"b": bkt, "k": k, "h": h, "l": l, "c": c, "v": v}
        else:
            cur["h"] = max(cur["h"], h)
            cur["l"] = min(cur["l"], l)
            cur["c"] = c
            cur["v"] += v
            cur["k"] = k
    if cur:
        agg.append(cur)
    agg = [x for x in agg if x["k"] < fire]
    if len(agg) < 3:
        return None
    closes = [x["c"] for x in agg]
    e = closes[0]
    emas = [e]
    for c in closes[1:]:
        e = c * 0.2 + e * 0.8
        emas.append(e)
    vws = [vw.get(x["k"]) for x in agg]
    healthy = [(vws[i] is not None and closes[i] >= emas[i] and closes[i] >= vws[i])
               for i in range(len(agg))]
    streak = 0
    for i in range(len(agg) - 1, -1, -1):
        if healthy[i]:
            streak += 1
        else:
            break
    rng = range(len(agg) - streak, len(agg))
    defenses = sum(1 for i in rng
                   if healthy[i] and vws[i] is not None and agg[i]["l"] <= vws[i])
    triple = 0
    for i in range(len(agg) - 1, 0, -1):
        if (agg[i]["h"] > agg[i - 1]["h"] and agg[i]["l"] > agg[i - 1]["l"]
                and agg[i]["v"] > agg[i - 1]["v"]):
            triple += 1
        else:
            break
    return streak, defenses, triple


def arm_verdicts(b10_full, hm_fire):
    """{'A': bool|None, 'B': bool|None, 'C': bool|None} for one fire."""
    m3 = metrics_at(b10_full, hm_fire, 180)
    m5 = metrics_at(b10_full, hm_fire, 300)
    return {
        "A": (m3[0] >= 6 and m3[1] >= 2) if m3 else None,
        "B": (m3[2] >= 2) if m3 else None,
        "C": (m5[0] >= 3 and m5[1] >= 2) if m5 else None,
        "m3": m3, "m5": m5,
    }
