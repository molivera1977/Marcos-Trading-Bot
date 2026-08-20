# PUNCH LIST — opened 2026-08-19 (Marcos: "add it to the list")

Everything here was found live on 8/19. Nothing below is shipped. Nothing below is kill-tested
unless it says so. Ordered by what costs money or blinds us soonest.

---

## P0 — THE EXIT DIDN'T REACH THE BOOK (cost: the record of every trade)

**VRAX 08:55:09 → 08:59:25, prevwap, −$17.46.** The exit completed correctly (E3 trail: run-high
$4.16 × 0.90 = $3.744, price $3.7405, ×53 sh = −$17.46 to the cent). Then **both** post-exit steps
failed: the trade record never posted, and `open_trades` was never cleared. Dashboard showed a
phantom position for 40 minutes; the 09:25 flatten "didn't fire" because there was nothing left
to flatten.

**CAUSE CONFIRMED 10:1x (CISS repeated the class inside log retention):**
`💥 worker CISS died: name 'cache' is not defined` — the 8/18 VWAP-provenance fields in the
record payload referenced `cache`, a LOCAL of `wait_for_flat_top_entry`, from `_trade_worker`
where it does not exist. Deterministic NameError after EVERY exit under the 8/18 22:56 build:
exit completes → payload build raises → record never posts → clear never runs → ghost row.
The earlier `extra.get` candidate was REFUTED (extra is normalized twice upstream).

* **FIXED (built 8/19 ~10:15, UNSHIPPED):** payload now reads `_session_cache` — the same dict
  `cache` aliases, and it IS in the worker's closure.
* **CISS ghost repaired by hand** (kevseq −$55.80 RTH, stop-loss in 18s off the halt-resumption
  flush; `off_tape_exit why=no_tape_seen` — exit itself worked; only record/clear died).
* **BONUS KILL from the same sweep:** `urllib` (never imported) in the zone-stamp day-high fetch
  meant the 8/3 TAPE PRE-BREAK GATE and the RETEST-BAND GATE were **fail-open dead from birth**
  — 16 days, zero blocks, invisible because fail-open looks identical to passing. FIXED
  (requests, same timeouts). NCRA/STAK/BOOM-class blocks were never happening.
* **CLASS KILLED: rig gate 20** (`test_undefined_names_20260819.py`) — pyflakes undefined-name
  sweep over both live services, guarded-`b4` allowlisted, RED on anything new. GREEN.
* Still to build: recovery sweep so a failed record/clear self-heals without a restart
  (the "restart will re-post" path assumes a restart that never comes).

⚠️ **UNTIL TONIGHT'S SHIP the RUNNING bot still ghosts every exit** — each one needs the manual
record+clear repair. Watch duty holds.

**THIRD DEFECT FROM THE SAME 8/18 BATCH, SAME SHAPE (found 10:3x, Marcos: "how about 9/90?"):**
`_log_decision() got multiple values for keyword arg` — the ema9x90 fire log passed `fire_k`
explicitly AND inside `**_fed_stamp`; the TypeError was caught by the block's except, which ate
the fire AND its `breakouts.append` conversion. **Six 9/90 fires (09:33-10:16) died as
`gate_fail_open` rows — the rank-#2 lane was dead on a log line during CDTG's exact +50% run.**
Which names fired is unrecoverable (the failopen row drops the ticker — add it). FIXED (explicit
`fire_k` removed; call shape exercised, no collision), UNSHIPPED. The batch's three kills —
`cache` (every exit record), kwargs (every 9/90 fire), `urllib` (pre-break gate, 16 days) — are
ONE CLASS: an exception between detection and action, eaten by a handler. Gate 20 covers the
undefined-name flavor; the kwargs flavor was visible only because this handler logged. The
still-silent handlers (kevseq/bounce/reclaim NO-ROW deaths) are the same graveyard, uninstrumented.

---

## P0 — 16 FIRES DIED UNINSTRUMENTED (cost: we cannot say why)

Duty watch 09:42 ET, the bot's own accounting:

