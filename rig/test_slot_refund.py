"""Rig: SLOT REFUND (7/29 night, Marcos: "we have to move fast and not be clipped every morning").
A session slot is spent by a TRADE, not an ATTEMPT. Gauntlet case = AMIX 7/29: the 09:32 ticket
consumed reclaim's RTH slot, died at the guards, and the real 09:40 flush entry (5.49 -> 7.25,
Kev's dip-and-rip) had no slot. Functional pins on the real _curl_rth_slot/_slot_refund pair,
wiring pins on all four refusal sites. Mutant: delete a _slot_refund call -> wiring pin goes red."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

from datetime import datetime
EASTERN = bot.EASTERN
_hm = datetime.now(EASTERN).strftime("%H:%M")
_sess = "PRE" if _hm < "09:30" else "RTH"

print("== the AMIX clip, functionally (curl lane) ==")
bot._curl_rth_n.clear()
bot.ENTRY_OPEN_ET = "00:00"                               # rig runs off-hours; open the floor
g1 = bot._curl_rth_slot("AMIX", "vr", _hm)
check("first fire takes the slot", g1 is True)
g2 = bot._curl_rth_slot("AMIX", "vr", _hm)
check("second fire is refused while slot is held", g2 is False)
bot._slot_refund("AMIX", "vwap_reclaim")                  # the ticket died at a guard
g3 = bot._curl_rth_slot("AMIX", "vr", _hm)
check("after refund the REAL entry converts (the 09:40 flush)", g3 is True)
bot._slot_refund("AMIX", "zone_flip")                     # wrong lane refund must not touch vr
g4 = bot._curl_rth_slot("AMIX", "vr", _hm)
check("refund is lane-scoped (zf refund never frees vr)", g4 is False)

print("== hidden counters refund ==")
_day = datetime.now(EASTERN).strftime("%Y-%m-%d")
bot._he_day.update({"d": _day, "PRE": 0, "RTH": 0}); bot._he_name.clear()
bot._he_day[_sess] = 2; bot._he_name[(_day, "NCRA", _sess)] = 1
bot._slot_refund("NCRA", "hidden_entry")
check("hidden day count decrements", bot._he_day[_sess] == 1)
check("hidden name count decrements", bot._he_name[(_day, "NCRA", _sess)] == 0)
bot._slot_refund("NCRA", "hidden_entry")
bot._slot_refund("NCRA", "hidden_entry")
check("refund floors at zero (never negative)", bot._he_day[_sess] == 0
      and bot._he_name[(_day, "NCRA", _sess)] == 0)

print("== wiring: every refusal path between conversion and BUY refunds ==")
for site, label in [("CHART-GATE BLOCKED {ticker} entry", "chart gate"),
                    ('"bad_stop_skip"', "bad stop (P0-A)"),
                    ('"minstop_reject"', "min-stop gate"),
                    ('"spread_reject"', "spread guard")]:
    i = src.find(site)
    seg = src[i:i + 420] if i > 0 else ""
    check(f"{label} refunds the slot", "_slot_refund(ticker, entry_type)" in seg)
check("refund logs a decision row", '"slot_refunded"' in src)
check("refund never raises (try/except)", "def _slot_refund" in src
      and "except Exception:" in src[src.find("def _slot_refund"):src.find("def _slot_refund") + 1600])

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — an attempt is not a trade: refused tickets refund the lane slot; the next fire converts")
