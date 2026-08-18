# AGENT WORKFLOW — the process that FAILED on 8/17, written down so it cannot fail the same way

Status: **LAW for any session running more than one agent against this repo.**
Built after the failure, not before it. Evidence: `data/audits/COMMIT_RECORD_REPAIR_20260817.md`
and its AST addendum (commit `d3a5dd5`).

## What actually happened

Several agents worked **one shared worktree at the same time**. No one lied and no one
skipped a gate on purpose:

1. Agent X finished its change and staged it. The staging was either `git add -A` or a
   path-scoped `git add marcos_trading_bot.py` — **both are fatal here**, because
   `marcos_trading_bot.py` is a single path that three agents were editing simultaneously.
2. Agent Y's **in-flight, uncommitted** edits to that same file were swept into X's commit.
3. So commit `460dca5` ("A-batch fixups: stamp position, EG4 negative control, and a
   clock-flaky rig section") silently carried a **money-behaviour change** — the B5 fail-open
   conversion — under a message that never mentions it and with **no `Acceptance:` trailer**.
   GATE 5 was never invoked on the change it was built to gate.
4. A later `--amend` intended to fix the trailer **destroyed another agent's commit message.**

The scan in `rig/spec_gate.py --scan` now finds `460dca5` from the record alone (see
`PENDING_CONVENE_20260817.md`). It found no other instance in the 27-commit range.

**The lesson is not "stage more carefully."** Path-scoped staging cannot separate two agents
who are both editing the same path. Discipline was not the missing ingredient; **separation**
was.

## The rules

### 1. One worktree per agent. Never share.

```bash
rig/agent_worktree.sh create F              # branch agent/F off HEAD, own checkout
cd "$(rig/agent_worktree.sh path F)"        # ALL of this agent's work happens here
# ... edit, rig, commit ...
rig/agent_worktree.sh remove F              # refuses if uncommitted work remains
```

`create` **refuses when the base tree is dirty** — branching off a dirty tree means the agent
reads one tree and commits against another. Commit or park the dirt first.
(`AGENT_WORKTREE_ALLOW_DIRTY=1` overrides, and you must say in your report that you used it
and what the dirt was.)

Commits land in the shared object store immediately and are visible repo-wide; the branch is
merged by whoever integrates. **A worktree is not isolation from review — it is isolation
from the index.** Agent X physically cannot stage agent Y's file, because X's checkout does
not contain Y's edits.

### 2. Path-scoped staging only. `git add -A` is banned.

Even inside your own worktree. Name every path:

```bash
git status --short          # ALWAYS, immediately before staging — read what you are about to commit
git add rig/spec_gate.py data/audits/AGENT_WORKFLOW.md
git status --short          # again: confirm the staged set is EXACTLY yours
git commit -m "..."
```

If `git status --short` shows a modified file you did not touch, **stop and report it** — you
are in a shared tree and rule 1 has already been broken.

### 3. Never `--amend` a commit you did not author in this session.

Amending rewrites someone else's message and sha. If a foreign commit needs a correction,
write a **new** commit that says what it corrects (that is what `8ac6791` and `d3a5dd5` do).
Amending your own just-written, unpushed commit is fine.

### 4. Retry on `index.lock`.

Concurrent agents contend for the index. Retry up to 5 times with backoff; never delete
`index.lock` by hand — another agent may be mid-write.

### 5. GATE 5 before you claim done.

Any commit touching `marcos_trading_bot.py` or `screener_app.py` needs an `Acceptance:`
trailer naming a spec that **fails at the parent and passes at the commit**:

```bash
python3 rig/spec_gate.py HEAD        # exit 0 = proven
```

### 6. Audit the range at the end of the session.

Per-commit gating is bypassable by accident; the range scan is not:

```bash
python3 rig/spec_gate.py --scan <session-start>..HEAD --markdown
```

Exit 1 means at least one behaviour-changing commit named no acceptance test. Append the
table to the convening file. This is the retroactive net under rules 1-5.

## Why the scan checks what it checks

The obvious ask — "flag a commit whose diff touches two disjoint feature regions" — needs a
model of what a feature region *is*, which this repo does not have. Any such model would be a
guess presented as a check. The signature every version of this failure produces is dull and
**exactly** computable instead:

> a commit that is behaviour-changing (AST-normalised, comments/docstrings/pure-logging
> stripped) and carries **no** `Acceptance:` trailer.

Contamination by `add -A`, by a shared path, by `--amend`, or by plain forgetfulness all land
there. Scan mode reports that, over a range, in one pass.

**Scan mode reports; it does not prove.** It does not run the acceptance tests (two worktree
checkouts per commit is far too slow over a range), so a commit that names a test is reported
`CLAIMED`, never `PROVEN`. Only `spec_gate.py <sha>` proves. That column exists so an audit
can never mistake "named a test" for "watched the test fail at the parent."
