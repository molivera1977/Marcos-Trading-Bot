#!/usr/bin/env python3
"""
Autonomous NEWCOMER CHART-READ pipeline (VISION) — Marcos's spec, 7/17:
  "As soon as newcomers are added to the scanner, that needs to trigger a chart read, then
   those notes need to be added to the instructions automatically. No read, no trade."

The loop:
  1. TRIGGER  — poll the bot's decision archive; detect a NEW active scanner newcomer.
  2. RENDER   — draw its DAILY chart (TIGHT recent ~6 days; yesterday high + overhead supply marked).
  3. READ     — Claude VISION reads the image like Kev (setup / meaningful break level / verdict).
  4. WRITE    — POST the read's level to /api/kev_watchlist (MERGED, not overwriting the sheet),
                so it lands in the same `_levels` store the bot's _chart_break_gate already reads.
  5. ENFORCE  — handled by the bot: _chart_break_gate = No-Break/No-Read, No-Trade (already built).

Extends the bot's EXISTING Anthropic integration (same key/SDK as evening_scan.py). Cost ~$9/mo on
Sonnet at ~55 reads/day (see LAYER2_AUDIT_NOTE.md). Model is env-configurable.

Run modes:
  python3 newcomer_vision_reader.py --once      # read all current unread active newcomers, exit
  python3 newcomer_vision_reader.py             # loop until STOP_HHMM (default 15:30 ET)

Requires env: ANTHROPIC_API_KEY (already on the bot's Railway env), SCREENER_URL, DASHBOARD_SECRET.
SHADOW-SAFE: this only WRITES chart-read levels; it never places a trade. The bot's gate stays in
shadow (CHART_GATE_ENFORCE unset) until validated — so even a bad read cannot cause a trade yet.
"""
import os, re, sys, io, json, time, base64, datetime as dt
import urllib.request
from zoneinfo import ZoneInfo

ET   = ZoneInfo("America/New_York")
U    = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")
SECRET = os.environ.get("DASHBOARD_SECRET", "marcos2026")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL   = os.environ.get("NEWCOMER_VISION_MODEL", "claude-sonnet-4-6")   # Sonnet: chart-read sweet spot
POLL_SECS = int(os.environ.get("NEWCOMER_POLL_SECS", "90"))
STOP_HHMM = os.environ.get("NEWCOMER_STOP_HHMM", "15:30")
DAY = os.environ.get("NEWCOMER_DAY") or dt.datetime.now(ET).strftime("%Y-%m-%d")

# Names that ALREADY have a level today (night sheet OR an earlier vision read) are excluded
# DYNAMICALLY in active_newcomers() — never re-read, never overwrite the human-marked sheet.
# (Was a hardcoded 7/17 sheet list — stale by the very next session; Fable audit 7/18.)
MAX_ATTEMPTS = int(os.environ.get("NEWCOMER_MAX_ATTEMPTS", "3"))    # per-name BILLED vision calls (cost guard)
MAX_RENDER_FAILS = int(os.environ.get("NEWCOMER_MAX_RENDER_FAILS", "10"))  # per-name chart-fetch fails —
#   /api/daily hits Webull LIVE (429-able); a failed render is free + retryable, so it gets its OWN,
#   looser cap (10 × 90s loop ≈ rides out a 15-min 429 storm) and must NEVER burn a billed attempt
SPACING      = float(os.environ.get("NEWCOMER_READ_SPACING", "2"))  # secs between reads (quota-kind)
_attempts = {}                                                      # per-name BILLED attempts (process = one day)
_rfail    = {}                                                      # per-name render failures
# only names the bot ACTUALLY considers (reached these) get the (billable) read — not raw flickers.
# "watching" = the bot's morning scanner batch (posted ~8:50-9:00) → read BEFORE the open (7/18).
ACTIVE_STATUSES = {"break_armed","consolidating","orb_break_armed","triggered_flat_top",
                   "triggered_ignition","filled","ignition_low_room_soft","low_room_soft",
                   "reentry_eligible","watching"}

