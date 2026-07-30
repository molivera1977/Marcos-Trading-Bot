"""Rig: DIP AND RIP (7/30 — Marcos: "go ahead and build it" + "Test it before you ship it").
Kev's halt strategy: halt on a sheet name -> resumption flush tags the marked level -> CONFIRM bar
fires, stop just under the level. Functional machine tests + wiring pins. The real-tape gauntlet
(AMIX 7/29 through the harness) lives in data/killtests/diprip_gauntlet_20260730.py."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

LVL = 5.29
NOW = int(time.time()) // 10 * 10
def B(i, o, h, l, c, v=50000):          # bars AFTER the halt bar (armed_k = NOW-600)
    return (NOW - 600 + i * 10, o, h, l, c, v)

print("== the AMIX shape, synthetically ==")
bot._dr_st.clear()
bot.dip_rip_arm("AAA", NOW - 610, LVL)
check("arms once (state exists)", "AAA" in bot._dr_st and not bot._dr_st["AAA"]["done"])
bot.dip_rip_arm("AAA", NOW - 300, 9.99)
check("second arm same day is a no-op (one watch/name/day)", bot._dr_st["AAA"]["level"] == LVL)
# resumption knife bar: flushes INTO the zone, closes at its low — tags but must NOT fire
r = bot.dip_rip_step("AAA", [B(1, 5.96, 5.96, 5.50, 5.50)])
check("knife bar tags the zone but never fires (TAG != entry)", r is None and bot._dr_st["AAA"]["tag"] is not None)
# confirm bar: closes up, above the level -> FIRE with stop just under the level
r = bot.dip_rip_step("AAA", [B(2, 5.63, 5.96, 5.63, 5.90)])
check("confirm bar fires", r is not None)
check("entry px = confirm close", r and abs(r["px"] - 5.90) < 1e-9)
check("stop just under the LEVEL (not the wick)", r and abs(r["stop"] - round(LVL * 0.997, 4)) < 1e-9)
check("watch retires after firing (one shot)", bot._dr_st["AAA"]["done"] is True)
r = bot.dip_rip_step("AAA", [B(3, 5.9, 6.2, 5.9, 6.1)])
check("no second fire same day", r is None)

print("== failure paths ==")
bot._dr_st.clear(); bot.dip_rip_arm("BBB", NOW - 610, LVL)
r = bot.dip_rip_step("BBB", [B(1, 5.6, 5.6, 5.1, 5.15)])       # decisive close below level
check("close <1% under the level retires the watch (level_lost)", r is None and bot._dr_st["BBB"]["why"] == "level_lost")
bot._dr_st.clear(); bot.dip_rip_arm("CCC", NOW - 4000, LVL)
bot._dr_st["CCC"]["armed_k"] = NOW - 4000
r = bot.dip_rip_step("CCC", [ (NOW - 3990, 5.6, 5.7, 5.5, 5.6, 1000), (NOW - 100, 5.6, 5.7, 5.55, 5.65, 1000) ])
check("window expiry retires the watch", bot._dr_st["CCC"]["why"] == "window_expired")
bot._dr_st.clear(); bot.dip_rip_arm("DDD", NOW - 610, LVL)
r = bot.dip_rip_step("DDD", [B(1, 6.4, 6.5, 6.2, 6.3), B(2, 6.3, 6.4, 6.25, 6.35)])
check("no tag = no fire (price never came back to the level)", r is None and bot._dr_st["DDD"]["tag"] is None)

print("== kill switch + wiring ==")
check("DIP_RIP default ON, zone 5%, window 600s",
      bot.DIP_RIP is True and bot.DIPRIP_ZONE == 0.05 and bot.DIPRIP_WINDOW_S == 600.0)
check("armed only from the halt-suspect site, sheet+above-level guarded",
      "dip_rip_arm(t, _lastk, _lvl_dr)" in src and "_lc_dr) > _lvl_dr" in src)
check("conversion branch exists, RTH-only, slotted 'dr'",
      '_curl_rth_slot(t, "dr", _hm_curl)' in src and 'triggered_dip_rip' in src)
check("slot refund knows the lane", '"dip_rip": "dr"' in src)
check("swap guard covers the new fire", "(_zf_fire, _vr_fire, _he_fire, _dr_fire)" in src)
check("boot banner reports DIP_RIP", "DIP_RIP={int(DIP_RIP)}" in src)
check("every non-fire outcome logs (armed/tag/expired/level_lost)",
      all(x in src for x in ('"diprip_armed"', '"diprip_tag"', '"diprip_expired"', '"diprip_level_lost"')))

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — halt -> flush tags Kev's level -> confirm fires with the stop under the level; one shot; all outcomes logged")
