#!/usr/bin/env python3
"""KILL-TEST — the dollar price of the LANE CLASSIFICATION REGISTRY's behavior delta (8/17).

WHAT CHANGES: tape-classified lanes that were missing from the chart-break gate's bypass tuple
and the extension guard's exempt tuple become EXEMPT (settled 7/24+7/26 doctrine). Newly-exempt
set = {kevseq, v2conv, grinder, bandpass, prevwap, crown_seam, halt_ladder, rocket_catcher}.

METHOD: decisions archive 6/29-8/17 (cache dir argv[1], {date, rows} per file). chart_gate_
blocked_trade / extension_reject rows carry NO lane stamp, so the lane is inferred by joining to
the nearest same-ticker row within +/-20s that carries machine/entry_type/lane or a triggered_*
status (documented limitation; the WFF/WETO/MF rows were hand-checked against the transcript).
Era 7/13+ only (line-in-the-sand). Counterfactual = E3 live-parity on data/universe/bars10s,
identical spec to scalar_veto_tape_lanes_20260817.py: $500 position, +1% entry slip, bank 1/2 at
+10% (resting limit, exact), trail rest 10%-off-run-high on CLOSES, intrabar stop FIRST (tie
against the trade), -0.5% on market exits, EOD flatten. Stop = joined trigger row's stop, else
the 60s-prior low, else entry*0.94 (6% min-stop parity).
"""
import json, os, sys, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B10 = os.path.join(ROOT, "data", "universe", "bars10s")
ARCH = sys.argv[1] if len(sys.argv) > 1 else None
assert ARCH and os.path.isdir(ARCH), "pass archive cache dir"

NEWLY_EXEMPT = {"kevseq", "v2conv", "grinder", "bandpass", "prevwap",
                "crown_seam", "halt_ladder", "rocket_catcher"}
ALL_LANES = NEWLY_EXEMPT | {"hidden_entry", "vwap_reclaim", "zone_flip", "flat_top",
                            "ma_pullback", "orb", "ignition", "dip_rip", "ema_bounce"}
GATE_ROWS = ("chart_gate_blocked_trade", "extension_reject")
POS, SLIP, MKT = 500.0, 0.01, 0.005


def hms(t):
    if not t: return None
    try:
        d = datetime.datetime.strptime(t.strip(), "%I:%M:%S %p")
        return d.hour * 3600 + d.minute * 60 + d.second
    except Exception:
        return None


