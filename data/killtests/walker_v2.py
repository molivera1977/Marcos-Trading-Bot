#!/usr/bin/env python3
"""
WALKER v2 — the shared exit walker with the GAP-THROUGH-STOP correction (8/21 night).

THE FLAW IT FIXES (found in the 8/21 accounting audit, the only defect the audit surfaced):
every walker this week returned `stop - half_spread` whenever a bar's LOW touched the stop.
But if the bar OPENS below the stop, no order fills at the stop — the realistic fill is the
bar's OPEN (still minus half the spread). Measured exposure on 91,391 bars / 60 name-days:
5.1% of bars open >=1% below the prior close, 1.6% >=2%, p99 3.67%. The old walker was
therefore mildly optimistic on LOSING exits — the direction that flatters us, which is the
direction that must never be flattered.

RULE APPLIED: fill price on a stop bar = min(stop, bar_open) - half_spread.
Same rule at the trail exit and the time flats: those exit at the bar CLOSE, which is already
a printed price, so they are unchanged. The +10% tier is a resting limit; a bar that GAPS UP
through the tier fills at max(tier, bar_open) — the same correction in our favor is NOT taken
(gap-ups through a limit fill AT the limit; only the remainder-above is real, and modelling it
would add optimism). Tier stays at the tier price. Conservative on both sides.

INTERFACE identical to the week's walkers: walk(bars, i0, entry, stop, pre, spread) ->
(pnl, notional, exit_index) with $30 risk, 70%/$1000 clamp, E3 exits, 09:25/15:45 flats.
`bal` parameterised (default 5000). SELF-TEST at import (mandated): a synthetic tape where the
stop bar gaps 2% through the stop must return the OPEN-based fill, and an identical tape
without the gap must reproduce the old walker's number exactly.
"""
import datetime as dt

RISK = 30.0


def _hm(t):
    return (dt.datetime.fromisoformat(str(t)[:19]) - dt.timedelta(hours=4)).strftime("%H:%M")


def walk(b, i0, entry, stop, pre, spr, bal=5000.0):
    px = entry + (spr / 2 if spr else entry * 0.005)
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(bal * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    half = (spr / 2 if spr else px * 0.0025)
    flat = "09:25" if pre else "15:45"
    for i in range(i0 + 1, len(b)):
        x = b[i]
        t = _hm(x["t"])
        if t >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
        if x["l"] <= stop:
            o = float(x.get("o") or x["c"])
            fill = min(stop, o)                      # GAP-THROUGH CORRECTION
            return banked + rem * ((fill - half) - px), sh * px, i
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)           # resting limit: fills AT the tier
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked, sh * px, i
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, i
    return banked + rem * ((b[-1]["c"] - half) - px), sh * px, len(b) - 1


# ── SELF-TEST (runs at import; import fails loudly if the correction is wrong) ──
def _selftest():
    def bar(t, o, h, l, c):
        return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": 1000}
    base = "2026-08-20T14:0{m}:00"   # 10:0x ET
    # tape A: stop 9.00, bar 2 LOW touches 8.99 but OPENS 9.10 -> old behaviour, fill at stop
    A = [bar(base.format(m=0), 10, 10, 10, 10),
         bar(base.format(m=1), 10, 10.1, 9.9, 10),
         bar(base.format(m=2), 9.10, 9.2, 8.99, 9.05)]
    # tape B: identical except bar 2 OPENS 8.82 (gapped 2% through the stop)
    B = [bar(base.format(m=0), 10, 10, 10, 10),
         bar(base.format(m=1), 10, 10.1, 9.9, 10),
         bar(base.format(m=2), 8.82, 9.2, 8.80, 9.05)]
    pa = walk(A, 0, 10.0, 9.0, False, 0.02)
    pb = walk(B, 0, 10.0, 9.0, False, 0.02)
    assert pa and pb, "selftest walks failed"
    sh = pa[1] / (10.0 + 0.01)
    # A fills at the stop (9.00 - half); B must fill at the OPEN (8.82 - half): worse by 0.18/sh
    diff = pa[0] - pb[0]
    exp = round(sh * (9.00 - 8.82), 2)
    assert abs(round(diff, 2) - exp) < 0.02, f"gap correction wrong: diff {diff:.2f} vs expected {exp:.2f}"
    # and A must equal the OLD walker's number exactly (no-gap case unchanged)
    old_fill_pnl = pa[1] / (10.0 + 0.01) * ((9.00 - 0.01) - (10.0 + 0.01))
    assert abs(pa[0] - old_fill_pnl) < 0.01, "no-gap case drifted from the old walker"
    return True


SELFTEST_OK = _selftest()
if __name__ == "__main__":
    print("walker_v2 selftest OK — gap-through-stop fills at min(stop, open); no-gap unchanged")
