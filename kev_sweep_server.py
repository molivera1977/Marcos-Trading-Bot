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
import os, re, json, time, csv, threading, datetime, urllib.request, urllib.error
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
            # 8/4 late: the endpoint 401s without the secret — every sweep row since the
            # migration was silently swallowed by the fail-soft except (sheet posts worked
            # because post_sheet DOES send it). The known #29 "decision-row write fix".
            headers={"Content-Type": "application/json", "X-Dashboard-Secret": SECRET}), timeout=10)
    except Exception:
        pass

def _proxy_url():
    """8/6 (Marcos's terminal tool succeeding at 9:26 while our fetches failed): the transcript
    fetch was ALREADY proxied but the yt-dlp LISTING went out on Railway's datacenter IP —
    YouTube challenges those, the sweep finds no videos, and it reads as "caption lag".
    Same Webshare rotating gateway for both steps now. Fail-open: no creds -> no proxy."""
    u, p = os.environ.get("PROXY_USER"), os.environ.get("PROXY_PASS")
    return f"http://{u}-rotate:{p}@p.webshare.io:80/" if u and p else None

def _list_videos(tab):
    from yt_dlp import YoutubeDL
    _opts = {"quiet": True, "extract_flat": True, "playlistend": LIMIT}
    _px = _proxy_url()
    if _px:
        _opts["proxy"] = _px
    with YoutubeDL(_opts) as y:
        info = y.extract_info(f"{CHANNEL}/{tab}", download=False)
    out = []
    for e in (info.get("entries") or []):
        if e and e.get("id"):
            out.append((e["id"], e.get("title") or ""))
    return out

def _fetch_transcript(vid):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig
    _u, _p = os.environ.get("PROXY_USER"), os.environ.get("PROXY_PASS")
    api = (YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
               proxy_username=_u, proxy_password=_p)) if _u and _p
           else YouTubeTranscriptApi())   # 8/6 fail-soft: local runs without creds still work
    tr = api.fetch(vid)
    return "\n".join(s.text for s in tr)

def _safe_name(title):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", title)[:80]

def fetch_pass(tab, outdir):
    """One fetch pass. Returns (new_saved, errors)."""
    outdir.mkdir(parents=True, exist_ok=True)
    # 8/9 (Marcos: "why so many new ones?"): YouTube ids CONTAIN underscores (EJxD_4mUiTA) —
    # split("_")[0] truncated those ids, so ~8 videos refetched EVERY pass of EVERY sweep
    # (~35-43 "new"/run for days, on the proxy budget). Ids are always 11 chars — slice, don't split.
    have = {f.name[:11] for f in outdir.glob("*.txt")}
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

# ── 8/11 TIKTOK SHEET BACKSTOP (task #45; Marcos: late 8/10 sheet existed ONLY on TikTok —
# both YouTube sweeps would have missed it; his link + yt-dlp caption pull recovered it).
# SHORTS-ONLY scope (Marcos: "tik tok would only have his shorts"): sheet + morning-UPDATE
# backstop, NOT a corpus source — long-form lessons stay YouTube. @momentum.official is his
# ONLY TikTok account (Marcos 8/11). No auth needed: public posts, captions free. ──
TIKTOK_USER = os.environ.get("KEV_TIKTOK", "momentum.official")

def _tiktok_list(limit=None):
    from yt_dlp import YoutubeDL
    _opts = {"quiet": True, "extract_flat": True, "playlistend": limit or LIMIT}
    _px = _proxy_url()
    if _px:
        _opts["proxy"] = _px
    with YoutubeDL(_opts) as y:
        info = y.extract_info(f"https://www.tiktok.com/@{TIKTOK_USER}", download=False)
    return [(e["id"], e.get("title") or "") for e in (info.get("entries") or [])
            if e and e.get("id")]

def _vtt_to_text(vtt):
    out, prev = [], None
    for ln in vtt.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("WEBVTT") or "-->" in ln or ln.isdigit():
            continue
        if ln != prev:
            out.append(ln); prev = ln
    return "\n".join(out)

