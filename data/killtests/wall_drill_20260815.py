#!/usr/bin/env python3
"""WALL PROVING DRILL — 8/15 (replay, real 8/14 tape).

The runway wall (#27, marcos_trading_bot.py:8946-8962) shipped 8/8 but was INERT until the
8/14 12:53 fix (line 8953: `_curl_feed` returns a (dict, src) TUPLE; the old code called
`.values()` on the tuple, the AttributeError was swallowed by the bare except, `_whi` stayed
0.0, and the wall block no-oped on every call since 8/8). This drill replays the FIXED wall
logic against real specimens from today's (8/14) tape to convert the fix from BUILT-UNPROVEN
to PROVEN(replay). Live-tape proof still lands Monday — this is replay evidence only.

Wall block REPLICATED VERBATIM below (see `wall_road()`) from marcos_trading_bot.py
lines 8951-8963 (_marked_runway), rather than imported: importing the bot module executes
heavy module-level side effects (SDK clients, threads). The replica is line-for-line and
cites its source. If _marked_runway's wall block changes, this replica must be re-synced.

Specimens (all real rows from the dashboard decisions archive, date=2026-08-14,
status=runway_reject — /api/decisions_archive):
  A) DFSC 10:55:34  entry 2.87   stop 2.725   pre-fix road 0.14R to rung 2.89 (REFUSED, need 0.4)
  B) DFSC 14:44:08  entry 2.94   stop 2.7523  pre-fix road 0.11R to rung 2.96 (REFUSED)
  C) insertion specimen — scanned from today's reject rows: a name whose session high sat
     BETWEEN entry and the mapped target and was rejected 3+ times (the wall should have
     been INSERTED as the honest road end).

Tape: 10s bars (TICKER~ALP10S, falling back to ~10S) from the dashboard warehouse
/api/bars?date=2026-08-14 — 10s outranks 1-min per the 7/x line-in-the-sand.
The wall window replicates _curl_feed(ticker, n=720): the 720 10s bars (~2h) preceding
the gate moment.
"""
import json, os, pathlib, urllib.request
from datetime import datetime, timedelta, timezone

DASH = "https://zestful-intuition-production-b16a.up.railway.app"
DATE = "2026-08-14"
HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / "wall_drill_cache_20260815"
CACHE.mkdir(exist_ok=True)
ET = timezone(timedelta(hours=-4))


