covers: 1a5e42f0a54e
# BLAST RADIUS CONVENING — 8/17 BATCH 5 (kevseq front-side source audit + M1 wall-clock window class)

Auditor: Blast Radius Auditor (separate context). Tree audited: **`1a5e42f`** (tip), working tree
**CLEAN** (`git status --porcelain` empty, verified this turn). Prior tip `6d66b86` was audited
GREEN in the batch-4 convening (`8a18da0`); that verdict stands and is not re-opened.

Clock: `date` run this turn → **Mon Aug 17 15:20:37 EDT 2026** (~35 min to the close).
Position state per the brief: **NIVF OPEN**; the restart resumes it. Flat-book gate remains
waived by Marcos (batch-4 waiver, recorded not re-litigated) — §6 is the safety proof it demands.

Commits in scope (`git log --oneline 8a18da0..HEAD`, run this turn):

| commit | what | money? |
|---|---|---|
| `9feff24` | kevseq day-gain floor sweep — NO SHIPPABLE THRESHOLD | **no** (doc/killtest only, 0 lines of `marcos_trading_bot.py`) |
| `b78a3ef` | front-side timeframe: alleged 3-min defect REFUTED; 1-min pinned + 3-min stamped | **no** (observability) |
| `1fd978f` | correction: 3-min premise FALSE; real defect = traded-minute vs wall-clock clocks; the switch built on the false premise REMOVED | **no** (observability) |
| `1a5e42f` | `_wallclock_window()` + kevseq caller front-side windowed to 50 wall-min (`M1_WALLCLOCK=1`) | **YES — the one behavior change** |

Whole-batch file census (`git diff --stat 8a18da0..HEAD`): 12 files, and the only executable
production file is `marcos_trading_bot.py` (+116/−6). `screener_app.py`, `newcomer_vision_reader.py`,
recorder/capture services: **untouched**.

## VERDICT: **GREEN** — no blocker. Deploy may proceed on Marcos's word.

---

## 1. THE FALSE PREMISE — independently re-verified, not taken on trust

