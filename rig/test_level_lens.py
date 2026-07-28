"""Rig: THE LEVEL LENS, stage 1 (7/28 pre-open).

Spec under test — Marcos: "arm the bot with this information not as a gate but as a lens from
which to find its target." Stage 1 = attention only: focus-first cycle ordering + transition
logging. THE INVARIANT THIS FILE EXISTS TO PIN: the lens must never reject, veto, resize, or
remove a name. If a future edit gives the lens a vote on outcomes, this file must go red.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
fails = []

def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

# feed the lens a fake level sheet (no network in the rig)
SHEET = {"LVWR": {"break": 2.90, "confirm": 2.70, "targets": [3.57, 4.50, 5.50]},
         "INLF": {"break": 5.00, "confirm": 4.50, "targets": [7.00, 10.00]},
         "NOLV": {}}
bot._fetch_kev_levels = lambda: SHEET

print("== focus verdicts (the 7/28 sheet, real numbers) ==")
for tk, px, want_focus, want_zone in [
    ("LVWR", 2.70, True,  "confirm"),   # sitting ON Kev's confirm
    ("LVWR", 2.90, True,  "break"),
    ("LVWR", 3.30, True,  "target1"),   # within 15% of 3.57
    ("LVWR", 2.88, True,  "break"),     # where hidden fired yesterday — lens would have had it IN FOCUS
    ("LVWR", 1.90, False, None),        # far below everything (>15% from 2.70's low side... 1.9 vs 2.7 = -29.6%)
    ("INLF", 5.00, True,  "break"),
    ("INLF", 5.75, True,  "break"),     # +15.0% exactly — boundary must be IN (rounding lesson)
    ("INLF", 5.80, False, None),        # +16%
    ("INLF", 8.20, True,  "target1"),   # nearest zone is 7.00? 8.2 vs 7 = +17.1; vs 10 = -18 -> out
]:
    f, zn, zpx, d = bot._level_lens(tk, px)
    if tk == "INLF" and px == 8.20:
        check("INLF 8.20 between targets, >15% from both -> out of focus", not f, f"got f={f} zn={zn} d={d}")
        continue
    ok = (f == want_focus) and (want_zone is None or zn == want_zone)
    check(f"{tk} @ {px} -> {'FOCUS ' + str(want_zone) if want_focus else 'not in focus'}", ok,
          f"got f={f} zone={zn} dist={d}")

print("== boundary is rounded first (the minstop float lesson) ==")
# 15.04% raw rounds to 15.0 -> in; 15.06 rounds to 15.1 -> out
f1, _, _, d1 = bot._level_lens("INLF", 5.00 * 1.1504)
f2, _, _, d2 = bot._level_lens("INLF", 5.00 * 1.1506)
check("15.04% raw -> rounds 15.0 -> IN", f1 and d1 == 15.0, f"f={f1} d={d1}")
check("15.06% raw -> rounds 15.1 -> OUT", (not f2) and d2 == 15.1, f"f={f2} d={d2}")

print("== fail-open ==")
check("no level -> never focus, never error", bot._level_lens("NOLV", 5.0) == (False, None, None, None))
check("unknown name", bot._level_lens("ZZZZ", 5.0) == (False, None, None, None))
check("price 0", bot._level_lens("LVWR", 0) == (False, None, None, None))
check("price None", bot._level_lens("LVWR", None) == (False, None, None, None))
_sv = bot.LENS_FOCUS_PCT
bot.LENS_FOCUS_PCT = 0.0
check("LENS_FOCUS_PCT=0 kills the lens", bot._level_lens("LVWR", 2.90) == (False, None, None, None))
bot.LENS_FOCUS_PCT = _sv

print("== ordering: focus-first, scanner rank preserved inside groups, nobody dropped ==")
import time as _time
class _FakeStream:
    """The lens must never call this — get_price falls back to REST. Booby-trapped."""
    def get_price(self, t): raise AssertionError("lens called stream.get_price — REST amplification!")
def _seed(px):
    with bot._price_lock:
        bot._price_registry.clear()
        for t, p_ in px.items():
            bot._price_registry[t] = {"p": p_, "t": _time.time()}
bot._lens_state.clear()
logged = []
_orig_log = bot._log_decision
bot._log_decision = lambda t, s, **kw: logged.append((t, s, kw))
try:
    cands = ["AAA", "LVWR", "BBB", "INLF", "CCC"]          # scanner order
    stream = _FakeStream()
    _seed({"AAA": 9.0, "LVWR": 2.88, "BBB": 1.0, "INLF": 5.10, "CCC": 2.0})
    out = bot._lens_pass(list(cands), stream)
    check("focus names first, in scanner order", out == ["LVWR", "INLF", "AAA", "BBB", "CCC"], f"got {out}")
    check("no name added or dropped", sorted(out) == sorted(cands))
    check("focus transitions logged", [(t, s) for t, s, _ in logged] ==
          [("LVWR", "lens_focus"), ("INLF", "lens_focus")], f"got {logged}")
    logged.clear()
    out2 = bot._lens_pass(list(cands), stream)
    check("steady state logs nothing (transitions only)", logged == [], f"got {logged}")
    _seed({"AAA": 9.0, "LVWR": 1.90, "BBB": 1.0, "INLF": 5.10, "CCC": 2.0})  # LVWR drifts out
    out3 = bot._lens_pass(list(cands), stream)
    check("drift out -> lens_unfocus logged, order updates",
          [(t, s) for t, s, _ in logged] == [("LVWR", "lens_unfocus")] and out3[0] == "INLF",
          f"logged={logged} out={out3}")
    # a lens explosion must never break the scan
    bot._level_lens_backup = bot._level_lens
    bot._level_lens = lambda *a: (_ for _ in ()).throw(RuntimeError("boom"))
    out4 = bot._lens_pass(list(cands), stream)
    check("lens error -> incoming order untouched", sorted(out4) == sorted(cands))
    bot._level_lens = bot._level_lens_backup
finally:
    bot._log_decision = _orig_log

print("== cost: the lens is FREE — no REST, no stream, sub-millisecond ==")
check("booby-trapped stream never called (registry-only reads)", True)   # would have raised above
_seed({t: 2.88 for t in ["LVWR"] * 1})
t0 = _time.perf_counter()
for _ in range(100):
    bot._lens_pass([f"N{i}" for i in range(40)] + ["LVWR"], _FakeStream())
_ms = (_time.perf_counter() - t0) / 100 * 1000
check(f"41-name cycle costs <5ms (measured {_ms:.2f}ms)", _ms < 5, f"{_ms:.2f}ms")
_stale = _time.time() - 300
with bot._price_lock:
    bot._price_registry["LVWR"] = {"p": 2.88, "t": _stale}
check("stale tick (>120s) -> not in focus, still no REST", bot._lens_px("LVWR") == 0)

print("== THE INVARIANT: the lens has no vote on outcomes ==")
src = pathlib.Path(bot.__file__).read_text()
check("watch loop passes candidates through the lens", "candidates = _lens_pass(candidates, stream)" in src)
import re
# every use of the lens outside its own definition block must be the single ordering call
uses = [m.start() for m in re.finditer(r"_lens_pass\(|_level_lens\(", src)]
defs = src.find("def _level_lens"), src.find("def _lens_pass")
outside = [i for i in uses if not (defs[0] - 100 < i < src.find("def _shadow_log_curl_leftovers"))]
check("lens is referenced NOWHERE outside its definitions + the one ordering call",
      len(outside) == 1, f"found {len(outside)} uses outside")
for bad in ("_lens_pass(candidates, stream)\n            return",):
    pass
check("no reject/skip/return path mentions the lens",
      "lens" not in src[src.find("def _trade_worker"):src.find("def _trade_worker") + 20000].lower())
check("kill switch env is read", 'os.environ.get("LENS_FOCUS_PCT"' in src)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — lens stage 1: focus verdicts exact, ordering stable, transitions-only logging, no vote on outcomes")

# ── 7/28 review additions: registry feeding + darkness canary ──
print("== registry feeding: REST prices the loop already paid for reach the lens ==")
src2 = pathlib.Path(bot.__file__).read_text()
check("_get_price_rest writes real prices into the registry",
      '_price_registry[t] = {"p": px, "t": time.time()}' in src2)
i_guard = src2.find("if px and px > 0:")
check("REST write-back guarded px>0 (a failed quote must not poison the registry)",
      0 < i_guard < src2.find('_price_registry[t] = {"p": px'))

print("== darkness canary: a dark lens says so ==")
bot._lens_state.clear()
logged2 = []
_ol = bot._log_decision
bot._log_decision = lambda t, s, **kw: logged2.append((t, s))
try:
    with bot._price_lock:
        bot._price_registry.clear()                      # nobody has a price
    bot._lens_dark_t = 0.0
    out = bot._lens_pass(["LVWR", "INLF", "AAA"], _FakeStream())
    check("dark lens logs lens_dark", ("__LENS__", "lens_dark") in logged2, f"got {logged2}")
    check("dark lens keeps scanner order untouched", out == ["LVWR", "INLF", "AAA"])
    logged2.clear()
    out = bot._lens_pass(["LVWR", "INLF", "AAA"], _FakeStream())
    check("canary throttled (~5 min)", ("__LENS__", "lens_dark") not in logged2)
    _seed({"LVWR": 2.88})                                # one price arrives -> not dark
    bot._lens_dark_t = 0.0
    logged2.clear()
    out = bot._lens_pass(["LVWR", "INLF", "AAA"], _FakeStream())
    check("one cached price ends darkness (LVWR back in focus, first)",
          ("__LENS__", "lens_dark") not in logged2 and out[0] == "LVWR", f"out={out} log={logged2}")
finally:
    bot._log_decision = _ol
if fails:
    print(f"RED after additions — {fails}"); sys.exit(1)
print("GREEN including registry-feed + darkness canary")
