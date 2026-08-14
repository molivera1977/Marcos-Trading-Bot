#!/usr/bin/env python3
"""FOUR-ARM HIDDEN-EXIT COMPARISON — v2 (2026-08-13 night rerun, calibrated).

Changes vs v1 (hidden_exit_fourarm_20260813.py):
 1. Cohort EXTENDS THROUGH 8/13 (adds today's hidden trades).
 2. Runner model RECALIBRATED TO THE LIVE TRAIL (marcos_trading_bot.py):
    - RUNG RATCHET (:8998): after any partial, floor = HIGHEST map rung
      (targets + next_supply + break, all > entry) cleared by a completed
      1-MIN CLOSE; floor never descends; exit remaining when price <= floor.
    - Trailing/stop (:8912): exit only on a completed 3-MIN CLOSE <= current
      stop.  Stop = initial stop_loss; -> ENTRY after tier #2
      (BE_FLOOR_AFTER_SCALE=2); after ANY tier, scale-bar-low ratchet
      (HIDDEN_SCALEBAR_STOP=1, :8858 — low of the 10s bucket at scale time),
      never down.
    - HEALTH FOLD (:9030): after a partial, 3-min close < EMA9(3-min) AND
      < rolling-45min VWAP -> fold the runner.
    - Live hidden tiers (:8554): 33% @ entry+1.0R, cum 55% @ x1.50,
      cum 75% @ x2.00 (HIDDEN_TRIM_R=1.0), resting-bank semantics
      (tape through the tier -> fill AT the tier price).
    v1's invented 0.90/0.95 percent bands are GONE.
 3. Fill model: ratchet exits fill BELOW the floor by per-trade slippage
    slip = min(3%, max(0.8%, est_slippage%))   [FGI 13.80->13.38 = 3.0% cap;
    INHD 12.00->11.90 = 0.8% floor; linear in the trade's own est_slippage].
    Stop/health exits fill at the qualifying 3-min close (the gap below the
    stop is already in the close).

CALIBRATION GATE: arm 3 (ratchet-primary = the live model incl. live tiers)
is replayed per-trade against the REAL recorded pnl BEFORE the four-arm
numbers are shown; cohort total must land within +/-20% of the real book.

Read-only vs live services. Results -> hidden_exit_fourarm_v2_20260813_RESULTS.txt.
census_lib.to24 imported for any 12-hour decision-row times (none consumed in
this run — trades store ISO timestamps — but the import is the law).
"""
import json, os, sys, shutil, urllib.request, urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo('America/New_York')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from census_lib import to24, BASE  # noqa: F401  (to24 = 12-hour store law)

V1CACHE = os.path.join(HERE, '.fourarm_cache_20260813')
CACHE = os.path.join(HERE, '.fourarm_cache_v2_20260813')
os.makedirs(CACHE, exist_ok=True)
# v2 refetch: trades/kev are DELETED and refetched fresh (cohort now includes
# tonight's full 8/13); immutable historical BAR files are seeded from v1.
for fn in os.listdir(V1CACHE) if os.path.isdir(V1CACHE) else []:
    if fn.startswith('bars_') and not os.path.exists(os.path.join(CACHE, fn)):
        shutil.copy(os.path.join(V1CACHE, fn), os.path.join(CACHE, fn))
for fn in ('trades.json', 'kev.json'):
    p = os.path.join(CACHE, fn)
    if os.path.exists(p):
        os.remove(p)

OUT = os.path.join(HERE, 'hidden_exit_fourarm_v2_20260813_RESULTS.txt')
START, END = '2026-07-24', '2026-08-13'
HIDDEN_TRIM_R = 1.0
BE_FLOOR_AFTER_SCALE = 2


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
    """Full-day [(ts, o, h, l, c, v)] 10s bars, else None.
    (v2: the WHOLE day — entry_ts_utc is trustworthy but recorded_at is NOT an
    exit time on resumed/rewritten records, so the model runs to its OWN exit.)"""
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
    """Per-trade below-floor slippage fraction for ratchet exits."""
    es = t.get('est_slippage')
    try:
        es = float(es)
    except (TypeError, ValueError):
        es = None
    if es is None:
        return 0.03          # no measurement -> conservative 3% (FGI cap)
    return min(0.03, max(0.008, es / 100.0))


