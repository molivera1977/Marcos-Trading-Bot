# CROWN-ONLY ROCKET STUDY — 2026-08-16 (Sunday)

Marcos: "how about study just the crowns." Analysis only; nothing shipped. Script:
`data/killtests/crown_rockets_20260816.py` → rows `crown_rockets_20260816_rows.json`. Tick/quote caches under
`data/universe/ticks_precursor/` (gitignored). Officers touched: Crown Steward (crown table $), Seam Scientist
(tick read), Trade Manager (exits), Statistician (scorecards), Historian (cohort record), Hidden Entry Architect
(halt-flush finding), Blast Radius: clean (no code path changed).

## Cohort and method

- **97 crown name-days** (first `leader_armed` row per ticker per day, 8/5–8/14 decisions archive, `limit=50000` —
  the default 5000-row page hides the morning; that is why crown counts looked like 1–5/day at first glance).
  Reasons: 65 fresh_highs / 32 halt. 40 crowns were premarket (graded from the 09:30 bell — RTH official).
- Tape: Alpaca SIP trades, full RTH day per name (excluded off-tape/late conditions), 10s bars BUILT from ticks
  (complete; the dashboard ~ALP10S capture is trade-sparse). NBBO quotes pulled for 90s windows before every
  post-crown event and matched contrast windows, plus a from-crown full-day quote pull for entry (a).
  The 1s crown-pinned capture (`SYM~ALP1S`, e.g. FGI 8/13 = 36,238 bars) exists and was cross-checked for
  coverage but SIP ticks are the finer, complete source, so the read uses SIP throughout.
- Events after the crown: **legs** = ≥25% low→high inside 5 min; **pushes** = ≥10%. Halts = ≥240s print gaps.
- Exits ($500 clip, +1% entry slip, −0.5% exit slip, stop-first): E3 (bank ½ @+10%, then 10%-off-high),
  E4 (10%-off-high from entry), E4W (20%-off-high), STRUCT (ratchet = higher of last completed 5-min
  higher-low formed after entry and latest halt-resumption bar low; never a % trail; if the ratchet is already
  above the tape the exit is that bar's open — no phantom fills), all flatten 15:45.
- Entries after the crown: (a) mid-range pullback (≥⅓ retrace of the post-crown range) + tick trigger
  (last-30s aggressor imbalance ≥ leg-median 0.49 AND tick-rate acceleration ≥ 2.57×); (b) plain 10s
  higher-low pullback (≥3 bars ≥3% off the running high, then higher low + close over prior bar high; stop =
  pullback low), up to 6 signals per name-day; (c) hold-a-core = the FIRST (b) signal held to 15:45.

## Headline numbers

| item | value |
|---|---|
| crown name-days | 97 (37 "rockets" max ride ≥25%, 23 mid, 37 duds <10%) |
| post-crown legs ≥25% / pushes ≥10% / halts | 31 / 725 / 460 |
| legs that START at a halt resumption (no prints ≥60s before) | **23 of 31** |
| legs with a readable pre-leg tape (prints+quotes) | 8 |
| our real post-crown trades / P&L | 105 trades, **+$874.07** (RTH, from the /api/trades book) |
| (c)-E4W ceiling summed over crowns | **−$1,449** (97 clips) |
| "money left on the crown table" (ceiling − captured) | **−$2,323 → the bot out-earned the ceiling** |
| best entry/exit combo | none positive; least bad = a/E4W −$9.53/trade, c/E4 −$11.53/trade |

## Verdicts

**(i) Buyer-arrival signature on crowned names — NOT READABLE as a pre-leg trigger, and mostly not there to read.**
23 of the 31 post-crown legs begin at a halt resumption: the "60s before" is a blank tape (median seconds-since-
last-print at the trough = 295s). The leg is decided in the reopening auction, not on visible order flow. On the
8 legs with a readable tape the last-30s aggressor imbalance is +0.49 (contrast ≈ 0), rate-accel 2.6×, micro
higher-lows 0.67 vs 0.40 (AUC 0.75) — directionally the "steps in" read, but n=8 and it did not survive as a
trigger: entry (a) built on those thresholds fired 538 times and lost under every exit. On the 576 quote-covered
**pushes** (≥10%) the aggressor imbalance is NOT enriched at all (median −0.06 vs −0.003, AUC 0.50), spread and
bid-size share are flat (AUC 0.49/0.51); the only enriched features are activity and range (prints/30s AUC 0.68,
30s range AUC 0.85, since-last-print AUC 0.32 = prints are denser) — i.e. pushes come out of FAST, ACTIVE, wide
30-second windows, which is a description of the dip that precedes the push, not a buyer arriving.

*Plain words — what the tape does in the last 20–30s before a crowned name's leg:* usually nothing, because the
name is halted; the leg is the reopen. When it isn't halted (BYAH 12:12, XHG 13:02, YJ 11:40): 60–90s of thin,
one-print-per-5s drift with a small bid, then a 5-second burst where 20–70 prints all lift the offer, the ask
steps up 2–4 ticks in that same 5 seconds and the ask size THINS (BYAH: 500→100 offered while price 3.36→3.70;
XHG: 3500→500 then 300 while 3.42→3.55). The signature is simultaneous with the move, not ahead of it — the
earliest visible marker is the ask-size collapse inside the burst's first 5s, which is ~1 bar of 5s data late
already. The pre-burst window looks like every other quiet window on the same name (that is what AUC≈0.5 on
aggressor/spread/bid-share for pushes means).

**(ii) What the crown table cost us — nothing; it paid.** The bot's actual post-crown trades made +$874 across
the 97 name-days (biggest: HUIZ 8/7 +$343, WFF 8/7 +$183, BQ 8/12 +$165, FGI 8/13 +$158, WYHG 8/6 +$98). The
$500 first-pullback-and-hold ceiling with E4W lost −$1,449 in aggregate (14% win). Per name-day the "left" column
is negative on 71 of 97. The crown table is not where the money is; the crown-time table gate/hole docket
(FGI cage 8/13, BANL breaches) remains a display/latency issue, not a P&L one on this evidence.

**(iii) Convexity bar (both halves +, ≥5 HR≥$250, worst > −$150, DD < $1,000, premium reported): NO combo clears.**
All 12 entry×exit cells are net negative in both halves of the sample. Home runs exist (a/E4W: 5 HR, premium
+$2,225; b/E4W: 6 HR, +$2,360) but they are paid for many times over by ~80% stopped/trailed clips at −$10 to
−$120. E3 never produced a home run on a crowned name (bank-half caps it). STRUCT was the worst exit in (b)/(c):
5-min higher-lows on these tapes are wide and get swept.

Failure condition written before the run: "the crown-only lens is refuted if no entry/exit cell is positive
in both halves." It is refuted. Crown status identifies names that HAVE rockets (37/97 ride ≥25% from crown
price; PLAG +536%, YJ +327%, WYHG +217%, WFF +182%, FGI +135%, YXT +130%, BOXL +117%, MSGY +115%, BYAH +104%),
but the crown itself does not tell you when to be long them: median worst dip after crown is −23%, and 37/97
never ride 10%.

