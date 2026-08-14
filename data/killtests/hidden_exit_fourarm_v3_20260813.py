#!/usr/bin/env python3
"""FOUR-ARM HIDDEN-EXIT COMPARISON — v3 (2026-08-13, CORRECTED-BOOK edition).

WHY v3: v2 calibrated against the RAW book (+$880.99) and deliberately
reproduced the fictional-fill quirk (tape_hi seeded with ~45min of PRE-ENTRY
tape) to hit the +/-20% gate.  Tonight that quirk was PROVEN A BUG (41
fictional fills, +$284.78 fake profit — census:
data/killtests/fictional_fills_census_20260813.md) and FIXED in the live bot
(tape since monitor birth only).  Friday's exit decision governs the FIXED
bot, so v3 models POST-ENTRY-TAPE-ONLY fills and calibrates against the
CORRECTED book.

CHANGES vs v2:
 1. CORRECTED BENCHMARK — real book minus each trade's fictional-fill
    inflation, recomputed per-trade in-script (census method): any partial
    fill above post-entry max high*1.001 -> subtract
    (fill_px - max(post_entry_hi, entry)) * qty.
 2. NO PRE-ENTRY TAPE SEEDING — model tape_hi accumulates from entry forward
    only (matches the fixed bot).  Tier fills need post-entry trade-through.
 3. CALIBRATION GATE v3 — arm-3 (live model) vs CORRECTED book within
    +/-20%; median |per-trade error| reported.  Fail -> STOP, top-5 worst
    with hypotheses, NO four-arm numbers.
 4. PANEL TEETH — per arm: median per-trade result; total with top-1 winner
    removed; +1% worse tier/exit fills stress; real-bars-only subset;
    UNSTABLE flag on any full-vs-real-bars ranking flip.
 5. Same four arms & live-trail mechanics as v2; per-trade slippage
    min(3%, max(0.8%, spread-linear)).

Read-only vs live services.  Results -> hidden_exit_fourarm_v3_20260813_RESULTS.txt.
NO recommendation — the full room verifies, Marcos decides Friday.
"""
import json, os, sys, shutil, urllib.request, urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo('America/New_York')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from census_lib import to24, BASE  # noqa: F401  (to24 = 12-hour store law)

V2CACHE = os.path.join(HERE, '.fourarm_cache_v2_20260813')
CACHE = os.path.join(HERE, '.fourarm_cache_v3_20260813')
os.makedirs(CACHE, exist_ok=True)
# seed immutable historical BAR files from v2; trades/kev refetched fresh
for fn in os.listdir(V2CACHE) if os.path.isdir(V2CACHE) else []:
    if fn.startswith('bars_') and not os.path.exists(os.path.join(CACHE, fn)):
        shutil.copy(os.path.join(V2CACHE, fn), os.path.join(CACHE, fn))
for fn in ('trades.json', 'kev.json'):
    p = os.path.join(CACHE, fn)
    if os.path.exists(p):
        os.remove(p)

OUT = os.path.join(HERE, 'hidden_exit_fourarm_v3_20260813_RESULTS.txt')
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
    """Full-day [(ts, o, h, l, c, v)] 10s bars, else None."""
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


def live_replay(t, tiers, rungs, day_bars, t_ent, slip, stress=0.0):
    """Replay the FIXED live runner model on post-entry 10s bars.

    v3: NO PRE-ENTRY SEEDING — tape_hi starts None and accumulates from the
    first post-entry bar (matches tonight's _tape_birth fix).  Tier fills
    require post-entry tape strictly THROUGH the level.
    stress: fraction subtracted from every exit fill price (slippage stress).
    Returns (pnl, fills [(label, shares, price)])."""
    entry, shares = t['entry'], float(t['shares'])
    stop0 = t.get('stop_loss') or entry * 0.94
    remaining, sold_cum = shares, 0.0
    tier_idx, partial_taken = 0, False
    current_stop, floor = stop0, 0.0
    path = [b for b in day_bars if b[0] >= t_ent]
    tape_hi = None                       # v3: post-entry only, no seed
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
        et_min = ts.astimezone(EASTERN_TZ).hour * 60 + ts.astimezone(EASTERN_TZ).minute
        if is_pre and et_min >= 9 * 60 + 25:
            sell('time_stop_925@%.4f' % o, remaining, o)
            break
        if et_min >= 15 * 60 + 45:
            sell('time_stop_1545@%.4f' % o, remaining, o)
            break
        tape_hi = h if tape_hi is None else max(tape_hi, h)
        # 1) resting-bank tier fills (POST-ENTRY tape strictly through the level)
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
        # 2) RUNG RATCHET exit (stream cadence: this 10s bar's low)
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


