# B1 — KEVSEQ FIRES AT A LEVEL, NOT A TRADED PRICE (EG1-a) — 2026-08-17

## FAILURE CONDITION (written FIRST)

This change is **WRONG** if any of the following turns out to be true:

1. The setup bar's HIGH is, in fact, a price the tape reliably offers on the fill bar — i.e.
   the drift measured today is a *quoting* artefact and not a real gap between signal and
   fill. Falsified by: fills clustering at the level rather than above it, over ≥5 sessions.
2. Raising the fire price to the fill bar's close shrinks size so far that the lane's realised
   dollars fall, even though its stated risk becomes honest. Falsified by: kevseq dollar
   expectancy per fire dropping in the same-tape counterfactual.
3. The two fires this turns into `degenerate_stop` refusals were, on the tape, winners. Then
   the refusal is costing money and the guard is the thing to argue with, not the fire price.
4. `KEVSEQ_FIRE_ON_CLOSE=0` does not restore the 8/16 behaviour byte-for-byte.

## LIMITS / CAVEATS

- **The "new risk" column below is a PROXY, not the shipped number.** The archive rows carry
  the detector's `fire_px` and the **live quote** at gate time (`price`); they do **not** carry
  the fill bar's close, which is what the fix actually uses. The close sits between the two.
  So the new-risk figures here are an **upper bound** on the shipped effect, not a measurement
  of it. A true measurement needs one session of `fire_px`-on-close rows.
- N = 23 kevseq fires, ONE session (2026-08-17). Single-day, single-regime.
- No counterfactual P&L is claimed. This changes the *price the signal reports*, and therefore
  sizing; whether that is worth dollars is Friday's question, not this document's.

## ROOT CAUSE

`kevseq_step` returned `px = float(pd["hi"])` — the H/W **setup bar's high**, i.e. the trigger
level. Every other detector in the bot returns the **fill bar's close `c`**: `hidden_entry_step`,
`v2_pullback_step`, `grinder_shadow_step`, `bandpass_step`, `kev_zoneflip_step`,
`kev_reclaim_step`, `dip_rip_step`, `ignition_10s_step` (AST-verified 8/17). kevseq was the sole
exception, born 8/16.

A level is not a price. The fill bar qualifies by having a HIGH above the level — its close can
be anywhere above the level, and on a vertical name it is far above.

## THE CONSEQUENCE CHAIN, STATED BEFORE THE NUMBERS

`would_stop` is **unchanged** by this fix — it is the setup's own structure (the H level, or the
W bar's wick low), measured off the setup bar. Moving only the fire price therefore moves
**risk-per-share**, and risk-per-share is the denominator of the entire downstream chain:

    fire px ↑  →  risk/share ↑  →  shares ↓  (position sizing)
                              →  runway RR ↓ (target distance ÷ risk)
                              →  min-stop-% gate: more fires now CLEAR the 6% floor
                              →  max-risk clamps bind on the wide ones

And, at the extreme, `px ≤ would_stop` — the tape closed back under the setup's own risk. The
old code reported that as a valid fire with positive risk. The new code appends
`degenerate_stop` to `why` and the fire is **refused**. That is the intended behaviour: a
signal whose risk-per-share is zero or negative is malformed and must not reach sizing.

## TODAY'S 23 KEVSEQ FIRES — RISK DISTRIBUTION, OLD vs NEW

| | n | min | median | mean | max | >10% | >20% |
|---|---|---|---|---|---|---|---|
| **OLD** (level vs stop) | 23 | 0.54% | 2.60% | 3.56% | 12.94% | 1 | 0 |
| **NEW** (traded price vs stop, proxy) | 21 | 0.25% | 3.34% | 9.28% | 41.46% | 5 | 3 |
| refused as `degenerate_stop` | 2 | — | — | — | — | — | — |

Drift (live quote vs fire level) across the 23: median **+0.97%**, mean **+7.05%**, max
**+59.75%**, min −5.49%.

**Read it this way.** The old column is not a smaller risk — it is a *fictitious* one. The bot
was already paying the new column at the fill; it simply reported the old one to sizing. Three
fires carried >20% real risk while telling the sizer 6%. That is the defect.