## Crown quality — does anything at crown time separate rockets from duds?

| feature at crown (medians) | rockets (n=37, ride ≥25%) | duds (n=37, ride <10%) |
|---|---|---|
| day gain vs prior close | +79% | +54% |
| minutes since 09:30 (RTH-clock) | 37 | 21 |
| gain from 09:30 open to crown | +13% | +2% |
| distance above session VWAP | +8.2% | +2.1% |
| halts before crown (RTH) | 0 | 0 |
| crown price | $3.25 | $4.77 |
| reason halt / fresh_highs | 10 / 27 | 11 / 26 |
| premarket crown | 13 | 13 |

Weak separators only: rockets are further above VWAP and already moving off the open at crown time (the
crown is late on them — it certifies a run in progress). Reason, halts-so-far, premarket-vs-RTH and price
do not separate. Nothing here is a gate; it is a fingerprint for the Crown Steward's docket only.

## Timeline table (all 97 crown name-days; RTH clock starts at max(crown, 09:30))

| date | sym | crown ET | why | crown px | max ride | worst dip | legs>=25% | pushes>=10% | halts post | fires | refusals | our trades | our P&L | (c)-E4W ceiling | left on table |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 08-05 | YXT | 12:07 | halt | 14.00 | +130% | -17% | 0 | 24 | 14 | 6 | 4 | 3 | -14 | -58 | -44 |
| 08-05 | BJDX | 12:27 | halt | 1.60 | +6% | -23% | 0 | 0 | 0 | 5 | 1 | 2 | -63 | -17 | +45 |
| 08-05 | INLF | 13:03 | halt | 6.81 | +8% | -15% | 0 | 2 | 0 | 1 | 0 | 0 | +0 | -14 | -14 |
| 08-05 | ASTC | 13:37 | halt | 10.43 | +23% | -18% | 0 | 2 | 0 | 1 | 0 | 0 | +0 | -28 | -28 |
| 08-05 | VRM | 14:28 | halt | 10.15 | +0% | -14% | 0 | 2 | 5 | 1 | 1 | 0 | +0 | -16 | -16 |
| 08-06 | WYHG | 09:30 | fresh_highs | 8.26 | +217% | -7% | 1 | 27 | 25 | 8 | 1 | 6 | +98 | +224 | +126 |
| 08-06 | PAVS | 09:30 | fresh_highs | 9.30 | +4% | -35% | 0 | 3 | 1 | 1 | 0 | 1 | -31 | -54 | -23 |
| 08-06 | CLRO | 09:30 | fresh_highs | 11.69 | +7% | -30% | 0 | 7 | 0 | 1 | 1 | 1 | +5 | -32 | -37 |
| 08-06 | CELZ | 09:30 | fresh_highs | 1.14 | +54% | -11% | 0 | 12 | 3 | 17 | 15 | 2 | +26 | -21 | -47 |
| 08-06 | MGRX | 09:30 | fresh_highs | 0.59 | +6% | -18% | 0 | 0 | 0 | 1 | 0 | 1 | -30 | -14 | +16 |
| 08-06 | FVN | 09:30 | fresh_highs | 14.22 | +20% | -40% | 0 | 12 | 27 | 2 | 1 | 1 | -6 | -9 | -3 |
| 08-06 | ENSC | 09:30 | fresh_highs | 0.63 | +55% | -27% | 0 | 11 | 1 | 4 | 2 | 2 | -1 | +145 | +146 |
| 08-06 | SUGP | 09:57 | halt | 2.05 | +32% | -21% | 0 | 9 | 9 | 4 | 3 | 1 | -30 | -38 | -8 |
| 08-06 | AZI | 10:06 | fresh_highs | 1.80 | +43% | -27% | 0 | 8 | 1 | 3 | 2 | 1 | -6 | -25 | -19 |
| 08-06 | GAUZ | 10:40 | halt | 0.84 | +15% | -51% | 2 | 19 | 2 | 10 | 11 | 0 | +0 | -66 | -66 |
| 08-06 | PN | 10:47 | fresh_highs | 9.99 | +54% | -33% | 0 | 20 | 1 | 10 | 11 | 2 | -1 | -40 | -39 |
| 08-06 | BYAH | 11:30 | fresh_highs | 3.25 | +104% | -16% | 1 | 14 | 0 | 3 | 2 | 0 | +0 | -37 | -37 |
| 08-06 | WLDS | 13:50 | halt | 4.53 | +4% | -20% | 0 | 1 | 0 | 2 | 1 | 0 | +0 | -24 | -24 |
| 08-06 | XHLD | 15:16 | halt | 2.80 | +94% | -10% | 1 | 6 | 2 | 3 | 3 | 0 | +0 | -64 | -64 |
| 08-07 | NAMI | 09:30 | fresh_highs | 9.11 | +4% | -57% | 0 | 3 | 0 | 1 | 2 | 0 | +0 | -30 | -30 |
| 08-07 | DSY | 09:30 | fresh_highs | 6.03 | +3% | -28% | 0 | 2 | 0 | 2 | 0 | 2 | -27 | -21 | +6 |
| 08-07 | CLRO | 09:30 | fresh_highs | 10.67 | +8% | -15% | 0 | 1 | 0 | 1 | 1 | 0 | +0 | -20 | -20 |
| 08-07 | MB | 09:30 | fresh_highs | 14.30 | +38% | -50% | 0 | 22 | 14 | 7 | 1 | 3 | -31 | +21 | +51 |
| 08-07 | VATE | 09:30 | fresh_highs | 11.04 | +27% | -9% | 0 | 4 | 0 | 15 | 13 | 2 | +15 | -14 | -28 |
| 08-07 | CELZ | 09:36 | fresh_highs | 1.86 | +1% | -31% | 0 | 1 | 0 | 12 | 4 | 5 | +23 | -28 | -51 |
| 08-07 | YJ | 10:18 | fresh_highs | 3.27 | +327% | -14% | 4 | 30 | 12 | 4 | 3 | 1 | -5 | +145 | +149 |
| 08-07 | ATGL | 11:24 | halt | 18.04 | +50% | -57% | 0 | 8 | 19 | 0 | 0 | 0 | +0 | -68 | -68 |
| 08-07 | VSA | 12:27 | halt | 6.00 | +33% | -46% | 0 | 5 | 6 | 0 | 0 | 0 | +0 | -51 | -51 |
| 08-07 | HUIZ | 12:54 | fresh_highs | 2.40 | +22% | -47% | 3 | 23 | 7 | 22 | 13 | 6 | +343 | -20 | -363 |
| 08-07 | CGTL | 12:59 | fresh_highs | 6.25 | +1% | -45% | 0 | 5 | 4 | 0 | 0 | 0 | +0 | -57 | -57 |
| 08-07 | WAFU | 13:05 | fresh_highs | 1.99 | +54% | -39% | 0 | 9 | 2 | 0 | 0 | 0 | +0 | +142 | +142 |
| 08-07 | WFF | 13:36 | halt | 3.74 | +182% | -54% | 5 | 24 | 11 | 17 | 12 | 3 | +183 | +18 | -165 |
| 08-07 | LZMH | 14:25 | halt | 1.95 | +7% | -48% | 0 | 8 | 2 | 1 | 1 | 0 | +0 | -106 | -106 |
| 08-07 | MSC | 14:48 | halt | 2.85 | +6% | -45% | 0 | 5 | 3 | 1 | 1 | 0 | +0 | -46 | -46 |
| 08-10 | JWEL | 09:30 | fresh_highs | 3.97 | +30% | -26% | 0 | 10 | 0 | 0 | 0 | 0 | +0 | -36 | -36 |
| 08-10 | HUDI | 09:30 | fresh_highs | 1.05 | +7% | -22% | 0 | 1 | 0 | 4 | 2 | 0 | +0 | -21 | -21 |
| 08-10 | DKI | 09:30 | fresh_highs | 5.19 | +3% | -25% | 0 | 0 | 3 | 0 | 0 | 0 | +0 | -18 | -18 |
| 08-10 | YMT | 09:30 | fresh_highs | 0.28 | +8% | -12% | 0 | 2 | 0 | 0 | 0 | 0 | +0 | -27 | -27 |
| 08-10 | XHLD | 09:30 | fresh_highs | 2.95 | +59% | -11% | 1 | 12 | 1 | 9 | 2 | 5 | +25 | -28 | -53 |
| 08-10 | AUUD | 09:30 | fresh_highs | 1.43 | +8% | -25% | 0 | 3 | 0 | 2 | 2 | 0 | +0 | -31 | -31 |
| 08-10 | SCKT | 09:32 | halt | 2.69 | +4% | -49% | 0 | 29 | 24 | 4 | 2 | 0 | +0 | -82 | -82 |
| 08-10 | ZJYL | 09:34 | fresh_highs | 3.33 | +12% | -19% | 0 | 1 | 0 | 2 | 1 | 1 | +11 | -21 | -33 |
| 08-10 | VIVK | 09:42 | fresh_highs | 1.75 | +10% | -19% | 0 | 2 | 0 | 2 | 1 | 0 | +0 | -20 | -20 |
| 08-10 | AEHL | 09:57 | halt | 8.11 | +10% | -38% | 0 | 5 | 16 | 5 | 1 | 0 | +0 | -55 | -55 |
| 08-10 | PCLA | 10:17 | fresh_highs | 11.73 | +67% | -36% | 1 | 10 | 5 | 3 | 1 | 1 | -2 | -9 | -7 |
| 08-10 | LZMH | 10:25 | halt | 1.72 | +9% | -38% | 0 | 11 | 8 | 0 | 1 | 0 | +0 | -66 | -66 |
| 08-10 | TNON | 10:45 | fresh_highs | 5.67 | +26% | -19% | 0 | 6 | 24 | 3 | 3 | 0 | +0 | -12 | -12 |
| 08-10 | WYHG | 11:09 | halt | 9.24 | +37% | -40% | 0 | 8 | 11 | 1 | 1 | 0 | +0 | +27 | +27 |
| 08-10 | THH | 11:38 | halt | 2.54 | +96% | -1% | 2 | 6 | 19 | 5 | 0 | 2 | -2 | +157 | +159 |
| 08-11 | WYHG | 09:30 | fresh_highs | 8.03 | +17% | -23% | 0 | 3 | 2 | 2 | 2 | 0 | +0 | -24 | -24 |
| 08-11 | WXM | 09:30 | fresh_highs | 10.72 | +19% | -32% | 0 | 9 | 4 | 10 | 5 | 3 | -24 | -35 | -11 |
| 08-11 | MGIH | 09:30 | fresh_highs | 1.56 | +10% | -9% | 0 | 0 | 9 | 0 | 0 | 0 | +0 | +30 | +30 |
| 08-11 | PLAG | 09:30 | fresh_highs | 1.07 | +536% | -4% | 0 | 24 | 28 | 10 | 2 | 8 | +23 | -21 | -43 |
| 08-11 | FRTT | 09:30 | fresh_highs | 1.43 | +16% | -13% | 0 | 3 | 0 | 5 | 0 | 0 | +0 | -23 | -23 |
| 08-11 | GLE | 09:30 | fresh_highs | 0.67 | +16% | -36% | 0 | 2 | 0 | 0 | 0 | 0 | +0 | -40 | -40 |
| 08-11 | MSGY | 09:38 | fresh_highs | 2.74 | +115% | +0% | 3 | 22 | 2 | 20 | 12 | 6 | +22 | -51 | -73 |
| 08-11 | QMCO | 09:41 | fresh_highs | 16.70 | +17% | -6% | 0 | 0 | 0 | 0 | 0 | 0 | +0 | +97 | +97 |
| 08-11 | ELPW | 09:49 | halt | 4.77 | +8% | -12% | 0 | 1 | 2 | 2 | 0 | 2 | +44 | -13 | -58 |
| 08-11 | GRI | 10:24 | fresh_highs | 2.38 | +7% | -27% | 0 | 2 | 0 | 12 | 4 | 0 | +0 | -42 | -42 |
| 08-11 | HXHX | 15:08 | halt | 0.45 | +27% | -0% | 1 | 1 | 1 | 0 | 0 | 0 | +0 | -18 | -18 |
| 08-11 | AIFA | 15:27 | fresh_highs | 3.02 | +14% | -4% | 0 | 2 | 0 | 0 | 0 | 0 | +0 | +3 | +3 |
| 08-12 | BOXL | 09:30 | fresh_highs | 4.57 | +117% | -6% | 0 | 14 | 0 | 10 | 10 | 1 | +34 | -19 | -53 |
| 08-12 | OFAL | 09:30 | fresh_highs | 2.54 | +49% | -47% | 0 | 8 | 22 | 2 | 0 | 2 | +31 | -19 | -50 |
| 08-12 | RMCF | 09:30 | fresh_highs | 1.74 | +24% | -30% | 0 | 8 | 8 | 26 | 26 | 0 | +0 | -31 | -31 |
| 08-12 | BAOS | 09:30 | fresh_highs | 1.09 | +12% | -42% | 0 | 2 | 0 | 0 | 0 | 0 | +0 | -29 | -29 |
| 08-12 | VBIO | 09:47 | halt | 1.17 | +11% | -83% | 1 | 16 | 8 | 0 | 0 | 0 | +0 | -104 | -104 |
| 08-12 | DOGZ | 09:50 | fresh_highs | 1.31 | +8% | -13% | 0 | 0 | 0 | 2 | 2 | 0 | +0 | -24 | -24 |
| 08-12 | BIVI | 10:00 | fresh_highs | 2.91 | +30% | -55% | 1 | 14 | 2 | 1 | 1 | 0 | +0 | -1 | -1 |
| 08-12 | BQ | 10:50 | fresh_highs | 1.36 | +54% | -15% | 0 | 15 | 3 | 12 | 1 | 10 | +165 | +57 | -109 |
| 08-12 | HXHX | 10:56 | fresh_highs | 0.72 | +4% | -32% | 0 | 2 | 0 | 2 | 1 | 0 | +0 | -46 | -46 |
| 08-12 | SCKT | 11:24 | fresh_highs | 1.98 | +10% | -22% | 0 | 1 | 0 | 5 | 5 | 0 | +0 | -28 | -28 |
| 08-12 | WCT | 11:31 | fresh_highs | 1.35 | +36% | -37% | 0 | 8 | 2 | 2 | 1 | 0 | +0 | -78 | -78 |
| 08-12 | BANL | 13:20 | fresh_highs | 7.20 | +4% | -31% | 0 | 6 | 5 | 6 | 4 | 0 | +0 | -48 | -48 |
| 08-13 | IVDA | 09:30 | fresh_highs | 0.47 | +26% | -6% | 0 | 4 | 0 | 0 | 0 | 0 | +0 | -15 | -15 |
| 08-13 | FGI | 09:30 | fresh_highs | 8.47 | +135% | -17% | 0 | 26 | 8 | 53 | 40 | 9 | +158 | -27 | -185 |
| 08-13 | OFAL | 09:30 | fresh_highs | 1.77 | +5% | -15% | 0 | 2 | 0 | 3 | 2 | 1 | +14 | -21 | -35 |
| 08-13 | YXT | 09:30 | fresh_highs | 5.27 | +8% | -17% | 0 | 2 | 0 | 3 | 3 | 0 | +0 | -14 | -14 |
| 08-13 | DFSC | 09:30 | fresh_highs | 2.58 | +38% | -19% | 1 | 13 | 3 | 27 | 23 | 3 | +17 | +7 | -10 |
| 08-13 | BNRG | 09:32 | halt | 3.20 | +15% | -11% | 0 | 0 | 21 | 14 | 12 | 0 | +0 | -15 | -15 |
| 08-13 | XHG | 09:37 | halt | 6.00 | +1% | -47% | 2 | 15 | 2 | 2 | 1 | 0 | +0 | -68 | -68 |
| 08-13 | PSQH | 10:20 | halt | 5.00 | +14% | -22% | 1 | 2 | 3 | 7 | 0 | 1 | -1 | -35 | -34 |
| 08-13 | HCTI | 11:22 | fresh_highs | 2.00 | +15% | -29% | 0 | 1 | 0 | 31 | 30 | 2 | +8 | -22 | -31 |
| 08-13 | INHD | 14:42 | fresh_highs | 11.33 | +30% | -4% | 0 | 6 | 4 | 3 | 1 | 1 | +2 | -38 | -40 |
| 08-14 | WETO | 09:30 | fresh_highs | 10.65 | +22% | -32% | 0 | 11 | 4 | 11 | 9 | 1 | +13 | -30 | -43 |
| 08-14 | LBGJ | 09:30 | fresh_highs | 3.71 | +10% | -23% | 0 | 1 | 1 | 1 | 0 | 1 | +15 | -17 | -32 |
| 08-14 | CGTL | 09:30 | fresh_highs | 5.03 | +8% | -18% | 0 | 2 | 1 | 3 | 0 | 0 | +0 | -35 | -35 |
| 08-14 | HHS | 09:58 | fresh_highs | 4.32 | +4% | -2% | 0 | 0 | 0 | 6 | 8 | 0 | +0 | -10 | -10 |
| 08-14 | ONFO | 09:59 | fresh_highs | 3.69 | +65% | -31% | 0 | 14 | 0 | 11 | 11 | 0 | +0 | +185 | +185 |
| 08-14 | MF | 09:59 | halt | 14.78 | +33% | -24% | 0 | 7 | 2 | 15 | 9 | 3 | -29 | -21 | +8 |
| 08-14 | AKAN | 10:01 | fresh_highs | 7.66 | +8% | -19% | 0 | 0 | 0 | 1 | 0 | 1 | -30 | -16 | +14 |
| 08-14 | HAO | 10:10 | fresh_highs | 3.63 | +15% | -6% | 0 | 2 | 4 | 17 | 11 | 1 | -32 | -15 | +17 |
| 08-14 | AEHL | 10:27 | fresh_highs | 7.28 | +4% | -42% | 0 | 2 | 18 | 1 | 0 | 0 | +0 | -32 | -32 |
| 08-14 | BANL | 10:48 | fresh_highs | 12.00 | +1% | -30% | 0 | 3 | 8 | 15 | 11 | 0 | +0 | -19 | -19 |
| 08-14 | LFS | 11:13 | fresh_highs | 3.20 | +29% | -28% | 0 | 5 | 0 | 4 | 4 | 0 | +0 | -13 | -13 |
| 08-14 | GIPR | 12:25 | halt | 1.15 | +10% | -63% | 0 | 9 | 1 | 1 | 0 | 1 | -38 | -53 | -15 |
| 08-14 | STKH | 12:47 | fresh_highs | 4.80 | +9% | -34% | 0 | 0 | 0 | 0 | 0 | 0 | +0 | -27 | -27 |
| 08-14 | SXTC | 14:27 | fresh_highs | 4.64 | +4% | -15% | 0 | 0 | 0 | 0 | 0 | 0 | +0 | -25 | -25 |