def three_point_replay(t, tiers, real_exit, post_hi, stress=0.0):
    """No-bars fallback: entry -> POST-ENTRY high -> real exit.
    v3: the trade-through test uses the post-entry high when we have one
    (here we don't have bars, so 'highest' from the record is the only high;
    it is recorded DURING the trade = post-entry by construction).
    Runner leg exits at the corrected-real exit price."""
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


def fictional_correction(t, path, t_ent):
    """Census method: post-entry max high from 10s tape; any partial fill
    above max(post_entry_hi, entry)*1.001 -> inflation
    (fill_px - max(post_entry_hi, entry)) * qty.  Returns (correction$, n_fills).
    No bars -> correction 0 (counted; stated in assumptions)."""
    pf = t.get('partial_fills') or []
    if not pf or not path or not t_ent:
        return 0.0, 0
    post = [b for b in path if b[0] >= t_ent]
    if not post:
        return 0.0, 0
    hi = max(b[2] for b in post)
    ref = max(hi, t['entry'])
    corr, n = 0.0, 0
    for qty, px in pf:
        if px > ref * 1.001:
            corr += (px - ref) * qty
            n += 1
    return corr, n


def run():
    trades_doc = get(f'{BASE}/api/trades', 'trades.json')
    kev = get(f'{BASE}/api/kev_watchlist', 'kev.json')
    levels_by_date = kev.get('_levels', {}) if isinstance(kev, dict) else {}

    cohort = [t for t in trades_doc['trades']
              if t.get('entry_type') == 'hidden_entry' and START <= t['date'] <= END]
    cohort.sort(key=lambda t: (t['date'], t.get('entry_ts_utc') or ''))
    raw_total = sum(t['pnl'] for t in cohort)

    # ---- prep + corrected benchmark ----
    prep = []
    fidelity_count = {'bars': 0, '3pt': 0}
    corr_total, corr_fills, corr_nobars = 0.0, 0, 0
    for t in cohort:
        t_ent = parse_ts(t.get('entry_ts_utc'))
        path = get_bars(t['ticker'], t['date']) if t_ent else None
        if path and not any(b[0] >= t_ent for b in path):
            path = None
        fid = 'bars' if path else '3pt'
        fidelity_count[fid] += 1
        corr, ncf = fictional_correction(t, path, t_ent)
        if fid == '3pt' and (t.get('partial_fills') or []):
            corr_nobars += 1
        corr_total += corr
        corr_fills += ncf
        prep.append({'t': t, 'path': path, 'fid': fid, 't_ent': t_ent,
                     'rungs': map_rungs(levels_by_date, t) or [],
                     'lv': level_targets(levels_by_date, t),
                     'slip': trade_slip(t), 'corr': corr,
                     'cpnl': t['pnl'] - corr})
    corrected_total = raw_total - corr_total

    def replay_arm(p, tiers, stress=0.0):
        t = p['t']
        if p['path']:
            return live_replay(t, tiers, p['rungs'], p['path'], p['t_ent'],
                               p['slip'], stress)
        # 3pt runner leg exits at the CORRECTED real exit contribution:
        # use real exit price; inflation on 3pt trades is uncorrectable (stated).
        return three_point_replay(t, tiers, t['exit'], None, stress)

    # ---- CALIBRATION v3: arm-3 (live model, post-entry tape) vs CORRECTED book ----
    cal_rows = []
    for p in prep:
        pnl, fills = replay_arm(p, live_tiers(p['t']))
        cal_rows.append((p['t'], pnl, fills, p['fid'], p['cpnl']))
    cal_total = sum(r[1] for r in cal_rows)
    errs = sorted(abs(r[1] - r[4]) for r in cal_rows)
    med_err = errs[len(errs) // 2] if errs else 0.0
    worst = sorted(cal_rows, key=lambda r: -abs(r[1] - r[4]))[:5]
    within = abs(cal_total - corrected_total) <= 0.20 * abs(corrected_total)

    L = []
    L.append('FOUR-ARM HIDDEN-EXIT COMPARISON v3 (CORRECTED-BOOK) — run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Cohort: entry_type==hidden_entry, %s..%s. N=%d' % (START, END, len(cohort)))
    L.append('')
    L.append('WHY v3: v2 calibrated against the RAW book and deliberately reproduced the')
    L.append('fictional-fill quirk (tape_hi seeded with ~45min PRE-ENTRY tape) to hit the')
    L.append('+/-20% gate.  Tonight that quirk was PROVEN A BUG (41 fictional fills,')
    L.append('+$284.78 fake profit; census: fictional_fills_census_20260813.md) and FIXED')
    L.append('in the live bot (tape since monitor birth only).  Friday\'s exit decision')
    L.append('governs the FIXED bot — v3 models POST-ENTRY-TAPE-ONLY fills and calibrates')
    L.append('against the CORRECTED book.')
    L.append('')
    L.append('================ BENCHMARK (corrected book) ================')
    L.append('  RAW book (recorded pnl):          $%.2f' % raw_total)
    L.append('  Fictional-fill correction:        -$%.2f  (%d fictional fills across cohort,'
             % (corr_total, corr_fills))
    L.append('    recomputed in-script by the census method: fill px > post-entry max high')
    L.append('    *1.001 -> subtract (fill_px - max(post_entry_hi, entry)) * qty)')
    L.append('  CORRECTED book (benchmark):       $%.2f' % corrected_total)
    L.append('  (%d trades with partial fills had NO post-entry bars -> correction 0 there.)'
             % corr_nobars)
    L.append('')
    L.append('================ CALIBRATION v3 (model vs CORRECTED book) ================')
    L.append('Arm-3 model = FIXED live trail replayed: live hidden tiers (33% @ entry+1R,')
    L.append('cum 55% @ x1.5, cum 75% @ x2), RUNG RATCHET floors, 3-min-close trailing')
    L.append('stop (BE after tier2 + scale-bar-low), health fold — tape_hi POST-ENTRY ONLY.')
    L.append('  CORRECTED BOOK: $%.2f' % corrected_total)
    L.append('  MODEL (arm 3):  $%.2f   (delta $%+.2f = %.1f%% of corrected)'
             % (cal_total, cal_total - corrected_total,
                100.0 * (cal_total - corrected_total) / corrected_total if corrected_total else 0))
    L.append('  Median |per-trade error| vs corrected per-trade pnl: $%.2f | mean |err|: $%.2f'
             % (med_err, sum(errs) / len(errs) if errs else 0))
    L.append('  GATE (+/-20%% of corrected): %s' % ('PASS' if within else 'FAIL'))
    L.append('  Worst-modeled 5 (vs corrected per-trade):')
    for t, pnl, _, fid, cpnl in worst:
        L.append('    %-5s %s  corrected $%+8.2f  model $%+8.2f  err $%7.2f  [%s] exit_reason=%s'
                 % (t['ticker'], t['date'], cpnl, pnl, abs(pnl - cpnl), fid,
                    t.get('exit_reason')))
    L.append('')
    if not within:
        L.append('CALIBRATION GATE FAILED — four-arm numbers WITHHELD per the run spec.')
        # aggregate structure of the failure
        neg = [r for r in cal_rows if r[1] < r[4]]
        pos = [r for r in cal_rows if r[1] >= r[4]]
        gap = [r for r in cal_rows
               if (r[0].get('partial_fills') or [])
               and not any(f[0].startswith('tier') for f in r[2])]
        L.append('')
        L.append('AGGREGATE DIAGNOSIS (the failure is BROAD, not a few outliers):')
        L.append('  model below corrected: %d trades, sum $%.2f' %
                 (len(neg), sum(r[1] - r[4] for r in neg)))
        L.append('  model above corrected: %d trades, sum $%+.2f' %
                 (len(pos), sum(r[1] - r[4] for r in pos)))
        L.append('  LIVE booked a partial fill but the post-entry-only model fills NO tier:')
        L.append('    %d trades, delta sum $%.2f  <- essentially the whole failure.' %
                 (len(gap), sum(r[1] - r[4] for r in gap)))
        L.append('  Leading hypothesis: the census correction removes only PRICE overage')
        L.append('  (fill px above post-entry high).  Fills that printed instantly on')
        L.append('  PRE-ENTRY tape at prices the stock later reached post-entry stay in the')
        L.append('  corrected book at full credit — but the FIXED bot would have filled them')
        L.append('  later or not before the stop.  The corrected book is therefore an UPPER')
        L.append('  BOUND on the fixed bot, not a clean benchmark of it; secondary')
        L.append('  hypothesis: live tier prices differ from the reconstructed entry+1R')
        L.append('  ladder on some trades (observed live partials at prices well under the')
        L.append('  reconstructed tier-1), and the model\'s 3-min trailing stop can exit')
        L.append('  before the tape trades through tier-1.')
        L.append('')
        L.append('Hypotheses for the worst-modeled 5:')
        for t, pnl, fills, fid, cpnl in worst:
            hi = t.get('highest') or t['entry']
            hyp = []
            if fid == '3pt':
                hyp.append('no post-entry bars (3pt fallback)')
            if pnl > cpnl:
                hyp.append('model rides longer than the live exit did (map-refresh/'
                           'intraday-rung fidelity gap, or live exited on stream data '
                           'the 10s tape smooths over)')
            else:
                hyp.append('live fills printed off our SIP 10s tape (stream-quote fills '
                           'the replay cannot see) or live tier filled on the now-fixed '
                           'pre-entry-tape bug (real book row still contains it; corrected '
                           'row subtracts only the above-post-entry-high overage)')
            L.append('    %-5s %s: %s' % (t['ticker'], t['date'], '; '.join(hyp)))
        open(OUT, 'w').write('\n'.join(L) + '\n')
        print('\n'.join(L))
        return

    # ---------------- FOUR ARMS ----------------
    arms = {1: 'GRID (thirds @ trim1/x1.5/x2)', 2: 'LEVEL-TIERS (quarters @ map levels)',
            3: 'RATCHET-PRIMARY (= LIVE model)', 4: 'HYBRID (rungs -> nearest map level below)'}

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
            pick = max(cand) if cand else r
            used.add(pick)
            t4.append(pick)
        t4 = sorted(set(t4))
        return [(v, (i + 1) / 3.0 if i < 2 else 1.0) for i, v in enumerate(t4)]

    mapless = sum(1 for p in prep if p['lv'] is None)
    no_level_above = sum(1 for p in prep if p['lv'] == [])
    results = {a: [] for a in arms}          # (t, pnl, fills, fid)
    stress_results = {a: [] for a in arms}   # pnl only, +1% worse exit fills
    for p in prep:
        for a in arms:
            tiers = arm_tiers(p, a)
            pnl, fills = replay_arm(p, tiers)
            results[a].append((p['t'], pnl, fills, p['fid']))
            spnl, _ = replay_arm(p, tiers, stress=0.01)
            stress_results[a].append(spnl)

    L.append('================ ASSUMPTIONS ================')
    L.append(' - Read-only replay; sizing = each trade\'s REAL shares; dollars end-to-end.')
    L.append(' - Path: FULL-DAY 10s bars (~10S pref, ~ALP10S fallback) from entry_ts_utc to')
    L.append('   the model\'s OWN exit / time stop / end of tape.')
    L.append('   %d trades on 10s bars, %d on 3-point fallback (runner leg exits at the REAL'
             % (fidelity_count['bars'], fidelity_count['3pt']))
    L.append('   exit price; 3pt trades get correction 0 — uncorrectable without tape).')
    L.append(' - v3 FILL MODEL: tape_hi accumulates POST-ENTRY ONLY (matches the fixed bot,')
    L.append('   _tape_birth).  No pre-entry seeding.  Tier fills = post-entry tape strictly')
    L.append('   THROUGH the level, fill AT it (resting-bank semantics).')
    L.append(' - Benchmark = CORRECTED book (census method recomputed per-trade in-script).')
    L.append(' - Known irreducible gap: live fills that printed OFF our SIP 10s tape')
    L.append('   (stream-quote fills) bias the model LOW on those trades; the correction only')
    L.append('   removes overage ABOVE the post-entry tape high, not sub-high stream fills.')
    L.append(' - Runner model (ALL arms) = the live trail; arms differ ONLY in the tier ladder.')
    L.append(' - Ratchet fills: floor*(1-slip), slip = min(3%, max(0.8%, est_slippage%));')
    L.append('   none recorded -> 3%. Stop/health fills at the 3-min close.')
    L.append(' - Slippage STRESS run: every exit fill price *0.99 (entry unchanged).')
    L.append(' - Rung ladder = current _levels snapshot; intraday map refreshes NOT')
    L.append('   reconstructed (known fidelity gap, both directions).')
    L.append(' - Arm 2: no map record = %d trades (runner-only); map but no level above = %d.'
             % (mapless, no_level_above))
    L.append(' - No commissions/borrow. census_lib.to24 imported (12-hour store law); no')
    L.append('   decision rows consumed this run — trades carry ISO timestamps.')
    L.append('')
    L.append('CORRECTED BOOK (benchmark): $%.2f   (raw $%.2f - correction $%.2f)'
             % (corrected_total, raw_total, corr_total))
    L.append('')

    def median(xs):
        s = sorted(xs)
        n = len(s)
        if n == 0:
            return 0.0
        return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

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

    L.append('================ ALL TRADES (N=%d) ================' % len(cohort))
    for a in arms:
        L += block('ARM %d — %s' % (a, arms[a]), results[a], stress_results[a])
        L.append('')

    # real-bars subset + stability
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
    L.append('')

    # stress ranking check
    rank_stress = sorted(arms, key=lambda a: -sum(stress_results[a]))
    L.append('Ranking (stress run):     %s' % ' > '.join('arm%d' % a for a in rank_stress))
    if rank_stress != rank_full:
        L.append('  NOTE: stress run reorders arms vs full cohort.')
    L.append('')

    # monster subset
    def mfe(t):
        return ((t.get('highest') or t['entry']) - t['entry']) / t['entry']
    fgi_ids = {id(t) for t in cohort if mfe(t) >= 0.30}
    L.append('================ MONSTER SUBSET (MFE >= +30%%): N=%d ================' % len(fgi_ids))
    for a in arms:
        rows = [r for r in results[a] if id(r[0]) in fgi_ids]
        if rows:
            L += block('ARM %d — %s' % (a, arms[a]), rows)
            L.append('')

    # ---------------- NAMED TRACE: FGI 8/13 entry 10.77 ----------------
    star = None
    for t in cohort:
        if t['ticker'] == 'FGI' and t['date'] == '2026-08-13' and abs(t['entry'] - 10.77) < 0.02:
            star = t
    if star is None:
        fgis = [t for t in cohort if t['ticker'] == 'FGI' and t['date'] == '2026-08-13']
        star = max(fgis, key=lambda t: t['pnl']) if fgis else max(cohort, key=lambda t: t['pnl'])
    sp = next(pp for pp in prep if pp['t'] is star)
    L.append('================ NAMED TRACE (dollars-not-R law) ================')
    L.append('Trade: %s %s | entry $%.4f x %d sh | stop %.4f | highest %.4f | real exit %.4f'
             % (star['ticker'], star['date'], star['entry'], star['shares'],
                star['stop_loss'], star['highest'], star['exit']))
    L.append('  raw pnl $%.2f | fictional correction $%.2f | corrected pnl $%.2f'
             % (star['pnl'], sp['corr'], sp['cpnl']))
    L.append('  exit_reason: %s | fidelity: %s | slip used: %.1f%%'
             % (star.get('exit_reason'), sp['fid'], 100 * sp['slip']))
    for a in arms:
        tt, pnl, fills, fid = next(r for r in results[a] if r[0] is star)
        L.append(' ARM %d — %s: pnl $%.2f' % (a, arms[a], pnl))
        for label, q, px in fills:
            L.append('    %-40s %8.2f sh @ $%.4f  -> $%+.2f'
                     % (label, q, px, q * (px - tt['entry'])))
    L.append('')
    L.append('No recommendation — numbers only; the full room verifies, Marcos decides Friday.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    run()
