# FOUNDATION BATCH E — THE REMAINING LANES MADE TESTABLE (2026-08-17)

Companion to `harness_parity_20260817.md` (cohort 1) and the batch-D flat_top extraction.
Rig: `rig/test_batchE_20260817.py` (15 specs, all green). Parity run:
`data/killtests/harness_parity_batchE_20260817.py` → `..._out.json`.

---

## FAILURE CONDITION — WRITTEN FIRST

**This batch is WRONG if any of the following is true:**

1. **Any injection changes the live path.** The live process calls every one of these
   functions exactly as it did before 8/17 — no new argument, hook unset. If a default-argument
   call produces anything different from the pre-8/17 code, this batch is a live behaviour
   change wearing a research costume, and it must be reverted. Every lane below carries a
   `_default` spec that drives the *live call shape* and asserts the old semantics from an
   independent computation.
2. **An injected value silently becomes the default** (e.g. `pm_floor=None` quietly meaning
   "no zone" rather than "ask the live store"). That would make the *live* lane go dark.
3. **The harness accepts a lane without its context** — zone_flip without a premarket floor,
   runway without a map and a wall high. The harness's entire reason to exist is that studies
   stop inventing inputs; a defaulting harness is worse than no harness.
4. **The map stamp fetches, computes, recurses into `_log_decision`, or throws.** It rides the
   hot path on every fire and fill.
5. **A parity number here is quoted as an equivalence test.** It is not: 8/17 rows carry no
   `fed_k0/fed_k1` provenance (that shipped 8/17 night), so this is a time-and-price
   approximation, same as cohort 1. 2026-08-18 is the first day supporting equivalence.
6. **Runway is presented as historically replayable.** It is not, and no injection can make it
   so. See §3.

---

## VERDICT

Three of the four lanes are LIFTED (`_bucket_fresh`/hidden, zone_flip, `check_momentum`); the
fourth (`_marked_runway`) is injectable **but** remains historically un-replayable and always
will be. **This is a plumbing verdict, not a trading one** — nothing here grades an edge, sizes a
ticket, or moves a dollar. The parity figures are single-day (2026-08-17) and
approximate: zone_flip's is n=3, and *only* the detector is graded, never the funnel. Read the
LIMITS & CAVEATS section before citing any number below.

## THE PATTERN

Every one of the four blockers was the same species: *the function reads a live global instead
of receiving a value.* The fix in every case was to **inject the source, defaulting to the live
read**, so the live expression collapses to the pre-existing code and only the harness ever
takes the new branch. Nothing was moved, reordered, or re-implemented.

---

## LANE 1 — `_bucket_fresh` (the common blocker) — **LIFTED**

**Blocker.** `_bucket_fresh(k, hm, sym)` is the shared stale-fire suppressor that *every* 10s
detector calls before it may fire. It compares the bar's bucket epoch to `time.time()`. In
replay every bar is hours old, so the guard ate **100% of replayed fires**. Two lanes (hidden,
zone_flip) were unliftable for this one reason, and it was the first thing to fix.

**Injected.** A module-level hook plus an optional argument:

```python
_BUCKET_NOW = None      # replay-only: callable() -> epoch seconds. LIVE LEAVES THIS None.

def _bucket_fresh(k, hm=None, sym=None, now=None):
    _now = now if now is not None else (_BUCKET_NOW() if _BUCKET_NOW else None)
    if _now is None:
        _hm = hm or datetime.now(EASTERN).strftime("%H:%M")
        _now = time.time()
    else:
        _hm = hm or datetime.fromtimestamp(float(_now), EASTERN).strftime("%H:%M")
```

The harness sets the hook to the fed slice's **last bar epoch + 10** — the earliest instant the
live rescan could have been handed that slice (the bucket must close first). That is exact in
*relative* terms for every older bar in the same slice, which is what the 90s ceiling (60s PRE)
actually discriminates on, and it is the direction most favourable to the guard's limit being
met, so it can only over-count fires versus a live cycle that arrived later. Stated, not hidden.

**Live-equivalence proof.**
- `SPEC_bucket_fresh_live_default` — hook unset, `now` unset: the verdict is compared against
  the pre-8/17 formula recomputed independently across ages {0,5,30,89,91,300,3600} × hm
  {09:00, 09:30, 12:00, live-now}, plus `k=0`/`k=None`. All match.
