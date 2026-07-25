"""Reader-on-Alpaca charts rig (7/25, Marcos: "if Alpaca is doing the rereads, why not do all
of the reads?"). FUNCTIONAL: capture /daily + /min1 routes (auth, sym validation, TTL cache) +
reader adapters (session labeling, schema, Webull FALLBACK when env absent or capture fails)."""
import sys, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# ── capture side ──
import alpaca_capture as cap
calls = {"n": 0}
class _FakeResp:
    status_code = 200
    def json(self):
        return {"bars": [{"t": "2026-07-24T13:30:00Z", "o": 1, "h": 2, "l": 0.9, "c": 1.5, "v": 100}]}
cap.requests.get = lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1), _FakeResp())[1]

check("C1 unauth -> 401", cap._hot_route("/daily", {"sym": "AAA"}, False)[0] == 401)
check("C2 bad sym -> 400", cap._hot_route("/daily", {"sym": "bad sym!"}, True)[0] == 400)
code, payload = cap._hot_route("/daily", {"sym": "AAA"}, True)
check("C3 /daily 200 + bars", code == 200 and payload.get("bars"))
n_before = calls["n"]
cap._hot_route("/daily", {"sym": "AAA"}, True)
check("C4 TTL cache (2nd call = no upstream)", calls["n"] == n_before)
code2, _ = cap._hot_route("/min1", {"sym": "AAA"}, True)
check("C5 /min1 200", code2 == 200)
check("C6 /hot + /health unchanged", cap._hot_route("/health", {}, True)[0] == 200)

# ── reader side ──
os.environ.pop("ALP_CAPTURE_URL", None); os.environ.pop("HOT_SECRET", None)
os.environ.setdefault("NEWCOMER_DAY", "2026-07-24")
import newcomer_vision_reader as R

# R1: no env -> _cap_get None -> _min1 falls back to Webull path (_get sentinel)
R.CAP_URL = ""; R.CAP_SECRET = ""
sentinel = {"bars": [{"time": "2026-07-24 09:31", "session": "RTH", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]}
R._get = lambda url, timeout=45: sentinel if "minute_ext" in url else {"bars": [{"date": "2026-07-23", "open": 1, "high": 1, "low": 1, "close": 1}]}
check("R1 no env -> Webull fallback (min1)", R._min1("AAA") == sentinel["bars"])
check("R2 no env -> Webull fallback (daily)", R._daily_rows("AAA")[0]["date"] == "2026-07-23")

# R3: capture path active -> session labeling from ET clock
R.CAP_URL = "http://cap"; R.CAP_SECRET = "s"
fake_min1 = [
    {"t": "2026-07-24T12:00:00Z", "o": 1, "h": 2, "l": 0.9, "c": 1.5, "v": 5},   # 08:00 ET = PRE
    {"t": "2026-07-24T14:00:00Z", "o": 1, "h": 2, "l": 0.9, "c": 1.5, "v": 5},   # 10:00 ET = RTH
    {"t": "2026-07-24T21:00:00Z", "o": 1, "h": 2, "l": 0.9, "c": 1.5, "v": 5},   # 17:00 ET = ATH
] * 4
R._cap_get = lambda path, sym: fake_min1 if path == "/min1" else [{"t": "2026-07-23T04:00:00Z", "o": 1, "h": 2, "l": 0.9, "c": 1.5}] * 3
rows = R._alp_min1_rows("AAA")
check("R3 min1 rows produced", rows is not None and len(rows) == 12)
sess = {r["session"] for r in rows}
check("R4 session labels PRE/RTH/ATH", sess == {"PRE", "RTH", "ATH"})
check("R5 minute_ext schema keys", set(rows[0].keys()) == {"time", "session", "open", "high", "low", "close", "volume"})
check("R6 daily conversion {date,open,...}", R._daily_rows("AAA")[0]["date"] == "2026-07-23")

# R7: capture returns junk -> fallback still safe
R._cap_get = lambda path, sym: None
check("R7 capture fail -> fallback (min1)", R._min1("AAA") == sentinel["bars"])

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
