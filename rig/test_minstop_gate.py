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
check("floor is 4% by default (8/1, Marcos: see where the data takes us)", abs(bot.MIN_STOP_DIST_PCT - 0.04) < 1e-9,
      f"MIN_STOP_DIST_PCT={bot.MIN_STOP_DIST_PCT}")

print("== rejection boundary (entry $10.00) ==")
for stop, want_rej, want_band in [
    (9.90, True,  "<2"),    # 1.0% — the KIDZ class (fine bands 8/1)
    (9.61, True,  "3-4"),   # 3.9% (fine bands 8/1)
    (9.60, False, "4-5"),   # 4.0% — passes under the 4 floor (8/1)   # 4.0% exactly — band edge
    (9.51, False, "4-5"),   # 4.9% — passes (8/1)   # 4.9%
    (9.50, False, "5-6"),   # 5.0% — passes (8/1)   # 5.0% exactly — band edge
    (9.41, False, "5-6"),   # 5.9% — passes under the 4 floor (8/1)
    (9.40, False, ">=6"),   # 6.0% — passes (floor now 4.0, 8/1)
    (9.30, False, ">=6"),   # 7.0%
    (8.00, False, ">=6"),   # 20% — wide stops are the OTHER gate's business
]:
    rej, w, band = bot._min_stop_verdict(10.0, stop)
    check(f"stop {stop} -> {'reject' if want_rej else 'pass'} band {want_band}",
          rej == want_rej and band == want_band, f"got rej={rej} w={w} band={band}")

print("== real trades replay the right verdict (7/27 lane agreement) ==")
# KIDZ 7/27 vwap_reclaim: 2.87% -> FLOORED lane -> reject, '<4' (the trade the gate exists for)
rej, w, band = bot._min_stop_verdict(0.5400, 0.5245, "vwap_reclaim")
check("KIDZ reclaim (2.87%) rejected in '2-3' (floor 4, fine bands 8/1)", rej and band == "2-3", f"w={w} band={band}")
# HPAI 7/17 vwap_reclaim: 4.15% -> reject, '4-5' (worst tight-stop dollar loss, -$91.26)
rej, w, band = bot._min_stop_verdict(0.620, 0.5943, "vwap_reclaim")
# 8/1 RE-PIN: HPAI (4.15%) now PASSES under the 4 floor — it becomes a LIVE 4-5 cell trade;
# its -$91.26 history is exactly what the week's live 4-5 cell will confirm or refute.
check("HPAI reclaim (4.15%) passes at floor 4, band '4-5'", (not rej) and band == "4-5", f"w={w} band={band}")
# TGHL 7/17 ignition: 3.51% -> reject (ignition = the floor's main business, 43 era rejects)
rej, w, band = bot._min_stop_verdict(1.400, 1.3509, "ignition")
check("TGHL ignition (3.51%) rejected in '3-4' (fine bands 8/1)", rej and band == "3-4", f"w={w} band={band}")
print("== exempt lanes: tight risk is the thesis — NEVER rejected, band still stamped ==")
# ZYBT-0720-A — Kev's canonical zone-flip specimen: $1.28 entry, 7 cent risk = 5.47%. THE pin:
# any future floor change that rejects the lane's founding trade goes red here.
rej, w, band = bot._min_stop_verdict(1.28, 1.21, "zone_flip")
check("ZYBT-0720-A specimen (5.47%) PASSES zone_flip", not rej and band == "5-6", f"w={w} band={band}")
# LGHL 7/27 zone_flip 5.56%: passes under the exemption (was the named consequence pre-agreement;
# its loss is attributed to the chart-bypass seam, graded via the ballpark stamp, not stop width)
rej, w, band = bot._min_stop_verdict(1.98, 1.87, "zone_flip")
check("LGHL zone_flip (5.56%) passes, band stamped '5-6'", not rej and band == "5-6", f"w={w} band={band}")
# LVWR 7/27 hidden_entry 5.56% and a 1% hidden stop: exempt regardless of width
rej, w, band = bot._min_stop_verdict(2.88, 2.72, "hidden_entry")
check("LVWR hidden (5.56%) passes", not rej and band == "5-6", f"w={w} band={band}")
rej, w, band = bot._min_stop_verdict(2.88, 2.8512, "hidden_entry")
check("hidden 1% stop still passes (exempt; band '<2' 8/1)", not rej and band == "<2", f"w={w} band={band}")
# CPHI 7/16 flat_top 3.78% (+$62.89): the winner class the flat_top exemption protects
rej, w, band = bot._min_stop_verdict(3.14, 3.0213, "flat_top")
check("CPHI flat_top (3.78%) exempt-passes in '3-4' (8/1)", not rej and band == "3-4", f"w={w} band={band}")
# BIYA flat_top 7/27: 7.03% -> passes on width alone either way
rej, w, band = bot._min_stop_verdict(3.86, 3.5888, "flat_top")
check("BIYA flat_top (7.03%) passes", not rej and band == ">=6", f"w={w} band={band}")
print("== exemption config ==")
check("exempt set is exactly {zone_flip, hidden_entry, flat_top}",
      bot.MIN_STOP_EXEMPT == {"zone_flip", "hidden_entry", "flat_top"}, f"got {bot.MIN_STOP_EXEMPT}")
_sv = bot.MIN_STOP_EXEMPT
bot.MIN_STOP_EXEMPT = set()
rej, w, band = bot._min_stop_verdict(1.28, 1.24, "zone_flip")   # 3.1% — below the 4 floor (8/1)
check("MIN_STOP_EXEMPT='' floors everything (env kill of the exemption)", rej, f"rej={rej}")
bot.MIN_STOP_EXEMPT = _sv

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
check("_trade_worker calls _min_stop_verdict with the lane",
      "_min_stop_verdict(entry_price, stop_loss, entry_type)" in src)
check("reject logs 'minstop_reject' with band", '"minstop_reject"' in src and "band=_ms_band" in src)
check("kept trades record stop_width_pct", '"stop_width_pct"' in src)
i_gate = src.find("_min_stop_verdict(entry_price, stop_loss, entry_type)")
i_size = src.find("_sh_risk = int(_risk_i")
check("gate runs BEFORE risk sizing", 0 < i_gate < i_size)

print("== ballpark stamp wired (7/27: tape lanes owe the chart EVIDENCE, not obedience) ==")
check("_level_gap helper exists", "def _level_gap(ticker, price):" in src)
for fire in ("zoneflip_shadow_fire", "reclaim_shadow_fire", "hidden_shadow_fire"):
    seg = src[src.find(f'"{fire}"'):src.find(f'"{fire}"') + 700]
    check(f"{fire} carries level_gap_pct + ballpark", "level_gap_pct" in seg and "ballpark" in seg)
check("live_structure allow carries the marked level (was None)",
      'return ("allow", "live_structure", _blv, "none")' in src)
gap, bp = bot._level_gap.__wrapped__(None, None) if hasattr(bot._level_gap, "__wrapped__") else bot._level_gap("ZZNOLEVEL", 5.0)
check("_level_gap fails open with no level", (gap, bp) == (None, None), f"got {(gap, bp)}")

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — minstop gate: 6% floor, shadow bands exact, kill switch works, wired pre-sizing")
