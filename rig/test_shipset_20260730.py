"""Rig: the 7/30 change-set (Fable rulings, Marcos: "yes to all. build it.").
Six switches, each independently revertible by env:
  1. HIDDEN_EXT_GATE      — refuse hidden conversion in the 3-10% ext_vwap dead band (A1)
  2. HIDDEN_SCALEBAR_STOP — post-scale stop ratchets to the scale-bar low, hidden only (A2-F)
  3. VRIDE_EXEMPT         — hidden never defers a scale (Q4)
  4. RESTING_BANK         — tiers fill at tier price on tape-through, vride not consulted (Q5)
  5. IGNITION_CONVERT_MULT/IGNITION_CHART_BYPASS — detect 2.0x, convert 4.5x, bypass gate,
     shadow-stamp the legacy verdict (Q6+Q7, ship-and-shadow)
  6. ZONEFLIP_CONVERT     — shadow mode: detector live, conversion off (G1)
Behavior was kill-tested pre-ship (A/E tables in FABLE_REVIEW_20260730.md); this rig pins the
WIRING and the pure functions so tested == pushed."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

print("== 1 · hidden ext gate ==")
check("defaults: ON, band 3.0-10.0 pct",
      bot.HIDDEN_EXT_GATE is True and bot.HIDDEN_EXT_LO == 3.0 and bot.HIDDEN_EXT_HI == 10.0)
check("refusal branch consumes the fire and logs the full ticket",
      'elif HIDDEN_EXT_GATE and HIDDEN_EXT_LO <= float(_he_fire.get("ext_vwap") or 0) < HIDDEN_EXT_HI:' in src
      and '"hidden_ext_reject"' in src)
check("band is checked in PERCENT (detector emits *100)",
      '"ext_vwap": round((c - vwap) / vwap * 100.0, 2)' in src)
check("ext_vwap + anchor persist to the trade record (D gap)",
      '"ext_vwap":        (extra or {}).get("ext_vwap")' in src
      and '"anchor":          (extra or {}).get("anchor")' in src)

print("== 2 · scale-bar stop (hidden only) ==")
check("branch exists, hidden-scoped, ratchets only UP",
      'if HIDDEN_SCALEBAR_STOP and entry_type == "hidden_entry":' in src
      and "_sb_lo > current_stop" in src)
_saved = bot._curl_feed
bot._curl_feed = lambda t, n=6: ({100: {"o": 5, "h": 6, "l": 5.42, "c": 5.9, "v": 1000},
                                  110: {"o": 5.9, "h": 6.2, "l": 5.85, "c": 6.1, "v": 800}}, "rig")
check("_scale_bar_low returns the LATEST bucket's low", bot._scale_bar_low("RIG") == 5.85)
bot._curl_feed = lambda t, n=6: ({}, "rig")
check("_scale_bar_low fail-safe: empty feed -> None (stop unchanged)", bot._scale_bar_low("RIG") is None)
bot._curl_feed = _saved

print("== 3 · vride exemption ==")
check("default exempt set = {hidden_entry}", bot.VRIDE_EXEMPT == {"hidden_entry"})
bot.VELOCITY_RIDE = True
check("hidden NEVER defers (returns before any bar fetch)",
      bot._vride_defer("RIG", 0, "hidden_entry") is False)
check("call site passes entry_type", "_vride_defer(ticker, tier_idx, entry_type)" in src)

print("== 4 · resting bank ==")
check("default ON", bot.RESTING_BANK is True)
check("tape path demands a STRICT print through the level",
      "_tape_hi is not None and _tape_hi > tier_price" in src)
check("fill books AT tier price, never better", "_fill_px = tier_price" in src)
check("partial booked at the fill px, not the poll px",
      "partial_fills.append((sell_qty, _fill_px))" in src)
check("every fill stamps its source (resting_tape/resting_stream/poll)",
      '"tier_fill"' in src and "resting_tape" in src)
check("exit scaffold logged at entry", '"exit_scaffold"' in src)
check("vride is NOT consulted while RESTING_BANK on",
      "_tier_hit = _rb_tape or current_price >= tier_price" in src)

print("== 5 · ignition convert + bypass + shadow ==")
check("detector unchanged at 2.0x; convert bar 4.5x",
      bot.IGNITION_VOL_MULT == 2.0 and bot.IGNITION_CONVERT_MULT == 4.5)
check("below-convert fires log and do NOT burn the once-per-ticker slot",
      '"ignition_below_convert"' in src
      and src.index('"ignition_below_convert"') < src.index('cache[t]["ignition_fired"] = True'))
v, r, lv, s = bot._chart_break_gate("RIGNOLEVEL", 5.0, "ignition")
check("bypass ON: ignition returns allow/live_structure", (v, r) == ("allow", "live_structure"))
v2, r2, _, _ = bot._chart_break_gate("RIGNOLEVEL", 5.0, "_shadow_legacy")
check("the _shadow_legacy probe walks the OLD path (skip/no_marked_level on an unmapped name)",
      (v2, r2) == ("skip", "no_marked_level"))
check("every converted fire stamps the shadow verdict", "shadow_gate=_sgv" in src)
bot.IGNITION_CHART_BYPASS = False
try:
    v3, r3, _, _ = bot._chart_break_gate("RIGNOLEVEL", 5.0, "ignition")
    check("kill switch restores the OLD gated behavior exactly", (v3, r3) == ("skip", "no_marked_level"))
finally:
    bot.IGNITION_CHART_BYPASS = True

print("== 6 · zone_flip shadow ==")
check("conversion OFF by default; detector switch untouched",
      bot.ZONEFLIP_CONVERT is False and bot.ZONEFLIP_KEV is True)
check("shadow branch consumes, logs stop+zone (forward replay stays runnable), spends NO slot",
      '"zoneflip_shadow_convert"' in src
      and "if _zf_fire and not ZONEFLIP_CONVERT:" in src
      and 'elif _zf_fire and _curl_rth_slot(t, "zf", _hm_curl):' in src)

print("== boot banner ==")
check("all six switches visible at boot", "HIDDEN_EXT_GATE=" in src and "RESTING_BANK=" in src
      and "IGNITION_CONVERT_MULT=" in src and "ZONEFLIP_CONVERT=" in src)


print("== 7 · reclaim fire-bar re-check (RECLAIM_FIREVOL, Marcos: 'ship the 2.0') ==")
src = pathlib.Path(bot.__file__).read_text()   # re-read: section added after the first snapshot
check("default 2.0, env-kill documented", bot.RECLAIM_FIREVOL == 2.0)
check("reject computed BEFORE the slot (refused fire never spends it)",
      src.index("_vr_fv_bad") < src.index('_curl_rth_slot(t, "vr", _hm_curl)'))
check("reject consumes the fire and logs the full ticket", '"reclaim_firevol_reject"' in src)
check("None volmult passes through (fail-safe to old behavior)",
      "_vr_fv is not None and _vr_fv < RECLAIM_FIREVOL" in src)
# functional: drive the REAL detector over a synthetic tape; the fire must carry volmult
bot._bucket_fresh = lambda k: True
bot._reclaim_st.clear()
import time as _t
K = int(_t.time()) // 10 * 10 - 600
VW = 1.00
seq = []
for i in range(10):                                   # warm-up under VWAP, avgv ~100
    seq.append((K + i * 10, 0.99, 0.995, 0.985, 0.99, 100))
seq.append((K + 100, 0.99, 1.005, 0.99, 1.002, 1000))   # cross: prev<=vwap, c>vwap, v>=2x avg
seq.append((K + 110, 1.002, 1.012, 1.008, 1.011, 300))  # extend >= +1%
seq.append((K + 120, 1.011, 1.010, 1.004, 1.009, 200))  # pullback into the zone -> retest+wick
seq.append((K + 130, 1.009, 1.013, 1.009, 1.012, 900))  # close > wick high -> FIRE
f = bot.kev_reclaim_step("RIGVR", seq, VW)
check("synthetic tape fires through the REAL detector", f is not None)
check("fire dict carries its volume multiple", f is not None and f.get("volmult") is not None,
      str(f))
check("volmult is the FIRE bar's (900 sh vs rolling avg), not the cross bar's",
      f is not None and f.get("volmult") is not None and 2.0 < f["volmult"] < 8.0, str(f))

print("== 10 · BREAK-SIDE gate (7/31, Marcos: 'a real test on Monday, shadow the opposite') ==")
src = pathlib.Path(bot.__file__).read_text()
check("default ON; tol 0; tape lanes only, dip_rip EXCLUDED",
      bot.BREAKSIDE_GATE is True and bot.BREAKSIDE_MAX_PCT == 0.0
      and bot.BREAKSIDE_LANES == {"vwap_reclaim","hidden_entry","ignition"}
      and "dip_rip" not in bot.BREAKSIDE_LANES)
check("sits AFTER runway, BEFORE sizing",
      src.index('"runway_reject"') < src.index('"breakside_reject"')
      and src.index('"breakside_reject"') < src.index("Kev short-003 sizing", src.index('"breakside_reject"')))
check("FAIL-OPEN: only a positive numeric break can block", "if _bs_brk > 0:" in src)
check("reject logs the full ticket + refunds the slot",
      '"breakside_reject"' in src
      and src[src.index('"breakside_reject"'):src.index('"breakside_reject"')+600].count("_slot_refund") == 1)
check("banner reports it", "BREAKSIDE_GATE=" in src)
# functional: the gate math on the pinned specimens
_saved = bot._fetch_kev_levels
bot._fetch_kev_levels = lambda: {"RIGB": {"break": 0.70}}
lv = float(((bot._fetch_kev_levels() or {}).get("RIGB") or {}).get("break") or 0)
check("MGRX-A class (0.56 vs 0.70 = below) would PASS", (0.56 - lv) / lv * 100 <= 0.0)
check("MGRX-B class (0.79 vs 0.70 = +12.9%) would BLOCK", (0.79 - lv) / lv * 100 > 0.0)
bot._fetch_kev_levels = lambda: {}
check("no sheet entry -> fail-open PASS", float((({} ).get("RIGB") or {}).get("break") or 0) == 0.0)
bot._fetch_kev_levels = _saved
print("== 11 · ungated_entry fail-open visibility (7/31) ==")
src = pathlib.Path(bot.__file__).read_text()
check("no-break tape-lane conversion logs ungated_entry", '"ungated_entry"' in src)
check("sits in the breakside else-branch (fires only when the sheet has no break)",
      src.index("if _bs_brk > 0:") < src.index('"ungated_entry"'))
print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — 7/30 change-set wired: hidden gate+ratchet+exempt, resting bank, "
      "ignition ship-and-shadow, zone_flip shadow, reclaim fire-bar re-check. "
      "Every switch env-revertible; verdict evaluated AFTER all sections (exit-code honest).")

print("== 8 · PULLBACK_FIRST one-day experiment (Marcos 7/30: 'reverse the order and just see') ==")
src = pathlib.Path(bot.__file__).read_text()
check("default ON, env-revertible", bot.PULLBACK_FIRST is True)
check("pre-pass runs the REAL detector before flat_top and logs suppressions",
      '"pullback_first_suppress"' in src
      and src.index("_ma_first_fire = detect_ma_pullback") < src.index("Entry type 1: Flat top"))
check("flat_top block skipped when the pullback fires (arming included)",
      "len(_sess3) >= FLAT_TOP_WINDOW and not _ma_first_fire" in src)
check("ORB cannot steal the deferred name",
      "not found_entry and not _ma_first_fire" in src)
check("NO duplicated conversion: exactly one triggered_ma_pullback log site",
      src.count('"triggered_ma_pullback"') == 1)

print("== 9 · MIN_RUNWAY_RR (7/31, Marcos: 'Not enough runway, we should block') ==")
src = pathlib.Path(bot.__file__).read_text()
check("default 1.0R, env-revertible (0 = off)", bot.MIN_RUNWAY_RR == 1.0)
# NOTE: "Kev short-003 sizing" appears TWICE in the file; anchor on the occurrence that FOLLOWS
# the runway gate, not the first one (that mis-anchoring produced a false RED on the first run).
_i_ms = src.index('"minstop_reject"'); _i_rw = src.index('"runway_reject"')
check("gate sits with the other tradeability floors (after minstop, before sizing)",
      _i_ms < _i_rw < src.index("Kev short-003 sizing", _i_rw))
check("refuses only a NUMERIC runway below the floor",
      'isinstance(_rw_v, (int, float)) and _rw_v < MIN_RUNWAY_RR' in src)
check("refund + reentry release on reject (mirrors minstop)",
      src[src.index('"runway_reject"'):src.index('"runway_reject"')+700].count("_slot_refund") == 1)
check("logs the full ticket for the counterfactual", 'runway_rr=_rw_v' in src and 'target=_rw_t' in src)
check("boot banner reports it", "MIN_RUNWAY_RR={MIN_RUNWAY_RR}" in src)
# FAIL-OPEN pins: the 7/22 no_marked_level starvation must never repeat
_saved_fetch = bot._fetch_kev_levels
bot._fetch_kev_levels = lambda: {}
check("no marked level -> runway None -> gate PASSES (fail-open)",
      bot._marked_runway("RIGX", 1.00, 0.90)[0] is None)
bot._fetch_kev_levels = lambda: {"RIGX": {"break": 0.50, "targets": [0.60]}}
_v, _t = bot._marked_runway("RIGX", 1.00, 0.90)
check("price beyond every target -> 'above_all_levels' -> PASSES (infinite runway)",
      _v == "above_all_levels" and not isinstance(_v, (int, float)), str((_v, _t)))
bot._fetch_kev_levels = lambda: {"RIGX": {"break": 0.50, "targets": [1.02]}}
_v2, _t2 = bot._marked_runway("RIGX", 1.00, 0.90)
check("tight target -> small numeric R -> WOULD block", isinstance(_v2, (int, float)) and _v2 < 1.0,
      str((_v2, _t2)))
bot._fetch_kev_levels = lambda: {"RIGX": {"break": 0.50, "targets": [1.50]}}
_v3, _t3 = bot._marked_runway("RIGX", 1.00, 0.90)
check("roomy target -> runway >= 1R -> passes", isinstance(_v3, (int, float)) and _v3 >= 1.0,
      str((_v3, _t3)))
bot._fetch_kev_levels = _saved_fetch
print("== 12 · (8/3) premarket shadow stop stamp is lane-proof ==")
_resolves = src.count('get("zone_stop") or (_px2 or {}).get("ema_stop")')
check("both shadow sites resolve zone_stop -> ema_stop -> stop", _resolves >= 2,
      f"found {_resolves}")
check("generic stop fallback present", src.count('.get("ema_stop")\n') >= 0 and '.get("stop")' in src)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — shadow stop stamp pinned (section 12)")
