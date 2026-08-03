"""Reader freshness + scale sanity (8/3, task #25) — pins the FUSE and YYAI failure classes.

Fixtures are the ACTUAL failed reads: FUSE v4 (targets 1.08/1.15 vs live 1.46) and YYAI
(targets 0.85/1.00, break vs live 0.178 after corrupt $11 history). Plus regression pins:
sane reads still pass, and last_px=0 keeps the old fail-open behavior.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "reader", pathlib.Path(__file__).resolve().parent.parent / "newcomer_vision_reader.py")
R = importlib.util.module_from_spec(spec)
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "rig-dummy")
spec.loader.exec_module(R)

fails = []
def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")
    if not cond: fails.append(name)

def V(rd, px): return R.validate_read(rd, px)

BASE = {"verdict": "MARGINAL", "confidence": "LOW"}

# 1. FUSE v4 class: top target below live tape -> REJECT
ok, why = V({**BASE, "break_level": 1.03, "targets": [1.08, 1.15], "stop_level": 0.97}, 1.46)
check("FUSE v4 (targets below live) rejected", not ok and "exhausted" in why, why)

# 2. YYAI class: levels 5x+ away from live price -> REJECT
ok, why = V({**BASE, "break_level": 0.80, "targets": [0.85, 1.00], "stop_level": 0.70}, 0.178)
check("YYAI (scale insane vs live) rejected", not ok, why)

# 3. sane fresh map passes (live below targets, levels in scale)
ok, why = V({**BASE, "break_level": 1.35, "targets": [1.55, 1.80], "stop_level": 1.28}, 1.42)
check("fresh sane map passes", ok, why)

# 4. fail-open preserved: no trusted price (0/None) -> old behavior (structure-only)
ok, why = V({**BASE, "break_level": 1.03, "targets": [1.08, 1.15], "stop_level": 0.97}, 0)
check("no live px -> old behavior (passes structure)", ok, why)
ok, why = V({**BASE, "break_level": 1.03, "targets": [1.08, 1.15], "stop_level": 0.97}, None)
check("None live px -> old behavior", ok, why)

# 5. regression: structural rejects still fire (missing break)
ok, why = V({**BASE, "targets": [1.5]}, 1.0)
check("missing break still rejected", not ok, why)

# 6. target barely above live (within 1%) is still exhausted -> REJECT
ok, why = V({**BASE, "break_level": 1.35, "targets": [1.465], "stop_level": 1.28}, 1.46)
check("top target within 1% of live rejected", not ok, why)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}"); sys.exit(1)
print("GREEN — reader freshness pins all pass")

# ── 8. the FUSE eyes: 10s-store rebuild kicks in when min1 is stale ─────────────
import json as _j
_calls = {}
def _fake_get(path, timeout=20, tries=3):
    if "~ALP10S" in path:
        return {"bars": [{"time": f"2026-08-03T{hh}:{mm:02d}:{ss:02d}", "open": 1.4, "high": 1.47,
                          "low": 1.39, "close": 1.46, "volume": 500}
                         for hh in ("14",) for mm in range(30, 45) for ss in (5, 25, 45)]}
    return {}
R._get_retry = _fake_get
R._min1 = lambda tk: [{"time": "2026-08-03T10:35:00", "session": "RTH", "open": 1.1, "high": 1.16,
                       "low": 1.08, "close": 1.15, "volume": 100}] * 12   # stale tail at 1.15
R.DAY = "2026-08-03"
png, meta = R.render_intraday_png("FUSE")
check("stale min1 -> rebuilt from 10s store", png is not None and abs(float(meta.get("last", 0)) - 1.46) < 1e-6,
      f"meta last={meta.get('last')}")

b10 = R._min1_from_10s("FUSE")
check("10s aggregation: 3x10s -> 1min bars", len(b10) == 15 and b10[0]["volume"] == 1500,
      f"n={len(b10)}")

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}"); sys.exit(1)
print("GREEN — 10s-rebuild pins pass")
