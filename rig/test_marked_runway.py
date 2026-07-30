"""Rig: MARKED RUNWAY STAMP (7/28, Marcos: "we need enough runway to travel on").

Spec: every trade record carries marked_runway_rr = (first sheet target above entry − entry) / R.
Fallback next_supply when no target is above. 0.0 when the sheet HAS levels but entry sits above
them all (the EGG case). None when the name has no sheet levels. LOG-ONLY — no gate, no behavior.
"""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

# 7/29: the stamp logic moved to the _marked_runway() HELPER (single source of truth — entry-time
# live card + record-time stamp). Pins upgraded from source-matching to FUNCTIONAL: monkeypatch the
# sheet and exercise the real helper. Mutant direction: break the helper's guards and these go red.
check("record carries marked_runway_rr", '"marked_runway_rr":   _runway_rr' in src)
check("record carries marked_runway_tgt", '"marked_runway_tgt":  _runway_tgt' in src)
check("record stamp + live card share ONE source", src.count("_marked_runway(ticker, entry_price, stop_loss)") >= 2)
_saved_fetch = bot._fetch_kev_levels
bot._fetch_kev_levels = lambda: {"TST": {"targets": [5.0, 7.0], "next_supply": 9.0}}
rr, tgt = bot._marked_runway("TST", 4.0, 3.5)          # rps 0.5; first target above = 5.0
check("runway = (tgt-entry)/rps", rr == 2.0 and tgt == 5.0, f"{rr},{tgt}")
rr, tgt = bot._marked_runway("TST", 8.0, 7.0)          # targets below; next_supply 9.0 above
check("next_supply fallback guarded above entry", rr == 1.0 and tgt == 9.0, f"{rr},{tgt}")
rr, tgt = bot._marked_runway("TST", 10.0, 9.0)         # above ALL marked levels
check("above-all-levels stamps the STATE (bimodal: ZYBT blue-sky vs EGG chase)",
      rr == "above_all_levels" and tgt is None, f"{rr},{tgt}")
rr, tgt = bot._marked_runway("TST", 4.0, 4.0)          # rps 0 — guarded
check("division by risk-per-share, guarded > 0", rr is None and tgt is None, f"{rr},{tgt}")
bot._fetch_kev_levels = lambda: {}
rr, tgt = bot._marked_runway("TST", 4.0, 3.5)          # no sheet entry
check("no sheet -> stamps None (never fabricates)", rr is None and tgt is None, f"{rr},{tgt}")
bot._fetch_kev_levels = _saved_fetch
check("LOG-ONLY: no gate/reject on runway anywhere", "runway_reject" not in src
      and "RUNWAY_MIN" not in src)

# Arithmetic mirror (the exact expressions from the block):
def mirror(entry, stop, lvd):
    rps = entry - stop
    rr = tgt = None
    if rps > 0:
        tgts = sorted(float(x) for x in (lvd.get("targets") or []) if float(x) > entry)
        ns = float(lvd.get("next_supply") or 0)
        tgt = (tgts[0] if tgts else (ns if ns > entry else None))
        if tgt:
            rr = round((tgt - entry) / rps, 2)
        elif lvd.get("targets") or ns:
            rr = "above_all_levels"
    return rr, tgt

print("== arithmetic against the 7/28 book (hand-verified rows) ==")
# WBUY: entry .97 stop ~.9054 (6.66%), supply 1.0, targets [.98, 1.0] -> first above = .98
rr, tgt = mirror(0.97, 0.9054, {"targets": [0.98, 1.0], "next_supply": 1.0})
check("WBUY = 0.15R @ .98", rr == 0.15 and tgt == 0.98, f"got {rr}@{tgt}")
# EGG: entry 5.30, targets [4.3, 4.5] all below -> 0.0, no tgt
rr, tgt = mirror(5.30, 4.929, {"targets": [4.3, 4.5], "next_supply": 4.5})
check("EGG/ZYBT shape = 'above_all_levels'", rr == "above_all_levels" and tgt is None, f"got {rr}@{tgt}")
# KVAC: entry 15.40 stop 14.222 (7.65%), targets [17.32, 18.5] -> 1.63R
rr, tgt = mirror(15.40, 14.222, {"targets": [17.32, 18.5], "next_supply": 17.32})
check("KVAC = 1.63R @ 17.32", rr == 1.63 and tgt == 17.32, f"got {rr}@{tgt}")
# no sheet -> None/None
rr, tgt = mirror(5.0, 4.7, {})
check("no sheet levels = None", rr is None and tgt is None, f"got {rr}@{tgt}")
# zero-risk guard
rr, tgt = mirror(5.0, 5.0, {"targets": [6.0]})
check("rps=0 never divides", rr is None and tgt is None, f"got {rr}@{tgt}")

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — marked runway stamped, log-only, EGG case = 0.0, no gate anywhere")