```
kevseq:        10 fires, ZERO fills — NO REFUSAL ROW
bounce:         3 fires, ZERO fills — NO REFUSAL ROW
vwap_reclaim:   3 fires, ZERO fills — NO REFUSAL ROW
BLIND GATE PASSES (decided without their data): {'ambient': 2}
```

Marcos's standing rule is *lanes fired, no fill → name the gate*. Three lanes cannot answer it.
Every one of those 16 is an unanswerable question about our own machine.

---

## P1 — THE MAP RE-READ LOOP (cost: the API bill, measured)

Invoices are the same ~$10.1 credit pack, but the interval is collapsing:
`Jul 30 → Aug 11 = 12d`, `Aug 11 → Aug 17 = 6d`, `Aug 17 → Aug 19 = 2d`. ~6× the burn.

Measured 8/19 04:53–09:50 (partial day): **38 freshness_breach, 26 reread_on_reject**, and
**24 of the 26 reads were triggered by freshness_breach**. Reads concentrate on a few names:

```
YJ    11 breaches →  5 rereads        EHGO   9 breaches → 6 rereads
TNON   5 breaches →  5 rereads        FEMY   4 breaches → 2 rereads
```

**Why the same name breaches forever — `map_age` is never reset by an auto-map:**

```
13:25:13  YJ   age=144.0m → AUTO-MAP $6.5
13:28:30  YJ   age=147.3m → AUTO-MAP $6.5      (age climbed, did not reset)
          EHGO age 143.5 → 145.9 → 154.6 → 156.9m
```

Once a map crosses the freshness threshold it stays across it for the rest of the session, so
every scan cycle re-breaches and queues another read. Not 24 names read once — **8 names read 26
times**, compounding as the day ages.

**MEASURED 8/19 (the archive endpoint holds weeks — the earlier "2-day retention, unmeasurable"
claim was wrong; wrong endpoint queried).** 524 age+dist points, 6 sessions, 54 names:

* Age does NOT predict wrongness at the median — the median 120m+ map sits within **2.6%** of
  live structure; the pre-registered decay (median |dist| rises with age) FAILS in every cohort,
  including the non-breach control.
* Staleness is TAIL risk: p90 |dist| 23.7% at 15-30m → **89.2%** at 120m+ (YJ 103%). The marker
  is not "old map" — it is "old map on a name that has MOVED," which dist already measures.
* **53% of freshness breaches (250/476) fired on maps still within 3%** — 175 pure age-triggers
  on accurate maps. IPST breached 47× on a correct map. 154 rereads queued across the 6 sessions,
  half+ buying nothing. THIS is the API bill.

**HYPOTHESIS (rig-gate before ship)**: make the reread trigger DISTANCE-PRIMARY — re-read when
the map is WRONG (dist past threshold), never merely old (age alone with dist≈0 queues no read).
Halves the vision spend and concentrates reads on maps that are actually lying — the FRESHEST
DATA rule expressed in the trigger. Fallback if the rig shows starvation: per-name-session
cooldown (blunt, but changes only spend, not what gates read).

---

## P1 — INSTRUMENT THE MAP-AGE QUESTION (blocks a real study)

Marcos asked whether stale maps cost money. **Not answerable today**, and the honest reason is
instrumentation, not absence of an effect:

* `map_dist_pct` is stamped almost exclusively on `freshness_breach` rows — 50 of 51 available
  rows. Selection on the outcome; the sample is only maps already known to be broken.
* Decision store retains **2 days**. 8/17 and earlier return zero rows.
* `entry_context` on trades started 8/16 — only **15 of 438** era trades carry `map_age_min`.

**To make it answerable** (none of this is a trading-behaviour change):
1. Stamp `map_age_min` + `map_dist_pct` on **every** map-consulting decision, breach or not.
2. Archive the decision log nightly before the 2-day window rolls. (10s bars already have 948
   name-days; decisions are the gap.)
3. Re-run the age→outcome split in ~2 weeks against real fills.

---

## P1 — STALE-FIRE SUPPRESSION CONSUMES THE AMMO (cost: CISS, halted at the high, untouched)

