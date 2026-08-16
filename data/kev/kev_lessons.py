#!/usr/bin/env python3
"""
kev_lessons.py — NIGHTLY KEV LESSONS REPORT (Marcos order 8/16: "with every picks sweep, also
pull his new shorts + videos and produce a report of lessons taught + what's usable for
improving the bot"). Kev Librarian office. Model for output quality:
data/killtests/kev_latest_mining_20260815.md (Friday's one-off).

Runs at the END of the existing sweep (kev_sweep_server.run_once), fail-soft — consumes only
what the sweep already pulled (YouTube shorts+videos, TikTok backstop dir). No new scraping.

Store roots (first existing set wins, or KEV_STORE_DIRS=colon-separated override):
  Railway : /data/kev/{shorts,videos,tiktok}                (kev_sweep_server DATA volume)
  local   : ~/Library/.../TradingBot/{transcripts,shorts/transcripts} + repo data/kev/tiktok
Watermark: data/kev/lessons_seen.json (video-id set = "processed for lessons").
Outputs  : data/kev/LESSONS_YYYYMMDD.md (new items, by theme), data/kev/KEV_LESSONS_LEDGER.md
           (rolling append), data/kev/lessons_latest.json (dashboard tile; mirrored to /data/kev
           when that volume exists so the tile survives redeploys).
Extraction: Claude API, same client/model pattern as newcomer_vision_reader.py.
Doctrine  : grade-the-bot — extract SYSTEM, discard PSYCHOLOGY (tagged, kept out of actionable).

Flags: --dry-run (no API, no writes; lists what WOULD run) · --since YYYY-MM-DD (mtime floor;
       bootstrap) · --limit N · --no-mark (don't advance watermark)
First run with no watermark and no --since: only files modified in the last
KEV_LESSONS_BOOTSTRAP_DAYS (default 3) are extracted; everything else is marked seen.
"""
import os, re, sys, json, time, datetime, pathlib, argparse

HERE = pathlib.Path(__file__).resolve().parent            # repo data/kev
REPO = HERE.parent.parent
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("KEV_LESSONS_MODEL", os.environ.get("NEWCOMER_VISION_MODEL", "claude-sonnet-4-6"))
SEEN_FP = HERE / "lessons_seen.json"
LEDGER_FP = HERE / "KEV_LESSONS_LEDGER.md"
LATEST_FP = HERE / "lessons_latest.json"
VOLUME = pathlib.Path("/data/kev")
THEMES = ("entries", "exits", "premarket", "halts", "sizing", "regime", "psychology", "other")
OFFICERS = ("Reclaim Architect", "Hidden Entry Architect", "Trade Manager", "Opening Bell", "First Hour",
            "Rocket Rider", "Side Marshal", "Seam Scientist", "Crown Steward", "Handicapper",
            "Execution Surgeon", "Cartographer", "Kev Librarian", "Forward Architect")

def _log(msg):
    print(f"[kev-lessons] {msg}", flush=True)

def store_dirs():
    env = os.environ.get("KEV_STORE_DIRS")
    if env:
        return [pathlib.Path(p) for p in env.split(":") if p]
    if VOLUME.exists():
        return [VOLUME / "shorts", VOLUME / "videos", VOLUME / "tiktok"]
    ic = pathlib.Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/TradingBot"
    return [ic / "transcripts", ic / "shorts" / "transcripts", HERE / "tiktok"]

_ID_RX = re.compile(r"^(?:\d{3}_)?([A-Za-z0-9_-]{11}|\d{15,20})_(.*)$")

def scan_store():
    """-> list of dicts {vid, title, path, mtime, source}. Handles both naming schemes:
    Railway `{vid}_{title}.txt`, local `NNN_{vid}_{title}.txt`, tiktok `{19digits}_{title}.txt/.vtt`."""
    out = []
    for d in store_dirs():
        if not d.exists():
            continue
        src = d.name if d.name != "transcripts" else ("shorts" if d.parent.name == "shorts" else "videos")
        for f in sorted(d.iterdir()):
            if f.suffix not in (".txt", ".vtt") or not f.is_file():
                continue
            m = _ID_RX.match(f.name)
            if not m:
                continue
            vid, rest = m.group(1), m.group(2)
            title = rest.rsplit(".", 1)[0].replace("_", " ").strip()
            out.append({"vid": vid, "title": title, "path": str(f),
                        "mtime": f.stat().st_mtime, "source": src})
    return out

def load_seen():
    try:
        return set(json.loads(SEEN_FP.read_text()).get("seen", []))
    except Exception:
        return set()

def save_seen(seen):
    SEEN_FP.write_text(json.dumps({"seen": sorted(seen), "updated": _now_iso()}, indent=0))

def _now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def read_text(path, cap=24000):
    t = pathlib.Path(path).read_text(errors="ignore")
    if path.endswith(".vtt"):
        lines = [l for l in t.splitlines() if l.strip() and "-->" not in l and not l.startswith(("WEBVTT", "Kind:", "Language:"))]
        dedup = []
        for l in lines:
            if not dedup or dedup[-1] != l:
                dedup.append(l)
        t = "\n".join(dedup)
    return t[:cap]

