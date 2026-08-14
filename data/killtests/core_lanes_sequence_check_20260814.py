#!/usr/bin/env python3
"""SEQUENCE-HONEST VERIFICATION OF THE NON-HIDDEN (CORE) LANES — 2026-08-14.

Marcos's challenge: the "+$239 real AUGUST core" claim rests on the price-level
book test — the SAME weaker test that flattered hidden until the v4
timing-corrected benchmark removed it.  This run closes that gap: the v4
two-stage sequence test (first post-entry touch of each recorded partial-fill
px vs an honest intrabar stop-fire) applied to every ERA (7/24+) trade with
entry_type != hidden_entry.

METHOD (engine adapted from hidden_exit_fourarm_v4_20260813.py benchmark_trade,
room-certified 8/13; NOT imported because that module's top-level code mutates
its cache dir — logic copied verbatim, then parametrized):
  * Post-entry-only 10s bars (~10S pref, ~ALP10S fallback), bars reused from the
    v2/v3/v4 caches; trades + kev map REFETCHED FRESH this run.
  * CONSERVATIVE SCOPE: only the recorded partial FILLS are re-adjudicated.
    The runner leg always exits at the trade's RECORDED exit px — we make no
    claim about how the non-hidden lanes' runner exits (trail/health-fold
    mechanics differ per lane; hidden's engine cannot faithfully model them).
    So this is a fills-fiction bracket, not a full re-simulation.  Labeled.
  * TWO BENCHMARK VARIANTS bracket the honest number, because non-hidden lanes
    do NOT share hidden's trail mechanics:
      (a) TRAIL variant  — v4 mechanics as-is (recorded stop; BE floor after
          2 scales; scale-bar-low ratchet; rung floors on 1-min closes above
          kev-map rungs; intrabar fire = first 10s bar low <= effective stop).
          This is the STRICT end: the trail tightens the stop, firing earlier,
          marking more fills fictional.
      (b) FLAT-STOP variant — the stop stays at the trade's recorded stop_loss,
          no trail, intrabar fire.  This is the CHARITABLE end: only fills the
          tape provably could not have printed before a plain stop-out lose
          credit.  Any lane whose real mechanics tighten stops at all sits
          between (b) and (a).
  * Same-bar tie favors the fill (v4 A5 — benchmark is an upper bound on that
    bar, stated not hidden).  Fiction fills exit at the effective stop *
    (1 - slip), slip = min(3%, max(0.8%, est_slippage/100)), 3% if unrecorded.
  * Trades with NO partial fills cannot carry fill-fiction: recorded pnl kept,
    counted in totals.  Trades with fills but NO entry_ts_utc = [NOT TIMED]
    (recorded pnl kept, flagged).  Fills but no post-entry bars = [NO BARS]
    (recorded pnl kept, flagged) — matches v4 A7.
  * [NOT MODELED — needs its own pass]: halt_ladder (5s-feed halt-lane
    mechanics; recorded stop semantics differ during LULD).  Its recorded pnl
    is kept in totals but excluded from correction; flagged in output.
  * Dollars end-to-end at each trade's real shares.  Read-only.  No writes to
    any live service.  census_lib.to24 imported per store law (unused here —
    trades carry ISO timestamps).

OUTPUT: per-lane raw book vs sequence-honest bracket, fiction-fill counts,
biggest specimens, and the AUGUST (8/1+) non-hidden headline bracket vs the
+$239 charitable claim.  The full room verifies at Friday's review.
"""
import json, os, shutil, sys, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo('America/New_York')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from census_lib import to24, BASE  # noqa: F401

CACHE = os.path.join(HERE, '.core_seq_cache_20260814')
os.makedirs(CACHE, exist_ok=True)
for src_name in ('.fourarm_cache_v4_20260813', '.fourarm_cache_v3_20260813',
                 '.fourarm_cache_v2_20260813'):
    src = os.path.join(HERE, src_name)
    if os.path.isdir(src):
        for fn in os.listdir(src):
            if fn.startswith('bars_') and not os.path.exists(os.path.join(CACHE, fn)):
                shutil.copy(os.path.join(src, fn), os.path.join(CACHE, fn))
