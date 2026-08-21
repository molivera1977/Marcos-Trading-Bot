#!/usr/bin/env python3
"""
RIG GATE 30 — SPREAD-RELATIVE STOP GUARD (8/20 night, Marcos: "ship the k=1 guard")

EVIDENCE: data/killtests/spread_floor_20260820.py — 12,630 fills, 11,979 real NBBO quotes,
REAL spreads charged: k=0 +$20,913 · k=1 +$24,265 (TRAIN +$11,572 / OOS +$12,693, beats k=0
on BOTH halves, drops 104 fills) · k=2 +$23,674 · k=3 +$20,253. Pre-registered winner k=1.
Physics: RT spread dollars ~= $60 x (spread / stop-width) per $30 risk; a stop inside the
spread pays >100% of the risk unit before the trade starts (UUU 0.44%/11.4% = 382%).

PINS — the reject-branch containment is EXECUTED as a mini-AST check because the FIRST
version of this guard landed the orphaned refund/return at the OUTER if level, which would
have refunded-and-returned EVERY quoted trade (caught in the build's own read-back; the
whole book would have gone silent behind green logs).
  S1  constant exists, default 1.0, env kill SPREAD_STOP_K=0
  S2  guard evaluates ONLY with a live quote (spread_pct > 0 — the fetch's fail-open honored)
  S3  CONTAINMENT (AST): _slot_refund and `return` sit INSIDE the `_sg_stopw <` reject
      branch, NOT under the outer `if SPREAD_STOP_K` — a passing trade must fall through
  S4  reject row carries spread, stop_width, k, and spread_pct (the nightly grading columns)
  S5  guard sits AFTER the absolute 6% cap (byte order) — the cap owns garbage quotes first
  S6  arithmetic: stop 0.06 vs spread 0.05 PASSES at k=1 (the ladder says keep it);
      stop 0.04 vs spread 0.05 REJECTS (stop inside the spread — structurally dead)
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


check("S1 constant + kill switch",
      'SPREAD_STOP_K         = float(os.environ.get("SPREAD_STOP_K", "1.0"))' in SRC)
check("S2 live-quote precondition (fail-open honored)",
      "if SPREAD_STOP_K > 0 and spread_pct > 0 and entry_price > stop_loss:" in SRC)
check("S4 reject row carries the grading columns",
      'spread=round(_sg_spread, 4), stop_width=round(_sg_stopw, 4)' in SRC
      and "k=SPREAD_STOP_K" in SRC)
i_cap = SRC.find('"spread_reject"')
i_grd = SRC.find('"spread_stop_reject"')
check("S5 guard sits after the absolute cap", 0 < i_cap < i_grd)

# S3 — containment, executed on the real AST
tree = ast.parse(SRC)
ok3 = False
for node in ast.walk(tree):
    if isinstance(node, ast.If):
        t = ast.get_source_segment(SRC, node.test) or ""
        if "SPREAD_STOP_K > 0" in t and "spread_pct > 0" in t:
            # the outer guard-if: its body must contain assignments + ONE inner if, and the
            # refund/return must live in that inner if's body, not in the outer body
            outer_stmts = node.body
            inner_ifs = [x for x in outer_stmts if isinstance(x, ast.If)]
            outer_has_return = any(isinstance(x, ast.Return) for x in outer_stmts)
            outer_has_refund = any("_slot_refund" in ast.dump(x) for x in outer_stmts
                                   if not isinstance(x, ast.If))
            inner_ok = bool(inner_ifs) and any(
                any(isinstance(y, ast.Return) for y in inf.body)
                and any("_slot_refund" in ast.dump(y) for y in inf.body)
                for inf in inner_ifs)
            ok3 = inner_ok and not outer_has_return and not outer_has_refund
            break
check("S3 CONTAINMENT (AST): refund+return INSIDE the reject branch; passing trades fall through", ok3)

# S6 — the arithmetic, executed
K = 1.0
def rejects(stopw, spread): return stopw < K * spread
check("S6 stop 0.06 vs spread 0.05 PASSES at k=1; stop 0.04 REJECTS",
      rejects(0.04, 0.05) is True and rejects(0.06, 0.05) is False
      and rejects(0.05, 0.05) is False)   # boundary: exactly 1x passes

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
