"""IGNITION FINE SWEEP + OUT-OF-SAMPLE SPLIT (7/30, Marcos: "run the finer sweep").
PRE-REGISTERED before results are seen:
  IN-SAMPLE  = 7/27 + 7/28   OUT-OF-SAMPLE = 7/29 + 7/30
  DECISION RULE: a threshold is CREDIBLE only if it beats baseline (2.0x) on BOTH halves.
  If the in-sample best fails out-of-sample, the finding is an overfit and dies.
Population = first ignition fire per ticker per day (the live once-per-ticker cap), chart gate NOT
applied (it is a separate open question), real detector stops, honest harness."""
import sys, pathlib, json, urllib.request, collections
import harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot(); bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
IN  = ("2026-07-27", "2026-07-28")
OUT = ("2026-07-29", "2026-07-30")

uni = collections.defaultdict(set)
for d in IN + OUT:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") in ("triggered_ignition", "ignition_low_room_soft", "daygain_reject") and r.get("ticker"):
            uni[d].add(r["ticker"])

def run(vol, days):
    bot.IGNITION_VOL_MULT = vol
    bot.IGNITION_MAX_EXT = 0.15
    bot.IGNITION_MIN_ABS_VOL = 5000; bot._IG10_MIN_ABS_VOL = 5000 / 6.0
    tot = n = w = 0
    for d in days:
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
                taken = True; tot += rep["pnl"]; n += 1; w += (rep["pnl"] > 0)
    return tot, n, w

print(f"{'vol_mult':>9} | {'IN-SAMPLE (7/27-28)':>32} | {'OUT-OF-SAMPLE (7/29-30)':>32}")
print(f"{'':>9} | {'n':>4}{'total':>11}{'$/fire':>9}{'w':>5} | {'n':>4}{'total':>11}{'$/fire':>9}{'w':>5}")
base_in = base_out = None
for v in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0):
    ti, ni, wi = run(v, IN)
    to, no, wo = run(v, OUT)
    if v == 2.0: base_in, base_out = (ti/ni if ni else 0), (to/no if no else 0)
    mark = ""
    if v != 2.0 and ni and no:
        better_both = (ti/ni > base_in) and (to/no > base_out)
        mark = "  <== beats baseline on BOTH" if better_both else ""
    print(f"{v:9.1f} | {ni:4}{ti:11.2f}{(ti/ni if ni else 0):9.2f}{wi:5} | {no:4}{to:11.2f}{(to/no if no else 0):9.2f}{wo:5}{mark}")