CISS admitted to the roster 09:38:40, ran $2.57 → $4.13 and HALTED. The bot logged, 4×:
`CISS ignition10s fire SUPPRESSED — bar 503.6s old > 240s (replay after restart/admission);
setup consumed, not traded`. Suppressing the replayed stale fires was CORRECT; consuming the
once-per-ticker setup on a suppressed fire was NOT — when the live ignition came minutes later
into the halt, the lane was already disarmed. The governing precedent is the slot-refund rule (see the `slot_refunded` path and
rig/test_slot_refund.py): an attempt is not a trade, and a SUPPRESSED attempt doubly so. Fix: stale suppression must leave the ammo intact
(mirror the existing shadow-path un-count pattern at the suppression site).

## P1 — GRADE TODAY'S REFUSALS IN DOLLARS (first fully-instrumented day)

Zero RTH fills through 09:57 while CISS +60% (halt), VRAX +50%, MSS, RDAC moved. Every refusal
carries a named gate (relvol, Kev's two conditions, runway, vel5, whitelist). Whether the gates
saved or cost money ON NET is measurable from today's decision rows + tape: price every refusal
through the real E3 exit engine, both ways, per gate. VRAX specimen: refused $3.63 on a 1.8-cent
EMA cross (9: 3.4021 / 20: 3.4199), spiked $4.29, round-tripped to $3.48 — the refusal aged
FINE on the round trip; only the E3 replay can say what a real position would have kept.
Strength Ombudsman's docket. No gate loosens on eyeball evidence.

## RETRACTED, THEN CORRECTED — "the Kev badge lies / Kev's sheet is absent" (8/19)

Both claims were MINE and both were WRONG — the first query checked only `src` and missed the
8/12 our-numbers-primacy re-shelving. Verified truth (reproduce: GET /api/kev_watchlist?date=2026-08-19 and count src/kev_name
fields): the badge keys off `kev_name` provenance and matches those fields; Kev's sheet WAS ingested (night 4 + morning 7); his 8 names today are
BIVI, EHGO, IH, SLE, TGL, TNON, YJ, ZNB — with his verbatim numbers preserved in `kev_shadow`
and vision primary, exactly per Marcos's 8/12 ruling. Six of eight green; YJ +161%, TNON +107%.

What SURVIVES as real work:
* 5 of his 8 rows carry break=None in kev_shadow — the sweep parsed names but not clean levels.
  Kev Librarian: check whether the sheet text carried numbers the parser dropped.
* His two biggest winners (YJ, TNON) are names the bot fired on all day and never filled —
  priced by the refusal-grading item below, not re-litigated by eyeball.

## P2 — CARRIED FROM 8/18–8/19

* `ship.sh` reports success on exit code without checking deployment STATUS.
* Nightly ledger line still prints a merged PRE+RTH figure, against the separation rule.
* No extended-hours flag in `_place_order` — blocks real premarket money (DRY_RUN unaffected).
* 60 historical VWAP-breach rows uncorrected; cause of truncated bar sets unknown.
* **17** pre-existing red rig gates (was 18 — `test_kev_merge` is a harness artifact, not a live
  defect: `screener_app.py:11` imports datetime at module level; the rig lifts the function into a
  fresh namespace without module globals).
* hidden_entry exits ("finds the entries but can't hold it") + vwap_reclaim review — Marcos's
  stated next work.
* ma_pullback premarket UNMEASURED; 30-min arm window unswept; harness parity unmeasured.

---

## SETTLED TODAY (do not re-litigate)

* PRE lanes = ignition, ma_pullback, prevwap, v2conv. The prevwap/v2conv carryover is **knowingly
  kept** (Marcos 8/19 "leave them"), not a bug.
* Restricted lanes still DETECT and LOG; they cannot convert. That is deliberate.
* Runway gate refusing TNON at $12.36 (0.21R) was **correct** — TNON poked $13.06 then collapsed
  to $11.10 and halted. One anecdote, not proof of the gate's expectancy.
* `/api/trades` is CLOSED-TRADES-ONLY. An open position is legitimately absent from it.

---

## LIMITS

The reread/map-decay numbers above aggregate 2026-08-12..2026-08-19 — multiple CONFIG EPOCHS.
Rows before the 8/17 config-hash stamp carry no code_sha/config_hash, so the aggregate was NOT
split per epoch; the current epoch is code_sha d4bfd68221a3 / config_hash 72f454cc5251 (from
today's decision rows). Detector behaviour changed inside the window (kevseq shipped 8/17,
session map 8/19), so per-lane counts mix machines. The 53%-within-3% breach finding was NOT
re-verified per epoch; direction was consistent across the two days spot-checked (8/18, 8/19).
Fire counts here are decision-row counts, not fills. Nothing in this file is a kill-test verdict.

## KEVSEQ REVIEW — TEMPO MEASURED 8/19 ("run the tempo check")

Marcos framed the lane as pattern+SEQUENCE; the too-fast-to-be-real hypothesis (from CISS's
18s-to-stop loss) was tested against Kev's own tape and REFUTED: Kev's 23 located fills run
MED 18s from break to fill (p25 12s, half under a minute) vs the machine's MED 50s over 78
fires — KEV IS FASTER THAN THE BOT. CISS's 50s sequence was normal tempo for both cohorts.
A minimum-dwell rule would cut Kev's own best-documented behavior. NOT built.
* Real gap found instead: Kev's SLOW tail (patient W fills p75 480s → hours) — the machine
  tops out at 27m. Coverage question, not a floor.
* CISS's loss re-narrowed to the HALT-RESUMPTION REGIME (off_tape_exit why=no_tape_seen —
  feed blindness at entry), a tape-quality condition inside the pattern's own terms.