def _get(url, timeout=45):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())

def _post(path, body, timeout=30):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Dashboard-Secret": SECRET},
                                 method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def _ampm(s):
    try:
        p=s.strip().split(); hh,mm,ss=p[0].split(":"); hh=int(hh)
        if p[1]=="PM" and hh!=12: hh+=12
        if p[1]=="AM" and hh==12: hh=0
        return f"{hh:02d}:{mm}:{ss}"
    except Exception:
        return "99:99:99"

# ── STEP 1: TRIGGER — active newcomers from the decision archive (+ last price) ──────────────
def _today_watchlist():
    """(levels, tickers) for DAY, or (None, None) if the dashboard is unreachable. Callers must
    FAIL CLOSED on None — skip the cycle / abort the post — never proceed blind: the POST endpoint
    REPLACES the day's tickers+levels, so a blind post would wipe them (Fable audit 7/18)."""
    try:
        wl = _get(f"{U}/api/kev_watchlist?date={DAY}")
        return (wl.get("levels") or {}), (wl.get("tickers") or [])
    except Exception as e:
        print(f"[watchlist] fetch failed: {e}", flush=True)
        return None, None

def active_newcomers():
    """Returns (first_seen_map, last_price_map) for active names WITHOUT a level today.
    Roster = decision-archive actives ∪ the bot's morning WATCHING batch (7/18: the day-keyed
    /api/watching?date= history, so a stale prior-day snapshot can never leak in)."""
    lv, _tk = _today_watchlist()
    if lv is None:
        return {}, {}                      # dashboard unreachable → fail closed, retry next loop
    marked = {str(k).upper() for k in lv if not str(k).startswith("_")}
    try:
        rows = _get(f"{U}/api/decisions_archive?date={DAY}&limit=8000").get("rows") or []
    except Exception as e:
        print(f"[trigger] archive fetch failed: {e}", flush=True); return {}, {}
    first, status, px = {}, {}, {}
    for r in rows:
        tk=(r.get("ticker") or "").upper(); tm=r.get("time") or ""
        if not tk or tk in marked or tk.startswith("_"): continue
        status.setdefault(tk, set()).add(r.get("status"))
        if tk not in first or _ampm(tm) < _ampm(first[tk]): first[tk]=tm
        p=r.get("price")
        if p is not None:
            try: px[tk]=float(p)     # last-written price wins (rows are appended in time order)
            except (TypeError, ValueError): pass
    try:                                   # morning batch: read the scanner BEFORE names go active
        watch = _get(f"{U}/api/watching?date={DAY}").get("tickers") or []
    except Exception:
        watch = []                         # fail-soft: the archive roster still drives
    for tk in watch:
        tk = str(tk).upper()
        if not tk or tk in marked or tk.startswith("_") or tk in first: continue
        first[tk] = ""                     # no archive row yet — sorts FIRST = read first
        status.setdefault(tk, set()).add("watching")
    active={tk: first[tk] for tk in first if status[tk] & ACTIVE_STATUSES}
    return active, {tk: px.get(tk) for tk in active}

