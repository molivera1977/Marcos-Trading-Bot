# LIVE-BOARD SYMPATHY STUDY — 8/17/26

Removes the load-bearing caveat from the prior night's one surviving edge. `seq_cross_ticker_20260817.md`
graded **H1 LEADER-FOLLOWER (sympathy window) = BOARD-SIGNAL** ($+41.22/tr vs $+15.83, p=0.001) —
but its "leader" was a **within-universe proxy** (gain>=40% runners only), not the live scanner board.
This study rebuilds the board from the dashboard's **durable decisions archive** — the bot's REAL-BOARD
view — and re-runs H1 against it.

Script: `seq_live_board_sympathy_20260817.py` · run: `seq_live_board_sympathy_20260817_run.txt` ·
machine: `seq_live_board_sympathy_20260817_out.json` · archive cache: `archive_cache/*.json`.
Engine chain imported UNCHANGED via `sequence_mining_pilot_20260817.py` (break-attack + grinder,
E3 $500 live-parity exits, 1,021 deduped fires). **Analysis only — no bot edits, no env changes.**

---

## 1. ARCHIVE SCHEMA INVENTORY

Endpoint: `GET /api/decisions_archive?date=YYYY-MM-DD&limit=20000`, header `X-Dashboard-Secret`.
Response: `{date, total, rows[], by_status{}, triggered_by_hour{}}`. **38 days returned data,
2026-06-29..2026-08-17; 35 are substantive (>=500 rows) — 8/09, 8/15, 8/16 are 2-4-row weekend stubs.**
96 distinct statuses on 8/14 alone. Every row carries `date`, `recorded_at`, `status`, `ticker`,
`time` (ET, 12-hour, e.g. `09:33:04 AM`); all other fields are per-status.

| status | rows (all cached days) | extra fields | what it reconstructs |
|---|---|---|---|
| `consolidating` | 93,370 | `price`, `rng_pct`, `vwap`, `w_high` | per-cycle scan tick on a watched name -> MEMBERSHIP |
| `daily_loaded` | 53,859 | (none) | name's daily bars loaded -> board JOIN time |
| `watching` | 13,654 | `price`, `vwap` | per-cycle scan tick -> MEMBERSHIP |
| `break_armed` | 9,378 | `price`, `w_high` | **live break detection on a real-board name -> LEADER/BREAK events** |
| `orb_break_armed` | 13,563 | `orb_high`, `price` | ORB break detection -> LEADER/BREAK events |
| `lens_focus` / `lens_unfocus` | 4,895 | `dist_pct`, `zone`, `zone_px` | lens attention -> membership + attention |
| `halt_suspect` | 4,385 | `gap_secs`, `held`, `last_bar_ts` | feed-gap stamp on a watched name -> membership |
| `broke_below_vwap` | 2,947 | `price`, `vwap` | per-cycle structural stamp -> membership |
| `leader_armed` | 103 | `why` (`fresh_highs`, ...) | explicit LEADER/CROWN arm event |
| `crown_eod_report` | 300 | `captured_usd`, `offered_pct`, `trades`, `refusals_post_crown`, `worst_map_age_min`, `worst_map_dist_pct` | EOD crown scorecard per crowned name |
| `board_funnel_fallback` | 22 | (none) | sentinel `_BOARD` — **counter only, no roster** |
| `lens_dark` | 81 | `n` | sentinel `__LENS__` — **count only, no per-name list** |

### HONEST SCHEMA FINDING — there is NO board-snapshot row

**No status emits the scanner's membership list at a point in time.** `board_funnel_fallback` and
`lens_dark` are counters on sentinel tickers (`_BOARD`, `__LENS__`), not rosters. Board membership
must be **INFERRED from per-name rows**. The bot cycles every watched name through
`consolidating`/`watching`/`break_armed`/`daily_loaded`/`halt_suspect`, so the defensible
reconstruction used here is:

* **BOARD MEMBERSHIP (coarse — minute-by-minute is NOT achievable):** a name is on the board at
  time *t* if it has at least one per-cycle row within ±60 min of *t*.
  **LIMITATION:** a name the bot loaded but which emitted no cycle row in a given hour is invisible.
  Membership is a **LOWER BOUND** and its resolution is the cycle cadence, not the minute.
  The coarsest fallback (set of all names with any row that day) is used for leader eligibility.