for fn in ('trades.json', 'kev.json'):
    p = os.path.join(CACHE, fn)
    if os.path.exists(p):
        os.remove(p)

OUT = os.path.join(HERE, 'core_lanes_sequence_check_20260814_RESULTS.txt')
START = '2026-07-24'
AUG_START = '2026-08-01'
BE_FLOOR_AFTER_SCALE = 2
NOT_MODELED_LANES = {'halt_ladder'}
CLAIM_AUG_CORE = 239.0


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
    try:
        es = float(t.get('est_slippage'))
    except (TypeError, ValueError):
        es = None
    if es is None:
        return 0.03
    return min(0.03, max(0.008, es / 100.0))


def map_rungs(levels_by_date, t):
    d = (levels_by_date.get(t['date']) or {}).get(t['ticker'])
    if not d:
        return []
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


def benchmark_trade(t, path, t_ent, rungs, slip, trail=True):
    """v4 benchmark_trade, parametrized: trail=False freezes the stop at the
    recorded stop_loss (charitable flat-stop variant).  Returns (pnl, detail)."""
    entry, shares = t['entry'], float(t['shares'])
    pf = [(float(q), float(px)) for q, px in (t.get('partial_fills') or [])]
    runner_qty = shares - sum(q for q, _ in pf)
    post = [b for b in path if b[0] >= t_ent] if (path and t_ent) else []
    detail = {'fiction': [], 'kept': [], 'runner_qty': runner_qty,
              'stop_fire': None, 'stop_px': None, 'no_bars': not post}
    if not post:
        return t['pnl'], detail

    touch_idx = []
    for q, px in pf:
        idx = None
        for i, b in enumerate(post):
            if b[2] >= px:
                idx = i
                break
        touch_idx.append(idx)

    stop0 = t.get('stop_loss') or entry * 0.94
    current_stop, floor = stop0, 0.0
    scales = 0
    m1 = MinuteAgg(1)
    order = sorted((ix, j) for j, ix in enumerate(touch_idx) if ix is not None)
    fire_idx, fire_stop = None, None
    oi = 0
    for i, (ts, o, h, l, c, v) in enumerate(post):
        while oi < len(order) and order[oi][0] == i:
            scales += 1
            if trail:
                if scales >= BE_FLOOR_AFTER_SCALE:
                    current_stop = max(current_stop, entry)
                if l > current_stop:
                    current_stop = l
            oi += 1
        eff = max(current_stop, floor if (trail and scales > 0) else 0.0)
        if l <= eff:
            fire_idx, fire_stop = i, eff
            break
        b1 = m1.push(ts, o, h, l, c, v)
        if trail and b1 is not None and scales > 0:
            for r in rungs:
                if b1[3] > r > floor:
                    floor = r
    detail['stop_fire'] = post[fire_idx][0] if fire_idx is not None else None
    detail['stop_px'] = fire_stop

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
        pnl += runner_qty * (t['exit'] - entry)
    return pnl, detail


