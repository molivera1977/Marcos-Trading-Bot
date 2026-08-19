#!/usr/bin/env python3
"""NIGHTLY BOOK VERIFICATION (Marcos 8/13: "make sure this nightly verification is done nightly").
Verifies TODAY's trades fill-by-fill against 10s tape; appends a dated section to
data/history/VERIFIED_BOOK.md and updates the nightly log. Post-8/13 fix, ANY fiction fill is a
REGRESSION ALARM (exit 2 + loud line). Runs from launchd at 22:45 ET nightly."""
import json, os, urllib.request, pathlib, datetime, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = datetime.timezone(datetime.timedelta(hours=-4))
DAY = datetime.datetime.now(ET).strftime("%Y-%m-%d")
def iso(s): return datetime.datetime.fromisoformat(str(s).replace("+0000","+00:00").replace("Z","+00:00"))
def bars(tk):
    # UNION of both feeds — the verified-book standard. First-feed-only falsely branded 3 fills
    # on the very first run (a fill can print on one feed's bars and not the other's).
    out = []
    for sfx in ("~10S","~ALP10S"):
        try:
            r = json.load(urllib.request.urlopen(f"{U}/api/bars?ticker={tk}{sfx}&date={DAY}", timeout=30))
            out += r.get("bars") or []
        except Exception: pass
    return out
# ORDER MATTERS (Marcos 8/18: "this nightly check should run before the nightly ledger
# check"). The ledger verification below grades fills against the book; if a stamped VWAP
# is wrong, every gate decision and study that reads those rows is already poisoned, so the
# data-integrity question must be answered FIRST. A ledger that reconciles cleanly against
# corrupt inputs is a false all-clear.
# ── 8/18 VWAP WATCHDOG (Marcos: "is there a program that can run to block these wrong vwap
# from coming back?" -> "fix them"). Re-derives every stamped session VWAP from raw 10s SIP tape
# and flags any that matches NEITHER session anchor. First run over the era: 60 BREACHES in 178
# graded rows — 52/112 hidden_entry, 3/3 kevseq, every one stamped ABOVE both anchors (the
# truncated-window signature); ignition 0/20, flat_top 0/15, vwap_reclaim 0/7 clean.
# It needs today's tape in data/universe/bars10s. That cache is NOT auto-maintained
# (harvester.py is a one-shot backfill), so the harvest is attempted first and its failure is
# reported rather than swallowed — a watchdog that silently grades zero rows is worse than none.
try:
    import subprocess as _vw_sp
    # 8/18: the harvest needs ALPACA_KEY/ALPACA_SECRET, which are NOT in the launchd env
    # (verified: the first wired run failed exactly there). They live in the Railway service, so
    # the harvest — and ONLY the harvest — runs under `railway run`, which injects them without
    # ever writing a secret to disk.
    # DELIBERATELY NOT wrapping the whole plist in `railway run`: that would make the ledger
    # verification below depend on Railway auth too, and a token hiccup would break a working
    # check to fix a broken one. This sub-step already fails gracefully and says so.
    _RW = os.path.expanduser("~/.railway/bin/railway")
    _hv_cmd = ([_RW, "run", "--service", "Marcos-Trading-Bot", sys.executable]
               if os.path.exists(_RW) else [sys.executable])
    _hv = _vw_sp.run(_hv_cmd + [str(ROOT / "data/universe/harvest_day.py"), DAY],
                     capture_output=True, text=True, timeout=1800, cwd=str(ROOT))
    if _hv.returncode != 0:
        print(f"⚠️  VWAP watchdog: harvest of {DAY} did not run "
              f"({(_hv.stderr or _hv.stdout).strip().splitlines()[-1:] or ['?']}). "
              "Rows without tape are UNAUDITED, not clean.")
    _va = _vw_sp.run([sys.executable, str(ROOT / "data/killtests/vwap_audit.py"), DAY],
                     capture_output=True, text=True, timeout=900)
    print(_va.stdout.rstrip())
    _vline = [l for l in _va.stdout.splitlines() if l.startswith("BREACHES:")]
    (ROOT / "data/history/nightly_verify.log").open("a").write(
        datetime.datetime.now(ET).isoformat()[:19] + " VWAP: " +
        (_vline or ["(no output)"])[0] + "\n")
    if _va.returncode == 1:
        print("🚨 VWAP BREACH: a stamped session VWAP matches NEITHER session anchor. Every "
              "study that reads those rows inherits the bad value — fix before trusting them.")
except Exception as _vwe:
    print(f"⚠️  VWAP watchdog did not run: {_vwe}")