The handed-over claim ("the kevseq caller supplies `aggregate_bars(..., SETUP_TF_MIN)` = a 3-MIN
front side") is **FALSE against this tree**, confirmed by my own read, not by the commit message:

- **(a) No 3-min value governs anything.** Every occurrence of the 3-min computation in the kevseq
  block (`grep -n "_ks_fs_3m|_ks_c3|_ks_e93|_ks_e203|front_side_3m"`, run this turn) is:
  `:8454` init to `None` · `:8461-8468` compute inside its own `try/except` · `:8504` and `:8547`
  passed to `_log_decision` as a stamp. **Zero reads back into `_ks_ctx`.** The only two writes to
  `_ks_ctx["front_side"]` are `:8483` (caller M1) and `:8492` (self 10s→1m). Rig **TF-a/TF-b/TF-d**
  pin exactly this; both are executed pins, and I re-derived the same result by grep independently.
- **(b) `KEVSEQ_FRONTSIDE_1M` is REMOVED, not defaulted off.** `grep -rn "KEVSEQ_FRONTSIDE_1M\|frontside_1m"`
  over the whole tree returns **only** rig line `3218-3219` — the pin **TF-e** asserting the string is
  absent from the bot source. No env var, no constant, no boot_config key, no dead branch.
- **(c) `b78a3ef` + `1fd978f` are observability-only.** `git diff 9feff24..1fd978f -- marcos_trading_bot.py`,
  comments stripped, is exactly: three new local inits (`_ks_fs_3m`, `_ks_fs_caller`, `_ks_self_fs`/`_ks_self_n`
  hoisted), the 3-min stamp block, the chained assignment `_ks_ctx["front_side"] = _ks_fs_caller = bool(...)`
  (same RHS, same target, plus a capture), five new kwargs on two `_log_decision` calls, one new
  `boot_config` kwarg. **Precedence unchanged** (`:8489` self only when caller is `None` — TF-k),
  **fail-closed unchanged** (`:6665-6667` `kevseq_step` still refuses on `None` — TF-l), and **no
  dollar path byte differs.** The one semantic risk in a hoist — `_ks_self_fs` being read before
  assignment on a partial cycle — is closed by the pre-init at `:8455` and pinned by **TF-g**.

**Doctrine note (Skepticism Needs Verification Too):** the agent wrote REFUTED and *did* name and run
the check (`kevseq_frontside_sources_20260817.py`, caller sign reproduced 31/31, output committed).
The law is satisfied; the reversal of the auditor's own prior framing inside `1fd978f` is the correct
shape (ledgered correction, not a silent edit).

---

## 2. THE ONE BEHAVIOR CHANGE — `_wallclock_window` (1a5e42f)

`_wallclock_window(bars, minutes)` at `:4488`, sole call site `:8479`.

### 2.1 Liquid-name byte-equivalence — pinned AND reasoned
Rig **M1W-a** pins it on a dense 50-bar fixture. I also **executed the helper myself** (exec'd from
source, ring 1) and reasoned the invariant independently:

anchor = `bars[-1].time`; cutoff = anchor − 50 min; a bar is kept iff `ts >= cutoff` (inclusive).
A dense N-bar list has `bars[0] = anchor − (N−1)` min, so for any N ≤ 51 **every** bar satisfies
`ts >= cutoff`. Order is preserved and the same dict objects are appended. My executed probe:
`dense 50 → identical: True, elementwise-identity: True`; `dense 51 → 51 kept`. The window can only
bite when span > count, i.e. exactly where the old code was wrong. **Liquid names: byte-equivalent.**

### 2.2 Short-after-window takes the EXISTING fail-closed path
`:8480` `if len(_ks_1m) >= EMA20_PERIOD + 2:` is **unchanged** — the window sits strictly upstream of
it. Windowed-short ⇒ `front_side` stays `None` ⇒ `KEVSEQ_SELF_FRONTSIDE` fallback (`:8489`) ⇒ if self
is also short, `None` ⇒ `kevseq_step` appends `front_side_unknown` and **refuses** (`:6667`).
Nothing computes an EMA on a truncated list. Pinned **M1W-c** (executes the same `len()` gate),
**FS-j/TF-l/TF-o** (fail-closed), **TF-n** (self fills in only when the caller is short).

### 2.3 Fail-safes — executed by me, not just read
| case | result (my executed probe) |
|---|---|
| unparseable anchor | list returned **unchanged** ✔ (M1W-g) |
| unparseable interior bar (`"junk"`, `None`, `{}`) | **dropped**, no raise → `[17:00, 17:40]` ✔ fail-closed |
| `bars=None` / `[]` / `minutes=0` | `[]` / `[]` / list unchanged, never raises ✔ (M1W-h) |
| thin RBNE-class (48 bars over 243 min) | 24 survive ✔ |
| non-dict bars (tuples) | raises `AttributeError` — **see finding F1 below** |

**F1 (INFORMATIONAL, not a blocker):** the helper's `except (ValueError, TypeError)` does not cover
`AttributeError`, so a non-dict bar list would raise. **Unreachable at the only call site**: `bars` =
`cache[t]["bars"]`, filled at `:8119` from `_fresh_session(get_intraday_bars(...))`, which itself calls
`.get()` on the elements — dicts by construction. And the entire kevseq ctx block sits inside
`try:` `:8452` … `except Exception: pass` at **`:8604`** (matching-indent scan, verified this turn),
so **no exception can escape into the scan loop** under any input. Rail 3 satisfied. Widening the
tuple to include `AttributeError` is a one-word hardening for a future call site, not owed tonight.

### 2.4 Anchoring + `_fresh_session` ordering
Anchor is `bars[-1]["time"]` — **the newest bar's own timestamp, never `now()`** (read at `:4498`,
docstring says the same and the code agrees). Staleness and the day boundary remain `_fresh_session`'s
job, and it runs **first**: `:8119` `cache[t]["bars"] = fresh` is assigned **only if** `_fresh_session`
returned non-empty, and `_fresh_session` enforces today-only + ≤900 s newest bar. So the window can
never straddle a session boundary — it operates on an already-today-trimmed list. Sole windowed site,
so "every windowed site" is that one site. ✔

### 2.5 Kill switch
`M1_WALLCLOCK=0` restores the raw list at the call site (`:8479-8480`, structural — pinned M1W-e);
`KS_FS_WALLCLOCK_MIN` env-tunable; both stamped in `boot_config` at `:12439` with `setup_tf_min`
(M1W-d/f, TF-i). One switch for the whole class, matching the lane-registry precedent.

---

## 3. CENSUS INTEGRITY — verified against the diff, not the doc

Diff hunk ranges for `marcos_trading_bot.py` (`git diff 8a18da0..HEAD | grep ^@@`, this turn):
**4485 · 6452 · 6530 · 8451 · 8500 · 8544 · 12436**.

The five FLAGGED-not-touched sites at their **current** line numbers (`grep -n get_intraday_bars`):

