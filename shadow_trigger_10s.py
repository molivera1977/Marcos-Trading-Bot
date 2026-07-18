#!/usr/bin/env python3
"""
10-SECOND INTRADAY TRIGGER — SHADOW LOGGER (built 7/18, for Fable audit). NEVER TRADES.

WHY THIS EXISTS
  Tonight's finding (project_chart_gate memory): the chart-read design has two halves —
  (1) SELECTION: the daily read marks a break level per name (validated: 30/31 winners across
      3 blind samples incl. an out-of-sample week); knives/do-not-trade get no level = vetoed.
  (2) TRIGGER: the actual entry is a break-AND-HOLD-on-VOLUME of the *intraday* base that forms
      after a validated name reclaims its daily level. This is visible ONLY on the 10-second tape
      (GLXG runner held+broke on expanding volume; VEEE/AP/CTNT faders spiked/gapped and volume
      died). The daily close-proxy CANNOT separate a gap-over-run (FXHO +50%) from a gap-over-fade
      (AP/CTNT) — only the 10s hold-on-volume can.

  The trigger THRESHOLDS are UNTUNED — they were eyeballed from ONE day (7/17), 3 names. Tuning
  them on that = overfitting. So this logger's job is to RUN FORWARD in shadow, on daily-validated
  names, and LOG every trigger + its real forward MFE/MAE, accumulating the 10s dataset needed to
  tune the thresholds on a real sample (dozens of days, hundreds of triggers). It changes NOTHING
  about live trading — it only writes a JSONL.

ARCHITECTURE
  armed names   = names with a valid daily level today (kev_watchlist _levels; NOT do-not-trade).
                  → this is the SELECTION veto; the fader VEEE is excluded HERE, upstream, not by
                    any intraday climax rule (which would overfit).
  trigger       = on an armed name, watch the recorder's live 10s bars for: a TIGHT BASE forms →
                  price BREAKS the base high → on VOLUME EXPANSION (vs base avg) → and HOLDS above
                  the break for HOLD bars. Log it. (First clean setups are the ones we care about;
                  we log all + a `seq` index so tuning can restrict to first-N / prime-window.)
  forward track = after a trigger, keep updating MFE/MAE from subsequent 10s bars so each logged
                  trigger carries its real outcome for later grading.

SHADOW-SAFE: reads bars + writes JSONL only. No order path, no bot state, no dashboard writes
  except an optional decision-log breadcrumb. Import side effects: none.

RUN:  python3 shadow_trigger_10s.py            # loop through the session
      python3 shadow_trigger_10s.py --once     # one pass (cron / test)
ENV:  SCREENER_URL, DASHBOARD_SECRET; TRIG_* threshold overrides (see below).
"""
import os, sys, json, time, datetime as dt
import urllib.request
from zoneinfo import ZoneInfo

ET  = ZoneInfo("America/New_York")
U   = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")
DAY = os.environ.get("TRIG_DAY") or dt.datetime.now(ET).strftime("%Y-%m-%d")
LOG = os.path.expanduser(f"~/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/shadow_triggers_{DAY}.jsonl")

# ── THRESHOLDS — UNTUNED (eyeballed from 7/17 GLXG/CJMB; DO NOT trust the values, that's the point) ──
BASE_BARS = int(os.environ.get("TRIG_BASE_BARS", "12"))     # 10s bars in the consolidation window (~2min)
TIGHT     = float(os.environ.get("TRIG_TIGHT", "0.05"))     # base range/mid must be <= this (tight coil)
VOLX      = float(os.environ.get("TRIG_VOLX", "3.0"))       # break bar volume >= VOLX * base avg volume
HOLD      = int(os.environ.get("TRIG_HOLD", "6"))           # bars price must stay above the break (~1min)
COOL      = int(os.environ.get("TRIG_COOL", "30"))          # bars cooldown between triggers on one name
POLL_SECS = int(os.environ.get("TRIG_POLL_SECS", "60"))
STOP_HHMM = os.environ.get("TRIG_STOP_HHMM", "16:00")

def _get(url, timeout=30):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())

