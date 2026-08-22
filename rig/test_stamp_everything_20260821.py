#!/usr/bin/env python3
"""
RIG GATE 34 — STAMP EVERYTHING: the chart-gate rows (8/21 night)

THE RULE (born in the 8/21 cross-AI exchange, tested against the gate ledger): every refusal
row carries price + would-be stop + the gate's own input, so rows are gradeable under theories
not yet conceived. AUDIT RESULT 8/21: daygain/vel5/momentum have stamped 100% since 8/19; the
chart-gate rows were the LAST refusal class with neither price nor stop (verified live:
chart_gate_block 8/20 n=1, with-stop 0). This ship closes that.

PINS
  P1 the verdict row (chart_gate_allow/block/skip) carries price= AND stop=_refusal_stop(extra)
  P2 the enforce-path row (chart_gate_blocked_trade) carries the same
  P3 the gate input (break_level) still present on both rows
  P4 _refusal_stop unchanged (zone_stop|ema_stop|stop, else None) — EXECUTED
  P5 module parses
"""
import ast, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []
def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok: FAIL.append(n)

seg = SRC[SRC.find('_log_decision(ticker, "chart_gate_" + _cg_verdict'):][:700]   # widened 8/21: the stamp added lines; 400 chars clipped break_level (gate-23 window lesson, 4th appearance)
check("P1 verdict row stamps price + stop",
      "price=round(float(entry_price), 4), stop=_refusal_stop(extra)" in seg)
seg2 = SRC[SRC.find('"chart_gate_blocked_trade"'):][:700]   # widened 8/21: the stamp added lines; 400 chars clipped break_level (gate-23 window lesson, 4th appearance)
check("P2 blocked_trade row stamps price + stop",
      "price=round(float(entry_price), 4)" in seg2 and "stop=_refusal_stop(extra)" in seg2)
check("P3 break_level still on both", seg.count("break_level=_cg_level") >= 1 and "break_level=_cg_level" in seg2)
ns = {}
a = SRC.find("\ndef _refusal_stop(")
b = SRC.find("\ndef ", a + 1)
exec(SRC[a:b], ns)
rs = ns["_refusal_stop"]
check("P4 EXECUTED: _refusal_stop semantics unchanged",
      rs({"zone_stop": 1.23}) == 1.23 and rs({"stop": 4.5}) == 4.5
      and rs({}) is None and rs(None) is None and rs({"ema_stop": "2.5"}) == 2.5)
ast.parse(SRC)
check("P5 module parses", True)
print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
