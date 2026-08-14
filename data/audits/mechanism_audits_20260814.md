# MECHANISM RE-ANALYSIS — 8/14/2026 (Marcos: "let's begin")
Two separate-context Systems Quant audits, read-only. Nothing ships from this file.

## AUDIT 1: MA_PULLBACK (the only verified-green lane)
Mechanism as coded: detect_ma_pullback (:4569-4625) on completed 3-min bars (today-only RTH via
_fresh_session :6935): >=25 closes + EMA9>EMA20 stack; confirmation candle = last completed bar
with lower wick >=40% of range OR green close; live price > confirmation close; volume >=1.2x
prior-3-bar avg; "held MA" = every rising EMA in [9,20,50,90] whose level the candle LOW reached
(low <= ma*1.005) and candle CLOSED back above; stop = min(deepest held MA, wick low)*0.99.
Conversion :7750-7778 requires price>vwap. PULLBACK_FIRST=1 outranks flat_top/ORB.

F1 DEFECT (warmup wall): the 7/27 "open-blindness fix" (:1219-1223) fetches 7 days of 1-min bars
to warm EMAs, but the scan path wraps it in _fresh_session (:6935) stripping to TODAY only. Lane
cannot fire before ~10:36-10:47 ET (25x3min closes); _calc_ema returns 0 below period (:4371) so
EMA50 nonexistent before ~12:05, EMA90 before ~14:00 — advertised "9/20/50/90" is 9/20-only most
of the day. The entire open — Kev's richest window — is structurally invisible to this lane.
F2 CLEAN: no session leaks (aggregate_bars date+grid bucketing; [:-1] drops forming bar).
F3 DEFECT (telemetry): ma_held stamped into extra (:7774) but absent from all 24 era records —
cannot slice the green record by which MA held.
F4 DESIGN-SMELL: no upper stop bound (MAX_STOP_DIST_PCT=0.0) — DFNS 7/27 fired with 18.2% stop.
F5 DATA: DFNS day_gain_at_entry=5152.57% (bad prior_day_close) contaminates day-gain cells.

Kev-blueprint distance: CONFIRMATION entry (bar completes + price above its close + next scan
pass) = up to 3-4 min and ~1 candle above the pullback low; no resting order at the MA. Stop sits
at the low, so realized R:R is structurally worse than Kev's by ~the confirmation candle range.

