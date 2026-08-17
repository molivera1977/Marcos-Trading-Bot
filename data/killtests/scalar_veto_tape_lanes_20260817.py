#!/usr/bin/env python3
"""KILL-TEST (BEFORE CODE) — the dollar price of momentum/vel5 scalar vetoes on TAPE lanes.
Batch-2 item A, 8/17. Doctrine under test: 7/26 "do-not-trade blocks CHART lanes only;
tape lanes trade through by design" — is exempting tape lanes from momentum_reject/vel5_reject
net POSITIVE? If NET NEGATIVE -> STOP, do not build the exemption.

TAPE-LANE SET (derived, not guessed — see scalar_veto_tape_lanes_20260817.md):
  10s live-structure lanes: kevseq, v2conv, grinder, bandpass, prevwap
  (hidden_entry / vwap_reclaim / zone_flip / ignition / bounce / orb / flat_top / ma_pullback
   are ALREADY in the momentum exempt tuple at :12595 — no counterfactual exists for them;
   their momentum_reject rows are universal-gate tradeability floors, which STAY.)

METHOD:
  archive rows 6/29-8/17 (cache dir passed as argv[1]); momentum_reject joined to a tape-lane
  triggered_* row same ticker/date within 180s BEFORE the reject; universal-gate /
  tradeability reasons EXCLUDED (topping tail, illiquid, thin ambient, universal gate,
  session-bars fail-open) — only setup-quality "no momentum build / volume" vetoes count.
  vel5_reject: machine stamped in-row; tape lanes are not in the vel5 applies-to set
  {flat_top, ma_pullback, orb, ema_bounce} so expected N=0 (verified, reported).
  Counterfactual: E3 live-parity on data/universe/bars10s (stress-test F spec):
  $500 position, +1% entry slip, bank 1/2 at +10% (resting limit, exact), trail rest
  10%-off-run-high on CLOSES, no breakeven, intrabar stop FIRST (tie against the trade),
  -0.5% on all market exits, EOD flatten. Stop = trigger row's stop, else fire-1min low,
  else entry*0.94 (6% min-stop floor parity).
"""
import json, os, sys, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B10 = os.path.join(ROOT, "data", "universe", "bars10s")
ARCH = sys.argv[1] if len(sys.argv) > 1 else None
assert ARCH and os.path.isdir(ARCH), "pass archive cache dir"

TAPE_TRIG = {"triggered_kevseq": "kevseq", "triggered_v2conv": "v2conv",
             "triggered_grinder": "grinder", "triggered_bandpass": "bandpass",
             "triggered_prevwap": "prevwap"}
TRADEABILITY = ("universal gate", "topping tail", "illiquid", "thin ambient",
                "session bars available")
POS, SLIP, MKT = 500.0, 0.01, 0.005

def hms(t):  # "10:18:37 AM" -> seconds
    if not t: return None
    try:
        return int(datetime.datetime.strptime(t.strip(), "%I:%M:%S %p").strftime("%H"))*3600 + \
               int(datetime.datetime.strptime(t.strip(), "%I:%M:%S %p").strftime("%M"))*60 + \
               int(datetime.datetime.strptime(t.strip(), "%I:%M:%S %p").strftime("%S"))
    except Exception: return None

def bar_secs(b):  # UTC ISO -> ET seconds (summer: UTC-4)
    hh, mm, ss = int(b["time"][11:13]), int(b["time"][14:16]), int(b["time"][17:19])
    return (hh - 4) * 3600 + mm * 60 + ss

def sim_e3(bars, i0, sig_px, stop, log=None):
    entry_px = sig_px * (1 + SLIP)
    sh = POS / entry_px; rem = sh; pnl = 0.0; scaled = False
    bank_sh = sh * 0.5; target = entry_px * 1.10; run_hi = entry_px
    def L(m):
        if log is not None: log.append(m)
    for i in range(i0 + 1, len(bars)):
        b = bars[i]
        if b["low"] <= stop:
            px = stop * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{b['time']} STOP {stop:.4f} fill {px:.4f}"); return pnl, "stop"
        if not scaled and b["high"] >= target:
            pnl += bank_sh * (target - entry_px); rem -= bank_sh; scaled = True
            L(f"{b['time']} BANK 1/2 at {target:.4f}"); continue
        run_hi = max(run_hi, b["high"])
        if scaled and b["close"] < run_hi * 0.90:
            px = b["close"] * (1 - MKT); pnl += rem * (px - entry_px)
            L(f"{b['time']} TRAIL close {b['close']:.4f} runhi {run_hi:.4f}"); return pnl, "trail"
    px = bars[-1]["close"] * (1 - MKT); pnl += rem * (px - entry_px)
    L(f"{bars[-1]['time']} EOD {px:.4f}"); return pnl, "eod"

