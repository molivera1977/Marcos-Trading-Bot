#!/usr/bin/env python3
"""FOUR-ARM HIDDEN-EXIT COMPARISON — v4 (2026-08-13, TIMING-CORRECTED edition).

WHY v4 (prescribed by the 8/13 full-room v3 verification):
v3 FAILED its gate (-246.9%) because its benchmark — the price-corrected book
($649.84) — removed only PRICE overage on fictional fills.  Fills that printed
instantly on PRE-ENTRY tape at prices the stock DID later reach post-entry kept
full credit, even when the honest (fixed) bot would have been stopped out
BEFORE the tape first touched the fill price.  v4 builds the TIMING-CORRECTED
BENCHMARK: the two-stage sequence test (first post-entry touch of each recorded
fill px vs the honest intrabar stop-fire time) extended to ALL trades; any fill
whose first touch postdates the honest stop-fire is TIMING-FICTION — its
banked profit is removed and those shares exit at the stop instead.
v4 also kills v3's known pessimism: stops fire INTRABAR (first 10s bar low <=
stop), matching INTRABAR_STOP=1 verified on the live env this session.

ASSUMPTIONS (stated up front, all of them):
 A1. Read-only replay; sizing = each trade's REAL shares; dollars end-to-end.
 A2. Path = full-day 10s bars (~10S pref, ~ALP10S fallback), post-entry slice
     from entry_ts_utc.  Bars reused from the v3/v2 caches (immutable
     history); trades + kev map REFETCHED FRESH this run.
 A3. Recorded fills = trade['partial_fills'] [[qty, px], ...]; the runner leg
     = shares - sum(partial qty), exiting at the recorded exit px.  Recorded
     pnl is reproduced from these legs before any correction (reconciliation
     printed; small rounding deltas absorbed into the runner leg).
 A4. BENCHMARK stop trajectory (honest fixed bot): starts at the trade's
     recorded stop_loss; INTRABAR fire = first 10s bar low <= effective stop.
     Live trail mechanics: a recorded fill 'scales' at its first post-entry
     touch time; after >= 2 scales the stop floors at breakeven (entry) and
     ratchets to the scale bar's low if higher; after the first scale, RUNG
     RATCHET floors rise on 1-min closes above map rungs; effective stop =
     max(trailing stop, rung floor).
 A5. Same-bar tie: if a fill's first touch and the stop-fire land on the SAME
     10s bar, the touch is counted FIRST (favor the fill — makes the
     benchmark an upper bound on that bar, stated not hidden).
 A6. TIMING-FICTION fill = first touch strictly after stop-fire, or never
     touched at all.  Its shares exit at the effective stop at fire time,
     price = stop * (1 - slip), slip = min(3%, max(0.8%, est_slippage/100));
     no est_slippage recorded -> 3%.
 A7. Trades with NO post-entry 10s bars keep their recorded pnl in the
     benchmark (uncorrectable without tape; counted and reported).
 A8. MODEL (all arms): identical to v3's live-trail replay EXCEPT stops fire
     INTRABAR — first 10s bar low <= effective stop, exit at the stop px
     * (1 - slip) (same slippage model).  Health fold still evaluates on
     3-min closes (that check IS a close-based rule live).  Tier fills =
     post-entry tape strictly THROUGH the level, fill AT it.  Within a bar
     the order is: tier fills (tape_hi from this bar's high), then stop.
 A9. Rung ladder = current _levels snapshot; intraday map refreshes NOT
     reconstructed (known fidelity gap, both directions).
 A10. Slippage STRESS run: every model exit fill price * 0.99.
 A11. No commissions/borrow.  census_lib.to24 imported (12-hour store law);
     no decision rows consumed — trades carry ISO timestamps.
 A12. CALIBRATION GATE: arm-3 total within +/-20% of the timing-corrected
     benchmark AND median |per-trade error| <= $15.  Fail -> STOP, top-5
     divergences with hypotheses, four-arm numbers WITHHELD.

Read-only vs live services.  Results -> hidden_exit_fourarm_v4_20260813_RESULTS.txt.
NO recommendation — the full room verifies after this run; Marcos decides.
"""
import json, os, sys, shutil, urllib.request, urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo('America/New_York')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from census_lib import to24, BASE  # noqa: F401  (to24 = 12-hour store law)

