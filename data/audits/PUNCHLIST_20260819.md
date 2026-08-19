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
* Caveat on record: Kev-side clock = min_since_sess_hi at the located fill (analog, not the
  identical instrument; fresh-high fills read ~0). Direction robust, medians not gospel.
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
  (waits for H/W, arrives late = the losing fast cohort). This is the Hidden Entry
  Architect's exact charter (8/14: anticipation, not confirmation) with its target now
  measured to the second. Three days' evidence, no OOS wall — nothing ships from this.
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

