#!/usr/bin/env python3
"""HIDDEN-LANE FIX SWEEP (2026-08-13) — entry dead, or exit killing a live signal?

Marcos: "so hidden as an entry is broken? Well, fix it."

Base engine = the CALIBRATED honest model from hidden_exit_fourarm_v4_20260813.py
(post-entry-only fills, INTRABAR stops on 10s bar lows, slippage
min(3%, max(0.8%, est_slippage/100)), 3% when unrecorded).  The room certified
that model at -9.3%/$0.00-median vs the stop-consistent benchmark.  Same 131
hidden trades (entry_type==hidden_entry, 7/24..8/13).  READ-ONLY; bars from the
.fourarm_cache_v4_20260813 cache (v3/v2 fallback copy handled by the imported
module).  Every variant = the SAME entries, different exit/stop config.

VARIANTS
 A  BASELINE          current config: live tiers (33%@+1R, 55%@x1.5, 75%@x2),
                      scale-bar ratchet + BE-after-2 + rung floors + trailing +
                      health fold + intrabar stop.  Must reproduce ~ -$2,156.
 B  WIDER STOP xB     original structural stop * buffer {1.00, 0.95, 0.90};
                      NO scale-bar ratchet / BE / rung floors until tier-2 has
                      filled; from tier-2 on, full live mechanics resume.
 C  DELAYED BE        baseline but BE floor arrives only after tier-2
                      (BE_FLOOR_AFTER_SCALE=2).  NOTE: live env default IS
                      already 2 (marcos_trading_bot.py:455), and the certified
                      v4 baseline model uses 2 — so C == A by construction.
                      C1 (BE-after-1, the code-default-if-unset branch :452) is
                      run as the CONTRAST so both semantics are priced.
 D  TIME-STOP HYBRID  static stop = max(original structural stop, entry*0.94)
                      (-6% catastrophe); tiers still fill; NO trail/BE/rung/
                      health; if neither tier-1 nor stop hit by entry+45min,
                      exit remaining at that bar's open.
 E  RE-ENTRY          baseline everywhere; if the baseline replay ends on a
                      stop fill, scan the next 20min of tape — first bar whose
                      HIGH reclaims the original entry px triggers ONE
                      re-entry, same shares, buy at entry*(1+slip) (full
                      slippage charged both times); re-entered position runs
                      the full baseline config from that bar (fresh original
                      stop, tiers continue from where they were NOT — tiers
                      restart from tier-1; stated assumption S5).
 F  NO-STOP CONTROL   (diagnostic only, NEVER shippable) no tiers, no trail,
                      no health; only a -7% catastrophe stop (entry*0.93,
                      intrabar, slipped); hold to EOD 15:45 (9:25 for PRE) /
                      end of tape.  Pure measure of the ENTRY signal.
 G  F + 1R BANK       tier-1 = 50% off at entry+1R; remainder = F rules
                      (-7% catastrophe only, to EOD).

ASSUMPTIONS
 S1. All engine assumptions A1-A11 of the v4 script are inherited verbatim
     (real shares, dollars end-to-end, tier fills strictly-through / fill AT,
     within-bar order = tier fills then stop, MinuteAgg rung clears on 1-min
     closes, health fold on 3-min closes where enabled).
 S2. 2 trades have no post-entry 10s bars -> three_point_replay fallback with
     each variant's tier ladder (for F that is runner-at-recorded-exit).
     Counted and reported; they carry no partial fills.
 S3. B's "original stop until tier-2" = the buffered structural stop is the
     ONLY stop component until the 2nd tier fills; then trail/BE/rung resume
     from the then-current bar (trail seeded at max(buffered stop, entry) via
     the BE-after-2 rule).
 S4. D's 45-min clock runs from entry_ts_utc; the time exit fills at the
     first bar OPEN at/after entry+45min (no slippage on a marketable time
     exit beyond the recorded-open print; same convention as the engine's
     9:25/15:45 time stops).
 S5. E re-entry restarts the tier ladder (fresh 33/55/75 off the same entry
     px and original R) and the original structural stop; one re-entry max;
     re-entry buy slipped entry*(1+slip), all exit fills slipped as usual.
 S6. F/G catastrophe = entry*0.93 fixed (STOP_LOSS_PCT=0.07 live constant,
     marcos_trading_bot.py:293); D catastrophe = entry*0.94 per the sweep
     spec (-6%); both intrabar, exit at stop*(1-slip).
 S7. Max-DD proxy = sum of losing trades' P&L (no intraday equity curve).
 S8. NO recommendation — numbers only; the full room verifies, Marcos
     decides before 03:55.

Results -> hidden_fix_sweep_20260813_RESULTS.txt
"""
import os, sys
from datetime import timedelta, timezone, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hidden_exit_fourarm_v4_20260813 as eng  # noqa: E402  (engine reuse)