V2CACHE = os.path.join(HERE, '.fourarm_cache_v2_20260813')
V3CACHE = os.path.join(HERE, '.fourarm_cache_v3_20260813')
CACHE = os.path.join(HERE, '.fourarm_cache_v4_20260813')
os.makedirs(CACHE, exist_ok=True)
for src in (V3CACHE, V2CACHE):
    if os.path.isdir(src):
        for fn in os.listdir(src):
            if fn.startswith('bars_') and not os.path.exists(os.path.join(CACHE, fn)):
                shutil.copy(os.path.join(src, fn), os.path.join(CACHE, fn))
for fn in ('trades.json', 'kev.json'):
    p = os.path.join(CACHE, fn)
    if os.path.exists(p):
        os.remove(p)

OUT = os.path.join(HERE, 'hidden_exit_fourarm_v4_20260813_RESULTS.txt')
START, END = '2026-07-24', '2026-08-13'
HIDDEN_TRIM_R = 1.0
BE_FLOOR_AFTER_SCALE = 2
RAW_REF, PRICE_CORR_REF = 880.99, 649.84


def get(url, cache_key):
    p = os.path.join(CACHE, cache_key)
    if os.path.exists(p):
        return json.load(open(p))
    try:
        d = json.load(urllib.request.urlopen(url, timeout=45))
    except Exception:
        d = None
    json.dump(d, open(p, 'w'))
    return d


def parse_ts(s):
    if not s:
        return None
    s = s.replace('Z', '+00:00').replace('+0000', '+00:00')
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def get_bars(ticker, date):
    for suf in ('~10S', '~ALP10S'):
        key = f'bars_{ticker}{suf}_{date}.json'
        d = get(f'{BASE}/api/bars?ticker={urllib.parse.quote(ticker + suf)}&date={date}', key)
        bars = (d or {}).get('bars') or []
        out = []
        for b in bars:
            t = parse_ts(b['time'])
            if t is None:
                continue
            out.append((t, float(b['open']), float(b['high']), float(b['low']),
                        float(b['close']), float(b.get('volume') or 0)))
        if len(out) >= 3:
            return out
    return None


def trade_slip(t):
    es = t.get('est_slippage')
    try:
        es = float(es)
    except (TypeError, ValueError):
        es = None
    if es is None:
        return 0.03
    return min(0.03, max(0.008, es / 100.0))


def map_rungs(levels_by_date, t):
    d = (levels_by_date.get(t['date']) or {}).get(t['ticker'])
    if not d:
        return None
    lv = set()
    for x in (d.get('targets') or []):
        try:
            lv.add(float(x))
        except (TypeError, ValueError):
            pass
    for k in ('next_supply', 'break'):
        try:
            v = float(d.get(k) or 0)
            if v > 0:
                lv.add(v)
        except (TypeError, ValueError):
            pass
    return sorted(v for v in lv if v > t['entry'] * 1.001)


def level_targets(levels_by_date, t):
    d = (levels_by_date.get(t['date']) or {}).get(t['ticker'])
    if not d:
        return None
    lv = []
    for x in (d.get('targets') or []):
        try:
            lv.append(float(x))
        except (TypeError, ValueError):
            pass
    try:
        ns = float(d.get('next_supply') or 0)
        if ns > 0:
            lv.append(ns)
    except (TypeError, ValueError):
        pass
    return sorted({v for v in lv if v > t['entry'] * 1.001})


class MinuteAgg:
    def __init__(self, n_min):
        self.n = n_min
        self.key = None
        self.cur = None
        self.completed = []

    def push(self, ts, o, h, l, c, v=0.0):
        k = (ts.date(), ts.hour * 60 + ts.minute - (ts.minute % self.n))
        done = None
        if k != self.key:
            if self.cur is not None:
                done = tuple(self.cur)
                self.completed.append(done)
            self.key, self.cur = k, [o, h, l, c, v]
        else:
            self.cur[1] = max(self.cur[1], h)
            self.cur[2] = min(self.cur[2], l)
            self.cur[3] = c
            self.cur[4] += v
        return done


def ema9(closes):
    if len(closes) < 2:
        return 0.0
    k = 2.0 / (9 + 1)
    e = closes[0]
    for c in closes[1:]:
        e = c * k + e * (1 - k)
    return e


