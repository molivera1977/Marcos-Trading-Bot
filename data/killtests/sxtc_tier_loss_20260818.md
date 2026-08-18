# OFFICIAL CORRECTION — SXTC 2026-08-18: TWO TIER BANKS LOST ON RESTART

**Marcos: "i want the official record to show what really happened."** This is that record.

## The correction

| | stored | TRUE | delta |
|---|---|---|---|
| SXTC ignition 8/18 | **−$7.62** | **+$21.89** | **+$29.51** |
| **RTH day total** | **−$18.00** | **+$11.51** | **+$29.51** |
| PRE day total (separate, per `feedback_rth_official_pre_separate`) | −$13.29 | −$13.29 | — |

**The 8/18 official RTH day is +$11.51 on 11 trades, 6/11 winners** (SXTC moves from loser to
winner). Premarket, on its own line, is −$13.29 on 1 trade.

## What really happened

Entry 109 shares @ $4.5999 (10:04:10). The position then **banked two tiers**:

| leg | shares | price | time | on the tape? |
|---|---|---|---|---|
| tier 1 | 54 | $4.8207 | 10:28:50 | **YES** — verified against SIP 10s bars |
| tier 2 | 27 | $5.0415 | 10:30:40 | **YES** |
| remainder | 28 | $4.53 | trailing stop | YES |

`54×(4.8207−4.5999) + 27×(5.0415−4.5999) + 28×(4.53−4.5999)`
`= +11.92 + 11.92 − 1.96 = ` **+$21.89**

The stored record carried `partial_fills: []` and priced all 109 shares as if they rode from
$4.5999 to $4.53 — **−$7.62**. Both banks were written to the durable decisions archive
(`tier_fill` rows, 10:28:56 and 10:30:58) and never reached the trade record.

## Cause: a RESTART-RESUME gap, not an accounting-model flaw

The tiers filled minutes after the 10:07 restart, while the monitor was running on rehydrated
state. The resumed monitor rebuilds the position but does **not** rebuild `partial_fills` from
the durable `tier_fill` rows — it trusts in-memory state that the restart had emptied. The rows
existed the whole time; nothing read them back.

This is the same family as the ghost open-trades / dead-executor work (#40–42) and is the first
case to slip through the resume path since those landed.

## Scope: ISOLATED, and that is measured, not assumed

Swept every era date 2026-07-13 .. 2026-08-18 (27 days with trades), joining every `tier_fill`
row to its trade record's `partial_fills`:

* **188 tier_fill rows in the era**
* **2 not on their record — both SXTC, both today — 1%**
* **1 day affected of 27**

The 26 other days reconcile perfectly. The runner-leg class that corrupted 36 records through
7/20 has **not** recurred. No other number quoted this week is affected by this defect.

## How it surfaced

Marcos looked at a reported −$31.29 and said "−$31 is wrong." It was wrong twice: (1) it summed
RTH and PRE into one headline, violating the 8/4 rule that premarket gets its own line; and
(2) it carried this lost tier bank. Neither would have been found by re-reading the summary —
both came out of a full-row verification he asked for.

## LIMITS

* The $4.53 exit price and the 28-share remainder are taken from the stored record; only the two
  missing tier legs are reconstructed, and both are verified against the tape.
* No fee/borrow model is applied here, consistent with every other figure in the book.
* The store is NOT rewritten by this document. It is a ledgered correction, in the same spirit as
  `pnl_runner_leg_correction_20260726.json`; the fix that prevents recurrence is separate.

## Owed

1. On resume, rebuild `partial_fills` from durable `tier_fill` rows instead of trusting in-memory
   state. Pin it in the rig with this SXTC case as the fixture.
2. Re-run this era sweep after that fix and after any future restart-heavy session.
