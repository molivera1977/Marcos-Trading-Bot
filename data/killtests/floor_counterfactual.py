"""FLOOR COUNTERFACTUAL — the day, both ways, on a faithful exit engine.

Run any time: `python3 data/killtests/floor_counterfactual.py`
Auto-discovers every `minstop_reject` from the live decision log, replays each on real 10s tape
through the ACTUAL exit engine, and prints Reality A (floor on, what happened) vs Reality B
(floor off = A + the rejects).

ENGINE FIDELITY — every parameter read from the live config, not assumed:
  · sizing        RISK_PER_TRADE $30 / risk-per-share, capped at MAX_TRADE_DOLLARS $1,000, min 1 sh
  · tiers         SCALE_TIERS [(1R, 50% cum), (2R, 75% cum)] — quantity by CUMULATIVE target,
                  int(initial x cum) - already_sold, exactly as monitor_trade computes it
  · VELOCITY_RIDE defer a scale while price gained >= VELO_RIDE_PCT 12% over the last VELO_BARS 3
                  one-minute bars (live, and it materially changes when tiers fill)
  · BE floor      BE_FLOOR_AFTER_SCALE = 2 (the 7/28 revert) — stop to entry only after scale #2
  · stop          EXITS_ON_3MIN: a COMPLETED 3-min bar CLOSING at/below the stop. No intrabar stop
                  (INTRABAR_STOP=0, refuted 7/27).
  · health fold   RUNNER_HEALTH_EXIT + HEALTH_VWAP_SESSION: after >=1 partial, fold when a 3-min
                  close is below BOTH the 3-min EMA9 and the SESSION VWAP (premarket-anchored)
  · cadence       exits are evaluated on the ~60s EMA_CHECK_INTERVAL, NOT every 10s bar — tiers
                  fill on the live stream price (10s), stop/fold only at the check
  · flatten       TRADE_WINDOW_END 15:45 force close
  · capital       no cap: the settled-capital break is `if not DRY_RUN`, so DRY_RUN never stops;
                  reservations release on exit; there is no concurrency limit in the code
  · HELD LOCK     a name with an OPEN position is skipped by the watch loop entirely
                  (marcos_trading_bot.py:5502 — `t in reentry["held"] -> continue`). Enforced here
                  CHRONOLOGICALLY across BOTH books: a reject cannot enter a name already held, and
                  in Reality B a reject that holds a name BLOCKS the real trade that came later in
                  the same name (KVAC 10:18 reject would have blocked the real 10:29 entry).

KNOWN LIMITS (stated, not hidden): fills are at the tier/stop price with NO slippage — today's real
trades ran 1.04-1.20R against plan, so losers here are optimistic by roughly that margin. Open
positions are marked at last trade. Entry assumes the reject price was fillable.
"""
import json, sys, urllib.request
from datetime import datetime, timezone, timedelta

U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now(ET).strftime("%Y-%m-%d")

RISK_PER_TRADE, MAX_TRADE_DOLLARS = 30.0, 1000.0
SIM_ACCOUNT = 3000.0          # settled pool; reservations release on exit (NOT DRY_RUN-gated — :8188)
MOMENTUM_BARS = 3
MOMENTUM_MIN_AVG_VOL = 10_000
EXPANSION_MIN, PEAK_REL_MIN = 1.5, 0.30   # live values (:486, :489)
TOPPING_TAIL_RATIO = 0.55
SCALE_TIERS = [(1.0, 0.50), (2.0, 0.75)]
BE_FLOOR_AFTER_SCALE = 2
VELO_RIDE_PCT, VELO_BARS = 0.12, 3
EMA_CHECK_SECS = 60
FLATTEN = "15:45"


def get(path):
    with urllib.request.urlopen(U + path, timeout=60) as r:
        return json.loads(r.read())


def bars10(tk):
    for sfx in ("~ALP10S", "~10S"):
        try:
            d = get(f"/api/bars?date={DATE}&ticker={tk}{sfx}")
        except Exception:
            continue
        out = []
        for b in d.get("bars") or []:
            try:
                t = datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S").replace(
                    tzinfo=timezone.utc).astimezone(ET)
                out.append((t, float(b["open"]), float(b["high"]), float(b["low"]),
                            float(b["close"]), float(b.get("volume") or 0)))
            except Exception:
                pass
        if out:
            return sorted(out)
    return []


def roll(seq, minutes):
    """10s bars -> N-minute bars, keyed by bucket start."""
    d = {}
    for t, o, h, l, c, v in seq:
        k = t.replace(second=0, microsecond=0)
        k = k.replace(minute=k.minute - k.minute % minutes)
        if k not in d:
            d[k] = [o, h, l, c, v]
        else:
            d[k][1] = max(d[k][1], h); d[k][2] = min(d[k][2], l); d[k][3] = c; d[k][4] += v
    return [(k, *vals) for k, vals in sorted(d.items())]


