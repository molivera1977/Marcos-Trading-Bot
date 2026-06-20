"""
Quick test to discover what Webull instrument + company_profile APIs return.
Run with:
    WEBULL_APP_KEY=... WEBULL_APP_SECRET=... WEBULL_ACCESS_TOKEN=... python3 test_webull_fields.py

Prints the raw JSON from both endpoints for a few tickers so we can see
exactly which fields are available for float, avg_vol, market_cap, sector.
"""
import os, sys, json

TICKERS = ["AAPL", "AMC", "SOUN"]   # mix of big/small cap to see what changes

def make_client():
    from webull.data import DataClient
    cfg = {
        "app_key":      os.environ["WEBULL_APP_KEY"],
        "app_secret":   os.environ["WEBULL_APP_SECRET"],
        "access_token": os.environ["WEBULL_ACCESS_TOKEN"],
        "region_id":    int(os.environ.get("WEBULL_REGION_ID", "6")),
        "device_id":    os.environ.get("WEBULL_DEVICE_ID", ""),
    }
    trade_token = os.environ.get("WEBULL_TRADE_TOKEN", "")
    if trade_token:
        cfg["trade_token"] = trade_token
    return DataClient(**cfg)

def pp(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)
    print(json.dumps(data, indent=2, default=str))

dc = make_client()

for ticker in TICKERS:
    print(f"\n\n{'#'*60}")
    print(f"  {ticker}")
    print(f"{'#'*60}")

    # 1. snapshot
    try:
        r = dc.market_data.get_snapshot(symbols=ticker, extend_hour_required=True)
        pp(f"snapshot ({r.status_code})", r.json())
    except Exception as e:
        print(f"snapshot error: {e}")

    # 2. instrument
    try:
        r = dc.instrument.get_instrument(symbols=ticker)
        pp(f"instrument ({r.status_code})", r.json())
    except Exception as e:
        print(f"instrument error: {e}")

    # 3. company_profile
    try:
        r = dc.instrument.get_company_profile(ticker)
        pp(f"company_profile ({r.status_code})", r.json())
    except Exception as e:
        print(f"company_profile error: {e}")

print("\n\nDone.")
