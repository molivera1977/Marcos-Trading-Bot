"""Server-side Kev content sweep (#29, 8/4) — replaces the laptop scheduled tasks that silently
died 7/26-27 (kev-sweep-night lastRun 7/26, morning 7/27; Marcos hand-fed content for a week).

Runs INSIDE the dashboard service as a daemon thread (no cron infra needed):
  - weekdays ~20:06 ET: fetch new shorts+videos -> /data/kev/ ; find "TOP 3 STOCKS <TOMORROW>"
    short; parse levels with Claude; merge-POST to the kev sheet for TOMORROW (src=kev).
  - weekdays ~09:02 ET: fetch again; find "TOP 3 ... UPDATE <TODAY>"; parse; merge-POST TODAY.
  - RETRY-UNTIL-CLEAN (Marcos 8/3: "you may have to run the kev sweep multiple times"): fetch
    passes repeat until one completes with 0 new + 0 errors, max 5, backoff between.
  - EVERY run writes a kev_sweep decision row (found/posted/errors) — silence is never ambiguous.

Env (dashboard service): PROXY_USER/PROXY_PASS (Webshare), ANTHROPIC_API_KEY, DASHBOARD_SECRET.
KEV_SWEEP_SERVER=0 disables. Fail-soft everywhere: a sweep failure must never hurt the dashboard.
"""
import os, re, json, time, csv, threading, datetime, urllib.request
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    import pytz
    ET = pytz.timezone("America/New_York")

CHANNEL = "https://www.youtube.com/@trade.momentum"
DATA = Path("/data/kev") if Path("/data").exists() else Path("/tmp/kev")
SECRET = os.environ.get("DASHBOARD_SECRET", "marcos2026")
SELF = "http://127.0.0.1:" + os.environ.get("PORT", "5001")
LIMIT = int(os.environ.get("KEV_SWEEP_LIMIT", "30"))

def _now():
    return datetime.datetime.now(ET)

def _decision(status, **kw):
    try:
        body = json.dumps({"ticker": "_KEV", "status": status, **kw}).encode()
        urllib.request.urlopen(urllib.request.Request(
            SELF + "/api/decision", data=body,
            headers={"Content-Type": "application/json"}), timeout=10)
    except Exception:
        pass

def _list_videos(tab):
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "extract_flat": True, "playlistend": LIMIT}) as y:
        info = y.extract_info(f"{CHANNEL}/{tab}", download=False)
    out = []
    for e in (info.get("entries") or []):
        if e and e.get("id"):
            out.append((e["id"], e.get("title") or ""))
    return out

def _fetch_transcript(vid):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig
    api = YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
        proxy_username=os.environ["PROXY_USER"], proxy_password=os.environ["PROXY_PASS"]))
    tr = api.fetch(vid)
    return "\n".join(s.text for s in tr)

def _safe_name(title):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", title)[:80]

def fetch_pass(tab, outdir):
    """One fetch pass. Returns (new_saved, errors)."""
    outdir.mkdir(parents=True, exist_ok=True)
    have = {f.name.split("_", 1)[0] for f in outdir.glob("*.txt")}
    new = errors = 0
    for vid, title in _list_videos(tab):
        if vid in have:
            continue
        try:
            text = _fetch_transcript(vid)
            (outdir / f"{vid}_{_safe_name(title)}.txt").write_text(
                f"{title}\nhttps://www.youtube.com/watch?v={vid}\n{'='*60}\n\n{text}")
            new += 1
            time.sleep(2)
        except Exception:
            errors += 1
            time.sleep(4)
    return new, errors

def sweep_until_clean():
    """Retry-until-clean across both tabs. Returns dict tally."""
    tally = {"passes": 0, "new": 0, "errors_final": 0}
    for i in range(5):
        tally["passes"] = i + 1
        n1, e1 = fetch_pass("shorts", DATA / "shorts")
        n2, e2 = fetch_pass("videos", DATA / "videos")
        tally["new"] += n1 + n2
        tally["errors_final"] = e1 + e2
        if (n1 + n2) == 0 and (e1 + e2) == 0:
            break
        time.sleep(10 + 10 * i)
    return tally

DAYNAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

def find_top3(for_date, update=False):
    """Newest shorts transcript whose title is the TOP 3 sheet for for_date."""
    dn = DAYNAMES[for_date.weekday()]
    md = f"{for_date.month}/{for_date.day}"          # titles use M/D
    best = None
    for f in sorted((DATA / "shorts").glob("*.txt"), key=lambda x: -x.stat().st_mtime):
        head = f.read_text(errors="ignore").split("\n", 1)[0].upper()
        if "TOP 3" not in head or dn not in head:
            continue
        if md.replace("/", "") not in head.replace("/", ""):
            continue
        if update != ("UPDATE" in head):
            continue
        best = f
        break
    return best