def momentum_ok(bs, fire_hms):
    """Replay check_momentum's THREE HARD rejects on 1-min bars as of the fire instant:
    (1) liquidity floor avg vol < 10k/bar, (2) topping tail on the last completed bar,
    (3) no volume build (expansion < 1.5x base OR peak-relative < 15%).
    Returns (ok, reason). This resolves the post-floor momentum gate instead of assuming it."""
    t0 = datetime.strptime(fire_hms, "%H:%M:%S").time()
    upto = [b for b in bs if b[0].time() <= t0]
    if len(upto) < 30:
        return True, ""                       # not enough tape to judge — fail open, as the bot does
    m1 = roll(upto, 1)
    if len(m1) < MOMENTUM_BARS + 2:
        return True, ""
    comp = m1[:-1]                            # completed bars only
    vols = [b[5] for b in comp][-MOMENTUM_BARS:]
    avg_vol = sum(vols) / len(vols) if vols else 0
    if avg_vol < MOMENTUM_MIN_AVG_VOL:
        return False, f"illiquid {avg_vol:,.0f}/bar < 10k"
    last = comp[-1]
    rng = last[2] - last[3]
    if rng > 0 and (last[2] - last[4]) / rng >= TOPPING_TAIL_RATIO:
        return False, "topping tail"
    brk = comp[-1][5]
    pvs = [b[5] for b in comp[-(MOMENTUM_BARS + 1):-1]]
    pav = sum(pvs) / len(pvs) if pvs else 0
    expansion = (brk / pav) if pav > 0 else 999.0
    peak = max((b[5] for b in comp), default=0)
    peak_rel = (brk / peak) if peak > 0 else 1.0
    if pvs and not (expansion >= EXPANSION_MIN and peak_rel >= PEAK_REL_MIN):
        return False, f"no build {expansion:.1f}x/{peak_rel*100:.0f}%peak"
    return True, ""


def simulate(tk, fire_hms, entry, width_pct):
    """Replay one rejected entry through the live exit engine. Returns dict or None."""
    bs = bars10(tk)
    if not bs:
        return None
    # session VWAP, premarket-anchored, running
    pv = vol = 0.0
    vwap_at = {}
    for t, o, h, l, c, v in bs:
        pv += ((h + l + c) / 3) * v; vol += v
        vwap_at[t] = pv / vol if vol else c
    t0 = datetime.strptime(fire_hms, "%H:%M:%S").time()
    seq = [b for b in bs if b[0].time() >= t0]
    if not seq:
        return None

    R = entry * width_pct / 100.0
    stop = entry - R
    shares = max(1, min(int(RISK_PER_TRADE / R), int(MAX_TRADE_DOLLARS / entry)))
    initial, rem = shares, shares
    tier_idx = 0; banked = 0.0; partials = []; note = []
    m1 = roll(seq, 1); m3 = roll(seq, 3)
    last_check = seq[0][0]

    for ts, o, h, l, c, v in seq:
        if ts.strftime("%H:%M") >= FLATTEN:
            note.append(f"15:45 flat")
            return dict(tk=tk, t=fire_hms, entry=entry, w=width_pct, sh=initial,
                        pnl=banked + (c - entry) * rem, note=" ".join(note), open=False)

        # ── TIERS: fill on the live (10s) price, deferred while accelerating ──
        if tier_idx < len(SCALE_TIERS) and rem > 0:
            rmult, cum = SCALE_TIERS[tier_idx]
            tier_px = entry + rmult * R
            if h >= tier_px:
                # VELOCITY_RIDE: gained >= 12% over the last 3 completed 1-min bars?
                prior = [x for x in m1 if x[0] < ts.replace(second=0, microsecond=0)]
                defer = False
                if len(prior) > VELO_BARS:
                    c_now, c_ago = prior[-1][4], prior[-1 - VELO_BARS][4]
                    if c_ago > 0 and (c_now - c_ago) / c_ago >= VELO_RIDE_PCT:
                        defer = True
                        if "ride" not in note:
                            note.append("ride")
                if not defer:
                    sold_so_far = initial - rem
                    target_sold = int(initial * cum)
                    qty = min(max(1, target_sold - sold_so_far), rem)
                    banked += (tier_px - entry) * qty
                    partials.append((qty, tier_px)); rem -= qty; tier_idx += 1
                    note.append(f"{rmult:.0f}R×{qty}")
                    if tier_idx >= BE_FLOOR_AFTER_SCALE:
                        stop = entry; note.append("→BE")
                    if rem <= 0:
                        return dict(tk=tk, t=fire_hms, entry=entry, w=width_pct, sh=initial,
                                    pnl=banked, note=" ".join(note) + " full exit", open=False)

        # ── STOP / HEALTH FOLD: only evaluated on the ~60s check cadence ──
        if (ts - last_check).total_seconds() < EMA_CHECK_SECS:
            continue
        last_check = ts
        k3 = ts.replace(second=0, microsecond=0); k3 = k3.replace(minute=k3.minute - k3.minute % 3)
        done3 = [x for x in m3 if x[0] < k3]
        if len(done3) < 2:
            continue
        closes = [x[4] for x in done3]
        ema9 = closes[0]
        for cl in closes[1:]:
            ema9 = cl * (2 / (9 + 1)) + ema9 * (1 - 2 / (9 + 1))
        last3 = done3[-1]
        if rem > 0 and last3[4] <= stop:
            return dict(tk=tk, t=fire_hms, entry=entry, w=width_pct, sh=initial,
                        pnl=banked + (c - entry) * rem,
                        note=" ".join(note) + f" STOP {ts.strftime('%H:%M')}", open=False)
        if rem > 0 and partials and last3[4] < ema9 and last3[4] < vwap_at.get(last3[0], c):
            return dict(tk=tk, t=fire_hms, entry=entry, w=width_pct, sh=initial,
                        pnl=banked + (c - entry) * rem,
                        note=" ".join(note) + f" FOLD {ts.strftime('%H:%M')}", open=False)

    last = seq[-1]
    return dict(tk=tk, t=fire_hms, entry=entry, w=width_pct, sh=initial,
                pnl=banked + (last[4] - entry) * rem,
                note=" ".join(note) + f" open@{last[0].strftime('%H:%M')}", open=True)


