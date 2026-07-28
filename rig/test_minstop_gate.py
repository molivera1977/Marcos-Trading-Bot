"""Rig: MINIMUM STOP WIDTH gate (7/27, Marcos's management call — 6% floor, shadow bands).

Tests the real _min_stop_verdict predicate (the inline gate calls it verbatim) + the config wiring.
Spec under test is Marcos's words: "put the 6% minimum stop in and shadow log what happens to the
4% and 5% rejects" — so the bands the shadow grade needs ('<4', '4-5', '5-6') must be exact.
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

print("== config ==")
check("floor is 6% by default", abs(bot.MIN_STOP_DIST_PCT - 0.06) < 1e-9,
      f"MIN_STOP_DIST_PCT={bot.MIN_STOP_DIST_PCT}")

print("== rejection boundary (entry $10.00) ==")
for stop, want_rej, want_band in [
    (9.90, True,  "<4"),    # 1.0% — the KIDZ class
    (9.61, True,  "<4"),    # 3.9%
    (9.60, True,  "4-5"),   # 4.0% exactly — band edge
    (9.51, True,  "4-5"),   # 4.9%
    (9.50, True,  "5-6"),   # 5.0% exactly — band edge
    (9.41, True,  "5-6"),   # 5.9%
    (9.40, False, ">=6"),   # 6.0% exactly — MUST PASS (floor is a minimum, not exclusive)
    (9.30, False, ">=6"),   # 7.0%
    (8.00, False, ">=6"),   # 20% — wide stops are the OTHER gate's business
]:
    rej, w, band = bot._min_stop_verdict(10.0, stop)
    check(f"stop {stop} -> {'reject' if want_rej else 'pass'} band {want_band}",
          rej == want_rej and band == want_band, f"got rej={rej} w={w} band={band}")

print("== real trades replay the right verdict ==")
# KIDZ 7/27: entry .5400 stop .5245 = 2.87% -> reject, '<4' (the trade the gate exists for)
rej, w, band = bot._min_stop_verdict(0.5400, 0.5245)
check("KIDZ 7/27 (2.87%) rejected in '<4'", rej and band == "<4", f"w={w} band={band}")
# HPAI 7/17: entry .620 stop .5943 = 4.15% -> reject, '4-5' (worst tight-stop dollar loss, -$91.26)
rej, w, band = bot._min_stop_verdict(0.620, 0.5943)
check("HPAI 7/17 (4.15%) rejected in '4-5'", rej and band == "4-5", f"w={w} band={band}")
# LGHL 7/27 zone_flip: entry 1.98 stop 1.87 = 5.56% -> reject, '5-6' — NAMED CONSEQUENCE: the 6%
# floor rejects the LGHL crater trade too. Shadow band will grade whether that was right.
rej, w, band = bot._min_stop_verdict(1.98, 1.87)
check("LGHL 7/27 (5.56%) rejected in '5-6' (named consequence)", rej and band == "5-6", f"w={w} band={band}")
# BIYA flat_top 7/27: entry 3.86 stop 3.5888 = 7.03% -> passes (a winner the gate must NOT touch)
rej, w, band = bot._min_stop_verdict(3.86, 3.5888)
check("BIYA flat_top 7/27 (7.03%) passes", not rej and band == ">=6", f"w={w} band={band}")

print("== fail-open on degenerate inputs (bad-stop skip owns those) ==")
check("entry 0 fails open", bot._min_stop_verdict(0, 1.0) == (False, None, None))
check("stop None fails open", bot._min_stop_verdict(10.0, None) == (False, None, None))

print("== kill switch ==")
_saved = bot.MIN_STOP_DIST_PCT
bot.MIN_STOP_DIST_PCT = 0.0
check("MIN_STOP_PCT=0 disables the gate", bot._min_stop_verdict(10.0, 9.90) == (False, None, None))
bot.MIN_STOP_DIST_PCT = _saved

print("== gate is wired into the entry path (source assertion) ==")
src = pathlib.Path(bot.__file__).read_text()
check("_trade_worker calls _min_stop_verdict", "_min_stop_verdict(entry_price, stop_loss)" in src)
check("reject logs 'minstop_reject' with band", '"minstop_reject"' in src and "band=_ms_band" in src)
check("kept trades record stop_width_pct", '"stop_width_pct"' in src)
i_gate = src.find("_min_stop_verdict(entry_price, stop_loss)")
i_size = src.find("_sh_risk = int(RISK_PER_TRADE")
check("gate runs BEFORE risk sizing", 0 < i_gate < i_size)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — minstop gate: 6% floor, shadow bands exact, kill switch works, wired pre-sizing")
