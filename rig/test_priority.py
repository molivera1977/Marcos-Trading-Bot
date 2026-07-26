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

# ── functional: monkeypatch sheet lookup + scanner Move% map, sort with the REAL key ──
_orig = bot._kev_sheet_name
bot._kev_sheet_name = lambda t: t in ("KEVA", "KEVB")
bot._move_pct.clear()
bot._move_pct.update({"JUNK": 45.0, "KEVA": 8.0, "MID": 22.0, "KEVB": 60.0, "STALE": 90.0})
# STALE: scanner says 90 but internal day_gain says 5 — SCANNER COLUMN MUST WIN (Marcos: "the actual
# column labeled move %"); FALLBK: not on the scan at all -> internal day_gain fallback (30).
rows = [B("JUNK", 1.0), B("KEVA", 1.0), B("MID", 1.0), B("KEVB", 1.0),
        B("STALE", 5.0), B("FALLBK", 30.0), B("NOSTAMP", None)]
rows.sort(key=bot._entry_priority)
order = [r[0] for r in rows]
check("P1 Kev-sheet names outrank ALL non-Kev (even a +90% mover)", order[0:2] == ["KEVB", "KEVA"])
check("P2 within-Kev ordered by scanner Move% desc", order[0] == "KEVB")
check("P3 non-Kev ranked by the SCANNER Move% column, not internal day_gain", order[2] == "STALE" and order[3] == "JUNK")
check("P3b name absent from the scan falls back to day_gain (30 slots between JUNK 45 and MID 22)",
      order.index("FALLBK") == 4)
check("P4 no rank at all sinks to the bottom (never jumps the queue)", order[-1] == "NOSTAMP")
bot._kev_sheet_name = _orig; bot._move_pct.clear()

# ── wiring pins ──
i_sort  = SRC.find("breakouts.sort(key=_entry_priority)")
i_pmkt  = SRC.find('_in_premkt = ENTRY_OPEN_ET <= _hm_pm < "09:30"')
i_spawn = SRC.find("_trade_worker_safe, args=entry")
check("P5 sort exactly once, BEFORE the premarket gate (cap keeps the BEST 6) and BEFORE spawn",
      SRC.count("breakouts.sort(key=_entry_priority)") == 1 and 0 < i_sort < i_pmkt < i_spawn)
check("P6 priority order printed when >1 candidate (log-visible for Friday attribution)",
      "entry priority:" in SRC and "'*KEV'" in SRC)
check("P7 key defn: tier-0 kev-sheet + SCANNER Move% rank (day_gain fallback), -999 sentinel",
      "def _entry_priority(b):" in SRC and "0 if _kev_sheet_name(b[0]) else 1" in SRC
      and "_move_pct.get(b[0])" in SRC and "-999.0" in SRC)
check("P8 Move% map refreshed from the FULL scanned set each gapper scan",
      "_move_pct.update({c[\"symbol\"]" in SRC and "float_checked or []" in SRC)

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