# ── candidate levels — PRECISE values computed from data (Lever 2: the model SELECTS, never eyeballs) ──
def _candidate_levels(hist):
    """Precise candidate levels from daily bars (through yesterday). The vision model reads STRUCTURE
    from the image but picks exact prices from THIS list — avoids pixel-misreads."""
    y=hist[-1]; prior=hist[:-1][-20:]
    pdh, pdc, pdl = y["h"], y["c"], y["l"]
    moHi = max(z["h"] for z in prior) if prior else pdh
    moLo = min(z["l"] for z in prior) if prior else pdl
    # swing/reaction highs: a high strictly greater than the 2 bars on each side (recent 30d)
    hs = hist[-30:]; react=[]
    for i in range(2, len(hs)-2):
        h=hs[i]["h"]
        if h>hs[i-1]["h"] and h>hs[i-2]["h"] and h>hs[i+1]["h"] and h>hs[i+2]["h"]:
            react.append(round(h,4))
    react=sorted(set(react))[-5:]
    # round numbers just above prior close
    rn=[]; x=(int(pdc*2)/2)+0.5
    for _ in range(4):
        if x>pdc: rn.append(round(x,2))
        x+=0.5
    return {"prior_day_high":round(pdh,4),"prior_day_close":round(pdc,4),"prior_day_low":round(pdl,4),
            "month_high":round(moHi,4),"month_low":round(moLo,4),
            "reaction_highs":react,"round_numbers_above":rn}

# ── STEP 2: RENDER — daily chart to PNG bytes (+ candidate levels) ───────────────────────────
def render_daily_png(ticker):
    try:
        bars = _get(f"{U}/api/daily?ticker={ticker}&count=45").get("bars") or []
    except Exception:
        return None, None
    b=[]
    for x in bars:
        try: b.append({"date":x["date"],"o":float(x["open"]),"h":float(x["high"]),
                       "l":float(x["low"]),"c":float(x["close"])})
        except Exception: pass
    b.sort(key=lambda z:z["date"]); hist=[z for z in b if z["date"] < DAY]
    if len(hist) < 2: return None, None    # ≥2 prior days (recent IPOs are core universe; was 6 — audit 7/18)
    cand=_candidate_levels(hist)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    # Kev weights YESTERDAY + recent days (Marcos 7/17) → show the recent window as LARGE, legible
    # candles (not a compressed 30-bar strip). Overhead supply that's older (month high) stays as a
    # LEVEL LINE so "room" is still visible even when it's off the candle window.
    RECENT_DAYS = int(os.environ.get("NEWCOMER_RECENT_DAYS", "6"))   # TIGHT (validated 7/18: Kev weights recent)
    show=hist[-RECENT_DAYS:]; y=hist[-1]
    pdh=cand["prior_day_high"]; pdc=cand["prior_day_close"]; moHi=cand["month_high"]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for i,x in enumerate(show):
        col="#26a69a" if x["c"]>=x["o"] else "#ef5350"
        ax.plot([i,i],[x["l"],x["h"]],color=col,lw=2.2)                       # thick = legible recent
        ax.add_patch(Rectangle((i-0.36,min(x["o"],x["c"])),0.72,abs(x["c"]-x["o"])+1e-9,color=col))
    ax.axhline(pdh,color="#1976d2",ls="--",lw=1.4,label=f"YESTERDAY high {pdh:.2f}")   # yesterday = key
    ax.axhline(pdc,color="#455a64",ls=":",lw=1.1,label=f"yesterday close {pdc:.2f}")
    if moHi > pdh*1.001:
        ax.axhline(moHi,color="purple",ls=":",lw=1.1,label=f"overhead ~month high {moHi:.2f}")
    for h in cand["reaction_highs"]:
        if abs(h-pdh) > 0.01: ax.axhline(h,color="gray",ls="-",lw=0.5,alpha=0.35)
    ax.set_title(f"{ticker}  DAILY last {len(show)}d (Kev: yesterday+recent)  yest: O{y['o']:.2f} H{y['h']:.2f} L{y['l']:.2f} C{y['c']:.2f}", fontsize=10)
    ax.set_xticks(range(len(show))); ax.set_xticklabels([x["date"][5:] for x in show],fontsize=7,rotation=45)
    ax.legend(fontsize=8, loc="best"); ax.grid(alpha=0.18)
    buf=io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format="png", dpi=90); plt.close(fig)
    return buf.getvalue(), cand

