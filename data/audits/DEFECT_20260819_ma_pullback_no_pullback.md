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


## STUDY RESULT (8/19) — NO SEPARATOR, AND THE TRIGGER IS NOT THE EDGE

`ma_pullback_separator_20260819.py`, 5,051 fires over 64 dates, driver self-test enforced.
Six candidate separators, each split at its median, train vs hold-out:

```
  separator        median | TRAIN low  TRAIN high     d | HO low   HO high      d   verdict
  ext_ma_pct         2.79 |    2.11      0.14     -1.96 |  -2.58    -4.80    -2.22   -
  conf_range_pct     3.63 |    2.88     -0.63     -3.51 |  -3.11    -4.28    -1.17   -
  vwap_dist_pct      2.85 |   -4.60      6.86     11.46 |  -7.17    -0.21     6.96   -
  run_15m_pct        3.03 |   -0.72      2.97      3.68 |  -1.95    -5.44    -3.48   -
  bars_since_dn      1.00 |    0.23      2.68      2.45 |  -3.48    -4.03    -0.55   -
  lowclose_pct       2.53 |    1.74      0.51     -1.23 |  -3.56    -3.83    -0.27   -
```

**NONE clears the pre-registered bar** (hold-out |d| >= $8/tr AND same sign as train).

* `ext_ma_pct` IS consistent in sign (more extended = worse, both halves) but only **-$2.22/tr**
  on hold-out — a quarter of the bar. Refusing half the lane's fires to capture $2/trade.
  **THE EXTENSION CEILING IS REFUTED AS STATED.** Marcos's PFSA counterexample (+18% above the
  9-EMA, WON $48.76, vs CDTG +40%, LOST $26.76) was the RULE, not an exception.
* `vwap_dist_pct` is the LARGEST effect and points the WRONG WAY: further above VWAP graded
  BETTER (+$6.96/tr hold-out, same sign as train). It argues against the extension theory.

### THE REAL FINDING: THE TRIGGER HAS NO EDGE; THE FUNNEL DOES

```
  detector only, full sample   n=5051   -$4,287.43   -$0.85/tr   win 36%
  detector only, hold-out      n=2069   -$7,640.18   -$3.69/tr   win 32%
  LIVE lane, funnel applied    n=  27   +$  460.95  +$17.07/tr   win 56%
```

The raw detector LOSES money. The live lane MAKES money. The funnel (PULLBACK_FIRST, the
`price > vwap` precondition, chart gate, day-gain, momentum, slots, capital, MA_PULLBACK_DEDUPE)
cuts 5,051 fires to 27 — **0.5%** — and flips the sign.

**So no separator appeared because there is no edge inside the trigger to sharpen.** An extension
ceiling would tune the wrong object.

NOT A CONTROLLED COMPARISON, stated: the detector set spans 5/18-8/18 (includes pre-era dates)
while the live book is 7/13+; the detector set contains fires the funnel would never see (session,
board membership); live n=27 is thin. The DIRECTION is supported — 0.5% selection with a sign
flip — not a precise attribution of the funnel's value.

### WHAT THE DEFECT NOW MEANS

CDTG buying $7.78 with no pullback is still real and still ugly, but it is a **FUNNEL failure,
not a trigger failure**. The open question is why the chart gate, day-gain and momentum checks
passed a name 66% above VWAP on a vertical expansion bar — not what number to cap extension at.
**No trigger change is proposed.**


## THE ANSWER CAME FROM MARCOS, NOT THE DATA (8/19, ~01:30)

After the separator study found nothing, Marcos stated the setup's DEFINITION — each condition
BEFORE it was measured, which is hypothesis-then-test, not data mining:

  1. *"a stock going up but having a momentary price collapse with low volume ... it NEEDS to be
     above VWAP"*
  2. *"the pullback itself needs low volume. if the pullback is high volume then that means the
     price is going down further"*
  3. *"we also need room to run. There has to be runway for the price to bounce back up"*
  4. *"this has to be done frontside"*

EACH TESTED IN TURN (hold-out, 19 unseen dates, driver self-test enforced):

**1. Above VWAP** — the single largest effect found all night:
```
    price ABOVE vwap   n=1432   -$1.26/tr   36% win   58% green
    price below vwap   n= 637   -$9.16/tr   25% win   15% green
```
Below VWAP loses 7x more per trade and is green on 15% of days vs 58%. Not a pullback — a collapse.

**2. Quiet dip** — monotonic in BOTH directions, exactly as stated:
```
    dip vol <= 0.20x advance   n=117   +$3.51/tr   75% green
    dip vol <= 0.79x           n=609   -$0.03/tr
    dip vol >  0.79x           n=611   -$2.37/tr
    dip vol >  1.50x           n=268   -$3.24/tr
```
The detector NEVER measures this. Its only volume test demands the CONFIRMATION bar be heavy;
the dip's volume is unexamined.

**3. Room to run** — I MEASURED IT BACKWARDS and said so:
```
    within 0.5% of session high   n=104   +$9.91/tr   82% green
    2-5% below                    n=136   -$5.41/tr
    10-20% below                  n= 68   -$3.08/tr
    >= 20% below                  n= 39  -$20.88/tr   21% green
```
I used "distance to the session high" as room-to-run. For a name pressing its high that distance
is ~0 BECAUSE THERE IS NO OVERHEAD SUPPLY — blue sky, maximum runway. A name 20% below its high
has a wall of trapped sellers. The metric actually measures PULLBACK DEPTH; both readings point
the same way as Marcos's rule. My naming was inverted, not his doctrine.

**4. Front side** — ALREADY IMPLIED by the first three:
```
    3 conditions              HO n=301  +$4.87/tr
    + 1-min front side        HO n=271  +$4.23/tr
```
95% of fires passing the three conditions are already front-side (309/326 train, 271/301 HO). A
name above VWAP and within 2% of its session high cannot be back-side. Adding the explicit test
costs 10% of fires for nothing. The definition is internally coherent.

### THE DEFINITION, THRESHOLDS FROM DOCTRINE (not fitted)
above VWAP  +  dip volume < advance volume  +  within 2% of the session high
```
    TRAIN     every fire  n=2982  +$1.12/tr  38% win  50% green
              DEFINITION  n= 326 +$11.35/tr  46% win  64% green   (11% of fires, +$10.23 swing)
    HOLD-OUT  every fire  n=2069  -$3.69/tr  32% win  55% green
              DEFINITION  n= 301  +$4.87/tr  42% win  74% green   (15% of fires, +$8.57 swing)
```
**IT FLIPS THE SIGN ON UNSEEN DATA**, same direction on both halves, with round numbers taken
from the definition rather than from the tables.

### STATUS
Still a HYPOTHESIS, and still not shipped. What would make it a proposal: one pre-registered
arm with these exact thresholds declared in advance, priced both ways (dollars gained vs dollars
of winners refused), through the funnel rather than detector-only, and a Marcos priced call.
What it already refutes: my extension ceiling, and my claim that "no separator exists" — six
separators I invented failed; the three HE stated all worked.
