"""Rig: WIDTH-PROPORTIONAL RISK (7/29, Marcos's design, Fable-ruled, shipped same night).
risk = $30 × min(1, stop_width / 6%). Pins: the exact table quoted to Marcos, the ceiling
invariant (never MORE than $30), both sizing sites wired, kill switch restores flat-$30
(mutant: run with RISK_PROP=0 → the table pins go RED)."""
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

R = bot.RISK_PER_TRADE
print("== the quoted table (entry $10) ==")
for w, want in [(0.08, 30.0), (0.06, 30.0), (0.045, 22.5), (0.03, 15.0), (0.015, 7.5)]:
    got = bot._scaled_risk(10.0, 10.0 * (1 - w))
    check(f"width {w*100:.1f}% -> ${want:.2f}", abs(got - want) < 0.01, f"got {got:.2f}")
# the real cases from 7/29
check("SKYQ 0.76% -> ~$3.80", abs(bot._scaled_risk(4.34, 4.34 * (1 - 0.0076)) - 3.80) < 0.02)
check("PYPD 1.41% -> ~$7.05", abs(bot._scaled_risk(4.26, 4.20) - 30 * ((4.26 - 4.20) / 4.26) / 0.06) < 0.02)

print("== invariants ==")
check("CEILING: never exceeds $30 (10x-wide stop)", bot._scaled_risk(10.0, 5.0) <= R + 1e-9)
check("invalid ticket returns ceiling (P0-A owns refusal)", bot._scaled_risk(10.0, 11.0) == R)
check("constant-notional property: shares*entry ~= $500 below ref",
      abs(int(bot._scaled_risk(10.0, 9.9) / 0.10) * 10.0 - 500.0) <= 10.0)

print("== wiring ==")
check("pre-fill sizing uses _scaled_risk", "_risk_i = _scaled_risk(entry_price, stop_loss)" in src)
check("post-fill re-derivation uses _scaled_risk (no re-inflation)",
      "int(_scaled_risk(entry_price, stop_loss) / (entry_price - stop_loss))" in src)
check("no remaining direct RISK_PER_TRADE sizing", "int(RISK_PER_TRADE / (entry_price - stop_loss))" not in src)
check("scaled entries log a risk_scaled row", '"risk_scaled"' in src)

print("== kill switch ==")
check("RISK_PROP defaults ON", bot.RISK_PROP is True)
check("REF = 6%", bot.RISK_PROP_REF == 0.06)
_saved = bot.RISK_PROP
bot.RISK_PROP = False
check("RISK_PROP=0 -> flat $30 at any width", bot._scaled_risk(10.0, 9.9) == R)
bot.RISK_PROP = _saved

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — risk scales to the wiggle room; ceiling holds; both sizing sites wired; kill switch exact")