* **REAL-BOARD BREAK EVENTS:** `break_armed` / `orb_break_armed` are the bot's own live break
  detections on real-board names, timestamped in ET. Used for the Arm A leader.
  **LIMITATION:** they carry `price`/`w_high` but **no volume**, so the prior study's burst-volume
  qualifier cannot be applied to non-universe board names. Arm B preserves burst-volume by
  restricting the bars-side burst leader to names that are on the real board.
* **LEADER/CROWN:** `leader_armed` (with `why`) and `crown_eod_report` are the explicit real-board
  leader events. `leader_armed` is **sparse (14 rows on 8/14) and mostly PREMARKET**, so it is
  reported here, not used as the H1 leader.

---

## 2. OVERLAP AND OOS SPLIT

| set | count | range |
|---|---|---|
| bars10s universe cache | 62 dates | 2026-05-18..2026-08-14 |
| archive (substantive) | 35 dates | 2026-06-29..2026-08-17 |
| **OVERLAP** | **34 dates** | **2026-06-29..2026-08-14** |

Archive-only: `2026-08-17` (today, no bars). Bars-only: 28 dates 2026-05-18..2026-06-26 (pre-archive).
34 >= 12, so the wall is real, not faked. Chronological, 1/3 held out (same discipline as the prior study):

- **MINE: 23 dates 2026-06-29..2026-07-30**
- **HOLD-OUT: 11 dates 2026-07-31..2026-08-14**
- **BOUNDARY: `2026-07-30 | 2026-07-31`**

### Board coverage — the caveat was REAL and it was large

**Mean real board = 113.5 names/day vs universe proxy 11.7 names/day — the real board is 9.7x wider.**
31/34 overlap dates have a post-09:30 real-board break leader (6/29, 6/30, 7/01 have none).
**On only 10 of those 31 dates is the real-board leader ALSO a universe (40%+ runner) name — the
proxy would have named a DIFFERENT leader on 21 of 31 dates (68%).** The prior study's leader was
usually the wrong name.

591 of the 1,021 graded fires fall on the 34 overlap dates.

---

## 3. THE KEY COMPARISON — within-universe vs real-board, IDENTICAL dates and split

Both columns below are computed on the **same 34 overlap dates with the same 7/30|7/31 boundary**,
so the comparison is apples-to-apples (the prior study's published numbers used 62 dates and an
18-date hold-out; they are quoted separately for reference).

| | prior study (62d, published) | within-universe (34d, same split) | REAL-BOARD Arm A | REAL-BOARD Arm B |
|---|---|---|---|---|
| leader definition | first 40%-runner burst-break | first 40%-runner burst-break | first REAL-BOARD `break_armed` | first burst-break **among real-board names** |
| MINE sympathy N / $/tr | 228 / $+32.80 | 131 / $+31.11 | 19 / $+35.33 | 61 / $+23.57 |
| MINE outside N / $/tr | 464 / $+26.85 | 262 / $+15.17 | 134 / $+14.61 | 105 / $+13.70 |
| MINE lift | $+5.95 | $+15.95 | $+20.72 | $+9.87 |
| **HOLD-OUT sympathy N / win / $/tr** | **101 / 79% / $+41.22** | **63 / 79% / $+38.18** | **12 / 67% / $+36.03** | **28 / 82% / $+38.18** |
| **HOLD-OUT outside N / win / $/tr** | **228 / 64% / $+15.83** | **135 / 68% / $+17.14** | **56 / 66% / $+17.84** | **40 / 55% / $+9.05** |
| **HOLD-OUT lift** | **$+25.39** | **$+21.04** | **$+18.19** | **$+29.13** |
| **null p (hold-out, 5000x)** | **0.001** | **0.011** | **0.211** | **0.127** |
| pooled lift (all 34d) | - | $+17.57 | $+20.04 | $+15.75 |
| pooled null p | - | - | 0.076 | 0.046 |

Hold-out day-level (Arm B): sympathy day mean $+118.78, day median $+104.53, **worst day $-77.79**
(9 days); outside day mean $+32.93, day median $+46.61, worst day $-151.48 (11 days).
Arm A: sympathy day mean $+61.76, median $+50.65, **worst day $-74.83** (7 days).

### Does the effect SURVIVE, GROW, or SHRINK?

**The effect SIZE survives — the STATISTICS do not.** Both real-board arms keep the direction and a
lift of the same magnitude as the proxy ($+18 to $+29/tr vs $+21 within-universe on the same dates).
Arm B's hold-out lift is actually the largest of the four columns. So this is **not** an artifact of
the 40%-gain filter in the sense of the direction being manufactured.

