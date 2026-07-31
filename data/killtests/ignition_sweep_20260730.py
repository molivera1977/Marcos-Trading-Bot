"""IGNITION PARAMETER SWEEP (7/30, Marcos: "tweak some numbers and let's see what happens").
Re-runs the REAL detector at each parameter setting over the archived tape, then prices every
resulting fire through the honest harness. Not bucket-reading — the detector actually re-fires.
Held constant: ladder (kev25), sizing chain, slippage. Downstream gates NOT applied (detector
population), so read RELATIVE differences, not absolute dollars."""
import sys, pathlib, collections
import harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")

# universe: names that produced an ignition fire at baseline on each day
import json, urllib.request
universe = collections.defaultdict(set)
for d in DAYS:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") in ("triggered_ignition", "ignition_low_room_soft", "daygain_reject"):
            if r.get("ticker"): universe[d].add(r["ticker"])
print("universe:", {d: len(v) for d, v in universe.items()})

BASE = dict(vol=bot.IGNITION_VOL_MULT, maxext=bot.IGNITION_MAX_EXT,
            minabs=bot.IGNITION_MIN_ABS_VOL, look=bot.IGNITION_BASE_LOOKBACK)
print("baseline:", BASE, "\n")

def run(vol, maxext, minabs, label):
    bot.IGNITION_VOL_MULT = vol
    bot.IGNITION_MAX_EXT = maxext
    bot.IGNITION_MIN_ABS_VOL = minabs
    bot._IG10_MIN_ABS_VOL = minabs / 6.0
    tot = 0.0; n = 0; w = 0
    for d in DAYS:
        for tk in universe[d]:
            b = harness.bars(tk, d)
            if not b: continue
            bot._ig10_st.pop(tk, None)
            for i, bar in enumerate(b):
                f = bot.ignition_10s_step(tk, [bar[:6]])
                if not f: continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s): continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if not rep or rep.get("refused"): continue
                tot += rep["pnl"]; n += 1; w += (rep["pnl"] > 0)
    print(f"  {label:34}{n:5} fires{tot:11.2f}{(tot/n if n else 0):9.2f}/fire{w:6} wins")
    return tot, n

print(f"  {'setting':34}{'n':>5}      {'total':>10}{'$/fire':>13}{'wins':>6}")
run(2.0, 0.15, 5000,  "BASELINE (live: 2.0x, +15%, 5k)")
run(3.0, 0.15, 5000,  "vol 3.0x")
run(4.0, 0.15, 5000,  "vol 4.0x")
run(5.0, 0.15, 5000,  "vol 5.0x")
run(2.0, 0.10, 5000,  "maxext +10%")
run(2.0, 0.08, 5000,  "maxext +8%")
run(2.0, 0.15, 10000, "min abs vol 10k (pre-sweep)")
run(4.0, 0.10, 10000, "COMBINED 4.0x / +10% / 10k")
run(5.0, 0.10, 10000, "COMBINED 5.0x / +10% / 10k")
