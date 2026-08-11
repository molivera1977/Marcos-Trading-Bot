"""CROWN + FRESHNESS EOD REPORT (8/8, #36 remainder + Crown Steward's daily scorecard).
Runs inside the dashboard as a daemon thread (kev_sweep pattern): weekdays ~16:20 ET, reads the
day's DURABLE records only (decisions JSONL + trades + bars store on /data) and posts ONE
crown_eod_report decision row per crown + a freshness_eod summary row. No engine pricing here —
the daily row carries the OFFERED move (post-crown session high vs crown-time price from the
day's stored ~ALP10S bars), CAPTURED dollars (that ticker's closed trades), REFUSALS count (gate
rejects post-crown), and the day's worst freshness breach. The Steward's weekly table prices the
refusals through the engine separately. Fail-soft everywhere. Kill: CROWN_EOD_REPORT=0."""
import os, json, time, threading, datetime, pathlib

def start(app_globals, run_now_day=None):
    """run_now_day: test hook — run the report synchronously for that day and return (no thread)."""
    if os.environ.get("CROWN_EOD_REPORT", "1") != "1":
        return
    ET = app_globals["EASTERN"]
    DECISIONS_DIR = app_globals["DECISIONS_DIR"]
    TRADES_FILE = app_globals["TRADES_FILE"]
    log_decision = app_globals["_log_decision_row"]

    def _tsec(t):
        try:
            hh, mm, ss = int(t[0:2]), int(t[3:5]), int(t[6:8])
            if t.endswith("PM") and hh != 12: hh += 12
            if t.endswith("AM") and hh == 12: hh = 0
            return hh * 3600 + mm * 60 + ss
        except Exception:
            return 0

    def _run(day):
        fp = DECISIONS_DIR / f"decisions-{day}.jsonl"
        if not fp.exists():
            return
        rows = []
        for line in fp.read_text().splitlines():
            try: rows.append(json.loads(line))
            except Exception: continue
        crowns = {}
        for r in rows:
            if r.get("status") == "leader_armed" and r.get("ticker"):
                crowns.setdefault(r["ticker"], _tsec(str(r.get("time") or "")))
        breaches = {}
        for r in rows:
            if r.get("status") == "freshness_breach" and r.get("ticker"):
                b = breaches.setdefault(r["ticker"], {"n": 0, "worst_age": 0, "worst_dist": 0})
                b["n"] += 1
                b["worst_age"] = max(b["worst_age"], float(r.get("map_age_min") or 0))
                b["worst_dist"] = max(b["worst_dist"], float(r.get("map_dist_pct") or 0))
        try:
            trades = [t for t in json.loads(TRADES_FILE.read_text()).get("trades", [])
                      if t.get("date") == day]
        except Exception:
            trades = []
        bars_dir = pathlib.Path("/data/bars") / day
        for tk, csec in sorted(crowns.items()):
            offered = None
            try:
                b = json.loads((bars_dir / f"{tk}~ALP10S.json").read_text())
                post = [x for x in b if True]
                px_at = None; hi = 0.0
                for x in post:
                    ts = str(x.get("time"))[11:19]
                    sec = (int(ts[:2]) - 4) * 3600 + int(ts[3:5]) * 60 + int(ts[6:8])
                    h = float(x.get("high") or 0); c = float(x.get("close") or 0)
                    if sec >= csec:
                        if px_at is None: px_at = c or h
                        hi = max(hi, h)
                if px_at:
                    offered = round((hi - px_at) / px_at * 100, 1)
            except Exception:
                pass
            captured = round(sum(float(t.get("pnl") or 0) for t in trades if t.get("ticker") == tk), 2)
            n_tr = sum(1 for t in trades if t.get("ticker") == tk)
            refusals = sum(1 for r in rows if r.get("ticker") == tk
                           and str(r.get("status", "")).endswith("_reject")
                           and _tsec(str(r.get("time") or "")) >= csec)
            br = breaches.get(tk) or {}
            log_decision({"ticker": tk, "status": "crown_eod_report",
                          "offered_pct": offered, "captured_usd": captured, "trades": n_tr,
                          "refusals_post_crown": refusals,
                          "freshness_breaches": br.get("n", 0),
                          "worst_map_age_min": br.get("worst_age"),
                          "worst_map_dist_pct": br.get("worst_dist")})
            print(f"[crown-eod] {tk}: offered {offered}% captured ${captured} "
                  f"({n_tr} trades, {refusals} refusals, {br.get('n',0)} breaches)", flush=True)
        log_decision({"ticker": "_EOD", "status": "freshness_eod",
                      "crowns": len(crowns), "breach_names": len(breaches),
                      "total_breaches": sum(b["n"] for b in breaches.values())})

    if run_now_day:
        _run(run_now_day)
        return

    def _loop():
        done = set()
        while True:
            try:
                now = datetime.datetime.now(ET)
                day = now.strftime("%Y-%m-%d")
                if now.weekday() < 5 and now.strftime("%H:%M") >= "16:20" and day not in done:
                    done.add(day)
                    _run(day)
            except Exception as e:
                print(f"[crown-eod] loop error: {e}", flush=True)
            time.sleep(120)
    threading.Thread(target=_loop, daemon=True, name="crown_eod").start()
    print("[crown-eod] daily crown/freshness report armed (16:20 ET weekdays)", flush=True)
