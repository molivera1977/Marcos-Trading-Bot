# CATALYST PROBE 8/16 — Alpaca News access, small-cap coverage, point-in-time catalyst kill-test
Sunday agenda item 8 (Marcos: "querying the tickers on our scanner for big catalysts"). READ-ONLY; no bot edits.
Script: `data/killtests/catalyst_probe_20260816.py` (raw output `catalyst_probe_20260816_raw.md`, news cache
`catalyst_probe_20260816_news_cache.json` — 437 name-days, 350 requests, JSON `catalyst_probe_20260816.json`).
Permutation check: scratch script, 5,000 shuffles, trade-level AND name-day-level (numbers below).

## TL;DR
1. **Access: WORKS on our plan.** `GET https://data.alpaca.markets/v1beta1/news` -> HTTP 200 with the trading keys.
   Fields: author, content, created_at, headline, id, images, source, summary, symbols, updated_at, url. Source in
   every article seen = `benzinga`. Rate limit header `X-Ratelimit-Limit: 10000` (per minute); 350 requests at
   ~3/s -> 0 x 429. Pagination via `next_page_token`, limit<=50.
2. **Coverage (the small-cap risk): 78% of top-12 runners had ANY headline in the (prior close, day close] window,
   but only 50% had a NON-DIGEST headline and only 36% had a non-digest headline BEFORE 09:30 ET.** Most "coverage"
   is Benzinga's "12 Industrials Stocks Moving In Friday's Pre-Market Session" digests — those are written AFTER the
   move (they are effectively a lagging movers scanner, not a catalyst).
3. **Kill-test: catalyst-presence DISCRIMINATES — INVERTED.** On the live-parity champion chain (36 dates 6/25-8/14,
   15:45 flatten, 15:30 cutoff, E3), trades on names with a point-in-time non-digest headline earn LESS:
   O-config portfolio catalyst **+$6.59/trade (N=45, 53% win)** vs no-catalyst **+$49.05/trade (N=109, 78% win)**;
   BA solo -$1.45 vs +$37.62; grinder solo +$8.47 vs +$28.52. Permutation p (name-day shuffle): BA 0.0000,
   O-config 0.0000, grinder 0.034. "Nothing at all" (no headline of any kind) is the BEST bucket in every lane.
4. **Toxic kind: EARNINGS** (O-config -$9.48/trade N=13; flat_top leg -$18.52 N=11, 27% win) and **HALT headlines**
   (BA solo -$5.63 N=14, 36% win — a pre-signal halt headline = the move already happened). Offerings are NOT
   toxic here (N=4 BA, +$27.86; tiny N, and note the window: only headlines BEFORE the signal count, so an
   offering that drops mid-day after entry is invisible to this stamp).
5. **Recommendation: stamp-only column, DO NOT gate.** Ship `catalyst` (kind, first-headline time, digest-only flag)
   as a scanner column + a `catalyst_kind` stamp on every entry-gate row. No entry rule until >=5 OOS days of
   stamps confirm the inversion. The interesting live hypothesis is the OPPOSITE of the agenda's framing:
   "no-news / halt-already-printed" names are where the champion lanes make their money; a "known catalyst"
   (esp. earnings) is a WEAKNESS flag for BA/flat_top, not a strength flag.

