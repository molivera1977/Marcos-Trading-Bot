"""BOTTLENECK REPLAY (Fable, 7/24 ~1am, Marcos: "replay the day with all of our entries and
exits per our system — I want to see how badly our bottlenecks affected us").

QUESTION: what would the CURL LANES (reclaim + zone-flip) have produced on 7/23 if they had been
fed the full Alpaca tape instead of the starved Webull shadow store (live fire count: ZERO)?

══ FIDELITY LEDGER (Wind Tunnel law 1 — read before trusting any number) ═══════════════════════
MODELED
  • Detection: the bot's OWN kev_reclaim_step / kev_zoneflip_step, IMPORTED (byte-identical
    logic, loaded via rig/loader). bot._curl_feed is monkeypatched to serve replay bars, so the
    zone-flip's _zf_pm_floor computes its 9:00–9:29 zone from the same feed.
  • Feed: full-day dashboard archive ~ALP10S 10s bars + ~ALPVWAP tick-VWAP (step-function
    aligned: bar k uses the latest vwap point <= k). This is what post-migration live sees.
  • Machines STEP from 04:00 (premarket warm-up, tonight's deployed behavior); ENTRIES allowed
    only 09:30–15:30 (ENTRY_OPEN_ET..entry cutoff); force-flat 15:45 (live doctrine).
  • Live-eligibility: reclaim seq==0 only (the day's first fire per name — live consumes one
    slot); first zone-flip fire per name. ONE POSITION AT A TIME across all names, chronological
    (the live bot's single-position constraint).
  • Entry fill: NEXT 10s bar's OPEN after the fire bar (never same-bar).
  • Exits = live kev25 doctrine (bot :392-397, :5630-5646): 50% @ +1R, 25% @ +2R; stop stays at
    STRUCTURE until scale #2, then break-even; 25% runner trails PREV-1-MIN-BAR LOW (folded from
    10s, close-based cross like live); hard stop; 15:45 force-flat.
  • Conservative same-bar rule: if one bar spans both the stop and a tier, the STOP fills first.
  • Halts: a >=90s gap between consecutive 10s buckets = halt window. No entries off a fire whose
    fill bar is the halt-resume bar; a stop pending through a halt fills at the first post-halt
    bar OPEN (the NVVE 7/23 lesson — stops gap, they don't fill at the stop price).
  • Sizing: live risk frame — shares = min($30 / (entry-stop), $1000 / entry), whole shares.
APPROXIMATED
  • Trail granularity: prev-bar-low checked on folded 1-min bars at 10s resolution (live checks
    completed 1-min bars via REST; close-based cross both).
  • Curl gates: day-gain floor + chart-gate NOT applied — both EXEMPT curl entries (verified:
    DAYGAIN legacy-scoped ed73f8d; _chart_break_gate docstring "curl-entry machines are EXEMPT").
OMITTED (each named, with its bias)
  • HEALTH TRAIL (VWAP+EMA fold) — cuts runners on health loss. Omission biases runner P&L
    OPTIMISTIC on names that lost health mid-run. Counter-bias: prev-bar-low trail still active.
  • Velocity-aware ride-through of tiers (would HOLD through tiers on acceleration → omission is
    CONSERVATIVE on monsters).
  • Slippage beyond next-bar-open; halt re-entry; capital/GFV ledger; every non-curl lane
    (flat-top/ORB/ignition/rocket ran LIVE on REST 1-min — they were not the starved bottleneck).
RECONCILIATION (law 2): live curl fires on 7/23 = 0 (the defect being measured). The 3 live
trades (ADVB +29.37 / PN −30.75 / NVVE −54.40 = −55.78) came from OTHER lanes and are context,
not reproduction targets. The sim-vs-live delta on the curl lanes IS the finding.
═══════════════════════════════════════════════════════════════════════════════════════════════
Usage: python3 bottleneck_replay.py [YYYY-MM-DD]   (default 2026-07-23)
Read-only vs the dashboard. Writes data/killtests/bottleneck_replay_<date>_results.txt
"""
import sys, json, pathlib, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "rig"))
from loader import load_bot
bot = load_bot()

B    = "https://zestful-intuition-production-b16a.up.railway.app"
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-23"
OUT  = pathlib.Path(__file__).resolve().parent / "data" / "killtests" / f"bottleneck_replay_{DATE.replace('-','')}_results.txt"
_log_lines = []
def log(s=""):
    print(s, flush=True); _log_lines.append(s)

def get(url):
    with urllib.request.urlopen(url, timeout=45) as r:
        return json.load(r)

def epoch(ts):   # "2026-07-23T13:30:00.000+0000" -> utc epoch
    return int(datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())