| site | current line | inside any hunk? |
|---|---|---|
| `check_momentum` count=390 | **4199** | NO (before 4485) |
| `_vride_defer` count=VELO_BARS+2 | **9989** | NO |
| `monitor_trade` bars fetch | **11146** | NO |
| volume-sizing guard count=6 | **13173** | NO |
| universal liquidity count=30 | **13261** | NO |

**None is touched.** Rationale accepted as recorded: three have FAIL-OPEN insufficient-data paths, so
windowing would make them *more* permissive on thin names (a money loosening — auditor cannot
authorize); two are position-open paths. **Marcos has ruled: leave all five alone.** Honored.

**No other consumer of `cache[t]["bars"]` was silently altered.** The full census of that key is three
lines: `:8122` (write), `:8204` (`bars = cache[t]["bars"]`, the read the kevseq block uses), and a
comment at `:6552`. Downstream of `:8204`, `bars` also feeds `cache[t].get("full_bars") or bars`
fallbacks at `:8463/:8708/:9035/:9109/:9131` — **all of those receive the RAW `bars`**, not `_ks_1m`;
the window result is bound to a fresh local (`_ks_1m`) and never written back to the cache. Rig
**M1W-j** pins exactly one call site; I re-derived the same count independently.

**Census-doc nit (no action):** `m1_wallclock_20260817.md` cites pre-edit line numbers (:9930, :11087,
:13113, :13201) that this batch's own insertions have shifted by ~60 lines. The *identities* are right;
only the citations drift. Noted so a future reader greps rather than jumps.

---

## 4. RESTART SEMANTICS
No new durable state. `_wallclock_window` is pure; the new locals live one cycle; the stamps are log
kwargs. `_ks_1m_agg` (batch-4) is unchanged and rebuilds from live tape within a cycle. A restart with
`M1_WALLCLOCK=1` simply re-applies the window on the next refresh. `M1_WALLCLOCK=0` needs no state
unwind — it is a read-time branch.

## 5. THE MONEY STATEMENT
**What changes:** on the kevseq lane only, the caller-sourced `front_side` is now computed from the
last **50 wall-clock minutes** of M1 bars instead of the last **50 traded bars**.

**On which names:** **thin tape only.** Where span ≈ count (every liquid name, every fast runner
while it is running) the lists are byte-identical and **nothing changes**. Where the traded-minute
grid stretches — the proven specimens **RBNE (48 bars = 243 min), UUU (49 bars = 584 min = 9.7 h),
FXHO (183 min)** — the caller's "20-bar EMA" stops being a multi-hour trend wearing a 1-minute label.

**Direction, stated honestly — it is BIDIRECTIONAL, not purely tightening:**
1. windowed list falls below `EMA20_PERIOD+2` → caller `None` → self fallback → possibly `unknown` →
   **refusal** (tighter); or
2. the windowed EMA9/EMA20 **flips sign** vs the hours-wide one → a name previously refused
   `front_side_off` can now pass (**looser**), or vice-versa.
Both live behind `M1_WALLCLOCK`. This is a correctness fix to a gate input, not a loosening or a
tightening by design, and it should be graded from `front_side_caller` / `front_side_self` /
`front_side_self_n` on the archive rows rather than assumed.

**Dollar exposure tonight:** `KEVSEQ_CONVERT` defaults **0** in code (`:6469`) — kevseq is a SHADOW
lane, so at the default this changes **rows, not dollars**. Today's front-side-only refusals were
**N=8** (IPST, PFSA ×2, WETO ×2, CDTG ×2, STFS) and 7 of 8 were the `unknown` class the 13:49 self-
frontside fix already closes. Cost of the alleged 3-min defect: **$0 / N=0**.
⚠️ **Carried forward UNRESOLVED from batch-4: I did NOT read the live Railway env this turn —
`KEVSEQ_CONVERT`'s live value is `[UNVERIFIED]`.** If it is `1` live, this is a real-money change on
thin names and must be re-priced by Marcos before deploy. That single env read is the one thing I
would want in hand before the switch is thrown.

## 6. NIVF-RESUME SAFETY PROOF (diff line ranges, batch-3 method)
Hunks: **4485, 6452, 6530, 8451, 8500, 8544, 12436**. Function boundaries (`grep -n "^def ..."`, this turn):

| safety surface | line | in a hunk? |
|---|---|---|
| `_recover_orphaned_trades` (the resume path) | **2954** | NO |
| `_manual_close_pending/_match/_ack` | **5370 / 5390 / 5413** | NO |
| `_place_order` | **9659** | NO |
| `close_position` | **9826** | NO |
| `_vride_defer` | **9978** | NO |
| `_exit_layer` | **10334** | NO |
| `monitor_trade` (and everything below it: stops, `_safety_close`, EOD flatten) | **10650 → EOF** | NO |

