# CORRECTION LEDGER — `_blended_pnl` runner-leg drop (pre-cc22b36 records)

_Generated 2026-07-26 00:27 EDT. Append-only: never edit a row — supersede it with a new file._
_Owner: The Statistician. Source of truth for any analysis touching stored `pnl` on trades dated <= 2026-07-20 midday._

## Why this file exists

The trade store **cannot be corrected in place**. Verified in `screener_app.py`:

- `/api/record_trade` (line 945) only ever does `_trades.append(trade)` (line 1015), and line 957
  **dedups by `trade_id`** — re-POSTing a corrected record for an existing id returns
  `{"deduped": true}` and changes nothing. It is a silent no-op, not an update.
- `/api/trades` (line 1064) is **GET only**. No PUT/PATCH exists.
- `/api/trades/clear` (line 1068) sets `_trades = []` — the only other mutation, and it wipes
  the whole book (193 records).

So in-place correction would require clear-all-then-repost — the replace-semantics wipe class.
**No write was made.** Railway was read-only (`GET /api/trades`). This ledger is the correction
vehicle instead: apply these deltas at analysis time.

## The bug

Fixed in **cc22b36** (2026-07-20 17:10 EDT), `marcos_trading_bot.py:2407`. The pre-fix code took
the runner quantity from the monitor loop's `remaining_shares`, which exit branches zero for
bookkeeping **before** the P&L math ran — so the runner leg contributed exactly $0. Stored `pnl`
on an affected record is therefore the **scale-out legs only**.

```python
# FIXED (cc22b36) — runner qty derived from what was never scaled out
pnl        = sum((px - entry_price) * qty for qty, px in partial_fills)
runner_qty = total_shares - sum(qty for qty, _px in partial_fills)
return pnl + (exit_price - entry_price) * runner_qty
```

## Method + precision (why these numbers differ slightly from a naive re-derive)

`entry` and `exit` are stored `round(x, 2)` (`screener_app.py:963-964`), so a naive re-derivation
from the stored record introduces an error that **scales with share count** — which masquerades as
a P&L correction. Two guards were applied:

1. **Entry precision recovered.** `entry = position_size / shares` (position_size is stored to 2dp,
   so entry error <= 0.005/shares, contributing <= **$0.005** to the whole-trade P&L regardless of
   size). Cross-checked against an independent recovery, `stop_loss + risk_per_share`: the two agree
   within **$0.0004** across all 133 records carrying both fields. `exit` remains 2dp — the only
   material residual, worth +/- 0.005 * runner_qty (carried per row as `+/-` below).
2. **Classified, not assumed.** A record is only corrected when stored `pnl` sits at the
   partials-only value AND *not* at the blended value. Records where the runner leg is smaller than
   the rounding envelope are marked AMBIGUOUS and **left alone**.

`pnl_pct` is NOT an independent witness — `marcos_trading_bot.py:6181` derives it from the same
`profit_loss`, and all 49 scaled records satisfy `pnl_pct == pnl / position_size * 100`.

## Validation anchors

- **BIYA 2026-07-20** re-derives to **$23.69**, matching the value independently documented as
  "true" in the `_blended_pnl` docstring. Stored is **$34.40**. Full trace below.
- ~~**All 7 post-fix scaled records** (>= ZYBT 2026-07-20T15:45:02) classify CLEAN...~~
  ⚠️ **CORRECTED 7/26 (adversarial audit): THE DEPLOY BOUNDARY ABOVE IS WRONG BY 1h26m.**
  `cc22b36` was committed **2026-07-20 17:10:56 −0400**; **ZYBT is recorded at 15:45:02 — 1h26m
  BEFORE the fix existed** (`git log` shows no commit between 15:45 and 17:10). ZYBT is a **pre-fix**
  record. It classifies CLEAN because its exit reason is `3:45pm time stop`, a branch that never
  zeroed `remaining_shares` — the same reason pre-fix ATPC 7/16 is CLEAN. The "boundary" was an
  exit-branch artifact, not evidence of the deploy.
  **True post-fix scaled sample = n=6** (SNTG/MTEN/ADVB/PN 7/22, ADVB 7/23, LVWR 7/24); 7/21 was the
  first session on fixed code and has no scaled records. All 6 classify CLEAN, and 5 do exercise a
  zeroing branch with runner_qty > 0 — real but thin evidence. **"The method produces no false
  positives" does NOT follow from n=6** and is withdrawn as a claim. A false positive requires a
  clean record whose stored value coincidentally lands on partials, which only happens when the
  runner leg is near zero; there is roughly ONE informative trial for that question (MTEN, dev $0.27
  vs a $0.285 envelope — the marginal case that nearly failed).
