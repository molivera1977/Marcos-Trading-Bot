"""#102 Webull singleton rig (Marcos 7/24, the 429 shitshow). Executes the REAL _make_data_client
from screener_app.py (AST-extracted — no Flask import), with a mocked build + fake clock, so we can
COUNT builds without hitting Webull. Proves: N calls = ONE build (the 429 fix), TTL refresh, thread
safety, build-failure backoff, and keep-serving-old-client on a failed refresh. Instant-revert pin."""
import sys, ast, pathlib, threading, time as _rt
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "screener_app.py").read_text()
_fn = next(n for n in ast.walk(ast.parse(SRC))
           if isinstance(n, ast.FunctionDef) and n.name == "_make_data_client")

PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

class FakeTime:
    def __init__(s): s.t = 1000.0
    def time(s): return s.t

def make_ns(singleton=True, ttl=120, build=lambda: "CLIENT"):
    ft = FakeTime(); builds = {"n": 0}
    def _b():
        builds["n"] += 1
        return build()
    ns = {"_DC_SINGLETON": singleton, "_DC_TTL_SECS": ttl,
          "_dc_cache": {"client": None, "built": 0.0, "next_try": 0.0},
          "_dc_lock": threading.Lock(), "_build_data_client": _b, "time": ft}
    exec(compile(ast.Module(body=[_fn], type_ignores=[]), "screener_app.py", "exec"), ns)
    return ns, ft, builds

# T1 — THE FIX: 50 calls = ONE build, same object every time
ns, ft, builds = make_ns()
objs = [ns["_make_data_client"]() for _ in range(50)]
check("T1 50 requests → ONE build (no per-request token re-verify = 429 killed)", builds["n"] == 1, f"builds={builds['n']}")
check("T1b all 50 return the SAME reused client", all(o is objs[0] for o in objs))

# T2 — instant revert: flag off → build every call
ns, ft, builds = make_ns(singleton=False)
[ns["_make_data_client"]() for _ in range(5)]
check("T2 WEBULL_CLIENT_SINGLETON=0 → original build-every-call behavior", builds["n"] == 5, f"builds={builds['n']}")

# T3 — TTL freshness refresh
ns, ft, builds = make_ns(ttl=120)
ns["_make_data_client"]();          ft.t = 1000 + 119; ns["_make_data_client"]()
check("T3 within TTL → reuse, no rebuild", builds["n"] == 1, f"builds={builds['n']}")
ft.t = 1000 + 121; ns["_make_data_client"]()
check("T3b past TTL → exactly one refresh", builds["n"] == 2, f"builds={builds['n']}")

# T4 — thread-safety: 20 concurrent first-calls → ONE build
ns, ft, builds = make_ns()
def _slow():
    builds["n"] += 1; _rt.sleep(0.03); return "CLIENT"
ns["_build_data_client"] = _slow
outs = []
ths = [threading.Thread(target=lambda: outs.append(ns["_make_data_client"]())) for _ in range(20)]
[t.start() for t in ths]; [t.join() for t in ths]
check("T4 20 concurrent calls → ONE build (lock holds)", builds["n"] == 1, f"builds={builds['n']}")

# T5 — build failure with no client: backoff, no rebuild storm
ns, ft, builds = make_ns(build=lambda: None)
r1 = ns["_make_data_client"](); r2 = ns["_make_data_client"]()
check("T5 failing build (no client) → None, and does NOT storm rebuilds", r1 is None and r2 is None and builds["n"] == 1, f"builds={builds['n']}")
ft.t = 1000 + 21; ns["_make_data_client"]()
check("T5b retries only after the backoff window", builds["n"] == 2, f"builds={builds['n']}")

# T6 — failed REFRESH keeps serving the old (token still valid 14d)
_seq = ["CLIENT", None]; _i = {"k": 0}
def _flaky():
    v = _seq[min(_i["k"], 1)]; _i["k"] += 1; return v
ns, ft, builds = make_ns(build=_flaky)
o1 = ns["_make_data_client"](); ft.t = 1000 + 121; o2 = ns["_make_data_client"]()
check("T6 failed refresh → keep serving the still-valid old client (no drop to None)", o1 == "CLIENT" and o2 == "CLIENT")

# SOURCE PINS
check("P1 token-check params preserved on the build path", "token_check_duration_seconds=60" in SRC and "token_check_interval_seconds=5" in SRC)
check("P2 singleton default-ON, flippable OFF", 'WEBULL_CLIENT_SINGLETON", "1"' in SRC)
check("P3 call sites unchanged (still call _make_data_client())", SRC.count("_make_data_client()") >= 4)
check("P4 build path split into _build_data_client (fast-path reuses, never rebuilds)", "def _build_data_client" in SRC)

print(f"\n{'='*60}\n#102 WEBULL SINGLETON RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL: print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