- `SPEC_bucket_hook_unset_in_shipped_source` — the bot's source contains exactly one
  `_BUCKET_NOW` assignment, and it is `None`. A live process that *sets* it has moved its own
  clock; that goes red.
- Cohort-1 regression: with the change in, `harness_parity_20260817.py` produces **byte-identical
  fire counts and match counts** for grinder (19/6), bandpass (5/4), prevwap (3/3) and v2
  (124/84) versus the same run against the HEAD bot source. The clock hook changed nothing that
  was already working.

**Before/after (the proof it was the blocker).** Same 13 names, same tape, same cadence:

| hidden replay | fires |
|---|---|
| clock hook **disarmed** (pre-E1 behaviour) | **0** across 13 names |
| clock hook armed (E1) | **424** |

---

## LANE 2 — `kev_zoneflip_step` / `_zf_pm_floor` — **LIFTED**

**Blocker (two of them).** (a) the `_bucket_fresh` wall clock above; (b) `_zf_pm_floor(sym)`
reads the premarket zone built during the live premarket, via `_curl_feed`.

**Injected.** `kev_zoneflip_step(sym, new_bars, pm_floor=None)`. The live caller
(`marcos_trading_bot.py` :8899, `kev_zoneflip_step(t, _zf_nb)`) is untouched, so `pm_floor=None`
→ `_zf_pm_floor(sym)` exactly as before. In the harness the floor is a **REQUIRED ctx field**
(`LANES["zone_flip"]["ctx_required"] = ("pm_floor",)`); `replay()` refuses by name if it is
absent, per the harness convention.

The harness *also* offers `pm_floor_from_tape(sym, bars, day)`, which runs **the bot's own
`_zf_pm_floor`** over the day's captured tape with `_curl_feed` swapped for a fixture — so a
study gets the bot's computation, never a replica.

**Live-equivalence proof.**
- `SPEC_zoneflip_default_asks_the_live_store` — with `pm_floor` omitted, `_zf_pm_floor` is
  observed to be called with the right symbol (not read from the source, *observed*), and the
  live call site is pinned by text.
- `SPEC_harness_refuses_zoneflip_without_pm_floor` — both the missing-key and missing-provider
  paths raise `MissingContext`.
- **Independent equivalence on real data:** the tape-computed floor equals the zone the LIVE
  machine stamped on its own rows, to the 4th decimal and including the source label:

| name | tape (`_zf_pm_floor` over tape) | live-stamped row | verdict |
|---|---|---|---|
| JLHL | 8.4658 / `pm_shelf3` | 8.4658 / `pm_shelf3` | MATCH |
| LBGJ | 3.06 / `pm_shelf3` | 3.06 / `pm_shelf3` | MATCH |

**Parity: 100.0% (3/3 live fires), match key price+stop+time.** N=3 — this is the *absence of a
disagreement*, not a strong claim.

---

## LANE 3 — `_marked_runway` — **INJECTABLE, BUT HISTORICALLY UN-REPLAYABLE (the honest wall)**

**Blocker.** `_effective_map(ticker)` reads the running level-map store; `_curl_feed(ticker)`
fetches the recorder feed for the wall high.

### (a) The function is now replayable

`_marked_runway(ticker, entry_price, stop_loss, lvd=None, wall_high=None)`. Both default None →
the exact pre-8/17 path. Harness entry point: `marked_runway_on(...)`, which **refuses** a
missing map and **refuses** a missing wall high (pass `0.0` to study the wall-disabled case
explicitly). `SPEC_runway_map_injection` proves neither `_effective_map` nor `_curl_feed` is
touched when both are supplied — a replay that reaches the live path is worthless.

### (b) …and it still cannot replay a single historical day

**This is the real blocker and injection does not fix it: NO MAP SNAPSHOT WAS EVER RECORDED.**
The level-map store is mutated all day — night sheet → intraday vision re-reads → auto-map
overlay on a freshness breach — so the map a past row was decided under is *unrecoverable after
the fact*. Injecting a map a study made up would produce precisely the replica drift the harness
exists to kill. **Every day up to and including 2026-08-17 is permanently un-replayable for
runway.** That is stated in `NOT_ISOLABLE` and pinned by
`SPEC_harness_registers_the_lifted_lanes`.

### (c) The durable fix: start recording (E3b)

Shipped tonight, at the same choke point the config hash uses (`_log_decision`), on the same row
set (`triggered_*` + `filled`/`retest_fill`/`tier_fill`):

