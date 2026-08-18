# CONFIG HASH FREEZE — definition, failure condition, and the 8/17 epoch report

FOUNDATION BATCH C, item C2. Written 2026-08-17 (night). Failure condition written BEFORE the fix.

## THE DEFECT

2026-08-17 carried **five `boot_config` rows**. "8/17 did X" is therefore a statement about a bag
of five machines, and "8/17 vs 8/14" compares two bags whose composition nobody recorded. A
strategy result and a config change are indistinguishable in every multi-day aggregate this
system has produced.

## THE HASH — exactly what it covers

`config_hash` = first 12 hex of `sha256` over:

1. `code=<code_sha>` — `RAILWAY_GIT_COMMIT_SHA` (or `GIT_COMMIT_SHA` / `GIT_SHA` /
   `SOURCE_VERSION`) trimmed to 12 when the platform supplies it; **otherwise the sha256 of
   `marcos_trading_bot.py`'s own bytes**. Both are stable across restarts of the same image —
   which the deploy id is NOT. Using the deploy id would have turned the epoch report into a
   restart counter, which is the opposite of what it is for. `code_src` labels which was used
   (`git` / `srcdigest`).
2. `NAME=<raw value>` for every behaviour-governing env var, **name-sorted**, with UNSET spelled
   `\x00<unset>` so it hashes differently from set-to-empty (setting `FOO=""` IS a config choice).

**The env list is SCANNED FROM SOURCE**, not hand-written: every `os.environ.get("NAME"` in
`marcos_trading_bot.py`, minus an explicit non-behavioural exclusion set (credentials, endpoints,
identity, filesystem paths, account balance, one-shot operator actions like `MANUAL_CLOSE` /
`TEST_TRADE` / `WAKE_ET`, and `RAILWAY_DEPLOYMENT_ID`). A hand list goes stale the first night
someone adds a switch and forgets — and a hash that silently stops covering a knob is *worse than
no hash*, because it reads as proof of sameness. The list currently resolves to ~180 variables;
`cfg_n` is stamped alongside the hash so a shrinking list is visible in the data.

The boot_config row's fields are a strict SUBSET of what this catches. The rig asserts every
switch named in the brief is inside it: `*_CONVERT`, `KEVSEQ_FIRE_ON_CLOSE`, `M1_WALLCLOCK`,
`DEDUPE_FIRES`, `LANE_REGISTRY_EXEMPT`, `TAPE_LANE_SCALAR_EXEMPT`, `GATE_FAIL_CLOSED`,
`RTH_HANDOFF_MIN`, `KEVSEQ_LIMIT_ENTRY`, `RISK_PROP`, `MAX_TRADE_DOLLARS`, `MIN_STOP_PCT`,
`MIN_RUNWAY_RR`, the caps — and that no credential is.

## WHAT IT STAMPS

| where | fields | how |
|---|---|---|
| `boot_config` row | `config_hash, code_sha, code_src, cfg_n` | via `_log_decision` |
| every `triggered_*` row | same | via `_log_decision` (status-prefix match) |
| every fill row (`filled`, `retest_fill`, `tier_fill`) | same | via `_log_decision` |
| every **trade record** | same | `post_trade_record_reliably`, the single choke point |

Deliberately NOT stamped: `watching` / `consolidating` and the other ambient rows — ~6,700 a day,
carrying no verdict anyone aggregates. Computed **once per process** (config is boot-time by
construction: every switch is read into a module constant at import).

## FAILURE CONDITION (pre-registered — this is WRONG if…)

1. …two processes running **identical code and identical env** produce **different** hashes. The
   report then measures restarts, not machines. Guarded: no deploy id, no timestamp, no pid in
   the digest; the rig asserts `RAILWAY_DEPLOYMENT_ID` changing does not move the hash.
2. …a **behaviour switch flip does not move** the hash. Guarded: the rig flips `V2_CONVERT`,
   `MAX_TRADE_DOLLARS` and the code sha and requires the hash to move each time.
