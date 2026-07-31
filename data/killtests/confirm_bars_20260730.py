"""MULTI-BAR CONFIRMATION (7/30, Marcos: "perhaps we need multiple 10 second confirmations"
+ "i believe that with reclaim").

Both curl lanes fire on ONE 10-second close above the wick high:
    zone_flip  :  if st["wick"] and c > st["wick"][0] and fired is None:
    vwap_reclaim: elif st["wick"] and c > st["wick"][0]:
That single bar is the entire "the turn is real" test. Marcos's read: one 10s close is not a
reclaim, it is a tick — demand N consecutive closes above the wick high before firing.

METHOD: the shipped detectors run, fed archived 10s bars. The disk file is NOT modified. Two
literals are substituted IN MEMORY (printed at run time so the change is auditable):
    c > st["wick"][0]   ->   _cf_ok(st, c)          (both lanes, 2 sites)
    st["wick"] = (h, l) ->   st["wick"] = (h, l); st["cf"] = 0   (2 sites, counter reset)
_cf_ok counts CONSECUTIVE closes above the wick high and returns True only at >= CONFIRM_N.
CONFIRM_N=1 is byte-equivalent to today's behaviour and is the fidelity control.

COST OF WAITING, and it is real: firing on the Nth bar means entering N-1 bars LATER and HIGHER
while the stop stays at the flush low / wick low. Wider stop, smaller size, less runway. This
test prices that cost honestly through the real sizing chain — it is not free.

PRE-REGISTERED, before any number was seen:
  1. CONFIRM_N=1 must reproduce the current fire population, or the patch is wrong and all
     other columns are VOID.
  2. OUT-OF-SAMPLE: TRAIN 07-13..07-24, TEST 07-27..07-30. Ranked on TRAIN, TEST read once.
  3. MONOTONE-OR-PLATEAU: a winning N must sit next to a non-losing neighbour. A lone spike at
     one N with losses either side is overfit (the rule that killed the 4-5% width bucket).
  4. FAILURE CONDITION: if no N is positive in TRAIN at n >= 15, multi-bar confirmation does
     not save these lanes and both go to Fable as KILL/SHADOW, not tuning.

Downstream gates (chart gate, slots, caps) are NOT applied — detector population, so read
RELATIVE differences between columns, not absolute dollars.
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

PATCHES = [('c > st["wick"][0]', '_cf_ok(st, c)', 2),
           ('st["wick"] = (h, l)', 'st["wick"] = (h, l); st["cf"] = 0', 2)]
PRELUDE = '''from __future__ import annotations
CONFIRM_N = 1
def _cf_ok(st, c):
    """N-consecutive-closes-above-the-wick-high confirmation (killtest substitution)."""
    w = st.get("wick")
    if not w:
        return False
    if c > w[0]:
        st["cf"] = st.get("cf", 0) + 1
    else:
        st["cf"] = 0
    return st.get("cf", 0) >= CONFIRM_N
'''

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    for old, new, want in PATCHES:
        got = src.count(old)
        assert got == want, f"expected {want} sites for {old!r}, found {got}"
        src = src.replace(old, new)
        print(f"  in-memory patch x{want}: {old!r}\n{'':>22}-> {new!r}")
    mod = types.ModuleType("cf_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["cf_patched_bot"] = mod
    exec(compile(PRELUDE + src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

print("PATCHING IN MEMORY (shipped file on disk untouched):")
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
print("universe:", {d: len(v) for d, v in universe.items()}, "\n")


def _feed(b):
    return ({k: {"o": o, "h": h, "l": l, "c": c, "v": v} for k, o, h, l, c, v, _ in b}, "killtest")


def _vwap_series(b):
    """session VWAP walked forward, the reclaim lane's own anchor."""
    out, pv, vv = [], 0.0, 0.0
    for k, o, h, l, c, v, hm in b:
        tp = (h + l + c) / 3.0
        pv += tp * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out


def run(lane, n_confirm):
    bot.CONFIRM_N = n_confirm
    fires = []
    for d in DAYS:
        for tk in sorted(universe[d]):
            b = harness.bars(tk, d)
            if not b:
                continue
            bot._zf_zone.clear(); bot._zf_st.clear(); bot._reclaim_st.clear()
            bot._curl_feed = lambda t, n=90, _b=b: _feed(_b)
            vw = _vwap_series(b) if lane == "reclaim" else None
            if lane == "zone_flip" and not bot._zf_pm_floor(tk):
                continue
            for i, bar in enumerate(b):
                if lane == "zone_flip":
                    f = bot.kev_zoneflip_step(tk, [bar[:6]])
                else:
                    f = bot.kev_reclaim_step(tk, [bar[:6]], vw[i])
                if not f:
                    continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s):
                    continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if rep and rep.get("shares"):
                    fires.append({"d": d, "tk": tk, "hm": bar[6], "pnl": round(rep["pnl"], 2),
                                  "w": round((e - s) / e * 100, 2), "px": e, "seq": f["seq"]})
    return fires


def agg(rows):
    n = len(rows); p = sum(r["pnl"] for r in rows)
    return n, p, (p / n if n else 0.0), (100 * sum(1 for r in rows if r["pnl"] > 0) / n if n else 0.0), \
           (sum(r["w"] for r in rows) / n if n else 0.0)


NS = (1, 2, 3, 4, 5, 6)
results = {}
for lane in ("zone_flip", "reclaim"):
    print("=" * 108)
    print(f"{lane.upper()}  —  consecutive 10s closes above the wick high required to fire")
    print("=" * 108)
    print(f"{'N':>3} | {'TRAIN n':>8} {'mean $':>9} {'win%':>6} {'total $':>10} {'avg w%':>7} "
          f"| {'TEST n':>7} {'mean $':>9} {'win%':>6} {'total $':>10} {'avg w%':>7}")
    for N in NS:
        fires = run(lane, N)
        results[f"{lane}_{N}"] = fires
        ntr, ttr, mtr, wtr, xtr = agg([r for r in fires if r["d"] in TRAIN])
        nte, tte, mte, wte, xte = agg([r for r in fires if r["d"] in TEST])
        flag = ""
        if mtr > 0 and ntr >= 15:
            flag = "  <-- TRAIN positive" + (" + HOLDS OOS" if mte > 0 else " (fails OOS)")
        print(f"{N:>3} | {ntr:>8} {mtr:>9.2f} {wtr:>6.1f} {ttr:>10.2f} {xtr:>7.2f} "
              f"| {nte:>7} {mte:>9.2f} {wte:>6.1f} {tte:>10.2f} {xte:>7.2f}{flag}")
    print()

json.dump(results, open(pathlib.Path(__file__).with_name("confirm_bars_20260730.json"), "w"), indent=1)
print("per-fire rows saved -> confirm_bars_20260730.json")
