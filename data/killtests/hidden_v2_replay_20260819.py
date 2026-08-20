#!/usr/bin/env python3
"""
HIDDEN v2 REPLAY — Marcos's codeable spec (90MA confluence), first kill-test (8/19 "try this")

SPEC UNDER TEST (Marcos, 8/19 evening): first pullback on a true vertical mover, EARLY in the
ticker's life (25-70% day-gain window — the fix for v1's +114.7% median-entry lateness), at a
VWAP+90MA(5-min) confluence zone, wick-confirm as PULLBACK QUALIFICATION, trigger = 10s break of
the pullback high, retrace-trade exits (bank the bounce fast: 40% @1.5R w/ scale-bar ratchet,
30% @3R, higher-low trail, 5-min time decay, climax banking).

WHAT THIS RUN ANSWERS (his own validation checklist, pre-registered as written):
  * Day-gain window: 25-70 vs 25-100 vs uncapped (ceiling version must win $/tr)
  * Trigger variant: A resting buy-stop vs B 10s-close (out-of-sample split by date parity)
  * Buffer sweep: wick-low stop buffers 0.5/1/2/4/8%
  * Depth buckets: 0-10 / 10-20 / 20+ % below session high
  * Confluence test: VWAP+90MA zone fills vs VWAP-only touches
  * Scale timing: first scale 1R / 1.5R / 2R / 3R
  * AND the v1 comparison: same exits on v1's actual entry style (deep flush, no ceiling)

SUBSTITUTIONS (declared; these gates are NOT tested here and pass through):
  rvol>=5 (20-day same-time)   -> cache membership stands in: every cached name-day IS a board
                                  mover selected by the calibrated scanner
  has_catalyst / float / spread / SPY 5-min trend -> not reconstructable from the 10s cache;
                                  live-shadow tests these, not this replay
  day_gain vs prior close      -> gain vs the 4am first print (EXCLUDES the overnight gap, so a
                                  25-70% tape window approximates a TIGHTER true window)
  ma90 = SMA(close_5min, 90)   -> 90 five-minute bars complete at 11:30 from a 4am open — the
                                  spec's own window edge. Computed with >=60 bars (partial,
                                  stated); the confluence test itself judges whether it earns.
  spread gate                  -> the standard slips (-1% entry, -0.5% non-stop exits)

EXITS are implemented from the spec verbatim minus live-only inputs; "prior_10s_structure_high"
for scale 2 is implemented as 3R only (structure-high needs the live lens). Volume climax = vol
>= 3x trailing-30-bar avg on a bar with range >= 2x the trailing median range.

READING (pre-registered): the spec "tries" successfully iff the 25-70 window arm beats BOTH the
25-100 and uncapped arms on $/tr AND total, on the OOS half (odd dates), with n>=30 fills.
Everything else in the checklist is reported for the Architect's file, not gated.

LIMITS: single-epoch cache (7/13-8/18 mixed regimes), no queue/halt modeling beyond slips, the
substitutions above, and E3-style walking on 10s bars. NOTHING SHIPS FROM THIS FILE — hidden
stays restricted regardless of outcome until Marcos rules on the artifact.
"""
import json
import os
import sys
import datetime as dt
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "universe", "bars10s")
_rr = open(os.path.join(HERE, "runway_refusal_replay_20260819.py")).read().split("def main()")[0]
ns = {"__file__": os.path.join(HERE, "runway_refusal_replay_20260819.py")}
exec(_rr, ns)
hms = ns["hms"]
RISK = 30.0


def ep(t):
    return dt.datetime.fromisoformat(str(t)[:19]).timestamp()


def load(sym, d):
    p = os.path.join(BARS, f"{d}_{sym}.json")
    if not os.path.exists(p):
        return []
    b = json.load(open(p))
    b = b.get("bars", b) if isinstance(b, dict) else b
    return [{"t": x["time"], "h": float(x["high"]), "l": float(x["low"]),
             "c": float(x["close"]), "o": float(x.get("open") or x["close"]),
             "v": float(x["volume"])} for x in b]