The batch's **highest touched line is 12436** (`boot_config` inside `main()`), and every other hunk is
at or below 8552 — i.e. module scope (`4485`), comment blocks (`6452`, `6530`), and inside
`wait_for_flat_top_entry` (the **scan/entry** path, `8451-8552`). **Not one line of the exit, stop,
safety-close, manual-close, or orphan-resume machinery is in the diff.** `python3 -m py_compile
marcos_trading_bot.py` → **COMPILE OK** (run this turn). NIVF resumes on exactly the code that is
managing it now.

## 7. DOCTRINE-INVERSION SWEEP
- **`feedback_skepticism_needs_verification_too`** — inverted? A REFUTED verdict was written. **HELD:**
  the named check exists, was executed, and its output is committed (31/31 signs reproduced). This is
  the law working, and `1fd978f` is a public self-reversal of the auditor's own prior framing.
- **`feedback_auditor_cannot_authorize_behavior`** — inverted? A behavior change (§2) rides an audit
  batch. **HELD, narrowly:** the change is fixing a gate INPUT to mean what its name claims, it carries
  a kill switch, and — decisively — the three fail-open gates whose windowing WOULD have loosened money
  behavior were deliberately **left alone and priced for Marcos** rather than fixed by the builder.
  That is the law being obeyed at the exact moment it was tempting to break. Flagged so §5 goes to
  Marcos priced, not assumed.
- **`feedback_lean_on_10s_data` (10s outranks 1-min)** — inverted? This makes the *1-min caller* more
  faithful while the 10s-derived `self` value stays a **fallback**, not the primary. **TENSION, FLAGGED,
  NOT RESOLVED HERE:** the doc's own reading is that `self` is the more faithful source on the names this
  lane trades, and doctrine leans toward 10s. Precedence was correctly left as a **money decision for
  Marcos** (TF-k pins it unchanged). Grade it from the now-stamped rows.
- **`feedback_no_lesser_fix`** — inverted? One site windowed of six window-sensitive. **HELD under
  permission:** Marcos ruled the other five stay. Recorded as a choice, not a drift.
- **`feedback_dollars_not_r`** — §5 is in dollars and names, with the `[UNVERIFIED]` env caveat stated
  rather than papered over. Held.
- **`feedback_maps_describe_not_serve` / `feedback_edge_over_mechanisms`** — `9feff24` is a REFUTATION
  with no threshold invented and no code change. Exemplary; held.
