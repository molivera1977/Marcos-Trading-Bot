#!/usr/bin/env python3
"""KEV UNCONDITIONAL READS — Monday 07:15 ET one-command check (D5, scripted 8/16).

Mechanism (newcomer_vision_reader.py ~line 675, #54 Build 2, KEV_READ_UNCONDITIONAL=1 default,
KEV_PRIMACY!=1): Kev-sheet names are READ like every other name (the read IS the flip); reader
worker starts at NEWCOMER_START_HHMM (07:00 env-shipped per ledger). Production trace = the
kev_watchlist record for each sheet name: after the read it carries src="vision", kev_name/
kev_shadow (Kev's numbers preserved beside), and `_ts` = the read's post time.
8/14 evidence already in the store: AKAN _ts 07:00:11, XHG _ts 07:00:28 (src=vision, kev_shadow=True);
DFSC/WETO carry later re-read _ts (14:45/14:03) — first-read time not recoverable from _ts alone.

PASS = every ticker on today's sheet has a record with a `_ts` <= 07:15 (or, if run later, ANY
`_ts` today) and kev_shadow present (i.e. the sheet's numbers were preserved while ours flipped in).
Also prints decisions rows read_requested / reread_* for the names.

Usage (Monday 07:15 ET): python3 data/killtests/kev_reads_0715_check.py [YYYY-MM-DD]
"""
import json, sys, datetime, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
U = "https://zestful-intuition-production-b16a.up.railway.app"
DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(ET).strftime("%Y-%m-%d")


def get(url):
    try:
        return json.load(urllib.request.urlopen(url, timeout=60))
    except Exception as e:
        return {"_err": str(e)}


def main():
    now = datetime.datetime.now(ET)
    d = get(f"{U}/api/kev_watchlist?date={DAY}")
    names = d.get("tickers") or []
    lv = d.get("levels") or {}
    print(f"[{now:%Y-%m-%d %H:%M:%S} ET] sheet {DAY}: {names}")
    if not names:
        print("NO SHEET NAMES posted yet (kev_sweep 8pm/9am) — nothing to read; check /api/decisions?status=kev_sweep")
        return 2
    ok = 0
    for t in names:
        r = lv.get(t) or {}
        ts = r.get("_ts"); src = r.get("src")
        hhmm = ts[11:19] if ts else None
        read = bool(ts) and src == "vision"
        by715 = bool(hhmm) and hhmm <= "07:15:00"
        flag = ("READ@" + hhmm + (" (<=07:15)" if by715 else " (late)")) if read else ("SHEET-ONLY src=" + str(src) if r else "NO RECORD")
        print(f"  {t:6} {flag:32} break={r.get('break')} kev_shadow={'yes' if r.get('kev_shadow') else 'no'} "
              f"blue_sky={r.get('blue_sky')} conf={r.get('confidence')}")
        ok += 1 if read else 0
    dec = get(f"{U}/api/decisions?date={DAY}&limit=2000").get("rows") or []
    for t in names:
        rr = [x for x in dec if x.get("ticker") == t and str(x.get("status")).startswith(("read_", "reread_", "kev_"))]
        if rr:
            print(f"  {t} reader/kev rows: " + ", ".join(f"{x['status']}@{x['time']}" for x in rr[:6]))
    verdict = ("PROVEN — all sheet names read (src=vision, Kev preserved in kev_shadow)" if ok == len(names)
               else f"NOT YET — {len(names)-ok}/{len(names)} sheet names unread" + (" (reader may still be in its first pass; re-run 07:30)" if now.strftime('%H:%M') < '07:30' else " — reader/render failure: pull reader logs"))
    print("VERDICT:", verdict)
    return 0 if ok == len(names) else 1


if __name__ == "__main__":
    sys.exit(main())
