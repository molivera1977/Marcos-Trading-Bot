#!/usr/bin/env python3
"""NIGHTLY OPEN-HOLES SWEEP (built 2026-08-16, Marcos: "why do you need my prodding? start the process now").

Runs 23:30 nightly (launchd com.marcos.tradingbot.holessweep), after the 23:00 wall grader.
  1. parse data/holes/HOLES.md (one `### Hnn · title` block per hole, `- key: value` fields)
  2. engine=oos holes: auto-grade from data/history/OOS_WALL.md day count -> RUNNING (day k/5) or VERDICT
  3. pick top-N (HOLES_PER_NIGHT, default 2) OPEN engine=script holes IN FILE ORDER whose script + requires exist
  4. run each via subprocess (timeout HOLES_TIMEOUT_S, default 3600), capture output to data/holes/runs/,
     pull the first VERDICT/REFUTED/PASS/FAIL line as the auto-verdict, write status RAN (officer confirms)
  5. rewrite HOLES.md fields in place, append a line to SWEEP_LOG.md, write holes_latest.json (dashboard tile)
Fail-soft everywhere. NEVER touches the bot, the universe cache, or any live service.
  --dry : select + report only, run nothing, write nothing except holes_latest.json (dry marker) and log line.
"""
import json, os, re, subprocess, sys, datetime as dt, pathlib, traceback

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = ROOT / "data" / "holes"
HOLES = HERE / "HOLES.md"
LOG = HERE / "SWEEP_LOG.md"
LATEST = HERE / "holes_latest.json"
RUNS = HERE / "runs"
WALL = ROOT / "data" / "history" / "OOS_WALL.md"
N = int(os.environ.get("HOLES_PER_NIGHT", "2"))
TIMEOUT = int(os.environ.get("HOLES_TIMEOUT_S", "3600"))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now()
TODAY = NOW.strftime("%Y-%m-%d")

BLOCK_RE = re.compile(r"^### (H\d+) · (.+)$")


def parse():
    """-> (preamble_lines, [hole dicts with 'id','title','fields'(ordered),'lines'])"""
    pre, holes, cur = [], [], None
    for line in HOLES.read_text().splitlines():
        m = BLOCK_RE.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "fields": {}, "order": []}
            holes.append(cur)
            continue
        if cur is None:
            pre.append(line)
            continue
        fm = re.match(r"^- ([a-z_]+): ?(.*)$", line)
        if fm:
            cur["fields"][fm.group(1)] = fm.group(2)
            cur["order"].append(fm.group(1))
    return pre, holes


def render(pre, holes):
    out = list(pre)
    while out and out[-1] == "":
        out.pop()
    for h in holes:
        out += ["", f"### {h['id']} · {h['title']}"]
        for k in h["order"]:
            out.append(f"- {k}: {h['fields'].get(k, '')}")
    return "\n".join(out) + "\n"


