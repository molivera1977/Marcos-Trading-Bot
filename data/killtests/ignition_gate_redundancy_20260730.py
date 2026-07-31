"""DOES 5.0x VOLUME MAKE THE GATES REDUNDANT? (7/30, Marcos: "test to see if these new parameters
even need the gate. the new parameters might do the job for us")

For each ignition fire at a given parameter set, evaluate the CHART GATE verdict against the day's
real sheet (allow if entry >= break, or within CHART_GATE_BAND below it; block otherwise; skip when
the name has no marked level) and split P&L by verdict. If 5.0x fires are profitable REGARDLESS of
gate verdict, the gate adds nothing on this lane. If the gate still separates, it earns its place."""
import sys, pathlib, json, urllib.request, collections
import harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot(); bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")
BAND = getattr(bot, "CHART_GATE_BAND", 0.02)

sheets, uni = {}, collections.defaultdict(set)
for d in DAYS:
    try:
        sheets[d] = json.load(urllib.request.urlopen(f"{harness.U}/api/kev_watchlist?date={d}", timeout=20)).get("levels") or {}
    except Exception:
        sheets[d] = {}
    rows = (json.load(urllib.request.urlopen(f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") in ("triggered_ignition", "ignition_low_room_soft", "daygain_reject") and r.get("ticker"):
            uni[d].add(r["ticker"])

def chart_verdict(d, tk, px):
    lv = (sheets.get(d) or {}).get(tk) or {}
    try: brk = float(lv.get("break") or 0)
    except (TypeError, ValueError): brk = 0.0
    if brk <= 0: return "no_level"
    if px >= brk: return "allow"
    if px >= brk * (1 - BAND): return "allow_band"
    return "BLOCK"

def run(vol, label):
    bot.IGNITION_VOL_MULT = vol
    bot.IGNITION_MAX_EXT = 0.15
    bot.IGNITION_MIN_ABS_VOL = 5000; bot._IG10_MIN_ABS_VOL = 5000 / 6.0
    buckets = collections.defaultdict(lambda: [0.0, 0, 0])
    for d in DAYS:
        for tk in uni[d]:
            b = harness.bars(tk, d)
            if not b: continue
            bot._ig10_st.pop(tk, None); taken = False
            for i, bar in enumerate(b):
                f = bot.ignition_10s_step(tk, [bar[:6]])
                if not f or taken: continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s): continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if not rep or rep.get("refused"): continue
                taken = True
                v = chart_verdict(d, tk, e)
                z = buckets[v]; z[0] += rep["pnl"]; z[1] += 1; z[2] += (rep["pnl"] > 0)
    print(f"\n== {label}")
    print(f"   {'chart-gate verdict':20}{'n':>5}{'total $':>11}{'$/fire':>9}{'wins':>7}")
    tot = n = 0
    for v in ("allow", "allow_band", "BLOCK", "no_level"):
        z = buckets.get(v)
        if not z or z[1] == 0: continue
        print(f"   {v:20}{z[1]:5}{z[0]:11.2f}{z[0]/z[1]:9.2f}{z[2]:7}")
        tot += z[0]; n += z[1]
    passed = sum(buckets[v][0] for v in ("allow", "allow_band"))
    pn = sum(buckets[v][1] for v in ("allow", "allow_band"))
    print(f"   {'ALL (gate off)':20}{n:5}{tot:11.2f}{(tot/n if n else 0):9.2f}")
    print(f"   {'GATE ON (allow only)':20}{pn:5}{passed:11.2f}{(passed/pn if pn else 0):9.2f}")

run(2.0, "BASELINE 2.0x")
run(5.0, "TIGHTENED 5.0x")