# ── STEP 3: READ — Claude vision (grounded persona + Kev spec + provided candidate levels) ──────
# Lever 1: the read IS the Momentum Operator reading per the canonical Kev system spec — not a generic
# "day trader". Lever 2: candidate levels are provided as DATA; the model SELECTS, never eyeballs.
READ_PROMPT = """You are an experienced small-cap momentum trader (Kev lineage) reading this TIGHT, recent DAILY chart of {ticker} (yesterday + the last several sessions). Mark the trigger for the NEXT trading day. Judge the chart on its own merits — no leaning toward caution or aggression.

★ MANDATORY — you MUST return a break_level (this is Kev's method): the specific price that, once broken and HELD, confirms a tradeable upside move. Required for EVERY name including weak/downtrending/choppy ones — for a weak name it is the price it must RECLAIM to become tradeable (yesterday's high, the reaction high, or the level it broke down from). NEVER return null for break_level. Why it's safe: we only trade if price actually reaches and HOLDS the level intraday; if it never gets there, we don't trade — so marking a level costs nothing and missing one costs a winner if it turns.

Assess objectively: TREND (up/down/sideways), STRUCTURE (base, coil near highs, pullback to support, breakdown, range), POSITION (near highs = room above, mid-range, at lows), ROOM (distance to next overhead vs risk to nearest support). For a gapper, use the MEANINGFUL recent structure high, not a stale prior-day high far below price.
setup="parabolic" ONLY for an already-vertical blow-off with no definable risk (that name has no safe reclaim — it will be vetoed). Everything else gets a real break_level.
Set verdict to your genuine lean (TAKE favors an upside break next day / SKIP favors downside-or-chop / MARGINAL mixed) — but the DECISION is the LEVEL, not the verdict.

PRECISE CANDIDATE LEVELS (computed from the data — SELECT the meaningful ones; do NOT estimate prices off the pixels):
{candidates}
current/last price ~ {last_px}

Return ONLY this JSON (no prose, no code fence). break_level is REQUIRED (never null); use null only for optional fields that don't apply:
{{"ticker":"{ticker}","setup":"base-breakout|uptrend-coil|pullback|downtrend|falling-knife|parabolic|chop","verdict":"TAKE|SKIP|MARGINAL","confidence":"HIGH|MEDIUM|LOW","break_level":0.00,"confirm_level":0.00,"next_supply":0.00,"stop_level":0.00,"targets":[0.00],"room_rr":0.0,"reason":"one concrete sentence citing the structure and the level"}}"""

def validate_read(rd, last_px):
    """LEVELS-ONLY validation (7/18): the DECISION is the break_level, not the verdict, so a break_level
    is MANDATORY for every read (parabolic = the one exception → vetoed at post, not here). Rejected =
    no level posted = that name is not armed. Returns (ok, why)."""
    if not isinstance(rd, dict) or rd.get("error"):
        return False, rd.get("error","not a dict")
    v = str(rd.get("verdict","")).upper()
    if v not in ("TAKE","SKIP","MARGINAL"):
        return False, f"bad verdict {v!r}"
    if str(rd.get("setup","")).lower() == "parabolic":
        return True, "parabolic → will be vetoed at post"      # valid read, no tradeable level
    brk = rd.get("break_level")
    try: brk = float(brk)
    except (TypeError, ValueError): return False, "mandatory break_level missing/non-numeric"
    if brk <= 0: return False, "break_level <= 0"
    stop = rd.get("stop_level")
    if stop is not None:
        try:
            if float(stop) >= brk: return False, "stop_level not below break_level"
        except (TypeError, ValueError): pass
    return True, "ok"