- Stronger evidence, from the adversarial audit: predicting buggy-ness **from the pre-fix source**
  (`cc22b36^`, which exit branches zero `remaining_shares` before the math) agrees with the
  arithmetic classification on **all 36**, with the only mismatches being AMST/HUBC 7/17 where
  `exit == entry` makes it undecidable and the delta is $0.
- Day totals reconcile exactly with the `project_new_era_baseline` memory ledger
  (7/13 +$234.15 / 7/14 -$61.48 / 7/15 -$112.55 / 7/16 -$30.82).

## Scope

| | count |
|---|---|
| records in store (GET /api/trades, 2026-07-26 00:27 EDT) | 193 |
| carry the `partial_fills` FIELD at all | 113 |
| **field ABSENT — predate commit `3cb9880` (7/13 15:53 ET)** | **80** |
| with non-empty `partial_fills` | 49 |
| **BUGGY — corrected here** | **36** |
| AMBIGUOUS — runner leg below noise floor, NOT corrected | 4 |
| CLEAN — exit branch that never zeroed `remaining_shares` | 9 |
| **provably affected but PERMANENTLY UNCOMPUTABLE** | **47** |

Fix commit `cc22b36` is dated **2026-07-20 17:10:56 −0400**, so every record on/before
7/20 15:45 is pre-fix. 7/21 was the first session on fixed code.

## ⚠️ The 47 uncomputable records — this ledger is a FLOOR, not a total

`partial_fills` was not persisted until commit **`3cb9880` (2026-07-13 15:53 ET)**. All 80 records
from 7/07 through 7/13 lack the field entirely — **absence of the field is NOT absence of
scale-outs**, and reading it that way was an error in the first draft of this file.

Those 80 can still be split, because the exit label is self-witnessing:
`_lbl = "Trailing stop 📉" if partial_taken else "Stop loss 🛑"` (`marcos_trading_bot.py:6025`,
also :6166). `HEALTH FOLD` is likewise guarded by `partial_taken`.

- **33 provably UNAFFECTED** — 24 `Stop loss 🛑` (label proves no partials) + 9 `3:45pm time stop`
  (branch never zeroed `remaining_shares` in any era).
- **47 provably AFFECTED but uncomputable** — 27 `Trailing stop 📉` + 20 `HEALTH FOLD`. Both branches
  zero `remaining_shares` before the math, so the runner leg was definitely dropped. **The scale-out
  quantities and prices were never written to disk. No analysis can recover them.**

**17 of the 47 are on 7/13** (11 Trailing + 6 HEALTH FOLD), i.e. inside the new era AND inside the
99-trade baseline window. The other 30 are pre-era (7/07–7/10) and don't matter under the
never-baseline-against-pre-era rule.

Sizing the 7/13 gap — **HYPOTHESIS, not measurement**: mean delta on the computable sample is
Trailing **+$3.55** (n=21) and HEALTH FOLD **+$3.79** (n=12), giving ~**+$62**; an independent
runner-fraction extrapolation gives **+$71 to +$88**. Individual deltas run −$20.62 to +$16.40, so
the spread is wide. Direction is positive with reasonable confidence (Trailing negative in only
7 of 21, HEALTH FOLD in 1 of 12) — but the magnitude is not knowable.

**Consequence: every total below is a floor.** Full new era 7/13–7/24 (n=139) = **−$39.39 corrected
FLOOR**; the true figure is plausibly near break-even. Whole book **+$2.25** is likewise a floor
(the 30 pre-era uncomputables add an unknown amount on top).

## Worked trace — BIYA, 2026-07-20 (the anchor)

