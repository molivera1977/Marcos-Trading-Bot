"""RECLAIM ANATOMY — WHERE DO THE WINNERS LIVE? (7/30, Marcos: "find our biggest winners of
reclaim and cross reference those constants. Let's see where the winners live").

Four of the five constants that define the reclaim lane have NEVER been measured:
    2.0x   volume multiple on the VWAP cross      (gate 1)
    +1%    extension required before a pullback counts (gate 2)
    +0.5%  pullback depth that arms the retest    (gate 2)
    -1%    invalidation                           (gate 2/3)
    N=1    confirmation bars                      (swept 7/30 -> confirm_bars_20260730.py)

This does NOT sweep them. It INSTRUMENTS the shipped machine so every fire carries the values it
actually measured at the moment it fired, then asks where the winners sit in that space. Sweeping
comes after we know where to aim — the ignition study went the other way and burned a day.

METHOD: the shipped detector runs on archived 10s bars. Disk file untouched. Four in-memory
substitutions add diagnostic fields to the state machine WITHOUT changing a single branch
condition — every patched line preserves its original code verbatim and only appends recording.
Each substitution is asserted unique and printed at run time.

READ THIS AS DESCRIPTIVE, NOT PRESCRIPTIVE. Splitting a population at the value that happens to
separate its winners is in-sample fitting by construction. Anything that looks like a threshold
here is a HYPOTHESIS that must then survive a pre-registered out-of-sample sweep before it is
recommended for anything. (7/27 law: before writing a verdict, name the check and run it.)
"""
import sys, json, types, pathlib, collections, urllib.request, statistics
import harness

RIG = pathlib.Path(__file__).resolve().parent.parent.parent / "rig"
sys.path.insert(0, str(RIG))
import loader as rig_loader

# (old, new, expected_count) — every `new` CONTAINS its `old` verbatim: recording only, no logic change
PATCHES = [
    ('st["phase"] = "extend"; st["ext"] = False',
     'st["phase"] = "extend"; st["ext"] = False; st["volmult"] = (v / avgv if avgv else 0.0);'
     ' st["cross_c"] = c; st["cross_k"] = k; st["maxext"] = 0.0; st["dip"] = None; st["bars"] = 0', 1),
    ('if c >= vwap * 1.01: st["ext"] = True',
     'st["maxext"] = max(st.get("maxext") or 0.0, (c - vwap) / vwap)\n'
     '            if c >= vwap * 1.01: st["ext"] = True', 1),
    ('st["phase"] = "retest"; st["wick"] = None',
     'st["phase"] = "retest"; st["wick"] = None; st["dip"] = (l - vwap) / vwap', 1),
    # anchor excludes the closing brace so the original code is preserved verbatim and the
    # recorded fields are simply appended to the same dict literal
    ('"wick_low": st["wick"][1], "seq": st["n"], "px": round(c, 4), "k": k',
     '"wick_low": st["wick"][1], "seq": st["n"], "px": round(c, 4), "k": k,\n'
     '                             "volmult": st.get("volmult"), "maxext": st.get("maxext"),\n'
     '                             "dip": st.get("dip"), "bars": st.get("bars"),\n'
     '                             "vwap": vwap, "cross_c": st.get("cross_c")', 1),
]

def load_patched():
    for m in ("anthropic", "resend", "webull", "webull.core", "webull.core.client",
              "webull.data", "webull.data.data_client", "websocket", "dotenv"):
        sys.modules.setdefault(m, rig_loader._Stub(m))
    src = rig_loader.BOT_PATH.read_text()
    for old, new, want in PATCHES:
        got = src.count(old)
        assert got == want, f"expected {want} site(s) for {old[:50]!r}, found {got}"
        assert old in new, "patch must PRESERVE the original code verbatim"
        src = src.replace(old, new)
        print(f"  instrumented x{want}: {old[:62]!r}")
    # bar counter from cross to fire: bumped once per bar inside the loop, no branch touched
    old_tail = '        prev_c = c\n    st["prev_c"] = prev_c'
    assert src.count(old_tail) == 1
    src = src.replace(old_tail, '        prev_c = c\n'
                                '        if st.get("bars") is not None: st["bars"] += 1\n'
                                '    st["prev_c"] = prev_c')
    mod = types.ModuleType("rc_patched_bot"); mod.__file__ = str(rig_loader.BOT_PATH)
    sys.modules["rc_patched_bot"] = mod
    exec(compile("from __future__ import annotations\n" + src, str(rig_loader.BOT_PATH), "exec"),
         mod.__dict__)
    return mod

print("INSTRUMENTING IN MEMORY (recording only — no branch condition altered):")
bot = load_patched()
bot._bucket_fresh = lambda k: True
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
print(f"disk file untouched: {rig_loader.BOT_PATH}\n")

DAYS = ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20",
        "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-27", "2026-07-28",
        "2026-07-29", "2026-07-30")

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