## Probe 1a — access check (XHG,DFSC,MF,WETO,LBGJ, 8/13-8/14): 14 articles
| created_at (UTC) | symbols | source | headline | digest? |
|---|---|---|---|---|
| 2026-08-13T12:04:34Z | XHG | benzinga | XChange TEC Announces Non-Binding Letter Of Intent To Acquire Hong Kong-Based AI |  |
| 2026-08-13T12:10:12Z | DFSC | benzinga | DEFSEC Technologies Q3 EPS $(0.92) Up From $(2.67) YoY, Sales $1.966M Up From $1 |  |
| 2026-08-13T13:44:53Z | CLBT,DFSC,FGI,FGL,LESL,XHG | benzinga | Dow Gains Over 100 Points; Producer Prices Unchanged In July | Y |
| 2026-08-13T13:48:50Z | DFSC | benzinga | DEFSEC Technologies Shares Halted On Circuit Breaker To The Upside, Stock Now Up |  |
| 2026-08-13T13:54:41Z | DFSC | benzinga | DEFSEC Technologies Shares Resume Trade, Then Halted To The Circuit Breaker To T |  |
| 2026-08-13T16:12:24Z | ARX,CLBT,CSCO,DFSC,FGI,LESL… | benzinga | Gold Down 2%; Cisco Shares Tumble After Q4 Results |  |
| 2026-08-13T17:05:55Z | AIRO,ATXG,DFSC,FGI,FGL,KITT… | benzinga | 12 Industrials Stocks Moving In Thursday's Intraday Session | Y |
| 2026-08-13T21:06:05Z | DFSC,GCDT,GPUS,HCAI,IPDN,KULR… | benzinga | 12 Industrials Stocks Moving In Thursday's After-Market Session | Y |
| 2026-08-14T08:37:25Z | AKAN,AMPG,BOXL,BYSI,BZAI,CAPR… | benzinga | Why Eton Pharmaceuticals Shares Are Trading Higher By 22%; Here Are 20 Stocks Mo | Y |
| 2026-08-14T12:06:36Z | CDTG,DFSC,FGL,FRGT,KULR,LBGJ… | benzinga | 12 Industrials Stocks Moving In Friday's Pre-Market Session | Y |
| 2026-08-14T13:40:55Z | CXAI,INV,MDXH,MVIS,STKH,WETO | benzinga | US Stocks Mixed; Retail Sales Fall In July | Y |
| 2026-08-14T17:06:02Z | AEYE,AMPG,AMPGZ,BZAI,CGTL,EXOD… | benzinga | 12 Information Technology Stocks Moving In Friday's Intraday Session | Y |
| 2026-08-14T17:06:03Z | FGI,FGL,GPUS,NPWR,OBAI,OFAL… | benzinga | 12 Industrials Stocks Moving In Friday's Intraday Session | Y |
| 2026-08-14T21:06:02Z | AIXI,AMPGZ,API,CETX,FIEE,GAUZ… | benzinga | 12 Information Technology Stocks Moving In Friday's After-Market Session | Y |

Timestamps vs moves: DFSC's real catalyst (Q3 EPS) printed 12:10Z (08:10 ET) — BEFORE its move; the halt
headlines printed 13:48/13:54Z (09:48/09:54 ET) DURING the move; the "12 Industrials Stocks Moving..." digests
printed 17:06Z/21:06Z AFTER. XHG's LOI headline 12:04Z (08:04 ET) preceded its 8/13 run. WETO/MF/LBGJ had
digest-only coverage on 8/14 (WETO +259% on 511M shares — no non-digest headline at all).

## Probe 1b — coverage census: top-12 by gain x last 10 manifest dates (120 name-days)
window per name-day = (prior business day 20:00Z, day 20:00Z]; digest = "N Stocks Moving..."/market-wrap style OR >5 symbols tagged; pre-open = created_at < 13:30Z
| date | names | any headline | non-digest headline | pre-open non-digest | names w/ ANY |
|---|---|---|---|---|---|
| 2026-08-03 | 12 | 9 | 6 | 5 | HYFM* UPC DFNS EZRA* FUSE SDST FCUV* CNCK* NEXR* |
| 2026-08-04 | 12 | 8 | 8 | 8 | AMIX* TNMG* ADGM* MOVE* PLTU* IBTA* BLZE* NUWE* |
| 2026-08-05 | 12 | 11 | 7 | 3 | YXT ZYBT INLF JLHL ASTC BJDX GTE* OESX* JDZG SHPU APPS* |
| 2026-08-06 | 12 | 11 | 8 | 7 | BYAH* WYHG* XHLD CLRO* ENSC* CELZ* AZI PN* LBGJ PAVS* WLDS |
| 2026-08-07 | 12 | 8 | 4 | 1 | IPW* YJ MB WFF ATGL NAMI WWR LZMH |
| 2026-08-10 | 12 | 8 | 4 | 2 | SCKT* STKH JWEL WYHG XHLD MTEN ARTW AUUD* |
| 2026-08-11 | 12 | 10 | 6 | 6 | PLAG* WXM GLE* FRTT* QMCO* WYHG CIGL STIM* GRI NIQ* |
| 2026-08-12 | 12 | 10 | 6 | 3 | OFAL VBIO BOXL* RMCF BIVI BQ CHOW XHLD NBIG* NBIL* |
| 2026-08-13 | 12 | 10 | 8 | 6 | XHG* FGI* DFSC* BGIN HCTI BYSI GXAI* IVDA* PSQH CURI* |
| 2026-08-14 | 12 | 9 | 3 | 2 | WETO MF GIPR AKAN* DFSC BOXL LBGJ TMS* XHG |
| **TOTAL** | 120 | 94 (78%) | 60 (50%) | 43 (36%) | * = pre-open non-digest |
rate-limit: 121 requests so far, 0 x HTTP 429 (pace 0.34s/req); headers seen: {'X-Ratelimit-Limit': '10000', 'X-Ratelimit-Remaining': '9999', 'X-Ratelimit-Reset': '1786894449'}

