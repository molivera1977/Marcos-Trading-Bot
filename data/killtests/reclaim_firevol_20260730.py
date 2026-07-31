"""RECLAIM: RE-CHECK VOLUME AT THE FIRE BAR (7/30, Marcos: "run it").

THE DEFECT THIS TESTS (found in today's five reclaim losers):
  The `v >= 2.0 * avgv` participation test lives in PHASE 1 (the VWAP cross). The machine then
  walks extend -> retest -> wick -> confirm, and FIRES on whatever bar happens to close above
  the wick high — with NO re-check that anyone is still trading. The gate and the entry are
  measured at different moments, sometimes 90+ seconds apart.
  All five of today's reclaim losers fired BELOW 2x: 0.1x, 0.8x, 1.8x, 1.5x, 0.1x.
  YHC bought a 150-share bar ($296). SKYQ bought 142 shares ($670).

THE TEST: require the FIRING bar to carry v >= RC_FIREVOL * avgv, where avgv is the same rolling
average the lane already computes. This is a RE-CHECK of an existing condition at the correct
moment — NOT the absolute dollar floor tested and refuted earlier today (that one applied a fixed
$ threshold and died by clipping the tail; this one is relative to the name's own tape).
RC_FIREVOL = 0 is the control and must reproduce today's behaviour exactly.

PRE-REGISTERED, written before any number was seen:
  1. FIDELITY: RC_FIREVOL=0 must reproduce n~784 / ~-$4849, or the patch changed behaviour: VOID.
  2. OOS: TRAIN 07-13..07-24 ranks; TEST 07-27..07-30 read ONCE, after.
  3. PLATEAU: a winning value needs a non-losing neighbour. Lone spikes are overfit.
  4. MIN n: TEST n < 30 is not eligible.
  5. TAIL TEST (the trap that killed the absolute floor): report how many >=2R-MFE fires survive.
     A setting that crosses zero by deleting the tail is REJECTED — reclaim's edge, if it has
     one, is convexity (10.2% of fires reach 5R+), not win rate.
  6. FAILURE CONDITION: if no value is positive on TEST at n>=30, the fire-bar volume re-check
     is REFUTED and reported as refuted. Today's 5 losers failing it proves nothing on its own —
     they were selected after the fact.
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

PATCH = ('elif st["wick"] and c > st["wick"][0]:',
         'elif st["wick"] and c > st["wick"][0] and v >= RC_FIREVOL * avgv:')

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    assert src.count(PATCH[0]) == 1, f"fire site not unique ({src.count(PATCH[0])})"
    src = "from __future__ import annotations\nRC_FIREVOL = 0.0\n" + src.replace(*PATCH)
    mod = types.ModuleType("fv_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["fv_patched_bot"] = mod
    exec(compile(src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

print("IN-MEMORY PATCH (disk file untouched):")
print(f"  {PATCH[0]!r}\n  -> {PATCH[1]!r}\n")
bot = load_patched()
bot._bucket_fresh = lambda k: True
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9

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

_bc = {}
def day_bars(d):
    if d not in _bc:
        _bc[d] = [(tk, b) for tk in sorted(universe[d]) for b in [harness.bars(tk, d)] if b]
    return _bc[d]

_vc = {}
def vwaps(d, tk, b):
    if (d, tk) not in _vc:
        out, pv, vv = [], 0.0, 0.0
        for k, o, h, l, c, v, hm in b:
            pv += ((h + l + c) / 3.0) * v; vv += v
            out.append(pv / vv if vv > 0 else c)
        _vc[(d, tk)] = out
    return _vc[(d, tk)]

def run(fv):
    bot.RC_FIREVOL = fv
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
                if not rep or not rep.get("shares"):
                    continue
                peak = e
                for x in b[i:]:
                    peak = max(peak, x[2])
                    if x[3] <= s:
                        break
                fires.append({"d": d, "pnl": round(rep["pnl"], 2), "mfe": (peak - e) / (e - s)})
    return fires

def agg(rs):
    n = len(rs)
    if not n:
        return 0, 0.0, 0.0, 0.0, 0
    p = sum(r["pnl"] for r in rs)
    return n, p, p / n, 100 * sum(1 for r in rs if r["pnl"] > 0) / n, sum(1 for r in rs if r["mfe"] >= 2)

print("=" * 118)
print("FIRE-BAR VOLUME RE-CHECK  (v >= X * avgv ON THE CONFIRMING BAR; cross gate unchanged at 2.0x)")
print("=" * 118)
print(f"{'X':>6} | {'TRAIN n':>8}{'mean $':>9}{'win%':>7}{'total $':>10} "
      f"| {'TEST n':>7}{'mean $':>9}{'win%':>7}{'total $':>10}{'tail>=2R':>10}{'tail kept':>11}")
base_tail = None
res = {}
for fv in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
    fires = run(fv)
    res[fv] = fires
    ntr, ttr, mtr, wtr, _ = agg([r for r in fires if r["d"] in TRAIN])
    nte, tte, mte, wte, tail = agg([r for r in fires if r["d"] in TEST])
    if base_tail is None:
        base_tail = tail or 1
        print(f"{fv:>6} | {ntr:>8}{mtr:>9.2f}{wtr:>7.1f}{ttr:>10.2f} "
              f"| {nte:>7}{mte:>9.2f}{wte:>7.1f}{tte:>10.2f}{tail:>10}{'100.0%':>11}  <-- CONTROL")
        continue
    tag = "  <-- POSITIVE OOS" if (mte > 0 and nte >= 30) else ""
    print(f"{fv:>6} | {ntr:>8}{mtr:>9.2f}{wtr:>7.1f}{ttr:>10.2f} "
          f"| {nte:>7}{mte:>9.2f}{wte:>7.1f}{tte:>10.2f}{tail:>10}"
          f"{100*tail/base_tail:>10.1f}%{tag}")

print("\n" + "=" * 118)
print("VERDICT AGAINST THE PRE-REGISTERED GATES")
print("=" * 118)
winners = []
for fv, fires in res.items():
    if fv == 0.0:
        continue
    nte, tte, mte, wte, tail = agg([r for r in fires if r["d"] in TEST])
    if mte > 0 and nte >= 30:
        winners.append((fv, mte, nte, tail))
if not winners:
    print("  NO value of the fire-bar volume re-check is positive on TEST at n>=30.")
    print("  -> FAILURE CONDITION MET (gate 6): REFUTED as a fix. Report as refuted.")
for fv, mte, nte, tail in winners:
    print(f"  X={fv}: TEST mean=${mte:.2f} n={nte} tail kept={100*tail/base_tail:.1f}% "
          f"-> {'PASSES gate 5' if tail/base_tail >= 0.7 else 'FAILS gate 5 (tail destroyed)'}")

json.dump({str(k): v for k, v in res.items()},
          open(pathlib.Path(__file__).with_name("reclaim_firevol_20260730.json"), "w"), indent=1)
print("\nrows saved -> reclaim_firevol_20260730.json")