# ── gather the day ───────────────────────────────────────────────────────────
dec = get(f"/api/decisions_archive?date={DATE}")
dec = dec if isinstance(dec, list) else dec.get("rows", [])
rejects = [r for r in dec if r.get("status") == "minstop_reject"]

trades = get("/api/trades"); trades = trades if isinstance(trades, list) else trades.get("trades", [])
closed = [t for t in trades if t.get("date") == DATE]
opens = get("/api/open_trades").get("open_trades", [])

closed_pnl = sum(float(t.get("pnl") or 0) for t in closed)
open_pnl = 0.0
for x in opens:
    e = x["entry_price"]
    open_pnl += sum((p - e) * q for q, p in (x.get("partial_fills") or []))
    open_pnl += ((x.get("last_price") or e) - e) * (x.get("remaining_shares") or 0)

print(f"FLOOR COUNTERFACTUAL — {DATE}   (generated {datetime.now(ET).strftime('%H:%M:%S')} ET)")
print("=" * 104)
print("REALITY A — floor ON (what actually happened)")
print(f"{'  time':8}{'ticker':7}{'lane':14}{'entry':>9}{'exit':>9}{'P&L':>10}  reason")
for t in sorted(closed, key=lambda x: x.get("recorded_at") or ""):
    print(f"  {(t.get('recorded_at') or '')[11:16]:6}{t['ticker']:7}{(t.get('entry_type') or '?'):14}"
          f"{float(t['entry']):9.3f}{float(t['exit']):9.3f}{float(t.get('pnl') or 0):+10.2f}  {t.get('exit_reason')}")
for x in opens:
    e = x["entry_price"]
    p = sum((pp - e) * q for q, pp in (x.get("partial_fills") or [])) + \
        ((x.get("last_price") or e) - e) * (x.get("remaining_shares") or 0)
    print(f"  {x.get('entry_time','')[:5]:6}{x['ticker']:7}{(x.get('entry_type') or '?'):14}"
          f"{e:9.3f}{(x.get('last_price') or 0):9.3f}{p:+10.2f}  OPEN")
print(f"{'':47}{'-' * 10}")
print(f"  {'A NET':41}{closed_pnl + open_pnl:+10.2f}   ({len(closed)} closed, {len(opens)} open)")

print()
print(f"REALITY B — floor OFF (A plus the {len(rejects)} it refused)")
print(f"{'  time':8}{'ticker':7}{'band':6}{'w%':>7}{'entry':>9}{'P&L':>10}  path")
tot = 0.0; bands = {}
held_until = {}          # ticker -> HH:MM:SS the position closes (the reentry["held"] lock)
reserved = {}            # ticker -> notional reserved (released when the position closes)
blocked_real = []        # real trades Reality B could NOT have taken (name already held by a reject)

# real entries, so a reject holding a name can block them in Reality B
real_entries = []
for t in closed:
    real_entries.append((t["ticker"], (t.get("entry_ts_utc") or "")[11:19] or (t.get("recorded_at") or "")[11:19],
                         float(t.get("pnl") or 0), "closed"))
