# BIG RIDES REVERSE-ENGINEER — 8/16 (analysis only; no behavior change)

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** IN-SAMPLE, no OOS wall, and the smallest shape cluster is n=9. The k=4 fingerprint clustering was fitted on the same name-days it is described from; a 60-name random contrast is a sanity check, not a hold-out. Treat every shape here as a HYPOTHESIS awaiting an out-of-sample week.

Script: `data/killtests/big_rides_reverse_20260816.py` (chain FP -> S -> G -> F -> C -> B -> E imported unchanged; live parity 15:30 cutoff / 15:45 flatten; E3 = bank 50% @+10% then 10%-off-high trail; E4 = never-bank 10%-off-high trail; $500, +1% entry slip, 0.5% mkt exit, halt_rule on). Raw output: `big_rides_reverse_20260816_out.md`; vectors/clusters: `big_rides_reverse_20260816.json`.
Universe: 729 RTH name-days, 62 dates (5/18-8/14). Marcos's framing: start from the WINNERS ("reverse engineering the big winners and seeing the doorways"); STEP 0 added on his correction ("we are throwing darts... break down the replay and the patterns should show themselves") — hypothesis-free fingerprints FIRST, doorway mapping second.

## HEADLINE (read this, then the tables)

**STEP 0 — the shapes that emerged (k=4 on neutral pre-ride fingerprints; contrast = 60 random non-big name-days snapped to the same centroids):**

| cluster | n big | n contrast | ratio | shape in plain words |
|---|---|---|---|---|
| C2 "front-side base, near the high, early" | 26 | 22 | 1.2:1 | start ~8% off the session high, above/at VWAP ~2/3 of the time, a prior 4x3min base top only ~3% away, ~31 min after open (many literally 09:30 = gap-and-go off the bell), volume unremarkable (1.0x), 69% had a >=4-min zero-print gap in the prior 30 min (halt or premarket illiquidity — see caveat) |
| C0 "deep backside pullback into a base, below VWAP" | 16 | 35 | 0.5:1 | start ~28% off the session high, BELOW VWAP 80-90% of the time before, prior base top ~5% away, lower-lows into the start, pre-10 volume 1.6x (capitulation prints), ~61 min after open, 31% day-2. This is the BASE-RATE shape — the contrast set lands here MORE than the winners do |
| C3 "late-day vertical extension, blue-sky, no base" | 11 | 3 | 3.7:1 | start ~3 hours after open (mean 182 min), already +280% above the session low, above VWAP, NO prior 4x3min base (distance ~26%+ = capped), gap +249%, halts in 82% of the prior 30 min. Distinctive (3.7:1) and it is where 7 of the 9 "no doorway" rides live |
| C1 "halt ladder" | 7 | 0 | 7:1 | halt flags in 100% of both the pre-30 and post-10 windows: the ride IS a sequence of LULD halts/resumptions; a base ~15% away; volume 1.9x pre; 43 min after open. Most distinctive shape (no contrast member) |