- **`feedback_rig_tests_spec_not_impl`** — the amended pins **FS-c / TF-c** now require the *windowed*
  call form. I judged the rewrite: the spec genuinely changed with the fix, the pins still assert the
  USER-facing property (the caller's source is M1, not the 3-min aggregate) and merely track the new
  expression. **Legitimate, not green-washing.** TF-e is the stronger form — it pins an **absence**.

## 8. ROLL CALL (every office present, per `data/audits/ROSTER.txt` — 31 offices)
- **Blast Radius Auditor** — this artifact. GREEN, one informational finding (F1, §2.3).
- **Systems Quant** — does `_wallclock_window` compute what its name claims? **YES**, executed
  independently (§2.1/2.3): anchored on the newest bar, inclusive cutoff, order-preserving, identity-
  preserving on dense lists. Finding: name and behavior agree.
- **Feed Engineer + Webull Vendor Desk** — "M1 REST returns TRADED minutes only and is count-capped" is
  now a **ledgered vendor-shape constraint** that has bitten a live detector. This is the office's charter
  case and the census (§3) is the deliverable. Five inheriting consumers remain on the traded grid **by
  Marcos's ruling** — that is a standing vendor-constraint item, not a closed one.
- **Pit Crew Chief** — two new envs (`M1_WALLCLOCK`, `KS_FS_WALLCLOCK_MIN`), both boot-stamped, `=0`
  restores today exactly, no durable state, no restart unwind. Deploy-safe. CLEAN.
- **Execution Surgeon** — no order, fill, limit, or stop-placement byte is in the diff (§6). CLEAN.
- **Trade Manager** — no exit, scale, `_exit_layer`, or EOD-flatten line touched (§6). CLEAN.
- **Strength Ombudsman** — **STAKE**: §5 direction 1 can convert strength into a thin-tape refusal, and
  direction 2 can release one. The bias ledger should record this as an input-correction with a
  bidirectional effect and re-run the refused-strength hearing once `front_side_caller` vs
  `front_side_self` has a week of rows.
- **Side Marshal** — front/back-side is this office's variable. `front_side_3m`, `front_side_tf`,
  `front_side_caller`, `front_side_self`, `front_side_self_n` are now on every kevseq row. **Data-only,
  as the office's charter requires.** No band edge or classifier arm touched.
- **Statistician** — owed a `RESULTS_LEDGER` line: the floor sweep (`9feff24`: best cell 125% no-top3
  HOLD-OUT N=40, +$2.10/tr, **p=0.3415**, curve non-monotone, REFUTED) and the 31/31 source
  reconstruction. Unledgered = rumor.
- **Dashboard Curator** — `front_side_caller` / `front_side_self` / `front_side_3m` and the enriched
  `kevseq_frontside_disagree` canary need a display; today they are archive-only.
- **Integrator** — parallel-logic registry: `_wallclock_window` is the ONE derived windowing path; the
  other five fixed-count fetches remain literal by ruling. Registered.
- **Hidden Entry Architect** — the caller/self clock split is a v2-inheritable finding: a "20-bar EMA"
  on a traded-minute grid is not a 20-minute EMA. The v2 rebuild should take wall-clock windows by
  construction rather than rediscover this.
- **Seam Scientist** — the stamped both-sources distribution is new research surface; no seam mechanism
  touched. CLEAN.
- **Historian** — 8/17 is the day a handed-down "3-minute defect" was refuted in code and the real one
  (two 1-minute clocks) was diagnosed and half-fixed. The refutation and its reversal are both on the
  record; the record is the point.
- **Momentum Operator** — `check_momentum` (**:4199**) is NOT touched (§3); its exempt tuple and vel5
  set are unchanged. CLEAN, and deliberately so.
- **Wind Tunnel Engineer** — **STAKE**: no offline study replicated the live front-side gate. Every
  kevseq dollar figure we hold remains a **front-side-free superset**. That fidelity gap is unchanged
  by this batch and stays open.
- **Crown Steward · Curl Mechanic · Reclaim Architect · Rocket Rider · Handicapper · Cartographer ·
  Kev Librarian · Quartermaster · Opening Bell · First Hour · Convexity Trader · Tape Veteran ·
  Forward Architect · Project Manager · Webull Broker Desk** — **CLEAN**: no crown, curl, reclaim,
  parabolic, selection, map, corpus, warehouse, pre-open, first-hour, tail-shape, broker, or backlog
  surface is in this diff. Named so no office is denied its say.

## 9. SPEC TENSIONS FOR MARCOS (not resolved here)
1. **`KEVSEQ_CONVERT`'s live value is `[UNVERIFIED]`** — read the Railway env before the switch is
   thrown. If `1`, §5 is a real-money change on thin names.
2. **Precedence (caller vs self) is still open** and the doc argues `self` is the more faithful source.
   Both values are now stamped; grade before inverting.
3. **The five flagged fetch sites** stay on the traded-minute grid by your ruling. Three would need
   fail-CLOSED insufficient-data semantics designed first; two are position-open ships.
4. **Window size 50 wall-min** is the fetch's own stated intent, not a measured optimum. It is env-tunable
   and should be graded, not trusted.

## 10. RIG — EXECUTED BY ME, EXIT CODE READ DIRECTLY
Invoked as a **script** (`python3 rig/test_shipset_20260804.py`), never pytest — the rig calls
`sys.exit()` at module scope and pytest INTERNALERRORs on it (batch-4 method note, honored).

Pre-artifact run, `SHIP_CHECK=1`: **638 green, exit 1, ONE RED — section Q only**
(`HEAD 1a5e42f0a54e not covered by data/audits/LATEST.md`) — the designed interlock firing because
this artifact did not yet exist. Sections **FS (12/12), TF (16/16), M1W (10/10)** all present AND
executed green in that same run. Post-commit rerun appended below.

### FINAL SHIP_CHECK (run after this artifact was committed as `fdf2876`)
`SHIP_CHECK=1 python3 rig/test_shipset_20260804.py` → **639 green, ZERO red, EXIT CODE 0.**
Section **Q** (convene-or-don't-ship interlock) **GREEN** — the audited tree is recorded.
Sections FS 12/12 · TF 16/16 · M1W 10/10 green in the same run. Judged by exit code, per
`feedback_rig_tests_spec_not_impl`.

**GREEN. Deploy authorized by the audit; the go/no-go on `M1_WALLCLOCK` (and the
`KEVSEQ_CONVERT` live-env read in §9.1) remains Marcos's.**
