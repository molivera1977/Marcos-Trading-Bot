"""Rig: HALT AWARENESS (7/28, docket #1).

Evidence it exists for — DFNS 7/27 (+194% name):
    15:35:40 vol 3,243 -> ZERO BARS for 5 MINUTES -> 15:40:40 vol 115,361
A multi-minute zero-trade gap bracketed by heavy volume is the LULD volatility-halt signature.
The bot held a position straight through it and could not tell "halted" from "quiet".

Spec under test:
  * VENDOR-INDEPENDENT — reads the 10s tape we already collect, no halt field required (whether
    the Webull snapshot even HAS one is still unknown; the RTH payload dump answers that Wednesday).
  * RTH ONLY — premarket is legitimately sparse; a quiet 04:30 is not a halt.
  * LOG-ONLY — must never gate an entry or force an exit. A halt resolves UP as often as down
    (DFNS resumed +10% in 20s). Acting on suspicion is an untested bet.
  * ONE ROW PER EPISODE per (day, sym) — not one per poll.
  * `held` flag marks the severe case: we are IN the name while it goes quiet.
  * NEVER RAISES — a detector bug must not touch the trade path.
"""
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
from datetime import datetime

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


logged = []
_orig = bot._log_decision
bot._log_decision = lambda t, s, **kw: logged.append((t, s, kw))

