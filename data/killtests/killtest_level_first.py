"""KILL-TEST — LEVEL-FIRST ENTRY: arm at Kev's sheet level, enter on his confirmation.

Question (Marcos, 7/27 night): the bot knows the names and the levels the night before — would
entering Kev's way, AT the level, have paid? Tests the pattern-first vs level-first gap that cost
LVWR today (his 1.47→3.57 vs our three losses 76–86% above the break).

MECHANICAL TRANSLATION of his stated process (the test's main risk — his words, my numbers):
  "strong break over X, then confirm off pullbacks over VWAP and over Y, range to targets"
   1. ARM  — first 10s bar whose high >= BREAK (a day gapping open >= BREAK arms at the open).
   2. DIP  — after arming, a pullback of >= 2% from the post-arm high whose LOW holds at/above
             BOTH the CONFIRM level and the running session VWAP (his two conditions, verbatim).
   3. CURL — enter when a 10s bar CLOSES above the prior bar's high (the bought-back wick).
             Entry = that close. STOP = the dip low ("risking the bottom of that wick").
   4. One entry per (date,ticker); no re-entries in v1.
  Exits, the bot's own shape so dollars are comparable: half at +1R then stop->entry; remainder
  exits at +3R, at the BE stop, or at the 16:00 close — whichever first. Intrabar touch order
  inside one 10s bar resolves AGAINST the strategy (stop before target).
  Sizing = the live chain: shares = $30 / risk-per-share, notional-capped at $1,000, min 1 share.

Cohort: EVERY sheet ticker on 7/23, 7/24, 7/27 with 10s bars — the full population, no selection.
RTH-only entries (premarket entries are disabled live; the sim honors the live constraint).
"""
import json, pathlib, urllib.request
from datetime import datetime, timezone, timedelta

