# Marcos Trading Bot — Signal Reference

Every signal/filter the bot uses, grouped by phase. Items marked **(NEW)** were added in the
June 2026 momentum-quality pass (Level 2, momentum filter, tiered exits, entry floor).

DRY_RUN mode is active — all orders are simulated. Account cap: $100/trade.

---

## 1. SCREENER (pre-market — picks candidates)

| Signal | Rule |
|--------|------|
| Gap-up detection | Pre-market gappers + halt-resume scanner |
| RVOL filter | Relative volume > 1.5× average |
| Price range | > 10% range off the open |
| Flat-top detection | 4-bar consolidation, < 8% range |
| EMA stack | EMA9 above EMA20 (bullish), 2 confirm bars |
| VWAP required | Price must be above VWAP |
| SPY sentiment | BULLISH / BEARISH / NEUTRAL context to Claude (hard −2.5% skip removed — was dead code) |
| Entry window | 9:00–11:00 AM ET (skipped in DRY_RUN to scan all day) |
| Min reward:risk | ≥ 2:1 |
| Intraday rescan | Every 5 min while watching |

## 2. ENTRY FILTERS (must pass ALL before buying)

| Signal | Rule |
|--------|------|
| VWAP reclaim confirmation | Price holds above VWAP for 3 ticks |
| VWAP reclaim volume | 2× average minute volume on the reclaim |
| Min absolute volume | Bounce bar ≥ 15,000 shares |
| VWAP pullback detection | Within 3% of VWAP = "at VWAP"; needs prior run ≥ 5% above VWAP |
| VWAP extension cap | Won't enter if price > 8% above VWAP (anti-chasing) |
| Bid-ask spread | Must be < 3% of ask |
| Entry limit buffer | Limit buy 1% above VWAP reclaim (caps slippage) |
| **Level 2 order book (NEW)** | Checks sell walls, bid/ask ratio, thin bids, no-bid |
| **Momentum filter (NEW)** | Avg vol last 3 bars ≥ 10k, vol acceleration ≥ 1.2×, ≥ 2/3 green bars |
| **Topping-tail skip (NEW)** | Skip entry if the last completed bar's upper wick ≥ 55% of its range (Kev's "tail off the high" = rejection) |
| EMA bounce entry | Prev bar within 1.5% of EMA9 = "touch"; 20-bar lookback; bounce vol 1.2× prior 3-bar avg |
| Position sizing | HIGH 70% / MED 50% / LOW 30% of account; hard cap $100/trade |
| No late entries | Final cutoff 3:30 PM ET |
| Early fade protection | Exit if price drops below VWAP within 2 min of entry |

## Data-only (recorded, NOT yet used to gate trades)

| Metric | What's captured |
|--------|-----------------|
| **90 EMA at entry (NEW)** | For every trade we record the 90 EMA and `entry_vs_ema90_pct` (how far entry was above/below it). Gathering data to decide later if a 90 EMA filter/entry helps. Does not affect any entry or exit. |

## 3. EXIT SIGNALS

| Signal | Rule |
|--------|------|
| **Morning tiered exits (NEW)** | +8% → sell 25%, +12% → sell 50%, +20% → sell last 25% |
| **Afternoon tiered exits (NEW)** | +4% → sell 50%, +6% → sell last 50% |
| **Topping-tail exit (NEW)** | In profit + last bar makes a fresh high then prints upper wick ≥ 55% of range → full exit (Kev's #1 exit) |
| Trailing stop | 5% below highest price (after first partial) |
| **Entry floor (NEW)** | After first partial, stop never drops below entry price |
| EMA9 dynamic stop | 2 consecutive bars below EMA9 (checked every 60s); initial stop = EMA9 × (1 − 2.5%) |
| Emergency stop loss | Hard −7% exchange-level stop |
| Overextension exit | Full profit target +20%, sell everything |
| Time stop | Force-close all positions 3:45 PM ET (no overnight holds) |

---

## Design notes

- **Tiered exits are time-of-day aware:** morning entries get wider tiers (runners need room);
  afternoon entries scale out tighter (PM moves fade faster).
- **Entry floor** means once you've taken a first partial, a winner can't turn back into a loser.
- **VWAP extension cap (8%)** is the wide net; **momentum + Level 2** are the fine filters that
  block dead-volume setups (e.g. the EZRA-style 1-share-print chop).
- **SPY sentiment** is advisory only — it nudges Claude to be more selective on red-market days
  but does not hard-block trading.
