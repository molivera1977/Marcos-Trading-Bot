# OPEN-HOLES SWEEP #1 — 8/16 (analysis only, no behavior change)

Marcos: "well start the process now" — three standing holes graded on the full 62-date universe
(data/universe/bars10s, 729 files, 2026-05-18..2026-08-14) under LIVE-PARITY E3 via the unchanged
engine chain (`flatten_parity_20260816.py` -> S -> G -> F -> C -> B -> E): +1% chase fill, 0.5%
market slip on exits, $500 clip, bank 1/2 at +10%, 10%-off-high trail after the bank, halt-gap
rule, no new entries >=15:30 ET, flatten 15:45 ET. Same PASS bar as the O-config runs (day mean AND
median > $50, green >=55%, both halves > 0, worst day > -$300; solo/dedup, no slot capacity).
Script: `open_holes_sweep1_20260816.py`; raw run: `_run.txt`; JSON: `_out.json`. All dollars through
the real $500 clip x 1.01 chase; one named trade traced per hole.

## VERDICTS

| hole | verdict | headline |
|---|---|---|
| A  day-2/3 continuation | **REDUNDANT** (repeat names already inside BA/grinder's field; no separate reload lane earned) | repeat name-days = 124/729 (17.0%). Break-attack on repeats: N=108, 64% win, **+$29.07/tr** vs day-1 +$26.05/tr (SE $6.5 vs $3.0 — indistinguishable). Grinder on repeats: N=35, +$37.32/tr vs +$27.03 (SE $11.6, noise). "Kev reload" first-pullback entry: 595 trades, 38% win, +$9.73/tr, worst day -$314.64 -> FAILS the bar (worst-day clause); on repeat names it is weaker (+$7.47/tr, active-day green 44%). |
| B  seam H2 micro-pullback (10s form) | **REFUTED at 10s resolution** (5s form = NEEDS-DATA) | 299 name-days fire; 19% win, **-$1,003.12** total, -$3.35/tr, 240/299 stopped, halves -$201/-$802, green 32%. Zero overlap with break-attack because BA cannot fire before ~9:42 (needs 4 completed 3-min bars): the seam is not redundant, it simply loses. 5s bars are not in the cache — the sub-10s seam stays ungraded. |
| C  ex-hidden v1 entries under E3 | **REFUTED — an ENTRY verdict, not an exit verdict** | v1's exact trigger fires 19,207 times on 445 name-days. Under E3: in-window 9:30-10:30 N=875 **-$3,827.18** (37% win); all-day dedup N=4,584 -$24,212.93; live-ish (ext gate 3-10% + name cap 2) N=456 -$3,550.21; first-fire-per-name-day N=435 -$2,327.90. Every variant negative in BOTH halves. |

## HOLE A — day-2/3 continuation (Kev reload playbook)

Census (manifest.json; "prior" = the 1-3 preceding trading days present in the manifest): 124 of 729
name-days (17.0%) are repeats; depth 1 prior day = 105, 2 = 18, 3 = 1. Full list in `_run.txt`.

Reload detector used (the simpler pick, as briefed): 9:30-10:30 ET, >=5% push from the RTH open, then
>=3% dip from the run high, first 10s bar with a higher low that closes above VWAP -> enter at close,
stop = dip low, one fire per name-day.

Solo, dedup, live parity, 62-date denominator. The 62-date day-median for the REPEAT cohort is a
denominator artifact (a 17% cohort is absent most days), so ACTIVE-DAY rows are given too:

## Lanes split day-1 vs repeat (solo, dedup, live parity, 62 dates)
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
  reload day1: N=487 win 39% mean/tr $+10.24 total $+4984.91 best $+584.23 worst $-101.78
  reload repeat: N=108 win 37% mean/tr $+7.47 total $+806.97 best $+193.15 worst $-58.93
  reload day1 ACTIVE-DAYS: 62 days, day mean $+80.40 median $+71.34 green 61%; per-trade mean SE $3.08
  reload repeat ACTIVE-DAYS: 48 days, day mean $+16.81 median $-5.61 green 44%; per-trade mean SE $5.12
  break-attack 9:30-10:30 day1: N=524 win 62% mean/tr $+26.05 total $+13650.02 best $+500.96 worst $-71.99
  break-attack 9:30-10:30 repeat: N=108 win 64% mean/tr $+29.07 total $+3139.16 best $+221.28 worst $-69.91
  break-attack 9:30-10:30 day1 ACTIVE-DAYS: 62 days, day mean $+220.16 median $+211.30 green 85%; per-trade mean SE $2.98
  break-attack 9:30-10:30 repeat ACTIVE-DAYS: 42 days, day mean $+74.74 median $+76.00 green 71%; per-trade mean SE $6.53
  grinder1030 day1: N=338 win 59% mean/tr $+27.03 total $+9136.02 best $+377.19 worst $-59.55
  grinder1030 repeat: N=35 win 57% mean/tr $+37.32 total $+1306.10 best $+163.75 worst $-59.24
  grinder1030 day1 ACTIVE-DAYS: 57 days, day mean $+160.28 median $+98.13 green 81%; per-trade mean SE $2.95
  grinder1030 repeat ACTIVE-DAYS: 13 days, day mean $+100.47 median $+82.15 green 85%; per-trade mean SE $11.58

Reading: (a) the reload entry is a weak lane everywhere (38% win, +$9.73/tr) and weaker on repeats;
(b) break-attack is NOT worse on repeats (+$29.07 vs +$26.05 per trade; repeat halves +$1,986/+$1,153,
active-day green 71%); (c) grinder is nominally better on repeats (+$37.32/tr) but N=35, SE $11.6 = noise.
Day-2 names are already caught by the champion's own detectors; nothing here earns a dedicated lane or a
day-2 boost/penalty. Repeat per-trade lists: `_out.json` A.lanes.*.trades_repeat.

## Hand-trace A: PCLA 2026-06-26 reload entry-bar 13:37:00Z sig 3.1500 stop 3.0900 repeat=False prior=[] -> $+584.23 trail@16:02:30
   RTH open 3.0100; fill = sig x1.01 = 3.1815; shares 157.2
   13:50:10 BANK 0.50 at +10% (3.4996)
   16:02:30 TRAIL[off10] close 10.3500 fill 10.2982
(PCLA is a day-1 name — the largest reload trade overall; the largest REPEAT reload trade is +$193.15.)

## HOLE B — seam H2 micro-pullback (task #38)

Resolution limit: the 5s program is graded here on **10s bars** (5s not in the cache); a >=4% single-10s-bar
surge is coarser than the 5s seam and sub-10s pullbacks are invisible. Detector: 9:30-9:40 ET, a 10s bar
closing >=4% above the prior close, then within the next 3 bars the first bar with a higher low -> enter at
that close, stop = that low; one fire per name-day; E3 exits.

signals: seam 299 name-days; break-attack 9:30-9:40 0
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|
seam stop width %: median 1.95 min 0.00 max 18.84; win 19%; per-trade mean $-3.35
overlap: seam name-days 299, BA name-days 0, both 0
  seam-only name-days: N=299 $-1003.12
seam exits: {'stop': 240, 'trail': 54, 'eod1545': 3, 'haltgap': 2}

Comparison to break-attack in the same window: BA has ZERO fires 9:30-9:40 (needs four completed 3-min
bars), so overlap is structurally 0 — the seam would be a distinct, earlier lane, and that lane loses:
80% of entries stop out (median stop width 1.95%, so E3's +10% bank sits ~5R away and is rarely reached
before the stop). Adding seam-only trades on top of BA is strictly additive-negative (-$1,003.12).

## Hand-trace B: ZCMD 2026-07-22 surge bar 13:30:20Z 2.1700->2.3000 (+6.0%), entry bar 13:30:30Z low 2.2600 > prev low 2.1600, sig 2.3800 fill 2.4038 -> $+377.78 trail@14:27:00
   13:31:00 BANK 0.50 at +10% (2.6442)
   14:27:00 TRAIL[off10] close 5.8250 fill 5.7959
(ZCMD is the best case; the lane is 240 stops against 54 trails.)

## HOLE C — ex-hidden v1 entries re-graded under E3

Trigger read this run at `marcos_trading_bot.py:5662` (hidden_entry_step) and ported exactly: ARM when
trailing 30-bar (5-min) close velocity >= 25% (stays armed); FIRE when bar low <= anchor=max(10s-EMA90,
VWAP), close >= anchor and >= VWAP, close in the top half of the range, body > -0.5%; anchor-maturity gate
nbars >= 90; stop = min(low-0.01, close x 0.95). Fed the FULL-day 10s bars (premarket-anchored VWAP, EMA
warmed from the first bar = the live deep pass); only RTH fires graded (PRE is its own book). Not modeled:
crown bypasses, daily cap 3/5, stale-fire guard (all only reduce N).

raw RTH fires: 19207 across 445 name-days
| cohort | N | win | total | mean/tr | day mean | day median | worst day |
|---|---|---|---|---|---|---|---|

by window (all fires, dedup):
  09:30-10:30: N=875 total $-3827.18 mean $-4.37 win 37%
  10:30-12:00: N=1241 total $+125.87 mean $+0.10 win 38%
  12:00-13:00: N=705 total $-3811.00 mean $-5.41 win 34%
  13:00-15:00: N=1402 total $-12592.58 mean $-8.98 win 29%
  15:00-16:00: N=361 total $-4108.04 mean $-11.38 win 27%
exits (all-day dedup): {'trail': 1197, 'stop': 2863, 'eod1545': 516, 'haltgap': 8}

Plain statement: under E3 exits (the same exits that carry BA +$16,789 and grinder +$10,442 on this
universe), hidden v1's entries lose in every window, every gate variant, both halves. The F-control
(-$4,012 under v1's own exits) and this re-grade (-$3,827 in-window under E3) agree: **"hidden is dead"
was an ENTRY verdict.** The 10:30-12:00 slice is merely flat (+$0.10/tr) — no rescue there. v2 (flush ->
higher-low + close > prior high) is a different trigger and is unaffected by this finding.

## Hand-trace C: NPT 2026-06-08 hidden fire 17:43:20Z bar o 3.0500 h 3.1300 l 3.0100 c 3.1200 ext_vwap +2.81% stop 2.9640 (5.0% risk) fill 3.1512 -> $+407.29 trail@18:11:50
   17:46:20 BANK 0.50 at +10% (3.4663)
   18:11:50 TRAIL[off10] close 8.0100 fill 7.9699
(NPT is the best single fire — 13:43 ET, outside the window, on a name that then tripled; the lane's
median trade is a stop.)

## Officers touched
Wind Tunnel (chain reused unchanged, live-parity mode), Statistician (numbers ledgered here + JSON),
Hidden Entry Architect (Hole C closes v1's entry-vs-exit question; v2 shadow unaffected), Seam Scientist
(Hole B: 10s form refuted; 5s form NEEDS-DATA), Forward Architect / Handicapper (Hole A: repeat status is
not a selection edge either way), Side Marshal (clean — side not stamped in this study), Blast Radius
Auditor (clean — analysis only, no live path touched), Cartographer (clean).