S = pathlib.Path("/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
DATES = ["2026-07-23", "2026-07-24", "2026-07-27"]
RISK, NOTIONAL_CAP = 30.0, 1000.0


def bars10(tkr, date):
    for sfx in ("~ALP10S", "~10S"):
        p = S / f"bars_{date}_{tkr}{sfx}.json"
        if not p.exists():
            try:
                d = json.loads(urllib.request.urlopen(
                    f"{U}/api/bars?date={date}&ticker={tkr}{sfx}", timeout=45).read())
            except Exception:
                continue
            p.write_text(json.dumps(d))
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        out = []
        for b in d.get("bars") or []:
            try:
                t = datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                et = t.astimezone(ET)
                out.append((et, float(b["open"]), float(b["high"]), float(b["low"]),
                            float(b["close"]), float(b.get("volume") or 0)))
            except Exception:
                pass
        if out:
            return sorted(out)
    return []


def simulate(bars, brk, confirm):
    """Returns (verdict, detail). Verdicts: no_break / no_confirm / trade(dict)."""
    armed = False; post_hi = 0.0
    dip_lo = None; dip_hi_bar = None
    cum_pv = cum_v = 0.0
    entry = None
    for i, (t, o, h, lo, c, v) in enumerate(bars):
        px = (h + lo + c) / 3.0
        cum_pv += px * v; cum_v += v
        vwap = cum_pv / cum_v if cum_v > 0 else c
        hm = t.strftime("%H:%M")
        if hm < "09:30":                                  # session VWAP builds from premarket,
            continue                                      # but entries are RTH-only (live rule)
        if hm >= "15:45":
            break
        if not armed:
            if h >= brk:
                armed = True; post_hi = h
            continue
        post_hi = max(post_hi, h)
        if entry is None:
            # track the dip: >=2% off the post-arm high, low holding confirm AND vwap
            if lo < post_hi * 0.98:
                if lo >= confirm and lo >= vwap:
                    if dip_lo is None or lo < dip_lo:
                        dip_lo = lo
                    # CURL: close above prior bar high while a valid dip exists
                    if dip_lo is not None and i > 0 and c > bars[i - 1][2]:
                        entry = dict(t=t, px=c, stop=dip_lo)
                        break
                else:
                    dip_lo = None                          # dip violated confirm/vwap — reset
    if not armed:
        return "no_break", None
    if entry is None:
        return "no_confirm", None
    # exits
    e, stp = entry["px"], entry["stop"]
    R = e - stp
    if R <= 0:
        return "no_confirm", None
    sh = max(1, min(int(RISK / R), int(NOTIONAL_CAP / e)))
    half = sh // 2 if sh >= 2 else 0
    rem = sh - half
    pnl = 0.0; banked_half = False; stop = stp
    seq = [b for b in bars if b[0] > entry["t"]]
    for t, o, h, lo, c, v in seq:
        if lo <= stop:                                     # stop first inside the bar (against us)
            pnl += (stop - e) * (rem if banked_half else sh)
            return "trade", dict(**entry, R=R, sh=sh, pnl=pnl, exit="stop", xt=t)
        if not banked_half and h >= e + R:
            pnl += R * half; banked_half = True; stop = e  # half at +1R, stop to entry
        if banked_half and h >= e + 3 * R:
            pnl += 3 * R * rem
            return "trade", dict(**entry, R=R, sh=sh, pnl=pnl, exit="+3R", xt=t)
    last = seq[-1][4] if seq else e
    pnl += (last - e) * (rem if banked_half else sh)
    return "trade", dict(**entry, R=R, sh=sh, pnl=pnl, exit="close", xt=seq[-1][0] if seq else entry["t"])


# ── run the full population ──────────────────────────────────────────────────
trades = json.loads((S / "trades.json").read_text())
trades = trades if isinstance(trades, list) else trades.get("trades", [])
bot_by_dt = {}
for t in trades:
    if t.get("date") in DATES and (t.get("entry_session") or "") != "PRE":
        bot_by_dt.setdefault((t["date"], t["ticker"]), 0.0)
        bot_by_dt[(t["date"], t["ticker"])] += float(t.get("pnl") or 0)

results, skipped = [], {"no_levels": 0, "no_bars": []}
for date in DATES:
    fn = S / ("kev27.json" if date == "2026-07-27" else f"kev_{date}.json")
    levels = json.loads(fn.read_text()).get("levels") or {}
    for tkr, lv in sorted(levels.items()):
        try:
            brk = float(lv.get("break") or 0)
            confirm = float(lv.get("confirm") or 0) or brk * 0.95   # no stated confirm → 5% band
        except (TypeError, ValueError):
            skipped["no_levels"] += 1; continue
        if brk <= 0:
            skipped["no_levels"] += 1; continue
        bars = bars10(tkr, date)
        if not bars:
            skipped["no_bars"].append(f"{date[5:]}_{tkr}"); continue
        verdict, d = simulate(bars, brk, confirm)
        results.append((date, tkr, brk, verdict, d))

n_nb = sum(1 for r in results if r[3] == "no_break")
n_nc = sum(1 for r in results if r[3] == "no_confirm")
tr = [r for r in results if r[3] == "trade"]
print(f"POPULATION: {len(results)} (date,ticker) sheet entries with 10s bars over {DATES}")
print(f"  no break of the level: {n_nb}  (no break, no trade — correctly stayed out)")
print(f"  broke but never confirmed: {n_nc}  (no confirmation, no trade)")
print(f"  TRADES TAKEN: {len(tr)}")
print(f"  skipped — no usable level: {skipped['no_levels']}, no 10s bars: {len(skipped['no_bars'])}")

print(f"\n{'date':6}{'tkr':6}{'break':>8}{'entry':>9}{'stop':>9}{'R/sh':>7}{'sh':>6}{'exit':>7}"
      f"{'P&L':>9}{'  bot same name':>15}")
print("=" * 92)
tot = bot_tot = 0.0
wins = 0
for date, tkr, brk, _, d in sorted(tr, key=lambda r: (r[0], r[1])):
    bot = bot_by_dt.get((date, tkr))
    tot += d["pnl"]; wins += d["pnl"] > 0
    print(f"{date[5:]:6}{tkr:6}{brk:8.2f}{d['px']:9.3f}{d['stop']:9.3f}{d['R']:7.3f}{d['sh']:6}"
          f"{d['exit']:>7}{d['pnl']:+9.2f}{('' if bot is None else f'{bot:+13.2f}'):>15}")
print("=" * 92)
overlap = [(dt, tk) for dt, tk, _, _, _ in [(r[0], r[1], 0, 0, 0) for r in tr] if (dt, tk) in bot_by_dt]
print(f"LEVEL-FIRST total: {tot:+.2f} on {len(tr)} trades ({wins} wins, "
      f"{wins/len(tr)*100 if tr else 0:.0f}%)")
print(f"BOT actual on the SAME (date,ticker)s it also traded: "
      f"{sum(bot_by_dt[k] for k in bot_by_dt if k in set((r[0], r[1]) for r in tr)):+.2f} "
      f"on {len([k for k in bot_by_dt if k in set((r[0], r[1]) for r in tr)])} names")
print(f"BOT actual across ALL {len(bot_by_dt)} traded names these 3 days: {sum(bot_by_dt.values()):+.2f}")
