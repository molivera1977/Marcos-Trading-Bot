"""ZONE-FLIP WIDENED-WINDOW STUDY (7/30, Marcos: "try it").

QUESTION: zone_flip's Z1 arm is specified to 9:30-9:45 only — fifteen minutes a day, which is
also the worst fifteen minutes on our clock. Is the flush-into-the-premarket-shelf setup bad,
or is it merely confined to a bad hour?

METHOD: the REAL detector runs — bot.kev_zoneflip_step and the real bot._zf_pm_floor zone — fed
archived 10s bars. The shipped file on disk is NOT modified. Instead the bot source is loaded
into memory and ONE literal is substituted (see PATCH below) so the arm window becomes settable.
Everything else is the shipped machine, byte for byte. No hand-written copy of the detector —
that is what voided the 7/29 chart-gate study.

The zone is ALWAYS the premarket shelf in every cell; only the window in which a flush may ARM
moves. Downstream gates (chart gate, slots, caps) are NOT applied — this is the DETECTOR
population, so read RELATIVE differences between cells, not absolute dollars.

PRE-REGISTERED (written before any number was seen):
  - FIDELITY GATE: the baseline cell (570-585) must produce fires on the same names/days the
    live lane triggered on. If it does not, the rig is not modelling the live lane and every
    other cell in this file is VOID.
  - "The clock is the problem" is SUPPORTED only if widened cells show a materially better
    per-fire dollar mean on n >= 20 fires. More fires at the same bad mean = the SETUP is the
    problem, not the hour, and widening is not a fix.
  - A single winning cell surrounded by losing cells is overfit, not signal (plateau rule).
"""
import sys, json, types, pathlib, collections, urllib.request
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

# ── in-memory source patch: the shipped constant becomes a module global we can set ──────────
PATCH = ("if 570 <= hm <= 585 and not st[\"armed\"]:",
         "if ZF_ARM_START <= hm <= ZF_ARM_END and not st[\"armed\"]:")

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    assert src.count(PATCH[0]) == 1, f"arm-window literal not found exactly once ({src.count(PATCH[0])})"
    src = src.replace(*PATCH)
    src = "from __future__ import annotations\nZF_ARM_START = 570\nZF_ARM_END = 585\n" + src
    mod = types.ModuleType("zf_patched_bot")
    mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["zf_patched_bot"] = mod
    exec(compile(src, str(rig_loader.BOT_PATH), "exec"), mod.__dict__)
    return mod

bot = load_patched()
print(f"PATCH applied in memory only: {PATCH[0]!r}\n              ->              {PATCH[1]!r}")
print(f"disk file untouched: {rig_loader.BOT_PATH}\n")

bot._bucket_fresh = lambda k: True          # archived bars are wall-clock stale by construction
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9

DAYS = ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
        "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-27", "2026-07-28",
        "2026-07-29", "2026-07-30")

# universe: every name the bot watched that day, so a widened window is free to find NEW names
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


def _feed_from(b):
    """archived harness bars -> the dict-of-dicts shape _curl_feed hands _zf_pm_floor."""
    return ({k: {"o": o, "h": h, "l": l, "c": c, "v": v} for k, o, h, l, c, v, _ in b}, "killtest")


def run(arm_start, arm_end, label):
    bot.ZF_ARM_START, bot.ZF_ARM_END = arm_start, arm_end
    fires, pnl, wins = [], 0.0, 0
    for d in DAYS:
        for tk in sorted(universe[d]):
            b = harness.bars(tk, d)
            if not b:
                continue
            bot._zf_zone.clear(); bot._zf_st.clear()
            bot._curl_feed = lambda t, n=90, _b=b: _feed_from(_b)
            if not bot._zf_pm_floor(tk):
                continue                                  # no premarket shelf -> lane idles, as live
            for i, bar in enumerate(b):
                f = bot.kev_zoneflip_step(tk, [bar[:6]])
                if not f:
                    continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s):
                    continue
                rep = harness.replay(tk, d, e, s, i0=i)
                if not rep or not rep.get("shares"):
                    continue
                fires.append({"d": d, "tk": tk, "hm": bar[6], "px": e, "stop": s,
                              "w": round((e - s) / e * 100, 2), "pnl": round(rep["pnl"], 2),
                              "seq": f["seq"], "zone_src": f["zone_src"], "shares": rep["shares"]})
                pnl += rep["pnl"]; wins += 1 if rep["pnl"] > 0 else 0
    n = len(fires)
    print(f"{label:<30} fires={n:>4}  wins={wins:>3} ({(wins/n*100 if n else 0):>5.1f}%)  "
          f"total=${pnl:>9.2f}  per-fire=${(pnl/n if n else 0):>7.2f}")
    return fires


print("=" * 100)
print("ARM-WINDOW SWEEP  (zone = premarket shelf in every cell; only the arm window moves)")
print("=" * 100)
CELLS = [(570, 585, "BASELINE 9:30-9:45 (live)"), (570, 600, "9:30-10:00"),
         (570, 630, "9:30-10:30"), (570, 720, "9:30-12:00"), (570, 960, "9:30-16:00 (all day)"),
         (585, 630, "9:45-10:30 (open EXCLUDED)"), (600, 960, "10:00-16:00 (open EXCLUDED)"),
         (630, 960, "10:30-16:00")]
out = {lab: run(a, z, lab) for a, z, lab in CELLS}

print("\n" + "=" * 100)
print("FIDELITY GATE — baseline cell vs the live lane's triggered fires")
print("=" * 100)
base = out["BASELINE 9:30-9:45 (live)"]
for f in sorted(base, key=lambda x: (x["d"], x["hm"])):
    print(f"  {f['d']}  {f['hm']}  {f['tk']:<6} entry {f['px']:>7.3f}  stop {f['stop']:>7.3f}  "
          f"w={f['w']:>5.2f}%  seq={f['seq']}  ${f['pnl']:>8.2f}")

allday = out["9:30-16:00 (all day)"]
print("\n" + "=" * 100)
print("ALL-DAY CELL, CUT BY FIRE HOUR  (the clock question, answered directly)")
print("=" * 100)
byhr = collections.defaultdict(list)
for f in allday:
    byhr[f["hm"][:2]].append(f["pnl"])
for hr in sorted(byhr):
    v = byhr[hr]
    print(f"  {hr}:00-{hr}:59   n={len(v):>3}  wins={sum(1 for x in v if x > 0):>3}  "
          f"total=${sum(v):>9.2f}  mean=${sum(v)/len(v):>7.2f}")

print("\nall-day cell by day:")
byday = collections.defaultdict(list)
for f in allday:
    byday[f["d"]].append(f["pnl"])
for d in sorted(byday):
    print(f"  {d}  n={len(byday[d]):>3}  total=${sum(byday[d]):>9.2f}")

json.dump(out, open(pathlib.Path(__file__).with_name("zoneflip_window_20260730.json"), "w"), indent=1)
print("\nper-fire rows saved -> zoneflip_window_20260730.json")
