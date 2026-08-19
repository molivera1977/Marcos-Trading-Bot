#!/usr/bin/env python3
"""
RIG GATE 19 — DIST-PRIMARY REREADS (8/19: "my api bill is jumping" -> "build now. save push for later.")

WHAT THIS PINS
  The paid vision reread out of `_effective_map` queues ONLY when the map is measurably WRONG
  (dist > FRESH_MAX_DIST) — never because it is merely old. Measured basis (6 archived sessions,
  524 points): 53% of freshness breaches fired on maps still within 3% of live structure; IPST
  queued 47 reads against a map that was never wrong. Age-stale-but-accurate maps keep the tape
  auto-map overlay and keep logging breach rows (trigger=age) — they just stop buying reads.

METHOD — the REAL functions, judged by observable effect, not by reading source:
  drives `_effective_map` through the live module with a monkeypatched `_freshest_rec` /
  `_log_decision` / reader-marker POST capture, then asserts on (a) whether a reread marker was
  queued, (b) the breach row's `trigger` field. Exit code is the verdict (sweeps judge by exit
  code — feedback_rig_tests_spec_not_impl).

  F1  age-stale (150m) + dist 0%      -> breach row trigger=age,  NO read queued   [the IPST class]
  F2  fresh age + dist 40%            -> breach row trigger=dist, read QUEUED      [the YJ class]
  F3  age-stale + dist 40%            -> breach row trigger=both, read QUEUED
  F4  kill switch REREAD_DIST_ONLY=0  -> F1's shape queues a read again (old behavior restorable)
  F5  fresh age + dist under ceiling  -> NO breach row at all (contract untouched for fresh maps)
"""
import os
import sys
import pathlib
from datetime import datetime, timedelta

os.environ.setdefault("DRY_RUN", "true")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()

FAIL = []


def check(name, ok):
    print(("  ok  " if ok else "  XX  ") + name)
    if not ok:
        FAIL.append(name)


def run_case(age_min, brk, live_px, dist_only="1", tkr="TSTX"):
    """Drive the real _effective_map once; return (breach_rows, reads_queued)."""
    now_iso = (datetime.now(bot.EASTERN) - timedelta(minutes=age_min)).isoformat()
    rec = {"break": brk, "confirm": brk, "targets": [brk * 2], "_ts": now_iso, "read_at": now_iso}
    rows, reads = [], []
    _orig = (bot._freshest_rec, bot._log_decision, bot._reread_on_reject,
             bot._is_leader, bot._auto_map)
    os.environ["REREAD_DIST_ONLY"] = dist_only
    try:
        bot._freshest_rec = lambda t: dict(rec)
        bot._log_decision = lambda t, status, **kw: rows.append((status, kw))
        bot._reread_on_reject = lambda t, gate, **kw: reads.append((t, gate))
        bot._is_leader = lambda t: True            # contract is crowns-only
        bot._auto_map = lambda t, px: {"break": round(px * 0.99, 4), "confirm": None,
                                       "targets": [], "auto_map": True,
                                       "_ts": datetime.now(bot.EASTERN).isoformat()}
        bot._effmap_cache.pop(tkr, None)           # defeat the 20s memo
        bot._fresh_breach_t.pop(tkr, None)         # defeat the 120s row cadence
        bot._effective_map(tkr, live_px)
    finally:
        (bot._freshest_rec, bot._log_decision, bot._reread_on_reject,
         bot._is_leader, bot._auto_map) = _orig
        os.environ["REREAD_DIST_ONLY"] = "1"
        bot._effmap_cache.pop(tkr, None)
        bot._fresh_breach_t.pop(tkr, None)
    breaches = [(s, kw) for s, kw in rows if s == "freshness_breach"]
    return breaches, reads


print("RIG GATE 19 — dist-primary rereads (the paid read queues on WRONG, never on OLD)")
print("=" * 84)

# F1 — the IPST class: 150m old, price sitting AT the break (dist 0). Breach logs, no read.
br, rd = run_case(age_min=150, brk=10.0, live_px=10.0)
check("F1 age-stale + accurate: breach row logged", len(br) == 1)
check("F1 age-stale + accurate: trigger=age", bool(br) and br[0][1].get("trigger") == "age")
check("F1 age-stale + accurate: NO read queued (the 47-read IPST class is dead)", rd == [])

# F2 — the YJ class: map minutes old but price ran 40% past the break. Read queues.
br, rd = run_case(age_min=2, brk=10.0, live_px=14.0)
check("F2 fresh-but-wrong: breach row trigger=dist", bool(br) and br[0][1].get("trigger") == "dist")
check("F2 fresh-but-wrong: read QUEUED", len(rd) == 1)

# F3 — both arms tripped.
br, rd = run_case(age_min=150, brk=10.0, live_px=14.0)
check("F3 old AND wrong: trigger=both", bool(br) and br[0][1].get("trigger") == "both")
check("F3 old AND wrong: read QUEUED", len(rd) == 1)

# F4 — kill switch restores read-on-every-breach.
br, rd = run_case(age_min=150, brk=10.0, live_px=10.0, dist_only="0")
check("F4 REREAD_DIST_ONLY=0: age-only breach queues a read again (rollback intact)", len(rd) == 1)

# F5 — fresh + accurate: the contract does not fire at all.
br, rd = run_case(age_min=2, brk=10.0, live_px=10.0)
check("F5 fresh + accurate: no breach row, no read", br == [] and rd == [])

print("=" * 84)
print(("GREEN — %d checks" % (8 + 1)) if not FAIL else ("RED — failing: %s" % FAIL))
sys.exit(1 if FAIL else 0)
