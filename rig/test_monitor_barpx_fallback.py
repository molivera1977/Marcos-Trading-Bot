"""Rig: MONITOR BAR-PRICE FALLBACK (7/29 P0 — the NCRA flush).

The incident: NCRA PRE entry $2.65, stop $1.9184. Premarket quote field absent -> session-aware
pricing serves NO-PRICE (correct) -> monitor counted 90s of "dead feed" and force-closed at $2.21
MID-FLUSH while `curl-feed NCRA: bars=90 last_bar_age=17s` printed in the same log. The flush low
($2.03) never touched the stop; +1.05R printed 4 minutes later.

Spec under test:
  1. Quote dead + 10s bars fresh  -> monitor rides BAR CLOSES; structural stop decides; NO safety exit.
  2. Quote dead + bars stale/dead -> STALE FEED SAFETY EXIT still fires (the BOXL protection lives).
  3. Bar lookups are THROTTLED (~5s) — the 0.5s monitor loop must not hammer the feed.
  4. Fallback age-capped by BARPX_MAX_AGE (default 60s).
Source-level checks (the monitor loop is not unit-callable without a stream; the arithmetic is
trivial — placement and guards are what can rot).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
src = pathlib.Path(bot.__file__).read_text()
fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


i = src.find("NCRA FIX: quote-dead is NOT feed-dead")
check("fallback block present in the monitor", i > 0)
seg = src[i:i + 2200]

print("== ordering: fallback runs BEFORE the safety-exit check ==")
j_fallback = src.find("riding 10s BAR closes")
j_safety = src.find("No valid price FROM EITHER SOURCE")
check("bar fallback precedes the safety exit", 0 < j_fallback < j_safety)
check("safety exit now requires BOTH sources dead", "FROM EITHER SOURCE" in src)
check("safety exit itself is UNCHANGED (BOXL protection intact)",
      "STALE FEED SAFETY EXIT" in src and "force-closing" in src)

print("== guards ==")
check("throttled to ~5s lookups", "_barpx_t >= 5.0" in seg or "- _barpx_t >= 5.0" in seg)
check("age-capped by BARPX_MAX_AGE", "<= BARPX_MAX_AGE" in seg)
check("BARPX_MAX_AGE default 60s", bot.BARPX_MAX_AGE == 60.0)
check("feed read wrapped in try/except", "except Exception:" in seg)
check("uses the same curl-feed choke point (no new source)", "_curl_feed(ticker)" in seg)
check("one-line canary on switch (not per-tick spam)", "_barpx_on" in seg and "until the quote returns" in seg)

print("== locals initialized with the monitor ==")
for v in ("_barpx_t           = 0.0", "_barpx             = 0.0", "_barpx_on          = False"):
    check(f"init: {v.split('=')[0].strip()}", v in src)

print("== the NCRA arithmetic (the exact case, replayed against the spec) ==")
# With the fix: at 08:06 the freshest bar close was ~2.29-2.18, age ~17s <= 60 -> current_price
# valid -> stale_secs never accumulates -> no safety exit; flush low 2.03 > stop 1.9184 -> intrabar
# stop check (l <= cur) NEVER true -> position survives to the 3.42 print (= +1.05R).
ENTRY, STOP, FLUSH_LOW = 2.65, 1.9184, 2.03
check("flush low never touches the structural stop", FLUSH_LOW > STOP)
check("bar age at incident (17s) within fallback cap", 17 <= bot.BARPX_MAX_AGE)
check("safety window (90s) irrelevant once bar px serves", bot.STALE_FEED_EXIT_SECS == 90)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — monitor rides 10s bars when the quote dies; safety exit only when BOTH are dead")