def bar_secs(b):
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
    rejects = []
    for f in sorted(glob.glob(ARCH + "/*.json")):
        j = json.load(open(f)); rows = j.get("rows", []); date = j.get("date")
        if not rows or (date or "") < "2026-07-13":
            continue
        rows = [r for r in rows if r.get("recorded_at")]
        rows.sort(key=lambda r: r["recorded_at"])
        for i, r in enumerate(rows):
            if r.get("status") not in GATE_ROWS: continue
            t0 = hms(r.get("time")); tk = r.get("ticker"); lane = None; trig = {}
            if t0 is None: continue
            for j2 in range(max(0, i - 80), min(len(rows), i + 40)):
                o = rows[j2]
                if o.get("ticker") != tk: continue
                ot = hms(o.get("time"))
                if ot is None or abs(ot - t0) > 20: continue
                for fld in ("machine", "entry_type", "lane"):
                    if o.get(fld) in ALL_LANES:
                        lane = o[fld]; trig = o
                st = str(o.get("status") or "")
                if st.startswith("triggered_") and st[10:] in ALL_LANES:
                    lane = st[10:]; trig = o
            if lane in NEWLY_EXEMPT:
                rejects.append((date, r, lane, trig))
    # the archive endpoint can serve a row twice (dashboard append + replay) — dedupe on the
    # natural key so a duplicated row cannot double-count a counterfactual dollar.
    _seen = set(); _dd = []
    for d, r, lane, trig in rejects:
        k = (d, r.get("ticker"), r.get("status"), r.get("time"), lane)
        if k in _seen: continue
        _seen.add(k); _dd.append((d, r, lane, trig))
    rejects = _dd

    print(f"newly-exempt-lane gate rejects (era 7/13+) N={len(rejects)}")
    by_gate = {}
    for d, r, lane, _ in rejects:
        by_gate.setdefault(r["status"], []).append(lane)
    for g, ls in by_gate.items():
        print(f"  {g}: {len(ls)}  {sorted(set(ls))}")

    results, missing = [], []
    for date, rej, lane, trig in rejects:
        sym = rej["ticker"]; path = os.path.join(B10, f"{date}_{sym}.json")
        if not os.path.exists(path):
            missing.append((date, sym, lane, rej.get("time"))); continue
        bars = json.load(open(path))["bars"]
        rs = hms(rej.get("time"))
        i0 = max((i for i, b in enumerate(bars) if bar_secs(b) <= rs), default=None)
        if i0 is None or i0 >= len(bars) - 2:
            missing.append((date, sym, lane, rej.get("time"))); continue
        sig_px = float(rej.get("entry") or rej.get("price") or bars[i0]["close"])
        stop = trig.get("stop") or trig.get("zone_stop")
        if not stop:
            lows = [b["low"] for b in bars[max(0, i0 - 6):i0 + 1]]
            stop = min(lows) if lows else sig_px * 0.94
        stop = float(stop)
        if stop >= sig_px: stop = sig_px * 0.94
        pnl, how = sim_e3(bars, i0, sig_px, stop)
        results.append(dict(date=date, sym=sym, lane=lane, gate=rej["status"],
                            t=rej.get("time"), px=sig_px, stop=round(stop, 4),
                            pnl=round(pnl, 2), exit=how))

    n = len(results); tot = sum(r["pnl"] for r in results)
    print(f"\nsimulated N={n}  (no bars10s name-day: {len(missing)})")
    for m in missing: print(f"   MISSING {m}")
    for r in results:
        print(f"  {r['date']} {r['sym']:6s} {r['lane']:9s} {r['gate']:24s} {r['t']:>11s} "
              f"px {r['px']:.4f} stop {r['stop']:.4f} -> ${r['pnl']:+8.2f} {r['exit']}")
    if n:
        wins = sum(1 for r in results if r["pnl"] > 0)
        print(f"\nTOTAL ${tot:+.2f}  $/tr ${tot/n:+.2f}  win {100*wins/n:.0f}%  (N={n})")
    # hand-trace WFF (today's kevseq specimen)
    wf = [r for r in results if r["sym"] == "WFF"]
    if wf:
        r = wf[0]; bars = json.load(open(os.path.join(B10, f"{r['date']}_WFF.json")))["bars"]
        rs = hms(r["t"]); i0 = max(i for i, b in enumerate(bars) if bar_secs(b) <= rs)
        log = []; pnl, how = sim_e3(bars, i0, r["px"], r["stop"], log)
        print(f"\nHAND-TRACE WFF {r['date']} kevseq: signal ${r['px']:.4f} -> fill "
              f"${r['px']*1.01:.4f} ({POS/(r['px']*1.01):.0f} sh = ${POS:.2f} at risk), "
              f"stop ${r['stop']:.4f} -> ${pnl:+.2f} ({how})")
        for m in log: print("   ", m)
    verdict = ("NET POSITIVE" if n and tot > 0 else
               ("NET NEGATIVE" if n and tot < 0 else "NO EVIDENCE (N=0 simulable)"))
    print(f"\nCOUNTERFACTUAL VERDICT: {verdict}  (build proceeds either way — Marcos ordered it; "
          f"doctrine is settled. He decides whether to keep LANE_REGISTRY_EXEMPT on.)")
    json.dump(dict(n_rejects=len(rejects), n=n, total=round(tot, 2),
                   per_tr=round(tot / n, 2) if n else None, verdict=verdict,
                   results=results, missing=missing),
              open(HERE + "/lane_registry_20260817_out.json", "w"), indent=1)


if __name__ == "__main__":
    main()