## Scorecards (all entries x exits, $500 clip)

| entry/exit | N | total | $/trade | win% | HR>=$250 | premium (sum of HR) | best | worst | maxDD | 8/5-8/10 | 8/11-8/14 | clears bar? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a/E3 | 538 | -5808 | -10.8 | 29 | 0 | +0 | +177 | -221 | -5808 | -2958 | -2850 | no |
| a/E4 | 538 | -5766 | -10.7 | 21 | 1 | +304 | +304 | -123 | -5766 | -2742 | -3025 | no |
| a/E4W | 538 | -5129 | -9.5 | 20 | 5 | +2225 | +891 | -123 | -5129 | -3256 | -1872 | no |
| a/STRUCT | 538 | -6397 | -11.9 | 21 | 2 | +596 | +305 | -166 | -6397 | -3009 | -3388 | no |
| b/E3 | 571 | -6417 | -11.2 | 23 | 0 | +0 | +164 | -106 | -6417 | -3011 | -3406 | no |
| b/E4 | 571 | -6840 | -12.0 | 16 | 1 | +279 | +279 | -92 | -6840 | -2859 | -3981 | no |
| b/E4W | 571 | -6817 | -11.9 | 12 | 6 | +2360 | +563 | -106 | -6817 | -3025 | -3792 | no |
| b/STRUCT | 571 | -8149 | -14.3 | 16 | 2 | +739 | +382 | -106 | -8149 | -4002 | -4147 | no |
| c/E3 | 97 | -1326 | -13.7 | 24 | 0 | +0 | +164 | -106 | -1326 | -711 | -615 | no |
| c/E4 | 97 | -1119 | -11.5 | 20 | 1 | +279 | +279 | -92 | -1119 | -389 | -730 | no |
| c/E4W | 97 | -1449 | -14.9 | 14 | 0 | +0 | +224 | -106 | -1449 | -564 | -885 | no |
| c/STRUCT | 97 | -1609 | -16.6 | 18 | 0 | +0 | +195 | -106 | -1609 | -866 | -743 | no |