def _vwap_series(b):
    out, pv, vv = [], 0.0, 0.0
    for k, o, h, l, c, v, hm in b:
        pv += ((h + l + c) / 3.0) * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out

fires = []
for d in DAYS:
    for tk in sorted(universe[d]):
        b = harness.bars(tk, d)
        if not b:
            continue
        bot._reclaim_st.clear()
        vw = _vwap_series(b)
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
            fires.append({
                "d": d, "tk": tk, "hm": bar[6], "pnl": round(rep["pnl"], 2), "px": e, "stop": s,
                "w": round((e - s) / e * 100, 2), "seq": f["seq"], "shares": rep["shares"],
                "volmult": round(f.get("volmult") or 0, 2),          # gate-1 volume multiple
                "maxext": round((f.get("maxext") or 0) * 100, 2),    # % above VWAP reached
                "dip": round((f.get("dip") or 0) * 100, 2),          # pullback depth vs VWAP
                "bars": f.get("bars"),                               # 10s bars cross -> fire
                "vwdist": round((e - f["vwap"]) / f["vwap"] * 100, 2)})  # entry vs VWAP

n = len(fires)
tot = sum(f["pnl"] for f in fires)
print(f"reclaim fires: n={n}  total=${tot:.2f}  mean=${tot/n:.2f}  "
      f"win={100*sum(1 for f in fires if f['pnl']>0)/n:.1f}%\n")

print("=" * 104)
print("THE 20 BIGGEST WINNERS — what did each one actually measure at fire time?")
print("=" * 104)
print(f"{'date':<11}{'time':<10}{'tk':<7}{'$pnl':>9}{'volmult':>9}{'maxext%':>9}{'dip%':>8}"
      f"{'bars':>6}{'vwdist%':>9}{'w%':>7}{'seq':>5}")
top = sorted(fires, key=lambda f: -f["pnl"])[:20]
for f in top:
    print(f"{f['d']:<11}{f['hm']:<10}{f['tk']:<7}{f['pnl']:>9.2f}{f['volmult']:>9.2f}"
          f"{f['maxext']:>9.2f}{f['dip']:>8.2f}{f['bars']:>6}{f['vwdist']:>9.2f}{f['w']:>7.2f}{f['seq']:>5}")

print("\n" + "=" * 104)
print("WINNERS vs LOSERS — median of each constant's MEASURED value")
print("=" * 104)
W = [f for f in fires if f["pnl"] > 0]
L = [f for f in fires if f["pnl"] <= 0]
BIG = sorted(fires, key=lambda f: -f["pnl"])[:max(20, n // 20)]   # top 5% (min 20)
print(f"{'metric':<26}{'BIG WINNERS':>14}{'all winners':>14}{'losers':>14}{'  gate today':>16}")
for key, lab, gate in (("volmult", "volume multiple", ">= 2.0x"), ("maxext", "extension % above VWAP", ">= 1.0%"),
                       ("dip", "pullback depth %", ">= -0.5%"), ("bars", "bars cross->fire", "(none)"),
                       ("vwdist", "entry vs VWAP %", "(none)"), ("w", "stop width %", "(none)")):
    m = lambda rows: statistics.median([r[key] for r in rows]) if rows else 0
    print(f"{lab:<26}{m(BIG):>14.2f}{m(W):>14.2f}{m(L):>14.2f}{gate:>16}")

print("\n" + "=" * 104)
print("P&L BY BUCKET — where the money actually sits (descriptive; NOT a threshold proposal)")
print("=" * 104)
def bucket(key, edges, lab):
    print(f"\n  -- {lab} --")
    for lo, hi in zip((None,) + edges, edges + (None,)):
        rows = [f for f in fires if (lo is None or f[key] >= lo) and (hi is None or f[key] < hi)]
        if not rows:
            continue
        p = sum(r["pnl"] for r in rows)
        print(f"     {str(lo if lo is not None else ''):>7} to {str(hi if hi is not None else ''):<7} "
              f"n={len(rows):>4}  win={100*sum(1 for r in rows if r['pnl']>0)/len(rows):>5.1f}%  "
              f"tot=${p:>9.2f}  mean=${p/len(rows):>7.2f}")
bucket("volmult", (2, 3, 4, 6, 10), "GATE 1: volume multiple on the cross (live floor 2.0x)")
bucket("maxext", (1, 2, 3, 5, 8), "GATE 2: extension above VWAP reached (live floor 1.0%)")
bucket("dip", (-2, -1, -0.5, 0, 0.5), "GATE 2: pullback depth vs VWAP (live arm within +0.5%)")
bucket("bars", (6, 12, 30, 60, 120), "bars from cross to fire (10s each)")
bucket("vwdist", (0, 0.5, 1, 2, 4), "entry distance above VWAP")

json.dump(fires, open(pathlib.Path(__file__).with_name("reclaim_anatomy_20260730.json"), "w"), indent=1)
print("\nper-fire rows saved -> reclaim_anatomy_20260730.json")
