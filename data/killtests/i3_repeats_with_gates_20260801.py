"""I3 — DO REPEAT FIRES SURVIVE GATING? (registered §I3; run 8/1 00:xx)

THE QUESTION: ignition's pro-cap evidence (606 raw fires −$1,759 vs first-only +$129) predates
every quality gate. Marcos's doctrine: instances on merits, never ticker counts. If TODAY'S gate
stack (convert>=4.5x + runway>=1R + break-side) filters repeats into profitability, per-name caps
are obsolete and I4 (concurrency) replaces them. If gated repeats still bleed, repeats have a
non-symbol problem that must be explained before any cap moves.

METHOD (the registered one, all four requirements):
  1. REAL detector re-run (ignition_10s_step at its live 2.0x detection) over archived tape,
     7/22-7/31 (the days with archived kev levels). EVERY fire kept, not once-per-ticker.
  2. Gates applied per fire: volx >= 4.5 (convert bar) · runway >= 1R vs the day's sheet
     (fail-open) · break-side entry <= break (fail-open). = Monday's live stack.
  3. CAPITAL BOUND: chronological walk per day, max 3 concurrent positions; a taken fire occupies
     its slot until its replay exit; later qualifying fires WAIT (skipped if busy — conservative).
  4. Fable's column: COST PER FAILED ATTEMPT (mean loss among losing taken attempts) — Kev's
     re-entry loop only transfers if failures are cheap.
  5. Trend-name separation (G8/§I2 law): names whose day range > 50% reported apart — one FCUV
     must never carry a verdict.
  SPLIT: TRAIN 7/22-7/28 · TEST 7/29-7/31, read once.
"""
import json, urllib.request, collections, datetime, pathlib, sys
import harness

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9

U = harness.U
DAYS = ["2026-07-%02d" % d for d in (22, 23, 24, 27, 28, 29, 30, 31)]
TRAIN = set(DAYS[:5])

