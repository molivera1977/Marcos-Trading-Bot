"""Resting exchange stop (8/2 fix) — order_type=STOP_LOSS + stop_price field.

Pins the two June defects closed at the code level (the server-side proof is the
8/2 preview_order probe: HTTP 200 with stop_price, 417 with aux_price/STP).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

failures = []

def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        failures.append(name)

# ── 1. order dict field mapping: stop_price key, never aux_price ────────────
bot = load_bot()
_orig_place_order = bot._place_order   # loader caches the module — hold the real one
captured = {}

def fake_place(ticker, shares, side, order_type, stop_price=None, limit_price=None, client_order_id=None):
    captured.update(ticker=ticker, shares=shares, side=side, order_type=order_type,
                    stop_price=stop_price)
    return "fake-id-123"

bot.DRY_RUN = False
bot.RESTING_STOP = True
bot._place_order = fake_place
rid = bot.place_stop_order("TEST", 7, 1.23)
check("live path returns order id", rid == "fake-id-123")
check("order_type is STOP_LOSS (underscore)", captured.get("order_type") == "STOP_LOSS",
      f"got {captured.get('order_type')}")
check("side SELL, shares int, stop passed", captured.get("side") == "SELL"
      and captured.get("shares") == 7 and captured.get("stop_price") == 1.23)

# ── 2. kill switch: RESTING_STOP=0 → software only, no order ────────────────
captured.clear()
bot.RESTING_STOP = False
check("RESTING_STOP=0 places nothing", bot.place_stop_order("TEST", 7, 1.23) is None
      and not captured)

# ── 3. DRY_RUN → software only, no order ────────────────────────────────────
bot.RESTING_STOP = True
bot.DRY_RUN = True
check("DRY_RUN places nothing", bot.place_stop_order("TEST", 7, 1.23) is None
      and not captured)

# ── 4. the real _place_order builds stop_price (not aux_price) into the dict ─
import inspect
src = inspect.getsource(_orig_place_order)
check("_place_order maps to stop_price key", '"stop_price"' in src and '"aux_price"' not in src)

# ── 5. cancel_order(None) is a safe no-op ───────────────────────────────────
bot2 = load_bot()
check("cancel_order(None) -> False", bot2.cancel_order(None) is False)

print()
if failures:
    print(f"RED — {len(failures)} failing: {failures}")
    sys.exit(1)
print("GREEN — resting stop pins all pass")
