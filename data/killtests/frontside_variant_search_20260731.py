"""RECOVER THE FROZEN METRIC BY VARIANT SEARCH (7/31 — phase-1 abort follow-up).

The 136-row discovery artifact is ground truth. The scoring script is lost. This searches the
definitional space until one variant reproduces the artifact; that variant IS the frozen metric
(the artifact is the spec — this is reconstruction, not fitting a hypothesis to outcomes, because
the artifact's P&L column is never consulted during the search).

AXES:
  scope    : bars from full session (pre incl.) vs RTH-only (09:30+)
  vanchor  : session VWAP from first tape tick vs RTH-anchored (09:30)
  align    : 3-min buckets on epoch%180 vs anchored to 09:30
  health   : close >= ema AND >= vwap   vs   close >= vwap only   vs  close >= ema only
  emaseed  : first close  vs  SMA of first 9
  defscope : defenses within the current streak vs whole day
Match target: artifact columns (streak, defenses) exact, >= 95% of computable rows.
"""
import json, pathlib, itertools, sys
import harness

ART = pathlib.Path(__file__).parent / "frontside_rows"
disc = json.load(open(ART / "frontside_rows.json"))
print(f"artifact rows: {len(disc)}")

# preload tape once per (tk, d)
tapes = {}
for row in disc:
    d, tk = row[0], row[1]
    if (tk, d) not in tapes:
        tapes[(tk, d)] = harness.bars(tk, d)
print(f"tapes loaded: {len(tapes)} ({sum(1 for v in tapes.values() if v)} non-empty)")

def compute(tk, d, hm_fire, scope, vanchor, align, health_mode, emaseed, defscope):
    b10 = tapes[(tk, d)]
    if not b10: return None
    if scope == "rth":
        b10 = [x for x in b10 if x[6] >= "09:30:00"]
        if not b10: return None
    fire_epoch = None
    for x in b10:
        if x[6][:5] >= hm_fire:
            fire_epoch = x[0]; break
    if fire_epoch is None: return None
    pv = vv = 0.0; vw = {}
    src = b10 if vanchor == "same" else [x for x in b10 if x[6] >= "09:30:00"]
    for k, o, h, l, c, v, hm in src:
        pv += ((h + l + c) / 3.0) * v; vv += v
        vw[k] = pv / vv if vv > 0 else c
    base = None
    if align == "930":
        r = [x for x in b10 if x[6] >= "09:30:00"]
        base = r[0][0] if r else b10[0][0]
    agg = []
    cur = None
    for k, o, h, l, c, v, hm in b10:
        off = (k - base) if base is not None else k
        bucket = off - (off % 180)
        if cur is None or cur["b"] != bucket:
            if cur: agg.append(cur)
            cur = {"b": bucket, "k_end": k, "o": o, "h": h, "l": l, "c": c, "v": v}
        else:
            cur["h"] = max(cur["h"], h); cur["l"] = min(cur["l"], l)
            cur["c"] = c; cur["v"] += v; cur["k_end"] = k
    if cur: agg.append(cur)
    agg = [x for x in agg if x["k_end"] < fire_epoch]
    if len(agg) < 3: return None
    closes = [x["c"] for x in agg]
    if emaseed == "sma" and len(closes) >= 9:
        e = sum(closes[:9]) / 9; emas = [e] * 9
        for c in closes[9:]:
            e = c * 0.2 + e * 0.8; emas.append(e)
    else:
        e = closes[0]; emas = [e]
        for c in closes[1:]:
            e = c * 0.2 + e * 0.8; emas.append(e)
    vws = []
    for x in agg:
        vws.append(vw.get(x["k_end"]))
    def ok(i):
        if vws[i] is None: return False
        if health_mode == "both":  return closes[i] >= emas[i] and closes[i] >= vws[i]
        if health_mode == "vwap":  return closes[i] >= vws[i]
        return closes[i] >= emas[i]
    healthy = [ok(i) for i in range(len(agg))]
    streak = 0
    for i in range(len(agg) - 1, -1, -1):
        if healthy[i]: streak += 1
        else: break
    rng = range(len(agg) - streak, len(agg)) if defscope == "streak" else range(len(agg))
    defenses = sum(1 for i in rng if healthy[i] and vws[i] is not None and agg[i]["l"] <= vws[i])
    return streak, defenses

results = []
for scope, vanchor, align, hm_mode, seed, ds in itertools.product(
        ("full", "rth"), ("same", "rth"), ("epoch", "930"), ("both", "vwap", "ema"),
        ("first", "sma"), ("streak", "day")):
    hits = n = 0
    for row in disc:
        d, tk, s_ref, d_ref, pnl, hm = row
        m = compute(tk, d, hm, scope, vanchor, align, hm_mode, seed, ds)
        if m is None: continue
        n += 1
        if m == (s_ref, d_ref): hits += 1
    results.append((hits / max(n, 1), hits, n, (scope, vanchor, align, hm_mode, seed, ds)))
results.sort(reverse=True)
print("\ntop 8 variants:")
for rate, hits, n, cfg in results[:8]:
    print(f"  {rate*100:5.1f}%  ({hits}/{n})  scope={cfg[0]} vanchor={cfg[1]} align={cfg[2]} "
          f"health={cfg[3]} seed={cfg[4]} defscope={cfg[5]}")
best = results[0]
if best[0] >= 0.95:
    print(f"\nMATCH FOUND: {best[3]} at {best[0]*100:.1f}% — this IS the frozen metric.")
    json.dump({"variant": best[3], "rate": best[0]},
              open(pathlib.Path(__file__).with_name("frontside_variant_FROZEN.json"), "w"))
else:
    print(f"\nNO VARIANT reaches 95% (best {best[0]*100:.1f}%). Show near-miss diagnostics:")
    cfg = best[3]
    shown = 0
    for row in disc:
        d, tk, s_ref, d_ref, pnl, hm = row
        m = compute(tk, d, hm, *cfg)
        if m and m != (s_ref, d_ref) and shown < 10:
            print(f"    {tk:<6}{d} {hm}  ref=({s_ref},{d_ref})  got={m}")
            shown += 1