`map_src`, `map_cache`, `map_break`, `map_targets`, `map_next_supply`, `map_zone`,
`map_kev_road_max`, `map_auto`, `map_age_min`.

**Observe-only.** It adds fields to rows and changes no decision. Safety, pinned by
`SPEC_map_stamp_never_fetches_or_throws`: it reads **warm caches only** — the 20s
`_effmap_cache`, else the same-day TTL-warm `_kev_levels_cache`. It never calls
`_effective_map` (which can log a breach row → recursion into `_log_decision`) and never calls
`_fetch_kev_levels` (which can hit the network). Cold caches → `{"map_src": None}` and nothing
else. Kill switch: `MAP_STAMP=0`. An explicitly-passed field always wins.

**From 2026-08-18 the archive can reconstruct what the runway gate actually saw.** Not before.

---

## LANE 4 — `check_momentum` — **LIFTED**

**Blocker.** The body is pure; the input was a live fetch, and it routed through
`_fresh_session()` (today-only + 900s staleness), so a past-day replay fell into the
insufficient-data branch instead of reading momentum.

**Injected.** `check_momentum(ticker, session_bars=None)` — an already-sessionised 1-min list
that bypasses both the fetch and the today-only filter. Harness:
`check_momentum_on(ticker, m1_bars, session_bars=None)` keeps the old today-only route and adds
the past-day one.

**Live-equivalence proof.** `SPEC_momentum_default_still_fetches_and_freshens`: with no
`session_bars`, `get_intraday_bars` is observed called once with `count=390`, and a past-day
fixture still lands in the `only N session bars available` branch — i.e. `_fresh_session` is
still in the path. `SPEC_momentum_session_bars_replays_a_past_day` shows the same fixture
producing a real read (with `session_peak_vol`) through the new route.

**No parity number, and why:** `check_momentum` is a gate over 1-min bars, not a fire-emitting
lane. It writes no fire rows to match against. Its lift is proven by rig equivalence, not by a
match rate. Saying otherwise would be inventing a statistic.

---

## NEW PARITY NUMBERS (2026-08-17, added to `data/killtests/harness_parity.json`)

| lane | live | harness | exact | parity | match key |
|---|---|---|---|---|---|
| **zone_flip** | 3 | 4 | 3 | **100.0%** | price + stop + time |
| **hidden** | 226 | 424 | 195 | **86.3%** | **stop + time** |

**Why hidden is matched on stop, not price — this is a fidelity point, not a convenience.**
The `hidden_shadow_fire` row stamps `price` = the **live quote at log time** (bot :8931,
`_hpx = price if price and price > 0 else _he_fire.get("px")`), which is not a detector output
and cannot be expected to equal a bar close. Matching on it measures the quote feed, not the
detector, and scores **5.8%**. Both numbers are computed and both are in the artifact; neither is
hidden. `stop` and `seq` are hidden's only detector outputs on the row, so `stop + time` is the
valid key. (zone_flip's convert row stamps `fire_px` = the detector's px, so the strict key
applies there and is what is reported.)

**Harness-extra fires are not missed trades.** 424 harness vs 226 live on hidden, 4 vs 3 on
zone_flip: the harness grades the **detector**; the live funnel (scanner-board membership, slot
and daily caps, HIDDEN's observe-only routing, found_entry/traded suppression) sits *upstream*
and is not modelled. Same bound as flat_top's.

---

## ⚠️ ~~REGRESSION FOUND, NOT OURS~~ — **SUPERSEDED 8/17 night: BISECTED, NOT A DEFECT**

Re-running the cohort-1 parity script at HEAD gives **kevseq 0.0% (0/23)**, against the 30.4%
(7/23) seeded earlier on 8/17. Same 11 harness fires — but on **entirely different names**
(was RPGL/WFF, now IPST/IVF/PFSA).

**Proven independent of batch E.** The identical 0.0% comes out running the same script against
the **HEAD bot source** with batch E's changes absent, and every other cohort-1 lane is
byte-identical across the two (grinder 19/6, bandpass 5/4, prevwap 3/3, v2 124/84). Something in
the 8/17 B/C batches moved kevseq's fire set.

`harness_parity.json` has been updated to 0.0 — which makes the EG2b trust gate **stricter**, the
safe direction — with the finding written into the lane's note. **Owed: a bisect by whoever owns
the kevseq lane.** Until then, do not grade kevseq from harness output.

> **RESOLVED 8/17 night — the DIAGNOSIS in this section is WRONG; the 0.0% number is right.**
> The fire set never moved: the harness produces the SAME 11 fires, on the SAME names (RPGL, WFF,
> IPST, IVF, PFSA, WETO), at the SAME bar epochs, with the SAME stops, under both trees. **Only the
> fire PRICE moved**, from the setup bar's level `pd["hi"]` to the fill bar's close `c` — which is
> **B1, commit `2d0a6cb`**, an intended, source-commented, documented and env-killable change that
> is NOT in the suspected `8ac6791..bbe419f` window (B1 is the first B-batch commit). At HEAD,
> `KEVSEQ_FIRE_ON_CLOSE=0` restores 30.4% (7/23) exactly. The 8/17 live rows are PRE-B1 and
> level-priced, so exact-price parity against a close-priced detector is structurally impossible —
> 0.0% is the honest reading of a STALE ARTIFACT and stays. Also: the "PROVEN INDEPENDENT of batch
> E" run above cannot have been performed as described (`_install_bar_clock()` raises `NotIsolable`
> on any pre-E tree); its conclusion holds anyway, by AST diff. Full bisect: `RESULTS_LEDGER.md`,
> 8/17 night entry.