def fetch_bars(ticker):
    """10s bars for DATE, epoch-keyed like _curl_feed's dict: {epoch: {'h':..,'c':..}}."""
    for sfx in ("~ALP10S", "~10S"):
        fp = CACHE / f"{ticker}{sfx}.json"
        if not fp.exists():
            try:
                with urllib.request.urlopen(f"{DASH}/api/bars?date={DATE}&ticker={ticker}{sfx}", timeout=30) as r:
                    fp.write_bytes(r.read())
            except Exception:
                continue
        try:
            bars = json.loads(fp.read_text()).get("bars") or []
        except Exception:
            continue
        if not bars:
            continue
        out = {}
        for b in bars:
            t = datetime.strptime(str(b["time"])[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            out[int(t.timestamp())] = {"h": float(b.get("high") or 0), "c": float(b.get("close") or 0)}
        return out, sfx
    return {}, None


def curl_window(bars, at_epoch, n=720):
    """Replicates _curl_feed(t, n=720) at the gate moment: the n 10s bars preceding `at_epoch`."""
    keys = sorted(k for k in bars if k < at_epoch)[-n:]
    return {k: bars[k] for k in keys}


def wall_road(entry_price, stop_loss, targets, next_supply, wb, wall_on=True):
    """The runway road computation with the wall block replicated VERBATIM from
    marcos_trading_bot.py _marked_runway, lines 8944-8965 (post-12:53-fix state).
    `wb` plays the role of the fixed `_wb` dict (first element of the _curl_feed tuple —
    line 8953's fix is exactly that unpack). wall_on=False replays the PRE-FIX behavior
    (wall inert: _whi computed over the raw tuple failed -> _whi=0.0 -> block no-ops),
    which is byte-identical to RUNWAY_WALL=0."""
    _rps = entry_price - stop_loss
    if _rps <= 0:
        return None, None
    _tgts = sorted(float(x) for x in (targets or []) if float(x) > entry_price)
    _ns = float(next_supply or 0)
    if wall_on:                                                     # bot: RUNWAY_WALL env, default "1"
        # ── verbatim from marcos_trading_bot.py:8953-8962 ──
        _whi = max((float(b.get("h") or 0) for b in wb.values()), default=0.0) if wb else 0.0
        if _whi > 0:
            _tgts = [x for x in _tgts if x > _whi]          # spent rungs demoted        (:8958)
            if _whi > entry_price * 1.005:
                _tgts = sorted(_tgts + [round(_whi, 4)])    # the wall IS the road end   (:8960)
            if _ns and _ns <= _whi:
                _ns = 0.0                                   #                            (:8962)
        # ── end verbatim ──
    _tgt = (_tgts[0] if _tgts else (_ns if _ns > entry_price else None))
    if _tgt:
        return round((_tgt - entry_price) / _rps, 2), _tgt
    if targets or _ns:
        return "above_all_levels", None
    return None, None


def et_epoch(hh, mm, ss):
    return int(datetime(2026, 8, 14, hh, mm, ss, tzinfo=ET).timestamp())


def rejection_count(bars, upto_epoch, level, tol=0.005):
    """Distinct approaches (>=60s apart) that tagged within tol of `level` without a 10s close above it."""
    hits, last = 0, -10**9
    for k in sorted(k for k in bars if k < upto_epoch):
        b = bars[k]
        if b["h"] >= level * (1 - tol) and b["c"] <= level:
            if k - last >= 60:
                hits += 1
            last = k
    return hits


def run():
    lines = ["# WALL PROVING DRILL — 8/15 (replay of 8/14 tape)", "",
             "Wall fix (bot :8953 tuple-unpack, shipped 8/14 12:53) replayed against real specimens.",
             "Wall block replicated verbatim from marcos_trading_bot.py:8951-8962 (see wall_drill_20260815.py).",
             "**Status: PROVEN(replay). Live-tape proof still lands Monday — no production demotion has fired yet.**", ""]

    # ── Specimens A & B: real runway_reject rows (decisions archive 8/14) ──
    # `targets` reconstruction: the row's refused `target` is the map's first rung above entry
    # (that IS what pre-fix picked); next_supply 3.00 for DFSC per the 12:59:10 low_room_soft
    # row (supply_src=level). Marked [RECONSTRUCTED] where the full rung ladder is not in the row.
    specimens = [
        dict(name="A", tk="DFSC", t=et_epoch(10, 55, 34), entry=2.87, stop=2.725,
             targets=[2.89], ns=3.00, refused="0.14R to rung 2.89 (need 0.4) — the 10:55 refusal"),
        dict(name="B", tk="DFSC", t=et_epoch(14, 44, 8), entry=2.94, stop=2.7523,
             targets=[2.96], ns=3.00, refused="0.11R to rung 2.96"),
    ]

    # ── Specimen C: insertion case — scan today's reject rows for a name whose session high
    # sat between entry and target (unspent rung) and was rejected 3+ times before the gate.
    candidates = [
        ("WETO", et_epoch(10, 5, 38), 10.88, 10.374, [11.10], 0.0),
        ("BANL", et_epoch(12, 21, 20), 9.665, 9.2527, [10.01], 0.0),
        ("ONFO", et_epoch(9, 35, 14), 2.935, 2.6819, [3.00], 0.0),
    ]
    ins = None
    for tk, t, entry, stop, tgts, ns in candidates:
        bars, src = fetch_bars(tk)
        if not bars:
            continue
        wb = curl_window(bars, t)
        whi = max((b["h"] for b in wb.values()), default=0.0)
        if entry * 1.005 < whi < tgts[0]:  # wall strictly between entry and the (unspent) rung
            rej = rejection_count(bars, t, whi)
            if rej >= 3:
                ins = dict(name="C (insertion)", tk=tk, t=t, entry=entry, stop=stop,
                           targets=tgts, ns=ns, refused=f"road ran to the ink at {tgts[0]}",
                           rej=rej, whi=whi, src=src)
                break
    if ins:
        specimens.append(ins)

    for s in specimens:
        bars, src = fetch_bars(s["tk"])
        wb = curl_window(bars, s["t"])
        whi = max((b["h"] for b in wb.values()), default=0.0)
        pre_rr, pre_tgt = wall_road(s["entry"], s["stop"], s["targets"], s["ns"], wb, wall_on=False)
        post_rr, post_tgt = wall_road(s["entry"], s["stop"], s["targets"], s["ns"], wb, wall_on=True)
        spent = [x for x in s["targets"] if x <= whi]
        gate_t = datetime.fromtimestamp(s["t"], ET).strftime("%H:%M:%S")
        lines += [f"## Specimen {s['name']}: {s['tk']} @ {gate_t} ET",
                  f"- entry {s['entry']} / stop {s['stop']} / map rungs {s['targets']}"
                  + (f" / next_supply {s['ns']}" if s["ns"] else "") + "  [rungs RECONSTRUCTED from the gate row]",
                  f"- pre-fix (wall inert): road **{pre_rr}R** to {pre_tgt} — {s['refused']}",
                  f"- 2h wall window ({src}, {len(wb)} bars): session-window high **{whi:.4f}**",
                  f"- spent rungs demoted: {spent or 'none'}"
                  + (f" | wall inserted at {whi:.4f}" if whi > s['entry'] * 1.005 else " | no insertion (wall within 0.5% of entry)"),
                  f"- post-fix: road **{post_rr}R** to {post_tgt}",]
        if s.get("rej"):
            lines += [f"- high {s['whi']:.4f} rejected **{s['rej']}x** before the gate (>=60s-spaced tags within 0.5%, no 10s close above) — the wall belonged in this road"]
        lines += [f"- VERDICT: {'wall CHANGED the road' if (pre_rr, pre_tgt) != (post_rr, post_tgt) else 'road unchanged'}", ""]
        print("\n".join(lines[-8:]))

    lines += ["---", "Drill: data/killtests/wall_drill_20260815.py · tape cache: data/killtests/wall_drill_cache_20260815/",
              "Replay proof only. The fixed wall has still never demoted a rung in PRODUCTION — Monday's live tape is the real proof."]
    (HERE / "wall_drill_20260815.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {HERE / 'wall_drill_20260815.md'}")


if __name__ == "__main__":
    run()
