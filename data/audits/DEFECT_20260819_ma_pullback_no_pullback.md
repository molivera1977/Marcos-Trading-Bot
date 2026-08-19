# OPEN DEFECT — ma_pullback fires on a VERTICAL EXPANSION BAR with no pullback at all

Opened after Marcos looked at the CDTG 1-min chart and asked: **"where is the pullback?"**
There isn't one. This documents the mechanism, with tape.

## THE TRADE

CDTG 2026-08-18 14:16:43, `entry_type=ma_pullback`, 12sh @ **$7.78**, stop $5.38, exit $5.55
15:15:01, **−$26.76**. Stamped at entry: `vs VWAP above`, **`VWAP dist % 66.53`**,
`SIDE front_side`, `map break 7.78`, **`break dist % 0`** (the map's break level WAS the fill),
`entry_ema9 5.5678`, `entry_vs_ema90_pct 94.29`.

## THERE WAS NO PULLBACK (1-min bars, harvested SIP tape)

```
  time    open   low   high  close  dir
  14:05   5.00   4.95  5.20  5.19   UP
  14:07   5.28   5.20  5.29  5.26   DOWN   <- last down-close before the fill
  14:10   5.52   5.25  5.63  5.50   DOWN   <- and this one, 6 min / $2.28 earlier
  14:12   5.58   5.43  6.09  5.96   UP
  14:13   5.96   5.95  6.85  6.79   UP
  14:14   6.80   6.62  7.38  7.35   UP
  14:15   7.36   6.75  7.78  7.78   UP
  14:16   7.78   7.78  7.78  7.78   UP     <- filled here
```
**+57% from 14:05 to the fill with no retrace.**

## THE MECHANISM

`_detect_ma_pullback`'s held-MA test is:

```python
if clo <= ma * (1 + MA_PULLBACK_TOUCH_TOL) and ccl > ma and rising:
```

`clo` = the candle's LOW, `ccl` = its CLOSE. **There is no ceiling on how far above the MA the
close may finish.** The 3-min confirmation bar 14:12–14:15 was:

```
  open 5.58   LOW 5.43   high 7.38   CLOSE 7.35     range +36%
  test: LOW <= ema9 x 1.005 = 5.5956  ->  5.43  PASSES
        CLOSE > ema9 = 5.5678         ->  7.35  PASSES
  close sits 40% ABOVE the MA it supposedly "pulled back to"
```

**The "dip to the MA" and the "reclaim above it" are the bottom and top of ONE vertical candle,
36% apart.** The rule never asks how price travelled between them, nor how far the close ended
from the MA.

Every other guard points the same way instead of catching it:
* "buyers must return" (volume > prior 3-bar avg) — a parabolic bar passes trivially
* `price <= ccl` rejects, i.e. "must be continuing UP" — a vertical passes trivially
* "bottoming wick OR green reclaim" — broadened 7/2 from wick-only; a huge green bar passes on
  the green branch alone

Every safeguard written to confirm *"a buyer stepped in after a weak pullback"* is satisfied MORE
easily by a violent expansion than by the setup it was written for.

## THE DOC I WROTE WAS WRONG TOO

The lane sheet given to Marcos says *"dips to a rising moving average and holds it"* and grades it
**"era +$160.82, 70.6% win"**. Checked against the live book this turn (era 7/13+):

```
  ACTUAL: n=27  total +$460.95  win 55.6%
  DOC:              +$160.82        70.6%
```
70.6% implies n=17, so the doc is a stale early-August snapshot presented undated. And the real
total is concentration-driven: 8/04 **+$291.41** and 7/30 **+$222.90** carry it; strip the single
best trade and it is **+$169.54**, with 8 of 16 traded days negative.

## STATUS

**OPEN. Nothing fixed. The lane is live and armed.**

The fix's SHAPE is obvious — require price to be within some band of the held MA at entry, i.e.
an extension ceiling. The NUMBER is not: `detect_ma_pullback` only became liftable on 8/18 (rig
gate 17) and its fire path is still unexercised — a smoke test produced ZERO fires over 40
name-days, which is the signature of a bad harness call, not proof of selectivity. No threshold
may be proposed until the driver demonstrably reproduces known live fires.

Related and also open: the CDTG double-fill (ma_pullback + kevseq, same second, same name) is a
separate defect — see DEFECT_20260818_cdtg_double_fill.md.
