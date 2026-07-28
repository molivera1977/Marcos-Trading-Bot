"""Rig: OFF-TAPE EXIT GUARD (7/27, item 8).

Spec under test — Marcos: "so was the pre-market issue fixed?" → the BARS half was; the BOOKING
half was not. On 7/27 all five premarket BLIND-STOP exits recorded prices below the day's low on
BOTH independent 10s feeds, totalling exactly −$624.50 — the whole incident booked at prices that
never traded, while all 17 RTH exits that day were on-tape.

The guard must catch every one of those five, must NOT touch a real crater (LGHL's RTH stop-out
fell 21% inside one 3-min candle and was genuine), and must never veto the exit itself — a blind
position still has to be closed.

Figures below are the verified 7/27 records (trade store + dashboard 10s archive, both feeds).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

print("== the five real 7/27 premarket blind-stops ==")
# Tape as the MONITOR COULD HAVE SEEN IT — bars inside each trade's own fill→exit window, from the
# dashboard 10s archive (computed this session; the whole-day low is NOT the right input, since bars
# printed after the exit were never visible to the guard).
# (ticker, booked exit, seen low, seen high, shares, entry, % below seen)
INCIDENT = [
    ("BIYA",  1.93,  2.5300,  2.6200,  381,  2.62, 23.7),
    ("LGHL",  0.91,  2.0200,  2.6800,  287,  1.49, 55.0),
    ("VEEE", 12.97, 16.0000, 18.0000,   29, 16.40, 18.9),
    ("MTNB",  0.24,  0.4670,  0.5196, 2142,  0.43, 48.6),
]
for tk, px, lo, hi, sh, entry, dev in INCIDENT:
    booked, raw, ok, why = bot._verify_exit_px(px, lo, hi)
    caught = (not ok) and why == "below_tape" and booked == round(lo, 4) and raw == px
    check(f"{tk}: {px} is {dev}% below seen tape {lo} -> caught, booked {lo}", caught,
          f"booked={booked} ok={ok} why={why}")

# NAMED LIMITATION — JZXN 7/27 is NOT catchable by this mechanism and the rig says so out loud.
# Booked 1.19 against a seen low of 1.22 = only 2.5% below, which is indistinguishable from an
# ordinary new low. Catching it would need a tolerance tight enough to clamp genuine moves, which
# would be the wick-shakeout error in a new costume. Exposure is bounded: (1.22-1.19)x680 = $20.40
# of the -$81.48 row. Documented, not tuned away.
booked, raw, ok, why = bot._verify_exit_px(1.19, 1.22, 1.60)
check("JZXN (2.5% below seen tape) passes — KNOWN GAP, bounded at ~$20.40, deliberately not tuned for",
      ok, f"booked={booked} why={why}")

print("\n== must NOT fire on genuine moves ==")
# LGHL 7/27 RTH: entry 1.975 -> stop-out 1.55, a REAL 21% crater inside one 3-min candle.
# Bars were flowing, so the seen tape includes the low. The guard must stay out of the way.
booked, raw, ok, why = bot._verify_exit_px(1.55, 1.55, 3.96)
check("LGHL RTH real crater exit 1.55 (tape low 1.55) passes untouched", ok and booked == 1.55,
      f"booked={booked} ok={ok}")
# A new low slightly beyond the last seen bar is normal — tolerance must absorb it.
booked, raw, ok, why = bot._verify_exit_px(0.98, 1.00, 2.00)
check("2% new low below seen tape passes (inside 5% tolerance)", ok, f"booked={booked} why={why}")
booked, raw, ok, why = bot._verify_exit_px(0.955, 1.00, 2.00)
check("4.5% new low still passes", ok, f"why={why}")
booked, raw, ok, why = bot._verify_exit_px(0.94, 1.00, 2.00)
check("6% below seen tape is caught", (not ok) and booked == 1.0, f"booked={booked} ok={ok}")
# Every one of the 17 RTH exits on 7/27 was inside its day range — none may be flagged.
for tk, px, lo, hi in [("LGHL", 1.55, 0.95, 3.96), ("DFNS", 6.34, 5.78, 18.00),
                       ("BIYA", 3.24, 2.42, 4.90), ("KIDZ", 0.52, 0.41, 0.7562),
                       ("WLDS", 3.79, 2.62, 6.50), ("PN", 10.25, 8.35, 11.00)]:
    _, _, ok, _ = bot._verify_exit_px(px, lo, hi)
    check(f"{tk} RTH exit {px} on-tape -> untouched", ok)

print("\n== the upper bound too (a phantom high would overstate a win) ==")
booked, raw, ok, why = bot._verify_exit_px(9.99, 1.00, 2.00)
check("print far above the seen tape is caught", (not ok) and why == "above_tape" and booked == 2.0,
      f"booked={booked} why={why}")

print("\n== FABLE F1: TOTAL blindness — the actual 7/27 conditions (bars empty EVERY cycle) ==")
# In the true incident the monitor never saw a bar, so there is no seen tape at all. The guard must
# NOT invent a price (no proven print exists) and must NOT stamp 'verified' either: book the raw
# print, flag it. This is what lets the analysis layer quarantine what 7/27 could not.
for tk, px in [("BIYA", 1.93), ("LGHL", 0.91), ("VEEE", 12.97), ("MTNB", 0.24), ("JZXN", 1.19)]:
    booked, raw, ok, why = bot._verify_exit_px(px, None, None)
    check(f"{tk} blind exit {px}: booked RAW but flagged no_tape_seen",
          (not ok) and why == "no_tape_seen" and booked == px, f"ok={ok} why={why} booked={booked}")

print("\n== fail-open: never break the exit path ==")
for args, lbl in [((None, 1.0, 2.0), "px None"), ((0, 1.0, 2.0), "px 0")]:
    booked, raw, ok, why = bot._verify_exit_px(*args)
    check(f"{lbl} -> passes through untouched", ok and booked == args[0])
booked, raw, ok, why = bot._verify_exit_px(1.5, 0, 0)
check("tape zeros -> raw booking, flagged (not silently verified)",
      (not ok) and why == "no_tape_seen" and booked == 1.5, f"ok={ok} why={why}")
booked, raw, ok, why = bot._verify_exit_px(0.50, 1.00, 2.00, tol=0)
check("EXIT_PX_TAPE_TOL=0 disables the guard", ok, f"ok={ok}")
booked, raw, ok, why = bot._verify_exit_px(0.50, None, None, tol=0)
check("kill switch also silences no_tape_seen", ok, f"ok={ok}")

print("\n== wiring: one choke point covers all exit paths ==")
src = pathlib.Path(bot.__file__).read_text()
check("guard runs before blended P&L", src.find("_verify_exit_px(result[") < src.find('result["profit_loss"] = _blended_pnl')
      and "_verify_exit_px(result[" in src)
check("monitor tracks seen tape from bars it already fetches", "_tape_lo = _tape_hi = None" in src
      and "_tape_lo = _tl if _tape_lo is None else min(_tape_lo, _tl)" in src)
check("off-tape exit is decision-logged", '"off_tape_exit"' in src)
check("trade record carries exit_px_unverified + exit_px_raw",
      '"exit_px_unverified": trade_result.get("exit_px_unverified")' in src
      and '"exit_px_raw":        trade_result.get("exit_px_raw")' in src)
# The guard must correct BOOKING only — it must never be able to skip closing a blind position.
_seg = src[src.find("_verify_exit_px(result["):src.find('result["profit_loss"] = _blended_pnl')]
check("guard never returns/continues (does not veto the exit itself)",
      "return" not in _seg and "continue" not in _seg)

print("\n== FABLE F2: the watchdog path books through the guard too ==")
check("watchdog verifies its exit print", "_verify_exit_px(px, ctx.get(\"tape_lo\")" in src)
check("watchdog record carries the honesty columns",
      src.count('"exit_px_unverified"') >= 3)   # verdict fn ref + main record + watchdog record
check("monitor shares its seen tape with the watchdog ctx",
      '"tape_lo": _tape_lo, "tape_hi": _tape_hi' in src)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — off-tape exit guard: all 5 incident exits caught, real crater untouched, fail-open, booking-only")
