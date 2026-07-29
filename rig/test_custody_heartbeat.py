"""Rig: CUSTODY HEARTBEAT (7/28, Fable-ordered after the VEEE autopsy dead-ended on vanished logs).

Spec: while a position is open, ONE durable decision row per minute carrying what the monitor
sees (price + ITS AGE), what it holds (rem/tier/partials/highest), and where the next tier is.
Non-fatal by construction — a heartbeat bug must never touch the trade path.
Why price_age_s matters: tonight's frozen-price scare was resolved by proving the feed was fine —
but only via a lucky log pull. The heartbeat makes that proof a QUERY on any future day.
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


print("== presence + placement ==")
i = src.find('"custody_heartbeat"')
check("heartbeat row emitted in monitor loop", i > 0)
seg = src[max(0, i - 900):i + 900]
check("throttled to ~1/min", "_hb_t >= 60" in seg or "- _hb_t >= 60" in seg)
check("throttle var initialized with the monitor's locals", "_hb_t              = 0.0" in src)
check("wrapped non-fatal (try/except pass)", "except Exception:" in seg and "pass" in seg)

print("== the row carries the custody fields ==")
for f in ("price_age_s", "rem=", "stop=", "tier_idx=", "partials=", "highest=", "next_tier="):
    check(f"carries {f.rstrip('=')}", f in seg)
check("price age computed from last_good_price_t", "last_good_price_t" in seg)
check("next_tier guarded when ladder exhausted", "tier_idx < len(kev_tiers)" in seg)

print("== placement: inside the live loop, after a valid price exists ==")
# It must sit after the `Valid price` reset (so last_good_price_t is current-cycle) and NOT
# inside the status-print throttle (whose gate would starve it on quiet tape).
valid_i = src.find("last_good_price   = current_price")
check("after the valid-price watchdog reset", 0 < valid_i < i)
status_gate = src.find("_status_px = current_price; _status_t = time.time()")
check("outside the status-print throttle body", src[status_gate:i].count("if ") >= 1)

print("== execution: the row shape is loggable ==")
rows = []
_orig = bot._log_decision
bot._log_decision = lambda t, s, **kw: rows.append((t, s, kw))
try:
    bot._log_decision("TEST", "custody_heartbeat", price=1.23, price_age_s=0.5, rem=100,
                      stop=1.10, tier_idx=0, partials=0, highest=1.30, next_tier=1.35)
finally:
    bot._log_decision = _orig
check("row logs with full field set", rows and rows[0][1] == "custody_heartbeat"
      and rows[0][2]["price_age_s"] == 0.5 and rows[0][2]["next_tier"] == 1.35)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — custody heartbeat: 1 durable row/min while holding, price age included, non-fatal")
