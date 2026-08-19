#!/usr/bin/env python3
"""
GATE 16 — A RESUMED TRADE MUST NOT LOSE ITS BANKED LEGS (8/18)

THE INSTANCE: a mid-session redeploy restarted the bot at 10:07:42 with SXTC open. The monitor
resumed with `partial_fills` EMPTY, so two banked legs — 54sh @ $4.8207 and 27sh @ $5.0415, both
verified on SIP tape AND both present in the durable tier_fill ledger at 10:28:56 / 10:30:58 —
vanished. The whole 109sh was marked out at the final exit: -$7.63 recorded against a true
+$21.89. One trade, $29.51 wrong, and the day's headline read -$18.00 instead of +$11.51.

THE CLASS: a single in-memory snapshot was treated as authoritative while a durable, independently
written record of the same facts sat unread. Same shape as the 8/18 VWAP defect, where the correct
tick line was discarded for disagreeing with a corrupt bar line.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "marcos_trading_bot.py")).read()
FAILS = []
def chk(c, label, detail=""):
    print(f"  {'PASS' if c else 'FAIL'}  {label}" + (f"   {detail}" if detail and not c else ""))
    if not c: FAILS.append(label)

print("GATE 16 — a resumed trade must not lose its banked legs")
print("=" * 74)
m = re.search(r'TIER_REHYDRATE\s*=\s*os\.environ\.get\(\s*"TIER_REHYDRATE",\s*"(\d)"\s*\)', SRC)
chk(bool(m), "A1 TIER_REHYDRATE kill switch exists")
chk(bool(m) and m.group(1) == "1", "A2 defaults ON")
chk("def _tier_fills_from_ledger(ticker):" in SRC, "B1 the ledger reader exists")
chk("status=tier_fill" in SRC, "B2 it reads the DURABLE tier_fill rows")
chk('r.get("qty"), r.get("price")' in SRC, "B3 it takes qty AND price from the row")
chk("out.sort(key=lambda z: z[0])" in SRC, "B4 legs are ordered oldest-first")
chk("return []" in SRC.split("def _tier_fills_from_ledger")[1].split("def ")[0],
    "B5 a read failure returns NO legs (never invents them)")
chk("if len(_led) > len(partial_fills):" in SRC,
    "C1 the ledger wins ONLY when it knows about MORE legs")
chk("remaining_shares = max(initial_shares - sum(int(q) for q, _p in partial_fills), 0)" in SRC,
    "C2 remaining_shares is RECOMPUTED from the rebuilt legs")
chk("tier_idx         = max(tier_idx, len(partial_fills))" in SRC,
    "C3 tier_idx advances to the rebuilt leg count")
chk("partial_taken    = True" in SRC.split("_rehydrated      = True")[0][-400:],
    "C4 partial_taken is set (a resumed trade is not 'fresh')")
chk("tier_rehydrated=_rehydrated" in SRC and "ledger_legs=len(_led)" in SRC and "banked=" in SRC,
    "D1 the trade_resumed row stamps whether a rebuild happened, and what was rebuilt")

# arithmetic on the REAL SXTC legs
ENTRY, INIT, EXIT = 4.60, 109, 4.53
legs = [(54, 4.8207), (27, 5.0415)]
rem = INIT - sum(q for q, _ in legs)
tot = sum(q * (p - ENTRY) for q, p in legs) + rem * (EXIT - ENTRY)
chk(abs(tot - 21.89) < 0.05, "E1 rebuilt SXTC P&L reconstructs the tape-verified +$21.89",
    f"got {tot:+.2f}")
chk(rem == 28, "E2 the runner remainder is 28sh", f"got {rem}")
chk(abs(INIT * (EXIT - ENTRY) + 7.63) < 0.02,
    "E3 the UNFIXED path reproduces the -$7.63 that was recorded")
print("=" * 74)
if FAILS:
    print(f"GATE 16 FAILED ({len(FAILS)}): " + "; ".join(FAILS)); sys.exit(1)
print("GATE 16 PASSED"); sys.exit(0)