**Coverage number: 78% any / 50% non-digest / 36% non-digest pre-open.** For a 09:35 entry the usable
figure is 36% — i.e. ~2 of 3 of our runners have NO real headline the bot could have read before the open.
A catalyst column will be BLANK for most of the board; that is information (see kill-test), not a defect.

## Probe 2 — point-in-time catalyst kill-test
Chain: `flatten_parity_20260816.py` NEW mode (S->G->F->C->B->engine unchanged; 15:45 flatten, 15:30 cutoff, E3).
Reconcile: O-config H4 N=154 +$5,643.21 (= flatten-parity NEW row); BA solo N=384; grinder solo N=231.
Stamp: catalyst=True iff an article tagged with the symbol has created_at <= the SIGNAL bar time (UTC) and
> prior business day 20:00Z, and is not a digest (>5 symbols or movers/market-wrap headline). KIND = first
keyword match on the first non-digest headline (offering > earnings > fda > merger > contract > analyst > halt > crypto_ai > other).
Windows: 36 dates 6/25-8/14; 317 name-days fetched.
### BA in-window (solo)
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 384 | 62% | $+9055.71 | $+23.58 | 36 | $+251.55 | $+237.46 | 29/36 |
| catalyst (non-digest, pt-in-time) | 138 | 45% | $-199.68 | $-1.45 | 33 | $-6.05 | $-29.23 | 12/33 |
| no catalyst | 246 | 71% | $+9255.39 | $+37.62 | 36 | $+257.09 | $+251.95 | 34/36 |
|   digest-only headline (Benzinga movers) | 91 | 70% | $+2805.06 | $+30.82 | 32 | $+87.66 | $+59.39 | 25/32 |
|   nothing at all | 155 | 72% | $+6450.33 | $+41.62 | 36 | $+179.18 | $+146.36 | 32/36 |
| by KIND (first non-digest headline) | | | | | | | | |
|   other | 47 | 43% | $-42.11 | $-0.90 | 21 | $-2.01 | $-0.73 | 10/21 |
|   earnings | 31 | 42% | $-109.38 | $-3.53 | 16 | $-6.84 | $-8.44 | 7/16 |
|   contract | 23 | 52% | $-54.55 | $-2.37 | 14 | $-3.90 | $-3.10 | 6/14 |
|   halt | 14 | 36% | $-78.85 | $-5.63 | 8 | $-9.86 | $-21.80 | 2/8 |
|   merger | 12 | 50% | $-88.19 | $-7.35 | 8 | $-11.02 | $-16.22 | 4/8 |
|   offering | 4 | 75% | $+111.45 | $+27.86 | 2 | $+55.73 | $+55.73 | 2/2 |
|   crypto_ai | 3 | 33% | $-25.88 | $-8.63 | 2 | $-12.94 | $-12.94 | 1/2 |
|   analyst | 2 | 100% | $+216.12 | $+108.06 | 2 | $+108.06 | $+108.06 | 2/2 |
|   fda_clinical | 2 | 0% | $-128.32 | $-64.16 | 2 | $-64.16 | $-64.16 | 0/2 |
verdict-input: catalyst -1.45 vs none +37.62 $/trade (delta -39.07); win 45% vs 71%

### grinder1030 (solo)
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 231 | 56% | $+5345.47 | $+23.14 | 34 | $+157.22 | $+112.55 | 29/34 |
| catalyst (non-digest, pt-in-time) | 62 | 42% | $+524.97 | $+8.47 | 13 | $+40.38 | $+27.30 | 8/13 |
| no catalyst | 169 | 62% | $+4820.50 | $+28.52 | 33 | $+146.08 | $+99.88 | 29/33 |
|   digest-only headline (Benzinga movers) | 36 | 64% | $+612.73 | $+17.02 | 12 | $+51.06 | $+62.49 | 9/12 |
|   nothing at all | 133 | 61% | $+4207.77 | $+31.64 | 30 | $+140.26 | $+103.73 | 25/30 |
| by KIND (first non-digest headline) | | | | | | | | |
|   earnings | 31 | 42% | $+165.94 | $+5.35 | 3 | $+55.31 | $+88.17 | 2/3 |
|   halt | 9 | 22% | $-41.12 | $-4.57 | 2 | $-20.56 | $-20.56 | 1/2 |
|   analyst | 8 | 62% | $+343.13 | $+42.89 | 2 | $+171.57 | $+171.57 | 2/2 |
|   crypto_ai | 7 | 29% | $-27.28 | $-3.90 | 1 | $-27.28 | $-27.28 | 0/1 |
|   other | 4 | 50% | $+10.79 | $+2.70 | 2 | $+5.39 | $+5.39 | 1/2 |
|   contract | 2 | 50% | $+11.38 | $+5.69 | 2 | $+5.69 | $+5.69 | 1/2 |
|   merger | 1 | 100% | $+62.12 | $+62.12 | 1 | $+62.12 | $+62.12 | 1/1 |
verdict-input: catalyst +8.47 vs none +28.52 $/trade (delta -20.06); win 42% vs 62%

