"""CLEAN-CLOCK RE-RUN of the PRE gate-cost census (v1 was built on the broken 24h filter —
its numbers are VOID). Week 8/10-8/13, PRE window 07:00-09:25, first refusal/name/gate/day.
Model unchanged: $200 clip, -6% first-touch stop, 35% MFE capture."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from census_lib import rows_for, px_of
from collections import defaultdict

CLIP, STOP, CAPTURE = 200.0, -0.06, 0.35
total = {}
for day in ("2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"):
    rows = rows_for(day)
    path = defaultdict(list)
    for r in rows:
        p = px_of(r)
        if p and r.get("ticker") and r["_t24"]:
            path[r["ticker"]].append((r["_t24"], p))
    for tk in path: path[tk].sort()
    seen = set()
    for r in rows:
        st = r.get("status")
        if st not in ("stale_fire_suppressed", "reclaim_firevol_reject"): continue
        tm = r["_t24"]
        if not ("07:00:00" <= tm < "09:25:00"): continue
        tk = r.get("ticker"); e = px_of(r)
        if not tk or not e: continue
        k = (day, tk, st)
        if k in seen: continue
        seen.add(k)
        aft = [v for t, v in path[tk] if tm < t <= "09:25:00"]
        if not aft: continue
        hi = max(aft); mfe = (hi - e) / e
        stopped = False
        for v in aft:
            if v >= hi: break
            if (v - e) / e <= STOP: stopped = True; break
        pnl = CLIP*STOP if (stopped or mfe <= 0) else (-6.0 if mfe < 0.04 else CLIP*mfe*CAPTURE)
        a = total.setdefault(st, [0, 0.0]); a[0] += 1; a[1] += pnl
        if abs(pnl) > 8:
            print(f"  {day} {tk:5s} {st[:22]:22s} {tm[:5]} @{e:.3f} mfe {mfe*100:+.1f}% -> ${pnl:+.2f}")
print()
for st, (n, p) in total.items():
    print(f"{st}: {n} first-refusals, modeled ${p:+.2f}")
print(f"WEEK TOTAL: ${sum(p for _, p in total.values()):+.2f}")