def run():
    trades_doc = get(f'{BASE}/api/trades', 'trades.json')
    kev = get(f'{BASE}/api/kev_watchlist', 'kev.json')
    levels_by_date = kev.get('_levels', {}) if isinstance(kev, dict) else {}

    cohort = [t for t in trades_doc['trades']
              if t['date'] >= START and t.get('entry_type') != 'hidden_entry']
    cohort.sort(key=lambda t: (t['date'], t.get('entry_ts_utc') or ''))
    raw_total = sum(t['pnl'] for t in cohort)
    print('Cohort N=%d non-hidden era trades, raw book $%.2f' % (len(cohort), raw_total),
          flush=True)

    rows = []          # one per trade
    recon_gap = 0.0
    for i, t in enumerate(cohort):
        lane = t.get('entry_type') or '?'
        pf = [(float(q), float(px)) for q, px in (t.get('partial_fills') or [])]
        row = {'t': t, 'lane': lane, 'pf': pf, 'status': None,
               'trail': t['pnl'], 'flat': t['pnl'],
               'det_trail': None, 'det_flat': None}
        if pf:
            legs = sum(q * (px - t['entry']) for q, px in pf) + \
                (t['shares'] - sum(q for q, _ in pf)) * (t['exit'] - t['entry'])
            recon_gap += abs(legs - t['pnl'])
        if not pf:
            row['status'] = 'NO_FILLS'
        elif lane in NOT_MODELED_LANES:
            row['status'] = 'NOT_MODELED'
        else:
            t_ent = parse_ts(t.get('entry_ts_utc'))
            if t_ent is None:
                row['status'] = 'NOT_TIMED'
            else:
                path = get_bars(t['ticker'], t['date'])
                if path and not any(b[0] >= t_ent for b in path):
                    path = None
                if path is None:
                    row['status'] = 'NO_BARS'
                else:
                    row['status'] = 'CHECKED'
                    rungs = map_rungs(levels_by_date, t)
                    slip = trade_slip(t)
                    row['trail'], row['det_trail'] = benchmark_trade(
                        t, path, t_ent, rungs, slip, trail=True)
                    row['flat'], row['det_flat'] = benchmark_trade(
                        t, path, t_ent, rungs, slip, trail=False)
        rows.append(row)
        if (i + 1) % 20 == 0:
            print('  %d/%d trades processed' % (i + 1, len(cohort)), flush=True)

    json.dump([{ "ticker": r["t"]["ticker"], "date": r["t"]["date"],
                 "trade_id": r["t"].get("trade_id"), "lane": r["lane"],
                 "status": r["status"], "raw": r["t"]["pnl"],
                 "trail": r.get("trail"), "flat": r.get("flat")} for r in rows],
              open("core_lanes_20260814_PER_TRADE.json", "w"), indent=1, default=str)
    print("per-trade dump written: %d rows" % len(rows), flush=True)

    def agg(sub):
        raw = sum(r['t']['pnl'] for r in sub)
        trail = sum(r['trail'] for r in sub)
        flat = sum(r['flat'] for r in sub)
        fic_trail = sum(len(r['det_trail']['fiction']) for r in sub if r['det_trail'])
        fic_flat = sum(len(r['det_flat']['fiction']) for r in sub if r['det_flat'])
        fic_trades_flat = sum(1 for r in sub if r['det_flat'] and r['det_flat']['fiction'])
        return raw, trail, flat, fic_trail, fic_flat, fic_trades_flat

    L = []
    L.append('CORE-LANES SEQUENCE-HONEST CHECK (non-hidden, era 7/24+) — run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Engine: v4 timing-corrected benchmark (hidden_exit_fourarm_v4), FILLS-ONLY')
    L.append('scope: runner legs ALWAYS at recorded exit; only partial fills re-adjudicated.')
    L.append('Bracket: [TRAIL = strict, hidden-style trail tightens the stop] .. [FLAT-STOP =')
    L.append('charitable, stop frozen at recorded stop_loss].  Honest number lies between.')
    L.append('Assumptions + caveats: see docstring.  Read-only run.')
    L.append('')
    n_status = defaultdict(int)
    for r in rows:
        n_status[r['status']] += 1
    L.append('Cohort N=%d | status: %s' % (len(rows), dict(n_status)))
    L.append('Leg reconciliation: sum |recorded-legs pnl - recorded pnl| = $%.2f' % recon_gap)
    L.append('')

    L.append('================ PER LANE (era 7/24+) ================')
    L.append('%-13s %3s %4s  %10s  %10s  %10s  %s' %
             ('lane', 'N', 'w/pf', 'RAW book', 'FLAT(char)', 'TRAIL(str)', 'fiction fills flat/trail'))
    lanes = sorted({r['lane'] for r in rows})
    for lane in lanes:
        sub = [r for r in rows if r['lane'] == lane]
        raw, trail, flat, ft, ff, _ = agg(sub)
        tag = '  [NOT MODELED — needs its own pass]' if lane in NOT_MODELED_LANES else ''
        L.append('%-13s %3d %4d  $%9.2f  $%9.2f  $%9.2f  %d / %d%s' %
                 (lane, len(sub), sum(1 for r in sub if r['pf']), raw, flat, trail, ff, ft, tag))
    raw, trail, flat, ft, ff, ftr = agg(rows)
    L.append('%-13s %3d %4d  $%9.2f  $%9.2f  $%9.2f  %d / %d' %
             ('TOTAL era', len(rows), sum(1 for r in rows if r['pf']), raw, flat, trail, ff, ft))
    L.append('')

    aug = [r for r in rows if r['t']['date'] >= AUG_START]
    raw_a, trail_a, flat_a, ft_a, ff_a, ftr_a = agg(aug)
    L.append('================ AUGUST CORE HEADLINE (non-hidden, 8/1+) ================')
    L.append('  RAW book (charitable claim basis):  $%.2f   (claim on the table: +$%.0f)'
             % (raw_a, CLAIM_AUG_CORE))
    L.append('  SEQUENCE-HONEST BRACKET:            $%.2f (strict/trail) .. $%.2f (charitable/flat-stop)'
             % (trail_a, flat_a))
    L.append('  Timing-fiction removed:             $%.2f (trail) / $%.2f (flat)'
             % (raw_a - trail_a, raw_a - flat_a))
    L.append('  Fiction fills (flat/trail):         %d / %d across %d trades (flat)'
             % (ff_a, ft_a, ftr_a))
    L.append('')

    L.append('================ BIGGEST SPECIMENS (fiction removed, FLAT variant) ================')
    def removed(r, key):
        d = r['det_%s' % key]
        return sum(q * (px - ex) for q, px, ex in d['fiction']) if d else 0.0
    spec = sorted((r for r in rows if r['det_flat'] and r['det_flat']['fiction']),
                  key=lambda r: -removed(r, 'flat'))[:8]
    for r in spec:
        t = r['t']
        d = r['det_flat']
        L.append('  %-5s %s %-12s raw $%+8.2f -> flat $%+8.2f (removed $%.2f, %d fill(s));'
                 ' trail $%+8.2f | stop-fire %s' %
                 (t['ticker'], t['date'], r['lane'], t['pnl'], r['flat'],
                  removed(r, 'flat'), len(d['fiction']), r['trail'],
                  d['stop_fire'].astimezone(EASTERN_TZ).strftime('%H:%M:%S ET')
                  if d['stop_fire'] else 'never'))
        for q, px, ex in d['fiction']:
            L.append('      FICTION %8.2f sh @ $%.4f (first touch after/never before stop) -> re-exit $%.4f'
                     % (q, px, ex))
    if not spec:
        L.append('  (none — no fiction fills found under the flat-stop variant)')
    L.append('')

    unchecked = [r for r in rows if r['pf'] and r['status'] != 'CHECKED']
    L.append('================ UNCHECKABLE TRADES WITH FILLS (recorded pnl kept) ================')
    for r in unchecked:
        t = r['t']
        L.append('  %-5s %s %-12s pnl $%+8.2f  [%s]' %
                 (t['ticker'], t['date'], r['lane'], t['pnl'], r['status']))
    L.append('')
    L.append('CAVEATS (owed at Friday review):')
    L.append(' 1. FILLS-ONLY scope: runner legs kept at recorded exits — any runner-leg')
    L.append('    fiction (exit px never printed post-entry) is NOT tested here.')
    L.append(' 2. TRAIL variant borrows hidden\'s trail mechanics (BE-after-2-scales, rung')
    L.append('    floors); the core lanes\' real trail rules differ per lane — treat TRAIL as')
    L.append('    a strictness bound, not that lane\'s true replay.')
    L.append(' 3. Same-bar touch-vs-stop tie favors the fill (v4 A5): bracket is charitable')
    L.append('    on ties in BOTH variants.')
    L.append(' 4. halt_ladder [NOT MODELED]; %d NOT_TIMED + NO_BARS fills-trades keep'
             % len([r for r in unchecked if r['status'] in ('NOT_TIMED', 'NO_BARS')]))
    L.append('    recorded pnl uncorrected — each is an unverified dollar figure.')
    L.append(' 5. Bars gaps: any live fill off-SIP that the 10s tape never shows would be')
    L.append('    wrongly marked fiction (v4 known limitation, both directions).')
    L.append('')
    L.append('No recommendation — numbers only; the full room verifies Friday, Marcos decides.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    run()
