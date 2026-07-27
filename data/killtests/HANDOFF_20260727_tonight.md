# HANDOFF — tonight's change-set (7/27, verdicts final, Marcos-approved)

**Read first:** `OUTCOME_PASS_20260727.md` (evidence) + RESULTS_LEDGER 7/27 entries (verdicts + 2 reversals).
Rules: one change-set, rig-gated, push only after flat + close (RTH law). No gate changes. Exit codes judge sweeps.

## The set (all approved in-session by Marcos)
1. **TRUE INTRABAR STOP** — stop touched on 10s/stream price → exit immediately at stop (Marcos reaffirmed 3×: "tired of −3R, −2R, −1.5R"). Keep 2R crater floor BENEATH it as broken-feed failsafe; 3-min structural exits unchanged above. Rig: LGHL+JZXN 7/27 replays exit at the stop bar; LVWR-7/24+DFNS replays now stop ~−1R (accepted cost, ≈$57 vs $441 saved).
2. **sessions=["PRE","RTH"]** on monitor/scan bar fetches (clock <09:30 or PRE-stamped position) + fix the hardcoded-EDT DST bomb in `_alpaca_intraday_bars`. Fail-without-fix rig test. Only after rig-green may ENTRY_OPEN_ET revert to 04:00 (do NOT revert tonight).
3. **BE_FLOOR_AFTER_SCALE 2→1** (law-compliance; measured harm only −$7.98 but it's Marcos's law).
4. **HIDDEN R-TRIM** — R-based first trim (+1R class) on hidden_entry; %-tiers retained above. Evidence: lane's closed record is 2/2 peaked-unbanked-red (VEEE 6.9R peak → −$25.33; LVWR 1.62R → −$39.29); ×1.50 first trigger unreachable (58c9816 inheritance). Rig: trim fires on VEEE+LVWR replays.
5. **ENTRY TIMESTAMP** stamped on every trade record (0/149 era rows have one — blocked 4 outcome queries; recorded_at is EXIT time).
6. **READ-LIST LIQUIDITY FLOOR** — same 10k/bar floor at `_post_read_list` selection as at entry. Rig: sub-floor name never reaches the posted list.

## Explicitly OUT
- Broker-stop un-stub (SDK proves STOP_LOSS supported; order-path change = ITS OWN NIGHT, immediately after).
- Any day-gain/chart-gate change. KIDZ canary instead: 3 exempt-lane fills < −40% dg before Fri 7/31 trips it; Friday re-runs Q3b regardless. Provisional −40% bound pre-shaped if tripped (Marcos: "i don't like it but we'll keep the canary").
- Slippage action ($1,206 est. vs −$205 era P&L) until Q2c-H1 validates the estimator (est vs realized fill on the ~10 joinable trades).

## Day state (verified 11:36 pull)
7/27: PRE −$624.50 (5 blind-stops, quarantined) + RTH −$181.25 (8 trades; winners only BIYA ignition ×2, +$72.60). Blow-through excess ≈$125 of the RTH loss. `/api/trades` serves CORRECTED P&L (verified 36/36) — do not re-apply the ledger.

## Standing laws touched today
Review BOTH sides (outcome AND consistency) — `feedback_review_both_sides.md`, born from F2/F7/ladder misgrades ($732). NEW lesson appended in ledger: a live-day verdict about closed trades MUST check open positions first (the VEEE reversal).