EASTERN_TZ = eng.EASTERN_TZ
OUT = os.path.join(HERE, 'hidden_fix_sweep_20260813_RESULTS.txt')


# ---------------------------------------------------------------------------
# Generalized replay: v4 live_replay with a config dict.
# cfg keys:
#   tiers            list[(px, cumfrac)]  ([] = none)
#   scalebar         bool   scale-bar-low ratchet on tier fills
#   be_after         int|None  BE floor after this many tier fills (None=never)
#   rung_floors      bool
#   health_fold      bool
#   stop_mult        float  initial stop = stop0 * stop_mult
#   freeze_until_tier int   mechanics (ratchet/BE/rung/health) frozen until
#                           this many tiers filled; stop stays at initial
#   catastrophe      float|None  floor stop at entry*(1-catastrophe)
#   structural_stop  bool   include the structural stop at all (False for F/G)
#   time_stop_min    int|None  exit remaining at bar open >= entry+N min if
#                           tier-1 not yet filled and not stopped
# Returns (pnl, fills, stop_bar_index_or_None)
# ---------------------------------------------------------------------------
def replay_cfg(t, rungs, day_bars, t_ent, slip, cfg, start_idx=0,
               entry_override=None):
    entry = entry_override if entry_override is not None else t['entry']
    ref_entry = t['entry']
    shares = float(t['shares'])
    stop0 = (t.get('stop_loss') or ref_entry * 0.94) * cfg['stop_mult']
    tiers = cfg['tiers']
    remaining, sold_cum = shares, 0.0
    tier_idx, partial_taken = 0, False
    current_stop = stop0 if cfg['structural_stop'] else 0.0
    cat = ref_entry * (1 - cfg['catastrophe']) if cfg['catastrophe'] else 0.0
    floor = 0.0
    path = [b for b in day_bars if b[0] >= t_ent][start_idx:]
    tape_hi = None
    is_pre = (t.get('entry_session') == 'PRE')
    m1, m3 = eng.MinuteAgg(1), eng.MinuteAgg(3)
    m1v = []
    fills = []
    deadline = (t_ent + timedelta(minutes=cfg['time_stop_min'])
                if cfg['time_stop_min'] else None)
    stop_bar = None

    def sell(label, qty, px):
        nonlocal remaining
        qty = min(qty, remaining)
        if qty <= 0:
            return
        fills.append((label, qty, px))
        remaining -= qty

    for bi, (ts, o, h, l, c, v) in enumerate(path):
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
        if deadline and tier_idx == 0 and ts >= deadline:
            sell('time_stop_45m@%.4f' % o, remaining, o)
            break
        tape_hi = h if tape_hi is None else max(tape_hi, h)
        # 1) tier fills (post-entry tape strictly through the level)
        while tier_idx < len(tiers) and remaining > 0:
            tp, cum = tiers[tier_idx]
            if tape_hi > tp:
                qty = shares if cum >= 1.0 else max(1.0, shares * cum - sold_cum)
                qty = min(qty, remaining)
                sell(f'tier{tier_idx+1}@{tp:.4f}', qty, tp)
                sold_cum += qty
                tier_idx += 1
                partial_taken = True
                live_mech = tier_idx >= cfg['freeze_until_tier']
                if live_mech and cfg['structural_stop']:
                    if cfg['be_after'] is not None and tier_idx >= cfg['be_after']:
                        current_stop = max(current_stop, ref_entry)
                    if cfg['scalebar'] and l > current_stop:
                        current_stop = l
            else:
                break
        if remaining <= 0:
            break
        live_mech = tier_idx >= cfg['freeze_until_tier']
        # 2) INTRABAR stop
        eff = 0.0
        if cfg['structural_stop']:
            eff = current_stop
        if cfg['catastrophe']:
            eff = max(eff, cat)
        if live_mech and cfg['rung_floors'] and partial_taken:
            eff = max(eff, floor)
        if eff > 0 and l <= eff:
            lbl = ('rung_ratchet' if (partial_taken and floor >= current_stop and floor > 0
                                      and cfg['rung_floors'])
                   else ('trail_stop' if partial_taken else 'stop_loss'))
            sell(f'{lbl}@{eff:.4f}(intrabar)', remaining, eff * (1 - slip))
            stop_bar = start_idx + bi
            break
        # 3) completed 1-min bar -> rung clears
        b1 = m1.push(ts, o, h, l, c, v)
        if b1 is not None:
            m1v.append((b1[3], b1[4]))
            if live_mech and cfg['rung_floors'] and partial_taken:
                for r in rungs:
                    if b1[3] > r > floor:
                        floor = r
        # 4) completed 3-min bar -> health fold
        b3 = m3.push(ts, o, h, l, c, v)
        if b3 is not None and cfg['health_fold']:
            c3 = b3[3]
            if live_mech and partial_taken and len(m3.completed) >= 3:
                e9 = eng.ema9([b[3] for b in m3.completed[-12:]])
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
    return pnl, fills, stop_bar