def vision_read(ticker, png_bytes, candidates, last_px):
    if not API_KEY:
        return {"error": "no ANTHROPIC_API_KEY"}
    try:
        import anthropic
    except Exception as e:
        return {"error": f"anthropic sdk missing: {e}"}
    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        img_b64 = base64.standard_b64encode(png_bytes).decode()
        prompt = READ_PROMPT.format(ticker=ticker, candidates=json.dumps(candidates),
                                    last_px=(round(last_px,4) if last_px else "n/a"))
        msg = client.messages.create(
            model=MODEL, max_tokens=700,
            messages=[{"role":"user","content":[
                {"type":"image","source":{"type":"base64","media_type":"image/png","data":img_b64}},
                {"type":"text","text": prompt},
            ]}],
        )
        raw = "".join(bl.text for bl in msg.content if getattr(bl,"type",None)=="text").strip()
        if "```" in raw:                                  # strip a stray fence if the model adds one
            raw = raw.split("```")[1].replace("json","",1).strip() if "```json" in raw else raw.split("```")[1].strip()
        return json.loads(raw)
    except Exception as e:
        return {"error": f"vision_read failed: {e}"}

# ── STEP 4: WRITE — merge the read's level into the kev_watchlist _levels store ──────────────
def post_level(ticker, read):
    """MERGE (never overwrite): GET today's levels, add/replace this ticker, POST the union.
    LEVELS-ONLY (7/18): post the mandatory break_level for EVERY name regardless of verdict — the
    intraday break-and-hold-on-volume (shadow_trigger_10s) is what filters knives, NOT the verdict.
    ONLY exception = setup 'parabolic' (no definable risk / Kev pass) → do-not-trade note = not armed.
    Fable audit 7/18: (a) ABORT if the GET fails — the POST endpoint REPLACES the day's store, a blind
    post wipes it; (b) pass the tickers list through UNCHANGED — posting cur.keys() grew the bot's
    force-watched kev list every rescan (marcos_trading_bot line ~6038) = stream/rate-limit pollution."""
    cur, tickers = _today_watchlist()
    if cur is None:
        return False                       # never post blind — retry next loop (attempts-capped)
    verdict = str(read.get("verdict","")).upper()
    reason  = str(read.get("reason",""))[:120]
    # the gate vetoes on the phrase "do not trade" in the note — scrub model-authored reason text so
    # a phrase inside a TAKE reason can't accidentally veto the name
    reason  = re.sub(r"do[- ]?not[- ]?trade", "", reason, flags=re.I).strip()
    if str(read.get("setup","")).lower() == "parabolic":
        entry = {"break": read.get("break_level"), "confirm": None, "targets": [],
                 "setup": "parabolic", "confidence": read.get("confidence"),
                 "note": f"do-not-trade — parabolic blow-off: {reason}", "src": "vision"}
    else:  # mandatory level for every other name → armed; intraday break-and-hold decides
        entry = {"break": read.get("break_level"), "confirm": read.get("confirm_level"),
                 "next_supply": read.get("next_supply"), "stop": read.get("stop_level"),
                 "room_rr": read.get("room_rr"), "targets": read.get("targets") or [],
                 "setup": read.get("setup"), "confidence": read.get("confidence"),
                 "note": f"vision {verdict} (levels-only): {reason}", "src": "vision"}
    cur[ticker] = entry
    try:
        _post("/api/kev_watchlist", {"date": DAY, "tickers": tickers, "levels": cur})
        return True
    except Exception as e:
        print(f"[write] post failed for {ticker}: {e}", flush=True); return False

