"""CAPITAL-PRIORITY rig (7/26, Marcos: "I want Kev's list and the ranked movers list in the
scanner to determine level of priority"). Functional sort tests on the real _entry_priority key
+ positional pins that the sort actually sits between the cache pre-warm and the worker spawn."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

B = lambda t, dg: (t, 1.0, 1.0, "flat_top", ({"day_gain": dg} if dg is not None else {}))

# ── functional: monkeypatch the sheet lookup, sort with the REAL key ──
_orig = bot._kev_sheet_name
bot._kev_sheet_name = lambda t: t in ("KEVA", "KEVB")
rows = [B("JUNK", 45.0), B("KEVA", 8.0), B("MID", 22.0), B("KEVB", 60.0), B("NOSTAMP", None)]
rows.sort(key=bot._entry_priority)
order = [r[0] for r in rows]
check("P1 Kev-sheet names outrank ALL non-Kev (even a +45% mover)", order[0:2] == ["KEVB", "KEVA"])
check("P2 within-Kev ordered by day_gain desc", order[0] == "KEVB")
check("P3 non-Kev ranked by day_gain desc (scanner movers rank)", order[2:4] == ["JUNK", "MID"])
check("P4 unstamped day_gain sinks to the bottom (never jumps the queue)", order[-1] == "NOSTAMP")
bot._kev_sheet_name = _orig

# ── wiring pins ──
i_warm  = SRC.find("pre-warm the chart-gate levels cache ONCE")
i_sort  = SRC.find("breakouts.sort(key=_entry_priority)")
i_spawn = SRC.find("_trade_worker_safe, args=entry")
check("P5 sort exists exactly once, AFTER the cache pre-warm, BEFORE worker spawn",
      SRC.count("breakouts.sort(key=_entry_priority)") == 1 and 0 < i_warm < i_sort < i_spawn)
check("P6 priority order printed when >1 candidate (log-visible for Friday attribution)",
      "entry priority:" in SRC and "'*KEV'" in SRC)
check("P7 key defn: tier-0 kev-sheet + day_gain rank, unstamped -999 sentinel",
      "def _entry_priority(b):" in SRC and "0 if _kev_sheet_name(b[0]) else 1" in SRC
      and "-999.0" in SRC)

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