# ---------------------------------------------------------------------------
# 1) TIMING-CORRECTED BENCHMARK (the room's two-stage sequence test, all trades)
# ---------------------------------------------------------------------------
def benchmark_trade(t, path, t_ent, rungs, slip):
    """Return (bench_pnl, detail dict).  See assumptions A3-A7."""
    entry, shares = t['entry'], float(t['shares'])
    pf = [(float(q), float(px)) for q, px in (t.get('partial_fills') or [])]
    runner_qty = shares - sum(q for q, _ in pf)
    post = [b for b in path if b[0] >= t_ent] if (path and t_ent) else []
    detail = {'fiction': [], 'kept': [], 'runner_qty': runner_qty,
              'stop_fire': None, 'stop_px': None, 'no_bars': not post}
    if not post:
        return t['pnl'], detail  # A7

    # first post-entry touch time (bar index) per recorded fill
    touch_idx = []
    for q, px in pf:
        idx = None
        for i, b in enumerate(post):
            if b[2] >= px:          # bar high touches fill px
                idx = i
                break
        touch_idx.append(idx)       # None = never touched

    # honest stop trajectory with intrabar fire (A4)
    stop0 = t.get('stop_loss') or entry * 0.94
    current_stop, floor = stop0, 0.0
    scales = 0
    m1 = MinuteAgg(1)
    # order fills by touch index for scale accounting
    order = sorted((ix, j) for j, ix in enumerate(touch_idx) if ix is not None)
    fire_idx, fire_stop = None, None
    oi = 0
    for i, (ts, o, h, l, c, v) in enumerate(post):
        # A5: same-bar tie -> touches (scales) count first
        while oi < len(order) and order[oi][0] == i:
            scales += 1
            if scales >= BE_FLOOR_AFTER_SCALE:
                current_stop = max(current_stop, entry)
            if l > current_stop:
                current_stop = l
            oi += 1
        eff = max(current_stop, floor if scales > 0 else 0.0)
        if l <= eff:
            fire_idx, fire_stop = i, eff
            break
        b1 = m1.push(ts, o, h, l, c, v)
        if b1 is not None and scales > 0:
            for r in rungs:
                if b1[3] > r > floor:
                    floor = r
    detail['stop_fire'] = post[fire_idx][0] if fire_idx is not None else None
    detail['stop_px'] = fire_stop

    # classify fills; fiction shares exit at the stop (A6)
    pnl = 0.0
    for j, (q, px) in enumerate(pf):
        ti = touch_idx[j]
        honest = ti is not None and (fire_idx is None or ti <= fire_idx)
        if honest:
            pnl += q * (px - entry)
            detail['kept'].append((q, px))
        else:
            exit_px = (fire_stop if fire_stop is not None else stop0) * (1 - slip)
            pnl += q * (exit_px - entry)
            detail['fiction'].append((q, px, exit_px))
    if runner_qty > 0:
        pnl += runner_qty * (t['exit'] - entry)   # runner leg at recorded exit (A3)
    return pnl, detail