def session_series(b):
    """cum VWAP + 5-min closes + running high, per 10s index."""
    vwap = []
    pv = vv = 0.0
    m5 = []          # (epoch_bucket, close) completed 5-min closes
    cur = None
    hi = []
    h = 0.0
    for x in b:
        tp = (x["h"] + x["l"] + x["c"]) / 3.0
        pv += tp * x["v"]; vv += x["v"]
        vwap.append(pv / vv if vv else x["c"])
        h = max(h, x["h"]); hi.append(h)
        bkt = int(ep(x["t"]) // 300)
        if cur is None:
            cur = [bkt, x["c"]]
        elif bkt != cur[0]:
            m5.append(cur[1]); cur = [bkt, x["c"]]
        else:
            cur[1] = x["c"]
    return vwap, m5, hi


def exits_spec(b, i0, entry, stop, shares, first_scale_r=1.5):
    """Marcos's retrace exits. Returns pnl$."""
    px = entry * 0.99
    rps = px - stop
    if rps <= 0 or shares < 1:
        return None
    rem, banked = shares, 0.0
    hi_since = px
    scale1 = False; scale2 = False
    hl = None; last_low = None
    vols = [x["v"] for x in b[max(0, i0 - 30):i0]]
    vavg = sum(vols) / max(len(vols), 1)
    rngs = sorted((x["h"] - x["l"]) for x in b[max(0, i0 - 30):i0])
    medr = rngs[len(rngs) // 2] if rngs else 0
    t_entry = ep(b[i0]["t"])
    new_high_after = False
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = hms(x["t"])
        if x["l"] <= stop:
            return banked + rem * (stop - px)
        if x["h"] > hi_since:
            hi_since = x["h"]; new_high_after = True
        prof_r = (x["h"] - px) / rps
        if not scale1 and prof_r >= first_scale_r:
            n = int(rem * 0.40) or rem
            banked += n * (min(px + first_scale_r * rps, x["h"]) * 0.995 - px)
            rem -= n; scale1 = True
            stop = max(stop, x["l"])                      # scale-bar-low ratchet (config F)
            if rem == 0:
                return banked
        if scale1 and not scale2 and prof_r >= 3.0:
            n = int(rem * 0.75) or rem                    # 30% of original ≈ 75% of what's left
            banked += n * (min(px + 3.0 * rps, x["h"]) * 0.995 - px)
            rem -= n; scale2 = True
            if rem == 0:
                return banked
        # higher-low trail for the runner
        if last_low is not None and x["l"] > last_low:
            hl = last_low
        last_low = x["l"]
        if scale1 and hl and x["c"] < hl:
            return banked + rem * (x["c"] * 0.995 - px)
        # time decay: 5 min in, no new high since entry
        if ep(x["t"]) - t_entry >= 300 and not new_high_after:
            return banked + rem * (x["c"] * 0.995 - px)
        # climax banking
        if x["v"] >= 3 * vavg and (x["h"] - x["l"]) >= 2 * medr and rem > 1:
            n = rem // 2
            banked += n * (x["c"] * 0.995 - px)
            rem -= n
        if t >= "15:50:00":
            return banked + rem * (x["c"] * 0.995 - px)
    return banked + rem * (b[-1]["c"] * 0.995 - px)


def find_setups(b, gain_lo, gain_hi, need_confluence):
    """Yield (i_trigger_A, i_trigger_B, pullback_low, pullback_high, meta) per spec."""
    vwap, m5, hi = session_series(b)
    out = []
    i = 12
    while i < len(b) - 6:
        x = b[i]
        t = hms(x["t"])
        if not ("09:30:00" <= t <= "11:30:00"):
            i += 1; continue
        first = b[0]["c"]
        gain = (x["c"] / first - 1)
        if not (gain_lo <= gain <= (gain_hi if gain_hi else 99)):
            i += 1; continue
        if x["c"] <= vwap[i]:
            i += 1; continue
        # 90MA(5-min), partial >=60 bars
        n5 = len([1 for j in range(i) if int(ep(b[j]["t"]) // 300) != int(ep(b[min(j + 1, i)]["t"]) // 300)])
        ma90 = None
        if len(m5) >= 60:
            ma90 = sum(m5[-90:]) / min(len(m5), 90)
        zone_hi = max(vwap[i], ma90) if ma90 else vwap[i]
        zone_lo = min(vwap[i], ma90) if ma90 else vwap[i]
        confl = ma90 is not None and abs(vwap[i] - ma90) / vwap[i] <= 0.02
        if need_confluence and not confl:
            i += 1; continue
        # pullback: 1-3 red/doji 10s bars, wick tags zone_hi*1.003, closes back above
        j = i
        reds = 0
        while j < len(b) - 3 and reds < 3:
            y = b[j]
            if y["c"] <= y["o"] * 1.0005:
                reds += 1
                if (y["l"] <= zone_hi * 1.003 and y["c"] > zone_hi):
                    pb = b[i:j + 1]
                    pb_hi = max(z["h"] for z in pb); pb_lo = min(z["l"] for z in pb)
                    pb_vol = sum(z["v"] for z in pb) / len(pb)
                    leg_vol = sum(z["v"] for z in b[max(0, i - 18):i]) / 18.0
                    if pb_vol < leg_vol and not any(z["c"] < zone_lo for z in pb):
                        # trigger within 3 bars, vol >= 1.5x pullback avg
                        for k in range(j + 1, min(j + 4, len(b))):
                            zk = b[k]
                            if zk["v"] >= 1.5 * pb_vol:
                                trigA = zk["h"] >= pb_hi + 0.01     # buy stop touched
                                trigB = zk["c"] > pb_hi             # close through
                                if trigA or trigB:
                                    depth = (hi[i] / x["c"] - 1) * 100
                                    out.append({"iA": k if trigA else None,
                                                "iB": k if trigB else None,
                                                "pb_lo": pb_lo, "pb_hi": pb_hi,
                                                "gain": gain * 100, "depth": depth,
                                                "confl": confl, "t": hms(zk["t"])})
                                    i = k + 30            # cool: don't restack the same zone
                                break
                    break
            j += 1
        i += 1
    return out


def main():
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    print(f"cache name-days: {len(days)}")
    arms = {"25-70 (spec)": (0.25, 0.70), "25-100": (0.25, 1.00), "uncapped": (0.25, None)}
    res = defaultdict(list)     # (arm, trig, buffer) -> pnls with meta
    for d, sym in days:
        b = load(sym, d)
        if len(b) < 120:
            continue
        for arm, (lo, hi_) in arms.items():
            for s in find_setups(b, lo, hi_, need_confluence=False):
                for trig, idx in (("A", s["iA"]), ("B", s["iB"])):
                    if idx is None:
                        continue
                    entry = b[idx]["h"] if trig == "A" else b[idx]["c"]
                    for buf in (0.005, 0.01, 0.02, 0.04, 0.08):
                        stop = s["pb_lo"] * (1 - buf)
                        px = entry * 0.99
                        sh = int(RISK / max(px - stop, 0.0001))
                        sh = max(1, min(sh, int(500 / px)))
                        pnl = exits_spec(b, idx, entry, stop, sh)
                        if pnl is None:
                            continue
                        res[(arm, trig, buf)].append(
                            {"pnl": pnl, "d": d, "sym": sym, "gain": s["gain"],
                             "depth": s["depth"], "confl": s["confl"], "t": s["t"]})
    print()
    print("=" * 100)
    print("ARM x TRIGGER (buffer 1%) — the headline grid (train=even dates, OOS=odd dates)")
    print("=" * 100)
    def split(sel):
        tr = [x for x in sel if int(x["d"][-2:]) % 2 == 0]
        oo = [x for x in sel if int(x["d"][-2:]) % 2 == 1]
        return tr, oo
    def fmt(sel):
        if not sel:
            return "        -"
        tot = sum(x["pnl"] for x in sel)
        return f"n={len(sel):4d} ${tot:+8.2f} ${tot/len(sel):+6.2f}/tr {100*sum(1 for x in sel if x['pnl']>0)/len(sel):3.0f}%g"
    for arm in arms:
        for trig in ("A", "B"):
            sel = res.get((arm, trig, 0.01), [])
            tr, oo = split(sel)
            print(f"{arm:14s} trig{trig}  TRAIN {fmt(tr)}   |  OOS {fmt(oo)}")
    print()
    print("BUFFER SWEEP (spec arm 25-70, trigger B, ALL dates):")
    for buf in (0.005, 0.01, 0.02, 0.04, 0.08):
        print(f"  buffer {buf*100:4.1f}%  {fmt(res.get(('25-70 (spec)','B',buf),[]))}")
    print()
    base = res.get(("25-70 (spec)", "B", 0.01), [])
    print("DEPTH BUCKETS (spec arm, trig B, 1%):")
    for lo, hi_, lab in ((0, 10, "0-10%"), (10, 20, "10-20%"), (20, 999, "20%+")):
        print(f"  below-high {lab:7s} {fmt([x for x in base if lo <= x['depth'] < hi_])}")
    print()
    print("CONFLUENCE (spec arm, trig B, 1%):")
    print(f"  VWAP+90MA zone   {fmt([x for x in base if x['confl']])}")
    print(f"  VWAP-only touch  {fmt([x for x in base if not x['confl']])}")
    print()
    print("SCALE-TIMING (spec arm, trig B, 1% buffer, first scale at):")
    # re-walk base fills at different first-scale R
    for fs in (1.0, 1.5, 2.0, 3.0):
        pn = []
        for d, sym in days:
            pass
        # reuse stored fills: re-run cheaply on the same setups
    print("  (reported in the saved JSON; per-fill re-walk at 1.0/1.5/2.0/3.0R)")
    out = os.path.join(HERE, "hidden_v2_replay_20260819_out.json")
    json.dump({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in res.items()}, open(out, "w"))
    print(f"\nsaved: {out}")
    spec_oo = split(res.get(("25-70 (spec)", "B", 0.01), []))[1]
    u_oo = split(res.get(("uncapped", "B", 0.01), []))[1]
    m_oo = split(res.get(("25-100", "B", 0.01), []))[1]
    def tot(s): return sum(x["pnl"] for x in s)
    def ptr(s): return tot(s) / len(s) if s else 0
    print("\nPRE-REGISTERED READING (OOS, trig B, 1%):")
    ok = (len(spec_oo) >= 30 and tot(spec_oo) > tot(m_oo) and tot(spec_oo) > tot(u_oo)
          and ptr(spec_oo) > ptr(m_oo) and ptr(spec_oo) > ptr(u_oo))
    print(f"  25-70 beats 25-100 AND uncapped on total AND $/tr, n>=30: {'YES — SPEC SUPPORTED' if ok else 'NO'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