def map_rungs(levels_by_date, t):
    """Live ladder: targets + next_supply + break, all > entry (bot :9001-:9010).
    Returns sorted list; None = no map record at all."""
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
    """Arm-2/4 marked tier candidates (v1 semantics: targets + next_supply above entry)."""
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
    """Aggregates 10s bars into completed N-minute bars."""
    def __init__(self, n_min):
        self.n = n_min
        self.key = None
        self.cur = None          # [o,h,l,c]
        self.completed = []      # list of (o,h,l,c)

    def push(self, ts, o, h, l, c, v=0.0):
        """Returns the just-COMPLETED bar (o,h,l,c,v) if this 10s bar opened a new bucket."""
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


def live_replay(t, tiers, rungs, day_bars, t_ent, slip):
    """Replay the LIVE runner model on full-day 10s bars from the entry timestamp
    until the model's OWN exit (or the session time stops / end of tape).
    tiers: [(price, cum_frac)] resting-limit ladder (arm-specific).
    rungs: map ladder for the RUNG RATCHET (may be empty).

    LIVE QUIRK REPRODUCED (:8886 + :8809): _tape_hi accumulates from the bars the
    monitor FETCHES — a ~45-minute window that includes PRE-ENTRY tape — so a tier
    below the recent pre-entry high fills immediately (measured live: every HUIZ
    8/7 tier-1 filled 1-4s after entry at entry+1R). tape_hi is therefore seeded
    with the 45 minutes of highs BEFORE entry.
    Returns (pnl, fills [(label, shares, price)])."""
    entry, shares = t['entry'], float(t['shares'])
    stop0 = t.get('stop_loss') or entry * 0.94
    remaining, sold_cum = shares, 0.0
    tier_idx, partial_taken = 0, False
    current_stop, floor = stop0, 0.0
    pre = [b for b in day_bars if b[0] < t_ent]
    path = [b for b in day_bars if b[0] >= t_ent]
    seed = [b[2] for b in pre if (t_ent - b[0]).total_seconds() <= 45 * 60]
    tape_hi = max(seed) if seed else None
    is_pre = (t.get('entry_session') == 'PRE')
    m1, m3 = MinuteAgg(1), MinuteAgg(3)
    m1v = []                      # completed 1-min (close, vol) for rolling VWAP
    fills = []

    def sell(label, qty, px):
        nonlocal remaining
        qty = min(qty, remaining)
        if qty <= 0:
            return
        fills.append((label, qty, px))
        remaining -= qty

    for ts, o, h, l, c, v in path:
        if remaining <= 0:
            break
        et_min = ts.astimezone(EASTERN_TZ).hour * 60 + ts.astimezone(EASTERN_TZ).minute
        # session time stops (live: PRE 9:25 flatten; 3:45pm EOD flatten)
        if is_pre and et_min >= 9 * 60 + 25:
            sell('time_stop_925@%.4f' % o, remaining, o)
            break
        if et_min >= 15 * 60 + 45:
            sell('time_stop_1545@%.4f' % o, remaining, o)
            break
        tape_hi = h if tape_hi is None else max(tape_hi, h)
        # 1) resting-bank tier fills (tape strictly through the level)
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
                # scale-bar-low ratchet (low of the 10s bucket at scale time)
                if l > current_stop:
                    current_stop = l
            else:
                break
        if remaining <= 0:
            break
        # 2) RUNG RATCHET exit check (stream cadence: this 10s bar's low)
        if partial_taken and floor > 0 and l <= floor:
            sell(f'rung_ratchet@{floor:.4f}', remaining, floor * (1 - slip))
            break
        # 3) completed 1-min bar -> rung clears + VWAP window
        b1 = m1.push(ts, o, h, l, c, v)
        if b1 is not None:
            m1v.append((b1[3], b1[4]))
            if partial_taken:
                for r in rungs:
                    if b1[3] > r > floor:
                        floor = r
        # 4) completed 3-min bar -> stop close / health fold
        b3 = m3.push(ts, o, h, l, c, v)
        if b3 is not None:
            c3 = b3[3]
            if c3 <= current_stop:
                lbl = 'trail_stop' if partial_taken else 'stop_loss'
                sell(f'{lbl}@close{c3:.4f}(stop {current_stop:.4f})', remaining, c3)
                break
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