def main():
    vetoed, vel5_tape, excluded = [], [], 0
    for f in sorted(glob.glob(ARCH + "/*.json")):
        j = json.load(open(f)); rows = j.get("rows", [])
        if not rows: continue
        trigs = [(r["ticker"], hms(r.get("time")), TAPE_TRIG[r["status"]], r)
                 for r in rows if r.get("status") in TAPE_TRIG]
        for r in rows:
            st = r.get("status")
            if st == "vel5_reject" and r.get("machine") in ("kevseq", "v2conv", "grinder",
                                                            "bandpass", "prevwap"):
                vel5_tape.append(r)
            if st != "momentum_reject": continue
            rs = hms(r.get("time"));  rz = (r.get("reason") or "").lower()
            if rs is None: continue
            cand = [t for t in trigs if t[0] == r.get("ticker") and t[1] is not None
                    and 0 <= rs - t[1] <= 180]
            if not cand: continue
            if any(k in rz for k in TRADEABILITY):
                excluded += 1; continue
            t = max(cand, key=lambda x: x[1])
            vetoed.append((j.get("date") or f[-15:-5], r, t[2], t[3]))
    print(f"tape-lane momentum vetoes N={len(vetoed)} (tradeability-excluded joins: {excluded})")
    print(f"vel5_reject on tape lanes N={len(vel5_tape)} (expected 0 — vel5 set is chart-only)")
    results = []; missing = []
    for date, rej, lane, trig in vetoed:
        sym = rej["ticker"]; path = os.path.join(B10, f"{date}_{sym}.json")
        if not os.path.exists(path):
            missing.append((date, sym, lane)); continue
        bars = json.load(open(path))["bars"]
        rs = hms(rej.get("time"))
        i0 = max((i for i, b in enumerate(bars) if bar_secs(b) <= rs), default=None)
        if i0 is None or i0 >= len(bars) - 2:
            missing.append((date, sym, lane)); continue
        sig_px = float(rej.get("price") or trig.get("price") or bars[i0]["close"])
        stop = trig.get("stop")
        if not stop:
            lows = [b["low"] for b in bars[max(0, i0-6):i0+1]]
            stop = min(lows) if lows else sig_px * 0.94
        stop = float(stop)
        if stop >= sig_px: stop = sig_px * 0.94
        pnl, how = sim_e3(bars, i0, sig_px, stop)
        results.append(dict(date=date, sym=sym, lane=lane, t=rej.get("time"),
                            px=sig_px, stop=stop, pnl=round(pnl, 2), exit=how,
                            reason=(rej.get("reason") or "")[:60]))
    n = len(results); tot = sum(r["pnl"] for r in results)
    print(f"\nsimulated N={n}  (no bars10s name-day: {len(missing)}: {missing})")
    for r in results:
        print(f"  {r['date']} {r['sym']:6s} {r['lane']:8s} {r['t']:>11s} px {r['px']:.4f} "
              f"stop {r['stop']:.4f} -> ${r['pnl']:+8.2f} {r['exit']:5s} | {r['reason']}")
    if n:
        wins = sum(1 for r in results if r["pnl"] > 0)
        print(f"\nTOTAL ${tot:+.2f}  $/tr ${tot/n:+.2f}  win {100*wins/n:.0f}%")
        # hand-trace the WETO row if present (dollars law)
        wt = [r for r in results if r["sym"] == "WETO"]
        if wt:
            r = wt[0]; bars = json.load(open(os.path.join(B10, f"{r['date']}_WETO.json")))["bars"]
            rs = hms(r["t"]); i0 = max(i for i, b in enumerate(bars) if bar_secs(b) <= rs)
            log = []; pnl, how = sim_e3(bars, i0, r["px"], r["stop"], log)
            print(f"\nHAND-TRACE WETO {r['date']}: entry fill {r['px']*1.01:.4f} "
                  f"({POS/(r['px']*1.01):.0f} sh = ${POS:.2f}) -> ${pnl:+.2f} ({how})")
            for m in log: print("   ", m)
    verdict = "BUILD (net positive)" if n and tot > 0 else "STOP — NET NEGATIVE (or N=0)"
    print(f"\nVERDICT: {verdict}")
    json.dump(dict(n=n, total=round(tot, 2), per_tr=round(tot/n, 2) if n else None,
                   vel5_tape_n=len(vel5_tape), results=results, missing=missing,
                   verdict=verdict),
              open(HERE + "/scalar_veto_tape_lanes_20260817_out.json", "w"), indent=1)

if __name__ == "__main__":
    main()
