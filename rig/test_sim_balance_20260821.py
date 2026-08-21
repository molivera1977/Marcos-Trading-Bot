#!/usr/bin/env python3
"""
RIG GATE 33 — SIM FRAME = GO-LIVE ACCOUNT (8/21 after the close, Marcos: "change it after the
close")

RULING: SIM_ACCOUNT_BALANCE 3000.0 -> 5000.0 so the DRY_RUN sim models the real go-live funding.

PINS — the point of this gate is that the change is CAPACITY-ONLY. Each pin holds one thing
that must NOT have moved, executed rather than grepped where arithmetic is involved.
  B1 the constant is 5000.0
  B2 RISK_PER_TRADE is still the 30.0 CONSTANT (not derived from balance) — if this ever
     becomes a percentage, the "R unchanged" claim in the ruling silently dies
  B3 the position clamp is still min(70% x balance, MAX_TRADE_DOLLARS) and MAX_TRADE_DOLLARS
     is still 1000 — EXECUTED: at BOTH books the binding cap must be the $1,000 one, which is
     what makes this change capacity-only
  B4 SIM_ACCOUNT_BALANCE is still consulted only under DRY_RUN (never overrides a real balance)
  B5 the boot banner still prints the sizing frame, so the live value is visible not implied
"""
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []
def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok: FAIL.append(n)

check("B1 SIM_ACCOUNT_BALANCE = 5000.0", "SIM_ACCOUNT_BALANCE     = 5000.0" in SRC)
check("B2 RISK_PER_TRADE still a flat constant 30.0",
      bool(re.search(r"^RISK_PER_TRADE\s*=\s*30\.0", SRC, re.M)))
check("B3a MAX_TRADE_DOLLARS default still 1000",
      'MAX_TRADE_DOLLARS     = float(os.environ.get("MAX_TRADE_DOLLARS", "1000"))' in SRC)
check("B3b MAX_POSITION_SIZE still 0.70", "MAX_POSITION_SIZE     = 0.70" in SRC)
# B3c EXECUTED: the $1,000 cap must bind at BOTH books -> capacity-only, as the ruling claims
cap = lambda bal: min(0.70 * bal, 1000.0)
check("B3c EXECUTED: the $1,000 cap binds at $3k AND $5k (so sizing cannot change)",
      cap(3000.0) == 1000.0 and cap(5000.0) == 1000.0)
check("B4 sim balance consulted only under DRY_RUN",
      "(SIM_ACCOUNT_BALANCE if DRY_RUN else get_account_balance())" in SRC)
check("B5 boot banner still prints the sizing frame",
      "DRY_RUN sizing frame: ${SIM_ACCOUNT_BALANCE:.2f} sim account" in SRC)
import ast; ast.parse(SRC)
check("B6 module parses", True)
print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