for x in opens:
    e = x["entry_price"]
    p = sum((pp - e) * q for q, pp in (x.get("partial_fills") or [])) + \
        ((x.get("last_price") or e) - e) * (x.get("remaining_shares") or 0)
    hh = x.get("entry_ts_utc") or ""
    real_entries.append((x["ticker"], hh[11:19] if hh else "00:00:00", p, "open"))

def to_et(utc_hms):
    """entry_ts_utc is UTC; ET = UTC-4 today."""
    try:
        h, m, s2 = (int(v) for v in utc_hms.split(":"))
        return f"{(h-4)%24:02d}:{m:02d}:{s2:02d}"
    except Exception:
        return utc_hms

for r in sorted(rejects, key=lambda x: x.get("recorded_at") or ""):
    hms = (r.get("recorded_at") or "")[11:19]
    tk = r["ticker"]
    if tk in held_until and hms < held_until[tk]:
        print(f"  {hms[:5]:6}{tk:7}{str(r.get('band')):6}{'':7}{float(r.get('price') or 0):9.3f}"
              f"{'—':>10}  BLOCKED — position already held until {held_until[tk][:5]}")
        continue
    _bs = bars10(tk)
    _mok, _mwhy = momentum_ok(_bs, hms) if _bs else (True, "")
    if not _mok:
        print(f"  {hms[:5]:6}{tk:7}{str(r.get('band')):6}{'':7}{float(r.get('price') or 0):9.3f}"
              f"{'—':>10}  MOMENTUM REJECT ({_mwhy}) — the post-floor gate would have refused it anyway")
        continue
    _px = float(r.get("price") or 0); _w = float(r.get("stop_width_pct") or 0)
    _R = _px * _w / 100.0
    _sh = max(1, min(int(RISK_PER_TRADE / _R), int(MAX_TRADE_DOLLARS / _px))) if _R > 0 else 0
    _need = round(_sh * _px, 2)
    _free = SIM_ACCOUNT - sum(v for v in reserved.values())
    if _need > _free:
        print(f"  {hms[:5]:6}{tk:7}{str(r.get('band')):6}{'':7}{_px:9.3f}"
              f"{'—':>10}  NO CAPITAL — needs ${_need:.0f}, ${_free:.0f} free")
        continue
    res = simulate(tk, hms, _px, _w)
    if not res:
        print(f"  {hms[:5]:6}{tk:7}{str(r.get('band')):6}{'':7}{float(r.get('price') or 0):9.3f}"
              f"{'—':>10}  no bars"); continue
    # record the hold window: exit time parsed out of the note, else end-of-data
    import re as _re
    m = _re.search(r"(?:STOP|FOLD|flat|open@)\s*(\d\d:\d\d)", res["note"])
    held_until[tk] = (m.group(1) + ":59") if m else "23:59:59"
    # does this hold block a REAL trade in the same name that came later?
    for rtk, rt_utc, rpnl, kind in real_entries:
        if rtk == tk:
            ret = to_et(rt_utc)
            if hms < ret < held_until[tk] and (rtk, ret) not in [b[:2] for b in blocked_real]:
                blocked_real.append((rtk, ret, rpnl, kind))
    reserved = {k: v for k, v in reserved.items() if held_until.get(k, "00:00:00") > hms}
    reserved[tk] = _need
    tot += res["pnl"]; b = str(r.get("band")); bands[b] = bands.get(b, 0.0) + res["pnl"]
    print(f"  {hms[:5]:6}{res['tk']:7}{b:6}{res['w']:6.2f}%{res['entry']:9.3f}{res['pnl']:+10.2f}  {res['note']}")

if blocked_real:
    print()
    print("  ⚠ REAL trades Reality B could NOT have taken (name already held by a reject):")
    for rtk, ret, rpnl, kind in blocked_real:
        print(f"      {ret[:5]} {rtk:6} {rpnl:+8.2f} ({kind}) — REMOVED from B")
print(f"{'':47}{'-' * 10}")
print(f"  {'rejects':41}{tot:+10.2f}")
_blocked_sum = sum(b[2] for b in blocked_real)
b_net = closed_pnl + open_pnl + tot - _blocked_sum
if blocked_real:
    print(f"  {'A minus blocked-in-B':41}{closed_pnl + open_pnl - _blocked_sum:+10.2f}")
print(f"  {'B NET (A - blocked + rejects)':41}{b_net:+10.2f}")
print()
print(f"  by band: " + " · ".join(f"{k} {v:+.2f}" for k, v in sorted(bands.items())))
print("=" * 104)
print(f"  A (floor ON):  {closed_pnl + open_pnl:+8.2f}")
print(f"  B (floor OFF): {b_net:+8.2f}")
print(f"  FLOOR'S COST:  {closed_pnl + open_pnl - b_net:+8.2f}")
print("=" * 104)
print("  fills have NO slippage (real trades today ran 1.04-1.20R vs plan) · opens marked at last")