def _tiktok_captions(vid):
    """Caption text for one TikTok post — the EXACT CLI path proven on the 8/10 night sheet
    (`--write-subs --write-auto-subs --skip-download`): bare extract_info returns EMPTY
    subtitle dicts for TikTok, so we run the download pipeline into a temp dir and read the
    .vtt it writes."""
    import tempfile, pathlib as _pl
    from yt_dlp import YoutubeDL
    with tempfile.TemporaryDirectory() as td:
        _opts = {"quiet": True, "skip_download": True, "writesubtitles": True,
                 "writeautomaticsub": True, "subtitleslangs": ["all"],
                 "outtmpl": str(_pl.Path(td) / "cap")}
        _px = _proxy_url()
        if _px:
            _opts["proxy"] = _px
        with YoutubeDL(_opts) as y:
            y.download([f"https://www.tiktok.com/@{TIKTOK_USER}/video/{vid}"])
        vtts = sorted(_pl.Path(td).glob("cap*.vtt"),
                      key=lambda p: (not p.name.lower().startswith("cap.eng"), p.name))
        if not vtts:
            raise RuntimeError("no vtt captions written")
        return _vtt_to_text(vtts[0].read_text(errors="ignore"))

def tiktok_pass(limit=None):
    """One TikTok backstop pass -> DATA/tiktok/. Returns (new_saved, errors). Fail-soft:
    a TikTok outage must never break the YouTube sweep (callers wrap in try)."""
    outdir = DATA / "tiktok"
    outdir.mkdir(parents=True, exist_ok=True)
    have = {f.name.split("_")[0] for f in outdir.glob("*.txt")}   # TikTok ids: 19 digits, no "_"
    new = errors = 0
    for vid, title in _tiktok_list(limit):
        if vid in have:
            continue
        try:
            try:
                text = _tiktok_captions(vid)
            except RuntimeError:
                time.sleep(5)                 # one retry before concluding caption-less —
                text = _tiktok_captions(vid)  # a transient miss must not stub a real sheet
            (outdir / f"{vid}_{_safe_name(title)}.txt").write_text(
                f"{title}\nhttps://www.tiktok.com/@{TIKTOK_USER}/video/{vid}\n{'='*60}\n\n{text}")
            new += 1
            time.sleep(2)
        except RuntimeError:
            # caption-less post (bio clips etc.) — stub it so it never re-errors on every pass.
            # NOTE: the title line still feeds find_top3, so a caption-less SHEET post still
            # surfaces the sheet's existence (vision/YouTube then carry the levels).
            (outdir / f"{vid}_{_safe_name(title)}.txt").write_text(
                f"{title}\nhttps://www.tiktok.com/@{TIKTOK_USER}/video/{vid}\n{'='*60}\n\n"
                f"[no captions on this post]")
            time.sleep(2)
        except Exception:
            errors += 1
            time.sleep(3)
    return new, errors

DAYNAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

def find_top3(for_date, update=False):
    """Newest shorts transcript whose title is the TOP 3 sheet for for_date."""
    dn = DAYNAMES[for_date.weekday()]
    md = f"{for_date.month}/{for_date.day}"          # titles use M/D
    best = None
    # 8/11 backstop + auditor BLOCKER fix: SHORTS FIRST, tiktok only when YouTube has no match
    # (mtime-merged pools let a caption-less TikTok stub out-mtime and SHADOW the real YouTube
    # sheet all night — backstop must never outrank the primary).
    for _dir in ("shorts", "tiktok"):
        for f in sorted((DATA / _dir).glob("*.txt"), key=lambda x: -x.stat().st_mtime):
            head = f.read_text(errors="ignore").split("\n", 1)[0].upper()
            if "TOP 3" not in head or dn not in head:
                continue
            if md.replace("/", "") not in head.replace("/", ""):
                continue
            if update != ("UPDATE" in head):
                continue
            best = f
            break
        if best:
            break
    return best