Base-rate table (TOP vs CONTRAST z-gap): the features that separate big rides from random name-days are **halt presence (+0.9z), distance-to-nearest-base (+0.6-0.7z: winners start FARTHER from a base, i.e. structure-less), being ABOVE VWAP before the start (+0.5-0.6z), higher-low sequence (+0.4z), closeness to the session high (+0.4-0.5z)**. NOT distinctive: gap% (0.0), day-2 (0.0), bar range ratio (~0), volume ratio (slightly NEGATIVE: winners' pre-10 volume 1.3x vs contrast 1.6x). Caveat: "halt" = >=4-min zero-print gap in the bar stream; on FULL-day bars this also catches premarket illiquidity, so read halt_pre30 as "gappy tape / halts", not pure LULD.

**Doorway census (secondary):** any of our RTH doors inside the first 20% of the leg = 51/60 (85%); v2 flush 82%, BA break 62%, VWAP band-pass 22%, ORB-15 22%, grinder-1030 18%; NONE = 9/60 (15%), of which 7 are C3 (late vertical, no base). But see STEP 5: v2 and BA are in 82%/62% of big rides only because they fire ~10k/~4.5k times over the universe (precision 1.8% each; v2 loses -$65.6k under E3 outside the big-ride windows). Doors that are BOTH present in big rides AND net-positive outside them: grinder-1030 (in 18% of big rides; +$8.9k E3 on its 363 non-big fires, +$24.56/tr) and ORB-15 (22%; +$9.6k, +$26.77/tr). VWAP band-pass is ~flat outside (+$1.27/tr).

**Best-capture exit on big rides:** E4 (never-bank trail) $25,490 vs E3 $15,049 vs full ride $98,667 from the same 123 doorway fills -> E4 keeps 0.26 of the ride, E3 0.15 (median capture E3 0.10, E4 0.12; 24% of E4 fills keep >=50% of the ride vs 2% for E3). Neither exit rides these legs; the 10%-off-high trail is knocked out by the intra-leg shakeouts (the leg definition tolerates 15%).

**Missing door (STEP 4):** the (g) cluster = C3, "late-day vertical extension": name already +100-900% on the day (INHD +901% at start, ZYBT +321%, CPHI +168%, PAVS +417%, BBBY.WS +104%), 3 of 9 start <=5 min after a halt resumption, all mid-range (16-45% below the session high = a pullback in a vertical), tape too fast/gappy for a 4x3min base to exist. Spec below as a HYPOTHESIS with kill-test — not graded as an entry today.

**False-positive ratio, best door:** grinder-1030: 387 fires, 24 land inside a big-ride window (6.2% precision), 355 on non-big name-days (138 name-days) — but those non-big fires are +$8.9k under E3, so the "false positives" are not losers; ORB-15: 3.5% precision, non-big fires +$9.6k. v2 flush: 1.8% precision, non-big fires -$65.6k (the v1 autopsy in one number).

---

## STEP 4b — MISSING-DOOR SPEC (hypothesis only; NOT graded as an entry today)

**H-VERT ("late vertical continuation"): on a name already >=+100% on the day and above premarket-anchored VWAP, after 10:30 ET, a pullback of 15-45% off the session high that holds a higher low for >=3 consecutive 10s bars and then reclaims the high of the pullback's last red minute, is followed by a >=+40% leg (15%-tolerance) more often than the same trigger fired on names <+100% on the day.**
Members it must catch (in-sample, so they cannot count as evidence): INHD 6/08 13:19, XHLD 8/06 14:59, WFF 8/07 13:44, ATGL 8/07 11:00, BBBY.WS 8/13 13:20, ZYBT 7/20 14:00 (post-halt), PAVS 6/09 10:46 (post-halt), CPHI 7/21 11:43 (post-halt).
Failure condition (write first): WRONG if, on the 729-universe, the trigger's non-big fires (>=+100% day names not in the top-60) lose more under E4 than the top-60 fires make; or if precision (fires in top-60 windows / total fires) < the grinder-1030 bar of 6%; or if the leg-after-trigger median < +15%.
Kill-test: (1) implement as a detector in the same chain (E.DAYS, unchanged sequencing), (2) count fires, precision, E3/E4 $ on big vs non-big, (3) OOS wall: because 8 of the 9 specimens are in-sample the verdict must wait for >=5 new dates (Seam Scientist rule), (4) hostile gauntlet: the halt-resumption specimens (ZYBT 7/20, PAVS 6/09, CPHI 7/21) must be run with the halt-gap fill rule and the resumption-open gap through the stop, (5) DOLLARS through the real sizing chain + one named trace (INHD 6/08 13:19).
Sub-hypothesis H-HALT (C1): a resumption print above the pre-halt high on a name that has already halted up >=2x today continues to the next halt more often than not — same kill-test template; owner Rocket Rider / Hidden Entry Architect.
What NOT to do: no "late-day override" of the back-side gate or the day-gain filters on the strength of 9 specimens (Strength Ombudsman hearing first; Auditor cannot authorize behavior).

## Notes / caveats (honesty)
- Ride definition is close-to-close on 10s bars with a 15% close-retrace tolerance; a leg with a 16% shakeout is split into two rides. Sensitivity to the tolerance not run.
- "First 20% of the leg" is price-based (entry <= start + 20% of the leg's gain) AND time-bounded (start..peak). Detector fires carry their own sequencing (a lane in an open trade cannot re-fire), exactly as the chain runs them.
- Premarket reclaim (f) is reported as CONTEXT only (7/60 name-days had a PRE band-pass fire 07:00-09:25); the PRE book flattens 09:25 so it cannot be an RTH doorway.
- Fingerprints run on FULL-day bars (premarket included, premarket-anchored VWAP) so 09:30 starts have a real before-window; halt flags therefore include premarket zero-print gaps.
- k-means: 8 seeds x k in {3,4,5}, best inertia per k; k=4 reported (k=3 sizes 33/16/11, k=5 25/13/11/9/2). Cluster membership at the margins is not stable to the seed; the four SHAPES are.
- Capture "full $" = $500 x (ride peak close / filled entry - 1): the ceiling if you held from the door to the peak close.
- Contrast set = 60 random non-top-60 name-days (seed 816), fingerprinted at their OWN best-ride start so the pre-30 window is the same construct.

---
# RAW OUTPUT (script transcript)

# BIG RIDES REVERSE-ENGINEER 8/16 — files 729, RTH name-days 729, dates 62 (2026-05-18..2026-08-14)

## STEP 0 — HYPOTHESIS-FREE FINGERPRINTS (30 min before ride start, first 10 min of ride) — the CLUSTERS are the finding
Features per minute (neutral): above-VWAP, % from session high, % from session low, distance to nearest prior 4x3min consolidation top (<=12% deep), bar range vs prior-20-bar avg, volume vs prior-20-bar avg, higher-low(+1)/lower-low(-1), halt flag; plus gap% vs prev close, minutes since open, day-2. Computed on FULL-day bars (premarket included; VWAP anchored premarket; session hi/lo incl. premarket) so 09:30 starts have a real before-window. Vector = pre30 mean, pre10 mean, post10 mean of each + extras. z-scored on TOP+CONTRAST.

### Base rate: TOP-60 vs 60 random non-big name-days (mean, and z-gap = (top-contrast)/pooled sd)
| feature | TOP-60 mean | CONTRAST mean | z-gap |
|---|---|---|---|
| halt_pre30 | 0.63 | 0.20 | +0.88 |
| post10_cons | 11.31 | 4.16 | +0.71 |
| post10_halt | 0.22 | 0.05 | +0.61 |
| pre10_cons | 9.19 | 3.43 | +0.60 |
| pre30_cons | 8.81 | 3.25 | +0.58 |
| pre10_above | 0.51 | 0.27 | +0.57 |
| pre30_halt | 0.25 | 0.09 | +0.53 |
| pre10_halt | 0.23 | 0.07 | +0.51 |
| pre30_above | 0.53 | 0.33 | +0.48 |
| pre30_from_hi | -13.53 | -20.81 | +0.48 |
| halt_post10 | 0.38 | 0.18 | +0.44 |
| pre30_hl | 0.09 | 0.01 | +0.44 |
| pre10_from_hi | -15.68 | -22.13 | +0.40 |
| post10_from_lo | 91.31 | 36.19 | +0.38 |
| pre30_from_lo | 85.35 | 33.40 | +0.38 |
| post10_from_hi | -15.18 | -21.08 | +0.37 |
| post10_above | 0.52 | 0.37 | +0.35 |
| pre10_from_lo | 78.18 | 33.05 | +0.35 |
| pre10_hl | -0.01 | -0.10 | +0.34 |
| pre10_vol_r | 1.30 | 1.62 | -0.32 |
| post10_vol_r | 1.07 | 1.34 | -0.29 |
| post10_hl | 0.24 | 0.30 | -0.23 |
| min_since_open | 67.94 | 50.97 | +0.20 |
| pre30_vol_r | 1.17 | 1.28 | -0.16 |
| pre30_rng_r | 0.77 | 0.68 | +0.14 |
| post10_rng_r | 0.56 | 0.66 | -0.11 |
| pre10_rng_r | 0.88 | 0.97 | -0.05 |
| gap% | 68.57 | 67.58 | +0.00 |
| day2 | 0.13 | 0.13 | +0.00 |
k=3: sizes [33, 16, 11] inertia 1370.6
k=4: sizes [26, 16, 11, 7] inertia 1281.5
k=5: sizes [25, 13, 11, 9, 2] inertia 1220.4

### k=4 clusters of the TOP-60 pre-ride fingerprints (contrast set assigned to nearest centroid)

#### Cluster 0: 16 big rides / 35 contrast name-days land here (ratio 0.5:1)
defining features (z vs pool, raw mean): post10_above -0.9z (0.04); pre10_above -0.7z (0.08); post10_from_hi -0.7z (-29.55); pre10_hl -0.6z (-0.20); pre10_from_hi -0.6z (-28.15); pre30_above -0.6z (0.19); pre30_from_hi -0.5z (-25.53)
members: CPOP 06-10 11:22 +500%, PLAG 08-11 10:01 +274%, MTEN 06-09 11:15 +247%, VERU 06-04 09:33 +238%, STAK 07-24 10:08 +227%, ZYBT 08-05 10:35 +158%, SRXH 07-08 11:38 +152%, AHMA 06-09 11:27 +149%, AIM 06-01 10:19 +149%, SDOT 06-29 09:41 +146%, VEEE 07-14 09:30 +138%, SMTK 06-08 10:12 +131%, HCAI 05-18 10:16 +129%, PCLA 05-26 11:13 +128%, LBGJ 08-06 09:47 +126%, BOXL 08-12 11:07 +126%
in words: mostly BELOW VWAP before; start 28% off session high (deep pullback/backside); 34% above session low; nearest base top 5% away; pre-10 volume 1.6x / range 0.6x prior-20 avg; post-10 vol 0.9x range 0.4x; start 61 min after open; gap +21%; day-2 31%; halt pre 25% / post 6%

#### Cluster 1: 7 big rides / 0 contrast name-days land here (ratio 7.0:1)
defining features (z vs pool, raw mean): post10_halt +2.5z (0.81); pre30_halt +2.4z (0.91); pre10_halt +2.0z (0.76); halt_post10 +1.6z (1.00); pre30_cons +1.2z (17.80); halt_pre30 +1.2z (1.00); post10_cons +1.0z (17.56)
members: FIEE 07-27 09:31 +283%, CPHI 07-21 11:43 +262%, YXT 08-05 10:16 +249%, SPHL 06-05 10:08 +191%, VSA 08-07 09:36 +160%, PN 07-22 09:30 +146%, IFBD 06-08 10:47 +132%
in words: mixed VWAP side before; start 13% off session high; 57% above session low; nearest base top 15% away; pre-10 volume 1.9x / range 0.7x prior-20 avg; post-10 vol 0.8x range 0.3x; start 43 min after open; gap +64%; day-2 0%; halt pre 100% / post 100%

#### Cluster 2: 26 big rides / 22 contrast name-days land here (ratio 1.2:1)
defining features (z vs pool, raw mean): post10_from_hi +0.7z (-6.98); pre10_from_hi +0.7z (-8.05); pre10_above +0.6z (0.66); pre30_from_hi +0.6z (-7.99); halt_pre30 +0.6z (0.69); post10_above +0.5z (0.67); pre30_vol_r -0.5z (0.92)
members: KMRK 06-10 09:30 +320%, AMIX 08-04 09:45 +305%, MTEN 06-08 09:47 +296%, STKH 07-28 12:25 +294%, VBIO 08-12 09:30 +294%, HCWB 05-20 09:30 +275%, PCLA 06-26 09:30 +259%, YOUL 06-09 10:53 +231%, STFS 07-28 09:38 +220%, ZCMD 07-22 09:30 +219%, CIGL 06-30 11:20 +207%, YJ 08-07 09:30 +205%, TJGC 06-03 12:00 +201%, RYOJ 05-22 11:20 +192%, PAVS 06-08 09:38 +188%, PRFX 06-15 09:30 +175%, NXXT 05-19 09:32 +175%, EGG 07-28 09:41 +174%, YMAT 05-29 09:30 +156%, GELS 06-11 10:50 +156%, CDTG 06-04 09:33 +143%, PAVS 07-23 09:37 +137%, SPKLW 06-11 09:44 +133%, PCLA 08-10 09:33 +131%, CPHI 07-15 09:30 +125%, BCARU 08-10 09:30 +125%
in words: mixed VWAP side before; start 8% off session high; 25% above session low; nearest base top 3% away; pre-10 volume 1.0x / range 1.3x prior-20 avg; post-10 vol 1.3x range 0.8x; start 31 min after open; gap +23%; day-2 8%; halt pre 69% / post 38%

#### Cluster 3: 11 big rides / 3 contrast name-days land here (ratio 3.7:1)
defining features (z vs pool, raw mean): pre10_cons +2.0z (25.95); pre30_cons +1.9z (24.54); post10_cons +1.9z (27.03); post10_from_lo +1.8z (329.08); pre30_from_lo +1.7z (299.25); pre10_from_lo +1.7z (281.07); min_since_open +1.5z (181.73)
members: INHD 06-08 13:19 +312%, BYAH 06-08 13:20 +276%, NPT 06-08 13:39 +256%, XHLD 08-06 14:59 +210%, DSY 06-10 09:42 +196%, VEEE 07-13 09:56 +183%, PAVS 06-09 10:46 +174%, WFF 08-07 13:44 +170%, ATGL 08-07 11:00 +170%, BBBY.WS 08-13 13:20 +153%, ZYBT 07-20 14:00 +148%
in words: mostly ABOVE VWAP before the ride; start 17% off session high; 281% above session low; nearest base top 26% away; pre-10 volume 1.2x / range 0.5x prior-20 avg; post-10 vol 1.1x range 0.4x; start 182 min after open; gap +249%; day-2 9%; halt pre 82% / post 45%

## STEP 1 — THE BIG RIDES (ride = close->close leg, closes never >15% off running high; RTH only)
Universe 729 RTH name-days. Top-60 cutoff = +124.7%. Median ride over the universe = +51.6%.

### Top-60 table (start/peak times ET; doorway = which of OUR detectors fired inside first 20% of the leg; capture = E3 $ / full-ride $ from that entry)
| # | name | date | ride % | start ET | peak ET | day-gain@start | VWAP@start | day2 | halt-in-ride | cluster | doorways | E3 $ | E4 $ | full $ | E3 cap | E4 cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CPOP | 2026-06-10 | +500% | 11:22 | 13:14 | +18% | below | N | Y | C0 | v2_flush@11:53 | +50 | +49 | +1090 | 0.05 | 0.05 |
| 2 | KMRK | 2026-06-10 | +320% | 09:30 | 11:31 | -3% | below | N | Y | C2 | v2_flush@09:31, BA_break@10:27, vwap_bandpass@10:27, grinder1030@10:53 | -60/+269/+269/+253 | -60/+488/+488/+457 | +1235/+1263/+1263/+1208 | -0.05/0.21/0.21/0.21 | -0.05/0.39/0.39/0.38 |
| 3 | INHD | 2026-06-08 | +312% | 13:19 | 15:49 | +901% | above | N | Y | C3 | NONE [mid-range(-24%off-hi) above-VWAP pre3min-range22.7% post-vol1.3x] | - | - | - | - | - |
| 4 | AMIX | 2026-08-04 | +305% | 09:45 | 13:09 | +44% | below | N | Y | C2 | v2_flush@10:12, BA_break@10:10 | -50/-1 | -50/-51 | +1122/+1271 | -0.04/-0.00 | -0.04/-0.04 |
| 5 | MTEN | 2026-06-08 | +296% | 09:47 | 14:06 | -2% | below | N | Y | C2 | v2_flush@09:49, BA_break@10:08, grinder1030@11:22 | +108/+100/-21 | +166/+151/-21 | +1452/+1407/+1380 | 0.07/0.07/-0.02 | 0.11/0.11/-0.02 |
| 6 | STKH | 2026-07-28 | +294% | 12:25 | 13:29 | +15% | below | N | Y | C2 | v2_flush@12:25 | +107 | +164 | +1396 | 0.08 | 0.12 |
| 7 | VBIO | 2026-08-12 | +294% | 09:30 | 09:56 | +6% | below | N | Y | C2 | v2_flush@09:30 | +490 | +931 | +1231 | 0.40 | 0.76 |
| 8 | FIEE | 2026-07-27 | +283% | 09:31 | 11:25 | -2% | below | N | Y | C1 | v2_flush@09:44, BA_break@10:08 | -27/-48 | -27/-48 | +1307/+1239 | -0.02/-0.04 | -0.02/-0.04 |
| 9 | BYAH | 2026-06-08 | +276% | 13:20 | 14:13 | +42% | below | N | Y | C3 | vwap_bandpass@13:24 | +443 | +835 | +842 | 0.53 | 0.99 |
| 10 | HCWB | 2026-05-20 | +275% | 09:30 | 10:42 | +0% | above | N | Y | C2 | v2_flush@09:30, BA_break@10:01, vwap_bandpass@09:32, orb15@10:03 | +75/+158/+52/+137 | +100/+267/+53/+224 | +1247/+851/+1111/+776 | 0.06/0.19/0.05/0.18 | 0.08/0.31/0.05/0.29 |
| 11 | PLAG | 2026-08-11 | +274% | 10:01 | 12:02 | +82% | below | N | Y | C0 | v2_flush@10:23, BA_break@10:09, orb15@10:12 | +87/+33/+68 | +124/+16/-49 | +1062/+1179/+966 | 0.08/0.03/0.07 | 0.12/0.01/-0.05 |
| 12 | CPHI | 2026-07-21 | +262% | 11:43 | 12:13 | +168% | above | N | Y | C1 | NONE [post-halt-resumption(<=5min) mid-range(-45%off-hi) above-VWAP pre3min-range91.4% post-vol0.8x] | - | - | - | - | - |
| 13 | PCLA | 2026-06-26 | +259% | 09:30 | 12:02 | -2% | above | N | Y | C2 | v2_flush@09:37, BA_break@09:50, vwap_bandpass@10:02, orb15@09:50 | +557/+496/+478/+499 | +1064/+942/+906/+948 | +1140/+1012/+975/+1019 | 0.49/0.49/0.49/0.49 | 0.93/0.93/0.93/0.93 |
| 14 | NPT | 2026-06-08 | +256% | 13:39 | 14:16 | +126% | below | N | Y | C3 | v2_flush@13:43, BA_break@13:47 | +430/+325 | +811/+599 | +1212/+936 | 0.36/0.35 | 0.67/0.64 |
| 15 | YXT | 2026-08-05 | +249% | 10:16 | 11:29 | +130% | below | N | Y | C1 | v2_flush@10:30 | +363 | +675 | +943 | 0.38 | 0.72 |
| 16 | MTEN | 2026-06-09 | +247% | 11:15 | 12:14 | +41% | below | Y | Y | C0 | v2_flush@11:15, BA_break@11:55 | +124/+52 | +198/+55 | +1149/+810 | 0.11/0.06 | 0.17/0.07 |
| 17 | VERU | 2026-06-04 | +238% | 09:33 | 12:25 | -6% | below | N | Y | C0 | v2_flush@10:24, BA_break@09:42, vwap_bandpass@09:47, grinder1030@10:46, orb15@09:46 | +411/+501/+498/+377/+498 | +772/+952/+945/+704/+945 | +914/+1114/+1107/+839/+1107 | 0.45/0.45/0.45/0.45/0.45 | 0.84/0.85/0.85/0.84/0.85 |
| 18 | YOUL | 2026-06-09 | +231% | 10:53 | 15:55 | +13% | below | N | Y | C2 | v2_flush@11:01, BA_break@10:59 | -37/+103 | -37/-44 | +926/+975 | -0.04/0.11 | -0.04/-0.05 |
| 19 | STAK | 2026-07-24 | +227% | 10:08 | 13:40 | -11% | below | N | Y | C0 | v2_flush@11:01, BA_break@10:14, grinder1030@11:00 | -13/+17/-47 | -13/-7/-47 | +910/+1017/+889 | -0.01/0.02/-0.05 | -0.01/-0.01/-0.05 |
| 20 | STFS | 2026-07-28 | +220% | 09:38 | 12:42 | -12% | below | N | Y | C2 | v2_flush@09:41, BA_break@10:50, grinder1030@11:26 | -39/-40/+26 | -39/-40/+1 | +911/+911/+842 | -0.04/-0.04/0.03 | -0.04/-0.04/0.00 |
| 21 | ZCMD | 2026-07-22 | +219% | 09:30 | 10:35 | +47% | below | N | Y | C2 | v2_flush@09:30 | +399 | +747 | +985 | 0.40 | 0.76 |
| 22 | XHLD | 2026-08-06 | +210% | 14:59 | 15:39 | +81% | above | N | Y | C3 | NONE [mid-range(-22%off-hi) above-VWAP pre3min-range11.1% post-vol1.5x] | - | - | - | - | - |
| 23 | CIGL | 2026-06-30 | +207% | 11:20 | 13:56 | -6% | below | N | Y | C2 | v2_flush@11:23, BA_break@11:54, grinder1030@12:14 | +63/+59/+48 | +75/+69/+46 | +1001/+985/+924 | 0.06/0.06/0.05 | 0.07/0.07/0.05 |
| 24 | YJ | 2026-08-07 | +205% | 09:30 | 10:21 | +6% | below | N | Y | C2 | v2_flush@09:33, BA_break@09:48, vwap_bandpass@09:52, orb15@09:49 | -32/+227/+190/+198 | -32/+404/+331/+346 | +900/+741/+640/+661 | -0.04/0.31/0.30/0.30 | -0.04/0.55/0.52/0.52 |
| 25 | TJGC | 2026-06-03 | +201% | 12:00 | 13:11 | +7% | below | N | Y | C2 | NONE [at-session-low(bottom-fish) below-VWAP pre3min-range21.7% post-vol0.0x] | - | - | - | - | - |
| 26 | DSY | 2026-06-10 | +196% | 09:42 | 10:15 | +260% | below | N | N | C3 | v2_flush@09:59 | +84 | +118 | +629 | 0.13 | 0.19 |
| 27 | RYOJ | 2026-05-22 | +192% | 11:20 | 12:13 | +30% | below | N | Y | C2 | v2_flush@11:40, BA_break@11:37 | +263/+293 | +477/+536 | +760/+836 | 0.35/0.35 | 0.63/0.64 |
| 28 | SPHL | 2026-06-05 | +191% | 10:08 | 10:31 | +51% | below | N | Y | C1 | orb15@10:09 | +269 | +489 | +715 | 0.38 | 0.68 |
| 29 | PAVS | 2026-06-08 | +188% | 09:38 | 14:09 | +0% | below | N | Y | C2 | v2_flush@12:02, BA_break@10:00, grinder1030@11:15 | -21/-10/+44 | -21/-10/+37 | +856/+916/+910 | -0.02/-0.01/0.05 | -0.02/-0.01/0.04 |
| 30 | VEEE | 2026-07-13 | +183% | 09:56 | 11:16 | +109% | below | N | Y | C3 | v2_flush@10:15, vwap_bandpass@10:18 | +99/+70 | +149/+90 | +668/+563 | 0.15/0.12 | 0.22/0.16 |
| 31 | PRFX | 2026-06-15 | +175% | 09:30 | 15:04 | +0% | below | N | Y | C2 | v2_flush@14:34, BA_break@10:13, grinder1030@12:22 | -32/-15/+75 | -32/-15/+99 | +605/+832/+832 | -0.05/-0.02/0.09 | -0.05/-0.02/0.12 |
| 32 | NXXT | 2026-05-19 | +175% | 09:32 | 15:27 | -4% | below | N | N | C2 | v2_flush@09:37, BA_break@09:42, orb15@09:49 | -18/+80/+47 | -18/+109/+45 | +764/+720/+591 | -0.02/0.11/0.08 | -0.02/0.15/0.08 |
| 33 | EGG | 2026-07-28 | +174% | 09:41 | 10:22 | +16% | below | N | Y | C2 | v2_flush@09:43 | +351 | -0 | +657 | 0.53 | -0.00 |
| 34 | PAVS | 2026-06-09 | +174% | 10:46 | 11:26 | +417% | below | Y | N | C3 | NONE [post-halt-resumption(<=5min) mid-range(-40%off-hi) below-VWAP pre3min-range52.6% post-vol0.9x] | - | - | - | - | - |
| 35 | WFF | 2026-08-07 | +170% | 13:44 | 14:09 | +25% | below | N | Y | C3 | NONE [mid-range(-30%off-hi) below-VWAP pre3min-range36.5% post-vol0.7x] | - | - | - | - | - |
| 36 | ATGL | 2026-08-07 | +170% | 11:00 | 11:49 | +29% | below | N | Y | C3 | NONE [mid-range(-17%off-hi) below-VWAP pre3min-range22.0% post-vol2.0x] | - | - | - | - | - |
| 37 | VSA | 2026-08-07 | +160% | 09:36 | 12:47 | -2% | below | N | Y | C1 | v2_flush@10:02, BA_break@10:49, vwap_bandpass@11:59, grinder1030@11:54 | +147/+146/+102/+133 | +245/+241/+155/+216 | +754/+748/+602/+705 | 0.20/0.19/0.17/0.19 | 0.32/0.32/0.26/0.31 |
| 38 | ZYBT | 2026-08-05 | +158% | 10:35 | 11:28 | +16% | below | N | Y | C0 | v2_flush@10:52, BA_break@10:57 | +241/+232 | +431/+414 | +688/+666 | 0.35/0.35 | 0.63/0.62 |
| 39 | YMAT | 2026-05-29 | +156% | 09:30 | 13:21 | -2% | below | Y | Y | C2 | v2_flush@09:42, BA_break@10:47 | -9/-12 | -9/-12 | +755/+755 | -0.01/-0.02 | -0.01/-0.02 |
| 40 | GELS | 2026-06-11 | +156% | 10:50 | 11:23 | +23% | below | N | Y | C2 | v2_flush@10:57 | +106 | +163 | +573 | 0.19 | 0.28 |
| 41 | BBBY.WS | 2026-08-13 | +153% | 13:20 | 13:29 | +104% | above | N | N | C3 | NONE [mid-range(-28%off-hi) above-VWAP pre3min-range64.8% post-vol1.3x] | - | - | - | - | - |
| 42 | SRXH | 2026-07-08 | +152% | 11:38 | 15:34 | -27% | below | N | Y | C0 | v2_flush@12:24, BA_break@12:10 | +88/+114 | +126/+177 | +587/+676 | 0.15/0.17 | 0.21/0.26 |
| 43 | AHMA | 2026-06-09 | +149% | 11:27 | 11:51 | +101% | below | N | Y | C0 | v2_flush@11:37, BA_break@11:37 | +238/+243 | +426/+436 | +544/+557 | 0.44/0.44 | 0.78/0.78 |
| 44 | AIM | 2026-06-01 | +149% | 10:19 | 12:20 | +20% | below | N | Y | C0 | v2_flush@10:36, BA_break@10:30 | -17/+166 | -17/+283 | +623/+628 | -0.03/0.26 | -0.03/0.45 |
| 45 | ZYBT | 2026-07-20 | +148% | 14:00 | 16:00 | +321% | above | N | Y | C3 | NONE [post-halt-resumption(<=5min) mid-range(-16%off-hi) above-VWAP pre3min-range22.1% post-vol0.7x] | - | - | - | - | - |
| 46 | PN | 2026-07-22 | +146% | 09:30 | 15:57 | -1% | below | N | Y | C1 | v2_flush@10:18, BA_break@10:10, vwap_bandpass@12:35, grinder1030@10:55, orb15@09:56 | +22/-36/+35/-18/+22 | -6/-36/+19/-18/-5 | +671/+638/+525/+637/+673 | 0.03/-0.06/0.07/-0.03/0.03 | -0.01/-0.06/0.04/-0.03/-0.01 |
| 47 | SDOT | 2026-06-29 | +146% | 09:41 | 12:00 | -18% | below | Y | Y | C0 | v2_flush@10:01, BA_break@09:58, orb15@10:04 | +109/+124/+97 | +168/+197/+144 | +568/+615/+529 | 0.19/0.20/0.18 | 0.30/0.32/0.27 |
| 48 | CDTG | 2026-06-04 | +143% | 09:33 | 11:39 | -10% | below | N | Y | C2 | v2_flush@09:50, BA_break@10:07 | -24/-27 | -24/-27 | +571/+603 | -0.04/-0.04 | -0.04/-0.04 |
| 49 | VEEE | 2026-07-14 | +138% | 09:30 | 10:55 | -27% | below | Y | Y | C0 | v2_flush@09:31 | -22 | -22 | +646 | -0.03 | -0.03 |
| 50 | PAVS | 2026-07-23 | +137% | 09:37 | 10:54 | -1% | below | N | Y | C2 | v2_flush@09:52, BA_break@09:46, vwap_bandpass@10:12, orb15@09:51 | -19/+262/+222/+241 | -19/+474/+395/+432 | +601/+634/+542/+585 | -0.03/0.41/0.41/0.41 | -0.03/0.75/0.73/0.74 |
| 51 | SPKLW | 2026-06-11 | +133% | 09:44 | 14:23 | +189% | below | N | Y | C2 | v2_flush@09:45 | +252 | +454 | +567 | 0.44 | 0.80 |
| 52 | IFBD | 2026-06-08 | +132% | 10:47 | 14:22 | -1% | below | N | Y | C1 | v2_flush@10:56, BA_break@11:03, grinder1030@11:03 | +103/+89/+89 | +155/+128/+128 | +642/+594/+594 | 0.16/0.15/0.15 | 0.24/0.22/0.22 |
| 53 | PCLA | 2026-08-10 | +131% | 09:33 | 11:02 | +3% | below | N | Y | C2 | v2_flush@09:55, BA_break@09:54, orb15@09:56 | +60/+60/+51 | +69/+69/+52 | +583/+583/+550 | 0.10/0.10/0.09 | 0.12/0.12/0.09 |
| 54 | SMTK | 2026-06-08 | +131% | 10:12 | 14:52 | +22% | below | Y | Y | C0 | v2_flush@10:47, BA_break@10:41 | -14/-25 | -14/-21 | +516/+531 | -0.03/-0.05 | -0.03/-0.04 |
| 55 | HCAI | 2026-05-18 | +129% | 10:16 | 13:09 | +33% | below | N | Y | C0 | v2_flush@10:29, BA_break@10:27 | -29/+29 | -29/+8 | +538/+546 | -0.05/0.05 | -0.05/0.01 |
| 56 | PCLA | 2026-05-26 | +128% | 11:13 | 15:46 | -9% | below | Y | Y | C0 | v2_flush@11:58, BA_break@11:36, vwap_bandpass@13:24 | -27/+259/-11 | -27/+469/-11 | +493/+557/+520 | -0.05/0.47/-0.02 | -0.05/0.84/-0.02 |
| 57 | LBGJ | 2026-08-06 | +126% | 09:47 | 13:27 | -5% | below | N | Y | C0 | v2_flush@09:52, BA_break@09:52, vwap_bandpass@11:57, orb15@10:17 | -15/+58/-20/+47 | -15/+66/-20/+45 | +586/+560/+534/+520 | -0.03/0.10/-0.04/0.09 | -0.03/0.12/-0.04/0.09 |
| 58 | BOXL | 2026-08-12 | +126% | 11:07 | 15:32 | +47% | below | N | N | C0 | v2_flush@11:51, BA_break@11:39 | +110/+118 | +171/+186 | +555/+578 | 0.20/0.20 | 0.31/0.32 |
| 59 | CPHI | 2026-07-15 | +125% | 09:30 | 10:47 | -7% | below | Y | Y | C2 | v2_flush@09:31, BA_break@10:01, vwap_bandpass@10:17, orb15@10:02 | +63/+51/+37/+39 | +76/+52/+23/+29 | +536/+492/+441/+450 | 0.12/0.10/0.08/0.09 | 0.14/0.11/0.05/0.06 |
| 60 | BCARU | 2026-08-10 | +125% | 09:30 | 10:03 | +54% | below | N | Y | C2 | v2_flush@09:31 | -33 | -33 | +452 | -0.07 | -0.07 |

### Top-20 by pure RTH low -> later high
| # | name | date | low->high % | ride % (15%-tol leg) |
|---|---|---|---|---|
| 1 | INHD | 2026-06-08 | +3807% | +312% |
| 2 | CPHI | 2026-07-21 | +2258% | +262% |
| 3 | YJ | 2026-08-07 | +975% | +205% |
| 4 | STAK | 2026-07-24 | +926% | +227% |
| 5 | NPT | 2026-06-08 | +836% | +256% |
| 6 | RGNT | 2026-06-15 | +823% | +124% |
| 7 | XHLD | 2026-08-06 | +609% | +210% |
| 8 | ZYBT | 2026-07-20 | +606% | +148% |
| 9 | PLAG | 2026-08-11 | +585% | +274% |
| 10 | CPOP | 2026-06-10 | +522% | +500% |
| 11 | BYAH | 2026-06-08 | +474% | +276% |
| 12 | ZCMD | 2026-07-22 | +462% | +219% |
| 13 | BBBY.WS | 2026-08-13 | +446% | +153% |
| 14 | YXT | 2026-08-05 | +440% | +249% |
| 15 | STKH | 2026-07-28 | +396% | +294% |
| 16 | AMIX | 2026-08-04 | +371% | +305% |
| 17 | SPHL | 2026-06-05 | +364% | +191% |
| 18 | SUNE | 2026-06-08 | +333% | +103% |
| 19 | KMRK | 2026-06-10 | +320% | +320% |
| 20 | JLHL | 2026-07-09 | +305% | +85% |

## STEP 2 — DOORWAY CENSUS over the top-60 (detector fired between ride start and peak, entry <= start + 20% of the leg)
| doorway | big rides with it | % of 60 |
|---|---|---|
| v2_flush | 49 | 82% |
| BA_break | 37 | 62% |
| vwap_bandpass | 13 | 22% |
| grinder1030 | 11 | 18% |
| orb15 | 13 | 22% |
| NONE | 9 | 15% |
| pre_reclaim(ctx) | 7 | 12% |
any of ours (RTH doors): 51 / 60 = 85%; NONE = 9 (15%). pre_reclaim(ctx) = a PRE band-pass fired somewhere 07:00-09:25 that day (context, not an RTH doorway; 9:25 flatten).

### Cluster x doorway (secondary to the clusters)
| cluster | n | v2_flush | BA_break | vwap_bandpass | grinder1030 | orb15 | NONE |
|---|---|---|---|---|---|---|---|
| C0 | 16 | 16 | 14 | 3 | 2 | 4 | 0 |
| C1 | 7 | 5 | 4 | 2 | 3 | 2 | 1 |
| C2 | 26 | 25 | 18 | 6 | 6 | 7 | 1 |
| C3 | 11 | 3 | 1 | 2 | 0 | 0 | 7 |

## STEP 3 — THE RIDE: capture ratio (E3 $ or E4 $) / (full ride $ from the doorway fill to the ride peak), $500, +1% slip, 0.5% mkt exit, 15:45 flatten
E3 capture: n=123 mean 0.15 median 0.10 p25 -0.01 p75 0.28 min -0.07 max 0.53 share<0 28% share>=0.5 2%
E4 capture: n=123 mean 0.25 median 0.12 p25 -0.02 p75 0.42 min -0.07 max 0.99 share<0 33% share>=0.5 24%

| doorway | n | E3 $ total | E4 $ total | full $ total | E3 cap (sum) | E4 cap (sum) |
|---|---|---|---|---|---|---|
| v2_flush | 49 | $+5060 | $+8558 | $+40126 | 0.13 | 0.21 |
| BA_break | 37 | $+4452 | $+7476 | $+29976 | 0.15 | 0.25 |
| vwap_bandpass | 13 | $+2365 | $+4210 | $+9664 | 0.24 | 0.44 |
| grinder1030 | 11 | $+958 | $+1602 | $+9761 | 0.10 | 0.16 |
| orb15 | 13 | $+2214 | $+3643 | $+9141 | 0.24 | 0.40 |
ALL doors in big rides: E3 $+15049 vs E4 $+25490 vs full $+98667 -> best-capture exit on big rides = E4 (0.26 of full).

## STEP 4 — THE MISSING DOOR: the (g) rides none of our detectors entered
N = 9. Tag counts: above-VWAP 5, below-VWAP 4, post-halt-resumption(<=5min) 3, mid-range(-24%off-hi) 1, mid-range(-45%off-hi) 1, mid-range(-22%off-hi) 1, at-session-low(bottom-fish) 1, mid-range(-40%off-hi) 1, mid-range(-30%off-hi) 1, mid-range(-17%off-hi) 1, mid-range(-28%off-hi) 1, mid-range(-16%off-hi) 1
| name | date | ride | start ET | cluster | tags |
|---|---|---|---|---|---|
| INHD | 2026-06-08 | +312% | 13:19 | C3 | mid-range(-24%off-hi) above-VWAP pre3min-range22.7% post-vol1.3x |
| CPHI | 2026-07-21 | +262% | 11:43 | C1 | post-halt-resumption(<=5min) mid-range(-45%off-hi) above-VWAP pre3min-range91.4% post-vol0.8x |
| XHLD | 2026-08-06 | +210% | 14:59 | C3 | mid-range(-22%off-hi) above-VWAP pre3min-range11.1% post-vol1.5x |
| TJGC | 2026-06-03 | +201% | 12:00 | C2 | at-session-low(bottom-fish) below-VWAP pre3min-range21.7% post-vol0.0x |
| PAVS | 2026-06-09 | +174% | 10:46 | C3 | post-halt-resumption(<=5min) mid-range(-40%off-hi) below-VWAP pre3min-range52.6% post-vol0.9x |
| WFF | 2026-08-07 | +170% | 13:44 | C3 | mid-range(-30%off-hi) below-VWAP pre3min-range36.5% post-vol0.7x |
| ATGL | 2026-08-07 | +170% | 11:00 | C3 | mid-range(-17%off-hi) below-VWAP pre3min-range22.0% post-vol2.0x |
| BBBY.WS | 2026-08-13 | +153% | 13:20 | C3 | mid-range(-28%off-hi) above-VWAP pre3min-range64.8% post-vol1.3x |
| ZYBT | 2026-07-20 | +148% | 14:00 | C3 | post-halt-resumption(<=5min) mid-range(-16%off-hi) above-VWAP pre3min-range22.1% post-vol0.7x |
cluster distribution of (g): {3: 7, 1: 1, 2: 1}

## STEP 5 — INVERSE CHECK: where do the same doorways fire when it is NOT a big ride?
For every detector: total fires over the universe (unchanged sequencing), fires that land inside a top-60 ride's first-20% window (TRUE), fires on top-60 name-days but outside the window, fires on non-top-60 name-days (FALSE-POP), name-days with >=1 fire.
| doorway | fires total | in-window (big) | big-day, off-window | non-big-day fires | non-big name-days w/ fire | precision in-window/total | fires per big-ride hit |
|---|---|---|---|---|---|---|---|
| v2_flush | 9388 | 168 | 493 | 8727 | 662 | 0.018 | 191.6 |
| BA_break | 4452 | 80 | 165 | 4207 | 669 | 0.018 | 120.3 |
| vwap_bandpass | 414 | 14 | 27 | 373 | 293 | 0.034 | 31.8 |
| grinder1030 | 387 | 24 | 8 | 355 | 138 | 0.062 | 35.2 |
| orb15 | 371 | 13 | 21 | 337 | 337 | 0.035 | 28.5 |

### The false-positive population under E3 (does the door pay for itself outside the big rides?)
| doorway | non-big fires | E3 $ | mean/tr | big-window fires E3 $ |
|---|---|---|---|---|
| v2_flush | 9220 | $-65561 | $-7.11 | $+8726 (n=168) |
| BA_break | 4372 | $-1247 | $-0.29 | $+6698 (n=80) |
| vwap_bandpass | 400 | $+507 | $+1.27 | $+2350 (n=14) |
| grinder1030 | 363 | $+8917 | $+24.56 | $+1412 (n=24) |
| orb15 | 358 | $+9584 | $+26.77 | $+2214 (n=13) |

## HAND-TRACES — the three biggest rides, bar-by-bar around the start (10s bars, ET; VWAP = session tp-VWAP)

### CPOP 2026-06-10 ride +500% start 11:22 @0.425 -> peak 13:14 @2.550; doorways: v2_flush@11:53 E3 $+50 E4 $+49 full $+1090; cluster C0
| ET | o | h | l | c | vol | vs VWAP | note |
|---|---|---|---|---|---|---|---|
| 11:19:40 | 0.555 | 0.555 | 0.540 | 0.548 | 72247 | -36.8% |  |
| 11:19:50 | 0.548 | 0.560 | 0.544 | 0.552 | 101742 | -36.4% |  |
| 11:20:00 | 0.552 | 0.562 | 0.550 | 0.562 | 160001 | -35.2% |  |
| 11:20:10 | 0.561 | 0.566 | 0.554 | 0.566 | 135726 | -34.6% |  |
| 11:20:20 | 0.564 | 0.576 | 0.564 | 0.574 | 122693 | -33.7% |  |
| 11:20:30 | 0.574 | 0.574 | 0.510 | 0.523 | 335673 | -39.5% |  |
| 11:20:40 | 0.517 | 0.524 | 0.494 | 0.510 | 172353 | -41.1% |  |
| 11:20:50 | 0.515 | 0.521 | 0.510 | 0.518 | 160513 | -40.2% |  |
| 11:21:00 | 0.517 | 0.540 | 0.517 | 0.527 | 241040 | -39.0% |  |
| 11:21:10 | 0.540 | 0.540 | 0.527 | 0.537 | 104464 | -37.9% |  |
| 11:21:20 | 0.537 | 0.547 | 0.537 | 0.547 | 93494 | -36.7% |  |
| 11:21:30 | 0.543 | 0.547 | 0.535 | 0.547 | 89193 | -36.7% |  |
| 11:21:40 | 0.546 | 0.547 | 0.540 | 0.547 | 61581 | -36.7% |  |
| 11:21:50 | 0.540 | 0.547 | 0.514 | 0.514 | 150485 | -40.4% |  |
| 11:22:00 | 0.514 | 0.514 | 0.475 | 0.480 | 383646 | -44.3% |  |
| 11:22:10 | 0.480 | 0.498 | 0.475 | 0.491 | 153588 | -43.1% |  |
| 11:22:20 | 0.489 | 0.491 | 0.457 | 0.463 | 431012 | -46.2% |  |
| 11:22:30 | 0.468 | 0.470 | 0.430 | 0.438 | 797965 | -49.0% |  |
| 11:22:40 | 0.438 | 0.460 | 0.425 | 0.425 | 442140 | -50.5% | << RIDE START |
| 11:22:50 | 0.428 | 0.441 | 0.410 | 0.433 | 390874 | -49.5% |  |
| 11:23:00 | 0.438 | 0.450 | 0.433 | 0.447 | 177184 | -47.8% |  |
| 11:23:10 | 0.449 | 0.450 | 0.439 | 0.447 | 178168 | -47.8% |  |
| 11:23:20 | 0.443 | 0.458 | 0.440 | 0.454 | 178660 | -47.0% |  |
| 11:23:30 | 0.451 | 0.460 | 0.451 | 0.459 | 152423 | -46.3% |  |
| 11:23:40 | 0.460 | 0.474 | 0.460 | 0.474 | 153455 | -44.5% |  |
| 11:23:50 | 0.471 | 0.478 | 0.460 | 0.474 | 146472 | -44.5% |  |
| 11:24:00 | 0.474 | 0.478 | 0.464 | 0.470 | 124421 | -45.0% |  |
| 11:24:10 | 0.470 | 0.482 | 0.469 | 0.474 | 90549 | -44.4% |  |
| 11:24:20 | 0.474 | 0.485 | 0.472 | 0.480 | 79719 | -43.7% |  |
| 11:24:30 | 0.480 | 0.487 | 0.474 | 0.480 | 66113 | -43.7% |  |
| 11:24:40 | 0.480 | 0.488 | 0.472 | 0.472 | 94718 | -44.7% |  |
| 11:24:50 | 0.472 | 0.484 | 0.472 | 0.480 | 59071 | -43.7% |  |
| 11:25:00 | 0.480 | 0.487 | 0.472 | 0.481 | 88536 | -43.6% |  |
| 11:25:10 | 0.480 | 0.488 | 0.476 | 0.484 | 110705 | -43.2% |  |
| 11:25:20 | 0.484 | 0.498 | 0.483 | 0.494 | 82326 | -42.1% |  |
| 11:25:30 | 0.494 | 0.515 | 0.494 | 0.505 | 144834 | -40.7% |  |
| 11:25:40 | 0.512 | 0.530 | 0.500 | 0.510 | 159270 | -40.1% |  |
| 11:25:50 | 0.507 | 0.525 | 0.505 | 0.525 | 176570 | -38.3% |  |
| 11:26:00 | 0.519 | 0.525 | 0.510 | 0.515 | 94054 | -39.5% |  |
| 11:26:10 | 0.515 | 0.530 | 0.514 | 0.518 | 84321 | -39.1% |  |
| 11:26:20 | 0.518 | 0.520 | 0.510 | 0.518 | 65103 | -39.1% |  |
| 11:26:30 | 0.518 | 0.520 | 0.511 | 0.516 | 90752 | -39.3% |  |
| 11:26:40 | 0.512 | 0.538 | 0.512 | 0.531 | 98443 | -37.6% |  |
| 11:26:50 | 0.537 | 0.538 | 0.523 | 0.532 | 76138 | -37.5% |  |
| 11:27:00 | 0.534 | 0.539 | 0.523 | 0.529 | 120902 | -37.8% |  |
| 11:27:10 | 0.529 | 0.545 | 0.529 | 0.539 | 114788 | -36.6% |  |
| 11:27:20 | 0.542 | 0.545 | 0.520 | 0.529 | 116292 | -37.7% |  |
| 11:27:30 | 0.529 | 0.543 | 0.526 | 0.539 | 100642 | -36.6% |  |
| 11:27:40 | 0.539 | 0.540 | 0.530 | 0.536 | 103019 | -36.9% |  |
(later) v2_flush entry at 11:53:40 px 0.794 stop 0.751
pre-ride minute fingerprint (m = minutes vs start): m | px | VWAP side | %fromHi | %fromLo | base-dist% | rng x | vol x | HL
  -30 | 0.922 | A | -20.5 | 196.5 | 99.0 | 0.3 | 0.9 | +1
  -27 | 0.924 | A | -20.3 | 197.2 | 99.0 | 0.4 | 0.7 | -1
  -24 | 0.959 | A | -17.3 | 208.5 | 99.0 | 0.4 | 1.3 | +1
  -15 | 0.750 | B | -35.3 | 141.3 | 74.5 | 0.4 | 0.8 | +1
  -12 | 0.717 | B | -38.2 | 130.5 | 66.7 | 0.4 | 0.5 | -1
  -9 | 0.609 | B | -47.5 | 95.7 | 41.5 | 0.6 | 2.0 | -1
  -6 | 0.491 | B | -57.7 | 57.9 | 14.2 | 0.6 | 1.4 | -1
  -3 | 0.523 | B | -54.9 | 68.3 | 21.7 | 0.5 | 0.7 | -1
  +0 | 0.459 | B | -60.4 | 47.6 | 6.7 | 0.4 | 1.2 | -1
  +3 | 0.516 | B | -55.5 | 66.0 | 20.0 | 0.2 | 0.6 | +1
  +6 | 0.563 | B | -51.4 | 81.2 | 31.0 | 0.2 | 0.9 | +1
  +9 | 0.619 | B | -46.7 | 99.0 | 43.9 | 0.4 | 1.2 | +1

### KMRK 2026-06-10 ride +320% start 09:30 @1.570 -> peak 11:31 @6.590; doorways: v2_flush@09:31 E3 $-60 E4 $-60 full $+1235, BA_break@10:27 E3 $+269 E4 $+488 full $+1263, vwap_bandpass@10:27 E3 $+269 E4 $+488 full $+1263, grinder1030@10:53 E3 $+253 E4 $+457 full $+1208; cluster C2
| ET | o | h | l | c | vol | vs VWAP | note |
|---|---|---|---|---|---|---|---|
| 09:30:00 | 1.570 | 1.570 | 1.570 | 1.570 | 20 | -0.0% | << RIDE START |
| 09:31:00 | 1.680 | 1.680 | 1.680 | 1.680 | 8 | +4.9% |  |
| 09:31:10 | 1.880 | 1.880 | 1.680 | 1.680 | 32 | +0.1% |  |
| 09:31:20 | 1.680 | 1.880 | 1.680 | 1.880 | 6 | +11.2% |  |
| 09:31:30 | 1.870 | 1.870 | 1.860 | 1.860 | 6 | +9.1% |  |
| 09:31:40 | 1.880 | 1.880 | 1.880 | 1.880 | 2 | +9.9% | << v2_flush entry 1.880 stop 1.680 |
| 09:31:50 | 1.870 | 1.870 | 1.870 | 1.870 | 2 | +9.1% |  |
| 09:33:00 | 1.770 | 1.770 | 1.770 | 1.770 | 1 | +3.2% |  |
| 09:35:30 | 1.680 | 1.680 | 1.680 | 1.680 | 1000 | -0.1% |  |
| 09:39:20 | 1.680 | 1.680 | 1.680 | 1.680 | 7 | -0.2% |  |
| 09:39:30 | 1.680 | 1.880 | 1.680 | 1.880 | 15 | +11.6% |  |
| 09:39:40 | 1.880 | 1.880 | 1.680 | 1.680 | 13 | -0.3% |  |
| 09:39:50 | 1.680 | 1.880 | 1.680 | 1.880 | 14 | +11.5% |  |
| 09:40:00 | 1.880 | 1.880 | 1.680 | 1.880 | 14 | +11.4% |  |
| 09:40:10 | 1.880 | 1.880 | 1.680 | 1.680 | 11 | -0.5% |  |
| 09:40:20 | 1.680 | 1.880 | 1.680 | 1.880 | 13 | +11.2% |  |
| 09:40:30 | 1.680 | 1.880 | 1.680 | 1.680 | 12 | -0.6% |  |
| 09:40:40 | 1.680 | 1.880 | 1.680 | 1.680 | 13 | -0.7% |  |
| 09:40:50 | 1.680 | 1.880 | 1.680 | 1.680 | 6 | -0.7% |  |
| 09:41:00 | 1.680 | 1.880 | 1.680 | 1.680 | 11 | -0.7% |  |
| 09:41:10 | 1.680 | 1.880 | 1.680 | 1.680 | 15 | -0.8% |  |
| 09:41:20 | 1.680 | 1.880 | 1.680 | 1.880 | 9 | +11.0% |  |
| 09:41:30 | 1.880 | 1.880 | 1.680 | 1.680 | 13 | -0.8% |  |
| 09:41:40 | 1.680 | 1.880 | 1.680 | 1.680 | 11 | -0.9% |  |
| 09:41:50 | 1.680 | 1.880 | 1.680 | 1.880 | 12 | +10.9% |  |
| 09:42:00 | 1.880 | 1.880 | 1.880 | 1.880 | 7 | +10.8% |  |
| 09:42:10 | 1.880 | 1.880 | 1.880 | 1.880 | 6 | +10.7% |  |
| 09:42:20 | 1.880 | 1.880 | 1.880 | 1.880 | 10 | +10.6% |  |
| 09:42:30 | 1.880 | 1.880 | 1.880 | 1.880 | 7 | +10.6% |  |
| 09:42:40 | 1.730 | 1.880 | 1.730 | 1.880 | 124 | +9.8% |  |
| 09:42:50 | 1.880 | 1.880 | 1.880 | 1.880 | 9 | +9.8% |  |
(later) BA_break entry at 10:27:10 px 1.850 stop 1.740
(later) vwap_bandpass entry at 10:27:10 px 1.850 stop 1.740
(later) grinder1030 entry at 10:53:00 px 1.910 stop 1.830
pre-ride minute fingerprint (m = minutes vs start): m | px | VWAP side | %fromHi | %fromLo | base-dist% | rng x | vol x | HL
  -9 | 1.650 | A | 0.0 | 1.9 | 0.0 | 1.0 | 1.0 | +0
  +0 | 1.570 | B | -4.8 | 0.0 | 4.8 | 1.0 | 1.0 | +0
  +3 | 1.770 | A | -5.8 | 12.8 | 7.3 | 0.0 | 0.0 | +0
  +9 | 1.880 | A | 0.0 | 19.7 | 13.9 | 0.9 | 0.1 | +0

### INHD 2026-06-08 ride +312% start 13:19 @10.515 -> peak 15:49 @43.370; doorways: NONE mid-range(-24%off-hi) above-VWAP pre3min-range22.7% post-vol1.3x; cluster C3
| ET | o | h | l | c | vol | vs VWAP | note |
|---|---|---|---|---|---|---|---|
| 13:16:10 | 12.830 | 12.900 | 12.550 | 12.550 | 112585 | +130.8% |  |
| 13:16:20 | 12.550 | 12.555 | 12.404 | 12.404 | 89569 | +128.0% |  |
| 13:16:30 | 12.410 | 12.410 | 11.460 | 11.874 | 329077 | +118.0% |  |
| 13:16:40 | 11.860 | 11.980 | 11.540 | 11.720 | 154965 | +115.0% |  |
| 13:16:50 | 11.710 | 12.410 | 11.700 | 12.188 | 168953 | +123.4% |  |
| 13:17:00 | 12.140 | 12.420 | 12.040 | 12.240 | 94925 | +124.2% |  |
| 13:17:10 | 12.188 | 12.300 | 12.020 | 12.170 | 85329 | +122.8% |  |
| 13:17:20 | 12.140 | 12.220 | 12.000 | 12.000 | 74983 | +119.6% |  |
| 13:17:30 | 12.000 | 12.130 | 11.670 | 12.010 | 113396 | +119.7% |  |
| 13:17:40 | 12.000 | 12.000 | 11.550 | 11.770 | 84123 | +115.2% |  |
| 13:17:50 | 11.780 | 12.000 | 11.700 | 11.930 | 64906 | +118.1% |  |
| 13:18:00 | 11.930 | 11.950 | 11.800 | 11.807 | 59634 | +115.8% |  |
| 13:18:10 | 11.800 | 11.940 | 11.580 | 11.930 | 105187 | +117.9% |  |
| 13:18:20 | 11.890 | 11.930 | 11.540 | 11.545 | 89907 | +110.8% |  |
| 13:18:30 | 11.549 | 11.659 | 11.220 | 11.262 | 166509 | +105.5% |  |
| 13:18:40 | 11.250 | 11.350 | 10.650 | 10.840 | 204397 | +97.6% |  |
| 13:18:50 | 10.770 | 11.200 | 10.770 | 10.960 | 183573 | +99.7% |  |
| 13:19:00 | 10.960 | 11.000 | 10.600 | 10.900 | 183648 | +98.4% |  |
| 13:19:10 | 10.880 | 11.000 | 10.510 | 10.515 | 121573 | +91.3% | << RIDE START |
| 13:19:20 | 10.510 | 10.840 | 10.450 | 10.799 | 126608 | +96.4% |  |
| 13:19:30 | 10.800 | 10.830 | 10.440 | 10.656 | 104788 | +93.7% |  |
| 13:19:40 | 10.650 | 10.710 | 10.480 | 10.670 | 97659 | +93.9% |  |
| 13:19:50 | 10.670 | 11.259 | 10.630 | 11.120 | 159497 | +102.0% |  |
| 13:20:00 | 11.140 | 12.000 | 11.120 | 11.770 | 272686 | +113.5% |  |
| 13:20:10 | 11.820 | 12.260 | 11.750 | 11.955 | 276333 | +116.6% |  |
| 13:20:20 | 11.970 | 13.000 | 11.940 | 12.723 | 324270 | +130.1% |  |
| 13:20:30 | 12.727 | 12.740 | 12.340 | 12.500 | 228610 | +125.8% |  |
| 13:20:40 | 12.490 | 12.610 | 12.420 | 12.580 | 138863 | +127.1% |  |
| 13:20:50 | 12.600 | 12.680 | 12.460 | 12.470 | 123175 | +125.0% |  |
| 13:21:00 | 12.462 | 12.720 | 12.450 | 12.450 | 219357 | +124.4% |  |
| 13:21:10 | 12.460 | 12.460 | 11.760 | 12.150 | 183772 | +118.8% |  |
| 13:21:20 | 12.125 | 12.270 | 11.777 | 12.050 | 114783 | +116.8% |  |
| 13:21:30 | 12.038 | 12.250 | 12.030 | 12.080 | 65975 | +117.3% |  |
| 13:21:40 | 12.080 | 12.460 | 12.010 | 12.350 | 138890 | +122.0% |  |
| 13:21:50 | 12.349 | 12.700 | 12.310 | 12.480 | 184186 | +124.2% |  |
| 13:22:00 | 12.490 | 12.610 | 12.260 | 12.347 | 112841 | +121.6% |  |
| 13:22:10 | 12.380 | 12.420 | 12.300 | 12.300 | 49091 | +120.7% |  |
| 13:22:20 | 12.310 | 12.380 | 12.250 | 12.300 | 64177 | +120.7% |  |
| 13:22:30 | 12.330 | 12.370 | 12.060 | 12.061 | 71661 | +116.3% |  |
| 13:22:40 | 12.060 | 12.170 | 11.900 | 11.900 | 138793 | +113.3% |  |
| 13:22:50 | 11.910 | 12.160 | 11.760 | 12.090 | 113820 | +116.6% |  |
| 13:23:00 | 12.090 | 12.900 | 12.090 | 12.571 | 273237 | +124.9% |  |
| 13:23:10 | 12.600 | 12.631 | 12.260 | 12.450 | 104743 | +122.6% |  |
| 13:23:20 | 12.430 | 12.450 | 12.200 | 12.390 | 78779 | +121.5% |  |
| 13:23:30 | 12.400 | 12.410 | 12.250 | 12.340 | 41488 | +120.5% |  |
| 13:23:40 | 12.347 | 12.360 | 12.250 | 12.315 | 35728 | +120.0% |  |
| 13:23:50 | 12.330 | 12.450 | 12.300 | 12.315 | 71875 | +120.0% |  |
| 13:24:00 | 12.330 | 12.640 | 12.310 | 12.445 | 145644 | +122.1% |  |
| 13:24:10 | 12.440 | 12.700 | 12.430 | 12.540 | 109526 | +123.7% |  |
pre-ride minute fingerprint (m = minutes vs start): m | px | VWAP side | %fromHi | %fromLo | base-dist% | rng x | vol x | HL
  -12 | 11.450 | A | -0.0 | 1045.0 | 99.0 | 0.0 | 0.1 | +1
  -6 | 12.850 | A | -6.8 | 1185.0 | 99.0 | 0.3 | 0.7 | +1
  -3 | 12.240 | A | -11.2 | 1124.0 | 99.0 | 0.4 | 0.8 | -1
  +0 | 11.770 | A | -14.6 | 1077.0 | 99.0 | 0.6 | 1.1 | -1
  +3 | 12.571 | A | -8.8 | 1157.1 | 99.0 | 0.4 | 0.7 | +0
  +6 | 14.260 | A | -2.9 | 1326.0 | 99.0 | 1.2 | 1.9 | +1
  +9 | 15.770 | A | -3.1 | 1477.0 | 99.0 | 0.3 | 0.8 | +1