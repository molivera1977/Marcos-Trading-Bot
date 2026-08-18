# DEFECT — THE EXTENSION GUARD IS BLIND ON 7 LANES (opened 8/18/26)

**Status:** OPEN — instrumented, bounded, and pinned. **NOT FIXED.** The fix is a money-behavior
change and is Marcos's priced call.

**Found by:** measuring item #2 of the 8/18 ship review instead of arguing it. The blast-radius
audit had reported "grinder and crown_seam now un-capped on 25%-over-EMA90." That is wrong in a way
that matters: **they were never capped.**

---

## 1. What the guard is supposed to do

`EXTENSION_MAX_PCT = 0.25` (:499, 7/3) — refuse an entry priced more than 25% above its 90-EMA.
Anti-chase. It reads the EMA out of the fire's own detail dict:

```python
_e90 = (b[4].get("ema90") or 0)
if b[3] in _ext_exempt_lanes():
    _kept.append(b)                                                    # declared exempt
elif _e90 > 0 and (b[1] - _e90) / _e90 > EXTENSION_MAX_PCT:
    _log_decision(b[0], "extension_reject", ...)                       # refuse
else:
    _kept.append(b)                                                    # FAIL OPEN
```

That final `else` conflates two completely different states — *"measured, and it's fine"* and
*"could not measure at all"* — and nothing distinguished them in the rows.

## 2. The measurement

`extension_reject` rows in the live decisions archive, **15 sessions**:

| 8/17 | 8/14 | 8/13 | 8/12 | 8/11 | 8/10 | 8/08 | 8/07 | 8/06 | 8/05 | 8/04 | 7/31 | 7/29 | 7/28 | 7/25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Not "rarely." **Never.** Query validated — 8/17 alone returns 15,267 rows across other statuses, so
both the archive and the status filter work.

## 3. The cause

AST census of all **17** `breakouts.append` fire sites, resolving detail dicts through variables
and `**` spreads:

| stamps `ema90` (10) | **BLIND (7)** |
|---|---|
| dip_rip, zone_flip, vwap_reclaim, hidden_entry, ignition, rocket_catcher, flat_top, orb, ma_pullback, bounce | **v2conv, grinder, bandpass, kevseq, prevwap, crown_seam, halt_ladder** |

For the blind seven, `_e90` is `0`, so the `elif` can never be true and every fire falls through to
fail-open. **Two of them convert today: grinder and crown_seam.**

*Method note:* the first pass of this census reported flat_top as blind. That was wrong — flat_top
builds its detail dict in a variable (`_ft_extra`) and a regex over the literal call text misses it.
The corrected census follows variable assignments. The rig fixture pins the negative control so the
detector cannot silently degrade into reporting nothing.

## 4. Why this is a CLASS, not an instance

All seven blind lanes are **tape lanes born after the guard was written.** That is precisely the
class already named on 8/17: *a lane born after a gate silently defaults to the wrong side of it* —
the same failure that left kevseq out of the copy-pasted chart-bypass tuple and killed WFF at
11:17:43 on a name that ran $1.61 → $6.00.

Per `feedback_kill_the_class_not_instance`, the second appearance of a class does not get an
instance patch. It gets a permanent pin over **every** consumer. That is `rig/test_extension_blindness_20260818.py` (gate 10).

## 5. What shipped tonight (observability only, no behavior change)

1. The fail-open branch now emits `_gate_blind("extension", ...)` **only when `_e90 <= 0`** — i.e.
   only on genuine blindness, never on a fire that was measured and passed. The row names the lane,
   so the blindness becomes countable and attributable per lane from tomorrow.
   *Grounding:* this describes source committed on this tree, not observed behavior — verified by
   gate 10 checks 10.4/10.5/10.6, which assert the literal `_gate_blind("extension"`, the
   `if _e90 <= 0:` guard, and the `lane=b[3]` attribution are present in `marcos_trading_bot.py`.
   **No row of this kind has been observed in production yet** — the first can only exist after this
   batch deploys, so every count below is UNMEASURED until 8/18 rows land.
2. **Gate 10** pins the class:
   - every fire site must stamp `ema90`, be a declared exempt lane, or be on the frozen
     `BLIND_KNOWN` list — a **new** lane that is none of the three goes RED;
   - `BLIND_KNOWN` may only **shrink** — adding to it goes RED;
   - the guard must still fail open and the 25% threshold must be unchanged, so this gate can never
     be mistaken for having armed it;
   - two negative controls prove the census can actually see a blind lane and does not false-flag a
     stamped one.