PARSE_PROMPT = """You are extracting Kev's TOP-3 stock watchlist levels from his video transcript.
Return STRICT JSON only, no prose: {"levels": {"<TICKER>": {"break": <num or null>,
"confirm": <num or null>, "targets": [<nums>],
"note": "<one-line plan summary with his key prices>"}}}
Rules: tickers are 2-5 capital letters he names as picks. Prices must come from the transcript.
Transcription garbles numbers: "$184" on a ~$1.80 stock means 1.84 — normalize to the stock's
obvious scale from context. Omit a field rather than guess. NEVER emit veto — Kev's stand-down
language ("leave it alone", "done", "do not trade") goes into the note VERBATIM, and you must
STILL extract every price he mentions alongside it. His numbers always post; his opinions are
information only.
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



# ── 8/8 (#32) FRAME-VISION CHECK — kill-tested same day on the NAMI/NMI specimen: frames
# recovered NAMI, CLRO, DSY exactly (captions had said NMI) and every Kev level appeared in the
# extracted price lines (NAMI 13/10; CLRO 20/16.5/12.77/10.5; DSY 15/8.21/7.30). The SCREEN is
# Kev's ground truth; captions are a witness. v1 = TICKER AUTHORITY: screen tickers override
# caption-parsed tickers (edit-distance pairing, order preserved); levels logged for cross-check
# (not enforced v1). Fail-soft at every step -> captions stand. Kill: KEV_VISION_CHECK=0.
_vision_cache = {}   # vid -> screen-ticker hits (8/8: retries must NOT re-download — proxy GB cap)
def _vision_check(vid, parsed_levels):
    if os.environ.get("KEV_VISION_CHECK", "1") != "1":
        return parsed_levels
    if str(vid).isdigit():   # 8/11 auditor W1: TikTok ids (19 digits) are NOT YouTube ids —
        # building a watch?v= URL burns ~80s of failed downloads in the fast path. Captions
        # stand without the frame check; ticker-authority layer loudly skipped.
        print(f"[kev-sweep] vision check skipped for TikTok-sourced sheet {vid} "
              f"(no YouTube frames) — captions stand", flush=True)
        return parsed_levels
    if vid in _vision_cache:
        hits = _vision_cache[vid]
        return _apply_screen_tickers(hits, parsed_levels) if hits else parsed_levels
    import tempfile, subprocess, base64, glob
    try:
        td = tempfile.mkdtemp()
        mp4 = os.path.join(td, "v.mp4")
        _px = _proxy_url()
        cmd = ["python3", "-m", "yt_dlp", "--extractor-args", "youtube:player_client=android",
               "-f", "best[height<=720]/best", "-o", mp4,
               f"https://www.youtube.com/watch?v={vid}"]
        if _px:
            cmd[3:3] = ["--proxy", _px]
        # 8/9 (Monday-sheet incident: one transient failure silently orphaned 2/3 of Kev's
        # picks): the download gets THREE attempts with backoff — a rate-walled first try is
        # YouTube weather, not a verdict.
        for _try, _wait in ((1, 0), (2, 20), (3, 60)):
            if _wait:
                time.sleep(_wait)
            subprocess.run(cmd, capture_output=True, timeout=180)
            if os.path.exists(mp4):
                break
            print(f"[kev-vision] download attempt {_try} failed", flush=True)
        if not os.path.exists(mp4):
            print("[kev-vision] download failed after 3 tries — captions stand", flush=True)
            return parsed_levels
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            print("[kev-vision] no ffmpeg — captions stand", flush=True)
            return parsed_levels
        subprocess.run([ff, "-i", mp4, "-vf", "fps=1/2,scale=480:-1", "-q:v", "5",
                        os.path.join(td, "f_%03d.jpg"), "-y"], capture_output=True, timeout=120)
        frames = sorted(glob.glob(os.path.join(td, "f_*.jpg")))
        if len(frames) < 6:
            return parsed_levels
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        hits = []
        for i in range(0, len(frames), 30):
            content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                        "data": base64.b64encode(open(f, "rb").read()).decode()}}
                       for f in frames[i:i + 30]]
            content.append({"type": "text", "text":
                "Frames from a stock watchlist video, in order. Some frames show a stock TICKER "
                "SYMBOL as large stylized text overlaid on a chart. List every such ticker in "
                "order of appearance. STRICT JSON: {\"tickers\":[str]}. Read letters EXACTLY."})
            msg = client.messages.create(model=os.environ.get("KEV_PARSE_MODEL", "claude-sonnet-4-6"),
                                         max_tokens=300,
                                         messages=[{"role": "user", "content": content}])
            raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "", 1).strip()
            try:
                for tk in json.loads(raw).get("tickers", []):
                    tk = str(tk).upper().strip()
                    if re.fullmatch(r"[A-Z]{1,5}", tk) and tk not in hits:
                        hits.append(tk)
            except Exception:
                continue
        _vision_cache[vid] = hits
        if not hits:
            print("[kev-vision] no on-screen tickers found — captions stand", flush=True)
            return parsed_levels
        print(f"[kev-vision] SCREEN tickers (authority): {hits}", flush=True)
        return _apply_screen_tickers(hits, parsed_levels)
    except Exception as e:
        print(f"[kev-vision] check failed ({e}) — captions stand", flush=True)
        return parsed_levels

def _apply_screen_tickers(hits, parsed_levels):
    try:
        def _dist(a, b):
            if a == b: return 0
            la, lb = len(a), len(b)
            d = [[i + j if i * j == 0 else 0 for j in range(lb + 1)] for i in range(la + 1)]
            for i in range(1, la + 1):
                for j in range(1, lb + 1):
                    d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1,
                                  d[i-1][j-1] + (a[i-1] != b[j-1]))
            return d[la][lb]
        out = {}
        caption_keys = list(parsed_levels.keys())
        used = set()
        for sk in hits:
            best, bd = None, 99
            for ck in caption_keys:
                if ck in used: continue
                dd = _dist(sk, ck)
                if dd < bd: best, bd = ck, dd
            if best is not None and bd <= 2:
                used.add(best)
                if sk != best:
                    print(f"[kev-vision] OVERRIDE: caption '{best}' -> screen '{sk}' "
                          f"(edit-dist {bd})", flush=True)
                out[sk] = parsed_levels[best]
            else:
                print(f"[kev-vision] screen ticker {sk} has no caption pair (dist>{bd}) — "
                      f"posted with note only", flush=True)
                out[sk] = {"note": "[vision] on-screen pick; caption parse found no plan"}
        for ck in caption_keys:              # caption-only leftovers survive (fail-open)
            if ck not in used and ck not in out:
                out[ck] = parsed_levels[ck]
        return out
    except Exception as e:
        print(f"[kev-vision] check failed ({e}) — captions stand", flush=True)
        return parsed_levels

def _last_px(tk):
    """Latest trade price via Alpaca; 0/None on any failure (caller fails open)."""
    k = os.environ.get("ALPACA_KEY"); sec = os.environ.get("ALPACA_SECRET")
    if not (k and sec):
        return None
    try:
        req = urllib.request.Request(f"https://data.alpaca.markets/v2/stocks/{tk}/trades/latest?feed=sip",
                                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": sec})
        j = json.load(urllib.request.urlopen(req, timeout=10))
        return float((j.get("trade") or {}).get("p") or 0) or None
    except Exception:
        return None

def _symbol_real(tk):
    """8/4 (EASY = verbal tic for EZRA, FUS = garble of FUSE — both posted as picks and FUS
    spammed INVALID_SYMBOL all morning): a parsed ticker must be a REAL listing before it
    reaches the sheet. Probe Alpaca's asset endpoint when keys exist; fail-OPEN without keys
    (regex-only, the old behavior) so a missing env never blanks the sheet."""
    k = os.environ.get("ALPACA_KEY"); sec = os.environ.get("ALPACA_SECRET")
    if not (k and sec):
        return True
    try:
        # 8/6: our env keys are PAPER keys — the live host 401s them, and the old
        # blanket `except -> False` dropped Kev's entire (real) Friday TOP-3.
        req = urllib.request.Request(f"https://paper-api.alpaca.markets/v2/assets/{tk}",
                                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": sec})
        a = json.load(urllib.request.urlopen(req, timeout=10))
        return bool(a.get("tradable")) or a.get("status") == "active"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False   # unknown symbol -> genuinely not real
        return True        # 401/5xx = API weather, never blank the sheet
    except Exception:
        return True        # network weather -> fail OPEN, same doctrine

_assets_cache = {"t": 0, "syms": None}
def _symbol_rescue(tk, pb=0.0):
    """8/9 (ZJYLL->ZJYL, ZNA->ZENA: caption garble guard-dropped 2/3 of Kev's Monday picks while
    the vision fallback was down): a NOT-REAL parsed symbol gets one caption-only rescue — the
    UNIQUE active listing within edit distance 1. Ambiguous (0 or 2+ matches) = no rescue; the
    downstream price fingerprint still validates whatever this returns. Fail-soft None."""
    try:
        k = os.environ.get("ALPACA_KEY"); sec = os.environ.get("ALPACA_SECRET")
        if not (k and sec):
            return None
        now = time.time()
        if not _assets_cache["syms"] or now - _assets_cache["t"] > 6 * 3600:
            req = urllib.request.Request("https://paper-api.alpaca.markets/v2/assets?status=active",
                                         headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": sec})
            _assets_cache["syms"] = {a["symbol"] for a in json.load(urllib.request.urlopen(req, timeout=20))
                                     if a.get("tradable") or a.get("status") == "active"}
            _assets_cache["t"] = now
        def _d1(a, b):
            if a == b: return False
            la, lb = len(a), len(b)
            if abs(la - lb) > 1: return False
            if la == lb:
                return sum(1 for x, y in zip(a, b) if x != y) == 1
            if la > lb: a, b, la, lb = b, a, lb, la
            i = j = diff = 0
            while i < la and j < lb:
                if a[i] == b[j]: i += 1; j += 1
                else:
                    diff += 1; j += 1
                    if diff > 1: return False
            return True
        cands = [s for s in _assets_cache["syms"] if _d1(tk, s)]
        if len(cands) == 1:
            return cands[0]
        # 8/9: multiple neighbors (ZNA -> {ZENA, ZNB}) — Kev's own parsed break price is the
        # tiebreaker: keep candidates whose live price sits within 2x of it; rescue only if
        # exactly ONE survives. No price or still ambiguous -> no rescue (conservative).
        if len(cands) > 1 and pb and pb > 0:
            _surv = []
            for _c in cands:
                try:
                    _cp = _last_px(_c)
                    if _cp and pb / 2.0 <= _cp <= pb * 2.0:
                        _surv.append(_c)
                except Exception:
                    pass
            if len(_surv) == 1:
                return _surv[0]
        return None
    except Exception:
        return None

def post_sheet(date_str, levels, src_file, src_text=""):
    post_sheet._src_text = src_text
    # 8/7 (Marcos: "his numbers have power but only i can veto" + the morning wipe that nulled
    # NAMI/CLRO): (a) the parser can NEVER mint veto:true — strip it; (b) None-valued fields are
    # DROPPED before the merge so a numberless update can never erase stored numbers.
    for _tk, _v in list(levels.items()):
        if isinstance(_v, dict):
            _v.pop("veto", None)
            for _k in [k for k, val in _v.items() if val is None]:
                _v.pop(_k, None)
    clean = {}
    for tk, v in levels.items():
        if not re.fullmatch(r"[A-Z]{1,5}", str(tk or "")):
            continue
        if not _symbol_real(tk):
            _rk = _symbol_rescue(tk, float(v.get("break") or 0) if isinstance(v, dict) else 0.0)
            if _rk:
                print(f"[kev-sweep] RESCUED {tk} -> {_rk} (unique edit-distance-1 active listing; "
                      f"caption-garble class ZJYLL/ZNA 8/9) — price fingerprint still applies", flush=True)
                v["note"] = f"[rescued {tk}->{_rk} caption garble] " + str(v.get("note") or "")
                tk = _rk
            else:
                print(f"[kev-sweep] DROPPED {tk}: not a real/active listing (parser hallucination guard)", flush=True)
                continue
        # 8/5 (HYM-for-HYFM, Marcos's catch): a REAL ticker can still be the WRONG ticker. The
        # transcript's own prices are the fingerprint — if the symbol's live price is more than
        # 3x away from the parsed break (either direction), the levels belong to a different
        # stock. Fail-open when no price is fetchable (never blank the sheet on API weather).
        try:
            _pb = float(v.get("break") or 0)
        except Exception:
            _pb = 0.0
        if _pb > 0:
            _px = _last_px(tk)
            if _px and (_pb > 3.0 * _px or _pb < _px / 3.0):
                # 8/5 RESCALE-AND-VERIFY (the AMIX-"1.4" lesson: spoken "fourteen" parsed as 1.4 —
                # the level was REAL, only the decimal was eaten; dropping lost Kev's $14 break and
                # plausibly an AMIX ticket). Before dropping, try decimal shifts: if a x10/x100
                # (or /10, /100) rescale of the break lands within 30% of the live price, rescale
                # EVERY numeric level by that factor and keep the entry, loudly.
                _fixed = False
                for _f in (10.0, 100.0, 0.1, 0.01):
                    _cand = _pb * _f
                    if _px * 0.7 <= _cand <= _px * 1.3:
                        for _k2 in ("break", "confirm"):
                            try:
                                if v.get(_k2): v[_k2] = round(float(v[_k2]) * _f, 4)
                            except Exception: pass
                        try:
                            v["targets"] = [round(float(x) * _f, 4) for x in (v.get("targets") or [])]
                        except Exception: pass
                        v["note"] = f"[rescaled x{_f:g} — transcript decimal garble] " + str(v.get("note") or "")
                        print(f"[kev-sweep] RESCALED {tk} x{_f:g}: break {_pb} -> {v.get('break')} "
                              f"(live {_px}) — AMIX-14 class decimal garble", flush=True)
                        _fixed = True
                        break
                if not _fixed:
                    print(f"[kev-sweep] DROPPED {tk}: parsed break {_pb} vs live {_px} — scale mismatch, "
                          f"no clean decimal shift (HYM/HYFM class)", flush=True)
                    continue
        # 8/5 CROSS-WIRE GUARD (the AMIX-$1.40 class: another ticker's plan attributed to this
        # one at a plausible-enough scale). Each parsed level must appear in the transcript
        # within ~500 chars of a mention of THIS ticker. Fail-open when the transcript text is
        # unavailable; DROP when the ticker is present but its "levels" never appear near it.
        try:
            _txt = post_sheet._src_text or ""
            if _txt and tk in _txt:
                import re as _re2
                _spans = [m.start() for m in _re2.finditer(_re2.escape(tk), _txt)]
                def _near(val):
                    # 8/5 fix (first live decision was a FALSE POSITIVE on CLZ): transcripts
                    # garble decimals — "a break of 106" means $1.06. Match the garbled forms
                    # too: digits-only (106 for 1.06, 150 for 1.50) alongside the exact ones.
                    _v = float(val)
                    _forms = {f"{_v:g}", f"{_v:.2f}".rstrip("0").rstrip("."),
                              str(int(round(_v * 100))), str(int(round(_v * 10)))}
                    if _v.is_integer(): _forms.add(str(int(_v)))
                    for _fmt in _forms:
                        if not _fmt or len(_fmt) < 2: continue   # single digits match everything
                        for _m in _re2.finditer(_re2.escape(_fmt), _txt):
                            if any(abs(_m.start() - _sp) < 500 for _sp in _spans):
                                return True
                    return False
                _lead = [float(x) for x in ([v.get("break")] if v.get("break") else [])
                         + list(v.get("targets") or [])[:1] if x]
                if _lead and not any(_near(_lv) for _lv in _lead):
                    print(f"[kev-sweep] DROPPED {tk}: its levels never appear near its mention in the "
                          f"transcript — cross-wire suspected (AMIX-$1.40 class)", flush=True)
                    continue
        except Exception:
            pass
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
        # 8/4 TOP-3-FIRST (the 8/4 morning sweep finished 09:34 — after the bell — because 73
        # backlogged transcripts fetched before the sheet parsed). Order now: one SHORTS pass
        # (the sheet lives there) -> parse/post immediately -> then the full retry-until-clean
        # sweep for the corpus. The bot gets its levels minutes in, not last.
        target = _now().date() + datetime.timedelta(days=1 if kind == "night" else 0)
        while kind == "night" and target.weekday() >= 5:      # Friday night -> Monday sheet
            target += datetime.timedelta(days=1)
        posted = 0; f = None
        _tt_new = _tt_err = 0; _tt_ran = False
        try:
            fetch_pass("shorts", DATA / "shorts")
            f = find_top3(target, update=(kind == "morning"))
            if not f:   # 8/11 TikTok BACKSTOP (auditor W2: only when YouTube missed — zero
                        # added latency on the nights the primary works; fail-soft on outage)
                _tt_ran = True
                try:
                    _tt_new, _tt_err = tiktok_pass()
                except Exception as _te:
                    _tt_err = -1
                    print(f"[kev-sweep] tiktok pass failed ({_te}) — YouTube-only this run", flush=True)
                f = find_top3(target, update=(kind == "morning"))
            if f:
                posted = post_sheet(target.strftime("%Y-%m-%d"),
                                    _vision_check(f.name.split("_", 1)[0], parse_top3(f)),
                                    f.name, src_text=f.read_text(errors="ignore"))
                print(f"[kev-sweep] {kind}: TOP-3 posted FIRST ({f.name}, {posted} names, "
                      f"{round(time.time()-t0)}s in)", flush=True)
        except Exception as _pe:
            print(f"[kev-sweep] {kind}: top3-first pass failed ({_pe}) — full sweep may still find it", flush=True)
        tally = sweep_until_clean()
        if not f:
            f = find_top3(target, update=(kind == "morning"))
            if f:
                posted = post_sheet(target.strftime("%Y-%m-%d"),
                                    _vision_check(f.name.split("_", 1)[0], parse_top3(f)),
                                    f.name, src_text=f.read_text(errors="ignore"))
        if kind == "night":
            _night_posted["day"] = _now().strftime("%Y-%m-%d"); _night_posted["ok"] = posted > 0
        if kind == "morning":
            _morning_posted["day"] = _now().strftime("%Y-%m-%d"); _morning_posted["ok"] = posted > 0
        _decision("kev_sweep", kind=kind, passes=tally["passes"], new=tally["new"],
                  fetch_errors=tally["errors_final"], sheet_file=(f.name if f else None),
                  posted=posted, secs=round(time.time() - t0),
                  tiktok_new=_tt_new, tiktok_errors=_tt_err)
        print(f"[kev-sweep] {kind}: {tally} sheet={'none' if not f else f.name} posted={posted}", flush=True)
    except Exception as e:
        _decision("kev_sweep_error", kind=kind, error=str(e)[:200])
        print(f"[kev-sweep] {kind} FAILED: {e}", flush=True)

_night_posted = {"day": None, "ok": False}
_morning_posted = {"day": None, "ok": False}

def _loop():
    done = set()
    retried = set()
    while True:
        try:
            now = _now()
            day = now.strftime("%Y-%m-%d")
            key_n = (day, "night")
            key_m = (day, "morning")
            # window widened 8/5: a container booting after 20:30 (deploys) still runs the night
            # sweep once; the done-set prevents repeats, the hourly retry handles late uploads.
            # 8/8: night sweep runs EVERY day — Kev posts Monday's TOP-3 on SUNDAY evening,
            # and weekday-gating left the weekend deaf (Monday sheet would sit empty until 20:06
            # Monday). run_once already aims weekend nights at Monday's sheet.
            if "20:06" <= now.strftime("%H:%M") <= "23:45" and key_n not in done:
                done.add(key_n); run_once("night")
            # 8/5 (Marcos: "what happened to the automated sweeps?" — Kev's Thursday sheet wasn't
            # up at 20:06 and the single-shot window left tomorrow EMPTY): retry hourly until the
            # sheet posts or 23:45. Each retry is a full fetch+parse; guards apply as always.
            if (key_n in done and not _night_posted.get("ok")
                    and _night_posted.get("day") == day
                    and "21:15" <= now.strftime("%H:%M") <= "23:45"
                    and (day, now.strftime("%H")) not in retried):
                retried.add((day, now.strftime("%H")))
                print(f"[kev-sweep] night sheet still empty — hourly retry {now:%H:%M}", flush=True)
                run_once("night")
            if now.weekday() < 5 and "09:02" <= now.strftime("%H:%M") <= "09:20" and key_m not in done:
                done.add(key_m); run_once("morning")
            # 8/5 (caption lag: Wed's UPDATE — incl. AMIX's real $14 break — never landed because
            # YouTube captions weren't ready in the single 09:02 window): retry every ~20 min
            # until the morning sheet actually posts or 11:00.
            if (now.weekday() < 5 and key_m in done and not _morning_posted.get("ok")
                    and _morning_posted.get("day") == day
                    and "09:25" <= now.strftime("%H:%M") <= "11:00"
                    and (day, "m", now.strftime("%H:%M")[:4]) not in retried):
                retried.add((day, "m", now.strftime("%H:%M")[:4]))
                print(f"[kev-sweep] morning UPDATE still unposted — retry {now:%H:%M}", flush=True)
                run_once("morning")
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
