"""ZONE-FLIP THRESHOLD SWEEP (7/30, Marcos: "keep to the morning and tweak").

The window study refuted the clock hypothesis — every arm window loses, win rate pinned near 32%.
So the window stays at the SHIPPED 9:30-9:45 and the two numbers that define the SETUP move instead:

  ZONEFLIP_FLUSH (0.04 live) — how deep the flush off the 9:30 open must be to arm
  ZONEFLIP_BAND  (0.02 live) — how close the low must come to the premarket shelf

Both are live module globals, so NO source patch is needed for them. The arm window is still
substituted in memory (shipped file untouched) only so this file pins it explicitly to 570-585
rather than trusting a default.

PRE-REGISTERED, written before any number was seen:
  1. OUT-OF-SAMPLE SPLIT. TRAIN = 07-13..07-24, TEST = 07-27..07-30. A cell is a candidate only
     if it is positive in TRAIN *and* holds in TEST. Cells are ranked on TRAIN only; TEST is
     read once, after.
  2. PLATEAU RULE. A winning cell must have winning neighbours. An isolated positive surrounded
     by negatives is overfit and is reported as noise, not signal — this is exactly how the
     4-5% width bucket died in the previous cut.
  3. MINIMUM n. Any cell with TRAIN n < 15 is not eligible regardless of dollars.
  4. FAILURE CONDITION, stated up front: if no cell clears 1-3, the honest finding is that the
     setup's thresholds are not the problem either, and zone_flip goes to Fable as a KILL/SHADOW
     candidate rather than a tuning candidate.

Downstream gates are NOT applied (detector population) — read relative differences.
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

PATCH = ('if 570 <= hm <= 585 and not st["armed"]:',
         'if ZF_ARM_START <= hm <= ZF_ARM_END and not st["armed"]:')

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    assert src.count(PATCH[0]) == 1, "arm-window literal not found exactly once"
    src = "from __future__ import annotations\nZF_ARM_START = 570\nZF_ARM_END = 585\n" + src.replace(*PATCH)
    mod = types.ModuleType("zf_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["zf_patched_bot"] = mod
    exec(compile(src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

bot = load_patched()
bot._bucket_fresh = lambda k: True
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
bot.ZF_ARM_START, bot.ZF_ARM_END = 570, 585          # the live morning window, pinned
print("window pinned to the shipped 9:30-9:45; disk file untouched\n")

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

def _feed(b):
    return ({k: {"o": o, "h": h, "l": l, "c": c, "v": v} for k, o, h, l, c, v, _ in b}, "killtest")

def run(flush, band):
    bot.ZONEFLIP_FLUSH, bot.ZONEFLIP_BAND = flush, band
    fires = []
    for d in DAYS:
        for tk in sorted(universe[d]):
            b = harness.bars(tk, d)
            if not b:
                continue
            bot._zf_zone.clear(); bot._zf_st.clear()
            bot._curl_feed = lambda t, n=90, _b=b: _feed(_b)
            if not bot._zf_pm_floor(tk):
                continue
            for i, bar in enumerate(b):
                f = bot.kev_zoneflip_step(tk, [bar[:6]])
                if not f:
                    continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s):
                    continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if rep and rep.get("shares"):
                    fires.append({"d": d, "tk": tk, "hm": bar[6], "pnl": round(rep["pnl"], 2),
                                  "w": round((e - s) / e * 100, 2), "seq": f["seq"]})
    return fires

def agg(rows):
    n = len(rows); p = sum(r["pnl"] for r in rows)
    return n, (p, p / n if n else 0.0, 100 * sum(1 for r in rows if r["pnl"] > 0) / n if n else 0.0)

FLUSHES = (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12)
BANDS   = (0.005, 0.01, 0.015, 0.02, 0.03, 0.05)
grid = {}
print("=" * 104)
print("TRAIN 07-13..07-24  —  grid mean $/fire   (n in parens; live cell = flush 0.04 / band 0.02)")
print("=" * 104)
hdr = "flush\\band"
print(f"{hdr:<12}" + "".join(f"{b*100:>15.1f}%" for b in BANDS))
for fl in FLUSHES:
    row = f"{fl*100:>9.0f}%  "
    for bd in BANDS:
        fires = run(fl, bd)
        grid[(fl, bd)] = fires
        n, (tot, mean, wr) = agg([r for r in fires if r["d"] in TRAIN])
        row += f"{(f'{mean:+.2f}({n})' if n else '  -  '):>15}"
    print(row)

print("\n" + "=" * 104)
print("CANDIDATES — pre-registered gates: TRAIN mean > 0, TRAIN n >= 15, then TEST read once")
print("=" * 104)
cands = []
for (fl, bd), fires in grid.items():
    ntr, (ttr, mtr, wtr) = agg([r for r in fires if r["d"] in TRAIN])
    if mtr > 0 and ntr >= 15:
        cands.append((mtr, fl, bd, ntr, ttr, wtr, fires))
if not cands:
    print("  NONE. No (flush, band) cell is positive in TRAIN at n >= 15.")
    print("  -> FAILURE CONDITION MET (gate 4): the thresholds are not the problem either.")
for mtr, fl, bd, ntr, ttr, wtr, fires in sorted(cands, reverse=True):
    nte, (tte, mte, wte) = agg([r for r in fires if r["d"] in TEST])
    # plateau check: the 4 orthogonal neighbours in the grid
    nb = []
    for dfl, dbd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        i, j = FLUSHES.index(fl) + dfl, BANDS.index(bd) + dbd
        if 0 <= i < len(FLUSHES) and 0 <= j < len(BANDS):
            _n, (_t, _m, _w) = agg([r for r in grid[(FLUSHES[i], BANDS[j])] if r["d"] in TRAIN])
            nb.append(_m)
    good_nb = sum(1 for m in nb if m > 0)
    print(f"  flush={fl*100:>4.0f}% band={bd*100:>4.1f}%  TRAIN n={ntr:>3} mean=${mtr:>7.2f} "
          f"win={wtr:>5.1f}% tot=${ttr:>8.2f}   |   TEST n={nte:>3} mean=${mte:>7.2f} "
          f"win={wte:>5.1f}% tot=${tte:>8.2f}   | plateau {good_nb}/{len(nb)} nbrs positive"
          + ("   <-- HOLDS OOS + PLATEAU" if mte > 0 and good_nb >= 2 else ""))

json.dump({f"{fl}_{bd}": v for (fl, bd), v in grid.items()},
          open(pathlib.Path(__file__).with_name("zoneflip_params_20260730.json"), "w"), indent=1)
print("\nper-fire rows saved -> zoneflip_params_20260730.json")