```
entry $7.5000 (position_size 487.50 / 65 sh)   exit $6.87   total 65 sh
  scale leg   32 sh @ $8.1101 -> (8.1101-7.5000)*32 = $+19.5232
  scale leg   16 sh @ $8.4300 -> (8.4300-7.5000)*16 = $+14.8800
  partials subtotal                             = $+34.4032  -> STORED $34.40  (runner = $0)
  runner qty  65 - 48 = 17 sh
  runner leg  17 sh @ $6.87  -> (6.8700-7.5000)*17 = $-10.7100
  CORRECTED                                     = $+23.6932  -> $23.69
  DELTA                                         = $-10.71
```

## Per-trade corrections (36 records)

`+/-` = residual uncertainty from the 2dp `exit` price (0.005 * runner_qty + 0.01).

| # | date | ticker | trade_id | stored $ | corrected $ | delta $ | +/- | runner sh | exit_reason |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-07-14 | TRNR | `6722375c776a485aa681fd8453999196` | +13.20 | +26.07 | **+12.87** | 0.34 | 66 | Trailing stop 📉 |
| 2 | 2026-07-14 | LEDS | `2a9d67f476474a9ab053f03fd53f35e7` | +11.20 | +21.85 | **+10.65** | 0.36 | 71 | Trailing stop 📉 |
| 3 | 2026-07-14 | SOBR | `e100e965faa646f384d4575c8027dd83` | +17.92 | +30.24 | **+12.32** | 0.57 | 112 | Trailing stop 📉 |
| 4 | 2026-07-14 | SDOT | `e7b41a6cb4924f119ae0d84f083a2d9b` | +14.16 | +12.81 | **-1.35** | 0.06 | 9 | Trailing stop 📉 |
| 5 | 2026-07-14 | RDGT | `ca32abddd1bf4e619d3140bce5af5802` | +2.07 | +2.37 | **+0.30** | 0.16 | 30 | HEALTH FOLD (lost VWAP+EMA) |
| 6 | 2026-07-14 | YYGH | `62765eaaddc641b9b32da73d2f38eeef` | +36.22 | +39.12 | **+2.90** | 0.15 | 29 | HEALTH FOLD (lost VWAP+EMA) |
| 7 | 2026-07-14 | IVF | `0df035ddec3c4523bcc7b78230f69ffd` | +2.10 | +2.96 | **+0.86** | 0.23 | 43 | Trailing stop 📉 |
| 8 | 2026-07-14 | HODO | `f520858870994b73bc63b937d9ac3039` | +15.35 | +21.72 | **+6.37** | 0.47 | 91 | Trailing stop 📉 |
| 9 | 2026-07-14 | CNEY | `4a33f360b3444abc918554e853cb9e91` | +15.64 | +27.02 | **+11.38** | 1.16 | 229 | Trailing stop 📉 |
| 10 | 2026-07-14 | UONEK | `82783bd008814cb0b9fb612aa074c075` | +10.06 | +14.12 | **+4.06** | 0.19 | 35 | HEALTH FOLD (lost VWAP+EMA) |
| 11 | 2026-07-15 | VTAK | `41d6b5ff9ddf4e649b545d5c479542a9` | +15.75 | +21.83 | **+6.08** | 2.03 | 405 | Trailing stop 📉 |
| 12 | 2026-07-15 | UBXG | `f7efe2325160426f886f2a490e6631b0` | +14.91 | +7.43 | **-7.48** | 0.12 | 22 | BLIND-STOP FAILSAFE 🛟 |
| 13 | 2026-07-15 | CLRO | `7f3c9b93f94949e394cffc03869d8634` | +11.75 | +26.00 | **+14.25** | 0.14 | 25 | Trailing stop 📉 |
| 14 | 2026-07-15 | LEDS | `1599c34b2f644084a7840035cfd8e12b` | +17.76 | +27.21 | **+9.45** | 1.06 | 210 | Trailing stop 📉 |
| 15 | 2026-07-15 | MIMI | `3ae63c9760ea408784f7b0178fe622ea` | +11.70 | +12.61 | **+0.91** | 0.47 | 91 | HEALTH FOLD (lost VWAP+EMA) |
| 16 | 2026-07-15 | TGHL | `8b60642394204b6c8e1354f64d7cfd9d` | +15.74 | +23.27 | **+7.53** | 1.04 | 207 | HEALTH FOLD (lost VWAP+EMA) |
| 17 | 2026-07-15 | ZSTK | `573bb20627c4483487574278e715a171` | +2.12 | +2.08 | **-0.04** | 0.03 | 4 | BLIND-STOP FAILSAFE 🛟 |
| 18 | 2026-07-15 | JLHL | `43f718ace7da42fba5252e87ca6efa38` | +44.43 | +50.18 | **+5.75** | 0.04 | 5 | HEALTH FOLD (lost VWAP+EMA) |
| 19 | 2026-07-15 | CLRO | `beea2881e9bb402782a464bdbe7b27c9` | +14.45 | -0.31 | **-14.76** | 0.10 | 18 | Trailing stop 📉 |
| 20 | 2026-07-15 | BIVI | `de70e4db6ba442c9a1cf165b24717a28` | +9.20 | +7.68 | **-1.52** | 0.78 | 153 | BLIND-STOP FAILSAFE 🛟 |
| 21 | 2026-07-16 | IQST | `16b22bd6229241cdb7d474b08010c640` | +16.33 | +32.73 | **+16.40** | 0.92 | 181 | Trailing stop 📉 |
| 22 | 2026-07-16 | DXST | `03547bc7981e4fdab9bb935520d97603` | +15.25 | +21.47 | **+6.22** | 0.58 | 113 | Trailing stop 📉 |
| 23 | 2026-07-16 | EHGO | `721a60f1ce2547d2970d0d615a59500c` | +19.76 | +28.38 | **+8.62** | 0.35 | 67 | Trailing stop 📉 |
| 24 | 2026-07-16 | DXST | `a829c2eb790c4288a7cfe4aa6a002dd7` | +16.98 | +10.36 | **-6.62** | 0.55 | 108 | Trailing stop 📉 |
| 25 | 2026-07-16 | CMND | `65be7caef293443686825d9f20964c48` | +4.75 | +9.58 | **+4.83** | 0.36 | 69 | Trailing stop 📉 |
| 26 | 2026-07-16 | TVRD | `41cc5af4174e4cbaa39cd4bd8a1ff86e` | +17.50 | +31.36 | **+13.86** | 0.64 | 126 | Trailing stop 📉 |
| 27 | 2026-07-16 | CLIK | `eb27172d26b64e40a381b0c0bf6aabd1` | +16.05 | +17.51 | **+1.46** | 0.38 | 73 | HEALTH FOLD (lost VWAP+EMA) |
| 28 | 2026-07-16 | CPHI | `dc0024ab6a1e49de84291402211ddb8e` | +49.62 | +62.89 | **+13.27** | 0.42 | 81 | HEALTH FOLD (lost VWAP+EMA) |
| 29 | 2026-07-17 | JLHL | `93e955d32cd94129b827929ed8ef7a68` | +15.50 | -5.12 | **-20.62** | 0.23 | 43 | Trailing stop 📉 |
| 30 | 2026-07-17 | TRUG | `70ecd4a454414f7a9a03f2f6073c73dc` | +15.44 | +11.68 | **-3.76** | 0.39 | 75 | Trailing stop 📉 |
| 31 | 2026-07-17 | VEEE | `5c32395d3d304d91870e062e3c6477b3` | +52.59 | +52.20 | **-0.39** | 0.01 | 1 | HEALTH FOLD (lost VWAP+EMA) |
| 32 | 2026-07-17 | CJMB | `c789f76e17034bc49475f9076b67d611` | +16.11 | +14.33 | **-1.78** | 0.91 | 180 | Trailing stop 📉 |
| 33 | 2026-07-17 | GLXG | `a3986108c3d14bc18cce33bdf3cf4496` | +10.22 | +11.06 | **+0.84** | 0.07 | 12 | HEALTH FOLD (lost VWAP+EMA) |
| 34 | 2026-07-17 | VEEE | `bcb3857fe9804503b42d9be459a81104` | +14.98 | +23.38 | **+8.40** | 0.05 | 7 | HEALTH FOLD (lost VWAP+EMA) |
| 35 | 2026-07-17 | LEDS | `aa267777b1644b5ea63e98b29d25fa32` | +46.40 | +46.89 | **+0.49** | 0.13 | 24 | HEALTH FOLD (lost VWAP+EMA) |
| 36 | 2026-07-20 | BIYA | `a770a14c04b049769fc10c3d6dcbb494` | +34.40 | +23.69 | **-10.71** | 0.10 | 17 | Trailing stop 📉 |
| | | | **TOTAL (36)** | **+657.61** | **+768.65** | **+111.04** | 15.59 | | |

