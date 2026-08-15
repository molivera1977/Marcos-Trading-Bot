# THE EYES AUDIT — 2026-08-15 (run 8/14 ~22:45-23:00 ET)
Mandate (Marcos 8/14 ~23:00): "I want all of these ideas that I developed, was promised, and okayed for build actually built. These are the eyes of the bot."
Method: RESULTS_LEDGER.md read end-to-end (1,969 lines) → promised-list → PRODUCTION evidence only (decision rows via /api/decisions_archive 8/11-8/14 + rolling /api/decisions, trade records, nightly_verify.log, OOS_WALL.md, launchctl, live endpoints). Code reading alone counts for NOTHING (founding exhibit: freshness contract + runway wall dead-at-birth 8/7→8/14 via missing tuple unpacks).
Evidence base: 11,283 decision rows today (8/14); 13,921 (8/13); 11,726 (8/12); 10,823 (8/11); 9 trades today.

---

## ⚠️ DEAD / DEAD-SUSPECT — FIX FIRST

1. **STICKY STAND-DOWN (#28, promised+shipped 8/8)** — DEAD-SUSPECT. Promise: "ceiling fire binds the ticker's chart lanes... standdown_active rows". Evidence: 4 `ceiling_reject` rows TODAY (e.g. archive 8/14) and **zero `standdown_active` rows in all four archived days (8/11-8/14) and the rolling 8000-row window (matched:0)**. Same silent-death signature as the tuple-unpack class. Drill/fix: exec-trace `_ceiling → standdown bind` on today's 4 ceiling specimens; if the row-writer is unreachable, this is the third dead-at-birth mechanism.
2. **CROWN PRE-CAP EXEMPTION (promised 8/12, "crown_pre_exempt rows for visibility")** — DEAD by its own canary. The 8/14 01:30 convening pre-registered: "zero crown_pre_exempt... rows day-one — 2nd zero-day = code-path escalation." Day two closed with **matched:0 era-window, 0 in 8/12-8/14 archives**. Escalation is now due: force-path drill (synthetic crowned PRE candidate through the session-cap recheck).
3. **AMBIENT DOLLAR FLOOR (AMBIENT_DVOL_MULT, shipped 8/6)** — DEAD-SUSPECT. Boot row stamps `ambient_dvol_mult` (config alive) but **zero ambient reject/skip rows in 4 days of halty microcap tape** (era kill-test predicted ~25 blocked trades/era; rolling window matched:0). Either the floor never binds at current mult or the row path is dead. Drill: replay today's thinnest fills through the ambient check with logging; confirm the reject row-writer fires on a synthetic sub-floor bar.
4. **PREMKT_CAPPED queryable rows (shipped 8/12)** — borderline (cap 10 may genuinely never bind at ~5-9 PRE trades/day), but it shares the 8/14 canary sentence with crown_pre_exempt. Drill: temporarily assert the row-writer with cap forced to 1 in rig exec-eval.

Resurrection confirmed today (formerly DEAD, now ALIVE): **freshness auto-map** — first-ever `auto_map_used:true` rows landed 8/14 12:58 (MF, old_break 25.1 → new_break 16.6), 10 rows today after the 8/14 unpack fix.

---

## FULL TABLE (mechanism | promised | status | production evidence)

| Mechanism | Promised | Status | Evidence (8/14 unless noted) |
|---|---|---|---|
| Chart-as-gate + enforce | 7/17 settled; enforced era | ALIVE | chart_gate_allow 75, chart_gate_block 17, chart_gate_blocked_trade 22, chart_gate_skip 5 |
| Vision reads + rereads | 8/4-8/6 | ALIVE | reread_latency 93 rows; reread_overdue 2 |
| Blue-sky comeback/summit maps + first-read | 8/6; first-reads 8/13 #54 | ALIVE | FGI 8/13 self-posted summit maps 16.50→18.45 (ledger, rows-verified); 8/14 reader first light 07:00:14 |
| Born-exhausted reread reroute | 8/14 item | ALIVE | read_exhausted_observed 17 rows |
| Auto-read on mapless fire | 8/13 #54 | ALIVE | read_requested 2 rows |
| Kev unconditional reads (inversion fix) | 8/13 | BUILT-UNPROVEN | shipped in #54 batch; no distinct row type. Drill: Monday 07:0x — confirm reads posted for all 3 Kev-sheet names |
| Freshness contract + breach alarm | 8/7 ("fucking do it") | ALIVE | freshness_breach 46 rows; freshness_eod 2 rows |
| Freshness AUTO-MAP floor | 8/7 | ALIVE (resurrected today) | auto_map_used:true ×10 from 12:58 (was dead 8/7→8/14, tuple unpack) |
| Runway gate + class-aware rungs/majors | 8/4 | ALIVE | runway_pass 12 (road_cls MAJOR, road_band, runway_rr stamped); runway_reject 22 |
| Runway WALL / spent-rung demotion | 8/8 (#27 close) | BUILT-UNPROVEN | unpack fixed 8/14 (ef55647, rig X-a pin); no distinct demotion row exists. Drill: replay a spent-rung day, assert wall-capped target in runway rows |
| Chart ceiling gate | 8/3 | ALIVE | ceiling_reject 4 rows |
| Break-side gate (+1% tol) | 8/3→8/8 | ALIVE | breakside_reject 17 rows |
| Back-side gate | 8/5 | ALIVE | backside_reject 14 rows (dd/stale stamped) |
| SIDE stamps (Marshal) | 8/8 | ALIVE | 264 rows with side today (front 140 / back 78 / reclaim 31 / basing 7 / unknown 8) — fixed from all-unknown 8/8 |
| Lens (stage 3) | 7/27 runway doctrine | ALIVE | lens_focus 279, lens_unfocus 205, lens_dark 1 |
| Crown system + rehydrate | 8/5 | ALIVE | leader_armed 14 rows; rehydrate proven 8/5 restart ("2 leaders restored") + 8/10 ×17 restarts |
| Crown freshness (_ts fix) | 8/13 21:00 | ALIVE | crown maps refreshing (MF auto-map row on crowned name) |
| entry_crown stamp on trades | 8/8 | ALIVE | today's trade record entry_crown=True (trade_id 118d8a0c…) |
| Leader meritocracy privileges (3× ammo/slots, uncapped, 60s reads, 1s pin) | 8/5-8/12 | ALIVE | leader_armed rows; 1s crown pin shipped 8/12 (auditor 8/8 GO); boot stamps leader_ammo/leader_curl_slots |
| Min-stop floor + exemptions | 7/27; 4% ruling 8/2+8/12 | ALIVE | minstop_reject 14 rows; boot stamps min_stop_pct/min_stop_exempt |
| Stop-coherence floor 0.5% (refuse + observe-only) | 8/13 | BUILT-UNPROVEN | zero stop_coherence_* rows ever (census said ~3/era — rare is plausible). Drill: rig exec-eval forcing a <0.5% pre-fill width; watch first live specimen |
| Retest band gate | 8/4 | ALIVE | boot retest_band stamp; retest_wait 3 / retest_fill 3 (real-print fill src per 8/14 ship); retest_expired 8/13 |
| Veto-as-data (no one has veto) | 8/12 | ALIVE | veto_noted_not_gating 10 rows |
| Tape pre-break gate | 8/3 | OFF BY VERDICT | TAPE_PREBREAK_GATE=0 since 8/4 (pre-registered failure condition met) — not dead, decommissioned |
| Ambient dollar floor | 8/6 | **DEAD-SUSPECT** | see top section |
| Day-gain floor + split-adjust guard | era; corruption found 8/14 (DFNS 5152%) | ALIVE (guard stamp-only per Marcos) | daygain_reject 75 rows |
| Ignition cell stamps / census cell gate | 8/14 (stamp-only default) | ALIVE | ignition_below_convert 35, triggered_ignition 31, ignition_ext_live_skip 3 |
| Observe-only splits: hidden / flat_top / reclaim | 8/14 | ALIVE | hidden_observe_only 37, flat_top_observe_only 21, reclaim_shadow_fire 56 (hidden ALSO converted today ×40 = Marcos's 09:52 live-tape override, as ordered) |
| v2 calibrated shadow (Hidden Architect) | 8/14 | ALIVE | v2_shadow_fire 250 rows; OOS_WALL day-1 v2 N=250 $-2943.88 graded |
| Grinder shadow + conversion (O-config) | 8/14 night | BUILT-UNPROVEN | commit 08e8639 + 31-0 convening (200afb7); OOS_WALL notes "grinder detector not yet deployed so N=0 expected; wall proper starts Mon 8/17". Drill = Monday's first grinder rows |
| flat_top BREAK-attack | 8/14 round 7 | BUILT-UNPROVEN | same commit/convening; first fires Monday |
| E3 exits (bank ½ +10%, 10%-off-high trail) | 8/14 | BUILT-UNPROVEN | shipped in 08e8639; zero fills through E3 yet. Drill: Monday first conversion traced through scaffold |
| Sticky stand-down (#28) | 8/8 | **DEAD-SUSPECT** | see top section |
| Counter economy (ticket/refund/conservation) | 8/7 #34 | ALIVE | slot_refunded 47 rows |
| Restart machinery (resume/counters/rehydrate) | 8/8 #35 | ALIVE | counters_rebuilt 3 rows today; trade_resumed proven 8/10 (~10 live cycles); boot barrier clean 8/10 drill |
| Kill-under-fire drill | verdict 8/11 (Wed 13:30) | OWED — never executed | missed 8/12 ("owned; hard-scheduled Thursday"), no ledger record of execution since. Trial gate still open |
| Intrabar stop | 8/2 | ALIVE (config) | INTRABAR_STOP=1 env-verified 8/13 session; boot stamp intrabar_stop |
| Off-tape exit guard | 7/27 | ALIVE | off_tape_exit 4 rows today |
| Resting broker stop + ratchet sync | 8/2 + 8/8 | BUILT-UNPROVEN | DRY_RUN returns fake stop ids by design; $5 live place+cancel + double-sell-race NEVER executed (owed since 8/2, re-owed 8/14 convening) |
| Resting-limit SELL tiers (#53) | ratified 8/13 | BUILT-UNPROVEN | RESTING_SELLS off (8/14 17:20 entry); proving-week item; no live path exercised |
| exit_ts stamps | 8/14 | ALIVE | trade record exit_ts_utc=2026-08-14T19:31:33Z |
| Honest fill register (tape-since-birth) | 8/13 | ALIVE | nightly_verify 8/14: "7 trades raw $-54.35 | FICTION 0" (11:32 run); 8/13 fictions correctly caught |
| Nightly book verifier (launchd 22:45) | 8/13 | ALIVE (watch tonight) | log rows 8/13+8/14; launchctl com.marcos.tradingbot.bookverify loaded (last exit 2 = the designed fiction-regression alarm from 8/13's FICTION>0 run); first fully-scheduled run tonight 22:45 — confirm log line |
| Nightly shadow grader / OOS wall | 8/14 | ALIVE | com.marcos.tradingbot.shadowgrade loaded exit 0; OOS_WALL.md day-1 row appended 8/14 |
| Books backup 22:30 | 8/12 | ALIVE | books_20260814_2230.tar.gz (4.5MB) landed in iCloud 22:30 tonight; restore drill passed 8/12 |
| 1s capture (hot-15 + crown pin) | 8/7/#39 + 8/12 | ALIVE | Quartermaster 8/12 sampling: 7-15.5k 1s bars/name (SCKT/PLAG/MSGY) |
| 5s capture + hot5 + consumers | 8/6 | ALIVE | halt_arm rows carry confirm5s/upratio/maxpull (5s-fed); hot5 endpoint live since 8/10 batch |
| Halt lane (arm→convert, cooldown/side stamps) | 8/8 | ALIVE | halt_arm 3 rows (WETO 09:47 prox 0.99, mins_since_halt 8.2, convert:true) |
| Early-arm shadow band | 8/8 | ALIVE (thin) | halt_early_arm rows 8/11 ×3, 8/12 ×2; zero 8/13-8/14 (band names scarce, watch) |
| Seam lane H2 shadow + heartbeat | 8/8 + 8/13 | ALIVE | seam_beat 6, seam_shadow_fire 1 (13:08, front_side) |
| Day-2 observer | day2 board | ALIVE | /day2 HTTP 200; lens rows feed it |
| EOD crown/freshness reports (#36) | 8/8 | ALIVE | crown_eod_report 28 rows + freshness_eod 2 rows today (16:20 daemon fired) |
| EOD winner sweep / evening scan | evening_scan.py | BUILT-UNPROVEN | no production row/log verified this audit. Drill: run log check next EOD |
| Kev sweep (night+morning, retries, guards) | 8/4+ | ALIVE | kev_sweep 4 rows today; Thursday sheet posted 8/13 via YouTube |
| TikTok backstop (#45) | 8/11 | ALIVE | /api/kev_tiktok_probe ok:true n=6 this audit; caught its first live sheet 8/12 morning |
| Frame-vision check (#32) | 8/8 | ALIVE | NAMI/CLRO recovery + vision cache; production catch 8/9 (manual assist) + shipped retry 8/9 |
| Duty portal (#44) | 8/10 | ALIVE | /duty HTTP 200 this audit; first live Q&A proven 8/10 22:02 |
| PRE session machinery (07:00-9:25, cap 10, flatten) | 8/10-8/12 | ALIVE | premarket_shadow_entry 25 rows; PRE trades in book; preopen_health 1 row |
| Reader start 07:00 | 8/12 | ALIVE | first read 07:00:14 on 8/14 (24th convening, day-one tape) |
| Deploy freeze + auto-expiry | 8/6+8/13 | ALIVE | entries_paused 13 rows 8/13; 60s auto-expiry drill proven 8/13 16:27 |
| Gate fail-open meter (#33) | 8/8 | ALIVE | gate_fail_open 2 rows today |
| Perimeter meter + wall (enforce token) | 8/8 | ALIVE (meter) / BUILT-UNPROVEN (refusal path) | perimeter_stamp 9 rows; perimeter_refused zero-ever = the wall never had to refuse (good) — drill: rig exec-eval pathless order → refused row |
| Board funnel (scanner = the universe, 60s) | 8/10 | ALIVE | board_funnel_fallback 1 row (fallback path exercised too); /api/scan 200, 21 names |
| Dashboard strips / premarket RTH parity / shadow board | 8/4-8/12 | ALIVE | /premarket 200, /dashboard strips serving; shadow rows populate board |
| Boot config stamps | 8/4 | ALIVE | boot_config 5 rows, 39 knobs incl. rung_ratchet/backside/breakside/mapless/reentry_crown_usd |
| Rung ratchet | 8/4 | ALIVE | boot stamp rung_ratchet; CELZ +$59.65 production capture 8/6 |
| Crown re-entry dollar rail | 8/5 | ALIVE (unexercised recently) | reentry_eligible 9 rows today; rail proven era 8/5 |
| Mapless block | 8/6 | ALIVE | mapless_reject 2 rows today (21 on FGI 8/13) |
| VWAP-side sizing 0.25 field | 8/8 | ALIVE | vwap_side_sized 2 rows today (3-4/day all week) |
| Stale-fire / stale-swap guards | 8/4 | ALIVE | stale_fire_suppressed 81, stale_swap_refused 69, stale_price_fix 1 |
| Kev primacy A/B (vision governs, kev_shadow) | 8/12 | ALIVE | Friday prereg frozen; kev_shadow recorded; veto rows data-only (10 today) |
| Hidden observe⇄convert switch | 8/14 | ALIVE | both row types today (override day, by design) |

---

## BUILT-UNPROVEN — the drill list
1. Runway WALL demotion — replay a spent-rung specimen; assert wall-capped target (post-fix, first natural specimen Monday).
2. Stop-coherence floor — forced sub-0.5% width through rig exec-eval + first live specimen watch.
3. Resting broker stop — the $5 place+cancel + double-sell race (owed since 8/2; go-live blocker).
4. Resting-limit sell tiers (#53) — build finishing this week; rig + $5 pair test.
5. O-config: grinder conversions + flat_top break-attack + E3 exits — Monday 8/17 first fires; nightly wall grades.
6. Kev unconditional reads — Monday 07:0x: reads present for all Kev-sheet names.
7. Perimeter refusal path — rig exec-eval pathless order → perimeter_refused row.
8. premkt_capped row-writer — rig with cap forced to 1.
9. EOD winner sweep — verify next run's log/output.
10. Kill-under-fire drill — still never executed (missed 8/12); schedule Monday with a DRY position.

## NEVER-BUILT — build queue (ledger citations)
1. **vwap_reclaim BAND-PASS variant (2-5min hold)** — registered 7/29, frozen 7/31 (ledger 8/8 "FRONT/BACK ARMS" + 8/14 12:30: "7/31 band-pass (2-5min hold) never encoded — the retrial build"). The coded variant is the refuted just-crossed band. In tonight's rebuild track per Marcos 8/14 12:18.
2. **Vertical-regime entry lane (#48)** — named open hole 8/5 (leader charter), registered as task #48 on 8/11 (~23:55 item #3B), priced repeatedly (WYHG/RDGT/THH 8/10; SCKT 5s vertical 8/11). Post-freeze design; no code.
3. **Auto-deploy disable on all three services** — ordered 8/14 17:20 ("FIX TONIGHT: disable auto-deploy... ship.sh becomes the only deploy path"). No ledger entry records it done; the seal-test comment sits in the ledger unresolved. Verify/execute tonight.
4. **ship.sh server-side enforcement + freeze wiring** — 8/14 01:30 concern #3 ("bare railway up bypasses it... wire it in"); convention-only today.
5. **TTL(600s)/FRESH_MAX_MIN alignment** — 8/14 01:30 concern #4; coincidental equality, not explicit.
6. **Catalyst/news awareness** — named open hole 8/11 (Kev SCKT: "NEWS was the fuel"); never approved as a build — needs Marcos's word to enter the queue.

## Counts
ALIVE: 55 · BUILT-UNPROVEN: 10 · DEAD/DEAD-SUSPECT: 4 (standdown_active, crown_pre_exempt, ambient floor, premkt_capped-borderline) · NEVER-BUILT: 6 · OFF-BY-VERDICT: 1 (tape pre-break) · OWED DRILL (standalone): kill-under-fire.
