# PENDING CONVENING — 8/17 reads/maps + boundary batch (BUILT, NOT DEPLOYED)

Blast Radius Auditor convening REQUIRED before any deploy (convene-or-don't-ship law;
this build session deliberately did NOT convene — separate context mandated). Tree to audit:
HEAD after the final batch commit. Full rig exit 0 after every item and at close.

## Items the convening must cover

1. **item1 (c4550d8)** — kev_shadow read-side: veto propagation (KEV_VETO_READ), kev_road_max
   stamp, KEV_ROAD runway extension in `_marked_runway`. BEHAVIOR CHANGE (road extension can
   flip runway_reject -> pass; Marcos-approved direction from the WETO refusal, priced in the
   commit). Verify: overlay wired on BOTH _freshest_rec return paths; _effective_map auto-map
   overlay preserves kev_road_max/veto; no gate consumes kev_shadow structure anywhere.
2. **item2 (a4fc25c)** — reread_on_reject marker (REREAD_ON_REJECT, 10-min cap) + reader
   marker-set addition. Read-side spend only (vision reads); check reader cap interaction
   (_capped still governs; marker storms bounded by the bot-side 10-min dict which RESETS on
   restart — restart semantics: worst case one extra marker per ticker per restart).
3. **item3 (b1711f9)** — read_starvation observe-only row in reader (READ_STARVATION).
   Observe-only; check the SYSTEM ticker row doesn't confuse dashboard consumers.
4. **item4 (e2ef254)** — ignition G1 shadow stamps (IGNITION_G1_SHADOW): vwap_side,
   hi_dist_pct, g1_shadow on triggered_ignition rows + breakout extra. NO enforcement
   (rig-asserted). Check: extra-dict key collision downstream (record/eyes writers), and that
   vwap at the fire site is the session vwap the guidance means (twin: monitor's session-VWAP
   fetch uses ["PRE","RTH"]; the scan-loop `vwap` variable's provenance should be named).
5. **item5 (fb90194)** — BOUNDARY_CENSUS_20260817.md + rig AK. Rig/docs only; confirm the
   bare-call pin (==3) and frozen-clock matrix match the shipped tree.

## Twins / neighborhoods to sweep

- `_freshest_rec` twins: `_effective_map` cache (20s TTL) now caches overlay output — veto and
  kev_road_max ride the cache; confirm no consumer caches a PRE-overlay rec elsewhere.
- `_marked_runway` consumers: gate site :12200s, live card :9860s, record sites :12800s —
  all now able to return kev_road_max-based (rr, tgt); confirm record-side stamps stay coherent
  (runway_pass rows can now carry a Kev-ceiling target).
- Reader: new statuses in the marker loop — dedup key includes recorded_at (storm-safe), but
  the bot's 10-min cap is the real limiter; verify _rr_state["seen_markers"] growth is bounded.
- Ignition consume block: stamps computed only on the convert path (post-daily-veto else); the
  ignition_daily_bad / below_convert rows do NOT carry stamps — acceptable? (guidance asked for
  "every conversion/fire decision point"; today only the FIRE row is stamped).

## Restart semantics

- `_reread_reject_t`, `_auto_read_asked`, `_starv` window, `_effmap_cache` all in-memory:
  restart = caps reset (bounded extra rows/reads, no money path).
- No env defaults changed except NEW envs (KEV_VETO_READ=1, KEV_ROAD=1, REREAD_ON_REJECT=1,
  READ_STARVATION=1, IGNITION_G1_SHADOW=1). Kill switches exist for all five.

## Doctrine-inversion sweep

- **8/12 OUR-NUMBERS PRIMACY: REAFFIRMED, not inverted.** Marcos 8/17 mid-build, verbatim:
  "remember I want Kev's picks but I want OUR map numbers ruling." The original item-1 spec
  (freshest-timestamp-wins promotion of kev_shadow structure) was CORRECTED mid-build and was
  NOT built: kev_shadow break/confirm/targets are never promoted, even when newer. Shipped
  shape = veto + kev_road_max + rung-exhausted road extension only. The convening should
  confirm no residual promotion path and record the reaffirmation in the ledger.
- 8/6 freshest-data law now scoped: freshest WITHIN our own sources (primary vs vision_shadow);
  Kev's word stays freshest for VETO only. Flag for Marcos if any officer reads tension.
- Item 1's KEV_ROAD is the only money-behavior change in the batch — it goes to Marcos priced
  (auditor-cannot-authorize law); the commit carries the WETO hand-trace.

## BATCH 2 (appended same day — build-only, NO deploy; book flat rule holds for the ship)

6. **item A (173d8f1)** — TAPE-LANE SCALAR-VETO EXEMPTION. ENFORCES SETTLED 7/26 doctrine
   ("do-not-trade blocks CHART lanes only; tape lanes trade through by design"; momentum scalar
   REFUTED). Kill-test FIRST: era archive join found exactly ONE tape-lane setup-quality veto
   (WETO 8/17 kevseq — today's specimen), E3 counterfactual +$25.14 -> BUILD by pre-registered
   rule (N=1 thinness flagged honestly; doctrine carries the weight). Change: worker momentum
   else-branch bypasses ONLY 'no momentum build' for kevseq/v2conv/grinder/bandpass/prevwap;
   illiquid + ambient TRADEABILITY floors and topping-tail keep their veto; every bypass logs
   scalar_veto_bypassed. Kill: TAPE_LANE_SCALAR_EXEMPT=0. Rig AL. MONEY-BEHAVIOR CHANGE
   (a previously vetoed tape-lane entry now proceeds) — doctrine-mandated, goes to Marcos priced.
7. **item B (cdbe7d4)** — CROWN forensic + CROWN_FIX_0817. Repairs the 8/5 meritocracy PROMISE'S
   VISIBILITY, not its behavior: forensic PROVED WETO was crowned 09:47:07 (one cycle after the
   first post-halt print over +40%); leader_armed was always the crown row. Fix = explicit
   observe-only 'crowned' row at qualify. Kill: CROWN_FIX_0817=0. Rig AM. Convening: confirm
   the 'crowned' status collides with nothing (dashboard by_status, rehydrate query untouched).

### Batch-2 sweep notes
- Item A touches the single momentum call site; vel5 set is chart-only (rig-pinned); exempt
  tuple unchanged; check_momentum internals untouched.
- Item B: 'crowned' written once, never read (rig-pinned); rehydrate still keys on leader_armed.

## Spec tensions logged for Marcos (NOT resolved here)

- Item 2: ceiling_reject was ALREADY a reader marker + fires `_request_auto_read` (30-min
  throttle). A stale ceiling_reject now posts BOTH lanes — double read-request pathways with
  different throttles (10 vs 30 min). Built as specced; dedup decision is Marcos's.
- Item 4: "at every ignition conversion/fire decision point" — stamps ride the fire/convert
  path only (the row that proceeds); refused fires (daily_bad, below_convert) are unstamped.
- Item 3: roster = today's levels sheet (kev_watchlist levels), not the bot's watch roster —
  the reader has no view of the bot's roster; chosen as the nearest in-process truth.
- Batch2 item A: counterfactual N=1 (the WETO specimen itself) — the exemption ships on doctrine
  + one priced specimen; Friday grades scalar_veto_bypassed rows on real traffic.
- Batch2 item B: two prior-close sources disagree (kevseq day_gain 137.17 vs eyes dg 124.45) —
  pin one source (split-adjustment class); and 40%-crossed-INSIDE-a-halt structurally delays the
  crown to resumption+1 cycle — halt-time crowning = behavior change, Marcos's call.