# ---------------------------------------------------------------------------
# 2) MODEL replay — v3 live trail, INTRABAR stops (A8)
# ---------------------------------------------------------------------------
def live_replay(t, tiers, rungs, day_bars, t_ent, slip, stress=0.0):
    entry, shares = t['entry'], float(t['shares'])
    stop0 = t.get('stop_loss') or entry * 0.94
    remaining, sold_cum = shares, 0.0
    tier_idx, partial_taken = 0, False
    current_stop, floor = stop0, 0.0
    path = [b for b in day_bars if b[0] >= t_ent]
    tape_hi = None
    is_pre = (t.get('entry_session') == 'PRE')
    m1, m3 = MinuteAgg(1), MinuteAgg(3)
    m1v = []
    fills = []

    def sell(label, qty, px):
        nonlocal remaining
        qty = min(qty, remaining)
        if qty <= 0:
            return
        fills.append((label, qty, px * (1.0 - stress)))
        remaining -= qty

    for ts, o, h, l, c, v in path:
        if remaining <= 0:
            break
        et = ts.astimezone(EASTERN_TZ)
        et_min = et.hour * 60 + et.minute
        if is_pre and et_min >= 9 * 60 + 25:
            sell('time_stop_925@%.4f' % o, remaining, o)
            break
        if et_min >= 15 * 60 + 45:
            sell('time_stop_1545@%.4f' % o, remaining, o)
            break
        tape_hi = h if tape_hi is None else max(tape_hi, h)
        # 1) resting-bank tier fills (post-entry tape strictly through the level)
        while tier_idx < len(tiers) and remaining > 0:
            tp, cum = tiers[tier_idx]
            if tape_hi > tp:
                qty = shares if cum >= 1.0 else max(1.0, shares * cum - sold_cum)
                qty = min(qty, remaining)
                sell(f'tier{tier_idx+1}@{tp:.4f}', qty, tp)
                sold_cum += qty
                tier_idx += 1
                partial_taken = True
                if tier_idx >= BE_FLOOR_AFTER_SCALE:
                    current_stop = max(current_stop, entry)
                if l > current_stop:
                    current_stop = l
            else:
                break
        if remaining <= 0:
            break
        # 2) INTRABAR stop (v4): first 10s bar low <= effective stop
        eff = max(current_stop, floor if partial_taken else 0.0)
        if l <= eff:
            lbl = ('rung_ratchet' if (partial_taken and floor >= current_stop and floor > 0)
                   else ('trail_stop' if partial_taken else 'stop_loss'))
            sell(f'{lbl}@{eff:.4f}(intrabar)', remaining, eff * (1 - slip))
            break
        # 3) completed 1-min bar -> rung clears + VWAP window
        b1 = m1.push(ts, o, h, l, c, v)
        if b1 is not None:
            m1v.append((b1[3], b1[4]))
            if partial_taken:
                for r in rungs:
                    if b1[3] > r > floor:
                        floor = r
        # 4) completed 3-min bar -> health fold (close-based rule, unchanged)
        b3 = m3.push(ts, o, h, l, c, v)
        if b3 is not None:
            c3 = b3[3]
            if partial_taken and len(m3.completed) >= 3:
                e9 = ema9([b[3] for b in m3.completed[-12:]])
                w = m1v[-45:]
                vsum = sum(x[1] for x in w)
                vw = (sum(x[0] * x[1] for x in w) / vsum) if vsum > 0 else 0.0
                if e9 > 0 and vw > 0 and c3 < e9 and c3 < vw:
                    sell(f'health_fold@{c3:.4f}', remaining, c3)
                    break
    if remaining > 0:
        px = path[-1][4] if path else entry
        sell('end-of-tape@%.4f' % px, remaining, px)
    pnl = sum(q * (p - entry) for _, q, p in fills)
    return pnl, fills


def three_point_replay(t, tiers, real_exit, post_hi, stress=0.0):
    entry, shares = t['entry'], float(t['shares'])
    hi = post_hi if post_hi is not None else (t.get('highest') or entry)
    remaining, sold_cum = shares, 0.0
    fills = []
    for i, (tp, cum) in enumerate(tiers):
        if hi > tp and remaining > 0:
            qty = shares if cum >= 1.0 else max(1.0, shares * cum - sold_cum)
            qty = min(qty, remaining)
            fills.append((f'tier{i+1}@{tp:.4f}', qty, tp * (1 - stress)))
            sold_cum += qty
            remaining -= qty
    if remaining > 0:
        fills.append(('3pt(real exit)', remaining, real_exit * (1 - stress)))
    pnl = sum(q * (p - entry) for _, q, p in fills)
    return pnl, fills


def live_tiers(t):
    entry = t['entry']
    R = max(entry - (t.get('stop_loss') or entry * 0.94), 0.01)
    raw = [(round(entry + HIDDEN_TRIM_R * R, 4), 0.33),
           (round(entry * 1.50, 4), 0.55),
           (round(entry * 2.00, 4), 0.75)]
    out, cum = [], 0.0
    for p, cfr in sorted(raw, key=lambda x: x[0]):
        if cfr <= cum:
            continue
        cum = cfr
        out.append((p, cfr))
    return out