PARSE_PROMPT = """You are extracting Kev's TOP-3 stock watchlist levels from his video transcript.
Return STRICT JSON only, no prose: {"levels": {"<TICKER>": {"break": <num or null>,
"confirm": <num or null>, "targets": [<nums>], "veto": <true if he says do-not-trade>,
"note": "<one-line plan summary with his key prices>"}}}
Rules: tickers are 2-5 capital letters he names as picks. Prices must come from the transcript.
Transcription garbles numbers: "$184" on a ~$1.80 stock means 1.84 — normalize to the stock's
obvious scale from context. Omit a field rather than guess. Do-not-trade names get veto:true
and no break/targets.
TRANSCRIPT:
"""

def parse_top3(path):
    import anthropic
    text = path.read_text(errors="ignore")[:12000]
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(model=os.environ.get("KEV_PARSE_MODEL", "claude-sonnet-4-6"),
                                 max_tokens=1200,
                                 messages=[{"role": "user", "content": PARSE_PROMPT + text}])
    raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "", 1).strip()
    return json.loads(raw).get("levels") or {}

def post_sheet(date_str, levels, src_file):
    clean = {}
    for tk, v in levels.items():
        if not re.fullmatch(r"[A-Z]{1,5}", str(tk or "")):
            continue
        rec = {"src": "kev", "note": f"[server-sweep {_now():%m/%d %H:%M}] " + str(v.get("note") or "")}
        for k in ("break", "confirm"):
            try:
                if v.get(k): rec[k] = float(v[k])
            except Exception:
                pass
        try:
            tg = [float(x) for x in (v.get("targets") or []) if float(x) > 0]
            if tg: rec["targets"] = tg
        except Exception:
            pass
        if v.get("veto"): rec["veto"] = True
        clean[tk] = rec
    if not clean:
        return 0
    body = json.dumps({"date": date_str, "tickers": sorted(clean), "levels": clean}).encode()
    urllib.request.urlopen(urllib.request.Request(
        SELF + "/api/kev_watchlist", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Dashboard-Secret": SECRET}), timeout=15)
    return len(clean)

def run_once(kind):
    """kind: 'night' (sheet for tomorrow) or 'morning' (UPDATE for today)."""
    t0 = time.time()
    try:
        tally = sweep_until_clean()
        target = _now().date() + datetime.timedelta(days=1 if kind == "night" else 0)
        while kind == "night" and target.weekday() >= 5:      # Friday night -> Monday sheet
            target += datetime.timedelta(days=1)
        f = find_top3(target, update=(kind == "morning"))
        posted = 0
        if f:
            posted = post_sheet(target.strftime("%Y-%m-%d"), parse_top3(f), f.name)
        _decision("kev_sweep", kind=kind, passes=tally["passes"], new=tally["new"],
                  fetch_errors=tally["errors_final"], sheet_file=(f.name if f else None),
                  posted=posted, secs=round(time.time() - t0))
        print(f"[kev-sweep] {kind}: {tally} sheet={'none' if not f else f.name} posted={posted}", flush=True)
    except Exception as e:
        _decision("kev_sweep_error", kind=kind, error=str(e)[:200])
        print(f"[kev-sweep] {kind} FAILED: {e}", flush=True)

def _loop():
    done = set()
    while True:
        try:
            now = _now()
            key_n = (now.strftime("%Y-%m-%d"), "night")
            key_m = (now.strftime("%Y-%m-%d"), "morning")
            if now.weekday() < 5 and "20:06" <= now.strftime("%H:%M") <= "20:30" and key_n not in done:
                done.add(key_n); run_once("night")
            if now.weekday() < 5 and "09:02" <= now.strftime("%H:%M") <= "09:20" and key_m not in done:
                done.add(key_m); run_once("morning")
        except Exception as e:
            print(f"[kev-sweep] loop error: {e}", flush=True)
        time.sleep(45)

def start():
    if os.environ.get("KEV_SWEEP_SERVER", "1") != "1":
        print("[kev-sweep] disabled by env"); return
    for dep in ("yt_dlp", "youtube_transcript_api", "anthropic"):
        try:
            __import__(dep)
        except ImportError:
            print(f"[kev-sweep] missing dep {dep} — sweep disabled (dashboard unaffected)"); return
    if not (os.environ.get("PROXY_USER") and os.environ.get("PROXY_PASS")
            and os.environ.get("ANTHROPIC_API_KEY")):
        print("[kev-sweep] missing PROXY_USER/PROXY_PASS/ANTHROPIC_API_KEY — sweep disabled"); return
    threading.Thread(target=_loop, daemon=True, name="kev_sweep").start()
    print("[kev-sweep] server-side sweep armed (20:06 + 09:02 ET weekdays, retry-until-clean)")