Frequency throttles (why 1/day vs Kev's 5-8): (1) warmup wall (biggest, least Kev-faithful);
(2) 3-min completed-bar granularity + 60s rescan = one look per candle; (3) confirmation stack
must align on ONE bar; (4) price>VWAP; (5) VEL5>=0 hard; (6) day-gain >=15% hard (kev-sheet
exempt); (7) back-side band; (8) break-side <=1% above marked break + MAPLESS fail-closed;
(9) min-stop >=4% (not exempt); (10) runway >=0.5/1.0R; (11) roster/slot/reentry scope.

Sample verification: DFNS 7/27 and AMIX 8/4 reproduce the coded arithmetic EXACTLY (stop = wick
low * 0.99 to the tick; stack and vwap conditions hold; ema90 null both = F1 live).

Attribution verdict: mechanism coherent + honestly implemented; green record REAL but
concentrated (AMIX +$291 + CYCU +$127 = majority of era total; ex-top-2 ~flat). "Above-VWAP"
cell is tautological (precondition); "10:30-12:00 best window" partly warmup-wall artifact.

Proposals (Friday room): (1) kill the warmup wall (seed 3-min series/EMAs from the multi-day
fetch) — largest fire-count unlock available; (2) restore ma_held to records + fix F5 stamp —
telemetry only; (3) anticipation-arm SHADOW rows (would-have-filled at MA touch vs actual
confirm fill) — prices the confirmation premium in dollars, feeds v2.

## AUDIT 2: IGNITION
Trigger CLEAN: ignition_10s_step (:5721-5778): just-closed 10s bar with share vol >= 2.0x avg of
prior 24 completed 10s bars (4-min base), >= ~833 shares, green close, close in top half of
range, close >= max close of base, close within [-5%,+15%] of session open. 4.5x convert (:7435)
same units/window. Premarket excluded from baseline (:5741). Below-convert fires don't burn the
slot (:7430-7439).

Defects/smells at the edges:
- D1 (borderline defect): degenerate base — base_vol "or 1" (:5758): zero-volume base -> volx =
  raw shares -> fabricated "hundreds-x" acceleration; ambient dollar floor backstops entry but
  census volx incomparable across liquidity regimes.
- D2 DEFECT (bounded): session-open anchor = first RTH bar the machine SEES (:5743); in-memory
  state + 40-min rehydrate -> any post-10:10 restart/late-join measures "% from open" from a
  false anchor for the rest of the window. Fictional-fill bug class: window silently anchored to
  the wrong session point.
- D3 DESIGN-SMELL (the census's bleeding cell): MIN_EXT=-5% admits below-open back-side entries
  (BOXL: ext -3.4%, 10:28:51, volx 9.1, lost). No VWAP/side term anywhere in the lane.
- D4 DEFECT (for grading): ignition_below_convert shadow rows lack day_gain/side/crown fields ->
  the paying-cell definition is not computable on the shadow cohort, and shadow rows are
  pre-gauntlet (not gate-matched) -> any "2.0x would have paid" verdict is structurally biased.
- D5 DESIGN-SMELL: retest loop reads the still-forming 10s bucket -> fire-bar noise satisfies the
  -1% "retest" instantly (AKAN: retest_wait and retest_fill same second, waited_s 0.0). The
  retest is a 1% discount, not pullback confirmation.

Gauntlet (actual, from code): PASSES day-gain 15% floor, backside gate, 90-EMA extension 25%,
min-stop 4%, runway, breakside+mapless fail-closed, retest wait, ambient dollar floor, universal
topping-tail. BYPASSES: chart gate entirely ("live_structure" even under ENFORCE :3218-3233),
ceiling/stand-down, tape pre-break, vel5, above-VWAP, daily-first veto.

Live specimens: LBGJ (converted 09:40:44 volx 5.1, paying cell, won), AKAN (converted 10:11:22
volx 6.5, dg 60.68 bleeding cell, instant retest fill, -$30.06), BOXL (converted 10:28:51 volx
9.1 ext -3.4%, after-10:30 cell, -$22.32) — all three walked exactly the coded path.

Verdict: detector honest; losses are the DESIGN admitting exactly the cohort the honest census
says bleeds (high day-gain, late, below-open back-side) — every remaining gate blind to it by
construction.

Proposals (Friday room): (1) census-cell gate — convert only dg<40 AND <10:30 ET (era kept
+$123..+$164 vs cut -$310..-$298) + close the MIN_EXT back-side door or add a side term;
(2) stamp day_gain/side/crown on below_convert rows + gate-match before any 2.0x verdict;
(3) fix silent anchors: persist true 9:30 open across restarts; require non-degenerate base
(min base dollar-vol); completed-bucket retest touch.

## AUDIT 3: DEAD LANES (vwap_reclaim / flat_top / orb / zone_flip)
- FLAT_TOP + ORB: CODE-DEFECT — retrial deserved. "Pullback" test counted price 1% ABOVE the
  level as a dip (:7602, PULLBACK_TOL=1%) and _confirm_reclaim (:5903-5925) is satisfied by the
  break bar itself -> the era bought the break print in a retest costume (~48-72s later). The
  -$394..-$430 book grades break-chasing, not the design. Post-8/6 RETEST_ENTRY books entry at
  ASSUMED _rt_lvl price (:10955) — fictional-fill class on the ENTRY side, still live.
- VWAP_RECLAIM: MIXED. Coded machine honest (3-gate seek/extend/retest) but fires ~30-40s after
  the cross — inside the just-crossed band the 7/31 study refuted; the study's 2-5min HELD
  band-pass was never encoded. Replay passes build state vs anachronistic current-vwap (:7036,
  :7042). Coded variant fairly condemned; band-pass design never stood trial (harvester-testable).
- ZONE_FLIP: DESIGN-DEAD. Faithful port of its kill-tested spec; didn't replicate (n=6). Stays
  shadowed under pre-registered re-arm. Minor: PM vols leak into rolling baseline (:5625 vs :5630).

## AUDIT 4: GATE STACK — THE SMOKING GUN
_curl_feed returns a TUPLE (d10, src) (:1149); TWO call sites never unpack it:
- :8373 _auto_map: len((tuple))=2 < 30 -> returns None EVERY CALL SINCE SHIPPED. The 8/7
  FRESHNESS CONTRACT has NEVER refreshed a map in production. Today: 26 freshness_breach rows,
  8 tickers, auto_map_used=false on all. ONFO actually refused 11x (not 7) vs a 70-min-old break
  while 6-49% past it.
- :8461 RUNWAY_WALL: tuple .values() -> AttributeError swallowed -> _whi=0.0 -> spent-rung
  demotion + wall insertion INERT since 8/8. DFSC's 0.14R refusal (rung 2c overhead) = signature.
Same class as the 8/8 _side_state missing-unpack (comment :8316 records the precedent).
Per-gate: backside CLEAN (coverage caveat: off-curl names ungated); breakside predicate CLEAN
(defect upstream); min-stop DESIGN-SMELL (hidden exemption priced at the 6% era, admits 3.1%
stops at today's 4% floor — MF specimen); runway DEFECT (dead wall); day-gain DEFECT (raw
adjustment -> split names corrupt prior_day_close; floor vacuous/inverted AND feeds crown
qualification :7842 — DFNS 5152% class); extension near-vacuous by exemption accretion;
ambient CLEAN; chart gate CLEAN + ENFORCE proven ON from live rows (52 enforced:true today).
Top proposals: (1) fix both unpacks + rig case + ONFO/DFSC replay + freshness_breach-without-
remediation alarm; (2) day-gain basis integrity (adjustment=split or cross-check, touches
crowning -> Marcos); (3) re-grade min-stop exempt cohort at 4% floor (query only).