### flat_top retest (solo)
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 208 | 37% | $+1217.52 | $+5.85 | 36 | $+33.82 | $+33.84 | 24/36 |
| catalyst (non-digest, pt-in-time) | 74 | 34% | $-32.28 | $-0.44 | 30 | $-1.08 | $-8.32 | 14/30 |
| no catalyst | 134 | 38% | $+1249.80 | $+9.33 | 36 | $+34.72 | $+29.12 | 21/36 |
|   digest-only headline (Benzinga movers) | 62 | 34% | $+191.74 | $+3.09 | 26 | $+7.37 | $-21.10 | 9/26 |
|   nothing at all | 72 | 42% | $+1058.06 | $+14.70 | 33 | $+32.06 | $+22.17 | 19/33 |
| by KIND (first non-digest headline) | | | | | | | | |
|   other | 26 | 31% | $-60.55 | $-2.33 | 15 | $-4.04 | $-13.71 | 7/15 |
|   earnings | 19 | 37% | $+70.59 | $+3.72 | 12 | $+5.88 | $-0.10 | 6/12 |
|   contract | 15 | 33% | $-55.90 | $-3.73 | 13 | $-4.30 | $-18.07 | 4/13 |
|   merger | 6 | 33% | $-64.48 | $-10.75 | 5 | $-12.90 | $-32.63 | 2/5 |
|   halt | 5 | 20% | $-15.76 | $-3.15 | 3 | $-5.25 | $-18.46 | 1/3 |
|   offering | 2 | 50% | $+43.03 | $+21.52 | 2 | $+21.52 | $+21.52 | 1/2 |
|   crypto_ai | 1 | 100% | $+50.79 | $+50.79 | 1 | $+50.79 | $+50.79 | 1/1 |
verdict-input: catalyst -0.44 vs none +9.33 $/trade (delta -9.76); win 34% vs 38%

### O-config portfolio (BA+grinder re-attack, 2-slot, H4)
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 154 | 71% | $+5643.21 | $+36.64 | 36 | $+156.76 | $+130.35 | 33/36 |
| catalyst (non-digest, pt-in-time) | 45 | 53% | $+296.65 | $+6.59 | 25 | $+11.87 | $+9.42 | 14/25 |
| no catalyst | 109 | 78% | $+5346.56 | $+49.05 | 36 | $+148.52 | $+111.29 | 33/36 |
|   digest-only headline (Benzinga movers) | 30 | 73% | $+1149.79 | $+38.33 | 22 | $+52.26 | $+45.26 | 18/22 |
|   nothing at all | 79 | 80% | $+4196.77 | $+53.12 | 35 | $+119.91 | $+94.40 | 31/35 |
| by KIND (first non-digest headline) | | | | | | | | |
|   other | 15 | 47% | $+52.19 | $+3.48 | 11 | $+4.74 | $+26.63 | 6/11 |
|   earnings | 13 | 38% | $-123.18 | $-9.48 | 11 | $-11.20 | $-40.09 | 4/11 |
|   contract | 6 | 67% | $+51.55 | $+8.59 | 4 | $+12.89 | $+12.22 | 2/4 |
|   halt | 4 | 50% | $-39.95 | $-9.99 | 3 | $-13.32 | $+5.27 | 2/3 |
|   analyst | 2 | 100% | $+226.51 | $+113.26 | 2 | $+113.26 | $+113.26 | 2/2 |
|   merger | 2 | 100% | $+91.29 | $+45.64 | 2 | $+45.64 | $+45.64 | 2/2 |
|   fda_clinical | 1 | 0% | $-70.39 | $-70.39 | 1 | $-70.39 | $-70.39 | 0/1 |
|   offering | 1 | 100% | $+57.88 | $+57.88 | 1 | $+57.88 | $+57.88 | 1/1 |
|   crypto_ai | 1 | 100% | $+50.75 | $+50.75 | 1 | $+50.75 | $+50.75 | 1/1 |
verdict-input: catalyst +6.59 vs none +49.05 $/trade (delta -42.46); win 53% vs 78%