## AMBIGUOUS — deliberately NOT corrected (4 records)

Runner leg is smaller than the rounding envelope, so stored is consistent with BOTH formulas.
Total swing if all four were corrected: **$-0.22** — immaterial.

⚠️ **CORRECTED 7/26 (adversarial audit): GLXG 7/17 should be classified BUGGY, making the true
count 37, not 36.** The envelope test is too **loose** at the margin here — it treats "within the
maximum possible rounding error" as a fit, when the likelihood ratio is overwhelming:
`|stored − partials| = $0.0044` (essentially exact) vs `|stored − blended| = $0.2244` against a
$0.230 envelope, i.e. it clears the blended test by $0.006. Its exit reason is `Trailing stop 📉`,
a zeroing branch. **Dollar impact: $0.22** — the whole-book total moves from +$2.25 to +$2.03,
which changes nothing material. AMST and HUBC are technically buggy on the same logic but have
`exit == entry` exactly, so their delta is $0.00. NYC is a genuine tie.
The per-trade table above is left at 36 so it continues to match the `.json`; apply the extra
$0.22 at the aggregate level if precision to the cent matters.

| date | ticker | trade_id | stored $ | would-be $ | envelope +/- |
|---|---|---|---|---|---|
| 2026-07-16 | NYC | `731cb7c3f6fa4d338fd297dee8363fc4` | +20.99 | +20.99 | 0.15 |
| 2026-07-17 | GLXG | `7c34cad722d34abb84a4cf7785162f3a` | +1.54 | +1.32 | 0.23 |
| 2026-07-17 | AMST | `c1912c9517234d9c9498fa4cff5800f7` | +5.00 | +5.00 | 0.22 |
| 2026-07-17 | HUBC | `1dec584dbc52484a864ccda6ae7e1fd4` | +0.81 | +0.81 | 0.15 |

