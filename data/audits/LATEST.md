# 25TH CONVENING — HIDDEN OBSERVE-ONLY SPLIT (8/14)
covers: a3032f670982  (code+rig commit "hidden observe-only split (HIDDEN_CONVERT, default 0) — Marcos order 8/14 01:39")

## THE SHIP
Marcos's verbatim order, 8/14 01:39 AM ET: **"we have to move hidden to observe"**.
Context: hidden v1's entry signal is REFUTED (F-control −$4,012, 13% win — data/killtests/hidden_fix_sweep_20260813_RESULTS*); its era profits were fictional-fill accounting (struck 8/13). The split:
- New env `HIDDEN_CONVERT` (marcos_trading_bot.py:5516), default "0" → observe-only.
- New `if not HIDDEN_CONVERT:` branch (:7338) consumes the fire and stamps a `hidden_observe_only` decision row BEFORE the cap check, so the crown/leader bypass (`not _is_leader(t)` at :7350) can never reach `breakouts.append`.
- Detection stays fully LIVE: `hidden_entry_step` (:7058) and `hidden_shadow_fire` logging (:7063) are outside any HIDDEN_CONVERT gate — the v2 rebuild's evidence stream is untouched.
- Rig section W added (rig/test_shipset_20260804.py:1289): executes the env-pin default, asserts observe-branch ordering upstream of the cap/crown check, evidence row, fire consumption, crown stamp, detection ungated.