### O-config flat_top leg
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 107 | 70% | $+3883.08 | $+36.29 | 36 | $+107.86 | $+87.49 | 29/36 |
| catalyst (non-digest, pt-in-time) | 34 | 47% | $-105.67 | $-3.11 | 24 | $-4.40 | $-2.41 | 12/24 |
| no catalyst | 73 | 81% | $+3988.75 | $+54.64 | 35 | $+113.96 | $+86.07 | 31/35 |
|   digest-only headline (Benzinga movers) | 24 | 75% | $+944.13 | $+39.34 | 20 | $+47.21 | $+40.78 | 16/20 |
|   nothing at all | 49 | 84% | $+3044.62 | $+62.14 | 34 | $+89.55 | $+64.33 | 27/34 |
| by KIND (first non-digest headline) | | | | | | | | |
|   other | 12 | 50% | $+68.71 | $+5.73 | 11 | $+6.25 | $+26.63 | 6/11 |
|   earnings | 11 | 27% | $-203.73 | $-18.52 | 10 | $-20.37 | $-40.26 | 3/10 |
|   contract | 4 | 75% | $+40.16 | $+10.04 | 3 | $+13.39 | $+15.72 | 2/3 |
|   halt | 3 | 33% | $-78.22 | $-26.07 | 3 | $-26.07 | $-33.00 | 1/3 |
|   fda_clinical | 1 | 0% | $-70.39 | $-70.39 | 1 | $-70.39 | $-70.39 | 0/1 |
|   offering | 1 | 100% | $+57.88 | $+57.88 | 1 | $+57.88 | $+57.88 | 1/1 |
|   merger | 1 | 100% | $+29.17 | $+29.17 | 1 | $+29.17 | $+29.17 | 1/1 |
|   crypto_ai | 1 | 100% | $+50.75 | $+50.75 | 1 | $+50.75 | $+50.75 | 1/1 |
verdict-input: catalyst -3.11 vs none +54.64 $/trade (delta -57.75); win 47% vs 81%

### O-config grinder leg
| split | N | win | total | $/trade | days | day mean | day median | green |
|---|---|---|---|---|---|---|---|---|
| ALL | 47 | 72% | $+1760.14 | $+37.45 | 25 | $+70.41 | $+58.79 | 22/25 |
| catalyst (non-digest, pt-in-time) | 11 | 73% | $+402.32 | $+36.57 | 9 | $+44.70 | $+57.42 | 7/9 |
| no catalyst | 36 | 72% | $+1357.81 | $+37.72 | 21 | $+64.66 | $+58.43 | 18/21 |
|   digest-only headline (Benzinga movers) | 6 | 67% | $+205.66 | $+34.28 | 5 | $+41.13 | $+36.87 | 4/5 |
|   nothing at all | 30 | 73% | $+1152.15 | $+38.41 | 20 | $+57.61 | $+57.34 | 17/20 |
| by KIND (first non-digest headline) | | | | | | | | |
|   other | 3 | 33% | $-16.52 | $-5.51 | 1 | $-16.52 | $-16.52 | 0/1 |
|   contract | 2 | 50% | $+11.38 | $+5.69 | 2 | $+5.69 | $+5.69 | 1/2 |
|   analyst | 2 | 100% | $+226.51 | $+113.26 | 2 | $+113.26 | $+113.26 | 2/2 |
|   earnings | 2 | 100% | $+80.55 | $+40.28 | 2 | $+40.28 | $+40.28 | 2/2 |
|   halt | 1 | 100% | $+38.27 | $+38.27 | 1 | $+38.27 | $+38.27 | 1/1 |
|   merger | 1 | 100% | $+62.12 | $+62.12 | 1 | $+62.12 | $+62.12 | 1/1 |
verdict-input: n/a

