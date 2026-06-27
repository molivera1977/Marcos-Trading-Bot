# Real-data exit/detection backtest (Webull bars)

Tunes the bot's ACTUAL detection (kevlib.py = verbatim find_next_supply/compute_room/etc.
extracted from marcos_trading_bot.py) + the Kev exit sim against REAL Webull 1-min bars.

Local Python is 3.9 (can't import the full bot module), so:
1. `railway run --service Marcos-Trading-Bot python3 fetch_cache.py` — pulls real Webull bars
   (creds injected by `railway run`) and caches them to /tmp/bars_<SYM>.json. The Webull
   historical feed is intermittent — fetch_cache retries; cache so you analyze offline.
2. `python3 analyze_exits.py` — runs detection + the exit-policy comparison on the cached bars.

KEY 6/26 finding: the instant-exit must be POST-SCALE (firing pre-scale on 1-min noise cut
SDOT to +1.1% vs its +60% move). Even fixed, exits capture only the FIRST LEG — the big
runners need the add-on-break / re-entry build. See [[project_kev_coverage]].
