# KILL-TEST: scalar vetoes on TAPE lanes — the price of momentum_reject/vel5_reject (8/17, pre-build)

**Run BEFORE any code (cheap check first). Verdict: BUILD — counterfactual net POSITIVE (+$25.14, N=1).**
Script: `scalar_veto_tape_lanes_20260817.py` (archive cache dir as argv[1]); rows out:
`scalar_veto_tape_lanes_20260817_out.json`.

## Doctrine under test
7/26 SETTLED: "do-not-trade blocks CHART lanes only; tape lanes trade through by design"; every
setup-quality scalar (room, day-gain-selector, momentum, extension) REFUTED; chart gate = the only
measured-discriminating selection layer. Tradeability floors (min-stop, liquidity, ambient dollar)
are NOT setup-quality and STAY.

## Tape-lane set — DERIVED, not guessed
- `TAPE_PREBREAK_LANES` (:7236) = hidden_entry, vwap_reclaim, zone_flip — the code's own
  "10s live-structure" set.
- Chart-gate bypass (:3349) = hidden_entry, vwap_reclaim, zone_flip + ignition (IGNITION_CHART_BYPASS).
- PRE_LANES (:13160) = hidden_entry, vwap_reclaim (+ v2conv when V2_PRE=1, :13170) — same family.
- 10s-fed shadow/conversion lanes born of the same scan-loop 10s feed: kevseq (:7938),
  v2conv (:7832), grinder (:7849), bandpass (:7897), prevwap (:8025).
- CHART lanes per `CHART_CEILING_LANES` (:7245) = flat_top, ma_pullback, orb, ema_bounce, dip_rip.
  dip_rip is therefore CHART (ceiling-gated) despite its BACKSIDE_EXEMPT status. rocket_catcher is
  the one lane the momentum gate was explicitly retained to guard (comment :12594) — stays gated.

## Gate reach (three-rings enumeration)
- **momentum gate** — single call site, worker `:12595-12645`. Exempt tuple TODAY: vwap_reclaim,
  bounce, ignition, hidden_entry, orb, flat_top, ma_pullback, zone_flip (those get universal gates
  only). Full `check_momentum` reaches: **kevseq, v2conv, grinder, bandpass, prevwap**, rocket_catcher,
  dip_rip, and any unlisted lane. `check_momentum` hard rejects = illiquid floor (tradeability),
  ambient dollar floor (tradeability), **"no momentum build" expansion/peak-rel scalar (the REFUTED
  setup-quality scalar)**, topping tail (Kev candle rule, not a refuted scalar).
- **vel5 gate** — single call site `:8908-8927`; applies ONLY to flat_top, ma_pullback, orb,
  ema_bounce (chart lanes). **No tape lane reaches vel5_reject** — verified in the archive: 0 of 299
  vel5_reject rows carry a tape-lane machine stamp.

## Counterfactual (era 6/29–8/17 archive, 35 non-empty days, E3 live-parity on bars10s)
Join: momentum_reject ↔ tape-lane triggered_* row, same ticker/date, ≤180s before; tradeability /
universal-gate reasons excluded (they stay law).
- **N = 1** — the entire era produced exactly one setup-quality scalar veto on a tape lane:
  **WETO 8/17 10:18:37 kevseq @ $19.495**, reason "no momentum build — 0.9× base (<1.5×) / 66% of
  peak". Why so few: grinder/bandpass/prevwap/v2 conversions were env-OFF all era; kevseq conversion
  is new — today was the first day a tape lane ever reached `check_momentum`. The veto class is new
  traffic, not old bleed — the exemption is PREVENTIVE law-enforcement, priced on its only specimen.
- **vel5_reject tape-lane N = 0** (structural — see reach above).
- E3 sim (stress-F spec: $500, +1% entry slip, bank 1/2 at +10% resting, trail 10%-off-high on
  closes, stop-first, −0.5% market exits): entry fill $19.6899 × 25 sh; banked ½ at $21.6589
  (10:29:20); trail out at 10:29:40 close $19.80 (runhi $22.43) → **+$25.14. Total +$25.14,
  $/tr +$25.14, 100% win.** Bars are partial-day (fetched 10:48 ET) but the trade CLOSED at 10:29 —
  the counterfactual is complete. NOTE the irony: E3's own 10%-off-closes trail gave back most of the
  $19.50→$23.79 run on the 10:29 flush; the veto's cost under E3 is +$25, not the +$100+ the eyeball
  suggests. That is an EXIT finding, not an entry one.
- **1-sec double-veto anatomy**: kevseq had already passed its own burst/context gates + chart_gate_allow
  + entry_zone; `check_momentum` then re-judged the same tape at 1-MIN resolution — the identical
  resolution mismatch that got ignition removed from the vel5 set on 7/26 (:8917 comment).

## Verdict
NET POSITIVE → build the exemption per spec. Honesty note for Marcos: N=1 is the thinnest possible
sample; the real justification is doctrinal (7/26 settled law + the ignition resolution-mismatch
precedent), with today's WETO as the priced specimen. Every future bypass logs
`scalar_veto_bypassed` — Friday grades the exemption on real rows.

Officers: Momentum Operator (scalar refutation stands), Systems Quant (gate-reach enumeration),
Statistician (dollar trace above), First Hour (10:18 window), Blast Radius Auditor (single call
site each). Clean: Webull Broker Desk, Cartographer.