* Caveat on record: Kev-side clock = min_since_sess_hi at the located fill (an analog of
  B->fire, not the identical instrument; fresh-high fills read ~0). Reproduce: the f-features
  in data/killtests/kev_rosetta_20260816_rows.json (24 rows) vs bars_since_b on
  kevseq_shadow_fire rows from /api/decisions_archive 8/17-19. Direction robust, medians not
  gospel — tagged as an analog, not an equivalence.
* Doctrine settled in-session: the PATTERN IS THE GATE (7/26 chart-gates-chart doctrine) —
  kevseq's scalar exemptions are coherent with its six internal conditions; the spec text's
  stale "normal gate stack applies" line should be updated to match the ruling, not vice versa.
* TEMPO→OUTCOME (69 shadow fires, E3, 3 days): fast <60s −$2.41/tr 18% green · 60-180s
  −$6.19/tr · **>=180s +$19.98/tr 50% green (n=6)** — the machine's money is the PATIENT
  W fills. **H-variant 0/9 green, −$16.31/tr** — watch for the 5-day wall; if confirmed, H dies.
* OVERLAP CHECK (Marcos: "can we run it"): REFUTED — 1/43 fast kevseq fires had an ignition
  event within 5 min prior. kevseq-fast is NOT late ignition; ignition's quiet-base cannot
  form at a running name's leg highs. The lanes fire at different tape moments.
* NET FINDING OF THE CHAIN: **nobody owns Kev's fast entry** — his median fill is 18s after
  the break, AT the B, on a loud tape. Ignition can't (needs quiet base); kevseq won't
  (waits for H/W, arrives late = the losing fast cohort). This matches the Hidden Entry
  Architect's charter as recorded in persona_hidden_architect.md (8/14: anticipation, not
  confirmation) — correspondence asserted from that memory, with the target now measured to
  the second (reproduce: the three checks above). Three days' evidence, no OOS wall — nothing ships from this.
## FOR THE HIDDEN STUDY (Marcos 8/19: "hidden can find them, it just can't hold them — later")

Starting coordinates from today's chain, so the study opens on evidence:
* Hidden's beat = the flush low (pure anticipation, no proof) — earliest fill in the leg
  grammar, which is WHY it finds them; the hold problem is that a flush entry's risk is
  unbounded until the reclaim proves out, and E3 (built for post-proof entries) trails it out.
