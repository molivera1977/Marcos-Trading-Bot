# FABLE REVIEW — 7/26: the stored-P&L correction, and what it exposes

**Opus ran every check below and both verifications. Fable renders the verdicts in §7.**
Standing rules apply: [[feedback_replay_rig_gate]], [[feedback_backtest_before_recommend]], DRY_RUN only.
Session date: 2026-07-26 (Sun). Market closed. No writes were made to the live store. Nothing pushed.

---

## 1. TL;DR

The trade store has been reporting the bot's P&L wrong since 7/14. Corrected, the whole book goes
from **−$108.79 to +$2.25**. But the correction is **not** good news, for two reasons:

1. The full new era (7/13–7/24) is still **−$39.39**, and that figure is a **FLOOR** — 47 affected
   records are permanently uncomputable.
2. The bug specifically erased the **runner leg**, i.e. the exit-quality signal. Every exit-doctrine
   conclusion drawn on ≤7/20 data used corrupted inputs.

---

## 2. The bug

Pre-`cc22b36` (committed **2026-07-20 17:10:56 −0400**), `_blended_pnl` took the runner-leg share
quantity from the monitor loop's `remaining_shares`, which exit branches zero for bookkeeping
**before** the P&L math ran. The runner leg contributed exactly **$0**. Stored `pnl` on an affected
record is therefore the **scale-out legs only**.

Marcos found this on 7/20 from his dashboard card. It was fixed the same day — **forward-only**.
Already-stored records were never re-derived. That backlog is what this review is about.

### The anchor trade, hand-checkable

```
BIYA 2026-07-20   entry $7.5000 (position_size 487.50 / 65 sh)   exit $6.87   65 sh
  scale leg   32 sh × ($8.1101 − $7.50) = +$19.5232
  scale leg   16 sh × ($8.4300 − $7.50) = +$14.8800
  partials subtotal                     = +$34.4032  → STORED $34.40  (runner = $0)
  runner qty  65 − 48 = 17 sh
  runner leg  17 sh × ($6.8700 − $7.50) = −$10.7100  ← erased by the bug
  CORRECTED                             = +$23.69    (delta −$10.71)
```
$23.69 independently matches the value documented as "true" in the `_blended_pnl` docstring.

---

## 3. The numbers (dollars)

| figure | stored | corrected |
|---|---|---|
| whole book (n=193, 7/07–7/24) | **−$108.79** | **+$2.25** (floor) |
| **full new era (n=139, 7/13–7/24)** | **−$150.43** | **−$39.39** (floor) |
| era window 7/13–7/16 (n=99) | +$29.30 | +$167.87 (floor) |
| book win rate | 58.4% (111W/79L) | 57.4% (109W/81L) |
| era $/trade | — | −$0.28 |

**Two trades were logged as wins but were losses** — both trailing-stop exits:
CLRO 7/15 **+$14.45 → −$0.31**; JLHL 7/17 **+$15.50 → −$5.12**.

**Shape of the era matters more than the total.** 7/13 (+$234.15) and 7/20 (+$123.91) are +$358.06
between them; **all eight other era days combined are −$397.45**. The most recent 40 trades
(7/17→7/24) are **−$207.26**. The flattering +$167.87 window happens to contain both carry days and
stops immediately before the worst one.

---

## 4. What is permanently unknowable

`partial_fills` was not persisted until **`3cb9880` (7/13 15:53 ET)**. 80 records lack the field
entirely. **Field-absent ≠ no scale-outs** — Opus got this wrong on the first pass; the blind
replication agent caught it.

The exit label self-witnesses partials: `"Trailing stop 📉" if partial_taken else "Stop loss 🛑"`
(`marcos_trading_bot.py:6025`). So the 80 split cleanly:

- **33 provably UNAFFECTED** (24 `Stop loss 🛑` + 9 `3:45pm time stop`)
- **47 provably AFFECTED but UNCOMPUTABLE** (27 `Trailing stop` + 20 `HEALTH FOLD`) — both branches
  zero `remaining_shares`, so the runner leg was definitely dropped, but the scale-out quantities
  and prices **were never written to disk**. No analysis recovers them.

**17 of the 47 are on 7/13** — inside the era AND inside the 99-trade window.

