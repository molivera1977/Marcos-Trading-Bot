"""DOES THE VOLUME MULTIPLE DO THE CHART GATE'S JOB? (7/30, Marcos: "i think the volume multiplier
does what the chart gate is asked to do, filter out slow movers that have a better chance of
wiggling and knifing")

His hypothesis predicts TWO things:
  (1) as vol_mult rises, the KNIFE RATE falls (fewer trades stopped out fast)
  (2) the chart gate adds nothing on top of a high vol_mult (redundant filters)
Measured: time-to-stop distribution + gate-on/gate-off P&L at each threshold."""
import sys, pathlib, json, urllib.request, collections, statistics as st
import harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot(); bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")

sheets, uni = {}, collections.defaultdict(set)
for d in DAYS:
    try: sheets[d] = json.load(urllib.request.urlopen(f"{harness.U}/api/kev_watchlist?date={d}", timeout=20)).get("levels") or {}
    except Exception: sheets[d] = {}
    rows = (json.load(urllib.request.urlopen(f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") in ("triggered_ignition", "ignition_low_room_soft", "daygain_reject") and r.get("ticker"):
            uni[d].add(r["ticker"])

def run(vol):
    bot.IGNITION_VOL_MULT = vol; bot.IGNITION_MAX_EXT = 0.15
    bot.IGNITION_MIN_ABS_VOL = 5000; bot._IG10_MIN_ABS_VOL = 5000 / 6.0
    out = []
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
                # time to stop (seconds) — None if it never stopped
                tts = None
                for j in range(i + 1, len(b)):
                    if b[j][3] <= s: tts = b[j][0] - b[i][0]; break
                # chart gate verdict via the REAL function
                bot._kev_levels_cache.update({"date": d, "ts": 9e18, "levels": sheets[d]})
                v = bot._chart_break_gate(tk, e, "ignition")[0]
                out.append({"pnl": rep["pnl"], "tts": tts, "gate": v})
    return out

print(f"{'vol':>5}{'n':>5}{'knife<2min':>12}{'knife<5min':>12}{'never stop':>12}{'med time-to-stop':>18}")
data = {}
for v in (2.0, 3.0, 4.0, 4.5, 5.0, 6.0):
    r = run(v); data[v] = r
    n = len(r)
    k2 = sum(1 for x in r if x["tts"] is not None and x["tts"] <= 120)
    k5 = sum(1 for x in r if x["tts"] is not None and x["tts"] <= 300)
    never = sum(1 for x in r if x["tts"] is None)
    tts = [x["tts"] for x in r if x["tts"] is not None]
    print(f"{v:5.1f}{n:5}{100*k2/n:11.0f}%{100*k5/n:11.0f}%{100*never/n:11.0f}%{(st.median(tts)/60 if tts else 0):15.1f}m")

print(f"\n{'vol':>5}{'gate OFF (all)':>18}{'gate ON (allow)':>18}{'gate adds':>12}")
for v in (2.0, 3.0, 4.0, 4.5, 5.0, 6.0):
    r = data[v]
    off = sum(x["pnl"] for x in r)
    on  = sum(x["pnl"] for x in r if x["gate"] == "allow")
    non = sum(1 for x in r if x["gate"] == "allow")
    print(f"{v:5.1f}{off:18.2f}{on:14.2f} (n={non:2}){on-off:12.2f}")
