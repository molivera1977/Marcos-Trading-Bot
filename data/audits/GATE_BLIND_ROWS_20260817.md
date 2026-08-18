# GATE-BLIND ROWS — expected volume, and how to read them (F1, 8/17)

**Question these rows exist to answer, which the 8/17 archive could not:**
*how often do the fail-open gates pass on ignorance, and what did those passes cost?*

## What was actually wrong (measured 8/17, not asserted)

| | |
|---|---|
| decision rows on 8/17 | **15,253** |
| `gate_fail_open` rows among them | **6** |
| ...of which `ambient` | **6 (all of them)** |
| ...attributable to a fire | **0** — every one under the `_GATE` pseudo-ticker, no lane |
| `check_momentum` blind passes recorded | **0** — in-memory `_bump`, dies with the process |
| volume-guard blind passes recorded | **0** — same |

And `_gate_failopen` throttles to **one row per gate per 60s**, so even the six are a
**floor, not a count**. This is the whole reason B5's fail-CLOSED conversion ships
default-OFF: arming it would be a silent tightening of unmeasured size.

## What ships now

One row **per occurrence**, at all five blind paths:

| gate | path | fails closed when armed? |
|---|---|---|
| `ambient` | `<5` completed bars | yes |
| `ambient` | exception | **never** |
| `momentum` | `< MOMENTUM_BARS` session bars | yes |
| `volguard` | no avg 1-min volume | yes |
| `volguard` | exception | **never** |

Both exception paths are stamped with an explicit note: **no arming can tighten them.**
That is a standing hole, named rather than hidden.

### Row shape

`status = gate_blind_<gate>` (one stream per gate; deliberately **distinct** from
`gate_fail_open`, so 8/17's archive stays comparable instead of being retconned).

| field | meaning |
|---|---|
| `ticker` | the real name — **not** `_GATE`. This is the attribution that was missing. |
| `lane` | entry_type, via a thread-local set at the entry path |
| `gate` | `ambient` / `momentum` / `volguard` |
| `missing` | what was absent, with the threshold (`"2<5 session bars"`) |
| `bars_have` / `bars_need` / `bars_fetched` / `vol_samples` / `avg_vol` | the sample sizes |
| `decision` | `pass_open` or `refuse_closed` — **the decision actually taken** |
| `armed` | was `GATE_FAIL_CLOSED` naming this gate at the time |
| `seq` | per-day sequence number (gaps ⇒ the cap was hit) |

De-duplication is bypassed for these rows (`_nodedup`). It had to be: `_log_decision`
collapses `(ticker, status)` for 120s, so two fires on one name inside two minutes would
become one row and every count built on them would again be a floor.

## Expected volume, and the bound

* **Cap: `GATE_BLIND_ROWS_MAX = 2000` rows per ET day**, across all three gates, resetting
  on the ET date change.
* **Why 2000:** 8/17 wrote 15,253 rows total, so the absolute worst case is **~13% archive
  growth**. Affordable, and the cap is env-tunable without a deploy of new code.
* **Expected actual volume: tens per day, order-of-magnitude.** These fire only when a gate
  has no data to judge with; the observable instance of that on 8/17 was 6+ (a floor).
  A day in the low hundreds would already be a surprise worth reporting.

> **If the cap is hit, that is THE FINDING — not a nuisance.** It would mean these gates
> pass on ignorance hundreds of times a day, and converting them to fail-closed stops being
> an option and becomes a priority.

On hitting the cap: **one** `gate_blind_capped` row (truncation is never silent), then
degrade to the old 60s-throttled `gate_fail_open` counter for the rest of the day. Bounded,
but never simply dropped.

## How to read it tomorrow

```sql
-- 1. the headline number that did not exist: blind passes per gate
SELECT gate, COUNT(*) FROM decisions
 WHERE date='2026-08-18' AND status LIKE 'gate_blind_%' AND status<>'gate_blind_capped'
 GROUP BY gate;

-- 2. WAS THE COUNT TRUNCATED?  Must be 0, or #1 is a floor again.
SELECT COUNT(*) FROM decisions WHERE status='gate_blind_capped' AND date='2026-08-18';

-- 3. which lane is paying for it
SELECT gate, lane, COUNT(*) FROM decisions
 WHERE date='2026-08-18' AND status LIKE 'gate_blind_%' GROUP BY gate, lane ORDER BY 3 DESC;

-- 4. pass_open vs refuse_closed (the B5 arming split)
SELECT gate, decision, armed, COUNT(*) FROM decisions
 WHERE date='2026-08-18' AND status LIKE 'gate_blind_%' GROUP BY gate, decision, armed;

-- 5. THE DOLLARS: join ticker+date to the fills/trades stream.  A blind pass that became a
--    fill is the unit of cost; a blind pass that led nowhere is free.  This is the join
--    that prices the fail-closed conversion.
```

**Reading order that answers the pricing question:** (2) first — if the day was truncated,
everything after it is a floor and must be reported as one. Then (1) for the rate, (3) to
find the lane responsible, (5) for the dollars. Only with (5) in hand should anyone argue
for arming `GATE_FAIL_CLOSED`.

**Caveat:** these rows measure how often a gate judged **without data**. They do not measure
whether the resulting trade was good — that needs the (5) join, and one day of it is one
day. The `armed` field exists so a future day's counterfactual can separate "would have
refused" from "did refuse".

Acceptance: `rig/test_batchF_20260817.py` (7 specs, all executing the shipped block).