def _et(p):
    return dt.datetime.strptime(str(p["time"])[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone(ET)

# ── SELECTION veto: armed names = valid daily level today, NOT do-not-trade ──────────────────
def armed_levels():
    try:
        lv = _get(f"{U}/api/kev_watchlist?date={DAY}").get("levels") or {}
    except Exception as e:
        print(f"[arm] kev_watchlist fetch failed: {e}", flush=True); return {}
    out = {}
    for tk, d in lv.items():
        if not isinstance(d, dict): continue
        note = str(d.get("note") or "").lower()
        if d.get("veto") or "do-not-trade" in note or "do not trade" in note:
            continue                                        # SELECTION veto — never watched intraday
        brk = d.get("break")
        try: brk = float(brk)
        except (TypeError, ValueError): continue
        if brk > 0:
            out[tk.upper()] = brk
    return out

def get_10s(ticker):
    try:
        r = _get(f"{U}/api/bars?date={DAY}&ticker={ticker}~10S")
        pts = [p for p in (r.get("bars") or []) if f"{_et(p):%Y-%m-%d}" == DAY]
        pts = [p for p in pts if "09:30" <= f"{_et(p):%H:%M}" <= "16:00"]
        pts.sort(key=_et)
        return [{"t": _et(p), "o": float(p["open"]), "h": float(p["high"]), "l": float(p["low"]),
                 "c": float(p["close"]), "v": float(p.get("volume") or 0)} for p in pts]
    except Exception:
        return []

# ── TRIGGER: intraday base → break → volume expansion → HOLD. Returns list of trigger dicts. ──
def detect(bars, daily_level):
    trig = []; last = -999
    for i in range(BASE_BARS, len(bars) - HOLD - 1):
        if i - last < COOL: continue
        base = bars[i - BASE_BARS:i]
        bh = max(b["h"] for b in base); bl = min(b["l"] for b in base); bmid = (bh + bl) / 2
        if bmid <= 0: continue
        rng = (bh - bl) / bmid
        bvol = sum(b["v"] for b in base) / len(base)
        cur = bars[i]
        if not (rng <= TIGHT and cur["c"] > bh and cur["v"] > VOLX * max(bvol, 1)):
            continue
        hold = bars[i + 1:i + 1 + HOLD]
        if not all(x["l"] >= bh * 0.985 for x in hold):     # break must HOLD (not tag-and-fade)
            continue
        last = i + HOLD
        seg = bars[i + 1:i + 121]                           # forward ~20min for MFE/MAE
        e = cur["c"]
        mfe = (max(s["h"] for s in seg) - e) / e * 100 if seg else None
        mae = (min(s["l"] for s in seg) - e) / e * 100 if seg else None
        trig.append({
            "seq": len(trig),                               # 0 = first clean setup of the day for this name
            "time": f"{cur['t']:%H:%M:%S}", "entry": round(e, 4),
            "daily_level": daily_level, "gap_over_daily": e >= daily_level and base[0]["o"] >= daily_level,
            "base_high": round(bh, 4), "base_range_pct": round(rng * 100, 2),
            "break_vol": round(cur["v"]), "base_avg_vol": round(bvol), "vol_mult": round(cur["v"] / max(bvol, 1), 1),
            "fwd_mfe_pct": None if mfe is None else round(mfe), "fwd_mae_pct": None if mae is None else round(mae),
            "prime_window": "09:30" <= f"{cur['t']:%H:%M}" <= "11:30",
        })
    return trig

def load_logged():
    seen = set()
    try:
        with open(LOG) as f:
            for line in f:
                try:
                    r = json.loads(line); seen.add((r["ticker"], r["time"]))
                except Exception: pass
    except FileNotFoundError: pass
    return seen

def process_once():
    armed = armed_levels()
    seen = load_logged()
    now = dt.datetime.now(ET)
    fired = 0
    for tk, lvl in armed.items():
        bars = get_10s(tk)
        if len(bars) < BASE_BARS + HOLD + 2: continue
        for t in detect(bars, lvl):
            k = (tk, t["time"])
            if k in seen: continue
            rec = {"ticker": tk, "day": DAY, "logged_at": f"{now:%H:%M:%S}", **t, "shadow": True}
            with open(LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
            seen.add(k); fired += 1
            print(f"[{now:%H:%M:%S}] SHADOW TRIGGER {tk} seq{t['seq']} @ {t['entry']} "
                  f"(base {t['base_range_pct']}% volx{t['vol_mult']} {'GAP-OVER' if t['gap_over_daily'] else 'clean'}) "
                  f"→ fwd MFE {t['fwd_mfe_pct']}% MAE {t['fwd_mae_pct']}%", flush=True)
    print(f"[{now:%H:%M:%S}] armed={len(armed)} new_triggers={fired} log={LOG.split('/')[-1]}", flush=True)
    return fired

def main():
    once = "--once" in sys.argv
    print(f"[shadow-10s] day={DAY} thresholds: base={BASE_BARS} tight={TIGHT} volx={VOLX} hold={HOLD} "
          f"(UNTUNED — accumulating data) | SHADOW ONLY, never trades", flush=True)
    if once:
        process_once(); return
    while True:
        if dt.datetime.now(ET).strftime("%H:%M") >= STOP_HHMM:
            print("[shadow-10s] session end — done.", flush=True); break
        try: process_once()
        except Exception as e: print(f"[loop] {e}", flush=True)
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
