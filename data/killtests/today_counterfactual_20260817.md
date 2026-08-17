# COUNTERFACTUAL REPLAY — "what if every 8/17 fix had been running from 07:00" (Mon 8/17/26)

Analysis only. No code changed, nothing deployed. Clock: `date` run in-turn → Mon Aug 17 15:12 EDT 2026.

Script `today_counterfactual_20260817.py` · run log `..._run.txt` · rows `..._out.json`
Archive: `GET /api/decisions_archive?date=2026-08-17` — 14,808 rows.
Tape: SIP 10s bars rebuilt this turn from Alpaca `/v2/stocks/trades` (`feed=sip`, 11:00–20:05Z) for
all **69 candidate tickers** (the local `data/universe/bars10s` cache held only 9 of them for 8/17).
Alpaca rejects sub-minute `timeframe` on the bars endpoint, so 10s buckets are built from raw
trades — same construction as the harvester's files (verified against `2026-08-17_WFF.json`).

---

## THE ANSWER, UP FRONT

**The fixes do not rescue today. On today's tape they make it worse.**

| | fills | day P&L |
|---|---|---|
| **ACTUAL** | 4 | **−$15.65** |
| **COUNTERFACTUAL (2 slots × $500)** | **10** | **−$157.71** |
| delta | +6 | **−$142.06** |
| counterfactual, 1 slot (real $604.16 balance) | 6 | −$76.17 |

RTH/PRE split of the counterfactual (official = RTH, PRE on its own line):
**RTH n=4 −$98.51 · PRE n=6 −$59.20.**

And the constraint is the only thing keeping it that small. **Unconstrained** — every unlocked fire
taken, no slot or capital limit — the same 117 fires grade **−$2,005.67 over N=117 (−$17.14/trade)**.
The 2-slot governor discards 106 of them; it is doing more for the P&L today than any fix does.

**Every single unlocked cohort grades negative per-trade on today's tape:**

| fix | unlocked fires | unconstrained $ | $/trade | fills that survived slot contention | $ |
|---|---|---|---|---|---|
| FIX5 caps-on-fills | 84 | −$1,665.54 | **−$19.83** | 9 | −$135.31 |
| FIX3 lane registry | 17 | −$172.53 | **−$10.15** | 0 | $0 |
| FIX6 kevseq limit entry | 9 | −$61.16 | **−$6.80** | 1 | −$22.40 |
| FIX2 tape-lane momentum exemption | 3 | −$27.85 | −$9.28 | 0 | $0 |
| FIX4 kevseq front_side self-compute | 1 | −$39.27 | −$39.27 | 0 | $0 |
| FIX1 bell-boundary handoff | not reconstructible (see limits) | — | — | — | — |
| (the 4 ACTUAL fires, for reference) | 3 modelled | −$39.32 | −$13.11 | **0 — crowded out** | — |

**This is a "the fixes change little, and what they change they change for the worse — today" answer.**
Today was a chop day for these lanes. That is one day, and one day is not a verdict on any of the six
fixes. But it is the honest number and it is the number Marcos asked for.

---

## THE COUNTERFACTUAL TRADE LIST (2 slots × $500, chronological)

| # | time ET | ticker | lane | unlocked by | entry | stop | exit | reason | @ | $ |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 07:03:15 | DFSC | v2conv | FIX5 | 3.0906 | 2.9376 | 3.3931 | trail | 07:27:50 | **+49.47** |
| 2 | 07:16:03 | PLSM | v2conv | FIX5 | 3.4264 | 3.0100 | 2.9949 | stop | 07:17:40 | **−62.96** |
| 3 | 07:45:36 | JLHL | v2conv | FIX5 | 8.5849 | 8.1599 | 8.1191 | stop | 09:46:40 | −27.13 |
| 4 | 08:04:29 | QNTM | v2conv | FIX5 | 4.5349 | 4.2500 | 4.2287 | stop | 08:27:30 | −33.75 |
| 5 | 08:56:28 | IPST | kevseq | FIX6 | 8.1405 | 7.8149 | 7.7758 | stop | 09:07:20 | −22.40 |
| 6 | 09:10:06 | STKH | v2conv | FIX5 | 3.6000 | 3.3505 | 3.7810 | eod | 16:00 | +37.57 |
| 7 | 09:47:08 | XPON | v2conv | FIX5 | 4.6215 | 4.3927 | 4.3707 | stop | 09:53:30 | −27.13 |
| 8 | 09:54:14 | AEHL | v2conv | FIX5 | 5.0803 | 4.8288 | 4.8047 | stop | 09:55:10 | −27.13 |
| 9 | 10:01:06 | JDZG | v2conv | FIX5 | 4.2066 | 3.9984 | 3.9784 | stop | 10:21:10 | −27.13 |
| 10 | 10:27:46 | JDZG | v2conv | FIX5 | 4.2318 | 4.0223 | 4.0869 | eod | 16:00 | −17.12 |

