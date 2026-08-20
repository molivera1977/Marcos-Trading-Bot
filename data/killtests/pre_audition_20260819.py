#!/usr/bin/env python3
"""
THE PRE AUDITION (8/19 night, Marcos: "lets answer the question, what deserves to run in pre?
Pre has always sucked.")

The book's answer since 7/13 (closed PRE trades, /api/trades): vwap_reclaim -$648.24 n=15,
hidden_entry -$35.00 n=25, v2conv -$13.29 n=1 — NOT ONE lane positive. (Limits: classified by
record time; includes the pre-8/10 blackout era.) This file is the forward-looking half:
every replayable pre candidate driven by the BOT'S OWN detector (live_harness.replay, 60s
live cadence) over the premarket bars of the 10s SIP cache, fires 07:00-09:20, exits = house
E3 (bank 1/2 @+10% -> BE -> 10%-off-run-high trail) with the 09:25 FLATTEN, slips -1%/-0.5%.

Candidates: prevwap (bandpass_step 07:00-09:25) · v2 (v2_pullback_step) · ignition10s ·
reclaim (kev_reclaim_step). hidden_v2 already auditioned separately tonight (OOS +$1.05/tr
all-fills, -$1.47/tr post-min-stop -> REFUSED pre).

Pre-registered reading: a lane deserves pre iff OOS (odd dates) $/tr > 0 with n>=30.
LIMITS: no queue/halt modeling; v2 quiet-tape gate not applied (live V2_QUIET_ONLY=1 refines
this set); ignition's non-detector gates (kev gate, rvol10d, ammo) not applied — this measures
the SIGNAL, the gates only remove fires. Nothing ships from this file.
"""
import importlib.util
import json
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "live_harness.py"))
H = importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
RISK = 30.0
LANES = ["prevwap", "v2", "ignition10s", "reclaim"]


def hmss(t):
    """cache stamps are UTC Z -> ET (EDT, all study dates are May-Aug 2026). The first run of
    this file compared UTC strings to ET windows and returned prevwap=0 on a lane that fired
    live 8/17 (WETO) — the positive control that exposed the class. VOID before this line."""
    import datetime as _dt
    return (_dt.datetime.fromisoformat(str(t)[:19]) - _dt.timedelta(hours=4)).strftime("%H:%M:%S")


def walk_e3(b, i0, entry, stop):
    """House E3 with the 09:25 premarket flatten."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for i in range(i0 + 1, len(b)):
        x = b[i]
        if hmss(x["t"]) >= "09:25:00":
            return banked + rem * (x["c"] * 0.995 - px)
        if x["l"] <= stop:
            return banked + rem * (stop - px)
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n; tiered = True; stop = px
            if rem == 0:
                return banked
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * (x["c"] * 0.995 - px)
    return banked + rem * (b[-1]["c"] * 0.995 - px)


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    fills = {ln: [] for ln in LANES}
    scanned = pre_days = 0
    for d, sym in days:
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        b = [{"t": x["time"], "o": float(x.get("open") or x["close"]), "h": float(x["high"]),
              "l": float(x["low"]), "c": float(x["close"]), "v": float(x["volume"])} for x in raw]
        pre_ix = [i for i, x in enumerate(b) if hmss(x["t"]) < "09:30:00"]
        if len(pre_ix) < 30:
            continue                                   # no premarket tape on this name-day
        pre_days += 1
        scanned += 1
        vw = H.running_vwap(raw, day=d)     # every lane gets the REAL session line — a None
        for ln in LANES:                    # provider silently disarms vwap gates (refused)
            try:
                fires = H.replay(sym, raw, [ln], day=d, batch_secs=60,
                                 vwap_provider=lambda s, i, bar, lane: vw[i],
                                 ctx_provider=lambda s, i, bar, lane: {})
            except H.HarnessError as e:
                print(f"  !! {ln} {d} {sym}: {e}", file=sys.stderr)
                continue
            for f in fires:
                i = f.get("i")
                if i is None or not ("07:00:00" <= hmss(b[i]["t"]) <= "09:20:00"):
                    continue
                stop = (f.get("stop") or f.get("would_stop")
                        or (f.get("px") or b[i]["c"]) * 0.94)
                stop_src = ("detector" if (f.get("stop") or f.get("would_stop"))
                            else "ASSUMED_6PCT")
                px = f.get("px") or b[i]["c"]
                r = walk_e3(b, i, px, float(stop))
                if r is not None:
                    fills[ln].append({"d": d, "sym": sym, "t": hmss(b[i]["t"]),
                                      "pnl": round(r, 2), "stop_src": stop_src})
    print(f"name-days scanned {scanned}, with premarket tape {pre_days}\n")
    print(f"{'lane':12s} {'split':6s} {'n':>5s} {'total':>10s} {'$/tr':>8s} {'green':>6s}")
    verdicts = {}
    for ln in LANES:
        rows = fills[ln]
        assumed = sum(1 for r in rows if r["stop_src"] == "ASSUMED_6PCT")
        for lab, sel in (("TRAIN", [r for r in rows if int(r["d"][-2:]) % 2 == 0]),
                         ("OOS", [r for r in rows if int(r["d"][-2:]) % 2 == 1])):
            v = [r["pnl"] for r in sel]
            if not v:
                print(f"{ln:12s} {lab:6s} {0:5d}")
                continue
            print(f"{ln:12s} {lab:6s} {len(v):5d} {sum(v):+10.2f} {sum(v)/len(v):+8.2f} "
                  f"{100*sum(1 for x in v if x > 0)/len(v):5.0f}%")
            if lab == "OOS":
                verdicts[ln] = (len(v) >= 30 and sum(v) / len(v) > 0, len(v), sum(v) / len(v))
        if assumed:
            print(f"{'':12s} [{assumed}/{len(rows)} fills carry an ASSUMED 6% stop — "
                  f"their rows are weaker evidence]")
    print("\nPRE-REGISTERED VERDICTS (deserves pre iff OOS $/tr > 0 with n>=30):")
    for ln, (ok, n, ppt) in verdicts.items():
        print(f"  {ln:12s} {'DESERVES PRE' if ok else 'NO'}  (OOS n={n}, ${ppt:+.2f}/tr)")
    json.dump(fills, open(os.path.join(HERE, "pre_audition_20260819_out.json"), "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
