# COMMIT-RECORD REPAIR — 8/17 night, two-agent working-tree collision

Filed by the A-batch (measurement-integrity) agent. **Both incidents are mine.** Nothing was
lost from the TREE — every file and every line of both agents' work is present and correct.
What was damaged is the COMMIT RECORD, and the convening needs to know it.

## Incident 1 — `git add <paths>` swept the other agent's in-flight bot edits

My commit **460dca5** ("A-batch fixups") staged `marcos_trading_bot.py` while the B-batch
agent had uncommitted B5 edits in that same file. Those edits rode into my commit, so a
money-behaviour change landed **without its Acceptance trailer**, through no act of theirs.
They disclosed this themselves. **The convening must treat 460dca5 as carrying an unlabelled
behaviour change**; its acceptance test is `rig/test_batchB_20260817.py::SPEC_fail_open_gates_observable_and_armable`,
which fails at 6ee3fe2 (460dca5's parent).

## Incident 2 — `git commit --amend` overwrote their commit message

I ran `--amend` believing HEAD was still my own 460dca5. Between my tool calls the B-batch
agent had committed **be32e2e** ("B4 (REFUTED as stated) + B5 acceptance & docs"), so my amend
rewrote THEIR commit: the result is **5cd2d34**, carrying their content plus a 32-line
`SPEC_stamp_position` addition of mine, under MY message. Their B4/B5 message survives only
in the reflog (`be32e2e`) and is reproduced VERBATIM below so it is not reflog-only.

History was NOT rewritten to repair this: 3fc2e1a (theirs) already sits on top, and rewriting
shared history under a live concurrent writer is the larger risk. The record is repaired here
instead.

**Standing rule for any future concurrent session: never `--amend`, never `git add -A`, and
re-read `git log -1` immediately before every commit.**

---

## The lost message, verbatim (original commit be32e2e, content now in 5cd2d34)

```
B4 (REFUTED as stated) + B5 acceptance & docs

B4 — THE PREMISE IS LARGELY REFUTED. Reproducing the 35 "stop >= entry" exclusions from
the 8/17 archive splits them into THREE causes, none of which is a detector emitting a
malformed signal. Count of fires where a detector's stop was at/above its OWN fire price:
ZERO.
  * ma_pullback 17 = the STUDY's hand-rolled stop (`conf-bar low -1%`) off a reconstructed
    1-min tape. The lane logs no stop at all, so derive_stop invented one. A defect in
    exit_params_our_fires_20260817.py, exactly the hazard rig EG2 exists to catch.
  * grinder 5 / kevseq 2 / v2conv 1 / dip_rip 1 = the study compared the logged stop against
    `price` (the LIVE QUOTE) instead of `fire_px`. Against their own fire price all nine
    stops are valid (XPON 4.67<4.72, WOK 2.59<2.7373, WTM 2130.66<2131.70, RPGL 2.55<2.64).
    What the rows actually record is NEGATIVE entry drift — B1 seen from the other side,
    and B1's fire-on-close + degenerate_stop refusal is the correct response. Shipped.
  * hidden 9 = a real defect, but at the LOGGING SITE, not the detector.
    hidden_entry_step computes stop = min(l-0.01, c*0.95) with px = c — both terms are
    strictly below c, so its stop can NEVER reach its fire price. The row pairs the live
    quote with the fire bar's stop (`price=_hpx` where _hpx is the quote). Same class as B1.

NO DETECTOR CHANGE SHIPPED, because the diagnosis does not support one: adding a
`bad_stop_refused` branch to lanes that provably cannot produce the condition would put an
unreachable branch on a money path. What ships is the INVARIANT, PINNED —
SPEC_no_detector_emits_bad_stop asserts every convertible detector carries its degeneracy
guard (V2_MINSTOP_PCT / `not (lo15 < c)` / `stop < c` / min(l-0.01, c*0.95) /
degenerate_stop). It PASSED at the parent, correctly: it is a regression pin and is labelled
as one, not dressed up as a fix. Handed off (logging owner): stamp fire_px on
hidden_shadow_fire; log a stop on triggered_ma_pullback; prefer fire_px in the study.

B5 — THE THREE FAIL-OPEN GATES: witnessed now, convertible when priced.
THE QUANTIFICATION FAILED, AND THAT IS THE FINDING. Today's 15,253 rows carry SIX
gate_fail_open rows, all `ambient` / "<5 bars", all logged under the `_GATE` pseudo-ticker
so not one is attributable to a fire. check_momentum's insufficient-bars path and the
volume-sizing guard's no-tape path left NO ROW AT ALL — _bump("fail_open") is an in-memory
counter. So: ambient >=6 emissions but UNKNOWN refused fires; momentum UNKNOWN; volguard
UNKNOWN. (And _gate_failopen throttles to one row per gate per 60s, so every count is a
floor.) A fail-closed default on an unknown number is a silent tightening.

SHIPPED ON: the observability — all three paths now write gate_fail_open, and the two with
a ticker in hand now pass it. SHIPPED OFF: the conversion, behind GATE_FAIL_CLOSED (empty
comma list; "momentum"/"volguard"/"ambient"/"all"). The armed volume guard refuses through
a volguard_closed_skip row + _slot_refund + held-lock release — deliberately NOT `shares=0`,
which sails through the capital reservation and reaches the order path as a degenerate order.
All three are money-behaviour changes WHEN ARMED and go to Marcos priced.

⚠️ GATE-5 COLLISION, DISCLOSED: the B5 edits to marcos_trading_bot.py were swept into the
concurrent agent's commit 460dca5 (they commit with `git add -A` on a shared working tree),
so B5's behaviour change landed WITHOUT its Acceptance trailer, through no deliberate act
here. The acceptance test is in THIS commit and does fail at 6ee3fe2 (460dca5's parent).
The convening must treat 460dca5 as carrying an unlabelled behaviour change.

Docs (failure condition + limits first): data/killtests/bad_stop_20260817.md,
data/killtests/fail_open_gates_20260817.md.

Acceptance: rig/test_batchB_20260817.py::SPEC_fail_open_gates_observable_and_armable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

```

---

## Addendum — AST evidence on WHY 460dca5 classified behaviour-changing

Filed after the fact. In the A-batch report I stated the reason as "spec_gate's stripper does
not clean `If`/`Try` bodies, so my `_log_decision` kwarg reordering survives normalisation."
I asserted that from reading `_Strip` rather than running it. Both halves have now been
executed and the picture is **two causes, not one**:

**(a) CONFIRMED — my half.** Isolated test on `spec_gate.normalize()`:

```
_log_decision(...) nested inside if/try, kwargs reordered  -> normalized IDENTICAL? False
_log_decision(...) at the top of a function body, same edit -> normalized IDENTICAL? True
```

`_Strip` cleans only `Module`, `FunctionDef` and `ClassDef` bodies. Every fire-row logging
call in the scan loop sits inside `if`/`try`, so it is never stripped, and a pure-formatting
kwarg move reaches the AST. That is the classifier's documented conservative direction, and
it correctly demanded a test — `SPEC_stamp_position` now covers it.

**(b) NOT MENTIONED, AND IT CAME FIRST — their half.** A full normalised-AST diff of
`marcos_trading_bot.py` between 460dca5 and its parent 6ee3fe2 puts the **first** divergence
at the B-batch agent's B5 code, not mine:

```
+ Assign(targets=[Name(id='GATE_FAIL_CLOSED', ...)], value=Call(... 'GATE_FAIL_CLOSED', '' ...))
+ FunctionDef(name='_fail_closed', ...)
```

That is a genuine money-behaviour change (the fail-open gate conversion), swept into my
commit by incident 1 above. So **460dca5 carried TWO behaviour changes and a trailer for
neither**; the one I later attached covers only the formatting half.

**For the convening:** the finding in incident 1 stands and is now evidenced, not inferred —
460dca5 must be audited as carrying the B5 gate change unlabelled. Its acceptance test is
`rig/test_batchB_20260817.py::SPEC_fail_open_gates_observable_and_armable`.

Reproduce:
```
python3 - <<'PY'
import sys; sys.path.insert(0,'rig'); import spec_gate as SG
s='def f():\n    if x:\n        _log_decision(t, "r", **st(1), price=1)\n'
print(SG.normalize(s)==SG.normalize(s.replace('**st(1), price=1','price=1, **st(1)')))
PY
python3 rig/spec_gate.py 460dca5 --verbose
```

---

## Incident 3 — the D-batch swept three staged files of the concurrent agent (8/17 night)

Filed by the **D-batch (break-attack extraction) agent. This incident is mine.**

My doc-only commit **1b5a8dc** ("D doc: LIMITS/CAVEATS section + an explicit qualified
VERDICT") carried three files that are not mine and are not the D batch's work:

- `data/audits/AGENT_WORKFLOW.md` (new, 111 lines)
- `rig/agent_worktree.sh` (new, 106 lines)
- `rig/spec_gate.py` (+85 lines)

**How.** I ran `git status --short` before staging, exactly as the standing rule requires, and
it was clean of those paths. Between that call and my `git add`, the other agent staged them
into the shared index. I then staged one path of my own and committed, and everything already
in the index rode along. `git add <paths>` does not commit only those paths — it commits the
index. **The standing rule is therefore insufficient as written**, and the correction is
recorded below.

**Nothing was lost.** All three files are present and correct in the tree exactly as their
author wrote them; only the commit they are attributed to is wrong.

**No unlabelled behaviour change landed.** All three paths are `rig/` and `data/audits/`,
which Gate 5 classifies as always-exempt, and my own D-batch commit (`ef0dfe5`, the one that
does touch `marcos_trading_bot.py`) carries its Acceptance trailer and was verified against
real git trees (`rig/spec_gate.py ef0dfe5` → PROVEN, green). So 1b5a8dc is a **record defect
only**, not a money-behaviour defect.

**History was NOT rewritten**, for the same reason as incidents 1 and 2: the other agent is a
live concurrent writer and may already have built on HEAD. The record is repaired here.

### Correction to the standing rule

The rule in this document said: *never `--amend`, never `git add -A`, and re-read `git log -1`
immediately before every commit.* That is necessary but **not sufficient** — it does not
protect the INDEX, which is shared mutable state between concurrent agents. Two agents cannot
safely share one index. The rule should read:

> Never `--amend`, never `git add -A`. Before committing, re-read BOTH `git log -1` AND
> `git status --short`, and **commit with explicit pathspecs** — `git commit -- <paths>` —
> which commits only those paths regardless of what else is in the index. Better still, give
> each concurrent agent its own `git worktree` so there is no shared index at all.

The `rig/agent_worktree.sh` that rode into 1b5a8dc appears to be the other agent reaching the
same conclusion independently, on the same night.