def et_hm(k):    # epoch -> "HH:MM" ET (EDT = UTC-4; DATE is a July date)
    h = (k // 3600) % 24; m = (k // 60) % 60
    h = (h - 4) % 24
    return f"{h:02d}:{m:02d}"

# ── 1. roster: 7/23 watching ∪ that day's gappers ────────────────────────────
watch = [t.upper() for t in (get(f"{B}/api/watching?date={DATE}").get("tickers") or [])]
dg    = (get(f"{B}/api/day2").get("daily_gappers") or {}).get(DATE) or []
names = list(dict.fromkeys(watch + [str(g.get("symbol")).upper() for g in dg if g.get("symbol")]))
log(f"roster: {len(names)} names (watching {len(watch)} ∪ gappers {len(dg)})")

# ── 2. fetch bars + vwap; build replay structures ────────────────────────────
DATA = {}   # sym -> {"bars":[(k,o,h,l,c,v)...] sorted, "vwap":[(ts,vw)...] sorted, "halt":set(resume_k)}
for t in names:
    try:
        bs = get(f"{B}/api/bars?ticker={t}~ALP10S&date={DATE}").get("bars") or []
        if len(bs) < 30: continue
        bars = sorted((epoch(b["time"]), float(b["open"]), float(b["high"]), float(b["low"]),
                       float(b["close"]), float(b["volume"])) for b in bs)
        vs = get(f"{B}/api/bars?ticker={t}~ALPVWAP&date={DATE}").get("bars") or []
        vwap = sorted((epoch(b["time"]), float(b["close"])) for b in vs)
        halt = set()
        for i in range(1, len(bars)):
            if bars[i][0] - bars[i-1][0] >= 90:          # >=90s bucket gap = halt/dead-tape window
                halt.add(bars[i][0])                     # the RESUME bar
        DATA[t] = {"bars": bars, "vwap": vwap, "halt": halt}
    except Exception as e:
        log(f"  fetch {t} failed: {e}")
log(f"data: {len(DATA)} names with >=30 bars")

# ── 3. monkeypatch the bot's feed so its OWN machines run on replay bars ─────
_replay_now = [0]     # virtual clock: the epoch of the bar being stepped
def _replay_curl_feed(t, n=90):
    d = DATA.get(t)
    if not d: return {}, "replay-none"
    cut = _replay_now[0] // 10 * 10
    out = {}
    for k, o, h, l, c, v in d["bars"]:
        if k + 10 <= cut:                                 # CLOSED buckets only, no lookahead
            out[k] = {"o": o, "h": h, "l": l, "c": c, "v0": 0, "v1": v}
    ks = sorted(out)[-n:]
    return {k: out[k] for k in ks}, "replay"
bot._curl_feed = _replay_curl_feed

def vwap_at(t, k):
    best = 0.0
    for ts, vw in DATA[t]["vwap"]:
        if ts <= k: best = vw
        else: break
    return best

# ── 4. detection sweep: step the bot's machines bar-by-bar (premarket warm-up) ─
H930, H1530, H1545 = 13*3600+30*60, 19*3600+30*60, 19*3600+45*60   # UTC secs-of-day (EDT)
def sod(k): return k % 86400

fires = []   # (fire_k, sym, lane, stop)
for t in sorted(DATA):
    d = DATA[t]
    rec_cur = 0
    for i, (k, o, h, l, c, v) in enumerate(d["bars"]):
        _replay_now[0] = k + 10                            # bar k just CLOSED
        # reclaim: feed THIS closed bar (incremental, mirrors live stepping)
        sv = vwap_at(t, k)
        if sv and sv > 0:
            fr = bot.kev_reclaim_step(t, [(o, h, l, c, v)], sv)
            if fr and fr.get("seq") == 0:
                fires.append((k, t, "reclaim", float(fr.get("stop") or 0)))
        # zone-flip: same incremental bar; machine computes its own zone via patched feed
        try:
            zf = bot.kev_zoneflip_step(t, [(k, o, h, l, c, v)])
        except Exception:
            zf = None
        if zf:
            stop = float(zf.get("stop") or zf.get("zone_stop") or 0)
            if not any(f[1] == t and f[2] == "zoneflip" for f in fires):
                fires.append((k, t, "zoneflip", stop))
fires.sort()
log(f"\nDETECTION: {len(fires)} live-eligible curl fires (reclaim seq-0 + first zone-flip per name)")
from collections import Counter
log("fires by hour (ET): " + str(sorted(Counter(et_hm(f[0])[:2] for f in fires).items())))
log("fires by lane:      " + str(Counter(f[2] for f in fires)))

# ── 5. trade sim: one position at a time, kev25 exits, conservative fills ────
def fold_1min(bars_upto):
    """fold 10s bars -> completed 1-min bars [(minute_k, low, close)] for the prev-bar-low trail."""
    mins = {}
    for k, o, h, l, c, v in bars_upto:
        mk = k // 60 * 60
        if mk not in mins: mins[mk] = [l, c]
        else:
            mins[mk][0] = min(mins[mk][0], l); mins[mk][1] = c
    return mins

trades = []
busy_until = 0
for fk, t, lane, stop in fires:
    if fk < busy_until: continue                          # single-position constraint
    if not (H930 <= sod(fk) < H1530): continue            # entries RTH-only (premarket = shadow)
    d = DATA[t]; bars = d["bars"]
    idx = next((i for i, b in enumerate(bars) if b[0] > fk), None)
    if idx is None: continue
    ek, eo, eh, el, ec, ev = bars[idx]
    if ek in d["halt"]: continue                          # fill bar = halt-resume → no chase entry
    entry = eo
    if not stop or stop >= entry:
        stop = round(entry * 0.93, 4)                     # machine gave no stop → curl fallback 7% (live floor class)
    R = entry - stop
    shares = min(int(30 / R) if R > 0 else 0, int(1000 / entry) if entry > 0 else 0)
    if shares < 1: continue
    t1, t2 = entry + R, entry + 2 * R                     # kev25: 50% @ +1R, 25% @ +2R, 25% runner
    rem, pnl, scale = 1.0, 0.0, 0
    cur_stop = stop
    exit_px = exit_reason = None
    for j in range(idx + 1, len(bars)):
        k, o, h, l, c, v = bars[j]
        if sod(k) >= H1545:                               # 3:45 force-flat
            exit_px, exit_reason = o, "3:45 force-flat"; break
        if k in d["halt"] and l <= cur_stop:              # resumed through a pending stop → gap fill at open
            exit_px, exit_reason = o, "stop (halt gap)"; break
        if l <= cur_stop:                                 # stop first on any spanning bar (conservative)
            exit_px, exit_reason = min(cur_stop, o), "stop"; break
        if scale == 0 and h >= t1:
            pnl += (t1 - entry) * shares * 0.50; rem = 0.50; scale = 1
        if scale == 1 and h >= t2:
            pnl += (t2 - entry) * shares * 0.25; rem = 0.25; scale = 2
            cur_stop = max(cur_stop, entry)               # BE floor after scale #2 (BE_FLOOR_AFTER_SCALE=2)
        if scale >= 1:                                    # runner trail: prev COMPLETED 1-min bar low, close cross
            mins = fold_1min(bars[max(0, j-30):j])
            done = sorted(mk for mk in mins if mk + 60 <= k)
            if len(done) >= 2:
                pbl = mins[done[-1]][0]
                if c < pbl:
                    exit_px, exit_reason = c, "prev-bar-low trail"; break
    if exit_px is None:
        exit_px, exit_reason = bars[-1][4], "eod"
    pnl += (exit_px - entry) * shares * rem
    busy_until = k if exit_px is not None else fk
    trades.append({"sym": t, "lane": lane, "t": et_hm(fk), "entry": round(entry, 4),
                   "stop": round(stop, 4), "sh": shares, "exit": round(exit_px, 4),
                   "why": exit_reason, "pnl": round(pnl, 2)})

log(f"\nSIM TRADES (one-at-a-time, RTH entries, kev25 exits): {len(trades)}")
log(f"{'time':>5} {'sym':<6}{'lane':<9}{'entry':>8}{'stop':>8}{'sh':>4}{'exit':>8}  {'exit_why':<18}{'pnl':>9}")
for tr in trades:
    log(f"{tr['t']:>5} {tr['sym']:<6}{tr['lane']:<9}{tr['entry']:>8}{tr['stop']:>8}{tr['sh']:>4}{tr['exit']:>8}  {tr['why']:<18}{tr['pnl']:>9.2f}")
tot = sum(tr["pnl"] for tr in trades)
w = sum(1 for tr in trades if tr["pnl"] > 0)
log(f"\n══ VERDICT ══")
log(f"curl-lane sim P&L (7/23, full Alpaca tape): {tot:+.2f}  ({w}W/{len(trades)-w}L of {len(trades)})")
log(f"live curl-lane P&L that day:                +0.00  (ZERO fires — the starved bottleneck)")
log(f"live day actual (other lanes):              -55.78  (ADVB +29.37 / PN -30.75 / NVVE -54.40)")
log(f"NOTE: sim number carries the fidelity ledger above — health-trail omitted (runner-optimistic),")
log(f"velocity-ride omitted (monster-conservative). Treat as ORDER OF MAGNITUDE, not gospel.")

OUT.write_text("\n".join(_log_lines) + "\n")
log(f"\nsaved -> {OUT}")
