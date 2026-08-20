#!/usr/bin/env python3
"""
MA_PULLBACK PRE AUDITION DRIVER (8/19 night, Marcos: "do the driver for pullback")

The one pre incumbent the roster audition could not score: ma_pullback v2 is a two-timeframe
lane (3-min flag ARM -> 1-min break FIRE) with its own driver requirement — the generic
harness replay() feeds 10s slices and would be silently wrong (its own LANES guard says so).

THIS DRIVER mirrors the live call site (marcos_trading_bot.py ~:11543) minute by minute:
  completed_m3 = fully-closed 3-min bars (aggregate_bars over closed 1-min bars)
  m1_closes    = closes of the fully-closed 1-min bars
  setup        = detect_ma_pullback(completed_m3, price, None)
  fire         = ma_pullback_v2_step(sym, setup, completed_m3, m1_closes, price, vwap,
                                     session_hi, now_m)   -- the bot's own functions, lifted.
Cadence = 1 minute (the live rescan). Exits = house E3 with the 09:25 flatten, slips -1%/-0.5%.
Fires counted 07:00-09:20 ET. Cache times are UTC -> converted (Addendum 6 class-fix).

DECLARED SUBSTITUTIONS (each removes a REFUSAL, never adds a signal):
  - _marked_runway patched to (999, None): no historical level maps exist, and unpatched the
    internal runway gate fails CLOSED on every fire (the CELZ class). Live, the gate only
    removes fires from this pool.
  - warmup seed None: premarket 3-min history starts at 04:00 ET (~60 bars by 07:00), so the
    90MA is unavailable early — same as live on a fresh name.
Pre-registered reading: deserves pre iff OOS (odd dates) $/tr > 0 with n>=30, and the TRAIN
half must agree in sign (the prevwap lesson). Nothing ships from this file.
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

N = H.ns()
step = H.fn("ma_pullback_v2_step")
detect = H.fn("detect_ma_pullback")
agg = H.fn("aggregate_bars")
bclose = H.fn("_bar_close")
N["_marked_runway"] = lambda sym, px, stop: (999.0, None)   # DECLARED: runway gate not modeled


def et_hms(k):
    return dt.datetime.fromtimestamp(k, dt.timezone.utc).strftime("%H:%M:%S")  # placeholder


def walk_e3(b10, i0, entry, stop, ethms):
    px = entry * 0.99
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(500 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for i in range(i0 + 1, len(b10)):
        k, o, h, l, c, v = b10[i]
        if ethms(k) >= "09:25:00":
            return banked + rem * (c * 0.995 - px)
        if l <= stop:
            return banked + rem * (stop - px)
        runhi = max(runhi, h)
        if not tiered and h >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 * 0.995 - px)
            rem -= n; tiered = True; stop = px
            if rem == 0:
                return banked
        if tiered and c <= runhi * 0.90:
            return banked + rem * (c * 0.995 - px)
    return banked + rem * (b10[-1][4] * 0.995 - px)


def main(limit=None):
    days = sorted({(f[:10], f[11:-5]) for f in os.listdir(BARS) if f.endswith(".json")})
    if limit:
        days = days[:limit]
    fills = []
    scanned = 0
    for d, sym in days:
        raw = json.load(open(os.path.join(BARS, f"{d}_{sym}.json")))
        raw = raw.get("bars", raw) if isinstance(raw, dict) else raw
        if len(raw) < 150:
            continue
        B = H.norm_bars(raw, day=d)

        def ethms(k):
            return (dt.datetime.utcfromtimestamp(k) - dt.timedelta(hours=4)).strftime("%H:%M:%S")

        if sum(1 for x in B if ethms(x[0]) < "09:30:00") < 60:
            continue                                        # needs real premarket tape
        scanned += 1
        m1 = H.bars10s_to_m1(B)

        def m1_epoch(bar):
            return int(dt.datetime.fromisoformat(bar["time"][:19]).replace(
                tzinfo=dt.timezone.utc).timestamp())

        # running vwap + session-high per 10s index
        vw = H.running_vwap(raw, day=d)
        # per-day detector state reset (the step keys its arm store on sym)
        for st_name in ("_mapb_arm",):
            if st_name in N and isinstance(N[st_name], dict):
                N[st_name].clear()
        hi = 0.0
        j10 = 0                                             # walking 10s cursor
        fired_ix = set()
        # minute loop across the pre window
        t0 = B[0][0]
        for k_min in range(t0 - t0 % 60 + 60, B[-1][0], 60):
            hm = ethms(k_min)[:5]
            if hm < "07:00":
                continue
            if hm > "09:20":
                break
            while j10 < len(B) and B[j10][0] + 10 <= k_min:
                hi = max(hi, B[j10][2])
                j10 += 1
            if j10 == 0:
                continue
            i_last = j10 - 1
            price = B[i_last][4]
            vwap = vw[i_last]
            if not (price and vwap and price > vwap):        # live gate: above VWAP only
                continue
            closed_m1 = [b for b in m1 if m1_epoch(b) + 60 <= k_min]
            if len(closed_m1) < 12:
                continue
            m3 = agg(closed_m1, 3)
            closed_m3 = [b for b in m3 if m1_epoch(b) + 180 <= k_min]
            if len(closed_m3) < 5:
                continue
            m1_closes = [bclose(b) for b in closed_m1]
            et_now = dt.datetime.utcfromtimestamp(k_min) - dt.timedelta(hours=4)
            now_m = et_now.hour * 60 + et_now.minute
            try:
                setup = detect(closed_m3, price, None)
                r = step(sym, setup, closed_m3, m1_closes, price, vwap, hi, now_m)
            except Exception as e:
                print(f"  !! {d} {sym} {hm}: {type(e).__name__} {e}", file=sys.stderr)
                break
            if r and r.get("fire") and i_last not in fired_ix:
                fired_ix.add(i_last)
                stop = float(r["stop"])
                pnl = walk_e3(B, i_last, float(r["px"]), stop, ethms)
                if pnl is not None:
                    fills.append({"d": d, "sym": sym, "t": ethms(B[i_last][0]),
                                  "pnl": round(pnl, 2),
                                  "w": round((r["px"] * 0.99 - stop) / (r["px"] * 0.99) * 100, 2)})
    print(f"name-days with usable pre tape: {scanned}\n")

    def rep(lab, sel):
        v = [f["pnl"] for f in sel]
        if not v:
            print(f"  {lab:22s} none")
            return
        print(f"  {lab:22s} n={len(v):4d}  ${sum(v):+9.2f}  ${sum(v)/len(v):+6.2f}/tr  "
              f"green {100*sum(1 for x in v if x > 0)/len(v):.0f}%")
    print("MA_PULLBACK v2 in PRE (07:00-09:20 fires, E3 + 09:25 flatten):")
    rep("TRAIN (even dates)", [f for f in fills if int(f["d"][-2:]) % 2 == 0])
    rep("OOS   (odd dates)", [f for f in fills if int(f["d"][-2:]) % 2 == 1])
    json.dump(fills, open(os.path.join(HERE, "mapb_pre_audition_20260819_out.json"), "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else None))
