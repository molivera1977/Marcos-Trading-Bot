"""RECLAIM ONE-SLOT REPLAY (7/28) — does the once-per-(day,sym,lane,session) live slot cost us?

Context: the confirmation sequence is CLEARED (reclaim_leg_cost_replay.py refuted "the gates cost
the leg" — entering at the cross was stopped out 6/6). Reclaim's problem is therefore selection or
exits. This tests one concrete selection rule: _curl_rth_slot() (:4088) grants the live slot to the
FIRST converting RTH fire per name; every later fire that day is shadow-only. Observed on KIDZ 7/27:
seq0 peaked +0.65% and stopped; seq1 peaked +51.97% and never stopped — and was untradeable.

METHOD: bot's own kev_reclaim_step over real ALP10S tape, RTH only, bars walked IN ORDER, session
VWAP accumulated progressively, no lookahead. For every fire: forward-walk with the stop checked on
EVERY bar BEFORE crediting the high (a stop swept on the way up ends the trade there). Peak measured
in DOLLARS through the real sizing chain (RISK_PER_TRADE / risk-per-share, $1k notional cap) —
R is not comparable across entries at different prices with different stops.

Compares three policies on the SAME fire population:
  FIRST   take seq0 only                       (what ships today)
  BEST    take the best fire of the day        (unachievable oracle — the ceiling, not a proposal)
  ALL     take every fire                      (what removing the cap would do)
Peak-$ is an UPPER BOUND on capture, not a P&L: it assumes a perfect exit at the high. It cannot
say a policy is profitable — only whether the slot rule is systematically discarding the better fire.
"""
import json, os, sys, urllib.request, urllib.parse, statistics as st
from datetime import datetime, timedelta, timezone
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()

U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
RISK = float(os.environ.get("RISK_PER_TRADE", "30"))
CAP = 1000.0
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9   # replay must detect; nothing trades here


def fetch(date, tk):
    try:
        r = json.load(urllib.request.urlopen(
            f"{U}/api/bars?date={date}&ticker={urllib.parse.quote(tk + '~ALP10S')}", timeout=25))
        return r.get("bars") or []
    except Exception:
        return []


def norm(bars):
    out = []
    for x in bars:
        t = x.get("time") or x.get("t")
        if not t:
            continue
        try:
            dt = datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc).astimezone(ET)
        except Exception:
            continue
        hm = dt.strftime("%H:%M")
        if hm < "09:30" or hm >= "16:00":
            continue
        out.append((int(dt.timestamp()), float(x.get("open") or x.get("o")),
                    float(x.get("high") or x.get("h")), float(x.get("low") or x.get("l")),
                    float(x.get("close") or x.get("c")), float(x.get("volume") or x.get("v") or 0), dt))
    return sorted(out)


def walk(bars, i0, entry, stop):
    """Stop checked BEFORE the high on every bar — no crediting moves the trade wasn't alive for."""
    r = entry - stop
    if r <= 0:
        return None
    peak = entry
    for j in range(i0 + 1, len(bars)):
        if bars[j][3] <= stop:
            return (peak - entry) / entry * 100, True
        peak = max(peak, bars[j][2])
    return (peak - entry) / entry * 100, False


def peak_dollars(entry, stop, pk_pct):
    rps = entry - stop
    if rps <= 0:
        return 0.0
    sh = int(min(RISK / rps, CAP / entry))
    return sh * entry * (pk_pct / 100.0)


def replay(sym, bars):
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    fires = []
    for i, (k, o, h, l, c, v, dt) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v
        vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        if f:
            w = walk(bars, i, f["px"], f["stop"])
            if not w:
                continue
            fires.append({"seq": f["seq"], "px": f["px"], "stop": f["stop"], "t": dt.strftime("%H:%M:%S"),
                          "pk_pct": w[0], "stopped": w[1],
                          "pk_$": peak_dollars(f["px"], f["stop"], w[0])})
    return fires


DATES = sys.argv[1:] or ["2026-07-27", "2026-07-28"]
allfires = {}
for date in DATES:
    idx = json.load(urllib.request.urlopen(f"{U}/api/bars?date={date}"))
    names = [t.split("~")[0] for t in idx.get("archived", {}).get(date, []) if "ALP10S" in t.upper()]
    print(f"{date}: {len(names)} names with 10s tape — replaying", flush=True)
    for n, tk in enumerate(names):
        b = norm(fetch(date, tk))
        if len(b) < 120:
            continue
        f = replay(tk, b)
        if f:
            allfires[(date, tk)] = f
        if (n + 1) % 50 == 0:
            print(f"   ...{n+1}/{len(names)}", flush=True)

multi = {k: v for k, v in allfires.items() if len(v) > 1}
print(f"\nnames that fired: {len(allfires)}   total fires: {sum(len(v) for v in allfires.values())}")
print(f"names with MORE THAN ONE fire (where the slot rule bites): {len(multi)}")

def policy(pick):
    tot = 0.0
    rows = []
    for (d, tk), fs in allfires.items():
        c = pick(fs)
        if c:
            tot += c["pk_$"]
            rows.append((d, tk, c))
    return tot, rows

t_first, r_first = policy(lambda fs: fs[0])
t_best, _ = policy(lambda fs: max(fs, key=lambda x: x["pk_$"]))
t_all = sum(f["pk_$"] for fs in allfires.values() for f in fs)
n_all = sum(len(v) for v in allfires.values())
print(f"\n{'policy':22}{'entries':>9}{'total peak $':>15}{'per entry':>12}")
print(f"  {'FIRST (ships today)':20}{len(r_first):9}{t_first:15.2f}{t_first/max(len(r_first),1):12.2f}")
print(f"  {'BEST (oracle ceiling)':20}{len(allfires):9}{t_best:15.2f}{t_best/max(len(allfires),1):12.2f}")
print(f"  {'ALL (no cap)':20}{n_all:9}{t_all:15.2f}{t_all/max(n_all,1):12.2f}")

print(f"\nstopped-out rate: FIRST {sum(1 for _,_,c in r_first if c['stopped'])}/{len(r_first)}"
      f"   ALL {sum(1 for fs in allfires.values() for f in fs if f['stopped'])}/{n_all}")

worse = [(d, tk, fs) for (d, tk), fs in multi.items()
         if max(f["pk_$"] for f in fs) > fs[0]["pk_$"] * 1.5]
print(f"\nnames where a LATER fire beat the first by >50%: {len(worse)}/{len(multi)} multi-fire names")
for d, tk, fs in sorted(worse, key=lambda x: -(max(f['pk_$'] for f in x[2]) - x[2][0]['pk_$']))[:12]:
    b = max(fs, key=lambda x: x["pk_$"])
    print(f"  {d[5:]} {tk:6} seq0 {fs[0]['t']} {fs[0]['pk_pct']:6.2f}% ${fs[0]['pk_$']:7.2f}"
          f"   ->  seq{b['seq']} {b['t']} {b['pk_pct']:6.2f}% ${b['pk_$']:7.2f}   (+${b['pk_$']-fs[0]['pk_$']:.2f})")

json.dump({f"{d}|{tk}": fs for (d, tk), fs in allfires.items()},
          open("/tmp/reclaim_slot_fires.json", "w"), default=str)
print("\nfires -> /tmp/reclaim_slot_fires.json")
print("\nPEAK-$ IS AN UPPER BOUND (perfect exit at the high), NOT a P&L. This can show the slot rule")
print("discards better fires; it CANNOT show any policy is profitable. Exit ladder not simulated.")
