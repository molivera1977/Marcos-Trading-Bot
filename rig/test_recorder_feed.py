"""Recorder feed-integrity tests — F1 (volume conservation) + F3 (slot priority).

F1's invariant is a CONSERVATION LAW: every share the counter reports must land in exactly one
bar — across bucket boundaries, across blackouts, never negative on counter resets. That's what
the 7/20 forensic measured being violated (10-25% structural leak + all blackout volume discarded).
Run:  python3 rig/test_recorder_feed.py
"""
import sys, pathlib, importlib.util

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("recorder", HERE.parent / "recorder.py")
rec = importlib.util.module_from_spec(spec)
sys.modules["recorder"] = rec
spec.loader.exec_module(rec)

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {detail}" if detail and not cond else ""))

def reset():
    rec._bars[10].clear(); rec._bars[60].clear(); rec._vwap.clear(); rec._prev_cv.clear()

def total_vol(sym, span=10):
    return sum(max((b["v1"] or 0) - (b["v0"] or 0), 0) for b in rec._bars[span].get(sym, {}).values())

print("F1: volume conservation")
# T1: bucket-boundary straddle — the 7/20 structural leak class
reset()
rec.ingest("T1", 1.00, 100, 1000)    # bucket 1000
rec.ingest("T1", 1.01, 150, 1009)    # same bucket
rec.ingest("T1", 1.02, 180, 1011)    # NEW bucket: old code lost the 150→180 delta
check("T1 straddling delta lands in the new bucket (Σ=80 == counter delta)",
      total_vol("T1") == 80, f"got {total_vol('T1')}")

# T2: blackout — whole gap's volume books into the resume bucket
reset()
rec.ingest("T2", 2.00, 1000, 2000)
rec.ingest("T2", 2.05, 1500, 2009)
rec.ingest("T2", 2.20, 4000, 2130)   # 2-min silent gap; counter kept counting
check("T2 blackout volume conserved (Σ=3000 == counter delta)",
      total_vol("T2") == 3000, f"got {total_vol('T2')}")

# T3: counter reset (PRE→RTH) — re-baseline, never negative
reset()
rec.ingest("T3", 3.00, 500, 3000)
rec.ingest("T3", 3.01, 50, 3010)     # counter dropped: new session regime
check("T3 counter reset → no negative volume, clean re-baseline",
      total_vol("T3") == 0 and rec._prev_cv["T3"] == 50, f"vol={total_vol('T3')}")

# T4: VWAP accumulator conserves across the same gap (reconnect no longer discards)
reset()
rec.ingest("T4", 1.00, 100, 4000)
rec.ingest("T4", 1.10, 600, 4009)
rec.ingest("T4", 1.20, 1100, 4130)   # gap; old reconnect-null would have dropped these 500
v = rec._vwap["T4"]
check("T4 VWAP den == full counter delta (1000)", v["den"] == 1000, f"den={v['den']}")

# T5: day reset clears the carried counter
reset()
rec.ingest("T5", 1.0, 999, 5000)
rec._reset_day()
check("T5 _reset_day clears _prev_cv (no cross-day leak)", "T5" not in rec._prev_cv)

print("F3: subscription priority + reserve")
# stub stream that records subscribe order and never errors
class _Stub:
    def __init__(self): self.calls = []
    def subscribe(self, chunk, cat, kinds): self.calls.append(list(chunk))
rec._stream = _Stub(); rec._subscribed.clear(); rec._sub_cap_hit = False

_sm_src = open(HERE.parent / "recorder.py").read().split("def scan_movers")[1].split("\ndef ")[0]
check("T6 scan_movers returns a LIST (ranked), not a set",
      "syms, seen = [], set()" in _sm_src and "syms.append(" in _sm_src
      and "syms.add(" not in _sm_src)

# T7: subscribe preserves caller's priority order under the cap
import datetime
rec._subscribed.clear(); rec._stream.calls.clear()
names = [f"A{i}" for i in range(50)]
rec.subscribe(names)
flat = [s for c in rec._stream.calls for s in c]
check("T7 priority order preserved; cap respected",
      flat == names[:len(flat)] and len(rec._subscribed) <= max(rec.RTH_SUB_CAP, rec.MAX_SUBSCRIBE),
      f"got {len(flat)} first={flat[:3]}")

# T8: pins — reserve + cooldown exist with sane values
check("T8 pins: RESERVE_LIVE=15, cooldown state present",
      rec.RESERVE_LIVE == 15 and isinstance(rec._last_hot_cycle, list))

# T9: the lockout-breaker path exists in the session loop (source-level pin)
src = open(HERE.parent / "recorder.py").read()
check("T9 hot-mover lockout breaker wired in rescan (cooldown 600s)",
      "HOT MOVER LOCKED OUT" in src and "hot_mover_flush" in src and ">= 600" in src)

# T10: F3-acceptance coverage canary wired (source pins)
src2 = open(HERE.parent / "recorder.py").read()
check("T10 F3-coverage canary: wired into persist + asks top-movers-vs-subscribed",
      "_coverage_report()" in src2 and "F3-coverage:" in src2 and "scan_movers()[:10]" in src2)

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