Gap sizing — **HYPOTHESIS, not measurement**: mean-delta extrapolation gives ~**+$62**; an
independent runner-fraction method gives **+$71 to +$88**. Direction is positive with reasonable
confidence (Trailing negative in only 7 of 21; HEALTH FOLD 1 of 12), magnitude is not knowable.
Deltas on the computable sample span −$20.62 to +$16.40.

**Consequence: the full era is somewhere between −$39.39 and roughly break-even, and cannot be pinned.**

---

## 5. Verification — two agents, separate contexts

Per [[feedback_signoff_requires_artifact]]. Both read-only; neither could write or POST.

### Agent A — BLIND REPLICATION (never shown Opus's figures)
Given only the raw store snapshot + the repo. Independently derived:

| | Opus | Agent A |
|---|---|---|
| affected records | 36 | **36** |
| total correction | +$111.04 | **+$111.05** |
| book corrected | +$2.25 | **+$2.26** |
| era 7/13–7/16 | +$167.87 | **+$167.87** |
| full era 7/13–7/24 | −$39.39 | **−$39.38** |
| sign flips | CLRO, JLHL | **same two** |

It also went further than Opus: read the pre-fix source to confirm *which* exit branches zero
`remaining_shares`, explaining why the `3:45pm time stop` records are clean. **And it caught the
`partial_fills`-absent error in §4** — the single most important finding in this document.

### Agent B — ADVERSARIAL AUDIT (instructed to refute, default to "refuted")

- **CONFIRMED** — no update path exists (swept the whole codebase, not just the three handlers).
- **CONFIRMED** — every headline dollar figure, reproduced to the cent.
- **REFUTED** — the deploy boundary. `cc22b36` committed **17:10:56**; ZYBT recorded **15:45:02** =
  **1h26m PRE-fix**. ZYBT is clean only because `3:45pm time stop` never zeroed `remaining_shares` —
  an exit-branch artifact, not deploy evidence. True post-fix sample is **n=6, not 7**, and the
  "method produces no false positives" claim is **withdrawn**.
