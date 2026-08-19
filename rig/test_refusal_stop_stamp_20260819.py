#!/usr/bin/env python3
"""
RIG GATE 23 — EVERY REFUSAL ROW CARRIES ITS STOP (8/19, Marcos: "stamp stops on the refusal rows")

WHY. A refused fire is a counterfactual we grade later through E3, and E3 needs the STOP. Only
runway/minstop/breakside recorded one; the other eight gates forced the 8/19 replay to ASSUME a
10% stop, and the assumption — not the tape — decided the verdicts:
  lane_restricted  +$210 @6%  ->  +$40 @15%   (sign unstable)
  momentum_reject   +$60 @6%  ->  +$49 @15%   (sign unstable)
  kev_gate         +$234 @6%  -> +$82 @15%    (and 94% of it was ONE name on ONE day)
Marcos, on being shown the table: "is all this correct from today" — it was not, and this is the
instrumentation that makes it correct next time.

PINS
  F1  the lane-proof helper exists and prefers zone_stop -> ema_stop -> stop -> fallback
  F2  HONESTY: absent stop stamps None (never a fabricated number) — an assumed 10% is exactly
      what corrupted the 8/19 table
  F3  all eight previously-unstamped refusal sites now pass stop=
  F4  the three already-trustworthy sites (runway/minstop/breakside) still carry theirs
  F5  no refusal site fabricates a stop from price (no `price *` inside a stop= argument)
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


check("F1 helper _refusal_stop exists, lane-proof order",
      "def _refusal_stop(" in SRC
      and 'd.get("zone_stop") or d.get("ema_stop") or d.get("stop") or fallback' in SRC)

check("F2 absent stop -> None, never fabricated",
      "return round(float(v), 4) if v else None" in SRC)

NEWLY = ["vel5_reject", "daygain_reject", "backside_reject", "lane_restricted",
         "momentum_reject", "ignition_relvol_reject", "ignition_kev_gate_reject",
         "premkt_capped"]
ALREADY = ["runway_reject", "minstop_reject", "breakside_reject"]

for g in NEWLY + ALREADY:
    # 8/19 (twice-bitten): match the EXACT quoted status, then scan a fixed WINDOW of the call
    # rather than hunting a closing paren — the first attempt matched the newer
    # ignition_rvol10d_reject row, the second ran past its 700-char paren window. Both produced
    # a FALSE RED on code that was correct. A pin that lies is worse than no pin.
    i = SRC.find('"%s",' % g)
    body = SRC[i:i + 900] if i != -1 else ""
    tag = "F3" if g in NEWLY else "F4"
    check(f"{tag} {g} logs stop=", i != -1 and "stop=" in body)

# F5 — no site may synthesise a stop from price inside the stop= argument
bad = re.findall(r"stop=[^,\n]*price\s*\*", SRC)
check("F5 no refusal site fabricates stop from price", not bad)

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