* Nearest working relative: **kevseq-W-slow** (wick to VWAP >=3min after the high, close back
  above) = +$19.98/tr, 50% green, n=6 — nearly hidden's trade taken through a stricter grammar.
  The study's cheapest first question: grade hidden's shadow detections through kevseq-W's
  hold/exit discipline and see if the finding survives the holding.
* Second target: Kev's unowned fast-B entry (18s median, loud tape) — adjacent to hidden's
  charter (anticipation-not-confirmation, 8/14).
* Hidden's live figures remain UNVERIFIED per Marcos ("those hidden numbers are fake").
## ZSTK 8/19 — THE +700% MONSTER AS MULTI-SPECIMEN ($1.52 -> $12.40)

Tracked all day, never entered. Reproduce: ZSTK rows in /api/decisions 8/19 (155 rows).
* RESTRICTED-BY-DESIGN (working as ordered, priced as counterfactual): vwap_reclaim fired
  $2.03 (09:35), ORB fired $4.90 (11:26) — both lane_restricted per Marcos's review bench.
  These rows belong in the refusal-grading study's restricted-lane cohort.
* AMMO BUG PROMOTED (was P1-deferred): 10:45 halt resumption — ignition's fire
  stale-suppressed AND consumed, the CISS class, now 2 monster specimens in one day.
* DIP_RIP AUDIT: armed 2x on a textbook halt ladder (10:45, 11:40), converted 0. The lane
  built for this exact tape. Cause unknown — needs the 10s tape walk (flush-hold condition
  vs feed gaps).
* FEED-DURING-VERTICALS (Quartermaster/Feed Engineer): bars 1900-2300s stale BETWEEN halts,
  VWAP=0 warnings, tick-sanity rejects (px 4.9 vs bar 2.33) on the day's biggest mover —
  same smell as CISS's off_tape_exit why=no_tape_seen. Does the 10s stream degrade exactly
  when names go vertical? Measurable from today's capture.
## DIP_RIP RE-ANCHOR — SWEPT AND REFUTED (8/19, "run the sweep now")

data/killtests/diprip_reanchor_sweep_20260819.py — 2,086 halt-rungs, 420 name-days, both arms
through E3. STATIC 527 fires +$2,059 (+$3.91/tr, 49% green) vs RE-ANCHOR 982 fires +$2,041
(+$2.08/tr, 40% green). Pre-registered reading (B>A total AND B $/tr>0): **RE-ANCHOR LOSES** —
doubles the fires, adds zero dollars; the marginal late-rung fills are dilution. ZSTK's +$35
was a true specimen of a flat population. Secondary also refuted: no rung-maturity gradient in
dip rates (65/59/53/61%). LIMITS in the artifact (sheet proxied by first-halt close; gap-vs-halt
ambiguity; up-close proxy). DO NOT re-propose without new evidence.
* RATION FINDING (Marcos 8/19: "it needs more attempts" — and the distribution agrees):
  static fires are median -$0.01 / mean +$3.91 = pure positive skew; skew pays only through
  attempt volume. The cohort split: rung-1-only (all the live one-watch ration permits) =
  +$0.68/tr n=220; rung 2+ (BANNED by the ration) = +$6.22/tr n=307, 51% green; gaps >8min dead.
  These are dips to the ORIGINAL anchor later in the day — NOT re-anchoring (refuted above).
  ⚠️ POST-HOC SLICE — pre-registered as a FORWARD test per story discipline: multi-watch shadow
  rows for N sessions; the rung-2+ cohort reproduces on unseen tape or dies. Proposal for the
  Monday halt-config review (Marcos rules): keep anchor + 10-min window, drop one-watch/day cap,
  consider gap<=8min filter. Nothing ships from the backtest slice.
## RUNWAY-FOR-RUNNERS — BOTH ARMS REFUTED (8/19, "run it")