## FINDINGS PER DIMENSION
1. **Correctness — PASS (verified by read, :7331–7396).** `HIDDEN_CONVERT = os.environ.get("HIDDEN_CONVERT", "0") == "1"` → default False. The observe branch is the FIRST arm of the if/elif chain inside `if _he_fire and HIDDEN_ENTRY and _hm_curl >= ENTRY_OPEN_ET:`; the crown-bypass cap check (:7349), the ext-gate arm (:7353), and the convert else-arm (:7371, the only `breakouts.append` for hidden, :7383) are all `elif`/`else` — unreachable when HIDDEN_CONVERT is False. No other path appends `"hidden_entry"` to breakouts (grep confirms :7383 is the sole site).
2. **Detection unharmed — PASS.** `hidden_entry_step` call (:7058) and `hidden_shadow_fire` row (:7063) sit in the detection block, ungated by HIDDEN_CONVERT. The combined-fire block (:7109) still sees `_he_fire` non-None (consumption happens at :7343, inside the entry-window gate) — identical to how hidden_capped/hidden_ext_reject fires flowed before.
3. **Blast radius — PASS.** All `_he_fire` consumers enumerated (:7013 init, :7058 set, :7109/:7112/:7116 combined-fire reads, :7331 gate, :7338/:7342-43 observe consume, :7353/:7366-67 ext-reject consume, :7372-73 convert consume). The new `_log_decision(t, "hidden_observe_only", ...)` uses only keys present on the `hidden_entry_step` fire dict (:5601-5602: stop, wick, anchor, ext_vwap, seq, px, k) — wick/px via .get, others direct, all exist. `_sess_he`, `_k_he`, `_he_day` (reset defensively :7334-35), `_he_name`, `_is_leader` all defined before the branch. No NameError path. Stale-price-fix block behavior unchanged.
4. **Restart semantics — PASS.** No counters mutated in the observe branch (`_he_day`/`_he_name` are read-only there); rows are decision-log only. Nothing new to rehydrate.
5. **Rig — PASS.** `python3 rig/test_shipset_20260804.py` run in this convening: ALL GREEN; section W passes ("hidden observe-only: default off + upstream of crown bypass + evidence row").
6. **Doctrine — see doctrine-inversion sweep below.**
7. **Strength/weakness bias — Marcos-priced.** Observe-only removes the hidden lane's strength access (crowns included). This is NOT auditor-authorized: it is Marcos's direct verbatim order above, priced by the F-control (−$4,012 vs don't-trade). Ombudsman records it as a priced strength refusal, graded by the v2 program.

Non-blocking pre-existing note: a hidden fire arriving before ENTRY_OPEN_ET is neither consumed nor observe-rowed (the :7331 window gate) — unchanged behavior from before this ship; hidden_shadow_fire still records it at detection. Logged for the Hidden Entry Architect, no fix authorized here.

## DOCTRINE-INVERSION SWEEP
This ship deliberately inverts standing doctrine — enumerated, all priced by Marcos's order, none accidental:
- **Leader meritocracy ("winners bypass rations", 8/5):** the crown bypass at :7350 and the crown ext-band bypass (HIDDEN_EXT_CROWN_BYPASS, :7362) are now unreachable for hidden while observing. INTENTIONAL — the order explicitly includes crowns ("env-cap-only was rejected as leaky: crowns bypass caps via not _is_leader(t)").
- **Convert-at-detection (7/24 Marcos: "we see it triggered but now do nothing!!"):** hidden returns to detect-but-don't-trade. INTENTIONAL — the 7/24 doctrine assumed the signal had edge; the F-control refuted that premise for hidden v1 specifically. Zone-flip/reclaim/dip-rip conversion paths untouched.
- **8/12 cap raise (hidden 5) and 8/6 crown-scoped ext gate:** idle (downstream of the observe gate), not repealed — they re-arm verbatim if HIDDEN_CONVERT=1 is ever set.
- Swept the rest of the system for old-doctrine encodings: monitor/exit paths for already-open hidden trades unchanged (correct — no open hidden positions are created going forward; existing ones exit normally); dashboards will show observe rows via the decision log (Curator queue item below). No other doctrine touched.

## DAY-ONE WALKTHROUGH (Friday 8/15)
A hidden wick fires on some runner at, say, 09:47: `hidden_entry_step` returns the fire → `hidden_shadow_fire` row stamps at detection (unchanged) → combined-fire block runs stale-price logic (unchanged) → :7331 gate passes (RTH, past ENTRY_OPEN_ET) → :7338 `not HIDDEN_CONVERT` is True → fire consumed, **`hidden_observe_only` row** with price/stop/anchor/ext_vwap/seq/fire_px/wick/crown/sess/day_n/name_n → `continue` never reached, loop proceeds to other detectors for t. Expected Friday: `hidden_observe_only` rows wherever hidden would previously have converted, capped, or ext-rejected (all three prior arms now funnel to observe); **ZERO `triggered_hidden_entry` rows all day — that is the canary.** Also expect zero hidden_capped / hidden_ext_reject / cap_raise_slot rows (their arms are downstream). hidden_shadow_fire rows continue at normal cadence (detection-health check).

## ROLL CALL (STANDING ROOM — every office, 8/10 law)
- Blast Radius Auditor — convener; findings above; SHIP.
- Hidden Entry Architect — TOUCHED: this ship is the v1 shutdown their charter requires; observe rows + shadow fires = the v2 evidence stream; confirms every v2-needed field rides the row. SHIP.
- Crown Steward — TOUCHED: crowned names lose hidden access by design; recorded as a Marcos-priced client-service reduction, crown= stamp on every observe row preserves the crown ledger. SHIP.
- Strength Ombudsman — TOUCHED: priced strength refusal (F-control −$4,012); enters the BIAS LEDGER as Marcos-authorized, graded by v2. SHIP.
- Side Marshal — clean: no side/gate logic touched; observe rows carry sess for their books.
- Systems Quant — TOUCHED: verified the code computes what the name claims (default-0 env pin executed in rig W; branch ordering asserted against source). SHIP.
- Integrator — TOUCHED: all consumers/seams of _he_fire enumerated (finding 3); no parallel-logic copy of the hidden convert path exists. SHIP.
- Pit Crew Chief — clean: no restart/rehydrate surface changed; deploy via ship.sh in main session, not here.
- Dashboard Curator — clean w/ queue item: hidden_observe_only rows surface via existing decision-log views; a dedicated observe-lane tile goes on the upgrade queue, not this ship.
- Feed Engineer — clean: no feed/vendor path touched.
- Webull Broker Desk — clean: fewer real orders, no order-semantics change.
- Quartermaster — clean: no data/storage path touched; decision log grows normally.
- Kev Librarian — clean: Kev corpus untouched; hidden v2 remains Kev flush-entry grounded.
- First Hour — TOUCHED (minor): the 9:30–10:30 window loses hidden conversions; attribution will show the lane's absence — expected, priced.
- Opening Bell — clean: pre-open prep unchanged; pre-ENTRY_OPEN_ET fires behave as before.
- Seam Scientist — clean: seam program untouched; observe rows are new specimen material.
- Forward Architect — clean: no new hypothesis shipped; v2 rebuild owns the follow-on.
- Momentum Operator — clean: ships on evidence (F-control), not noise.
- Trade Manager — clean: exits/monitors for any legacy open hidden trade unchanged.
- Tape Veteran — clean: outside hypothesis (v1 fired on exhaustion wicks in blue-sky) already registered with the Architect.
- Reclaim Architect — clean: reclaim shares the 10s feed but its fire path is untouched (verified :7051).
- Execution Surgeon — clean: no orders from this lane → no planned-vs-realized surface.
- Handicapper — clean: selection/character book untouched.
- Rocket Rider — clean: rocket_catcher stays superseded; parabolic regime unaffected.
- Cartographer — clean: maps/levels untouched.
- Wind Tunnel Engineer — TOUCHED: the F-control kill-test (hidden_fix_sweep_20260813) is the evidence basis; fidelity already graded there.
- Statistician — TOUCHED: RESULTS_LEDGER entry appended this convening; hidden P&L now cleanly partitioned (no new fills to contaminate).
- Convexity Trader — clean: 13% win with negative mean = no tail worth keeping; concurs with shutdown.
- Curl Mechanic — TOUCHED: fire-count acceptance shifts to hidden_observe_only + hidden_shadow_fire rows; Friday cadence check owned here.
- Project Manager — clean: morning brief adds the canary check (zero triggered_hidden_entry).
- Historian — TOUCHED: records 8/14 as hidden v1's end-of-conversion date; era hidden profits already struck 8/13.

## VERDICT
**SHIP — unanimous, 31/31.** No blocking findings. Deploy via ship.sh in the main session only; do not push from this convening.