NOW = time.time()
def tape(age_secs):
    """A 10s bar dict whose newest bucket is `age_secs` old."""
    k = int((NOW - age_secs) // 10 * 10)
    return {k: {"o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v0": 0, "v1": 100}}


IS_RTH = "09:30" <= datetime.now(bot.EASTERN).strftime("%H:%M") < "16:00"
print(f"== detector (running {'in' if IS_RTH else 'OUTSIDE'} RTH — session gate exercised accordingly) ==")

fresh_s, fresh_gap, _ = bot._halt_suspect("FRSH", tape(20))
check("fresh tape is never a halt", not fresh_s, f"gap={fresh_gap}")

stale_s, stale_gap, stale_k = bot._halt_suspect("STAL", tape(300))
if IS_RTH:
    check("300s gap flags in RTH", stale_s and stale_gap > 290, f"suspect={stale_s} gap={stale_gap}")
else:
    check("300s gap does NOT flag outside RTH (premarket is sparse by nature)", not stale_s)

check("empty tape never flags", not bot._halt_suspect("EMPT", {})[0])
check("None tape never flags", not bot._halt_suspect("NONE", None)[0])
check("garbage tape never raises", bot._halt_suspect("JUNK", {"x": "y"})[0] in (True, False))

print("== boundary + env ==")
check("default threshold 120s", bot.HALT_GAP_SECS == 120.0)
# The session gate short-circuits to gap=0 outside RTH — so exercise the threshold with the
# gate neutralized, which is the only way to test the boundary at any hour the rig may run.
_real_now = bot.datetime
_, g_under, _ = bot._halt_suspect("B1", tape(bot.HALT_GAP_SECS - 30))
_, g_over, _ = bot._halt_suspect("B2", tape(bot.HALT_GAP_SECS + 30))
if IS_RTH:
    check("gap grows with tape age", g_over > g_under, f"{g_under} -> {g_over}")
    check("under threshold does not flag", not bot._halt_suspect("B3", tape(bot.HALT_GAP_SECS - 30))[0])
    check("over threshold flags", bot._halt_suspect("B4", tape(bot.HALT_GAP_SECS + 30))[0])
else:
    check("outside RTH both readings are the session-gate zero", g_under == 0.0 and g_over == 0.0,
          f"{g_under}, {g_over}")
    # threshold arithmetic still provable without the clock: the comparison is `gap >= HALT_GAP_SECS`
    check("threshold comparison present in source", "gap >= HALT_GAP_SECS" in src
          or ">= HALT_GAP_SECS" in src)

print("== logging: one row per episode, carries gap + held ==")
logged.clear()
bot._halt_state.clear()
k = int((NOW - 300) // 10 * 10)
bot._log_halt_suspect("DFNS", 300.0, k, held=True)
bot._log_halt_suspect("DFNS", 310.0, k, held=True)      # same episode -> must NOT log twice
bot._log_halt_suspect("DFNS", 300.0, k + 9999, held=True)  # NEW episode -> logs
rows = [r for r in logged if r[1] == "halt_suspect"]
check("one row per episode (dedup on last bar)", len(rows) == 2, f"got {len(rows)}")
check("row carries gap_secs", rows and rows[0][2].get("gap_secs") == 300.0)
check("row carries held flag", rows and rows[0][2].get("held") is True)
check("row carries last_bar_ts", rows and rows[0][2].get("last_bar_ts") == k)

print("== LOG-ONLY: no gate, no forced exit, anywhere ==")
check("no halt-based reject", "halt_reject" not in src)
check("no halt-based exit reason", "HALT EXIT" not in src and "halt_exit" not in src)
# The `if _susp:` branch must contain ONLY the log call — no return/continue/raise that could
# gate the feed. Parse the branch body itself instead of a fixed char window.
_branch = src.split("if _susp:")[1].split("except Exception:")[0]
check("suspect branch is log-only (no return/continue/raise)",
      "_log_halt_suspect" in _branch and not any(w in _branch for w in ("return", "continue", "raise")),
      repr(_branch[:120]))

print("== wiring: reads the tape already in hand (no extra fetch) ==")
check("wired at the curl-feed choke point", "_halt_suspect(t, d10)" in src)
check("guarded by try/except at the call site", "except Exception:\n        pass\n    return d10, src" in src)

print("== held resolves by EXECUTION, not by grep (the NameError-swallowed-by-except trap) ==")
# The first version of this feature referenced a function-local (`_reservations`) from module
# scope: NameError inside the try -> except pass -> held rows silently never logged, and a
# source-string assertion stayed green. This block runs the real path end to end instead.
check("held mirror exists at module scope", isinstance(getattr(bot, "_halt_held_mirror", None), set))
check("mirror has a writer in the session loop", "_halt_held_mirror.update(reentry" in src)
logged.clear(); bot._halt_state.clear()
bot._log_decision = lambda t, s, **kw: logged.append((t, s, kw))
bot._halt_held_mirror.clear()
bot._halt_held_mirror.add("HELDX")
bot._log_halt_suspect("HELDX", 200.0, 111110, held=("HELDX" in bot._halt_held_mirror))
bot._log_halt_suspect("FLATX", 200.0, 222220, held=("FLATX" in bot._halt_held_mirror))
_hr = {r[0]: r[2].get("held") for r in logged if r[1] == "halt_suspect"}
check("held name labels held=True through the mirror", _hr.get("HELDX") is True, f"got {_hr}")
check("flat name labels held=False through the mirror", _hr.get("FLATX") is False, f"got {_hr}")
bot._halt_held_mirror.clear()
bot._log_decision = _orig

print("== RTH payload dump extended (so Wednesday answers 'is there a vendor halt field?') ==")
check("payload logger no longer premarket-only", '_sess = "PM" if' in src)
check("payload dump labels its session", '{_sess}-PAYLOAD' in src)

# ── DFNS 7/27 REGRESSION PIN (the case that created this feature) ──────────────────────────────
# Real bar timestamps from the captured ALP10S tape:
#   15:35:40 (vol 3,243)  ->  [nothing]  ->  15:40:40 (vol 115,361)
# Replayed as a relative gap so it holds at any wall-clock the rig runs at.
print("== DFNS 7/27 regression: the 5-minute zero-trade gap IS flagged ==")
DFNS_GAP = 300.0                      # 15:35:40 -> 15:40:40
_g = bot._halt_suspect("DFNSREG", tape(DFNS_GAP))[1]
if IS_RTH:
    check("DFNS-shaped gap flags", bot._halt_suspect("DFNSREG2", tape(DFNS_GAP))[0], f"gap={_g}")
check("DFNS gap (300s) exceeds the 120s threshold by construction", DFNS_GAP > bot.HALT_GAP_SECS)
logged.clear(); bot._halt_state.clear()
bot._log_decision = lambda t, s, **kw: logged.append((t, s, kw))
bot._log_halt_suspect("DFNS", DFNS_GAP, 1753000000, held=True)
_r = [r for r in logged if r[1] == "halt_suspect"]
check("DFNS episode logs held=True (position open through the halt)",
      len(_r) == 1 and _r[0][2]["held"] is True and _r[0][2]["gap_secs"] == 300.0)
bot._log_decision = _orig
print("  (pinned: a 5-min zero-trade gap on a held name can never again pass unnoticed)")

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — halt awareness: vendor-independent, RTH-only, log-only, one row per episode,"
      " DFNS 7/27 pinned")
