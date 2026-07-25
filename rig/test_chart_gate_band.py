"""#109 CHART-GATE BAND rig (Marcos 7/24: "let's definitely add this").
Kill-test basis: band_killtest.py over ALL 70 no_break_below_level blocks 7/22-7/24 replayed
with the capped-loss exit — 0-2% below level = +0.66R/trade (n=16) vs 2-5% = -0.31,
>10% = -0.69. Gate stays; a 2% pullback band under the level opens (Kev's own entry class:
EHGO 3.81/3.95 under the highs). CHART_GATE_BAND=0 = kill switch, restores hard gate.
FUNCTIONAL tests on the real _chart_break_gate with a monkeypatched sheet."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# monkeypatch the sheet: SNTG break=2.00; VETO name; and one with no level
bot._fetch_kev_levels = lambda: {
    "SNTG": {"break": "2.00", "targets": []},
    "VETO": {"break": "3.00", "veto": True},
}
gate = bot._chart_break_gate

# ── band arithmetic (default CHART_GATE_BAND=0.02, brk=2.00 → floor 1.96) ──
check("B1 above level allows (broke_level)", gate("SNTG", 2.01, "flat_top")[:2] == ("allow", "broke_level"))
check("B2 exactly at level allows",          gate("SNTG", 2.00, "flat_top")[:2] == ("allow", "broke_level"))
check("B3 1% below → band allow",            gate("SNTG", 1.98, "flat_top")[:2] == ("allow", "band_below_level"))
check("B4 exactly band floor (2% = 1.96) allows", gate("SNTG", 1.96, "flat_top")[:2] == ("allow", "band_below_level"))
check("B5 just under floor (1.9599) BLOCKS", gate("SNTG", 1.9599, "flat_top")[:2] == ("block", "no_break_below_level"))
check("B6 deep below (>10%) BLOCKS",         gate("SNTG", 1.70, "flat_top")[:2] == ("block", "no_break_below_level"))

# ── untouched behavior ──
check("U1 no marked level still skips",      gate("NOPE", 1.00, "flat_top")[:2] == ("skip", "no_marked_level"))
check("U2 veto still skips",                 gate("VETO", 3.50, "flat_top")[:2] == ("skip", "veto_do_not_trade"))

# ── kill switch: CHART_GATE_BAND=0 restores the hard gate ──
_saved = bot.CHART_GATE_BAND
bot.CHART_GATE_BAND = 0.0
check("K1 band=0 → 1% below BLOCKS (old behavior)", gate("SNTG", 1.98, "flat_top")[:2] == ("block", "no_break_below_level"))
check("K2 band=0 → above level still allows",       gate("SNTG", 2.01, "flat_top")[:2] == ("allow", "broke_level"))
bot.CHART_GATE_BAND = _saved

# ── enforcement contract: band verdict is 'allow' so ENFORCE mode passes it (line ~7090 checks !='allow') ──
check("E1 band verdict IS 'allow' (passes ENFORCE gate)", gate("SNTG", 1.97, "flat_top")[0] == "allow")
check("E2 default band value is 0.02", abs(_saved - 0.02) < 1e-9)

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