### Hand-traced specimens

**WFF 12:01:27 PM** — the specimen in the batch brief.
- setup high (old fire px) **5.1329**; live quote at gate **8.20**; `would_stop` **4.80**
- OLD stated risk `(5.1329 − 4.80)/5.1329` = **6.49%**
- NEW risk against the price actually paid `(8.20 − 4.80)/8.20` = **41.46%**
- drift **+59.75%**. Sizing built the position as if one share risked $0.33; it risked $3.40.
  At a $500 slot that is 97 shares planned at $32 of risk vs 61 shares at $207 of risk —
  **6.4× the intended risk**, silently. With the fix the fire prices at the close and the
  min-stop / max-risk gates see the real number.
- Same name, **11:58:33 AM**: fire 4.77 → live 6.92, drift +45.07%, risk 6.08% → 35.26%.
  Two consecutive fires on one name, both mis-stated by >5×.

**WETO 13:50:04 PM** — the second required specimen, and a compound defect.
- setup high (old fire px) **17.11**; live quote **18.81**; `would_stop` **16.93**
- OLD stated risk **1.05%**; NEW **9.99%** — a 9.5× understatement.
- `fire_age_s` on this row is **2284.8 s (38 minutes)**. The fill bar was 38 minutes old. So
  this fire was *both* priced at a level and fired off a stale bar — B1 and B2 in one row.
  The 13:54:28 WETO fire four minutes later carries `fire_age_s` 18.0 s and drift +0.95%:
  when the bar is fresh, the level and the close nearly agree. **The drift is largely a
  staleness symptom**, which is why B2 matters and why the two items were found together.

**TRUG 13:36:08 PM** — the refusal case.
- fire level 1.67, live **1.585**, stop **1.64**. The tape was *below the setup's own stop*.
  OLD: reported a valid fire at 1.80% risk. NEW: `px ≤ would_stop` → `degenerate_stop` →
  **refused**. `RPGL 11:46:57` is the same shape (live 2.55 = stop 2.55, risk exactly 0).

## WHAT CHANGED

`marcos_trading_bot.py`:
- new env `KEVSEQ_FIRE_ON_CLOSE` (**default 1 = the fix**; `0` restores the 8/16 level).
- `kevseq_step`: `px = float(c) if KEVSEQ_FIRE_ON_CLOSE else float(pd["hi"])`.
- the fire dict's `"px"` is written as an explicit conditional on `c` so the EG1-a property
  computer (which reads the dict literal) can grade the lane as pricing off a traded print.
- the fire dict gains `"level_px"` — the old trigger level, kept as evidence so every row can
  still be sliced by the level the setup broke.
- `would_stop`, the `degenerate_stop` check, and the caller's own
  `_ksf["would_stop"] < _ksf["px"]` conversion guard are all UNCHANGED — they now simply see
  the honest price.

## DEFAULT: **ON**

Reason: parity with all eight sibling detectors is the settled shape of the codebase, and the
old value was not a price at all. Leaving it off would mean knowingly reporting a fictitious
risk-per-share to the sizer. The kill switch exists and is one env away.

**This is a MONEY-BEHAVIOUR change** (sizing, and two of today's 23 fires become refusals).
Per `feedback_auditor_cannot_authorize_behavior` it goes to Marcos **priced**, with the table
above, and does not ride an auditor's ship.

## ACCEPTANCE

- `rig/test_batchB_20260817.py::SPEC_kevseq_fire_on_close` — drives the shipped `kevseq_step`
  over a synthetic B→H/W→fill tape and asserts the fire prices at the fill bar's close with the
  switch ON, at the setup high with it OFF, inside `[bar_lo, bar_hi]`, and with `would_stop`
  identical either way.
- `rig/test_batchB_20260817.py::SPEC_kevseq_degenerate_stop_refuses` — the TRUG/RPGL shape:
  close below the setup stop must produce `ok=False` with `degenerate_stop` in `why`.
- EG1 pin `kevseq.a` flips `OPEN` → `True` in `rig/test_shipset_20260804.py`.
