"""Rig: STALE-FIRE GUARD (7/28, Fable-ruled after the LVWR 07:27 trace).

Spec: detection may replay history (state machines need it); ACTION may not — a fire on a 10s
bar older than CURL_FIRE_MAX_AGE_SECS is suppressed, consumed (state resets exactly as a fire
would), and logged. Cursor seeding was REJECTED (it would skip state-building for newcomers).
The LVWR case: a ~15-min replay after the 07:25 deploy fired a reclaim whose setup was long
finished — with entries on, that converts a dead signal into a live entry.
"""
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

logged = []
_orig = bot._log_decision
bot._log_decision = lambda t, s, **kw: logged.append((t, s, kw))

def reclaim_seq(sym, vwap, buckets):
    """Drive kev_reclaim_step through a full seek->extend->retest->curl at given bucket times.
    bars: (k, o, h, l, c, v)"""
    NOW = time.time()
    b = []
    ks = iter(buckets)
    def bar(o, h, l, c, v):
        return (next(ks), o, h, l, c, v)
    # seek: cross above vwap on 2x vol (need prior bar below)
    b.append(bar(9.0, 9.4, 8.9, 9.4, 100))     # below vwap(10) — seeds prev_c + vols
    b.append(bar(9.5, 10.4, 9.4, 10.3, 300))   # cross above on 3x vol -> extend
    b.append(bar(10.3, 10.3, 10.1, 10.2, 100)) # >= vwap*1.01 -> ext=True
    b.append(bar(10.2, 10.2, 10.02, 10.1, 100))# dips to vwap*1.005 -> retest
    b.append(bar(10.1, 10.2, 10.03, 10.15, 100)) # wick: low at line, close upper half
    b.append(bar(10.2, 10.6, 10.18, 10.5, 200))  # close > wick high -> FIRE bar
    return bot.kev_reclaim_step(sym, b, vwap)

print("== reclaim: fresh buckets FIRE ==")
NOW = time.time()
fresh = [NOW - 60, NOW - 50, NOW - 40, NOW - 30, NOW - 20, NOW - 10]
logged.clear(); bot._reclaim_st = getattr(bot, "_reclaim_st", {})
bot._reclaim_st.clear() if hasattr(bot, "_reclaim_st") else None
f = reclaim_seq("FRSH", 10.0, fresh)
check("fresh sequence fires", f is not None and f.get("px") == 10.5, f"got {f}")
check("fire carries its bucket k", f is not None and abs(f.get("k", 0) - (NOW - 10)) < 1)
check("no suppression logged", not any(s == "stale_fire_suppressed" for _, s, _ in logged))

print("== reclaim: the LVWR replay (15-min-old bars) is SUPPRESSED + consumed + logged ==")
logged.clear()
stale = [NOW - 960, NOW - 950, NOW - 940, NOW - 930, NOW - 920, NOW - 910]
f2 = reclaim_seq("STAL", 10.0, stale)
check("stale sequence does NOT fire", f2 is None, f"got {f2}")
sup = [(t, s, kw) for t, s, kw in logged if s == "stale_fire_suppressed"]
check("suppression logged with lane + age", len(sup) == 1 and sup[0][2].get("lane") == "vwap_reclaim"
      and sup[0][2].get("bar_age_s", 0) > 800, f"got {sup}")
check("setup consumed (seq advanced)", bot._reclaim_st["STAL"]["n"] == 1
      and bot._reclaim_st["STAL"]["phase"] == "seek")

print("== reclaim: replay builds state, FRESH tail still fires (the newcomer case) ==")
logged.clear()
mixed = [NOW - 900, NOW - 890, NOW - 880, NOW - 870, NOW - 30, NOW - 10]
f3 = reclaim_seq("MIXD", 10.0, mixed)
check("old bars built the setup, fresh curl fires", f3 is not None and f3.get("px") == 10.5, f"got {f3}")

print("== boundary: 90s default, env-tunable ==")
check("default is 90", bot.CURL_FIRE_MAX_AGE_SECS == 90.0)
check("89s-old bucket is fresh", bot._bucket_fresh(NOW - 89))
check("91s-old bucket is stale", not bot._bucket_fresh(NOW - 91))
check("k=0/None never fresh", not bot._bucket_fresh(0) and not bot._bucket_fresh(None))

print("== hidden + zone_flip + ignition10s carry the same guard (source assertions) ==")
src = pathlib.Path(bot.__file__).read_text()
for lane, marker in [("hidden_entry", '_log_stale_fire(sym, "hidden_entry"'),
                     ("zone_flip", '_log_stale_fire(sym, "zone_flip"'),
                     ("ignition10s", '_log_stale_fire(sym, "ignition10s"')]:
    check(f"{lane} guard wired", marker in src)
check("reclaim feed now carries the bucket", '_nb.append((_k, _b["o"]' in src)
check("hidden unpacks 6-tuples", "for k, o, h, l, c, v in new_bars:   # 7/28" in src)

print("== conversions stamp fire_px / fire_age_s / drift_pct (Fable: stamp, don't gate) ==")
for m in ('"triggered_vwap_reclaim_kev3gate"', '"triggered_zone_flip"', '"triggered_hidden_entry"'):
    i = src.find(m)
    seg = src[i:i + 600]
    check(f"{m} carries the drift stamps", "fire_px=" in seg and "drift_pct=" in seg and "fire_age_s=" in seg)
check("NO drift-based rejection anywhere (held for Friday)", "drift_reject" not in src
      and "DRIFT_MAX" not in src)

bot._log_decision = _orig
print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — stale-fire guard: replay detects, never acts; suppressions visible; drift stamped not gated")
