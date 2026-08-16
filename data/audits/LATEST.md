# SHIP CONVENING — 2026-08-16 (Sunday, 11:15 ET) HARDENING: `_curl_feed` 2s memo + entry snapshot AFTER the durable save (+ auditor fix: durable row re-carries entry_context)
covers: 3af620733e4e (HEAD at audit = the auditor's code fix "audit fix (070ed5d caveat)"; audited ship = 070ed5d647a8 "harden: _curl_feed 2s memo + entry snapshot after durable save" on top of acf89f85c11b build #0, audited 31-0 in SESSION_20260816_build0.md). Prior convening archived to SESSION_20260816_build0.md.
Chair: Blast Radius Auditor. Separate-context convening: every claim below is from a `git show`/file read or an execution run THIS session. Clock: `date` run this turn = Sun Aug 16 11:15:15 EDT 2026. No push, no deploy from this convening.

## SHIP DESCRIPTION + AUTHORIZATION
Plumbing hardening answering finding 3 of the build #0 convening (fill-to-monitor latency). Two code commits:
- **070ed5d (audited)**: `CURL_FEED_MEMO_SECS` (default "2", "0" disables) + `_curl_memo` dict + `_curl_memo_lock` (:1088-1090). `_curl_feed` (:1121): on hit returns `dict(bars), src` (a copy); on miss fetches, and stores `(ts, dict(d10), src)` under the lock ONLY when `d10` is non-empty (fail-through on empty/error); bound 512 keys with a stale sweep. Entry site (:12067-12100): `_save_open_trade_sync` now runs FIRST (without `entry_context`), then the eyes snapshot, then the watchdog registration, then `monitor_trade`. Rig section AE (a-g).
- **3af6207 (auditor fix, this convening)**: after the snapshot succeeds, one SYNC merge post `{"ticker","trade_id","entry_context"}` to `/api/open_trade` (:12094-12101) so the durable row carries the eyes again; `_bump("memo_hits")` on memo hit; `memo_hits=` on the EXEC HEALTH line (:8404); rig AE-h/AE-i + `_bump` stub in the AE exec namespace.
Authorization class: observe-only / latency plumbing (no gate, sizing, exit, or order-path logic changes). No Marcos ruling required. Behavior-relevant nuance disclosed in finding 2.

## FINDINGS (each verified by direct read/execution this session)
1. **Memo contract verified by read + execution.** Hit path returns a 2-tuple `(dict-copy, src)` identical in shape to the miss path (rig AE-b executes the real function body: 2 calls = 1 fetch, `_r1 == _r2 == (bars, "alpaca")`). Empty results never cached (AE-d: 2 fetches, memo stays empty). Write is under `_curl_memo_lock`; the read is lock-free on an immutable tuple (a torn read cannot occur — the tuple is replaced atomically by dict assignment). Bounded: sweep at >512 keys drops entries older than TTL; keyed (ticker, n) so n=90/360/720 consumers never see the wrong depth (AE-c). "0" disables (AE-e). Copy-on-return means no caller can mutate the cached bars.
2. **Memo hit skips the canary/halt-awareness block — assessed NOT material.** On a hit `_curl_feed` returns before the 120s-throttled canary print, `_halt_suspect`, `_leader_high_probe`, `_halt_credit_note`, `_leader_violence`, and the DIP_RIP arm (:1152-1188). All are re-run on the next miss, at most 2s later, over the same bars (a halt signature is a >120s zero-trade gap — a 2s deferral cannot hide or create one; the code itself labels the block "LOG-ONLY, one row per episode"). Fresher halt path elsewhere: `_halt5_confirm` (:6959, halt-lane 5s feed) and the LULD-band "halt distance" eye (:9224) do not go through `_curl_feed`'s side-effect block; the frozen-price monitor inside `monitor_trade` (7/28, verified then) reads its own price stream. Net: a 2s-stale halt-awareness LOG on a hot name, never a 2s-stale halt DECISION.
3. **Entry sequence confirmed by read (:12060-12120): fill → `_open_trade` registration → alerts → `_save_open_trade_sync` (blocking) → eyes snapshot (≤3 feed reads, now sharing one fetch via the memo) → [auditor fix] one sync merge post → watchdog `_active_monitors` registration → `_marked_runway` (gate-time value reused when present) → `monitor_trade`.** Stop protection: the resting stop (`stop_order_id`) is placed at the fill BEFORE this block and handed to `monitor_trade`; nothing new sits between the fill and the resting stop. What sits between the fill and the MONITOR's start: the durable save (pre-existing), the snapshot (build #0), and now the ~one-round-trip merge post (this fix; typical <200 ms, worst 6 s only when the screener is unreachable — in which case the first sync save already ate the same 6 s and recovery has bigger problems). Chair judged that acceptable vs the alternative (async poster) — see finding 4.
4. **THE CAVEAT — FIXED, not docketed.** After 070ed5d the durable `/api/open_trade` row no longer carried `entry_context`; `_post_resume_record` (:2734), the watchdog record path (:2776 reads the watchdog ctx — that one WAS still fine), and `_recover_orphaned_trades` close path (:2974) read `o.get("entry_context")` from that row → every restart-recovery record would have lost its entry eyes (the `_entry_ctx_by_trade` registry is process memory and dies with the process). Fix (3af6207, +6 lines): re-post `entry_context` alone via `_save_open_trade_sync`. Why SYNC and not `_save_open_trade` (async): the screener endpoint is MERGE (`_open_trades.setdefault(key, {}).update(data)`, screener_app.py:1378-1396), so a late-landing async post after the trade's own `_clear_open_trade` would recreate a row with trade_id but no entry_price — and the hollow-row guard (:2928) admits any row with a trade_id, so the next boot would "recover" a zero-entry ghost. Sync removes that race by construction. Verified: the monitor's per-loop posts never carry an `entry_context` key (grep: the only writers are the entry site, the watchdog ctx, and the record paths), so merge preserves it for the life of the row.
5. **Rig executed MYSELF after the fix**: `python3 rig/test_shipset_20260804.py` → **ALL GREEN, exit 0**, A..AE (AE-a..i green). SHIP_CHECK=1 result at the foot.
6. **`memo_hits` observability**: trivial, added — `_bump("memo_hits")` inside a try (the `_bump` name binds at module import; the rig namespace stubs it), printed on the EXEC HEALTH line. Ratio = memo_hits vs the curl-feed canary counts in the log.

FIX-NOW LIST: none remaining (caveat fixed in-convening). Tracked: (a) prod `CURL_SOURCE` still [UNVERIFIED] from this seat — under webull-source the memo saves only dict copies (harmless); (b) flat-book-verified-in-turn owed at deploy by whoever deploys; (c) the hollow-row guard admits trade_id-only rows (pre-existing; noted for Pit Crew, not touched).

## DAY-ONE WALKTHROUGH (Monday 8/17, default env, DRY_RUN=true)
- **Every conversion**: durable row appears (without eyes) within the fill's second → the same row gains `entry_context` one round-trip later (inspect `/api/open_trades`: every open row must show `entry_context` non-null within ~1 s of `entry_ts_utc`); watchdog ctx carries it; the record path carries it. Missing on any open row after 5 s = the re-post regressed — pull the cord.
- **Every completed record** (normal, watchdog, resume, recovery): `entry_context` non-null; the tale page renders the entry|exit eyes side by side (unchanged from build #0). A recovery record with `entry_context: null` = finding 4 regressed.
- **Memo hit ratio observable**: `⚙️ EXEC HEALTH ... memo_hits=N` climbs on conversion days (each entry snapshot ≈ 2 hits of 3 reads); zero all day on a day with conversions = memo disabled or keys not colliding — investigate, not a money issue.
- **Passive canary** (carried): zero fill-to-monitor gaps > 15 s in the log.
- **Halt log**: `_log_halt_suspect` rows still appear on halt-signature names (finding 2 — deferred ≤2 s, never suppressed).

## DOCTRINE-INVERSION SWEEP
doctrine-inversion sweep: n/a — no rule about who trades, what gates, or what is exempt changes; the memo is a transparent cache with fail-through, the ordering change moves instrumentation after the persist.

## ROLL CALL (every ROSTER.txt office, 31)
- **Blast Radius Auditor** (chair): finding — memo contract executed; caveat confirmed real (three recovery readers of a field the row no longer had) and FIXED with the race-free variant; sequence read line-by-line.
- **Dashboard Curator**: finding — tale/history eyes render unchanged; recovery records now keep their entry block on the tale page (they would have gone blank under 070ed5d alone).
- **Systems Quant**: finding — memo returns what its name claims (copy, tuple shape, keyed by n); `memo_hits` counts hits only (misses = canary counts).
- **Pit Crew Chief**: finding — kill switch = `CURL_FEED_MEMO_SECS=0`; no deploy here; hollow-row guard admits trade_id-only rows (tracked, pre-existing); flat-book at deploy owed.
- **Integrator**: finding — all four `entry_context` consumers enumerated (:2734 durable, :2776 watchdog ctx, :2974 durable, :12225 record/registry) and each now has a live source; `post_to_dashboard` back-fill (:10234) unchanged.
- **Side Marshal**: clean — `_side_state` untouched; its `_curl_feed(n=360)` read is memo-keyed separately.
- **Crown Steward**: clean — crown stamps unchanged; `_leader_high_probe` deferred ≤2 s on a memo hit (finding 2), never dropped.
- **Feed Engineer**: finding — under alpaca-source the entry snapshot now costs one `/hot` GET instead of up to three; empty/error never cached so a hiccup cannot pin a name to no-bars for 2 s.
- **Webull Broker Desk**: clean — no order-path change; resting stop placement precedes the whole block.
- **Quartermaster**: finding — durable open-trade rows again carry `entry_context` (his restore-drill expectation for open-trade rows: eyes present).
- **Kev Librarian**: clean.
- **First Hour**: clean — no window logic; attribution gains nothing new beyond build #0.
- **Opening Bell**: clean.
- **Seam Scientist**: clean.
- **Strength Ombudsman**: clean — no gate touched.
- **Forward Architect**: finding — hollow-row guard tightening (require entry_price for a resume/close) registered as a hypothesis for the post-freeze backlog.
- **Momentum Operator**: clean.
- **Trade Manager**: clean — exits untouched; monitor start delayed by one merge post (finding 3, bounded).
- **Tape Veteran**: hypothesis — a 2 s memo means two consumers within 2 s see identical bars; nothing decides on sub-2 s deltas from `_curl_feed` (10 s bars) — recorded, no action.
- **Reclaim Architect**: clean.
- **Execution Surgeon**: finding — fill-to-monitor path now = persist + snapshot(1 fetch) + 1 merge post; canary carried.
- **Handicapper**: clean.
- **Rocket Rider**: clean.
- **Cartographer**: clean — `_marked_runway` reuses the gate-time value; its `n=720` read memo-keyed.
- **Wind Tunnel Engineer**: clean.
- **Statistician**: finding — `memo_hits` registered on the exec-health row (`_log_decision("_exec_health")` unchanged in fields; print line only).
- **Convexity Trader**: clean.
- **Curl Mechanic**: finding — canary print now fires on misses only; a "stale vs absent" read is still visible every 120 s per name (memo TTL 2 s ≪ 120 s throttle).
- **Project Manager**: finding — tags: rig ALL GREEN incl. AE-a..i [VERIFIED]; caveat fixed [VERIFIED]; prod CURL_SOURCE [UNVERIFIED].
- **Historian**: finding — for the record: the first convening whose caveat was closed in-room with a code fix (two-commit pattern: 3af6207 code, bookkeeping commit follows).
- **Hidden Entry Architect**: clean.

## VERDICT
Room vote on "070ed5d + 3af6207 (HEAD) are ship-clean as audited (memo contract executed, fail-through, bounded, kill switch; entry order persist-first with the durable eyes restored; halt-awareness deferral immaterial; rig ALL GREEN incl. AE; no doctrine touched; no push/deploy from this convening)": **31-0 APPROVE, 0 blocking**. Flat-book-verified-in-turn owed at the moment of deploy.

SHIP_CHECK result (run after the bookkeeping commit): see the chair's return message.

— Convening closed 2026-08-16 (clock cited above). Blast Radius Auditor, chair.