### Equity curves (cumulative $ by day)

| entry/exit | 08-05 | 08-06 | 08-07 | 08-10 | 08-11 | 08-12 | 08-13 | 08-14 |
|---|---|---|---|---|---|---|---|---|
| a/E3 | -508 | -1016 | -2540 | -2958 | -3497 | -4893 | -5304 | -5808 |
| a/E4 | -666 | -842 | -2193 | -2742 | -3168 | -4531 | -4817 | -5766 |
| a/E4W | -542 | -722 | -2428 | -3256 | -2782 | -4426 | -4307 | -5129 |
| a/STRUCT | -464 | -704 | -2187 | -3009 | -3647 | -4616 | -5686 | -6397 |
| b/E3 | -644 | -1461 | -2533 | -3011 | -3637 | -5202 | -5664 | -6417 |
| b/E4 | -677 | -1352 | -2556 | -2859 | -3683 | -5353 | -5925 | -6840 |
| b/E4W | -677 | -985 | -2040 | -3025 | -4236 | -6361 | -6309 | -6817 |
| b/STRUCT | -529 | -1512 | -2625 | -4002 | -4886 | -6571 | -7198 | -8149 |
| c/E3 | -133 | -364 | -514 | -711 | -720 | -938 | -1164 | -1326 |
| c/E4 | -133 | -347 | -385 | -389 | -455 | -678 | -926 | -1119 |
| c/E4W | -133 | -188 | -323 | -564 | -701 | -1074 | -1321 | -1449 |
| c/STRUCT | -114 | -152 | -468 | -866 | -1007 | -1269 | -1460 | -1609 |

