#!/usr/bin/env python3
"""NIGHTLY BOOK VERIFICATION (Marcos 8/13: "make sure this nightly verification is done nightly").
Verifies TODAY's trades fill-by-fill against 10s tape; appends a dated section to
data/history/VERIFIED_BOOK.md and updates the nightly log. Post-8/13 fix, ANY fiction fill is a
REGRESSION ALARM (exit 2 + loud line). Runs from launchd at 22:45 ET nightly."""
import json, urllib.request, pathlib, datetime, sys
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

if res["fiction"]:
    print("🚨 REGRESSION: fictional fill(s) AFTER the 8/13 fix — investigate before next session")
    sys.exit(2)
sys.exit(0)
