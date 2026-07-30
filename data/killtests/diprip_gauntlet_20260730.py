"""DIP-RIP GAUNTLET: the real 7/29 AMIX halt tape through the REAL detector + honest harness.
Ground truth: halt flagged 09:39:38; resumption 09:40:40 (o5.96 l5.50); level 5.29 (sheet);
Kev bought 5.49 -> rode to 7.25. PASS = the lane fires on the resumption confirm (~09:41),
never on the knife bar, and the harness P&L is a winner. Also a NEGATIVE control: SPRC (no halt)
must never arm/fire."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent/"rig"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
import harness
bot = load_bot()

LVL = 5.29
b = harness.bars("AMIX", "2026-07-29")
halt_k = max(x[0] for x in b if x[6] <= "09:36:00")           # last print before the gap
bot._dr_st.clear()
bot.dip_rip_arm("AMIX", halt_k, LVL)
fire = None
for k,o,h,l,c,v,hm in b:
    if hm < "09:36:00" or hm > "10:00:00": continue
    f = bot.dip_rip_step("AMIX", [(k,o,h,l,c,v)])
    if f:
        fire = (hm, f); break
print("ARM at halt bar:", [x[6] for x in b if x[0]==halt_k])
print("state after walk:", {k2:v2 for k2,v2 in (bot._dr_st.get('AMIX') or {}).items() if k2!='tag'},
      "tag:", (bot._dr_st.get('AMIX') or {}).get('tag'))
if fire:
    hm, f = fire
    print(f"\nFIRE at {hm}: entry {f['px']}  stop {f['stop']}  (level {f['level']}, tag low {f['tag_low']})")
    i0 = next(i for i,x in enumerate(b) if x[6] >= hm)
    rep = harness.replay("AMIX", "2026-07-29", f["px"], f["stop"], i0=i0)
    print(f"harness: shares {rep['shares']} ({rep['clamp']})  P&L ${rep['pnl']:+.2f}")
    for e in rep["events"][:6]: print("   ", e)
else:
    print("\nNO FIRE — gauntlet FAILED")
print("\nNEGATIVE CONTROL — SPRC (no halt was flagged): watch must never exist")
print("SPRC state:", bot._dr_st.get("SPRC"))