## Per-date rollup

| date | corrected recs | day stored $ | day corrected $ | day delta $ | +/- |
|---|---|---|---|---|---|
| 2026-07-14 | 10 | -61.48 | -1.12 | **+60.36** | 3.69 |
| 2026-07-15 | 10 | -112.55 | -92.38 | **+20.17** | 5.81 |
| 2026-07-16 | 8 | -30.82 | +27.22 | **+58.04** | 4.20 |
| 2026-07-17 | 7 | -183.80 | -200.62 | **-16.82** | 1.79 |
| 2026-07-20 | 1 | +134.62 | +123.91 | **-10.71** | 0.10 |
| **TOTAL** | **36** | | | **+111.04** | 15.59 |

Dates with zero corrections (no scaled records, or already clean): 7/07, 7/08, 7/09, 7/10, **7/13**,
7/21, 7/22, 7/23, 7/24. **7/13 carries no scale-outs at all** — the era's best day is unaffected.

## Effect on headline figures

| figure | stored | corrected |
|---|---|---|
| whole book (n=193) | **$-108.79** | **$+2.25** |
| whole-book win rate | 58.4% (111W/79L) | 57.4% (109W/81L) |
| NEW ERA 7/13-7/16 (n=99) | **$+29.30** | **$+167.87** |
| era win rate | 61.2% (60W/38L) | 60.2% (59W/39L) |
| era $/trade | $+0.30 | $+1.70 |

Whole book flips from **losing $108.79 to making $2.25** — a **$111.04** swing (+/- $15.59).

### Two trades change sign (they were logged as wins; they were losses)