def run():
    trades_doc = get(f'{BASE}/api/trades', 'trades.json')
    kev = get(f'{BASE}/api/kev_watchlist', 'kev.json')
    levels_by_date = kev.get('_levels', {}) if isinstance(kev, dict) else {}

    cohort = [t for t in trades_doc['trades']
              if t.get('entry_type') == 'hidden_entry' and START <= t['date'] <= END]
    cohort.sort(key=lambda t: (t['date'], t.get('entry_ts_utc') or ''))
    raw_total = sum(t['pnl'] for t in cohort)
    print('Cohort N=%d, raw book $%.2f' % (len(cohort), raw_total), flush=True)

    # ---- prep + TIMING-CORRECTED BENCHMARK ----
    prep = []
    fidelity_count = {'bars': 0, '3pt': 0}
    bench_total = 0.0
    bench_by_day = defaultdict(float)
    raw_by_day = defaultdict(float)
    fiction_fills = 0
    fiction_trades = 0
    nobars_pf = 0
    recon_gap = 0.0
    for i, t in enumerate(cohort):
        t_ent = parse_ts(t.get('entry_ts_utc'))
        path = get_bars(t['ticker'], t['date']) if t_ent else None
        if path and not any(b[0] >= t_ent for b in path):
            path = None
        fid = 'bars' if path else '3pt'
        fidelity_count[fid] += 1
        rungs = map_rungs(levels_by_date, t) or []
        slip = trade_slip(t)
        # reconciliation: recorded legs -> recorded pnl (A3)
        pf = [(float(q), float(px)) for q, px in (t.get('partial_fills') or [])]
        legs = sum(q * (px - t['entry']) for q, px in pf) + \
            (t['shares'] - sum(q for q, _ in pf)) * (t['exit'] - t['entry'])
        recon_gap += abs(legs - t['pnl'])
        bpnl, det = benchmark_trade(t, path, t_ent, rungs, slip)
        if fid == '3pt' and pf:
            nobars_pf += 1
        fiction_fills += len(det['fiction'])
        if det['fiction']:
            fiction_trades += 1
        bench_total += bpnl
        bench_by_day[t['date']] += bpnl
        raw_by_day[t['date']] += t['pnl']
        prep.append({'t': t, 'path': path, 'fid': fid, 't_ent': t_ent,
                     'rungs': rungs, 'lv': level_targets(levels_by_date, t),
                     'slip': slip, 'bpnl': bpnl, 'bdet': det})
        if (i + 1) % 10 == 0:
            print('  benchmark: %d/%d trades done (running bench $%.2f)'
                  % (i + 1, len(cohort), bench_total), flush=True)

    def replay_arm(p, tiers, stress=0.0):
        t = p['t']
        if p['path']:
            return live_replay(t, tiers, p['rungs'], p['path'], p['t_ent'],
                               p['slip'], stress)
        return three_point_replay(t, tiers, t['exit'], None, stress)

    # ---- CALIBRATION GATE (A12): arm-3 vs TIMING-CORRECTED benchmark ----
    cal_rows = []
    for i, p in enumerate(prep):
        pnl, fills = replay_arm(p, live_tiers(p['t']))
        cal_rows.append((p['t'], pnl, fills, p['fid'], p['bpnl']))
        if (i + 1) % 10 == 0:
            print('  calibration: %d/%d trades replayed' % (i + 1, len(prep)), flush=True)
    cal_total = sum(r[1] for r in cal_rows)

    def median(xs):
        s = sorted(xs)
        n = len(s)
        if n == 0:
            return 0.0
        return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

    errs = [abs(r[1] - r[4]) for r in cal_rows]
    med_err = median(errs)
    worst = sorted(cal_rows, key=lambda r: -abs(r[1] - r[4]))[:5]
    within_pct = abs(cal_total - bench_total) <= 0.20 * abs(bench_total) if bench_total else False
    gate_pass = within_pct and med_err <= 15.0

    L = []
    L.append('FOUR-ARM HIDDEN-EXIT COMPARISON v4 (TIMING-CORRECTED) — run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Cohort: entry_type==hidden_entry, %s..%s. N=%d' % (START, END, len(cohort)))
    L.append('')
    L.append('Assumptions A1-A12: see the docstring of this script (stated up front).')
    L.append('Leg reconciliation (A3): sum |recorded-legs pnl - recorded pnl| over cohort'
             ' = $%.2f' % recon_gap)
    L.append('Fidelity: %d trades on 10s bars, %d on 3-point fallback (benchmark keeps'
             % (fidelity_count['bars'], fidelity_count['3pt']))
    L.append('recorded pnl on no-bars trades; %d of those had partial fills).' % nobars_pf)
    L.append('')
    L.append('================ 1) TIMING-CORRECTED BENCHMARK ================')
    L.append('Two-stage sequence test on ALL %d trades: (a) first post-entry touch of each'
             % len(cohort))
    L.append('recorded fill px on real 10s bars; (b) honest INTRABAR stop-fire (first 10s')
    L.append('bar low <= effective stop; live trail mechanics: BE after 2 scales, scale-bar-')
    L.append('low ratchet, rung floors on 1-min closes).  Touch after fire = TIMING-FICTION:')
    L.append('profit removed, shares exit at the stop * (1 - slip).')
    L.append('  TIMING-CORRECTED BENCHMARK total:  $%.2f' % bench_total)
    L.append('  Timing-fiction fills: %d (across %d trades)' % (fiction_fills, fiction_trades))
    L.append('  vs RAW book            $%.2f : delta $%+.2f' % (RAW_REF, bench_total - RAW_REF))
    L.append('  vs PRICE-CORRECTED     $%.2f : delta $%+.2f' % (PRICE_CORR_REF, bench_total - PRICE_CORR_REF))
    L.append('  (this run\'s fresh raw book: $%.2f)' % raw_total)
    L.append('  Per-day (benchmark | raw):')
    for d in sorted(bench_by_day):
        L.append('    %s   $%+9.2f | $%+9.2f' % (d, bench_by_day[d], raw_by_day[d]))
    L.append('')
    L.append('================ 3) CALIBRATION GATE (arm-3 vs benchmark) ================')
    L.append('Arm-3 = live model: post-entry-only tape_hi fills, INTRABAR stops (v4),')
    L.append('live hidden tiers (33%% @ entry+1R, cum 55%% @ x1.5, cum 75%% @ x2), rung')
    L.append('ratchet, BE-after-scale, health fold on 3-min closes.')
    L.append('  BENCHMARK:      $%.2f' % bench_total)
    L.append('  MODEL (arm 3):  $%.2f   (delta $%+.2f = %+.1f%% of benchmark)'
             % (cal_total, cal_total - bench_total,
                100.0 * (cal_total - bench_total) / bench_total if bench_total else 0.0))
    L.append('  Median |per-trade error|: $%.2f (gate <= $15) | mean |err|: $%.2f'
             % (med_err, sum(errs) / len(errs) if errs else 0.0))
    L.append('  GATE: within +/-20%%: %s | median err <= $15: %s  ==> %s'
             % ('PASS' if within_pct else 'FAIL',
                'PASS' if med_err <= 15.0 else 'FAIL',
                'CALIBRATED' if gate_pass else 'FAIL'))
    L.append('  Top-5 divergences (vs benchmark per-trade):')
    for t, pnl, _, fid, bpnl in worst:
        L.append('    %-5s %s  bench $%+8.2f  model $%+8.2f  err $%7.2f  [%s] exit_reason=%s'
                 % (t['ticker'], t['date'], bpnl, pnl, abs(pnl - bpnl), fid,
                    t.get('exit_reason')))
    L.append('')

    arms = {1: 'GRID (thirds @ trim1/x1.5/x2)', 2: 'LEVEL-TIERS (quarters @ map levels)',
            3: 'RATCHET-PRIMARY (= LIVE model)', 4: 'HYBRID (rungs -> nearest map level below)'}

    # named traces are owed EITHER way; build the helper first
    def trace_lines(star, sp, arm_results=None):
        TL = []
        TL.append('Trade: %s %s | entry $%.4f x %d sh | stop %.4f | highest %.4f | real exit %.4f'
                  % (star['ticker'], star['date'], star['entry'], star['shares'],
                     star['stop_loss'], star['highest'], star['exit']))
        TL.append('  raw pnl $%.2f | exit_reason: %s | fidelity: %s | slip %.1f%%'
                  % (star['pnl'], star.get('exit_reason'), sp['fid'], 100 * sp['slip']))
        det = sp['bdet']
        TL.append('  BENCHMARK $%.2f | honest stop-fire: %s @ stop %.4s'
                  % (sp['bpnl'],
                     det['stop_fire'].astimezone(EASTERN_TZ).strftime('%H:%M:%S ET')
                     if det['stop_fire'] else 'never (rode to recorded exit)',
                     str(det['stop_px']) if det['stop_px'] is not None else 'n/a'))
        for q, px in det['kept']:
            TL.append('    KEPT fill      %8.2f sh @ $%.4f  -> $%+.2f'
                      % (q, px, q * (px - star['entry'])))
        for q, px, ex in det['fiction']:
            TL.append('    TIMING-FICTION %8.2f sh @ $%.4f  -> re-exited @ $%.4f = $%+.2f'
                      ' (removed $%+.2f)'
                      % (q, px, ex, q * (ex - star['entry']), q * (px - ex)))
        if det['runner_qty'] > 0:
            TL.append('    runner leg     %8.2f sh @ recorded exit $%.4f -> $%+.2f'
                      % (det['runner_qty'], star['exit'],
                         det['runner_qty'] * (star['exit'] - star['entry'])))
        src = arm_results if arm_results is not None else \
            {3: [(star, *replay_arm(sp, live_tiers(star)), sp['fid'])]}
        for a in sorted(src):
            row = next((r for r in src[a] if r[0] is star), None)
            if row is None:
                continue
            _, pnl, fills, _ = row
            TL.append('  ARM %d — %s: pnl $%.2f' % (a, arms[a], pnl))
            for label, q, px in fills:
                TL.append('    %-42s %8.2f sh @ $%.4f  -> $%+.2f'
                          % (label, q, px, q * (px - star['entry'])))
        return TL

    def pick(ticker, date, entry_px=None):
        cands = [p for p in prep if p['t']['ticker'] == ticker and p['t']['date'] == date]
        if entry_px is not None:
            ex = [p for p in cands if abs(p['t']['entry'] - entry_px) < 0.02]
            if ex:
                return ex[0]
        # HUIZ specimen: the trade with the biggest removed fiction
        if cands:
            return max(cands, key=lambda p: sum(q * (px - ex) for q, px, ex
                                                in p['bdet']['fiction']) if p['bdet']['fiction'] else p['t']['pnl'])
        return None

    if not gate_pass:
        L.append('CALIBRATION GATE FAILED — four-arm numbers WITHHELD per the run spec.')
        neg = [r for r in cal_rows if r[1] < r[4]]
        pos = [r for r in cal_rows if r[1] >= r[4]]
        L.append('AGGREGATE: model below bench %d trades (sum $%.2f); above %d (sum $%+.2f).'
                 % (len(neg), sum(r[1] - r[4] for r in neg),
                    len(pos), sum(r[1] - r[4] for r in pos)))
        L.append('Hypotheses for the top-5 divergences:')
        for t, pnl, fills, fid, bpnl in worst:
            hyp = []
            if fid == '3pt':
                hyp.append('no post-entry bars (3pt fallback)')
            if pnl > bpnl:
                hyp.append('model rides past the honest stop (rung-ladder/map-refresh '
                           'fidelity, or tier ladder reconstruction differs from live '
                           'resting-bank prices)')
            else:
                hyp.append('model stops before the benchmark keeps its honest fills '
                           '(intrabar stop vs the benchmark\'s A5 tie rule, or live '
                           'fills off-SIP the 10s tape never shows)')
            L.append('    %-5s %s: %s' % (t['ticker'], t['date'], '; '.join(hyp)))
        L.append('')
        L.append('================ 5) NAMED TRACES (owed even on gate-fail) ================')
        for tick, dt, epx in (('FGI', '2026-08-13', 10.77), ('HUIZ', '2026-08-07', None)):
            sp = pick(tick, dt, epx)
            if sp:
                L += trace_lines(sp['t'], sp)
                L.append('')
        L.append('No recommendation — the full room verifies, Marcos decides.')
        open(OUT, 'w').write('\n'.join(L) + '\n')
        print('\n'.join(L))
        return

    # ---------------- 4) FOUR ARMS (gate passed) ----------------
    def arm_tiers(p, a):
        t = p['t']
        entry = t['entry']
        R = max(entry - (t.get('stop_loss') or entry * 0.94), 0.01)
        ft = round(entry + HIDDEN_TRIM_R * R, 4)
        lv = p['lv']
        if a == 1:
            return [(ft, 1/3), (round(entry*1.5, 4), 2/3), (round(entry*2.0, 4), 1.0)]
        if a == 2:
            return [(v, 0.25 * (i + 1)) for i, v in enumerate((lv or [])[:3])]
        if a == 3:
            return live_tiers(t)
        rungs_pct = [ft, round(entry*1.5, 4), round(entry*2.0, 4)]
        used, t4 = set(), []
        for r in rungs_pct:
            cand = [v for v in (lv or []) if v < r and v not in used and v > entry * 1.001]
            pick_ = max(cand) if cand else r
            used.add(pick_)
            t4.append(pick_)
        t4 = sorted(set(t4))
        return [(v, (i + 1) / 3.0 if i < 2 else 1.0) for i, v in enumerate(t4)]

    mapless = sum(1 for p in prep if p['lv'] is None)
    no_level_above = sum(1 for p in prep if p['lv'] == [])
    results = {a: [] for a in arms}
    stress_results = {a: [] for a in arms}
    for i, p in enumerate(prep):
        for a in arms:
            tiers = arm_tiers(p, a)
            pnl, fills = replay_arm(p, tiers)
            results[a].append((p['t'], pnl, fills, p['fid']))
            spnl, _ = replay_arm(p, tiers, stress=0.01)
            stress_results[a].append(spnl)
        if (i + 1) % 10 == 0:
            print('  four-arm: %d/%d trades replayed' % (i + 1, len(prep)), flush=True)

    L.append('Arm 2: no map record = %d trades (runner-only); map but no level above = %d.'
             % (mapless, no_level_above))
    L.append('')

    def block(name, rows, spnls=None):
        pnls = [r[1] for r in rows]
        n = len(pnls)
        tot, mean, med = sum(pnls), sum(pnls) / n, median(pnls)
        wins = sum(1 for p_ in pnls if p_ > 0)
        top1 = max(rows, key=lambda r: r[1])
        top3 = sorted(rows, key=lambda r: -r[1])[:3]
        worst_ = min(rows, key=lambda r: r[1])
        out = ['%s' % name,
               '  total $%.2f | mean $%.2f | MEDIAN $%.2f/trade | win rate %.1f%% (%d/%d)'
               % (tot, mean, med, 100.0 * wins / n, wins, n),
               '  ex-top-1 total $%.2f (top-1 = %s %s $%.2f)'
               % (tot - top1[1], top1[0]['ticker'], top1[0]['date'], top1[1]),
               '  worst %s %s $%.2f | top-3 tail: %s (tail $%.2f)'
               % (worst_[0]['ticker'], worst_[0]['date'], worst_[1],
                  ', '.join('%s %s $%.2f' % (r[0]['ticker'], r[0]['date'], r[1]) for r in top3),
                  sum(r[1] for r in top3))]
        if spnls is not None:
            out.append('  STRESS (+1%% worse exit fills): total $%.2f | median $%.2f'
                       % (sum(spnls), median(spnls)))
        return out

    L.append('================ 4) FOUR ARMS — ALL TRADES (N=%d) ================' % len(cohort))
    for a in arms:
        L += block('ARM %d — %s' % (a, arms[a]), results[a], stress_results[a])
        L.append('')

    L.append('================ FIDELITY SPLIT: REAL-BARS SUBSET ONLY ================')
    rb_totals, full_totals = {}, {}
    for a in arms:
        rows = [r for r in results[a] if r[3] == 'bars']
        full_totals[a] = sum(r[1] for r in results[a])
        rb_totals[a] = sum(r[1] for r in rows)
        L += block('ARM %d — %s [bars-only, N=%d]' % (a, arms[a], len(rows)), rows)
        L.append('')
    rank_full = sorted(arms, key=lambda a: -full_totals[a])
    rank_rb = sorted(arms, key=lambda a: -rb_totals[a])
    L.append('Ranking (full cohort):    %s' % ' > '.join('arm%d' % a for a in rank_full))
    L.append('Ranking (real-bars only): %s' % ' > '.join('arm%d' % a for a in rank_rb))
    unstable = [a for a in arms if rank_full.index(a) != rank_rb.index(a)]
    if unstable:
        for a in unstable:
            L.append('  UNSTABLE: arm %d ranking flips (full #%d -> bars-only #%d)'
                     % (a, rank_full.index(a) + 1, rank_rb.index(a) + 1))
    else:
        L.append('  No ranking flips — all arms STABLE across the fidelity split.')
    rank_stress = sorted(arms, key=lambda a: -sum(stress_results[a]))
    L.append('Ranking (stress run):     %s' % ' > '.join('arm%d' % a for a in rank_stress))
    if rank_stress != rank_full:
        L.append('  UNSTABLE: stress run reorders arms vs full cohort.')
    L.append('')

    L.append('================ 5) NAMED TRACES ================')
    for tick, dt, epx in (('FGI', '2026-08-13', 10.77), ('HUIZ', '2026-08-07', None)):
        sp = pick(tick, dt, epx)
        if sp:
            L += trace_lines(sp['t'], sp, results)
            L.append('')
    L.append('No recommendation — numbers only; the full room verifies, Marcos decides.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    run()