data/killtests/runway_runner_arms_20260819.py — 108 runway_reject fires, 6 sessions, E3.
LIVE(refuse-all) $0 · A stale-rung demotion **-$442.08** (41 takes, 1 green) · B runner
exemption >=50% run **-$306.55** (23 takes, 13 SKK-class losers swallowed). Pre-registered
win condition (total>0 AND zero SKK-class takes): BOTH FAIL.
**The inversion:** a rung sitting 1-5% overhead on a name that has ALREADY run is not stale
ink — it is where the move dies. That cohort is the WORST in the dataset (-$10.78/tr). The
"map is behind the tape" reasoning was backwards; TNON->$17 was the exception (and TNON's own
replay stopped out, per the morning trace).
**RUNWAY IS SETTLED — DO NOT RELAX.** Three independent measurements now: 95-refusal replay
(net-saves ~$544), today's live cohort (+$3.89 n=11, flat), both engineered escape hatches
deeply negative. Any future proposal must beat this bar with new evidence.
**Highest-value open gate question is now MIN-STOP** (+$177 left behind on 8/19 alone, n=22,
14 rows stop-less so 10% assumed) — the multi-day sweep is the next study, same method.
## RUNWAY — FOUR RELAXATIONS TESTED, FOUR REFUTED (8/19)

E3 replay, 108-109 runway_reject fires, 6 sessions. LIVE (refuse all) = $0 baseline.
  take-all            -$543.66   (morning 95-fire replay)
  A stale-rung demote -$442.08   41 takes, 1 green
  B day-gain >=50%    -$306.55   13 SKK-class swallowed
  C CROWN-exempt       -$67.47   36 takes, 11 SKK-class  (Marcos: "letting crown names go")
**The crown DOES discriminate** — crowned refusals -$1.87/tr / 36% green vs non-crowned
-$6.39/tr / 17% green — but the cohort is still net-negative and takes 11 near-full-R losses.
Nine crowned refusals paid $20+ (FGI +$79.92, BANL +$41.26, MSS +$39.73, LFS +$34.53,
CDTG +$28.86); they are outnumbered.
**RUNWAY STANDS.** Any future proposal must beat: 4 arms, all negative, ~$500 of net saves.
* POST-HOC ONLY, NOT A FINDING: crowned + MAJOR + rr 0.50-0.75 recurs among the winners
  (FGI .75, IPST .63, CDTG .59, EJH .50). Found AFTER seeing results — the re-anchor trap.
  Needs pre-registration + its own cohort before it is worth another sentence.

## EXITS — "LET WINNERS RUN" REFUTED (8/19, crown_let_it_run_20260819.py)

272 era trades replayed, trail width the ONLY variable, crowned (n=86) vs non-crowned control
(n=186). T10 (current) beats T15/T20/T30/NONE on BOTH cohorts; widening costs -$549 on crowns.
Mean give-back from the run-high RISES with trail width (43->50): these names round-trip, so a
looser leash exits FURTHER down the retrace, it does not capture more move. Medians identical
across arms — the median trade never reaches the +10% tier, so trail width only touches winners.
NOT crown-specific: widening hurts crowns MORE than non-crowns. Also: crowned trades underperform
non-crowned at the same exit ($1.98 vs $2.43/tr) — the crown identifies entry-worthiness, not
holding power. LIMITS: hidden_entry is 66/86 of the crowned cohort and its figures are UNVERIFIED.
* EXPLORATORY (post-hoc): tighter trails (T05/T07/T12) also lose to T10 on all cohorts.
  T10 appears to be a local optimum on this data — NOT a claim, no pre-registration.


## 8/20 — THE "APPROVED NUMBER, UNEXAMINED MEASURE" CLASS (for discussion)

Three instances found in one session. Same disease, three places: a threshold Marcos approved
is attached to an implementation nobody examined. All three verified in-session, none shipped.
REPRODUCE: `python3 rig/test_premkt_rulings_20260820.py` (the shipped fixes) ·
`python3 data/killtests/premkt_minstop_20260820.py` (the premarket ladder) ·
`grep -n 'PRE_MIN_DVOL\|_pm_session_dvol\|IGNITION_VWAP_TOL\|VWAP_SIDE_SIZING' marcos_trading_bot.py`
(the three constants and their measures).