## 6. What is NOT done, and why

**The guard is not armed on the seven lanes.** Stamping `ema90` on them would immediately start
*rejecting entries that currently fill.* That is a money change on two converting lanes, and
`feedback_auditor_cannot_authorize_behavior` puts it with Marcos, priced — not with whoever happens
to be auditing.

There is also a real argument that arming it would be **wrong**, and it is already on the record:
the 7/26 kill-test found the 17 extension-rejected slow triggers ran **1.69R medMFE / 65% ≥1R** —
*better* than the trades the guard kept. That is why you exempted flat_top / orb / ma_pullback by
hand on 7/26. The same finding may well apply to a grinding leader, which is exactly the population
grinder trades. **This is untested on tape lanes** — HYPOTHESIS, not a recommendation.

## 7. Consequence for item #2 of the ship review

Item #2 was "`LANE_REGISTRY_EXEMPT=1` widens the extension exemption 7 → 14 lanes, un-capping
grinder and crown_seam."

The seven lanes it newly exempts are **exactly** the seven that are already blind. So the change
converts an *accidental* exemption into a *declared* one and alters no entry, no size, no stop.

**Item #2 is a formal no-op on live behavior and needs no sign-off.** It is, if anything, an
improvement in honesty: an exemption that is written down can be argued with; one that exists
because a field was never passed cannot.

## 8. Pre-registered failure conditions

- If `gate_blind` rows tagged `gate="extension"` do **not** appear for grinder/crown_seam fires
  tomorrow, this diagnosis is wrong and must be retracted — the lanes would not be reaching the
  guard at all, which is a different defect.
- If the count is large and those fires are systematically deep over the 90-EMA, "tape lanes are
  structurally non-extended" is falsified and the exemption's stated rationale dies with it.
- If the count is ~0 because the lanes are genuinely never extended, the guard is simply irrelevant
  to them and the honest action is to delete the exemption rather than defend it.

## LIMITS — what this document does NOT establish

- **It does not measure a cost.** Zero `extension_reject` rows proves the guard never *fired*. It
  does **not** show the guard would have been right to fire, or that anything was lost or gained by
  its silence. No fire has been graded here. Nothing in this document supports arming it.
- **The 15 sessions are not a clean sample of the guard.** They are the sessions queried. They are
  not stratified by regime, and they include days whose fills are affected by the contamination
  sources already on the ledger (A–H). The zero is a fact about rows, not a seasoned statistic.
- **The blind/stamped census is STATIC.** It reads source with AST. It proves which lanes *can*
  supply an `ema90`, not what any lane did on any specific fire. A lane could stamp `ema90` and
  still pass a stale or wrong value — that is not tested here.
- **`v2conv`, `bandpass`, `prevwap`, `kevseq`, `halt_ladder` do not convert today**, so five of the
  seven blind lanes have no live consequence at all right now. Only **grinder** and **crown_seam**
  matter for tomorrow, and their blind-fire counts are **UNMEASURED** — the instrumentation that
  would count them ships with this batch and has never run in production.
- **The 7/26 result (1.69R medMFE, 65% ≥1R on 17 extension-rejected slow triggers) is CHART-lane
  evidence, n=17.** It is quoted here as the reason the obvious fix may be wrong. It is **not**
  evidence about tape lanes, and it must not be cited as if it were. Any claim that grinder behaves
  the same way is a HYPOTHESIS with no test behind it.
- **The item-#2 no-op conclusion is about live behavior only.** It says exempting the seven changes
  no entry today, because they were already unreachable by the guard. It does not say the exemption
  is *correct* — that question is untested and stays open.
- **No P&L figure appears in this document**, in dollars or in R, because none has been computed.
  Any future version that asserts a cost must carry the dollars through the real sizing chain with
  a named trade traced end to end (`feedback_dollars_not_r`).

## 9. Owed next

1. **Count first** (tomorrow's rows): per-lane blind counts + the actual extension distribution.
2. **Then** grade: for blind fires, what did the trade do? Reuse the 7/26 method (medMFE, %≥1R).
3. **Then** Marcos decides per lane — arm, exempt-by-declaration, or delete the guard for tape lanes.