BASE_CFG = dict(scalebar=True, be_after=2, rung_floors=True, health_fold=True,
                stop_mult=1.0, freeze_until_tier=0, catastrophe=None,
                structural_stop=True, time_stop_min=None)


def cfg_for(name, t, lv):
    tiers = eng.live_tiers(t)
    c = dict(BASE_CFG, tiers=tiers)
    if name == 'A':
        return c
    if name.startswith('B'):
        buf = {'B100': 1.00, 'B95': 0.95, 'B90': 0.90}[name]
        return dict(c, stop_mult=buf, freeze_until_tier=2)
    if name == 'C1':
        return dict(c, be_after=1)
    if name == 'C2':
        return dict(c)  # == A; live env default already 2
    if name == 'D':
        return dict(c, scalebar=False, be_after=None, rung_floors=False,
                    health_fold=False, catastrophe=0.06, time_stop_min=45)
    if name == 'F':
        return dict(c, tiers=[], scalebar=False, be_after=None,
                    rung_floors=False, health_fold=False,
                    structural_stop=False, catastrophe=0.07)
    if name == 'G':
        entry = t['entry']
        R = max(entry - (t.get('stop_loss') or entry * 0.94), 0.01)
        return dict(c, tiers=[(round(entry + R, 4), 0.50)], scalebar=False,
                    be_after=None, rung_floors=False, health_fold=False,
                    structural_stop=False, catastrophe=0.07)
    raise ValueError(name)


def run_variant(name, prep):
    rows = []
    for p in prep:
        t = p['t']
        cfg = cfg_for(name if name != 'E' else 'A', t, p['lv'])
        if not p['path']:
            pnl, fills = eng.three_point_replay(t, cfg['tiers'], t['exit'], None)
            rows.append((t, pnl, fills, '3pt'))
            continue
        pnl, fills, stop_bar = replay_cfg(t, p['rungs'], p['path'], p['t_ent'],
                                          p['slip'], cfg)
        note = 'bars'
        if name == 'E' and stop_bar is not None:
            post = [b for b in p['path'] if b[0] >= p['t_ent']]
            fire_ts = post[stop_bar][0]
            re_idx = None
            for j in range(stop_bar + 1, len(post)):
                if post[j][0] > fire_ts + timedelta(minutes=20):
                    break
                if post[j][2] >= t['entry']:
                    re_idx = j
                    break
            if re_idx is not None:
                buy_px = t['entry'] * (1 + p['slip'])
                pnl2, fills2, _ = replay_cfg(t, p['rungs'], p['path'],
                                             p['t_ent'], p['slip'], cfg,
                                             start_idx=re_idx,
                                             entry_override=buy_px)
                fills = fills + [('REENTRY buy@%.4f' % buy_px, 0.0, buy_px)] + \
                    [('re:' + lb, q, px) for lb, q, px in fills2]
                pnl = pnl + pnl2
                note = 'bars+reentry'
        rows.append((t, pnl, fills, note))
    return rows


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