def _date_guess(title, mtime):
    m = re.search(r"(\d{1,2})[/_](\d{1,2})[/_](\d{2})", title)
    if m:
        return f"20{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d} (from title)"
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") + " (file date; publish date UNVERIFIED)"

PROMPT = """You are the Kev Librarian for a small-cap momentum trading bot (Marcos's bot). Kev (@trade.momentum)
is the system spec. Extract every TRADING-SYSTEM lesson taught in this transcript. Ignore filler.
Doctrine: extract SYSTEM, discard PSYCHOLOGY (still list psychology items, theme="psychology", they are
tagged and skipped from the actionable list). Do not invent lessons; each needs a verbatim quote.

Bot mechanisms you may map to (use these exact names when they fit; else 'none'):
reclaim (pullback reclaim entry) · zone_flip · dip_rip · hidden_entry (10s flush/rocket lane, v2 rebuild) ·
break_attack (breakout over structure) · grinder · halt_lane (arm-only converts, crowns) · pbl_trail
(prior-bar-low trail) · scale_out_ladder (half/quarter/runners under prior highs) · topping_tail_exit ·
vwap_anchor (premarket anchor) · backside_gate (block 15-30% below stale high) · min_stop_width ·
liquidity_floor · leader_crown (40%+ gain AND halt/fresh-highs -> extra slots) · sizing_chain ·
premarket_session (07:00-09:25 entries) · top3_sheet (his TOP-3 levels) · character_book · none

Owning offices (pick one): {officers}

Return ONLY JSON, no prose:
{{"lessons":[{{"theme":"entries|exits|premarket|halts|sizing|regime|psychology|other",
 "lesson":"<one sentence, imperative, what he actually does>",
 "quote":"<verbatim from transcript, <=45 words>",
 "bot_mapping":"HAVE|PARTIAL|MISSING",
 "mechanism":"<name above or none>",
 "hypothesis":"<one testable sentence: 'If we X on Y then Z measured by $ over N days'>",
 "officer":"<office>"}}]}}
Cap at 8 lessons; prefer specific, structural, repeatable rules over generalities.

SOURCE: {title}  (date: {date}; kind: {source})
TRANSCRIPT:
{text}"""

def extract(item, client):
    text = read_text(item["path"])
    if len(text.strip()) < 200:
        return [], "too-short (music/no captions)"
    prompt = PROMPT.format(officers=", ".join(OFFICERS), title=item["title"], date=item["date"],
                           source=item["source"], text=text)
    msg = client.messages.create(model=MODEL, max_tokens=2200,
                                 messages=[{"role": "user", "content": prompt}])
    raw = "".join(getattr(b, "text", "") for b in msg.content)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return [], "no-json"
    try:
        data = json.loads(m.group(0))
    except Exception as e:
        return [], f"bad-json {e}"
    out = []
    for l in data.get("lessons", []):
        if not isinstance(l, dict) or not l.get("lesson"):
            continue
        th = str(l.get("theme", "other")).lower()
        if th not in THEMES:
            th = "other"
        out.append({"theme": th, "lesson": l.get("lesson", "").strip(), "quote": l.get("quote", "").strip(),
                    "date": item["date"], "source_title": item["title"], "vid": item["vid"], "source": item["source"],
                    "bot_mapping": str(l.get("bot_mapping", "MISSING")).upper()[:7],
                    "mechanism": l.get("mechanism", "none") or "none",
                    "hypothesis": l.get("hypothesis", "").strip(), "officer": l.get("officer", "Kev Librarian")})
    return out, "ok"

