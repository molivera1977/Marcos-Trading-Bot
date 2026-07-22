"""Reader source pins — #84 re-read probe isolation (7/22) + #77 ledger pass-through.
Source-level pins only (the reader is API/LLM-bound; functional runs live)."""
import sys, pathlib
SRC = (pathlib.Path(__file__).resolve().parent.parent / "newcomer_vision_reader.py").read_text()
PASS, FAIL = [], []
def check(n, cond):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n)

check("R1 #84 retry helper exists and reread uses it",
      "def _get_retry(" in SRC and SRC.count("_get_retry(") >= 3)
check("R2 #84 sections isolated: passive/marker/fire each have their own except",
      "passive-section error" in SRC and "marker-section error" in SRC and "fire error" in SRC)
check("R3 #84 marker pull shrunk to limit=1500 w/ retry (active_newcomers keeps its full-day 8000 — it fails soft)",
      "_get_retry(f\"{U}/api/decisions_archive?date={DAY}&limit=1500\")" in SRC
      and SRC.count("limit=8000") == 1)
check("R4 #84 per-name bar failure continues the sweep (no cycle kill)",
      "one name's bars failing must not kill the sweep" in SRC)
check("R5 #77 ledger pass-through intact (read_version/trigger/read_at/history)",
      '"read_version", "trigger", "read_at", "history"' in SRC)
check("R6 verdict enum unchanged (TAKE|MARGINAL|SKIP)", "TAKE" in SRC and "MARGINAL" in SRC)
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL: print("RED:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
