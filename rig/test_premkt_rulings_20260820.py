#!/usr/bin/env python3
"""
RIG GATE 28 — THE 8/20 PREMARKET + OPENING-BLOCK RULINGS

Marcos, 8/20 after the capital-aware ladders: "I dont want a cap on pre if it can make money.
I am never for a cap" · "all three pre decisions finalized" · "keep v2conv in pre and record
the ruling" · "does v2conv need to be seated in RTH 9:30 to 10:30?" · "perhaps we need to
separate roster orders for the different time blocks" · "go with what the data says".

THE CLASS THIS CLOSES. Three live thresholds were justified on $/TRADE and, re-measured on
TOTAL DOLLARS with capital modeled and no trade cap, were destroying money. The same
arithmetic error appeared twice in one session's advice, so these pins state BOTH numbers.

PINS
  A1 PRE_MAX_TRADES default 0 (= unlimited) and every enforcement site honours 0
  A2 PRE_MIN_DVOL default 50000 (ladder: $0 +$6,071 · $50k +$5,954 · $250k +$4,894 · $1M +$3,725)
  A3 the dvol measure is CUMULATIVE by bucket key, deep-seeded once per name, kill-switched
  A4 the live gate calls _pm_session_dvol, NOT a raw sum over a 15-min window
  A5 premarket min-stop floor = PRE_MIN_STOP_PCT (1.0), RTH keeps MIN_STOP_DIST_PCT untouched
  A6 v2conv holds a TIME-WINDOWED RTH seat 09:30-10:30 (not a flat RTH_LANES entry)
  A7 the opening block has its own roster with ignition AHEAD of v2conv (the 324-contest
     head-to-head refuted seating v2conv first: it fired first on only 47/324 and lost the
     contested cohort +$4,353.61 vs +$8,642.60, on BOTH halves)
  A8 HONESTY: v2conv is NOT in the flat RTH_LANES list (its seat is the window, or nothing)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


check("A1 PRE_MAX_TRADES default 0 = unlimited",
      'PRE_MAX_TRADES = int(os.environ.get("PRE_MAX_TRADES", "0"))' in SRC
      and 'PRE_MAX_TRADES <= 0 or _pre_day["n"] < PRE_MAX_TRADES' in SRC
      and 'PRE_MAX_TRADES > 0 and _pre_day["n"] >= PRE_MAX_TRADES' in SRC
      and 'cap_full=bool(PRE_MAX_TRADES > 0 and _pre_day["n"] >= PRE_MAX_TRADES)' in SRC)
check("A2 PRE_MIN_DVOL default 50000",
      'PRE_MIN_DVOL = float(os.environ.get("PRE_MIN_DVOL", "50000"))' in SRC)
check("A3 cumulative-by-bucket measure, seeded, kill-switched",
      "def _pm_session_dvol(" in SRC
      and "acc[int(k)] =" in SRC
      and 'PM_DVOL_CUMULATIVE = os.environ.get("PM_DVOL_CUMULATIVE", "1") == "1"' in SRC
      and "if not PM_DVOL_CUMULATIVE:" in SRC
      and "_curl_feed(sym, n=PM_DVOL_SEED_BARS)" in SRC)
_i = SRC.find("_pm_dvol = 0.0")
check("A4 the gate uses _pm_session_dvol (not the 15-min raw sum)",
      _i != -1 and "_pm_session_dvol(entry[0], _d10pm)" in SRC[_i:_i + 400]
      and "sum((b.get(\"c\") or 0) * max((b.get(\"v1\") or 0)" not in SRC[_i:_i + 400])
# 8/20 #6 amendment: PRE-ness now comes from the CALLER (is_premkt <- the _pre_convert
# conversion stamp), never the wall clock — the auditor proved a 09:29 fire crossing 09:30 in
# the worker flipped floors. Default False keeps every legacy/rig call deterministic RTH.
check("A5 premarket stop floor separate; RTH untouched; PRE-ness from the conversion stamp",
      'PRE_MIN_STOP_PCT = float(os.environ.get("PRE_MIN_STOP_PCT", "1.0"))' in SRC
      and "_need = PRE_MIN_STOP_PCT if is_premkt else MIN_STOP_DIST_PCT * 100.0" in SRC
      and 'entry_type=None, is_premkt=False' in SRC
      and '_ms_pre = bool((extra or {}).get("_pre_convert"))' in SRC
      and "floor=_ms_floor, pre=_ms_pre" in SRC)
# 8/20 Fable review: the v2conv seat is SUSPENDED — its evidence ran at a 1% floor and RTH
# runs 4%; re-measured AT 4% it fails the both-halves bar (train +$2.64/tr vs OOS +$25.48/tr,
# 72% of value refused). The MECHANISM ships inert (defaults "") and these pins EXECUTE it —
# Blast Radius #9 proved the string-match version was green while the try/except swallowed a
# NameError and the branch never ran. A pin that lies is worse than no pin.
import os as _os
_ns = {"os": _os}
for _fn in ("_lane_window_ok", "_lane_rank"):
    _i = SRC.find(f"\ndef {_fn}(")
    _j = SRC.find("\ndef ", _i + 1)
    _ns_src = SRC[_i:_j]
    exec(compile(_ns_src, _fn, "exec"), _ns)
_ns.setdefault("LANE_WINDOWS", {})            # start empty; armed case exercised below
_ns["PRE_LANE_RANK"] = ["ignition", "v2conv", "vwap_reclaim", "ma_pullback"]
_ns["OPEN_LANE_RANK"] = []                    # start empty; armed case exercised below
_ns["OPEN_BLOCK"] = ("09:30", "10:30")
_ns["LANE_RANK"] = ["ignition", "hidden_v2", "ema9x90", "ma_pullback"]
_ns["ENTRY_OPEN_ET"] = "07:00"
check("A6a mechanism EXECUTED: an un-windowed lane is never window-seated",
      _ns["_lane_window_ok"]("v2conv", "09:45") is False)
_ns["LANE_WINDOWS"]["v2conv"] = ("09:30", "10:30")
check("A6b mechanism EXECUTED: armed window seats v2conv 09:45, not 10:30, not kevseq",
      _ns["_lane_window_ok"]("v2conv", "09:45") is True
      and _ns["_lane_window_ok"]("v2conv", "10:30") is False
      and _ns["_lane_window_ok"]("kevseq", "09:45") is False)
check("A7a roster EXECUTED: empty block roster -> LANE_RANK everywhere (the kill-switch path)",
      _ns["_lane_rank"]("hidden_v2", "09:45") == 1
      and _ns["_lane_rank"]("kevseq", "09:45") == _ns["_lane_rank"]("kevseq", "11:00") == 5)
# 8/20 LATER: Marcos settled the RTH floor at 1% — the suspension's named condition — and
# ordered the seat in ("which then means v2conv moves in to the first RTH hour") with the
# roster set by COMPETITION at the 1% floor (ignition +$18.65/fill > v2conv +$12.90 >
# kevseq +$12.31 > hidden_v2 +$10.88, all both-halves; unreplayable ema9x90/ma_pullback
# follow the measured four). These pins exercise the SHIPPED armed defaults.
_ns["OPEN_LANE_RANK"] = ["ignition", "v2conv", "kevseq", "hidden_v2", "ema9x90", "ma_pullback"]
check("A7b roster EXECUTED: contest order in-block (v2conv #2, hidden_v2 #4), other hours unchanged",
      _ns["_lane_rank"]("v2conv", "09:45") == 1
      and _ns["_lane_rank"]("kevseq", "09:45") == 2
      and _ns["_lane_rank"]("hidden_v2", "09:45") == 3
      and _ns["_lane_rank"]("hidden_v2", "11:00") == 1
      and _ns["_lane_rank"]("v2conv", "11:00") == 5
      and _ns["_lane_rank"]("v2conv", "08:00") == 1)
check("A7c wiring: whitelist consults the window; seat + roster ARMED in the shipped defaults",
      "_b[3] in RTH_LANES or _lane_window_ok(_b[3], _rl_now)" in SRC
      and 'os.environ.get("LANE_WINDOWS", "v2conv:09:30-10:30")' in SRC
      and '"OPEN_LANE_RANK", "ignition,v2conv,kevseq,hidden_v2,ema9x90,ma_pullback"' in SRC)
check("A9 RTH floor settled at 1% (Marcos 8/20) with the ladder in the comment",
      'os.environ.get("MIN_STOP_PCT", "1.0")' in SRC
      and "the 4%" in SRC and "+$42,310" in SRC)
_rth = re.search(r'"RTH_LANES",\s*(#[^\n]*\n\s*)*"([^"]*)"', SRC)
check("A8 v2conv NOT in the flat RTH whitelist (window seat only)",
      _rth is not None and "v2conv" not in _rth.group(2))

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