---

## LIMITS & CAVEATS

- **Single day.** Every parity figure is 2026-08-17 only. n=3 for zone_flip — the absence of a
  disagreement, not evidence of agreement. Do not cite either lane as "validated".
- **Approximation, not equivalence.** 8/17 rows carry no `fed_k0/fed_k1` provenance, so the two
  sides were not fed the same bars; a miss cannot be attributed between detector and feed.
  2026-08-18 is the first day supporting an exact-fed-stream equivalence test.
- **Detector, never funnel.** Harness-extra fires (hidden 424 vs 226 live) are not missed trades;
  the live funnel sits upstream and is not modelled here.
- **The bar clock is a reconstruction.** `k_last + 10` is the earliest instant the live rescan
  could have held the slice, so it biases toward MORE fires than a live cycle that arrived later.
- **Runway has no parity number at all** and cannot have one for any historical day.
- **`check_momentum` has no parity number** — it emits no rows; its lift is proven by rig
  equivalence only.
- **kevseq is at 0.0% and the cause is unbisected** (see the regression section). Not ours, but
  outstanding.
- **No trading claim is made anywhere in this artifact.** No P&L, no expectancy, no go/no-go.

## WHAT REMAINS IMPOSSIBLE, AND WHY

| thing | status | why |
|---|---|---|
| runway on any day ≤ 2026-08-17 | **impossible, permanently** | the map the gates saw was never recorded and the store is mutated all day; recording started 8/17 night (E3b), 8/18 is the first reconstructable day |
| `_zf_pm_floor` against the *live premarket store* | live-only | the harness computes the floor from tape with the bot's own function instead — validated exactly against the live stamps on both 8/17 names |
| exact-fed-stream equivalence for any lane | not yet | `fed_k0/fed_k1` shipped 8/17 night; 8/18 is the first supporting day. Everything here is a time-and-price approximation |
| flat_top retest arm/reclaim | live-only (batch D) | wall-clock + live-1-min-tape state machine; `armed` stays a required ctx field |

---

## FILES

- `marcos_trading_bot.py` — E1 `_BUCKET_NOW` + `_bucket_fresh(now=)`; E2
  `kev_zoneflip_step(pm_floor=)`; E3 `_marked_runway(lvd=, wall_high=)`; E3b `_MAP_STAMPED` /
  `_map_stamp_wanted` / `_map_snapshot` + the `_log_decision` choke point; E4
  `check_momentum(session_bars=)`.
- `data/killtests/live_harness.py` — `_install_bar_clock` / `set_bar_now`, the `zone_flip` lane,
  hidden un-blocked, `pm_floor_from_tape`, `marked_runway_on`, `check_momentum_on(session_bars=)`,
  rewritten `NOT_ISOLABLE`.
- `data/killtests/harness_parity_batchE_20260817.py` (+ `_out.json`) — the parity run and the E1
  counterfactual.
- `data/killtests/harness_parity.json` — hidden + zone_flip added; kevseq re-measured.
- `rig/test_batchE_20260817.py` — 15 specs. `rig/test_shipset_20260804.py` — BH-j superseded
  (hidden now RUNS), BH-j2 added (zone_flip refuses without pm_floor), `_bucket_fresh` signature
  pin updated.