### O-config portfolio: catalyst trades (for the one-trade trace rule)
| date | sym | det | sig(UTC) | pnl | kind | first headline (created_at) |
|---|---|---|---|---|---|---|
| 2026-06-25 | AZI | flat_top | 13:45:30 | $+15.72 | contract | Autozi Internet Technology Signs ~$5.25M Securities Purchase Agreement (2026-06-24T20:16:22Z) |
| 2026-06-25 | AZI | grinder | 18:42:30 | $-46.04 | contract | Autozi Internet Technology Signs ~$5.25M Securities Purchase Agreement (2026-06-24T20:16:22Z) |
| 2026-06-29 | TNMG | flat_top | 14:25:30 | $+44.27 | contract | TNL Mediagene's Keychron Orca Echo Tops ¥300 Million GMV Within Five D (2026-06-29T12:09:31Z) |
| 2026-06-30 | GVH | flat_top | 13:46:40 | $+24.55 | contract | Globavend Launches First Fully AI-Produced Original Micro Drama Using  (2026-06-30T08:48:54Z) |
| 2026-06-30 | GVH | flat_top | 14:28:30 | $-44.37 | contract | Globavend Launches First Fully AI-Produced Original Micro Drama Using  (2026-06-30T08:48:54Z) |
| 2026-07-01 | STKE | grinder | 15:17:10 | $+74.05 | analyst | Cantor Fitzgerald Maintains Overweight on Sol Strategies, Lowers Price (2026-07-01T14:47:51Z) |
| 2026-07-02 | YRD | flat_top | 13:46:10 | $-38.25 | other | Yiren Digital Authorizes New Share Repurchase Program To Repurchase Up (2026-07-02T10:14:38Z) |
| 2026-07-02 | CWD | flat_top | 14:16:00 | $-70.39 | fda_clinical | Caliber Begins Next Phase Of Its Real Estate Fund Tokenization Strateg (2026-07-02T11:17:31Z) |
| 2026-07-02 | YRD | grinder | 15:15:00 | $-27.57 | other | Yiren Digital Authorizes New Share Repurchase Program To Repurchase Up (2026-07-02T10:14:38Z) |
| 2026-07-02 | YRD | grinder | 15:46:40 | $-27.29 | other | Yiren Digital Authorizes New Share Repurchase Program To Repurchase Up (2026-07-02T10:14:38Z) |
| 2026-07-02 | YRD | grinder | 16:24:10 | $+38.34 | other | Yiren Digital Authorizes New Share Repurchase Program To Repurchase Up (2026-07-02T10:14:38Z) |
| 2026-07-06 | LUCY | flat_top | 13:47:00 | $-63.54 | earnings | Innovative Eyewear Reports Preliminary Q2 Net Sales Of ~$0.99M, Up 71% (2026-07-06T12:08:59Z) |
| 2026-07-06 | ABTC | flat_top | 13:54:10 | $-33.00 | halt | Trading Halt: Halt status updated at 8:55:00 AM ET: Quotation Resumpti (2026-07-06T12:55:00Z) |
| 2026-07-06 | ABTC | grinder | 16:19:50 | $+38.27 | halt | Trading Halt: Halt status updated at 8:55:00 AM ET: Quotation Resumpti (2026-07-06T12:55:00Z) |
| 2026-07-07 | NPT | flat_top | 13:42:10 | $+54.48 | other | Texxon Holding Announces That Its Henan Polystyrene Production Facilit (2026-07-07T13:25:25Z) |
| 2026-07-08 | SRXH | flat_top | 13:49:30 | $-25.23 | other | SRX Global Declares Special Cash Dividend Of $0.05 Per Share (2026-07-08T13:10:57Z) |
| 2026-07-08 | IOTR | flat_top | 13:56:40 | $-40.09 | earnings | iOThree Chairman And CEO Issues Shareholder Letter; FY26 Revenue $14.7 (2026-07-07T20:37:53Z) |
| 2026-07-08 | TVRD | grinder | 15:28:40 | $+152.46 | analyst | Raymond James Upgrades Tvardi Therapeutics to Outperform, Announces $1 (2026-07-08T10:02:13Z) |
| 2026-07-09 | TDTH | flat_top | 14:28:00 | $+74.24 | other | Trident Digital Tech Holdings Announces Strategic Equity Investment In (2026-07-09T12:03:21Z) |
| 2026-07-09 | FBRX | grinder | 16:17:00 | $+65.01 | earnings | Forte Biosciences Reports Results From FB102 Double-Blind Placebo-Cont (2026-07-09T12:08:21Z) |
| 2026-07-13 | BRAI | flat_top | 13:43:00 | $+26.72 | other | Braiin Releases ARIA-Agentic Real Estate Intelligence And Automation,  (2026-07-13T12:32:19Z) |
| 2026-07-13 | QTTB | flat_top | 13:56:00 | $-40.96 | earnings | Q32 Bio To Reveal 36-Week Topline Results From Part B Of The SIGNAL-AA (2026-07-10T20:08:25Z) |
| 2026-07-15 | AMDD | flat_top | 13:51:20 | $+9.42 | halt | Trading Halt: Halted at 7:50:00 p.m. ET - Trading Halt: Halt News Pend (2026-07-14T23:50:00Z) |
| 2026-07-17 | BIYA | flat_top | 13:45:40 | $-32.17 | other | Baiya International Group (BIYA) Stock Is Trending Overnight—Here's Wh (2026-07-17T04:02:26Z) |
| 2026-07-20 | SDOT | flat_top | 13:54:20 | $-54.71 | other | Why Is Sadot Stock Surging on Monday? (2026-07-20T12:46:02Z) |
| 2026-07-22 | MSS | flat_top | 13:43:30 | $-54.63 | halt | Trading Halt: Halted at 7:50:00 p.m. ET - Trading Halt: Halt News Pend (2026-07-21T23:50:00Z) |
| 2026-07-22 | QMLS | grinder | 18:23:20 | $+57.42 | contract | QumulusAI Enters Two-Year, $18M Take-Or-Pay Agreement To Supply Nvidia (2026-07-22T13:13:14Z) |
| 2026-07-23 | AEHL | flat_top | 13:45:10 | $-46.83 | other | Antelope Enterprise Stock Surges Nearly 38% After Hours: Why Is It Mov (2026-07-23T05:58:19Z) |
| 2026-07-27 | ENTX | flat_top | 13:48:20 | $+57.88 | offering | Entera Bio Enters Into Securities Purchase Agreement For Oversubscribe (2026-07-27T12:33:08Z) |
| 2026-07-27 | KIDZ | flat_top | 14:15:10 | $+34.15 | earnings | KIDZ AI Outlines View On Current Share-Price Discount; Intends To Seek (2026-07-27T11:24:01Z) |
| 2026-07-29 | MSS | flat_top | 13:42:10 | $+43.40 | other | Maison Solutions CEO Shares Letter With Shareholders; Company Intends  (2026-07-29T13:38:51Z) |
| 2026-07-29 | NCRA | flat_top | 14:22:50 | $+29.17 | merger | Nocera Acquires 30% Stake In Taiwanese Memory And Storage Solution Fir (2026-07-29T12:02:56Z) |
| 2026-07-29 | GMM | flat_top | 14:29:30 | $-46.77 | earnings | Global Mofy Metaverse H1 EPS $(69.66) Down From $43.50 YoY, Sales $39. (2026-07-29T05:51:23Z) |
| 2026-08-03 | CNCK | flat_top | 13:44:00 | $+40.43 | other | Coincheck Group Files Prospectus For Resale Of Up To 56,447,361 Ordina (2026-07-31T20:27:37Z) |
| 2026-08-03 | NEXR | grinder | 17:22:20 | $+62.12 | merger | Nexera Technologies Announces Letter Of Intent For Exclusive Worldwide (2026-08-03T11:42:32Z) |
| 2026-08-04 | PLTU | flat_top | 13:43:20 | $+50.75 | crypto_ai | Palantir's AI Sovereignty Bet Could Be the Next Big ETF Catalyst (2026-08-04T12:36:17Z) |
| 2026-08-05 | APPS | flat_top | 13:45:50 | $-44.77 | earnings | Digital Turbine Q1 Adj. EPS $0.19 Beats $0.14 Estimate, Sales $165.983 (2026-08-04T20:09:51Z) |
| 2026-08-05 | OESX | flat_top | 13:48:20 | $-58.28 | earnings | Orion Energy Sys Q1 EPS $0.47 Beats $0.14 Estimate, Sales $25.743M Bea (2026-08-05T11:04:05Z) |
| 2026-08-06 | PN | flat_top | 13:45:20 | $-35.38 | other | PN Smart Energy Announces Incorporation Of Two Wholly Owned US Subsidi (2026-08-06T13:03:54Z) |
| 2026-08-06 | PN | flat_top | 14:10:30 | $+62.01 | other | PN Smart Energy Announces Incorporation Of Two Wholly Owned US Subsidi (2026-08-06T13:03:54Z) |
| 2026-08-11 | NIQ | flat_top | 13:42:00 | $+50.44 | earnings | NIQ Global Intelligence Sees Q3 Adj EPS $0.22-$0.24 vs $0.22 Est; Sees (2026-08-10T20:01:43Z) |
| 2026-08-11 | NIQ | grinder | 15:19:40 | $+15.54 | earnings | NIQ Global Intelligence Sees Q3 Adj EPS $0.22-$0.24 vs $0.22 Est; Sees (2026-08-10T20:01:43Z) |
| 2026-08-12 | NBIG | flat_top | 13:47:20 | $+64.60 | earnings | Nebius Q2 Outlook: Will Goldman’s $35.5 Billion Revenue Forecast Overp (2026-08-12T08:02:29Z) |
| 2026-08-13 | CURI | flat_top | 13:45:40 | $-18.07 | earnings | CuriosityStream Q2 EPS $0.15 Beats $0.04 Estimate, Sales $23.245M Beat (2026-08-12T20:07:05Z) |
| 2026-08-14 | TMS | flat_top | 13:54:20 | $-40.44 | earnings | Teamshares Q2 EPS $0.16 Beats $(0.20) Estimate, Sales $148.660M Miss $ (2026-08-14T11:08:50Z) |