- **PARTIALLY REFUTED** — the count is **37, not 36** (GLXG 7/17; envelope too loose). Worth **$0.22**.
- **PARTIALLY REFUTED** — `position_size = entry × shares` is **false for 46 records** (pre-7/11 it
  was the flat $100 reservation cap) and the validation was circular. **$0.00 impact** here, but the
  same recovery would **silently return the trigger price instead of the fill in live mode**
  (`_reserved` at `:7354` computed before `entry_price` is rebound at `:7435`; holds only because
  DRY_RUN's fill equals the trigger at `:5629`). Do not reuse on live-mode records.

### 🚫 One claim Opus made in conversation is REFUTED — do not cite it
**"vwap_reclaim is the era's worst lane by ~8.5×."** It exists only in the 7/13–7/16 window; on the
**full era it is 1.81×**. Dropping each lane's worst single trade → 3.20×; dropping ignition's worst
three → **ignition flips to +$22.04**. It is also **tautological**: only **8 of 32** vwap_reclaim
trades have any partial fills, so the correction could not move that lane by construction. Opus
reported the full era for P&L and silently switched to the short window for this ratio.

---

## 6. The context that reframes all of the above

Marcos's claim, checked against each day's own log: **there is no clean trading day in the era.**

| day | corrected | the defect, from that day's log |
|---|---|---|
| 7/13 | +$234.15 | whitelist silently dropping `entry_type` since 7/11; logs rotated; CRMT bars never archived |
| 7/14 | −$1.12 | NVVE stop-blind 6 min (429 storm); ELWT BE floor leaked; 99K log msgs dropped; mid-day push force-closed 6 positions |
| 7/15 | −$92.38 | **already declared "VOID for strategy"** — B14/B15/B16 |
| 7/16 | +$27.22 | **stream died silently at the 9:31 open, zombie 45 min**; 3 Webull kicks; PM-VWAP silently falling back to RTH-only |
| 7/17 | −$200.62 | **"sentinel poisoned the seed → Kev's picks went uncaptured"**; tier-1 seeded zero Kev picks **every day** |
| 7/20 | +$123.91 | **38 silent vendor kicks ≈ 32% of RTH deaf**; FGMC poisoned the batch subscribe (0 subscribed) |
| 7/21 | −$40.45 | **10s machines fired 0× all day**; missed all 3 rockets |
| 7/22 | −$7.68 | #68 downshift, #81 amnesia, #84 re-read 503-starved (0 v2 maps), ghost session from 12:27 |
| 7/23 | −$55.78 | **recorder capturing median 10.6% of tape** vs Alpaca 94.7% |
| 7/24 | −$26.64 | curl lanes starved: replay says **+$100.69** available, **0 fires** live |

Five of these are **not day-defects but window-spanning**: the ~10.6% recorder capture ("the curl
lanes have been starving on ~10%-complete data all along"), entry VWAP being the wrong line for two
weeks (27% of entries flipped side), tier-1 seeding zero Kev picks every day, 32% of RTH deaf, and
the whitelist dropping fields since 7/11 (same class as this P&L bug).

**So the corrected −$39.39 is more accurate and no more meaningful.** It measures a system that was
blind to part of the tape — sometimes 90% of it — every single day.

---

## 7. VERDICTS NEEDED FROM FABLE

### Q1 — Is the era baseline salvageable as a measurement, or do we formally void it? [HIGHEST]
**Evidence:** §4 (47 uncomputable, 17 inside the window) + §6 (no clean day).
On 7/15 Marcos already ruled one day VOID and restarted the strategy-evaluation clock — that restart
never completed (7/16 opened with a dead stream). **Question:** do we void the era for strategy
purposes and define what "clean day #1" requires, or keep −$39.39 as a working floor? This decides
whether *any* strategy tuning right now is legitimate, and it gates Q3.

### Q2 — Monday 7/27: eleven changes land simultaneously with zero live exposure. Ship or split?
**Evidence:** 11 commits between 7/24 22:13 and 7/25 01:12, all after Friday's close, none yet
exposed to live tape — Alpaca reader end-to-end (`b1b6676`), premarket paper-trading regime (4
commits), hidden entry lane (`58c9816`), float cap 20M→30M, chart-gate 2% band (`3237bae`),
stale-price guard (`a4fe777`).
**Question:** this looks like a violation of the one-change-set-per-night rule
([[feedback_replay_rig_gate]]), and it lands the *data-layer migration* — the fix aimed at the worst
defect in §6 — at the same time as four behavioral changes. If Monday goes wrong (or right),
attribution is impossible. Split, or accept and define per-change acceptance checks up front?

### Q3 — Which prior verdicts must be re-run on corrected P&L?
**Evidence:** `RESULTS_LEDGER.md`. At minimum these consumed the corrupt `pnl`:
- **7/23 capture-ratio verdict** — its own caveat says *"28/102 pnl cross-check fails unexplained."*
  That is almost certainly this bug (Opus's 7/14–7/16 buggy count is also 28, though the record ID
  lists were **not** matched — **[UNVERIFIED]**).
- **7/23 quarters / exit-counterfactual kill-test** — built on the same 47 ≥1R-potential trades.
- **The era red-day diagnosis** — "entry quality, not exits… exits beat every alternative by $1,057"
  and "wins +0.71R vs losses −1.12R", both currently tagged [UNVERIFIED] in
  [[project_new_era_baseline]].
**Question:** priority order, and is any of it worth doing *before* Q1 is settled?

### Q4 — Store write-path: permanent ledger, or build a merge endpoint?
**Evidence:** `/api/record_trade` appends and **dedups by trade_id** (silent no-op on re-post);
`/api/trades` is GET-only; `/api/trades/clear` wipes all 193. Confirmed by Agent B across the whole
codebase. An out-of-band path exists (edit the `/data` volume JSON + restart) and was **not** used.
**Question:** is ledger-at-analysis-time the permanent answer, or do we build a merge/patch endpoint?
Note the 7/24 wipe scar and [[feedback_replace_endpoint_merge_only]] — any such endpoint must be
merge-only by construction.

---

## What Fable does NOT need to review
The correction arithmetic itself (independently replicated + adversarially audited, §5), the ledger
mechanics, or the classification method. Those are settled. Fable's scope is Q1–Q4.

## Artifacts
- `data/killtests/pnl_runner_leg_correction_20260726.md` — full per-trade ledger, method, caveats
- `data/killtests/pnl_runner_leg_correction_20260726.json` — `{trade_id: corrected}` for code
- `data/killtests/RESULTS_LEDGER.md` — 7/26 row + superseding 7/26 review row
- Memories: [[project_pnl_correction_ledger]], [[project_new_era_baseline]]

**State:** files written to the working tree, **not committed, not pushed**. Live store untouched
(193 records, still serving −$108.79, and always will).
