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

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