2 winners / 8 losers. **Biggest single unlocked trade: DFSC v2conv 07:03 +$49.47** (FIX5 — the cap
that today's real bot had already burned at 04:35 on five premarket ghosts).
**Counterfactual worst case: PLSM v2conv 07:16 −$62.96** — a 12%-wide stop taken out in 97 seconds,
worse than any single trade the real bot took today.

### One trade traced end-to-end (dollars, doctrine)
DFSC, v2conv, signal $3.06 at 07:03:15 (`v2conv_capped` row, cap refunded by FIX5).
Fire bar `11:03:00Z o/h/l/c 3.06, vol 26`. Entry = 3.06 × 1.01 slip = **$3.0906**;
$500 / 3.0906 = **161.78 sh**. Stop = 60s-prior low $2.9376 (4.95% — clears the 4% min-stop floor
untouched). Bank ½ (80.89 sh) at +10% = $3.3997, hit `11:19:40Z` → +$24.99.
Run-high $3.7700; close crosses 10%-off-run-high at 07:27:50 → remainder out at
$3.4102 × (1−0.5%) = **$3.3931** → +$24.48. **Total +$49.47.**

---

## WHAT EACH FIX ACTUALLY DID TO THE REFUSAL STACK

Method: for every refusal, the fix only reverses it if the refusal reason is the one that fix
addresses **and** the rest of the stack (min-stop 4% / degenerate stop / back-side band / entry
window / slots / capital / one-position-per-name) still passes. **125 candidate reversals assembled,
117 cleared the stack, 31 died on a surviving gate:**

| surviving refusal | n |
|---|---|
| `unfilled_limit` (FIX6 — the fire bar never traded at fire+0.5%) | 16 |
| `backside_gate` (15–30% under a ≥20-min-stale session high) | 8 |
| `pre_open_blackout` (fire before ENTRY_OPEN_ET 07:00) | 7 |

**FIX5 (caps on fills)** — the largest single unlock: 47 `v2conv_capped` + 48 `grinder_capped`
refusals, 84 of which cleared the stack. Root cause confirmed in `ghost_cap_20260817.md`: five
premarket v2 triggers that never became trades ate `V2_DAILY_CAP=5` by 04:35:06. So this fix does
exactly what it claims. It unlocks a cohort that lost **−$19.83/trade** today.

**FIX3 (lane registry)** — 42 `chart_gate_blocked_trade` rows; 17 joined to a newly-exempt tape lane
and cleared the stack; **all 17 were crowded out by slots** and contributed $0 to the day. Their
unconstrained grade is −$10.15/trade — same sign and same order as the artifact's own pre-registered
era number (−$64.25 / N=13). Failure-condition #1 in `lane_registry_20260817.md` is edging toward
tripped, not away from it.

**FIX4 (kevseq front_side self-compute)** — the headline "58 refusals" is real, but **only 7 of the
58 had `front_side_unknown` as the SOLE reason**; the other 51 also carried `day_gain`, `no_burst`
or `burst_unmeasured` and stay refused. Of those 7, re-running the shipped test (EMA9 vs EMA20 over
a 10s→1-min aggregate built from today's SIP tape, ≥22 completed minutes) returns front_side=True on
exactly **1**. That one fire grades −$39.27 and never got a slot. **Net effect on today: zero fills.**

**FIX6 (KEVSEQ_LIMIT_ENTRY)** — the most defensible fix and it still nets negative. It **vetoes 16 of
25 kevseq fires** as `unfilled_limit` — including all three WFF fires. The real WFF trade
(fire $5.1329 → filled $8.20, −$6.88) becomes **NO TRADE**, a +$6.88 improvement. But the fix is
symmetric: it also refuses the WETO 13:50/13:54 fires and the 11:17 WFF fire that
`lane_registry_20260817.md` graded at +$32.58. The 9 kevseq fires that *do* fill at the limit grade
−$61.16. **FIX6 is a risk-integrity fix, not a P&L fix, and today it costs money.**

**FIX2 (tape-lane momentum exemption)** — only 6 `momentum_reject` rows exist all day, 3 on tape
lanes. −$27.85 unconstrained, 0 fills. Immaterial either way.

**The four real trades get crowded out.** In the counterfactual chronology, FIEE (+$22.73 actual),
DFSC-ignition and NIVF **all hit `no_free_slot`** — the extra premarket v2conv volume the cap-refund
unlocks is holding both slots when the 09:38 FIEE ignition fires. That is the single most important
finding in this replay: **these fixes do not add trades to the day, they REPLACE the day's trades
with earlier, worse ones.** Slot contention is not a footnote here; it is the mechanism.

---

## THE FIX7 QUESTION — the artifact does not exist yet

`data/killtests/m1_wallclock_20260817.md` is **NOT PRESENT** (`ls` run this turn; latest commit
`1fd978f` diagnoses the traded-minute-vs-wall-clock defect but ships no fix). So per instruction the
replay was run **without it**, and there is no "with" arm to run — the behaviour is unspecified.
What can be said: FIX7 would widen the population entering the FIX4 path (more names reaching 22
wall-clock minutes of 1-min context sooner), i.e. it acts as a **multiplier on FIX4's cohort**, which
graded −$39.27/trade on its single specimen today. **Directionally that makes today worse, not
better.** That is an inference, tagged **[UNVERIFIED]** until the artifact and its arm exist.

---

## HONEST LIMITS — read these before quoting any number above

1. **FIX1 (bell-boundary) discovery is NOT reconstructible, and the prompt's framing overstates it.**
   The 09:30–09:36 window is not empty in the archive: **140 rows across 38 tickers printed inside
   it**, IVF among them. What the boundary broke was the read-list/entry evaluation, not all logging.
   Names present before AND after but absent inside the window — the only reconstructible cohort —
   number **four**: BRNX, MYSZ, SVRE, YYAI. A name that never entered the roster leaves no trace at
   all and cannot be recovered by any method.
   As an **illustrative upper bound only** (naive 09:30:30 entry, E3 exits, **no gate stack applied**
   — this is NOT a modelled bot decision): IVF +$34.25, BRNX −$8.80, MYSZ −$17.58, SVRE −$7.43,
   YYAI −$14.51 → **−$14.07 for the five.** IVF's ramp is real and is the one place today where the
   boundary plausibly cost money; the other four pay it back. **Not counted in the headline.**
2. **Fills are modelled, not real.** Assumptions: $500 clip; +1% entry slip on market-lane entries;
   kevseq entries at exactly `fire_px × 1.005` when the fire bar's low reached it, else NO TRADE;
   bank ½ at +10% as an exact resting limit; trail 10% off run-high on **closes** after the scale;
   **intrabar stop evaluated FIRST** (every tie ruled against the trade); −0.5% on market exits;
   EOD flatten at 16:00 ET at last print. No partial-fill, queue-position, spread or halt modelling.
   Stops: the trigger row's own stop where stamped, else the 60s-prior low, else entry × 0.94, then
   widened to the 4% min-stop floor (live behaviour) rather than refused.
3. **Downstream gates I could not replay** — ambient/dvol, lens focus, crown state, runway RR,
   spread, per-lane internal conditions. Those are refusal-only gates: replaying them can only
   REDUCE the counterfactual fill count. Since the counterfactual is net negative, **the true number
   is probably less bad than −$157.71 and cannot be better than the actual by way of these.**
4. **Cap-refusal rows carry no stop.** For the 95 `*_capped` rows the stop is inferred from tape
   (item 2). Real v2/grinder stops would differ; the cohort's −$19.83/trade is therefore
   stop-construction-sensitive. It is not sensitive enough to flip: 8 of 10 fills stopped out.
5. **Ordering is knife-edge.** The 2-slot engine's result depends entirely on which fire arrives
   first. The 1-slot sensitivity (−$76.17) and the unconstrained grade (−$2,005.67) bracket it. Treat
   −$157.71 as one draw from a wide distribution whose **mean is clearly negative**, not as a point
   estimate.
6. **One day. N=10.** Nothing here refutes any of the six fixes. FIX5 and FIX6 close real, proven
   defects; a defect fix that loses money on one chop day is still a defect fix. What this replay
   *does* refute is the hopeful story that today would have been green with the fixes in place.

## WHAT THIS SAYS FOR THE WEEK

- The fixes' value is **integrity**, not expectancy. Do not sell them as P&L.
- The load-bearing risk they create is **volume**: FIX5 alone would have taken the day from 4 fires
  to 84 eligible ones. On $604.16 of capital that is 100% governed by the slot count. If any of these
  ships live, the slot/capital governor is the thing that must be right.
- The one number worth chasing from today is the **crowd-out**: the fixes cost the day its only real
  winner (FIEE) by filling both slots with premarket v2conv chop. That argues for **ranking** fires,
  not just gating them — which is the hole `kevseq_reconciliation_20260817.md` already named.