| date | ticker | stored | corrected | exit_reason |
|---|---|---|---|---|
| 2026-07-15 | CLRO | +$14.45 | **-$0.31** | Trailing stop |
| 2026-07-17 | JLHL | +$15.50 | **-$5.12** | Trailing stop |

Both were trailing-stop exits — the runner rode back down and the erased leg was a real loss.
This is the bug's systematic tilt: it flatters trailing-stop/fade exits and understates trades
whose runner finished strong. Any win-rate or exit-doctrine analysis over <= 7/20 data that used
raw stored `pnl` is biased, not merely noisy.

## How to apply

```python
import json
LEDGER = json.load(open("data/killtests/pnl_runner_leg_correction_20260726.json"))
FIX = {r["trade_id"]: r["corrected"] for r in LEDGER if r["cls"] == "BUGGY"}
pnl = FIX.get(trade["trade_id"], trade["pnl"])   # corrected where known, stored otherwise
```

## Caveats

- `exit` is only stored to 2dp; per-row uncertainty is the `+/-` column, **$15.59 summed** across
  all 36 (dominated by high runner-share trades: VTAK +/-$2.03, CNEY +/-$1.16, LEDS 7/15 +/-$1.06).
  The whole-book conclusion (negative -> positive) survives the entire band.
- Corrections are arithmetic re-derivations of what the fixed code **would have** recorded from the
  same stored fills. They are not re-executions against the tape; fills themselves are unaudited.
- The 9 CLEAN records mean not every exit branch zeroed `remaining_shares` (`3:45pm time stop`,
  `RECOVERED after restart`). Scope is determined per-record by the signature, **never by date
  alone** — the fix date is not a valid scope filter.
- **`position_size = entry x shares` is FALSE for 46 records** (adversarial audit): pre-7/11,
  `position_size` was the flat **$100 reservation cap**, not notional. The `$0.0004` cross-check
  against `stop_loss + risk_per_share` is **structurally blind to exactly those records** — they
  predate both fields — so "validated across 133 records" was circular as originally stated.
  **Dollar impact here: $0.00**, since all 46 carry no `partial_fills` and are never corrected.
- **Latent hazard for any future re-derivation:** `_reserved = round(shares * entry_price, 2)`
  (`marcos_trading_bot.py:7354`) is computed **before** `entry_price` is rebound to the actual fill
  (:7435). Under DRY_RUN the fill equals the trigger (:5629) so `position_size/shares` recovers
  entry correctly. **In live mode with real slippage this recovery would silently return the
  TRIGGER price, not the fill.** Do not reuse this technique on live-mode records without checking.
- The live store still holds the OLD values and will continue to (no write path). Any consumer
  reading `/api/trades` directly — including the dashboard at `_compute_stats()` — still shows
  **$-108.79**. This ledger does not change that; it records what the truth is.
- The API has no update path, but the underlying JSON on Railway's `/data` volume is read at boot by
  `_load_trades()`. Editing that file + restarting is an out-of-band write path. It exists; it was
  **not** used and should not be.

## Review status

Both reviews were run in separate contexts on 2026-07-26 and are recorded here in full.

- **Blind replication** (never shown these figures): independently reproduced 36 records,
  **+$111.05** correction, book **+$2.26**, era windows identical, same 2 sign flips, same BIYA
  trace. It also caught the `partial_fills`-absent error corrected above.
- **Adversarial audit** (instructed to refute): **CONFIRMED** the no-write-path claim and every
  headline dollar figure to the cent. **REFUTED** the deploy boundary (C6) and the
  "no false positives from n=7" claim. **PARTIALLY REFUTED** the count (37, not 36, worth $0.22)
  and the `position_size` assumption ($0 impact).
- A lane-comparison claim ("vwap_reclaim is the era's worst lane by ~8.5x") was made in
  conversation off this data and is **REFUTED — do not use it.** It holds only in the 7/13-7/16
  window (full era: **1.81x**), collapses to 3.20x dropping one trade per lane, and flips ignition
  positive (+$22.04) dropping three. It is also tautological: only **8 of 32** vwap_reclaim trades
  have partial fills, so the correction could not move that lane by construction.