VARIANTS = [
    ('A',    'BASELINE — current live config (must reproduce ~ -$2,156)'),
    ('B100', 'WIDER STOP x1.00 — original stop, NO ratchet/BE/rung until tier-2'),
    ('B95',  'WIDER STOP x0.95 — stop 5% wider, frozen until tier-2'),
    ('B90',  'WIDER STOP x0.90 — stop 10% wider, frozen until tier-2'),
    ('C2',   'DELAYED BE (BE_FLOOR_AFTER_SCALE=2) — == baseline; env already 2'),
    ('C1',   'CONTRAST: BE-after-1 (the code-default-if-unset branch)'),
    ('D',    'TIME-STOP HYBRID — static stop+(-6%)cat, 45min time-out pre-tier1'),
    ('E',    'RE-ENTRY-AFTER-STOP — baseline + one 20-min entry-px reclaim re-entry'),
    ('F',    'NO-STOP CONTROL — hold to EOD, only -7% catastrophe (DIAGNOSTIC ONLY)'),
    ('G',    'F + 1R BANK — 50% off at +1R, rest to EOD with -7% catastrophe'),
]

ENV_MAP = {
    'A':    'live today (HIDDEN_SCALEBAR_STOP=1, BE_FLOOR_AFTER_SCALE=2 env default)',
    'B100': 'PARTIAL tonight: HIDDEN_SCALEBAR_STOP=0 kills the ratchet (bot :5527/:8864); '
            'but BE/rung freeze-until-tier-2 NEEDS CODE (BE fires per BE_FLOOR_AFTER_SCALE '
            'and rung floors arm on first partial regardless)',
    'B95':  'NEEDS CODE — no env widens the structural stop by a buffer '
            '(STOP_LOSS_PCT only moves the -7% catastrophe floor)',
    'B90':  'NEEDS CODE — same as B95',
    'C2':   'live today — BE_FLOOR_AFTER_SCALE env default is already 2 (bot :455)',
    'C1':   'env-only tonight: BE_FLOOR_AFTER_SCALE=1',
    'D':    'NEEDS CODE — no 45-min time-stop or static-stop mode exists for hidden',
    'E':    'NEEDS CODE — no re-entry-after-stop mechanism exists',
    'F':    'NEVER SHIPPABLE (diagnostic); approximable but not honestly: '
            'no env removes the structural stop',
    'G':    'NEEDS CODE — tier ladder + stop removal both differ from live',
}


