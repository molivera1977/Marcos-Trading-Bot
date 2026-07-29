"""Rig: CUSTODY REPRODUCTION (7/28 Fable order, ledger 8ac9954).

The 7/27 scandal: an ALIVE monitor (highest=$23.29 stamped by its own loop) watched VEEE trade
$5 above scale tier 1 ($18.16) for ~an hour and never executed the scale branch three lines
below the highest-update. 7/27 logs unrecoverable. This test drives the REAL monitor_trade on
today's code with a VEEE-shaped price path and asserts the ladder fires. GREEN here means
today's code scales correctly -> the 7/27 defect lived in 7/27's code or its price feed, and
Wednesday live (entry_ts + 10s capture now running) is the confirmation. RED here means the
custody bug is STILL LIVE — do not trade until fixed.
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

# ── the proven harness pattern from test_tonight_20260727 ──
class _Stream:
    def __init__(self, path):
        self.path, self.i = list(path), 0
    def loop_sleep(self):
        return 0
    def get_price(self, _t):
        px = self.path[min(self.i, len(self.path) - 1)]
        self.i += 1
        return px
    connected = True

_CLOCK = [0]

class _FrozenDT(bot.datetime):
    @classmethod
    def now(cls, tz=None):
        _CLOCK[0] += 1
        t = (bot.EASTERN.localize(bot.datetime(2026, 7, 27, 10, 30, 0))
             + bot.timedelta(seconds=30 * _CLOCK[0]))
        return t.astimezone(tz) if tz is not None else t.replace(tzinfo=None)

calls = {"close": [], "cancel": []}

def replay(path, entry, stop, entry_type, vride=False):
    saved = {"datetime": bot.datetime}
    bot.datetime = _FrozenDT
    _CLOCK[0] = 0
    calls["close"].clear(); calls["cancel"].clear()
    stubs = [("close_position", lambda t, q, *a, **k: calls["close"].append((t, q)) or True),
             ("cancel_order", lambda *a, **k: calls["cancel"].append(a) or True),
             ("place_stop_order", lambda *a, **k: None),
             ("_post_trade_state", lambda *a, **k: None),
             ("_save_open_trade", lambda *a, **k: None),
             ("send_partial_exit_alert", lambda *a, **k: None),
             ("get_intraday_bars", lambda *a, **k: [])]
    if not vride:
        stubs.append(("_vride_defer", lambda *a, **k: False))
    for n, v in stubs:
        saved[n] = getattr(bot, n, None); setattr(bot, n, v)
    bot._active_monitors.pop("T", None); bot._monitor_abort.discard("T")
    try:
        return bot.monitor_trade("T", 100, entry, entry * 2, stop, _Stream(path),
                                 None, vwap=0, entry_type=entry_type)
    finally:
        for n, v in saved.items():
            setattr(bot, n, v)

# ── T1: the VEEE shape — rise through tier1 ($18.16) and tier2 ($19.02), hover, fall to stop ──
E, S = 17.30, 16.4398
path = [17.30, 17.60, 18.20, 18.50, 19.10, 20.00, 21.50, 23.29] + [19.0] * 6 + [16.40] * 4
print("== T1 VEEE-shaped path on TODAY'S code (hidden_entry) ==")
r = replay(path, E, S, "hidden_entry")
pf = r.get("partial_fills") or []
check("ladder SCALED at least once (the 7/27 failure)", len(pf) >= 1, f"partial_fills={pf}, result={r.get('exit_reason')}")
check("close_position actually called for the scale", len(calls["close"]) >= 1)
check("monitor recorded the peak", (r.get("highest") or 0) >= 23.0, f"highest={r.get('highest')}")
check("runner exit is not a full-size stop", r.get("exit_reason") != "Stop loss 🛑" or len(pf) >= 1,
      f"reason={r.get('exit_reason')}")

# ── T2: same path as flat_top (rules out lane-specific tier wiring) ──
print("== T2 same path, flat_top lane ==")
r2 = replay(path, E, S, "flat_top")
check("flat_top scales on the same path", len(r2.get("partial_fills") or []) >= 1)

# ── T3: VELOCITY_RIDE live (real _vride_defer, bars=[] -> defer False by data-absence) ──
print("== T3 with the real _vride_defer in the loop (bars empty -> must not block) ==")
r3 = replay(path, E, S, "hidden_entry", vride=True)
check("scale still fires with real _vride_defer", len(r3.get("partial_fills") or []) >= 1)

# ── T4: WLDS shape — price NEVER above tier, straight to stop: full stop is CORRECT here ──
print("== T4 WLDS-shaped control (no tier touch -> full stop is the right answer) ==")
r4 = replay([4.06, 4.07, 3.95, 3.85, 3.80], 4.06, 3.819, "hidden_entry")
check("no phantom scale below tier", not (r4.get("partial_fills") or []))
check("stop exit recorded", "top" in str(r4.get("exit_reason", "")))

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    print("*** CUSTODY BUG LIVE ON TODAY'S CODE — do not trade until fixed ***")
    sys.exit(1)
print("GREEN — today's monitor scales the VEEE shape; the 7/27 failure is not reproducible on current code")