def test_spec(h):
    d = {}
    for part in h["fields"].get("test", "").split("|"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def runnable(h):
    """script exists, requires paths exist, and no 'note' declares a missing detector/arm."""
    t = test_spec(h)
    if t.get("engine") != "script":
        return False, "engine!=script"
    s = ROOT / t.get("script", "")
    if not s.exists():
        return False, f"missing script {t.get('script')}"
    for r in [x for x in t.get("requires", "").split(";") if x]:
        if not (ROOT / r).exists():
            return False, f"missing data {r}"
    note = t.get("note", "").lower()
    for bad in ("not written", "to be added", "needs adding", "lacks --only", "until it exists"):
        if bad in note:
            return False, f"blocked by note: {t.get('note')}"
    return True, "ok"


def wall_days():
    try:
        return [l for l in WALL.read_text().splitlines() if l.strip().startswith("- ") and "PRE-WALL" not in l]
    except Exception:
        return []


def grade_oos(h, wall):
    """RUNNING with day count until >=5 wall days, then VERDICT (numbers = last wall line; officer reads vs bar)."""
    lane = test_spec(h).get("lane", "")
    days = len(wall)
    if h["fields"].get("status") not in ("OPEN", "RUNNING"):
        return None
    if days < 5:
        h["fields"]["status"] = "RUNNING"
        h["fields"]["last_run"] = f"{TODAY} (auto-oos)"
        h["fields"]["verdict"] = f"- (OOS day {days}/5, lane={lane}; wall={WALL.relative_to(ROOT)})"
        return f"{h['id']} oos day {days}/5"
    last = wall[-1].strip()
    h["fields"]["status"] = "VERDICT"
    h["fields"]["last_run"] = f"{TODAY} (auto-oos)"
    h["fields"]["verdict"] = f"OOS {days} days reached; latest wall line: {last} -- officer grades vs bar"
    return f"{h['id']} oos VERDICT-ready ({days} days)"


VERDICT_RE = re.compile(r"(VERDICT|REFUTED|PASS|FAIL|REDUNDANT)", re.I)


def run_hole(h):
    t = test_spec(h)
    RUNS.mkdir(exist_ok=True)
    out = RUNS / f"{h['id']}_{NOW.strftime('%Y%m%d_%H%M')}.txt"
    cmd = [sys.executable, str(ROOT / t["script"])] + [a for a in t.get("args", "").split() if a]
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=TIMEOUT)
        text = (p.stdout or "") + ("\n[stderr]\n" + p.stderr if p.stderr else "")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        text, rc = "TIMEOUT", -9
    except Exception as e:
        text, rc = f"EXC {e}", -1
    out.write_text(text)
    vline = ""
    for line in text.splitlines():
        if VERDICT_RE.search(line):
            vline = line.strip()[:400]
            break
    h["fields"]["last_run"] = f"{TODAY} (auto rc={rc})"
    if rc == 0:
        h["fields"]["status"] = "RAN"
        h["fields"]["verdict"] = f"(auto, awaiting officer confirmation) {vline or 'no verdict line'} | out={out.relative_to(ROOT)}"
    else:
        h["fields"]["verdict"] = f"(auto-run FAILED rc={rc}; stays OPEN) out={out.relative_to(ROOT)}"
    return rc, vline


def main():
    pre, holes = parse()
    wall = wall_days()
    notes = []
    for h in holes:
        if test_spec(h).get("engine") == "oos":
            r = grade_oos(h, wall)
            if r:
                notes.append(r)
    picks = []
    for h in holes:
        if h["fields"].get("status") != "OPEN":
            continue
        ok, why = runnable(h)
        if ok:
            picks.append(h)
        if len(picks) >= N:
            break
    ran = []
    for h in picks:
        if DRY:
            ran.append(f"{h['id']} DRY-SELECTED ({test_spec(h)['script']})")
        else:
            rc, v = run_hole(h)
            ran.append(f"{h['id']} rc={rc} {v[:80]}")
    counts = {}
    for h in holes:
        counts[h["fields"].get("status", "?")] = counts.get(h["fields"].get("status", "?"), 0) + 1
    if not DRY:
        HOLES.write_text(render(pre, holes))
    line = f"- {NOW.strftime('%Y-%m-%d %H:%M')} | {'DRY ' if DRY else ''}picked={[h['id'] for h in picks]} | ran={ran} | oos={notes} | counts={counts}"
    if not LOG.exists():
        LOG.write_text("# HOLES SWEEP LOG (append-only; one line per nightly run)\n\n")
    with LOG.open("a") as f:
        f.write(line + "\n")
    top_open = [{"id": h["id"], "title": h["title"], "owner": h["fields"].get("owner", "")}
                for h in holes if h["fields"].get("status") in ("OPEN", "RUNNING")][:5]
    latest_v = [{"id": h["id"], "title": h["title"], "status": h["fields"].get("status"),
                 "last_run": h["fields"].get("last_run", ""), "verdict": h["fields"].get("verdict", "")[:300]}
                for h in sorted(holes, key=lambda x: x["fields"].get("last_run", ""), reverse=True)
                if h["fields"].get("status") in ("VERDICT", "RAN", "REFUTED")][:5]
    LATEST.write_text(json.dumps({"run_at": NOW.isoformat(timespec="minutes"), "dry": DRY, "counts": counts,
                                  "picked": [h["id"] for h in picks], "ran": ran, "oos": notes,
                                  "top_open": top_open, "latest_verdicts": latest_v, "file": "data/holes/HOLES.md"}, indent=1))
    print(line)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            with LOG.open("a") as f:
                f.write(f"- {NOW.strftime('%Y-%m-%d %H:%M')} | SWEEP CRASHED: {traceback.format_exc().splitlines()[-1]}\n")
        except Exception:
            pass
        sys.exit(0)  # fail-soft