### Permutation (5,000 shuffles, delta = catalyst $/trade minus no-catalyst $/trade)
| lane | N | catalyst N | observed delta | p (trade shuffle) | p (name-day shuffle) |
|---|---|---|---|---|---|
| BA solo | 384 | 138 | -$39.07 | 0.0000 | 0.0000 (311 name-days) |
| grinder1030 solo | 231 | 62 | -$20.06 | 0.0012 | 0.034 (87 name-days) |
| O-config H4 | 154 | 45 | -$42.46 | 0.0000 | 0.0000 (128 name-days) |

### Verdicts per lane
- **BA in-window (flat_top break-attack):** catalyst DISCRIMINATES, negatively — -$1.45 vs +$37.62/trade, 45% vs 71% win, p<0.001 at name-day level. Proposal-grade as a WEAKNESS stamp. Earnings (-$3.53, N=31), halt (-$5.63, N=14), merger (-$7.35, N=12) all red; no kind is green at N>=5.
- **grinder post-10:30:** same direction, weaker (p=0.034 name-day; the 62 catalyst trades sit on only 13 name-days, 31 of them "earnings" on 3 names). Not proposal-grade alone.
- **E3 exits / live-parity flatten:** exits are the same code in both buckets; the split is an ENTRY-population effect, not an exit effect. Flatten cohort untouched.
- **O-config portfolio:** +$6.59 vs +$49.05/trade; the flat_top leg carries it (-$3.11 vs +$54.64); grinder leg flat (+$36.57 vs +$37.72, N=11).
- **Toxic kind:** EARNINGS is the only kind red at N>=10 in the portfolio (-$9.48/trade, 38% win; flat_top leg -$18.52, 27%). HALT-headline-before-signal is red in BA (-$5.63, 36%). Offerings: N=4/2/1 across lanes, all green — NOT toxic in this window; too thin to say anything, and offerings that hit AFTER entry are not captured by a pre-signal stamp (that is a separate, exit-side question).