levels = {}
universe = collections.defaultdict(set)
for d in DAYS:
    try:
        levels[d] = json.load(urllib.request.urlopen(
            f"{U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {}
        rows = json.load(urllib.request.urlopen(
            f"{U}/api/decisions_archive?date={d}&limit=50000", timeout=60)).get("rows") or []
    except Exception as e:
        print(f"!! {d} fetch failed {e}"); continue
    for r in rows:
        if str(r.get("status", "")).startswith(("triggered_ignition", "ignition_")):
            if r.get("ticker"):
                universe[d].add(r["ticker"])
print("universe:", {d: len(v) for d, v in universe.items()})
for d in DAYS:
    assert universe[d], f"coverage collapse {d} (G8)"

def hm_s(e):
    return datetime.datetime.fromtimestamp(e, harness.ET).strftime("%H:%M:%S")

fires = []
for d in DAYS:
    for tk in sorted(universe[d]):
        b = harness.bars(tk, d)
        if not b:
            continue
        bot._ig10_st.pop(tk, None)
        seq = 0
        for i, bar in enumerate(b):
            f = bot.ignition_10s_step(tk, [bar[:6]])
            if not f:
                continue
            e, s = f.get("px"), f.get("stop")
            if not (e and s and e > s):
                continue
            seq += 1
            lv = (levels[d].get(tk) or {})
            try: brk = float(lv.get("break") or 0)
            except Exception: brk = 0.0
            tg = sorted(float(x) for x in (lv.get("targets") or []) if float(x) > e)
            ns = float(lv.get("next_supply") or 0)
            t1 = tg[0] if tg else (ns if ns > e else None)
            rw = (t1 - e) / (e - s) if t1 else None
            gate = (float(f.get("volx") or 0) >= 4.5
                    and not (isinstance(rw, float) and rw < 1.0)
                    and not (brk > 0 and e > brk))
            fires.append({"d": d, "tk": tk, "i0": i, "epoch": bar[0], "hm": hm_s(bar[0]),
                          "e": e, "s": s, "volx": f.get("volx"), "rw": rw, "brk": brk,
                          "seq": seq, "gate": gate})
print(f"detector fires: {len(fires)}  (gate-passing: {sum(1 for f in fires if f['gate'])})")

# trend-name flag
trend = set()
for d in DAYS:
    for tk in universe[d]:
        b = harness.bars(tk, d)
        if not b: continue
        rth = [x for x in b if x[6] >= "09:30:00"]
        if rth and min(x[3] for x in rth) > 0 and max(x[2] for x in rth) / min(x[3] for x in rth) > 1.5:
            trend.add((d, tk))

# ── capital-bounded chronological sim, gated fires only ─────────────────────────────────────
MAXPOS = 3
taken, skipped_busy = [], 0
for d in DAYS:
    day = sorted([f for f in fires if f["d"] == d and f["gate"]], key=lambda x: x["epoch"])
    active = []      # exit epochs
    for f in day:
        active = [x for x in active if x > f["epoch"]]
        if len(active) >= MAXPOS:
            skipped_busy += 1
            continue
        rep = harness.replay(f["tk"], d, f["e"], f["s"], i0=f["i0"])
        if not (rep and rep.get("shares")):
            continue
        ev = rep.get("events") or []
        exit_hm = ev[-1][0] if ev else "15:45:00"
        try:
            h, m, sec = map(int, exit_hm.split(":"))
            base = datetime.datetime.fromtimestamp(f["epoch"], harness.ET)
            exit_epoch = base.replace(hour=h, minute=m, second=sec).timestamp()
        except Exception:
            exit_epoch = f["epoch"] + 3600
        active.append(exit_epoch)
        taken.append({**f, "pnl": rep["pnl"]})
print(f"capital-bounded (max {MAXPOS}): taken={len(taken)}  skipped-while-busy={skipped_busy}")

def agg(g, lab):
    n = len(g)
    if not n:
        print(f"  {lab:<44} n=0"); return
    p = sum(x["pnl"] for x in g)
    losers = [x["pnl"] for x in g if x["pnl"] < 0]
    cfa = (sum(losers) / len(losers)) if losers else 0.0
    print(f"  {lab:<44} n={n:>3}  ${p:>9.2f}  mean ${p/n:>7.2f}  "
          f"win {100*sum(1 for x in g if x['pnl']>0)/n:>4.0f}%  cost/fail ${cfa:>7.2f}")

print("\n" + "=" * 100)
print("I3 — GATED, CAPITAL-BOUNDED (Monday's stack, max 3 concurrent)")
print("=" * 100)
for split, days in (("TRAIN 7/22-28", TRAIN), ("TEST 7/29-31", set(DAYS) - TRAIN)):
    sub = [x for x in taken if x["d"] in days]
    print(f"\n{split}:")
    agg([x for x in sub if x["seq"] == 1], "FIRST fire per name")
    agg([x for x in sub if x["seq"] > 1], "REPEAT fires")
    agg([x for x in sub if x["seq"] > 1 and (x["d"], x["tk"]) not in trend], "  repeats EX-TREND-NAMES (>50% range out)")
    agg([x for x in sub if x["seq"] > 1 and (x["d"], x["tk"]) in trend], "  repeats on trend names only")

print("\nUNGATED reference (same capital sim, gates ignored):")
taken2 = []
for d in DAYS:
    day = sorted([f for f in fires if f["d"] == d], key=lambda x: x["epoch"])
    active = []
    for f in day:
        active = [x for x in active if x > f["epoch"]]
        if len(active) >= MAXPOS: continue
        rep = harness.replay(f["tk"], d, f["e"], f["s"], i0=f["i0"])
        if not (rep and rep.get("shares")): continue
        ev = rep.get("events") or []
        try:
            h, m, sec = map(int, (ev[-1][0] if ev else "15:45:00").split(":"))
            base = datetime.datetime.fromtimestamp(f["epoch"], harness.ET)
            active.append(base.replace(hour=h, minute=m, second=sec).timestamp())
        except Exception:
            active.append(f["epoch"] + 3600)
        taken2.append({**f, "pnl": rep["pnl"]})
agg([x for x in taken2 if x["seq"] == 1], "FIRST (ungated)")
agg([x for x in taken2 if x["seq"] > 1], "REPEAT (ungated)")

json.dump({"taken": taken, "skipped_busy": skipped_busy},
          open(pathlib.Path(__file__).with_name("i3_repeats_20260801.json"), "w"), indent=1, default=str)
print("\nrows -> i3_repeats_20260801.json")
print("\nVERDICT RULE (registered): gated repeats non-negative on BOTH splits with cheap failures")
print("=> caps -> concurrency (I4). Gated repeats bleed => repeats have a non-symbol problem.")