# ── Kev-sheet SHADOW reads (Marcos 7/18: "I want to give you the Kev list at night with his
# levels but I want us to also have an automated read for them so we can grade out our reading
# capabilities.") — HIS levels stay canonical for the gate; OUR read of the same chart is stored
# BESIDE them under 'vision_shadow'. The gate reads only top-level break/note, so a shadow can
# NEVER affect trading. grade_reads_eod.py turns the pairs into the daily reading scorecard. ──
def post_shadow(ticker, read):
    cur, tickers = _today_watchlist()
    if cur is None:
        return False                       # never post blind (endpoint REPLACES the day's store)
    entry = dict(cur.get(ticker) or {})
    entry["vision_shadow"] = {
        "break": read.get("break_level"), "confirm": read.get("confirm_level"),
        "next_supply": read.get("next_supply"), "stop": read.get("stop_level"),
        "setup": read.get("setup"), "verdict": read.get("verdict"),
        "confidence": read.get("confidence"), "room_rr": read.get("room_rr"),
        "reason": str(read.get("reason", ""))[:160],
        "model": MODEL, "read_at": f"{dt.datetime.now(ET):%H:%M:%S}",
    }
    cur[ticker] = entry
    try:
        _post("/api/kev_watchlist", {"date": DAY, "tickers": tickers, "levels": cur})
        return True
    except Exception as e:
        print(f"[shadow] post failed for {ticker}: {e}", flush=True); return False

def sheet_shadow_pass(dry=False, out_rows=None):
    """One shadow read per sheet name per day (presence of 'vision_shadow' = done). Runs at the
    top of every cycle, so a late-posted sheet still gets its exam on the next 90s poll."""
    lv, _ = _today_watchlist()
    if lv is None:
        return 0
    todo = sorted(str(tk).upper() for tk, d in lv.items()
                  if isinstance(d, dict) and not str(tk).startswith("_")
                  and d.get("src") != "vision" and "vision_shadow" not in d)
    done = 0
    for tk in todo:
        if _attempts.get(tk, 0) >= MAX_ATTEMPTS or _rfail.get(tk, 0) >= MAX_RENDER_FAILS:
            continue
        time.sleep(SPACING)
        png, cand = render_daily_png(tk)
        if not png:
            _rfail[tk] = _rfail.get(tk, 0) + 1
            print(f"  [shadow] {tk}: no daily chart (fetch fail {_rfail[tk]}/{MAX_RENDER_FAILS}) — retry", flush=True)
            continue
        rd = vision_read(tk, png, cand, (cand or {}).get("prior_day_close"))
        if rd.get("error"):                # transport/API error → free retry, never burns the graded cap
            _rfail[tk] = _rfail.get(tk, 0) + 1
            print(f"  [shadow] {tk}: read error ({_rfail[tk]}/{MAX_RENDER_FAILS}): {rd['error']}", flush=True)
            continue
        _attempts[tk] = _attempts.get(tk, 0) + 1
        ok_v, why = validate_read(rd, None)
        if out_rows is not None:
            out_rows.append({**rd, "ticker": tk, "_shadow": True, "_accepted": ok_v, "_why": why})
        if not ok_v:
            print(f"  [shadow] {tk}: REJECTED ({why})", flush=True); continue
        kev = (lv.get(tk) or {}).get("break")
        if dry:
            print(f"  [shadow-DRY] {tk}: our break={rd.get('break_level')} vs Kev {kev} (not stored)", flush=True)
            done += 1; continue
        ok = post_shadow(tk, rd)
        print(f"  [shadow] {tk}: our break={rd.get('break_level')} vs Kev {kev} "
              f"→ {'stored' if ok else 'POST FAILED'}", flush=True)
        done += 1
    return done

# ── driver ───────────────────────────────────────────────────────────────────────────────────
def already_read():
    """Names that already have a vision level today (avoid re-reading / re-billing)."""
    try:
        lv = _get(f"{U}/api/kev_watchlist?date={DAY}").get("levels") or {}
        return {tk for tk,v in lv.items() if isinstance(v,dict) and v.get("src")=="vision"}
    except Exception:
        return set()

