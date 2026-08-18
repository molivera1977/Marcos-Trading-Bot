# B5 — THE THREE FAIL-OPEN GATES: WITNESSED NOW, CONVERTIBLE WHEN PRICED — 2026-08-17

## FAILURE CONDITION (written FIRST)

This change is **WRONG** if:

1. Insufficient data is genuinely *not* evidence of a thin name — i.e. the names routed into
   these paths perform like the names that pass the gates on real data. Falsified by: grading
   the `gate_fail_open` rows this ship starts producing against the trades that followed them.
   (`_ambient_dvol_ok`'s own docstring already argues this: *"a data gap is not evidence of thin
   tape"*. That argument is on the record and is not dismissed here — it is what makes the
   default matter.)
2. `GATE_FAIL_CLOSED=""` (the default) changes any decision. It must not: it refuses nothing.
3. The armed volume guard sizes a position to zero shares and lets the order path see it. It
   must instead refuse through the capital-skip shape (row + slot refund + held-lock release).
4. The new witness rows storm the archive. `_gate_failopen` throttles to one row per gate per
   60 s — see the caveat below, which cuts both ways.

## LIMITS / CAVEATS

- **The conversion cost is NOT QUANTIFIED, and cannot be from today's rows.** That is the
  central finding of this document, not a footnote.
- `_gate_failopen` is **throttled to one row per gate per 60 seconds**. Every count below is a
  count of *throttled row-emissions*, not of fail-open events. The true event count is ≥ the
  row count, possibly far larger. Tomorrow's numbers will carry the same caveat.
- One session. Premarket + RTH combined.

## WHAT `m1_wallclock_20260817.md` FLAGGED

Three gates pass **by default** when data is insufficient — they are most permissive exactly
when they know least, and thin names are precisely what routes into them:

1. `check_momentum` (:4199) — fewer than `MOMENTUM_BARS` session bars → *"passing by default"*.
2. the volume **sizing** guard (:13113 class) — avg 1-min volume of 0 → **no share cap at all**,
   i.e. the wrong-but-restraining cap is *removed* on the names whose tape cannot be seen.
3. the universal/ambient liquidity gate (`_ambient_dvol_ok`) — fewer than 5 completed bars → pass.

## THE QUANTIFICATION — AND WHY IT COULD NOT BE DONE

Today's archive (15,253 rows) contains **6** `gate_fail_open` rows. Every one of them:

| gate | rows today | `why` | attributable to a ticker? |
|---|---|---|---|
| ambient | **6** | `<5 bars` (all six) | **no** — logged under `_GATE` |
| momentum | **0** | — | — |
| volguard | **0** | — | — |

**Two of the three gates left no trace at all.** `check_momentum`'s insufficient-data path called
`_bump("fail_open")` — an in-memory counter that surfaces only in a console health line and never
reaches the archive. The volume guard's `_vav == 0` path logged nothing whatsoever (only its
*exception* path left a `_clamp` witness).

So the honest answer to *"how many of today's fires reached each gate with insufficient data and
would now be refused"* is:

- **ambient: at least 6 fail-open emissions, none attributable to a fire** (the row carries
  `_GATE`, not the ticker), so even here the number of *refused fires* is unknown.
- **momentum: UNKNOWN.**
- **volguard: UNKNOWN.**

A fail-closed default on an unknown number is a silent tightening of unmeasured size — which is
the thing the brief explicitly says not to ship. So:

## WHAT SHIPPED, AND THE DEFAULTS

**ON by default — the observability.** Every one of the three fail-open paths now writes a
`gate_fail_open` row, and the two that had a ticker in hand now pass it (`momentum` and
`volguard` are attributable; `ambient`'s call site has no ticker on the `<5 bars` branch and is
left as `_GATE`). Tomorrow the number exists.

**OFF by default — the conversion.** `GATE_FAIL_CLOSED` is an empty comma list. Arm with
`momentum`, `volguard`, `ambient`, or `all`.

| gate | fail-closed default | why |
|---|---|---|
| `momentum` | **OFF** | cost UNKNOWN (0 rows today). It also gates *every* entry, so it is the highest-blast-radius of the three. |
| `volguard` | **OFF** | cost UNKNOWN (0 rows today). It is a SIZING guard: armed, it refuses the trade outright, which is a strictly larger action than the cap it replaces. |
| `ambient` | **OFF** | 6 emissions today but **none attributable to a fire**, so the refused count is still unknown. Its own docstring argues the fail-open is deliberate; overriding a documented deliberate choice without a number is not an auditor's call. |

**All three are money-behaviour changes when armed.** Per
`feedback_auditor_cannot_authorize_behavior` they go to Marcos priced; the observability rows are
the observe-only half and ship freely.

## HOW THE ARMED PATHS REFUSE

- `check_momentum` → `return False, details` with the existing `details["reason"]`, i.e. the same
  shape as every other momentum reject. No new downstream path.
- `_ambient_dvol_ok` → `return (not _fail_closed("ambient")), 0.0, 0.0`, i.e. the existing
  `ambient_reject` row and reject path fire.
- the volume guard → an explicit `volguard_closed_skip` row, `_slot_refund`, `held`-lock release
  and `return` — **the identical shape to `no_capital_skip`**. Deliberately *not* `shares = 0`:
  a zero-share position sails through the capital reservation (`_reserved` = 0) and would reach
  the order path as a degenerate order. That trap is called out here because it is the obvious
  implementation and it is wrong.

## ACCEPTANCE

`rig/test_batchB_20260817.py::SPEC_fail_open_gates_observable_and_armable` — **executes**
`_fail_closed` in three isolated namespaces (unset / `"momentum, ambient"` / `"all"`) and asserts
the default refuses nothing, the list parses per-gate, and `all` arms everything; then pins that
all three fail-open sites emit a witness row, that each is wired to its own switch, and that the
armed volume guard refuses through `volguard_closed_skip` rather than by zero-sizing.
