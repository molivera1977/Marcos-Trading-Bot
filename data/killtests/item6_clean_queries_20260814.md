# Item 6 — Clean Queries (strict basis), 2026-08-14

Statistician officer. Read-only re-grades on fictional-fill-free numbers.
Sources: `data/history/VERIFIED_BOOK.json` (pnl_strict/charitable/raw; fills cat verified_strict / verified_generous_only / FICTION) joined by trade_id to the live trade store (`/api/trades`, pulled 8/14 12:31 ET, 473 rows; join 141/141 for Q1, zero misses). VERIFIED_BOOK covers 7/13–8/13; today (8/14) excluded.

## Query 1 — LEADER MERITOCRACY cohort re-run (the +$635 claim stays SUSPENDED)

Cohort: all VERIFIED_BOOK trades 8/5–8/13 (n=141, strict computable on all 141).
IMPORTANT COVERAGE FACT: `entry_crown=true` stamps exist ONLY 8/10 onward (73 store rows, dates 8/10–8/14; zero on 8/5–8/7). So "uncrowned since 8/5" mixes 3 pre-stamp days; the 8/10+ table is the apples-to-apples read.

### 8/5–8/13 (full period)
| Cohort | Lane | N | Strict $ | Charitable $ | Raw $ | Mean strict/trade |
|---|---|---|---|---|---|---|
| Crowned | ALL | 67 | +487.59 | +547.36 | +603.84 | +7.28 |
| Crowned | hidden | 62 | +403.13 | +452.51 | +499.98 | +6.50 |
| **Crowned** | **ex-hidden** | **5** | **+84.46** | **+94.85** | **+103.86** | **+16.89** |
| Uncrowned | ALL | 74 | +45.06 | +336.17 | +484.61 | +0.61 |
| Uncrowned | hidden | 41 | +192.78 | +467.94 | +605.46 | +4.70 |
| Uncrowned | ex-hidden | 33 | −147.72 | −131.77 | −120.85 | −4.48 |

### 8/10–8/13 only (crown stamp actually live)
| Cohort | Lane | N | Strict $ | Mean strict/trade |
|---|---|---|---|---|
| Crowned | ALL | 67 | +487.59 | +7.28 |
| Crowned | ex-hidden | 5 | +84.46 | +16.89 |
| Uncrowned | ALL | 17 | +24.31 | +1.43 |
| Uncrowned | hidden | 5 | −27.83 | −5.57 |
| Uncrowned | ex-hidden | 12 | +52.14 | +4.34 |

**Answer to the question asked (crown value EX-hidden, strict basis): +$84.46 on n=5 (+$16.89/trade), vs uncrowned ex-hidden +$52.14 on n=12 (+$4.34/trade) in the stamp-live window.** Positive, but n=5 is anecdote-grade — this measures nothing about the mechanism's edge, only that the crowned ex-hidden trades happened to pay this week. Crown cohort remains ~93% hidden-lane by count (62/67), so the meritocracy evidence base is still hidden-contaminated exactly as suspected; the isolated ex-hidden slice is too thin to grade. Doctrine stands on Marcos's word; this is measurement only.

Caveats: (1) crowned-vs-uncrowned is SELECTION, not treatment — crowns go to names already ripping; positive crowned P&L cannot be read as privilege value. (2) 8/5–8/9 "uncrowned" rows may include trades that would have been crowned had the stamp existed (or crowns not yet rehydrated to durable rows). (3) The suspended +$635 claim is not re-certified by anything here.

## Query 2 — 7/26 EXIT DOCTRINE before/after (OBSERVATIONAL, NOT CAUSAL)

Ledger context (RESULTS_LEDGER.md, 7/26 block): the exit counterfactual verdict was "exits are NOT ignition's problem — do not touch"; what shipped 7/26 on the exit path was the EXIT-PATH CONTRADICTION REVIEW + 2 finishers (plus the wider 11-change bundle). So "after" reflects the whole 7/26 change-set AND a different market/lane mix — this is a before/after read only. Do not attribute deltas to exits causally.

| Window | N | Strict computable | Strict $ | Charitable $ | Raw $ | Mean strict/trade | Winners (strict) | Winners banking ≥1 tier | Runner capture (median / mean)* |
|---|---|---|---|---|---|---|---|---|---|
| PRE (7/13–7/24) | 139 | 74 (53%) | −371.98 | −392.38 | −39.39 | −5.03 | 32 | 28 (88%) | 0.286 / 0.265 (n=32) |
| POST (7/27–8/13) | 273 | 273 (100%) | −500.94 | −99.15 | +135.17 | −1.83 | 133 | 130 (98%) | 0.229 / 0.242 (n=82) |

\* Runner capture = (exit−entry)/(highest−entry) on strict winners with ≥1% MFE (tiny denominators excluded; raw-mean version is dominated by a few near-zero-MFE outliers and is not reported).

**Read:** mean strict/trade improved −$5.03 → −$1.83; tier-banking on winners 88% → 98%; runner capture essentially unchanged (~0.24–0.29 of MFE captured — exits still leave ~3/4 of the excursion). Strict totals are negative in BOTH windows while raw is positive post — i.e., the book's positive raw P&L still leans on generous/fictional fills.

Caveats (honest, all of them): PRE strict is computable on only 74/139 rows (65 nulls — entry_ts_missing / no_bars era rows), so the PRE column is a biased subsample; observational before/after across a regime change, lane-mix change (hidden lane live 7/24, halt lane, crown era), and 11 simultaneous 7/26 ships; "banked a tier" = store partial_fills non-empty OR >1 verified fill — field-absent ≠ no scale-out on older rows; small N throughout.

## One-line takeaways
- Q1: Crown ex-hidden strict = +$84.46 on n=5 — positive but statistically meaningless; the meritocracy evidence base remains 93% hidden-lane.
- Q2: Post-7/26 mean strict improved (−$5.03 → −$1.83/trade) with near-universal tier-banking, but runner capture is flat (~25% of MFE) and both windows are strict-negative — observational only.