def process_once(dry=False, out_rows=None):
    sheet_shadow_pass(dry=dry, out_rows=out_rows)   # the Kev-sheet exam runs FIRST (8:50, pre-open)
    # dry (bake-off / live-proof): read + validate + PRINT every active newcomer, never post.
    seen = set() if dry else already_read()
    roster, pxmap = active_newcomers()
    todo = [(tm,tk) for tk,tm in roster.items() if tk not in seen]
    todo.sort()
    print(f"[{dt.datetime.now(ET):%H:%M:%S}] active={len(roster)} already-read={len(seen)} "
          f"to-read={len(todo)}{'  (DRY — no posts)' if dry else ''}", flush=True)
    for tm,tk in todo:
        if _attempts.get(tk, 0) >= MAX_ATTEMPTS or _rfail.get(tk, 0) >= MAX_RENDER_FAILS:
            continue                       # gave up on this name today (cost guard) → stays unarmed
        time.sleep(SPACING)                # pace Webull-backed daily GETs + vision calls
        png, cand = render_daily_png(tk)
        if not png:                        # /api/daily is Webull-live → could be a 429; free retry
            _rfail[tk] = _rfail.get(tk, 0) + 1
            print(f"  {tk}: no daily chart (fetch fail {_rfail[tk]}/{MAX_RENDER_FAILS}) — retry next loop", flush=True)
            continue
        last_px = pxmap.get(tk) or (cand or {}).get("prior_day_close")
        rd = vision_read(tk, png, cand, last_px)
        if rd.get("error"):                # transport/API error → NOT a graded attempt (an Anthropic
            _rfail[tk] = _rfail.get(tk, 0) + 1     # outage at 8:50 must never kill a name for the day);
            print(f"  {tk}: read error ({_rfail[tk]}/{MAX_RENDER_FAILS}): {rd['error']}", flush=True)
            continue                               # bounded by the free-retry cap + 90s loop cadence
        _attempts[tk] = _attempts.get(tk, 0) + 1   # count GRADED reads only (billed + parseable)
        ok_v, why = validate_read(rd, last_px)
        if out_rows is not None:                              # capture EVERY read for grading (accepted or not)
            out_rows.append({**rd, "ticker": tk, "_accepted": ok_v, "_why": why})
        if not ok_v:
            print(f"  {tk}: REJECTED ({why}) → no post = no-read = no-trade", flush=True); continue
        if dry:
            print(f"  {tk}: DRY {rd.get('verdict')}/{rd.get('confidence')} [{rd.get('setup')}] "
                  f"break={rd.get('break_level')} (not posted)  ({str(rd.get('reason',''))[:55]})", flush=True)
            continue
        ok = post_level(tk, rd)
        print(f"  {tk}: {rd.get('verdict')}/{rd.get('confidence')} [{rd.get('setup')}] "
              f"break={rd.get('break_level')} supply={rd.get('next_supply')} stop={rd.get('stop_level')} "
              f"→ {'posted' if ok else 'POST FAILED'}  ({str(rd.get('reason',''))[:55]})", flush=True)
    return len(todo)

def main():
    once = "--once" in sys.argv
    dry  = "--dry" in sys.argv                 # read+validate+PRINT, never post (bake-off / live-call proof)
    out  = None
    if "--out" in sys.argv:
        try: out = os.path.expanduser(sys.argv[sys.argv.index("--out") + 1])
        except IndexError: out = None
    print(f"[vision-reader] day={DAY} model={MODEL} once={once} dry={dry} stop={STOP_HHMM} "
          f"key={'set' if API_KEY else 'MISSING'}", flush=True)
    out_rows = [] if out else None
    if once or dry:
        process_once(dry=dry, out_rows=out_rows)
        if out is not None and out_rows is not None:
            with open(out, "w") as f:
                json.dump({r["ticker"]: r for r in out_rows}, f, indent=1)
            print(f"[vision-reader] wrote {len(out_rows)} reads → {out}", flush=True)
        return
    while True:
        now = dt.datetime.now(ET)
        if now.strftime("%H:%M") >= STOP_HHMM:
            print(f"[vision-reader] {now:%H:%M} reached {STOP_HHMM} — done.", flush=True); break
        try: process_once()
        except Exception as e: print(f"[loop] error: {e}", flush=True)
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