## Tick-read enrichment (legs>=25% vs quiet contrast windows; last 30s before the trough bar)

| feature | leg median (n) | push median | contrast median (n) | AUC leg vs contrast | frac legs beyond contrast median |
|---|---|---|---|---|---|
| aggressor imbalance last30s (buy-sell)/tot | 0.4934 (8) | -0.0603 | -0.003262 (521) | 0.72 | 0.88 |
| tick-rate accel (last30 / prior60 rate) | 2.572 (8) | 1.125 | 0.88 (553) | 0.79 | 0.88 |
| prints in last 30s | 0 (31) | 143 | 19 (606) | 0.22 | 0.23 |
| spread last30 (rel, lower=tighter) | 0.00731 (8) | 0.0075 | 0.007509 (538) | 0.46 | 0.62 |
| bid-size share last30 (bid/(bid+ask)) | 0.4683 (8) | 0.5139 | 0.5035 (538) | 0.47 | 0.25 |
| seconds since last print | 295.2 (31) | 0.2494 | 2.214 (606) | 0.26 | 0.23 |
| micro higher-lows share (5s lows rising) | 0.6667 (7) | 0.4 | 0.4 (443) | 0.75 | 0.86 |
| 30s range (hi/lo-1) | 0.08976 (8) | 0.0446 | 0.01217 (521) | 0.93 | 0.88 |

