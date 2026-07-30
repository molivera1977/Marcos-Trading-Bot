"""GAUNTLET: anchor-maturity gate vs the hidden lane's real tape (7/27-7/29 disaster names).
For each historical hidden trade: replay the REAL detector over the archived 10s tape with the
gate ON, and report (a) is the original losing fire refused, (b) what mature fires remain (the
lane's new sample), (c) grade any mature fires on the honest harness."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent/"rig"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
import harness
bot = load_bot()
bot.CURL_FIRE_MAX_AGE_SECS = 10**9
CASES = [("2026-07-27","LVWR"),("2026-07-27","VEEE"),("2026-07-28","WLDS"),
         ("2026-07-29","NCRA"),("2026-07-29","AMIX")]
print(f"gate: HIDDEN_ANCHOR_REQ={bot.HIDDEN_ANCHOR_REQ} MIN_BARS={bot.HIDDEN_ANCHOR_MIN_BARS}\n")
tot_new=0.0; n_new=0
for day, tk in CASES:
    b = harness.bars(tk, day)
    if not b: print(f"{day[5:]} {tk}: no tape"); continue
    bot._he_st.pop(tk, None)
    pv=vol=0.0; fires=[]
    for i,(k,o,h,l,c,v,hm) in enumerate(b):
        pv += ((h+l+c)/3.0)*v; vol += v
        vw = pv/vol if vol>0 else 0.0
        f = bot.hidden_entry_step(tk, [(k,o,h,l,c,v)], vw)
        if f: fires.append((i,hm,f))
    st = bot._he_st.get(tk) or {}
    print(f"{day[5:]} {tk}: bars={len(b)}  MATURE fires={len(fires)}  (gate refusals logged as shadow rows)")
    for i,hm,f in fires[:4]:
        rep = harness.replay(tk, day, f["px"], f["stop"], i0=i)
        pl = rep["pnl"] if rep and not rep.get("refused") else None
        print(f"    {hm} px {f['px']} stop {f['stop']} nbars-ok  -> harness P&L {pl}")
        if pl is not None: tot_new += pl; n_new += 1
print(f"\nmature-fire cohort: n={n_new}  total ${tot_new:+.2f}")
