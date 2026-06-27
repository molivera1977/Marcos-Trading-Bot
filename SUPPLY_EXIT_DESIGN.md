# Kev-Faithful Exit System — Design Spec (LOCKED 2026-06-26)

**Source:** three of Kev's detailed trade recaps + one risk-management education video (logged in
[[project_kev_lessons]] #15–18, June 2026). This RETIRES our made-up exit numbers (`+8/12/20%` /
`+4/6%` tiers, `TRAIL_PCT = 5%`) and replaces them with Kev's actual, stated rules. Per
[[feedback_kev_is_the_bible]] + [[feedback_grade_the_bot]]: Kev's stated method is gospel; the only
made-up numbers allowed are ones he gives.

## The core insight: Kev's exits are R-MULTIPLES, not percentages
Risk `R = entry − stop`, where **stop = the bottom of the demand zone / the previous candle's low**
(YAS 10¢, FCHL 7¢, CMD 3¢ — all "risk off the previous bar low / bottom of the zone"). Everything
scales off R, not a fixed %. That's why our fixed `+8%` first tier was wrong — it ignores the trade's
actual risk and sits above where low-room moves can go.

## The rules (all Kev, all stated on tape)
1. **Stop = bottom of the zone / previous candle low** → defines **R**.
2. **+1R → SELL HALF** ("up 1R, sell half → the trade is risk-free; worst case the rest stops at
   break-even"). THE keep-green-trades-green rule. (He'll do it at +2R if it spikes fast.)
3. **Trim into strength → down to a ~¼ runner** ("get down to runners / a quarter left, trimming into
   profits") at the supply/resistance zones.
4. **Trail the stop UP to each cleared level** — broken resistance becomes support becomes the new stop
   ("now I'm risking off the opening high — guaranteed profitable trade"). REPLACES `TRAIL_PCT=5%`.
5. **Add ~¼-size on each confirmed break** of the next level (pivot off it). = the scale-in / "keep going
   back" mechanic; the exit and the adds are ONE continuous trim-add-trail dance.
6. **INSTANT FULL EXIT: a new high that closes back BELOW the previous candle's high.** Kev: "instant
   exit every single time, I don't care about confidence — it's a massive reversal indication." (The
   precise, mechanical form of the topping-tail exit.)
7. **Also cut on:** no continuation after the break (SGMT breakeven), volume/buyers leaving (FCHL),
   break of the higher-low (HCWB "walk away"). Topping-tail exit is REGIME-DEPENDENT (great slow days,
   costs you a runner on a trend day — HCWB) → soften on strong trend.

## Targets = the supply LADDER (not a %)
Scale into the successive supply zones (premarket high, prior-day high, pivots, the daily resistance
ladder — 135/160/175/200-MA/psych on HCWB). Once price clears ALL overhead → open room → ride the
runner aggressively (the squeeze-to-new-highs). Reuses `find_next_supply`/`compute_room`.

## BACKTEST vs the old %-tiers (today's stocks, /tmp/kev_exit_test.py) — KEV WINS ALL 5
| Stock | move | KEV | OLD | |
|---|---|---|---|---|
| BDRX | +1.7R | **+2.5%** | **−2.4%** | +1R fills; old +8% never fills → stop-out |
| AZI  | +2.2R | **+3.1%** | −2.2% | same — old never scales, exposed |
| ILLR | +1.6R | +6.3% | +5.8% | wash |
| IVF  | +5.7R | **+21.3%** | +15.0% | trim-into-strength + runner > capped +20% |
| SDOT | +3.9R | **+27.6%** | +15.0% | same (halt-y caveat) |
Robust finding (no fine modeling): **+1R fills on all moves; +8% misses the small-room movers** → Kev
turns the BDRX/AZI give-backs into risk-free wins and captures more of the big runners.

## Build plan (NOT yet implemented — code change to monitor_trade)
- Replace `EXIT_TIERS_AM/PM` + `TRAIL_PCT` logic with: R from stop; sell 50% at +1R; trim to ¼ runner
  into `find_next_supply` levels; trail stop to each cleared level; instant-exit on new-high-fails-prior-
  bar-high; keep failed-breakout / lost-higher-low / regime-aware-topping-tail.
- The ADD-on-break (scale-in) pairs with same-name re-entry — design together.
- Exit-generating logic → independent agent audit before shipping. Verify with the Monday decision-log data.