### Caveats (Skepticism Needs Verification Too — named)
1. Selection confound: names Benzinga writes about are more-followed names; the inversion may be "crowded/known name" rather than "catalyst". The stamp still discriminates either way; the CAUSE is unproven.
2. Keyword KIND classifier is homegrown; "earnings" regex also catches "Q2" digest-like phrasing. Kind-level numbers are N<=31 and inherit misclassification.
3. Single news source (benzinga). Coverage % is a Benzinga-on-Alpaca number, not a "does a catalyst exist" number (SEC 8-K/PR-wire not queried).
4. 36 dates, in-sample; the O-config lanes were selected on this window. The catalyst split was NOT part of that selection, and the permutation is at name-day level, but OOS days are still owed before any rule.

## Recommendation for the scanner-column build (stamp-only first, per doctrine)
1. `catalyst` service call at scanner refresh (60s server-side pull already the design of record): one batched
   `symbols=` request per refresh (all board names in one call, limit 50 + pagination), start = prior business
   day 20:00Z. Well inside the 10,000/min limit.
2. Columns: `news_n` (non-digest count), `news_first_et`, `news_kind`, `news_digest_only` (bool), `news_headline`
   (latest non-digest, truncated). Digest filter = >5 symbols OR movers/market-wrap regex (both needed).
3. Stamp `catalyst_kind` + `news_first_et` on every entry-gate row (observe-only). NO gate. Re-grade after
   >=5 live days: expected sign is NEGATIVE for BA/flat_top on `earnings` and `halt`.
4. Any behavior change (skip earnings-catalyst BA entries, or size down) goes back to Marcos priced: in-window it
   would have moved O-config from +$5,643 to ~+$5,766 (dropping earnings N=13, -$123) — small; NOT worth a
   gate on today's evidence. The larger lever (skip ALL catalyst BA trades) removes -$105.67 over 34 trades and
   ~$0 net on grinder — also small in dollars; the value is in what it tells the Strength Ombudsman/Side
   Marshal about WHICH names the lanes actually pay on (blue-sky/no-news), not in a filter.