def three_point_replay(t, tiers, real_exit):
    """No-bars fallback: entry -> highest -> real exit; tiers fill if highest
    trades through; remaining exits at the real exit price (= trusting the
    live book for the runner leg). Conservative and calibration-neutral."""
    entry, shares = t['entry'], float(t['shares'])
    hi = t.get('highest') or entry
    remaining, sold_cum = shares, 0.0
    fills = []
    for i, (tp, cum) in enumerate(tiers):
        if hi > tp and remaining > 0:
            qty = shares if cum >= 1.0 else max(1.0, shares * cum - sold_cum)
            qty = min(qty, remaining)
            fills.append((f'tier{i+1}@{tp:.4f}', qty, tp))
            sold_cum += qty
            remaining -= qty
    if remaining > 0:
        fills.append(('3pt(real exit)', remaining, real_exit))
    pnl = sum(q * (p - entry) for _, q, p in fills)
    return pnl, fills


def live_tiers(t):
    """The bot's hidden ladder (:8554): 33% @ entry+1R, cum 55% @ x1.5, cum 75% @ x2.
    Monotonic re-order exactly as the bot does."""
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
    real_total = sum(t['pnl'] for t in cohort)

    # precompute per-trade path + shared inputs
    prep = []
    fidelity_count = {'bars': 0, '3pt': 0}
    for t in cohort:
        t_ent = parse_ts(t.get('entry_ts_utc'))
        path = get_bars(t['ticker'], t['date']) if t_ent else None
        if path and not any(b[0] >= t_ent for b in path):
            path = None          # tape ends before the entry — no post-entry bars
        fid = 'bars' if path else '3pt'
        fidelity_count[fid] += 1
        prep.append({'t': t, 'path': path, 'fid': fid, 't_ent': t_ent,
                     'rungs': map_rungs(levels_by_date, t) or [],
                     'lv': level_targets(levels_by_date, t),
                     'slip': trade_slip(t)})

    # ---------------- CALIBRATION: arm 3 = live model, per-trade vs real ----------------
    cal_rows = []
    for p in prep:
        t = p['t']
        tiers = live_tiers(t)
        if p['path']:
            pnl, fills = live_replay(t, tiers, p['rungs'], p['path'], p['t_ent'], p['slip'])
        else:
            pnl, fills = three_point_replay(t, tiers, t['exit'])
        cal_rows.append((t, pnl, fills, p['fid']))
    cal_total = sum(r[1] for r in cal_rows)
    errs = sorted(abs(r[1] - r[0]['pnl']) for r in cal_rows)
    med_err = errs[len(errs) // 2] if errs else 0.0
    worst = sorted(cal_rows, key=lambda r: -abs(r[1] - r[0]['pnl']))[:5]
    within = abs(cal_total - real_total) <= 0.20 * abs(real_total)

    L = []
    L.append('FOUR-ARM HIDDEN-EXIT COMPARISON v2 (CALIBRATED) — run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Cohort: entry_type==hidden_entry, %s..%s (8/13 INCLUDED). N=%d'
             % (START, END, len(cohort)))
    L.append('')
    L.append('================ CALIBRATION FIRST (model vs real book) ================')
    L.append('Arm-3 model = the LIVE trail replayed: live hidden tiers (33% @ entry+1R,')
    L.append('cum 55% @ x1.5, cum 75% @ x2), RUNG RATCHET floors (map rungs cleared by 1-min')
    L.append('close, incl. break), 3-min-close trailing stop (BE after tier2 + scale-bar-low),')
    L.append('health fold (3-min close < EMA9 AND < rolling VWAP).')
    L.append('  REAL BOOK  (recorded): $%.2f' % real_total)
    L.append('  MODEL      (arm 3):    $%.2f   (delta $%+.2f = %.1f%% of real)'
             % (cal_total, cal_total - real_total,
                100.0 * (cal_total - real_total) / real_total if real_total else 0))
    L.append('  Median |per-trade error|: $%.2f  | mean |err|: $%.2f'
             % (med_err, sum(errs) / len(errs) if errs else 0))
    L.append('  GATE (+/-20%% of real): %s' % ('PASS' if within else 'FAIL'))
    L.append('  Worst-modeled 5:')
    for t, pnl, _, fid in worst:
        L.append('    %-5s %s  real $%+8.2f  model $%+8.2f  err $%7.2f  [%s] exit_reason=%s'
                 % (t['ticker'], t['date'], t['pnl'], pnl, abs(pnl - t['pnl']), fid,
                    t.get('exit_reason')))
    L.append('')
    if not within:
        L.append('CALIBRATION GATE FAILED — four-arm numbers WITHHELD per the run spec.')
        L.append('Diagnose the worst-modeled trades above before rerunning.')
        open(OUT, 'w').write('\n'.join(L) + '\n')
        print('\n'.join(L))
        return

    # ---------------- FOUR ARMS ----------------
    arms = {1: 'GRID (thirds @ trim1/x1.5/x2)', 2: 'LEVEL-TIERS (quarters @ map levels)',
            3: 'RATCHET-PRIMARY (= LIVE model)', 4: 'HYBRID (rungs -> nearest map level below)'}
    results = {a: [] for a in arms}
    mapless = no_level_above = 0
    for p in prep:
        t = p['t']
        entry, shares = t['entry'], float(t['shares'])
        R = max(entry - (t.get('stop_loss') or entry * 0.94), 0.01)
        ft = round(entry + HIDDEN_TRIM_R * R, 4)   # live first trim
        lv = p['lv']
        if lv is None:
            mapless += 1
        elif lv == []:
            no_level_above += 1

        def replay(tiers):
            if p['path']:
                return live_replay(t, tiers, p['rungs'], p['path'], p['t_ent'], p['slip'])
            return three_point_replay(t, tiers, t['exit'])

        # Arm 1 GRID: thirds at ft / x1.5 / x2 (cum 1/3, 2/3, 1.0? no — runner rides: cum .33/.67 keeps 1/3 runner)
        results[1].append((t, *replay([(ft, 1/3), (round(entry*1.5, 4), 2/3),
                                       (round(entry*2.0, 4), 1.0)]), p['fid']))
        # Arm 2 LEVEL-TIERS: quarters at first 3 marked levels; mapless -> ratchet-only
        tiers2 = [(v, 0.25 * (i + 1)) for i, v in enumerate((lv or [])[:3])]
        results[2].append((t, *replay(tiers2), p['fid']))
        # Arm 3 = calibration rows (live model)
        results[3] = cal_rows
        # Arm 4 HYBRID: each grid rung replaced by nearest unused marked level below it
        rungs_pct = [ft, round(entry*1.5, 4), round(entry*2.0, 4)]
        used, t4 = set(), []
        for r in rungs_pct:
            cand = [v for v in (lv or []) if v < r and v not in used and v > entry * 1.001]
            pick = max(cand) if cand else r
            used.add(pick)
            t4.append(pick)
        t4 = sorted(set(t4))
        results[4].append((t, *replay([(v, (i + 1) / 3.0 if i < 2 else 1.0)
                                       for i, v in enumerate(t4)]), p['fid']))

    L.append('================ ASSUMPTIONS ================')
    L.append(' - Read-only replay; sizing = each trade\'s REAL shares; dollars end-to-end.')
    L.append(' - Path: FULL-DAY 10s bars (~10S pref, ~ALP10S fallback) from entry_ts_utc to the')
    L.append('   model\'s OWN exit / time stop / end of tape (recorded_at is NOT trusted as an')
    L.append('   exit time — resumed/rewritten records carry recorded_at ~ entry).')
    L.append('   %d trades on 10s bars, %d on 3-point fallback (fallback runner leg exits at' % (fidelity_count['bars'], fidelity_count['3pt']))
    L.append('   the REAL exit price — calibration-neutral by construction).')
    L.append(' - LIVE QUIRK REPRODUCED: tape_hi seeded with the 45 min of PRE-ENTRY highs —')
    L.append('   the monitor\'s _tape_hi accumulates over its fetched bar window, which includes')
    L.append('   pre-entry tape, so tiers below the recent high fill immediately (measured live:')
    L.append('   every HUIZ 8/7 tier-1 filled 1-4s after entry). Without this seed the model was')
    L.append('   -$1,186 off the book; with it, calibration passes.')
    L.append(' - Known irreducible gap: a few live fills printed OFF our SIP 10s tape')
    L.append('   (HUIZ 8/7 58sh@2.88; post-entry tape high 2.46) — stream-quote fills the')
    L.append('   replay cannot see; they bias the model LOW on those trades.')
    L.append(' - Tier fills: resting-bank semantics — tape strictly THROUGH the level, fill AT it.')
    L.append(' - Runner model (ALL arms) = the live trail (see calibration header). Arms differ')
    L.append('   ONLY in the tier ladder handed to it.')
    L.append(' - Ratchet fills: floor*(1-slip), slip = min(3%, max(0.8%, est_slippage%));')
    L.append('   no est_slippage recorded -> 3% (conservative). Stop/health fills at the 3-min close.')
    L.append(' - Rung ladder = current _levels snapshot (targets+next_supply+break > entry);')
    L.append('   intraday map refreshes NOT reconstructed (known fidelity gap, both directions).')
    L.append(' - Arm 2: no map record = %d trades (runner-only); map but no level above entry = %d.' % (mapless, no_level_above))
    L.append(' - Arm-1 grid keeps a 1/3-equivalent runner only until x2 (cum 1.0 at x2 = fully out);')
    L.append('   arm-4 hybrid mirrors that ladder on substituted levels.')
    L.append(' - No commissions/borrow. census_lib.to24 imported (12-hour store law); no decision')
    L.append('   rows consumed this run — trades carry ISO timestamps.')
    L.append('')
    L.append('REAL BOOK (recorded pnl, cohort): $%.2f' % real_total)
    L.append('')

    def mfe(t):
        return ((t.get('highest') or t['entry']) - t['entry']) / t['entry']

    def block(name, rows):
        pnls = [r[1] for r in rows]
        n = len(pnls)
        tot, mean = sum(pnls), sum(pnls) / n
        wins = sum(1 for p_ in pnls if p_ > 0)
        top3 = sorted(rows, key=lambda r: -r[1])[:3]
        worst_ = min(rows, key=lambda r: r[1])
        return ['%s' % name,
                '  total $%.2f | mean $%.2f/trade | win rate %.1f%% (%d/%d)'
                % (tot, mean, 100.0 * wins / n, wins, n),
                '  worst %s %s $%.2f | top-3 tail: %s (tail $%.2f)'
                % (worst_[0]['ticker'], worst_[0]['date'], worst_[1],
                   ', '.join('%s %s $%.2f' % (r[0]['ticker'], r[0]['date'], r[1]) for r in top3),
                   sum(r[1] for r in top3))]

    L.append('================ ALL TRADES (N=%d) ================' % len(cohort))
    for a in arms:
        L += block('ARM %d — %s' % (a, arms[a]), results[a])
        L.append('')
    fgi_ids = {id(t) for t in cohort if mfe(t) >= 0.30}
    L.append('================ MONSTER SUBSET (MFE >= +30%%): N=%d ================' % len(fgi_ids))
    for a in arms:
        rows = [r for r in results[a] if id(r[0]) in fgi_ids]
        if rows:
            L += block('ARM %d — %s' % (a, arms[a]), rows)
            L.append('')

    # ---------------- NAMED TRACE: FGI 8/13, entry 10.77 ----------------
    star = None
    for t in cohort:
        if t['ticker'] == 'FGI' and t['date'] == '2026-08-13' and abs(t['entry'] - 10.77) < 0.02:
            star = t
    if star is None:   # fall back to biggest 8/13 FGI
        fgis = [t for t in cohort if t['ticker'] == 'FGI' and t['date'] == '2026-08-13']
        star = max(fgis, key=lambda t: t['pnl']) if fgis else max(cohort, key=lambda t: t['pnl'])
    L.append('================ NAMED TRACE (dollars-not-R law) ================')
    L.append('Trade: %s %s | entry $%.4f x %d sh | stop %.4f | highest %.4f | real exit %.4f'
             % (star['ticker'], star['date'], star['entry'], star['shares'],
                star['stop_loss'], star['highest'], star['exit']))
    L.append('  real pnl $%.2f | exit_reason: %s | fidelity: %s | slip used: %.1f%%'
             % (star['pnl'], star.get('exit_reason'),
                next(pp['fid'] for pp in prep if pp['t'] is star),
                100 * next(pp['slip'] for pp in prep if pp['t'] is star)))
    for a in arms:
        tt, pnl, fills, fid = next(r for r in results[a] if r[0] is star)
        L.append(' ARM %d — %s: pnl $%.2f' % (a, arms[a], pnl))
        for label, q, px in fills:
            L.append('    %-40s %8.2f sh @ $%.4f  -> $%+.2f'
                     % (label, q, px, q * (px - tt['entry'])))
    L.append('')
    L.append('No recommendation — numbers only; the decision is Marcos\'s on Friday.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    run()
