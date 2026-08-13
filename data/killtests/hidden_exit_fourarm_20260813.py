#!/usr/bin/env python3
"""FOUR-ARM HIDDEN-EXIT COMPARISON kill-test (2026-08-13).

Cohort: completed trades entry_type==hidden_entry, 2026-07-24..2026-08-12 (8/13 excluded).
Read-only vs live services. Results -> hidden_exit_fourarm_20260813_RESULTS.txt.

Arms (sizing = trade's real shares):
 1 GRID:    1/3 @ first-trim (actual first partial price if recorded else entry*1.02),
            1/3 @ entry*1.5, 1/3 @ entry*2.0; remainder rides ratchet.
 2 LEVELS:  quarters @ map levels above entry (targets+next_supply, sorted, through-touch);
            unfilled quarters ride ratchet. Mapless -> ratchet-only (labeled).
 3 RATCHET: one 1/3 trim (same as arm 1 first trim), rest ratchet only.
 4 HYBRID:  each pct rung replaced by the lowest unused map level BELOW it (if any);
            remainder rides ratchet.

Ratchet (all arms): once +10% -> floor = max(entry, high*0.90); once +25% -> high*0.95.
Exit when bar low <= floor; FILL = floor*0.97 (FGI live measurement -3.0%).
Tier fills only when path trades THROUGH: bar high > tier*1.001.
End-of-data: remaining shares exit at the trade's real exit price.

Fidelity: per-trade 10s bars (~10S preferred, ~ALP10S fallback) windowed
entry_ts_utc..recorded_at; else 3-point model entry -> highest -> exit
(tiers <= highest fill; ratchet evaluated off highest, then exit).
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone

BASE = 'https://zestful-intuition-production-b16a.up.railway.app'
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.fourarm_cache_20260813')
os.makedirs(CACHE, exist_ok=True)
OUT = os.path.join(HERE, 'hidden_exit_fourarm_20260813_RESULTS.txt')
START, END = '2026-07-24', '2026-08-12'

def get(url, cache_key):
    p = os.path.join(CACHE, cache_key)
    if os.path.exists(p):
        return json.load(open(p))
    try:
        d = json.load(urllib.request.urlopen(url, timeout=30))
    except Exception:
        d = None
    json.dump(d, open(p, 'w'))
    return d

def parse_ts(s):
    if not s: return None
    s = s.replace('Z', '+00:00').replace('+0000', '+00:00')
    try: return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception: return None

def get_bars(ticker, date, t_ent, t_exit):
    """Return list of (high, low) 10s bars in [t_ent, t_exit], or None."""
    for suf in ('~10S', '~ALP10S'):
        key = f'bars_{ticker}{suf}_{date}.json'
        d = get(f'{BASE}/api/bars?ticker={urllib.parse.quote(ticker + suf)}&date={date}', key)
        bars = (d or {}).get('bars') or []
        if not bars: continue
        out = []
        for b in bars:
            t = parse_ts(b['time'])
            if t is None or t < t_ent or (t_exit and t > t_exit): continue
            out.append((float(b['high']), float(b['low'])))
        if len(out) >= 3:
            return out
    return None

def ratchet_floor(entry, high):
    g = (high - entry) / entry
    if g >= 0.25: return high * 0.95
    if g >= 0.10: return max(entry, high * 0.90)
    return None

def replay(trade, tiers, tier_sizes, path, real_exit):
    """tiers: list of prices; tier_sizes: shares per tier. Remaining shares ride ratchet.
    path: list of (high, low). Returns (pnl_dollars, fills list of (label, shares, price))."""
    entry = trade['entry']; shares = trade['shares']
    remaining = float(shares)
    fills = []
    tier_state = [False] * len(tiers)
    high_so_far = entry
    done = False
    for hi, lo in path:
        # tiers first (favor the up-move within the bar), in ascending price order
        order = sorted(range(len(tiers)), key=lambda i: tiers[i])
        for i in order:
            if done or tier_state[i] or remaining <= 0: continue
            if hi > tiers[i] * 1.001:
                sz = min(tier_sizes[i], remaining)
                if sz > 0:
                    fills.append((f'tier@{tiers[i]:.4f}', sz, tiers[i]))
                    remaining -= sz
                tier_state[i] = True
        if remaining <= 0: done = True; break
        high_so_far = max(high_so_far, hi)
        fl = ratchet_floor(entry, high_so_far)
        if fl is not None and lo <= fl:
            px = fl * 0.97
            fills.append((f'ratchet@{fl:.4f}->fill', remaining, px))
            remaining = 0; done = True; break
    if remaining > 0:
        fills.append(('end-of-data(real exit)', remaining, real_exit))
        remaining = 0
    pnl = sum(sz * (px - entry) for _, sz, px in fills)
    return pnl, fills

def three_point_path(trade):
    """Conservative sequence: entry -> highest -> exit."""
    e, h, x = trade['entry'], trade['highest'] or trade['entry'], trade['exit']
    return [(e, e), (h, min(e, h)), (h, min(x, h)), (x, x)]

def first_trim_price(t):
    pf = t.get('partial_fills') or []
    if pf:
        try: return float(pf[0][1])
        except Exception: pass
    return t['entry'] * 1.02

def map_levels(levels_by_date, t):
    d = (levels_by_date.get(t['date']) or {}).get(t['ticker'])
    if not d: return None
    lv = []
    for x in (d.get('targets') or []):
        try: lv.append(float(x))
        except Exception: pass
    ns = d.get('next_supply')
    if ns:
        try: lv.append(float(ns))
        except Exception: pass
    lv = sorted({v for v in lv if v > t['entry'] * 1.001})
    return lv  # may be empty list (map exists, no levels above entry)

def run():
    trades_doc = get(f'{BASE}/api/trades', 'trades.json')
    kev = get(f'{BASE}/api/kev_watchlist', 'kev.json')
    levels_by_date = kev.get('_levels', {}) if isinstance(kev, dict) else {}

    cohort = [t for t in trades_doc['trades']
              if t.get('entry_type') == 'hidden_entry' and START <= t['date'] <= END]
    cohort.sort(key=lambda t: (t['date'], t.get('entry_ts_utc') or ''))

    arms = {1: 'GRID (current)', 2: 'LEVEL-TIERS', 3: 'RATCHET-PRIMARY', 4: 'HYBRID'}
    results = {a: [] for a in arms}   # (trade, pnl, fills, fidelity)
    fidelity_count = {'bars': 0, '3pt': 0}
    mapless = 0        # no _levels entry at all for (date, ticker)
    no_level_above = 0 # map exists but no marked level above entry

    for t in cohort:
        entry = t['entry']; shares = t['shares']
        t_ent = parse_ts(t.get('entry_ts_utc'))
        t_exit = parse_ts(t.get('recorded_at'))
        path = get_bars(t['ticker'], t['date'], t_ent, t_exit) if t_ent else None
        if path:
            fid = 'bars'
        else:
            fid = '3pt'; path = three_point_path(t)
        fidelity_count[fid] += 1
        ft = first_trim_price(t)
        third = shares / 3.0; quarter = shares / 4.0
        lv = map_levels(levels_by_date, t)
        if lv is None: mapless += 1
        elif lv == []: no_level_above += 1

        # Arm 1 GRID
        p, f = replay(t, [ft, entry*1.5, entry*2.0], [third]*3, path, t['exit'])
        results[1].append((t, p, f, fid))
        # Arm 2 LEVEL-TIERS
        if lv:
            tiers = lv[:3]
            p, f = replay(t, tiers, [quarter]*len(tiers), path, t['exit'])
        else:
            p, f = replay(t, [], [], path, t['exit'])
        results[2].append((t, p, f, fid))
        # Arm 3 RATCHET-PRIMARY
        p, f = replay(t, [ft], [third], path, t['exit'])
        results[3].append((t, p, f, fid))
        # Arm 4 HYBRID
        rungs = [ft, entry*1.5, entry*2.0]
        used = set(); tiers4 = []
        for r in rungs:
            cand = [v for v in (lv or []) if v < r and v not in used]
            if cand:
                pick = max(cand)  # closest marked level below the rung
                used.add(pick); tiers4.append(pick)
            else:
                tiers4.append(r)
        p, f = replay(t, tiers4, [third]*3, path, t['exit'])
        results[4].append((t, p, f, fid))

    # ---- report ----
    L = []
    L.append('FOUR-ARM HIDDEN-EXIT COMPARISON — kill-test run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Cohort: entry_type==hidden_entry, %s..%s (8/13 EXCLUDED for tonight rerun). N=%d'
             % (START, END, len(cohort)))
    L.append('')
    L.append('ASSUMPTIONS (all stated up front):')
    L.append(' - Read-only replay; sizing = each trade\'s REAL shares; dollars through that chain.')
    L.append(' - Path fidelity: 10s bars (TICKER~10S pref, ~ALP10S fallback) windowed entry_ts_utc..recorded_at;')
    L.append('   fallback = 3-point model entry->highest->exit (conservative: high precedes final exit).')
    L.append('   Split: %d trades on 10s bars, %d on 3-point model.' % (fidelity_count['bars'], fidelity_count['3pt']))
    L.append(' - Tier fill only when path trades THROUGH: bar high > tier*1.001; fill at tier price.')
    L.append(' - Ratchet: floor active at +10% = max(entry, high*0.90); at +25% = high*0.95;')
    L.append('   exit when bar low <= floor; FILL = floor*0.97 (FGI live measurement 13.80->13.38 = -3.0%).')
    L.append(' - Within a bar, tier fills are taken before the ratchet check (favors the up-move).')
    L.append(' - End-of-data: remaining shares exit at the trade\'s REAL recorded exit price.')
    L.append(' - Arm 1 first trim = actual first partial price when recorded, else entry*1.02.')
    L.append(' - Arm 2 ratchet-only trades: no _levels map entry = %d; map present but NO marked level above entry = %d.' % (mapless, no_level_above))
    L.append(' - Arm 4 rung substitution: closest unused marked level below each percentage rung.')
    L.append(' - Fractional shares used in the arithmetic (real thirds/quarters of real share counts).')
    L.append(' - No commissions/borrow modeled; real trades\' recorded pnl includes what it includes.')
    L.append('')
    real_total = sum(t['pnl'] for t in cohort)
    L.append('REAL BOOK (recorded pnl, this cohort): $%.2f  (baseline for comparison)' % real_total)
    L.append('')

    def block(name, rows):
        pnls = [p for _, p, _, _ in rows]
        n = len(pnls)
        tot = sum(pnls); mean = tot / n if n else 0
        wins = sum(1 for p in pnls if p > 0)
        best = max(rows, key=lambda r: r[1]); worst = min(rows, key=lambda r: r[1])
        top3 = sorted(rows, key=lambda r: -r[1])[:3]
        out = ['%s' % name,
               '  total $%.2f | mean $%.2f/trade | win rate %.1f%% (%d/%d)' % (tot, mean, 100.0*wins/n, wins, n),
               '  best  %s %s  $%.2f' % (best[0]['ticker'], best[0]['date'], best[1]),
               '  worst %s %s  $%.2f' % (worst[0]['ticker'], worst[0]['date'], worst[1]),
               '  top-3 monsters (tail $): ' + ', '.join('%s %s $%.2f' % (r[0]['ticker'], r[0]['date'], r[1]) for r in top3)
               + '  | tail total $%.2f' % sum(r[1] for r in top3)]
        return out

    L.append('================ ALL TRADES (N=%d) ================' % len(cohort))
    for a in arms:
        L += block('ARM %d — %s' % (a, arms[a]), results[a]); L.append('')

    # FGI-class subset: MFE >= +30%
    def mfe(t):
        return ((t['highest'] or t['entry']) - t['entry']) / t['entry']
    fgi_ids = {id(t) for t in cohort if mfe(t) >= 0.30}
    L.append('================ FGI-CLASS SUBSET (MFE >= +30%%): N=%d ================' % len(fgi_ids))
    for a in arms:
        rows = [r for r in results[a] if id(r[0]) in fgi_ids]
        if rows: L += block('ARM %d — %s' % (a, arms[a]), rows); L.append('')

    # trace: biggest hidden winner by real pnl
    star = max(cohort, key=lambda t: t['pnl'])
    L.append('================ NAMED TRACE (dollars-not-R law) ================')
    L.append('Trade: %s %s | entry $%.4f x %d sh | stop %.4f | highest %.4f | real exit %.4f | real pnl $%.2f | fills fidelity: %s'
             % (star['ticker'], star['date'], star['entry'], star['shares'], star['stop_loss'],
                star['highest'], star['exit'], star['pnl'],
                next(fid for tt, _, _, fid in results[1] if tt is star)))
    for a in arms:
        tt, p, f, fid = next(r for r in results[a] if r[0] is star)
        L.append(' ARM %d — %s: pnl $%.2f' % (a, arms[a], p))
        for label, sz, px in f:
            L.append('    %-28s %8.2f sh @ $%.4f  -> $%+.2f' % (label, sz, px, sz*(px - tt['entry'])))
    L.append('')
    L.append('No recommendation — numbers only; the decision is Marcos\'s on Friday.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))

if __name__ == '__main__':
    run()