def write_reports(day, lessons, items, skipped, dry=False):
    actionable = [l for l in lessons if l["theme"] != "psychology"]
    psych = [l for l in lessons if l["theme"] == "psychology"]
    order = {"MISSING": 0, "PARTIAL": 1, "HAVE": 2}
    actionable.sort(key=lambda l: (order.get(l["bot_mapping"], 3), l["theme"]))
    md = [f"# Kev Lessons — {day} (nightly, auto) — Kev Librarian", "",
          f"Sources consumed this run: {len(items)} new transcript(s) ({sum(1 for i in items if i['source']=='videos')} videos, "
          f"{sum(1 for i in items if i['source']=='shorts')} shorts, {sum(1 for i in items if i['source']=='tiktok')} tiktok). "
          f"Model {MODEL}. Lessons: {len(actionable)} actionable + {len(psych)} psychology (tagged, skipped per grade-the-bot).",
          "Publish dates marked '(file date; publish date UNVERIFIED)' are store mtimes, not upload dates — Historian rule.", ""]
    md.append("## Sources")
    for i in items:
        md.append(f"- `{i['vid']}` {i['title']} — {i['date']} [{i['source']}] {skipped.get(i['vid'],'')}".rstrip())
    md.append("")
    md.append("## What's usable for the bot (MISSING first, then PARTIAL, then HAVE)")
    for th in THEMES:
        grp = [l for l in actionable if l["theme"] == th]
        if not grp:
            continue
        md.append(f"\n### {th.upper()}")
        for l in grp:
            md.append(f"- **[{l['bot_mapping']} · {l['mechanism']}]** {l['lesson']}  \n"
                      f"  > \"{l['quote']}\" — {l['source_title']} ({l['date']})  \n"
                      f"  Hypothesis: {l['hypothesis']}  · Officer: {l['officer']}")
    if psych:
        md.append("\n## Psychology (tagged, not actionable)")
        for l in psych:
            md.append(f"- {l['lesson']} — \"{l['quote']}\" ({l['source_title']})")
    md.append("")
    text = "\n".join(md)
    if dry:
        return text
    (HERE / f"LESSONS_{day.replace('-','')}.md").write_text(text)
    with LEDGER_FP.open("a") as fh:
        if LEDGER_FP.stat().st_size == 0:
            fh.write("# KEV LESSONS LEDGER (rolling, append-only; one block per nightly run)\n\n")
        fh.write(f"\n---\n## {day} run {_now_iso()} — {len(items)} sources, {len(actionable)} actionable, {len(psych)} psych\n")
        for l in actionable:
            fh.write(f"- [{l['theme']}/{l['bot_mapping']}/{l['mechanism']}] {l['lesson']} | \"{l['quote']}\" | {l['source_title']} ({l['date']}) | {l['officer']}\n")
    latest = {"day": day, "run_at": _now_iso(), "model": MODEL, "sources": len(items),
              "n_actionable": len(actionable), "n_psych": len(psych),
              "top": [{k: l[k] for k in ("theme", "lesson", "bot_mapping", "mechanism", "officer", "source_title", "date")}
                      for l in actionable[:12]],
              "report": f"data/kev/LESSONS_{day.replace('-','')}.md"}
    LATEST_FP.write_text(json.dumps(latest, indent=1))
    try:
        if VOLUME.exists():
            (VOLUME / "lessons_latest.json").write_text(json.dumps(latest, indent=1))
    except Exception:
        pass
    return text

def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD mtime floor")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("KEV_LESSONS_LIMIT", "60")))
    ap.add_argument("--no-mark", action="store_true")
    a = ap.parse_args(argv)
    day = datetime.date.today().strftime("%Y-%m-%d")
    seen = load_seen()
    allitems = scan_store()
    _log(f"store: {len(allitems)} files across {[str(d) for d in store_dirs()]}; seen={len(seen)}")
    floor = None
    if a.since:
        floor = datetime.datetime.strptime(a.since, "%Y-%m-%d").timestamp()
    elif not seen and not SEEN_FP.exists():
        floor = time.time() - 86400 * float(os.environ.get("KEV_LESSONS_BOOTSTRAP_DAYS", "3"))
        _log("no watermark: bootstrap mode (recent files only; older marked seen)")
    fresh = [i for i in allitems if i["vid"] not in seen and (floor is None or i["mtime"] >= floor)]
    # de-dup by vid (same video may sit in two stores)
    uniq = {}
    for i in fresh:
        uniq.setdefault(i["vid"], i)
    fresh = sorted(uniq.values(), key=lambda i: i["mtime"])[: a.limit]
    for i in fresh:
        i["date"] = _date_guess(i["title"], i["mtime"])
    _log(f"new for lessons: {len(fresh)}")
    if a.dry_run:
        for i in fresh:
            _log(f"  would extract {i['vid']} [{i['source']}] {i['title'][:70]}")
        return 0
    if not fresh:
        if not a.no_mark:
            save_seen(seen | {i["vid"] for i in allitems})
        return 0
    if not API_KEY:
        _log("ANTHROPIC_API_KEY missing — nothing extracted (watermark NOT advanced)")
        return 2
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    lessons, skipped, done = [], {}, []
    for i in fresh:
        try:
            ls, why = extract(i, client)
            lessons += ls
            done.append(i)
            if why != "ok":
                skipped[i["vid"]] = f"(skipped: {why})"
            _log(f"{i['vid']} {why} +{len(ls)} lessons")
            time.sleep(1)
        except Exception as e:
            skipped[i["vid"]] = f"(ERROR: {str(e)[:80]})"
            _log(f"{i['vid']} error {e}")
    write_reports(day, lessons, fresh, skipped)
    if not a.no_mark:
        save_seen(seen | {i["vid"] for i in done} | ({i["vid"] for i in allitems} if floor is not None and not a.since else set()))
    _log(f"wrote LESSONS_{day.replace('-','')}.md ({len(lessons)} lessons)")
    return 0

def run_safe():
    """Entry for the sweep: never raises."""
    try:
        return run([])
    except Exception as e:
        _log(f"FAILED soft: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run())
