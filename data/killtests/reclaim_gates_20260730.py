"""RECLAIM FOUR-GATE SWEEP (7/30, Marcos: "run it").

The four constants that define the reclaim lane and have NEVER been swept:
    RC_VOL  2.0x    volume multiple required on the VWAP cross          (gate 1)
    RC_EXT  1.01    extension above VWAP required before a pullback counts (gate 2)
    RC_DIP  1.005   how close to VWAP the pullback must come to arm/wick  (gate 2/3)
    RC_INV  0.99    invalidation — close this far under VWAP resets       (gate 2/3)

ONE-AT-A-TIME: each constant sweeps while the other three sit at their shipped values. A full
4-D grid would be ~600 runs and would fit noise at this n; a 1-D sweep answers "is this knob at
a bad value" without pretending we can co-optimise 784 fires.

METHOD: the shipped detector runs on archived 10s bars. Disk file UNTOUCHED. Five in-memory
substitutions turn the literals into module globals; each is asserted unique and printed. The
shipped values reproduce today's behaviour exactly (fidelity control = the live column).

PRE-REGISTERED, written before any number was seen:
  1. FIDELITY: the shipped-value cell must reproduce n=784 / -$4849.30 from the anatomy run,
     or the patch changed behaviour and the whole file is VOID.
  2. OOS: TRAIN 07-13..07-24, TEST 07-27..07-30. Ranked on TRAIN, TEST read once, after.
  3. PLATEAU: a winning value needs a non-losing neighbour. Lone spikes are overfit.
  4. MIN n: TRAIN n < 15 is not eligible.
  5. FAILURE CONDITION: if no value of any constant is positive in TRAIN at n >= 15, the gates
     are not where reclaim's money is going — consistent with the slippage finding (median
     0.67R of every stop eaten by the calibrated fill) — and the lane's problem is the TICKET,
     not the selection. That result gets reported as such, not buried.

Downstream gates are NOT applied (detector population): read RELATIVE differences.
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

PATCHES = [
    # gate 1 — volume multiple on the cross (anchor is reclaim-specific; zone_flip has its own 2.0)
    ('prev_c is not None and prev_c <= vwap and c > vwap and avgv > 0 and v >= 2.0 * avgv',
     'prev_c is not None and prev_c <= vwap and c > vwap and avgv > 0 and v >= RC_VOL * avgv', 1),
    # gate 2 — extension required
    ('if c >= vwap * 1.01: st["ext"] = True',
     'if c >= vwap * RC_EXT: st["ext"] = True', 1),
    # gate 2 — pullback depth that arms the retest
    ('if st["ext"] and l <= vwap * 1.005:',
     'if st["ext"] and l <= vwap * RC_DIP:', 1),
    # gate 3 — the wick must dip into the same VWAP zone
    ('if rng > 0 and l <= vwap * 1.005 and (c - l) / rng >= 0.5:',
     'if rng > 0 and l <= vwap * RC_DIP and (c - l) / rng >= 0.5:', 1),
    # invalidation, both sites (extend-phase and retest-phase)
    ('elif c < vwap * 0.99:', 'elif c < vwap * RC_INV:', 1),
    ('if c < vwap * 0.99:', 'if c < vwap * RC_INV:', 1),
]
PRELUDE = "from __future__ import annotations\nRC_VOL = 2.0\nRC_EXT = 1.01\nRC_DIP = 1.005\nRC_INV = 0.99\n"

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    for old, new, want in PATCHES:
        got = src.count(old)
        assert got == want, f"expected {want} site(s) for {old[:55]!r}, found {got}"
        src = src.replace(old, new)
        print(f"  parameterised x{want}: {old[:70]!r}")
    mod = types.ModuleType("rg_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["rg_patched_bot"] = mod
    exec(compile(PRELUDE + src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

print("PARAMETERISING IN MEMORY (shipped file on disk untouched):")
bot = load_patched()
bot._bucket_fresh = lambda k: True
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
print(f"disk file untouched: {rig_loader.BOT_PATH}\n")

TRAIN = ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
         "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24")
TEST  = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")
DAYS  = TRAIN + TEST

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

_bar_cache = {}
def day_bars(d):
    if d not in _bar_cache:
        _bar_cache[d] = [(tk, harness.bars(tk, d)) for tk in sorted(universe[d])]
        _bar_cache[d] = [(tk, b) for tk, b in _bar_cache[d] if b]
    return _bar_cache[d]

def _vwap_series(b):
    out, pv, vv = [], 0.0, 0.0
    for k, o, h, l, c, v, hm in b:
        pv += ((h + l + c) / 3.0) * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out

_vw_cache = {}
def vwaps(d, tk, b):
    key = (d, tk)
    if key not in _vw_cache:
        _vw_cache[key] = _vwap_series(b)
    return _vw_cache[key]

def run():
    fires = []
    for d in DAYS:
        for tk, b in day_bars(d):
            bot._reclaim_st.clear()
            vw = vwaps(d, tk, b)
            for i, bar in enumerate(b):
                f = bot.kev_reclaim_step(tk, [bar[:6]], vw[i])
                if not f:
                    continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s):
                    continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if rep and rep.get("shares"):
                    fires.append({"d": d, "pnl": round(rep["pnl"], 2), "w": round((e - s) / e * 100, 2)})
    return fires

def agg(rows):
    n = len(rows); p = sum(r["pnl"] for r in rows)
    return n, p, (p / n if n else 0.0), (100 * sum(1 for r in rows if r["pnl"] > 0) / n if n else 0.0), \
           (sum(r["w"] for r in rows) / n if n else 0.0)

SWEEPS = [
    ("RC_VOL", "volume multiple on the cross", 2.0, (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)),
    ("RC_EXT", "extension above VWAP required", 1.01, (1.000, 1.005, 1.01, 1.02, 1.03, 1.05, 1.08)),
    ("RC_DIP", "pullback depth to VWAP", 1.005, (1.000, 1.0025, 1.005, 1.01, 1.02, 1.03)),
    ("RC_INV", "invalidation below VWAP", 0.99, (0.999, 0.995, 0.99, 0.98, 0.97, 0.95)),
]
results = {}
for name, lab, live, values in SWEEPS:
    print("=" * 112)
    print(f"{name} — {lab}   (shipped = {live}; other three held at shipped values)")
    print("=" * 112)
    print(f"{'value':>9} | {'TRAIN n':>8}{'mean $':>9}{'win%':>7}{'total $':>10}{'avg w%':>8} "
          f"| {'TEST n':>7}{'mean $':>9}{'win%':>7}{'total $':>10}{'avg w%':>8}")
    for v in values:
        setattr(bot, name, v)
        fires = run()
        results[f"{name}={v}"] = fires
        ntr, ttr, mtr, wtr, xtr = agg([r for r in fires if r["d"] in TRAIN])
        nte, tte, mte, wte, xte = agg([r for r in fires if r["d"] in TEST])
        tag = "  <-- SHIPPED" if v == live else ""
        if mtr > 0 and ntr >= 15:
            tag += "  TRAIN+" + (" HOLDS OOS" if mte > 0 else " fails OOS")
        print(f"{v:>9} | {ntr:>8}{mtr:>9.2f}{wtr:>7.1f}{ttr:>10.2f}{xtr:>8.2f} "
              f"| {nte:>7}{mte:>9.2f}{wte:>7.1f}{tte:>10.2f}{xte:>8.2f}{tag}")
    setattr(bot, name, live)          # restore before the next sweep
    print()

json.dump({k: v for k, v in results.items()},
          open(pathlib.Path(__file__).with_name("reclaim_gates_20260730.json"), "w"), indent=1)
print("per-fire rows saved -> reclaim_gates_20260730.json")