tr = [t for t in (json.load(urllib.request.urlopen(U+"/api/trades", timeout=60)).get("trades") or [])
      if t.get("date") == DAY]
res = {"date": DAY, "n": len(tr), "fills_ok": 0, "fiction": [], "no_bars": [], "raw": 0.0}
for t in tr:
    res["raw"] += float(t.get("pnl") or 0)
    fills = [f for f in (t.get("partial_fills") or []) if isinstance(f,(list,tuple)) and len(f)>=2]
    if not fills: continue
    try: ets = iso(t["entry_ts_utc"])
    except Exception: res["no_bars"].append(t["ticker"]+":no_entry_ts"); continue
    B = bars(t["ticker"])
    if not B: res["no_bars"].append(t["ticker"]); continue
    for q, fp in fills:
        touched = any(iso(b["time"]) >= ets and float(b.get("high") or 0) >= float(fp)*0.999
                      for b in B if b.get("time"))
        if touched: res["fills_ok"] += 1
        else: res["fiction"].append({"ticker": t["ticker"], "qty": q, "px": fp})
md = ROOT/"data/history/VERIFIED_BOOK.md"
line = (f"\n## NIGHTLY {DAY}: {res['n']} trades raw ${res['raw']:+.2f} | fills ok {res['fills_ok']} | "
        f"FICTION {len(res['fiction'])} {res['fiction'] or ''} | no-bars {res['no_bars'] or 'none'}\n")
md.open("a").write(line)
(ROOT/"data/history/nightly_verify.log").open("a").write(
    datetime.datetime.now(ET).isoformat()[:19] + line)
print(line.strip())
# ── 8/17 ENFORCEMENT GATE 3: re-verify the CLAIMS LEDGER every night ────────────────────────
# data/audits/CLAIMS.md holds every fact about the machine I have previously stated WRONG, each
# with the command that reproduces it. Running it here means a drifted fact surfaces the night
# it drifts, instead of the next time I quote it from memory. Appended to the EXISTING nightly
# job on purpose — no new launchd agent was created (that needs Marcos's say-so).
# Read-only (greps). Non-fatal: it reports, it never blocks the book verification.
try:
    import subprocess as _cl_sp
    _cl = _cl_sp.run([sys.executable, str(ROOT / "data/audits/verify_claims.py")],
                     capture_output=True, text=True, timeout=300)
    print(_cl.stdout.rstrip())
    (ROOT / "data/history/nightly_verify.log").open("a").write(
        datetime.datetime.now(ET).isoformat()[:19] + " CLAIMS: " +
        (_cl.stdout.strip().splitlines() or ["(no output)"])[-1] + "\n")
    if _cl.returncode != 0:
        print("🚨 CLAIMS LEDGER NOT VERIFIED — a stated fact no longer reproduces. "
              "Append a corrected row to data/audits/CLAIMS.md (never edit the old one).")
except Exception as _cle:
    print(f"⚠️  claims verifier did not run: {_cle}")

# ── 8/17 ENFORCEMENT GATE 7: reconcile SETTLED DECISIONS against the live machine ───────────
# data/audits/DECISIONS.md restates every settled ruling as a command. 8/17 found four rulings
# that had quietly stopped being true (kev_shadow unread since 8/12, the chart-gate bypass list
# stale, the refuted momentum scalar still vetoing kevseq, #57 asserted-shipped but queued).
# Running it here surfaces a drift the night it happens instead of the next time it costs money.
# Appended to the EXISTING nightly job on purpose — no new launchd agent (that needs Marcos).
# Read-only (greps + one GET). Non-fatal: it reports, it never blocks the book verification.
try:
    import subprocess as _dc_sp
    _dc = _dc_sp.run([sys.executable, str(ROOT / "data/audits/reconcile_decisions.py")],
                     capture_output=True, text=True, timeout=300)
    print(_dc.stdout.rstrip())
    (ROOT / "data/history/nightly_verify.log").open("a").write(
        datetime.datetime.now(ET).isoformat()[:19] + " DECISIONS: " +
        (_dc.stdout.strip().splitlines() or ["(no output)"])[0] + "\n")
    if "DRIFTED" in _dc.stdout and "0 DRIFTED" not in _dc.stdout:
        print("🚨 A SETTLED DECISION HAS DRIFTED — restore the behaviour, or take a NEW "
              "decision to Marcos. Never let the row quietly rot.")
except Exception as _dce:
    print(f"⚠️  decision reconciler did not run: {_dce}")

if res["fiction"]:
    print("🚨 REGRESSION: fictional fill(s) AFTER the 8/13 fix — investigate before next session")
    sys.exit(2)
sys.exit(0)