3. …a **rotated credential moves** it. A token re-mint (~8/23) must not open a false epoch.
   Guarded by the exclusion set + rig assertion.
4. …the scanned env list **shrinks silently**. `cfg_n` rides on every stamped row precisely so
   this is checkable from data. If `cfg_n` drops between epochs, the hash stopped covering
   something and every comparison using it is suspect.
5. …a study cites a multi-day number without saying which hashes it covers. That is what gate
   EG2c exists to catch, and it is enforced forward from 2026-08-18.

## LIMITS / CAVEATS

- The hash proves the CODE and the LISTED ENV matched. It cannot see broker-side state, the day's
  Kev sheet, data-vendor behaviour, or the market. **Same hash does not mean same world.**
- The `srcdigest` fallback means a repo-dirty local run hashes differently from the committed
  tree. That is correct (different code) but is not a git sha, hence `code_src`.
- **Rows logged before tonight carry no hash.** 8/17 and every earlier day are reconstructible
  only by boot_config-row segmentation, which OVERCOUNTS — two restarts of the same image look
  like two epochs. `config_epochs.py` labels such output `INFERRED` and says so on the report.
- The epoch report's per-epoch fire numbers are **ROW counts, not distinct setups**. See
  `data/killtests/ma_pullback_dup_20260817.md` — ma_pullback logged 210 rows for ~123 setups on
  8/17. This report is MIXED-EPOCH by construction whenever it spans more than one hash.

## THE 8/17 EPOCH REPORT (INFERRED — pre-stamp day)

`python3 data/audits/config_epochs.py 2026-08-17`

```
2026-08-17 — 5 epochs  [INFERRED]
   boot#1   03:55–11:13   fire_rows=203  fills=5  | ma_pullback×95, flat_top×44, ignition×31, vwap_reclaim_kev3gate×13
   boot#2   11:13–11:51   fire_rows=25   fills=0  | ma_pullback×8, flat_top×6, v2conv×5, grinder×3
   boot#3   11:57–13:48   fire_rows=83   fills=2  | ma_pullback×56, flat_top×13, kevseq×5, v2conv×5
   boot#4   13:49–13:56   fire_rows=8    fills=0  | grinder×5, kevseq×2, ma_pullback×1
   boot#5   13:58–15:26   fire_rows=82   fills=0  | ma_pullback×50, flat_top×11, kevseq×7, v2conv×5
   TOTAL fire_rows=401 fills=7
```

Read it plainly: **epoch boot#1 is 51% of the day's fire rows and 5 of its 7 fills**, and epoch
boot#4 lived seven minutes. Any 8/17 figure quoted as one number is dominated by one machine that
ran the morning, with four others contributing the afternoon. `fills=7` counts `filled` (4) plus
`retest_fill` (2) plus `tier_fill` (1).

## THE GATE — EG2c (rig/test_gates_20260817.py)

An artifact that reports an aggregate **spanning more than one day** must either name the config
hashes it covers or declare `MIXED-EPOCH` — **inside its LIMITS/CAVEATS section**, where a reader
looking for the caveat will find it. The trigger is narrow on purpose: an explicit date-range
token (`8/11-8/17`, `2026-08-11..2026-08-17`, "through") or an explicit multi-day phrase. Two
dates mentioned in prose do not trip it.

Eight negative controls, both directions: no-LIMITS range doc flags; range doc with unrelated
LIMITS flags; `MIXED-EPOCH` in LIMITS is clean; named hashes in LIMITS is clean; a single-day doc
is not flagged; the `m/d` range form trips identically; two prose dates do not trip; and a
declaration placed OUTSIDE the LIMITS section does **not** satisfy the rule.

Enforced forward from 2026-08-18 (EG4's precedent): the stamp ships tonight, so no earlier
artifact could have named a hash. Pre-existing violators are reported, not failed.
