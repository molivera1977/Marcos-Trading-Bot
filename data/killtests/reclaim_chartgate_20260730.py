"""RECLAIM THROUGH THE REAL CHART GATE (7/30, Marcos: "reclaim uses the chart or not?" -> "run it").

WHAT THIS TESTS: reclaim currently BYPASSES the chart gate. _chart_break_gate's first branch
returns ("allow","live_structure") for hidden_entry / vwap_reclaim / zone_flip before any check
runs — Marcos's 7/24 call, because these lanes trade live 10s structure and unmapped intraday
names were dying on no_marked_level. The marked level rides along as evidence, never a veto.
Question: if the bypass were removed, would the REAL gate separate the 419 dead-on-arrival fires
from the 169 movers — the discriminator that 13 tape features and 6 grammar constants missed?

METHOD: the REAL _chart_break_gate is called — NOT a hand-written copy. My hand-written version
was WRONG on 7/29 (passed 12 fires where the real gate passed 5), which voided that study. Two
in-memory substitutions only (disk file untouched):
  1. the bypass tuple drops "vwap_reclaim" so reclaim falls through to the legacy gate path
  2. _fetch_kev_levels is redirected to the ARCHIVED levels for the replayed date
     (/api/kev_watchlist?date=...) instead of today's live sheet

LEVEL COVERAGE IS THE BINDING CONSTRAINT: archived levels are empty for 07-13 and near-empty for
07-17. Days before 07-22 are EXCLUDED — a gate cannot be graded on days when the map is missing.
That shrinks the sample and the split; both are reported honestly rather than papered over.

PRE-REGISTERED, written before any number was seen:
  1. Three outcomes are reported SEPARATELY and never merged: ALLOW (gate passed), BLOCK (gate
     refused on a real read), SKIP (no marked level / read exhausted — the gate had nothing to
     judge). Counting SKIP as a "block" is the error that inflates every gate study.
  2. The gate is a DISCRIMINATOR only if the BLOCK bucket is materially worse per fire than the
     ALLOW bucket. Blocking money-losers is the whole claim.
  3. OOS: TRAIN 07-22..07-24, TEST 07-27..07-30. TEST read once, after.
  4. TAIL: report >=2R-MFE fires kept in ALLOW. A gate that crosses zero by deleting the tail is
     rejected (the trap that killed the absolute liquidity floor earlier today).
  5. FAILURE CONDITION: if ALLOW is not better than the ungated population on TEST, the chart
     gate does not save reclaim either, and that is reported as the finding.
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

PATCH = ('if entry_type in ("hidden_entry", "vwap_reclaim", "zone_flip"):',
         'if entry_type in ("hidden_entry", "zone_flip"):')

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    assert src.count(PATCH[0]) == 1, f"bypass tuple not unique ({src.count(PATCH[0])})"
    src = "from __future__ import annotations\n" + src.replace(*PATCH)
    mod = types.ModuleType("cg_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["cg_patched_bot"] = mod
    exec(compile(src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

print("IN-MEMORY PATCH (disk file untouched):")
print(f"  {PATCH[0]}\n  -> {PATCH[1]}\n")
bot = load_patched()
bot._bucket_fresh = lambda k: True
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9

# archived levels per replayed date, in place of today's live sheet
_lv_cache = {}
def levels_for(d):
    if d not in _lv_cache:
        try:
            _lv_cache[d] = (json.load(urllib.request.urlopen(
                f"{harness.U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {})
        except Exception:
            _lv_cache[d] = {}
    return _lv_cache[d]

TRAIN = ("2026-07-22", "2026-07-23", "2026-07-24")
TEST  = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")
DAYS  = TRAIN + TEST
print("level coverage (archived kev_watchlist):")
for d in DAYS:
    lv = levels_for(d)
    print(f"  {d}: {len(lv):>3} names, {sum(1 for v in lv.values() if (v or {}).get('break')):>3} with a break")
print()

universe = collections.defaultdict(set)
for d in DAYS:
    try:
        rows = (json.load(urllib.request.urlopen(
            f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or [])
    except Exception as e:
        print(f"  !! {d}: archive fetch failed ({e})"); continue
    for r in rows:
        if r.get("ticker"):
            universe[d].add(r["ticker"])

# ── PREFETCH WITH RETRY + COVERAGE ASSERTION ─────────────────────────────────────────────────
# Run 1 was VOID: bar fetches silently returned [] on timeout partway through, leaving TEST with
# 29 fires against ~520 in every other study today. harness.bars() swallows the exception and
# caches the empty result, so a throttled fetch is indistinguishable from a name with no tape.
# Fix: fetch every (day, ticker) up front with retries, and REFUSE TO PROCEED if a day's coverage
# looks like a fetch failure rather than a real absence.
import time as _time
def prefetch():
    got = collections.defaultdict(int)
    for d in DAYS:
        for tk in sorted(universe[d]):
            b = None
            for attempt in range(4):
                b = harness.bars(tk, d)
                if b:
                    break
                harness._bars_cache.pop((tk, d), None)   # drop the poisoned empty cache entry
                _time.sleep(0.4 * (attempt + 1))
            if b:
                got[d] += 1
        print(f"  {d}: {got[d]}/{len(universe[d])} tickers with tape "
              f"({100*got[d]/max(len(universe[d]),1):.0f}%)")
    bad = [d for d in DAYS if got[d] < 0.5 * len(universe[d])]
    if bad:
        raise SystemExit(f"ABORT — bar coverage collapsed on {bad}; this is the run-1 failure mode. "
                         f"Re-run; do NOT report partial results.")
    return got

print("prefetching bars (retry on empty, coverage asserted):")
prefetch()
print()

def vwap_series(b):
    out, pv, vv = [], 0.0, 0.0
    for k, o, h, l, c, v, hm in b:
        pv += ((h + l + c) / 3.0) * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out

fires = []
for d in DAYS:
    bot._fetch_kev_levels = lambda _d=d: levels_for(_d)
    for tk in sorted(universe[d]):
        b = harness.bars(tk, d)
        if not b:
            continue
        bot._reclaim_st.clear()
        vw = vwap_series(b)
        for i, bar in enumerate(b):
            f = bot.kev_reclaim_step(tk, [bar[:6]], vw[i])
            if not f:
                continue
            e, s = f["px"], f["stop"]
            if not (e and s and e > s):
                continue
            rep = harness.replay(tk, d, e, s, i0=i)
            if not rep or not rep.get("shares"):
                continue
            verdict, reason, level, src = bot._chart_break_gate(tk, e, "vwap_reclaim")
            peak = e
            for x in b[i:]:
                peak = max(peak, x[2])
                if x[3] <= s:
                    break
            fires.append({"d": d, "tk": tk, "hm": bar[6], "pnl": round(rep["pnl"], 2),
                          "mfe": (peak - e) / (e - s), "verdict": verdict, "reason": reason,
                          "level": level})

def agg(rs):
    n = len(rs)
    if not n:
        return 0, 0.0, 0.0, 0.0, 0
    p = sum(r["pnl"] for r in rs)
    return n, p, p / n, 100 * sum(1 for r in rs if r["pnl"] > 0) / n, sum(1 for r in rs if r["mfe"] >= 2)

print("=" * 112)
print("GATE VERDICT BREAKDOWN — ALLOW / BLOCK / SKIP reported separately (gate 1)")
print("=" * 112)
print(f"{'verdict':<10}{'reason':<24}{'n':>6}{'win%':>8}{'total $':>12}{'mean $':>10}{'tail>=2R':>10}")
by = collections.defaultdict(list)
for f in fires:
    by[(f["verdict"], f["reason"])].append(f)
for (v, r), rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    n, t, m, w, tail = agg(rs)
    print(f"{v:<10}{r:<24}{n:>6}{w:>7.1f}%{t:>12.2f}{m:>10.2f}{tail:>10}")

print("\n" + "=" * 112)
print("GATE 2 — is BLOCK worse than ALLOW?  (the entire claim of a gate)")
print("=" * 112)
for lab, sel in (("ALLOW (gate passed)", lambda f: f["verdict"] == "allow"),
                 ("BLOCK (gate refused)", lambda f: f["verdict"] == "block"),
                 ("SKIP  (nothing to judge)", lambda f: f["verdict"] == "skip"),
                 ("ALL FIRES (ungated)", lambda f: True)):
    n, t, m, w, tail = agg([f for f in fires if sel(f)])
    print(f"  {lab:<26} n={n:>4}  win={w:>5.1f}%  total=${t:>9.2f}  mean=${m:>7.2f}  tail={tail:>3}")

print("\n" + "=" * 112)
print("GATE 3/5 — OUT OF SAMPLE (TEST read once)")
print("=" * 112)
for split, days in (("TRAIN 07-22..24", TRAIN), ("TEST  07-27..30", TEST)):
    sub = [f for f in fires if f["d"] in days]
    nA, tA, mA, wA, tailA = agg([f for f in sub if f["verdict"] == "allow"])
    nU, tU, mU, wU, tailU = agg(sub)
    verdict = "IMPROVES" if (mA > mU and nA >= 30) else "does NOT improve"
    print(f"  {split}:  ALLOW n={nA:>4} mean=${mA:>7.2f}  vs  UNGATED n={nU:>4} mean=${mU:>7.2f}"
          f"   tail kept {(100*tailA/tailU if tailU else 0):>5.1f}%   -> {verdict}")

te = [f for f in fires if f["d"] in TEST]
nA, tA, mA, wA, tailA = agg([f for f in te if f["verdict"] == "allow"])
nU, tU, mU, wU, tailU = agg(te)
print("\n" + "=" * 112)
print("VERDICT")
print("=" * 112)
if nA < 30 or mA <= mU:
    print("  FAILURE CONDITION MET (gate 5): the chart gate does not improve reclaim out of sample.")
    print("  Reported as such — the bypass is not what is costing this lane.")
else:
    print(f"  ALLOW beats ungated on TEST: ${mA:.2f} vs ${mU:.2f} on n={nA}, tail kept "
          f"{100*tailA/tailU if tailU else 0:.1f}% -> candidate, pending Fable.")

json.dump(fires, open(pathlib.Path(__file__).with_name("reclaim_chartgate_20260730.json"), "w"), indent=1)
print("\nrows saved -> reclaim_chartgate_20260730.json")
