#!/usr/bin/env python3
"""
RIG GATE 26 — THE PRE ROSTER IS A MEASURED RULING (8/19 night)

Marcos: "lets answer the question, what deserves to run in pre? Pre has always sucked." ...
"i want whatever lanes scoring well to join pre."

Evidence = data/killtests/pre_audition_20260819.py, TRUE-ET rerun (the first run compared the
cache's UTC stamps to ET windows and is VOID — caught by a failed positive control: prevwap
replayed 0 fires vs a live fire 8/17 WETO). 769 pre name-days, bot's own detectors:
  ignition +9.48/+7.87 (train/OOS $/tr) · v2conv +7.25/+7.76 · reclaim +6.38/+4.94 ·
  prevwap +0.34/+11.07 (one-sided — ON NOTICE, kept as incumbent).

PINS
  P1  PRE_LANES default carries ignition AND vwap_reclaim (the new joiner)
  P2  VWAPRECLAIM_CONVERT default ON, with the owner-ruling comment (an auditor cannot lift a
      suspension — feedback_auditor_cannot_authorize_behavior; the OWNER did, on the record)
  P3  RTH stays protected: vwap_reclaim NOT in the RTH_LANES default (pre-only conversion)
  P4  hidden_v2 NOT in the PRE default (true-ET pre replay refused it)
  P5  the UTC->ET conversion lives in the audition killtest (the class-fix, in the evidence)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
AUD = (ROOT / "data" / "killtests" / "pre_audition_20260819.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


check("P1 PRE_LANES default = ignition + vwap_reclaim (+ma_pullback rider)",
      '"ignition,vwap_reclaim" + (",ma_pullback" if MA_PULLBACK_V2 else "")' in SRC)
check("P2 VWAPRECLAIM_CONVERT default ON by owner ruling",
      'VWAPRECLAIM_CONVERT = os.environ.get("VWAPRECLAIM_CONVERT", "1") == "1"' in SRC
      and "BY THE OWNER'S RULING" in SRC)
_rth = re.search(r'"RTH_LANES",\s*(#[^\n]*\n\s*)*"([^"]*)"', SRC)
check("P3 vwap_reclaim NOT in the RTH whitelist default (pre-only)",
      _rth is not None and "vwap_reclaim" not in _rth.group(2))
_pre = re.search(r'"PRE_LANES",\s*(#[^\n]*\n\s*)*"([^"]*)"', SRC)
check("P4 hidden_v2 NOT in the PRE default (measured refusal)",
      _pre is not None and "hidden_v2" not in _pre.group(2))
check("P5 audition killtest converts UTC->ET (class-fix in the evidence)",
      "timedelta(hours=4)" in AUD and "UTC" in AUD)
# 8/19 ~23:3x ET Marcos: "make sure the roster is lined up in order from best to worst" (pre)
# + "bench prevwap and have it shadow. make it earn its way after we retool."
# 8/21 SUPERSEDED by the REAL-COST competition (Marcos: "roster according to this last
# competition and ship"): v2conv PRE both halves NEGATIVE (-$1,559.31) -> benched from pre;
# vwap_reclaim already benched -> rank entry removed. The audition order this pin froze was
# PAPER-cost evidence; the pin now freezes the real-cost order instead.
check("P6 PRE_LANE_RANK default = real-cost order (8/21): ignition, ma_pullback",
      '"PRE_LANE_RANK", "ignition,ma_pullback"' in SRC)
# 8/20 AMENDMENT: _lane_rank gained a third branch (opening-block roster). The premarket
# branch is unchanged in MEANING — pinned on the branch, not the old one-liner.
check("P7 _lane_rank consults PRE_LANE_RANK inside the premarket window",
      '_pre = (ENTRY_OPEN_ET <= _hm_r < "09:30")' in SRC and "_lst = PRE_LANE_RANK" in SRC)
check("P8 prevwap NOT in PRE_LANE_RANK (benched to shadow, earns its way back)",
      "prevwap" not in re.search(r'"PRE_LANE_RANK", "([^"]*)"', SRC).group(1))
check("P9 prevwap convert default stays OFF in code (bench = env 0 + this default)",
      'PREVWAP_CONVERT    = os.environ.get("PREVWAP_CONVERT", "0") == "1"' in SRC)

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
