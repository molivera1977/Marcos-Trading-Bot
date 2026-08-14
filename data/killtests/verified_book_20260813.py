#!/usr/bin/env python3
"""THE VERIFIED BOOK — 8/13. Every era trade (2026-07-13+) verified against 10s tape.

ASSUMPTIONS (all stated, none smoothed):
- Trade P&L as rendered by /api/trades (runner-leg correction already applied) = "raw".
- Bars: cached .fourarm_cache_v3/_v2/_20260813 first, then /api/bars ~10S, fallback ~ALP10S.
  Best available feed per (ticker,day): prefer 10S, but if ALP10S has more bars use the UNION
  of both feeds' bars (tape is tape; either feed printing a price proves it printed).
- Entry verified: some bar within +/-3min of entry_ts_utc whose [low,high] overlaps
  [entry*0.995, entry*1.005]. Trades missing entry_ts_utc (162/412): window = whole day up to
  recorded_at; flagged entry_ts_missing (verification is weaker, labeled).
- Fill strict: post-entry bar high >= fill_px*0.999 at ts <= recorded_at.
  Fill generous: same test, post-entry through end of day's bars.
  Post-entry = ts >= entry_ts - 60s (bar-boundary slack); if no entry_ts, from day start.
- Exit verified: any post-entry bar overlaps [exit*0.99, exit*1.01].
- CHARITABLE pnl: each FICTION fill re-booked at max(entry, best post-entry high in the
  generous window); delta = sh*(best_provable - fill_px). Everything else as recorded.
- STRICT pnl: FICTION fill shares exit at the trade's recorded exit px instead.
- no_bars trades: excluded from verified totals, listed + summed separately.
- RTH/PRE: entry_session field; else entry_ts ET < 09:30 => PRE; else recorded_at ET.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ROOT = "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/killtests"
CACHES = [f"{ROOT}/.fourarm_cache_v3_20260813", f"{ROOT}/.fourarm_cache_v2_20260813",
          f"{ROOT}/.fourarm_cache_20260813"]
BASE = "https://zestful-intuition-production-b16a.up.railway.app"
ET = ZoneInfo("America/New_York")

def load_trades():
    tr = json.load(open(CACHES[0] + "/trades.json"))["trades"]
    return [t for t in tr if t.get("date", "") >= "2026-07-13"]

def parse_ts(s):
    if not s: return None
    s = s.replace("Z", "+00:00").replace("+0000", "+00:00")
    try: return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError: return None

def fetch(url):
    try:
        return json.load(urllib.request.urlopen(url, timeout=60))
    except Exception:
        return None

def get_bars(sym, date):
    """Return list of (ts_utc, low, high) union of best feeds; [] if none."""
    feeds = {}
    for feed in ("10S", "ALP10S"):
        data = None
        for c in CACHES:
            p = f"{c}/bars_{sym}~{feed}_{date}.json"
            if os.path.exists(p):
                data = json.load(open(p)); break
        if data is None:
            data = fetch(f"{BASE}/api/bars?ticker={sym}~{feed}&date={date}")
            if data and data.get("bars"):
                json.dump(data, open(f"{CACHES[0]}/bars_{sym}~{feed}_{date}.json", "w"))
        if data and data.get("bars"):
            feeds[feed] = data["bars"]
    out = []
    for bars in feeds.values():
        for b in bars:
            ts = parse_ts(b["time"])
            if ts: out.append((ts, float(b["low"]), float(b["high"])))
    out.sort()
    return out

def main():
    trades = load_trades()
    days = sorted({t["date"] for t in trades})
    results = []
    n = 0
    for t in trades:
        n += 1
        sym, date = t["ticker"], t["date"]
        bars = get_bars(sym, date)
        entry = float(t["entry"]); exitp = float(t["exit"]); pnl = float(t["pnl"])
        ets = parse_ts(t.get("entry_ts_utc"))
        rts = parse_ts(t.get("recorded_at"))
        # session
        sess = t.get("entry_session")
        if not sess:
            ref = ets or rts
            sess = "PRE" if ref and ref.astimezone(ET).time() < datetime.strptime("09:30", "%H:%M").time() else "RTH"
        r = {"trade_id": t["trade_id"], "ticker": sym, "date": date, "session": sess,
             "lane": t.get("entry_type") or "unknown", "entry": entry, "exit": exitp,
             "pnl_raw": pnl, "shares": t.get("shares"), "entry_ts_missing": ets is None}
        if not bars:
            r.update(no_bars=True, entry_verified=None, exit_verified=None,
                     fills=[], pnl_charitable=None, pnl_strict=None)
            results.append(r)
            if n % 10 == 0: print(f"progress {n}/{len(trades)}", flush=True)
            continue
        r["no_bars"] = False
        # entry
        if ets:
            win = [b for b in bars if abs((b[0] - ets).total_seconds()) <= 180]
        else:
            win = [b for b in bars if rts is None or b[0] <= rts]
        r["entry_verified"] = any(lo <= entry * 1.005 and hi >= entry * 0.995 for _, lo, hi in win)
        # post-entry bars
        start = (ets - timedelta(seconds=60)) if ets else None
        post = [b for b in bars if start is None or b[0] >= start]
        post_strict = [b for b in post if rts is None or b[0] <= rts]
        best_high = max((hi for _, _, hi in post), default=None)
        # fills
        fills = []
        for f in (t.get("partial_fills") or []):
            sh, px = int(f[0]), float(f[1])
            s_ok = any(hi >= px * 0.999 for _, _, hi in post_strict)
            g_ok = s_ok or any(hi >= px * 0.999 for _, _, hi in post)
            cat = "verified_strict" if s_ok else ("verified_generous_only" if g_ok else "FICTION")
            fills.append({"shares": sh, "px": px, "cat": cat})
        r["fills"] = fills
        r["exit_verified"] = any(lo <= exitp * 1.01 and hi >= exitp * 0.99 for _, lo, hi in post)
        # pnl constructions
        char = strict = pnl
        for f in fills:
            if f["cat"] == "FICTION":
                bp = max(entry, best_high if best_high is not None else entry)
                char += f["shares"] * (bp - f["px"])
                strict += f["shares"] * (exitp - f["px"])
        r["pnl_charitable"] = round(char, 2)
        r["pnl_strict"] = round(strict, 2)
        results.append(r)
        if n % 10 == 0: print(f"progress {n}/{len(trades)}", flush=True)

    json.dump(results, open("/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/history/VERIFIED_BOOK.json", "w"), indent=1)
    report(results, days)

def sums(rows, key):
    return round(sum(r[key] for r in rows if r.get(key) is not None), 2)

def report(results, days):
    ok = [r for r in results if not r["no_bars"]]
    nb = [r for r in results if r["no_bars"]]
    L = []
    L.append("# THE VERIFIED BOOK — era 2026-07-13 onward (built 2026-08-13)")
    L.append("")
    L.append("**Headline uses CHARITABLE (fiction fills re-booked at best provable price); STRICT (fiction fills exit at recorded exit) is the floor.**")
    L.append("")
    L.append("## Assumptions")
    L.append("See header of `data/killtests/verified_book_20260813.py` — trade pnl as rendered (correction applied) = raw; union of 10S+ALP10S tape; entry ±3min/0.5%; fill touch = bar high >= px*0.999; exit ±1%; NO smoothing or interpolation; no-bars trades excluded from verified totals and listed below; 162 trades lack entry_ts_utc (whole-day window, flagged).")
    L.append("")
    for sess in ("RTH", "PRE"):
        s = [r for r in ok if r["session"] == sess]
        snb = [r for r in nb if r["session"] == sess]
        L.append(f"## {sess} era book")
        L.append(f"- trades verified: {len(s)}  |  no-bars (excluded): {len(snb)} (raw ${sums(snb,'pnl_raw'):+.2f})")
        L.append(f"- RAW: ${sums(s,'pnl_raw'):+.2f}   CHARITABLE: ${sums(s,'pnl_charitable'):+.2f}   STRICT: ${sums(s,'pnl_strict'):+.2f}")
        L.append("")
    L.append("## Per-day (verified trades only; no-bars raw $ shown separately)")
    L.append("| date | sess | n | raw | charitable | strict | delta(char-raw) | no-bars n | no-bars raw$ |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    deltas = []
    for d in days:
        for sess in ("RTH", "PRE"):
            s = [r for r in ok if r["date"] == d and r["session"] == sess]
            snb = [r for r in nb if r["date"] == d and r["session"] == sess]
            if not s and not snb: continue
            raw, ch, st = sums(s, "pnl_raw"), sums(s, "pnl_charitable"), sums(s, "pnl_strict")
            deltas.append((d, sess, round(ch - raw, 2)))
            L.append(f"| {d} | {sess} | {len(s)} | {raw:+.2f} | {ch:+.2f} | {st:+.2f} | {ch-raw:+.2f} | {len(snb)} | {sums(snb,'pnl_raw'):+.2f} |")
    L.append("")
    L.append("## Per-lane")
    L.append("| lane | n | raw | charitable | strict | fiction $ (char delta) |")
    L.append("|---|---|---|---|---|---|")
    lanes = sorted({r["lane"] for r in ok})
    for ln in lanes:
        s = [r for r in ok if r["lane"] == ln]
        raw, ch, st = sums(s, "pnl_raw"), sums(s, "pnl_charitable"), sums(s, "pnl_strict")
        L.append(f"| {ln} | {len(s)} | {raw:+.2f} | {ch:+.2f} | {st:+.2f} | {ch-raw:+.2f} |")
    L.append("")
    L.append("## Best days re-ranked (RTH, CHARITABLE)")
    dtot = {}
    for r in ok:
        if r["session"] == "RTH":
            dtot[r["date"]] = dtot.get(r["date"], 0) + r["pnl_charitable"]
    for d, v in sorted(dtot.items(), key=lambda x: -x[1])[:8]:
        raw = sums([r for r in ok if r["date"] == d and r["session"] == "RTH"], "pnl_raw")
        L.append(f"- {d}: charitable ${v:+.2f} (raw ${raw:+.2f})")
    L.append("")
    allfills = [f for r in ok for f in r["fills"]]
    ev = [r for r in ok if r["entry_verified"]]
    xv = [r for r in ok if r["exit_verified"]]
    L.append("## Component stats (verified-cohort)")
    L.append(f"- entries verified: {len(ev)}/{len(ok)} ({100*len(ev)/max(1,len(ok)):.1f}%)  [{sum(1 for r in ok if r['entry_ts_missing'])} lacked entry_ts_utc — whole-day window]")
    for cat in ("verified_strict", "verified_generous_only", "FICTION"):
        c = sum(1 for f in allfills if f["cat"] == cat)
        L.append(f"- fills {cat}: {c}/{len(allfills)} ({100*c/max(1,len(allfills)):.1f}%)")
    L.append(f"- exits verified: {len(xv)}/{len(ok)} ({100*len(xv)/max(1,len(ok)):.1f}%)")
    L.append("")
    L.append("## Unverifiable (no bars on either feed)")
    L.append(f"Total: {len(nb)} trades, raw ${sums(nb,'pnl_raw'):+.2f} — NOT in verified totals.")
    for r in nb:
        L.append(f"- {r['date']} {r['ticker']} {r['session']} {r['lane']} raw ${r['pnl_raw']:+.2f} ({r['trade_id'][:8]})")
    open("/Users/marcosolivera/Desktop/Marcos-Trading-Bot/data/history/VERIFIED_BOOK.md", "w").write("\n".join(L) + "\n")
    print("WROTE VERIFIED_BOOK.md/.json")
    print("\n".join(L[:40]))
    print("DELTAS>|20|:", [x for x in deltas if abs(x[2]) > 20])

if __name__ == "__main__":
    main()