def main():
    # ---- pull cohort + prep exactly as the engine does ----
    trades_doc = eng.get(f'{eng.BASE}/api/trades', 'trades.json')
    kev = eng.get(f'{eng.BASE}/api/kev_watchlist', 'kev.json')
    levels_by_date = kev.get('_levels', {}) if isinstance(kev, dict) else {}
    cohort = [t for t in trades_doc['trades']
              if t.get('entry_type') == 'hidden_entry'
              and eng.START <= t['date'] <= eng.END]
    cohort.sort(key=lambda t: (t['date'], t.get('entry_ts_utc') or ''))
    print('Cohort N=%d raw book $%.2f' % (len(cohort), sum(t['pnl'] for t in cohort)),
          flush=True)

    prep = []
    for t in cohort:
        t_ent = eng.parse_ts(t.get('entry_ts_utc'))
        path = eng.get_bars(t['ticker'], t['date']) if t_ent else None
        if path and not any(b[0] >= t_ent for b in path):
            path = None
        prep.append({'t': t, 'path': path, 't_ent': t_ent,
                     'rungs': eng.map_rungs(levels_by_date, t) or [],
                     'lv': eng.level_targets(levels_by_date, t),
                     'slip': eng.trade_slip(t)})
    nb = sum(1 for p in prep if not p['path'])

    L = []
    L.append('HIDDEN-LANE FIX SWEEP — run %s'
             % datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'))
    L.append('Cohort: entry_type==hidden_entry %s..%s, N=%d (%d on 3pt fallback).'
             % (eng.START, eng.END, len(cohort), nb))
    L.append('Engine: v4 calibrated honest model (intrabar stops, post-entry fills,')
    L.append('slip=min(3%%,max(0.8%%,est)); certified -9.3%%/$0.00-median vs benchmark).')
    L.append('QUESTION: entry dead, or exit killing a live signal?  F answers it.')
    L.append('Assumptions S1-S8 in the script docstring.  NO recommendation.')
    L.append('')

    all_rows = {}
    for name, desc in VARIANTS:
        rows = run_variant(name, prep)
        all_rows[name] = rows
        pnls = [r[1] for r in rows]
        tot = sum(pnls)
        wins = sum(1 for x in pnls if x > 0)
        losses = sum(x for x in pnls if x < 0)
        top3 = sorted(rows, key=lambda r: -r[1])[:3]
        L.append('VARIANT %-4s %s' % (name, desc))
        L.append('  total $%+.2f | median $%+.2f | win %.1f%% (%d/%d) | '
                 'max-DD-proxy (sum of losses) $%.2f'
                 % (tot, median(pnls), 100.0 * wins / len(pnls), wins, len(pnls), losses))
        L.append('  top-3 tail: %s (tail $%+.2f) | ex-top-1 total $%+.2f'
                 % (', '.join('%s %s $%+.2f' % (r[0]['ticker'], r[0]['date'], r[1])
                              for r in top3),
                    sum(r[1] for r in top3), tot - top3[0][1]))
        if name == 'E':
            n_re = sum(1 for r in rows if r[3] == 'bars+reentry')
            L.append('  re-entries taken: %d' % n_re)
        L.append('  ENV-MAPPABILITY: %s' % ENV_MAP[name])
        L.append('')
        print('variant %s done: $%.2f' % (name, tot), flush=True)

    # ---- named traces: FGI 8/13 (entry ~10.77) and HUIZ 8/7 ----
    L.append('================ NAMED TRACES (per-variant verdicts) ================')

    def pick(ticker, date, epx=None):
        cands = [i for i, p in enumerate(prep)
                 if p['t']['ticker'] == ticker and p['t']['date'] == date]
        if epx is not None:
            ex = [i for i in cands if abs(prep[i]['t']['entry'] - epx) < 0.02]
            if ex:
                return ex[0]
        if cands:
            return max(cands, key=lambda i: abs(prep[i]['t']['pnl']))
        return None

    for tick, dt, epx in (('FGI', '2026-08-13', 10.77), ('HUIZ', '2026-08-07', None)):
        i = pick(tick, dt, epx)
        if i is None:
            L.append('%s %s: NOT IN COHORT' % (tick, dt))
            continue
        t = prep[i]['t']
        L.append('%s %s | entry $%.4f x %d sh | stop %.4f | highest %.4f | '
                 'real exit %.4f | raw pnl $%+.2f (%s)'
                 % (t['ticker'], t['date'], t['entry'], t['shares'],
                    t['stop_loss'], t['highest'], t['exit'], t['pnl'],
                    t.get('exit_reason')))
        for name, _ in VARIANTS:
            _, pnl, fills, note = all_rows[name][i]
            L.append('  %-4s $%+9.2f  [%s]' % (name, pnl, note))
            for lb, q, px in fills:
                if q == 0.0 and lb.startswith('REENTRY'):
                    L.append('        %s' % lb)
                else:
                    L.append('        %-40s %8.2f sh @ $%.4f -> $%+.2f'
                             % (lb, q, px, q * (px - t['entry'])))
        L.append('')

    L.append('READING F: if F is NEGATIVE the entries are dead and no exit fixes')
    L.append('them; if F is strongly POSITIVE the signal lives and the exit is the')
    L.append('killer.  G is the minimal realistic harvest of F.  F itself is a')
    L.append('DIAGNOSTIC CONTROL and is never shippable.')
    L.append('NO recommendation — the full room verifies, Marcos decides before 03:55.')
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