1. **PRE_MIN_DVOL = $250,000** [reproduce: `grep -n 'PRE_MIN_DVOL' marcos_trading_bot.py` and
   `sed -n '/def _curl_feed/,+6p' marcos_trading_bot.py` for the 15-min default] — constant's own comment says "cum session $ volume floor" and
   its 7/25 calibration cites "cum $vol"; the code calls `_curl_feed(entry[0])` with no `n`,
   whose docstring reads "step consumers use the 15-min default" (CURL_SOURCE=alpaca verified
   live). So a session-cumulative threshold is compared to a 15-MINUTE window. Measured on
   8/20's 15 `premkt_thin` refusals vs true session-cumulative from SIP: 8 of 15 clear $250k
   on the intended measure (PWCM $2.81M/12.9x, CDTG $3.21M/19.5x, AZI $1.05M/16.9x, RCON x3,
   IVF, WETO). The other 7 were genuinely thin (GRAN $8k, RETO $23k, INLF $42k) — the floor's
   INTENT is sound, the measurement is not. Fix built, not shipped (needs a cumulative source:
   the 10s hot feed's own comment caps deep requests at 720 buckets/2h).

2. **Ignition stack arm — zero tolerance while its sibling has 2%.** Same gate
   (~:11148): `_ig_vwap_bad = price < vwap*(1-IGNITION_VWAP_TOL)` (2% band) vs
   `_ig_stack_bad = _e9 < _e20` (no band). ZSTK 8/20 09:31:16 refused at ema9 4.0749 vs ema20
   4.0817 = $0.0068 (0.167%, arithmetic re-run). Structural aggravator: the stack is EMA9/20
   on 3-MIN bars seeded with premarket closes, and at 09:31 the first RTH 3-min bar is still
   incomplete (dropped by `[:-1]`) — so the gate judged the OPEN on PREMARKET CLOSES ONLY.
   Reconstruction positive control PASSED (rebuilt ema9 4.0749 vs 4.0749 stamped, ema20 4.0818
   vs 4.0817, seed n=90 vs 90). Study built: data/killtests/ignition_stack_grace_20260820.py
   (natural experiment — the gate's reject rows begin 8/19, but pre-gate `triggered_ignition`
   fires include stack-down cases that CONVERTED). BLOCKED: `triggered_ignition` rows carry
   base_hi but NO stop, and the stop is `base_lo*(1-ZONE_STOP_BUFFER)` over
   IGNITION_BASE_LOOKBACK=4 1-min bars — rebuildable from tape; finish before grading.

3. **VWAP_SIDE_SIZING: env 0.25, approved 0.5.** Code default 0.5; the block's own kill-test
   note (vwap_sizing_20260808) says "FIELD entries above session VWAP take HALF size",
   half-above +$912 vs actual +$393, and Marcos's ruling is recorded as "Go with B". Railway
   runs 0.25 (verified). Only trace of the quarter: EYES_AUDIT_20260815 line "VWAP-side sizing
   0.25 field | 8/8 | ALIVE" — an OBSERVATION, not an authorization
   ([[feedback_auditor_cannot_authorize_behavior]]). Deduped cohort: 24 filled trades on
   cut names = +$23.85 at quarter; excluding the 8 fake-P&L hidden_entry rows = +$8.61 on 16
   trades; 8/20 trades missing from the pull. WEAK/small-n — the doubling assumption is an
   approximation (tier quantities round). PROPER TEST QUEUED: replay the cohort at
   0.25/0.5/1.0 through the REAL sizing chain, train/OOS, hidden_entry excluded.

DISCUSSION QUESTION FOR MARCOS: every gate/threshold in the book was approved as a NUMBER.
How many are attached to a measure nobody has read? Candidate sweep: enumerate every
env-tunable threshold, and for each state (a) what it claims to measure, (b) what the code
actually reads, (c) whether a ruling exists for the live value. That is a build, not a chat —
but today produced three hits in one session, which is the argument for doing it.