But the pre-registered null fails in both real-board arms: **p=0.211 (A) and p=0.127 (B)** against
p=0.011 for the within-universe run on identical dates. The cause is **power, not reversal**: adding
the real-board membership requirement cuts the hold-out sympathy cohort from **63 fires to 28 (B) /
12 (A)**, because most universe fires are on names the archive shows the bot was NOT cycling at that
minute. At N=12-28 the within-date shuffle cannot separate the effect from "this was a hot half-hour."

**Neither real-board arm clears the p<0.05 bar. The prior BOARD-SIGNAL grade does not carry over to
the live board on this evidence.**

---

## 4. TRADEABLE FRACTION — the harder finding

A sympathy-window fire could only ever become a lane if (a) the name was on the bot's real board at
fire time and (b) it passes the live liquidity floor `_ambient_dvol_ok` (`marcos_trading_bot.py:3983`):
median $-volume of the trailing 10 completed bars >= `AMBIENT_DVOL_MULT`(15) x `MAX_TRADE_DOLLARS`($500)
= **$7,500**. Applied here to **10s** bars, i.e. a ~6x STRICTER floor than the live 1-min version —
so these are conservative LOWER bounds.

| arm | window fires (any name) | on real board at fire time | + passes liquidity floor | tradeable cohort |
|---|---|---|---|---|
| A | 92 | 31 (34%) | **13 (14%)** | N=13, win 54%, **$/tr $+0.88**, median $+16.38, total $+11.38 |
| B | 196 | 89 (45%) | **48 (24%)** | N=48, win 62%, **$/tr $+3.49**, median $+19.39, total $+167.37 |

**Only 14-24% of sympathy-window fires were fires the bot could actually have taken, and that
tradeable slice earns $+0.88 to $+3.49 per trade — against $+35.60/$+28.16 for the unfiltered
window cohort.** The sympathy premium lives almost entirely on fires that fail the liquidity floor.
Whatever H1 is measuring, it is largely **thin-tape** — which lands on the same rock as the 8/14
finding that thin-tape effects do not survive the real sizing chain.

---

## VERDICT: **UNDERPOWERED** (with a hard secondary refutation)

- **On the H1 effect itself: UNDERPOWERED.** The direction and magnitude survive the removal of the
  40%-runner caveat (hold-out lift $+29.13/tr, Arm B, 82% win on 28 fires), but **no real-board arm
  clears its pre-registered null (p=0.211 / p=0.127)**, and the hold-out cohorts are 12 and 28 fires.
  I will not upgrade a sliver: this is not a confirmation, and it is not a refutation of the effect.
  It needs more overlap days — the archive only starts 6/29, and every additional trading day adds
  ~1-3 qualifying sympathy fires. A re-run at ~60 overlap dates is the honest next gate.
- **On whether this could become a LANE: SHRINKS-TO-NOISE.** The tradeable fraction is 14-24%, and
  that tradeable cohort earns **$+0.88-$3.49/tr**. That number is not underpowered ambiguity — it is
  a measured near-zero on 48 fires. **Do not build a sympathy-window lane on this.**
- Pooled Arm B p=0.046 is noted and **not** counted: pooling includes the mined dates and is not an
  out-of-sample result.
- **The prior study's `BOARD-SIGNAL` grade for H1 should be read down to a hypothesis**, and its
  caveat is confirmed as material in one specific way: **the proxy named the wrong leader on 68% of
  dates (21/31)** while still producing a stronger p-value than the correct-leader run — a textbook
  sign that the proxy's significance was partly borrowed from the 40%-gain filter itself.

## Officers touched

Side Marshal (real-board context stamps), Seam Scientist (OOS wall + hypothesis read-down),
Statistician (ledgered artifacts; the prior H1 number is now qualified in the record),
Dashboard Curator (the decisions archive is confirmed as a research-grade source **but has no
board-roster row** — registered as a display/telemetry gap), Quartermaster (38 archive days now
cached locally at `data/killtests/archive_cache/`), Handicapper (selection implication: the
sympathy premium is thin-tape), Convexity Trader (judged on mean-after-floor, not win-rate),
Strength Ombudsman (clean — no strength refused; the shrink is a liquidity floor, not a bias),
Blast Radius Auditor (n/a — analysis only, no live-path change).