Deltas last30 vs prior60 (leg median, contrast median): {'aggr delta': (0.111, 0.0), 'spread delta': (-0.0002, 0.0), 'bidshare delta': (-0.0171, 0.0065)}
Entry (a) thresholds derived from legs: aggr30 >= 0.493 rate_accel >= 2.57

## Three tick-level hand-traces (biggest post-crown legs with a readable tape)

Columns: 5s bucket, prints, volume, last, low–high, buy-vol (at/above ask), sell-vol (at/below bid), NBBO at
bucket end. Buy/sell classification AFTER the trough (T+10 onward) uses the last quote in the pulled window and
is stale — read those rows for price/prints only.

**BYAH 8/6, crown 11:30 (fresh_highs at $3.25), leg 12:12:40 → 3.36→3.80 in 45s (+13%, then +39% within 5 min).**
Pre-leg tape: 90s of 1 print per 5s (100–300 shares) at 3.35–3.38, bid 3.32→3.36 (bid steps up 12:12:00 with 400
shown — the only "step-in" tell, 25s early), ask 3.38–3.40 with 500–700. At 12:12:25 27 prints/8,335 shares lift
3.40→3.50 and the ask jumps to 3.50 with 1,300, then 3.55/1,000, 3.70/1,100, and 12:12:40 ask size collapses to
100. Read: one bid uptick, then the burst. Aggressor imbalance +0.98 in the last 30s but almost all of it is the
burst itself.

**XHG 8/13, crown 09:37 (halt at $6.00), leg 13:02:30 → 3.56→4.88 within 5 min (+37%).**
Pre-leg tape is BUSY, not quiet: 20–70 prints per 5s from 13:01:30, a 24k-share lift 3.42→3.54 at 13:01:50 with
ask 3.55/500, then two-sided churn 3.47–3.57 with a 4,700 bid at 3.52 (13:02:05) and 6,400 at 3.56 (13:02:35).
The big bid sitting under price is the "finds a buyer" picture; the leg fires 60s later. Aggressor +0.60 vs prior
+0.56 — no acceleration; bid-share 0.67 (bid heavier than ask) is the strongest single value in the whole leg
set. Trigger latency: bid appears 13:02:05, leg 13:03+.

**HUIZ 8/7, crown 12:54 (fresh_highs at $2.40), leg 14:42:50 — halt-resumption flush.** Prints resume 14:42:30
after a 5-min halt: 215 prints/125k shares in 5s at 2.11–2.21, rip to 2.42 in the next 5s, then a 45-second
FLUSH to 1.69 (−30%) on 30k sold at the bid per 5s, then 84k lifted at 1.69–1.87 in one 5s bucket and back to
2.20 by 14:43:25. This is Kev's flush-entry picture at 5s resolution (the ask went 10,400→14,300 shown at 1.69
= the wall got eaten from below). No pre-read exists — the halt hides everything before the reopen, and the
whole round trip is 60s. Hidden Entry Architect: this is a v2 specimen, not a crown-lane specimen.

## Caveats

- 8-day sample, one crown regime (meritocracy live 8/5). Rockets counted from crown price to session high are
  OFFERED not capturable.
- Halt detection = ≥240s print gap on SIP; halt_suspect rows from the archive were not merged (460 detected).
- Day gain uses Alpaca prior daily close (SIP raw). VWAP = RTH-anchored from 10s bars (live ~vwap is premarket-
  anchored).
- Entry (a) thresholds were fitted on the same 8 legs it was then graded on (in-sample and STILL negative).
- The "ceiling" is a specific $500 hold-a-core with E4W; a perfect-foresight ceiling would be much larger, but that
  is not an entry.
