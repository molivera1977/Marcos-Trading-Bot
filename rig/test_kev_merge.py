"""Kev-sheet MERGE-ONLY rig (Marcos 7/24, after the 09:25 open-window wipe: "we need to be able
to update Kev's list every morning so the code HAS to be able to handle that").
FUNCTIONAL: executes the REAL _merge_kev_levels from screener_app.py (AST-extracted, no Flask
import). Red-test anchor = this morning's exact disaster payload must now be harmless."""
import sys, ast, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "screener_app.py").read_text()

# ── extract the real function (no import of the Flask app) ────────────────────
tree = ast.parse(SRC)
fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
           and n.name == "_merge_kev_levels"), None)
assert fn is not None, "_merge_kev_levels not found in screener_app.py"
ns = {}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "screener_app.py", "exec"), ns)
merge = ns["_merge_kev_levels"]

PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

def store36():
    """Approximation of the 7/24 09:25 store: 35 vision reads + nothing else."""
    s = {f"T{i}": {"break": float(i), "src": "vision"} for i in range(1, 36)}
    s["LGCL"] = {"break": 1.9, "src": "vision", "note": "reader read"}
    return s

# ── R1: THE DISASTER PAYLOAD REPLAY — subset write can no longer wipe ─────────
s = store36()
out = merge(s, {"LGCL": {"break": 2.0, "src": "kev", "targets": [2.47, 3.0]}})
check("R1 subset write keeps ALL unmentioned names (36 stay 36)", len(out) == 36, f"got {len(out)}")
check("R1b the mentioned ticker IS updated", out["LGCL"]["break"] == 2.0 and out["LGCL"]["src"] == "kev")
check("R1c original store object untouched (pure function)", s["LGCL"]["break"] == 1.9)

# ── R2: server-side Kev protection — vision write CANNOT clobber src=kev ──────
s2 = {"LGCL": {"break": 2.0, "src": "kev", "targets": [2.47, 3.0]}}
out2 = merge(s2, {"LGCL": {"break": 1.85, "src": "vision", "note": "re-read"}})
check("R2 kev top-level survives a vision write", out2["LGCL"]["break"] == 2.0 and out2["LGCL"]["src"] == "kev")
check("R2b vision read preserved as vision_shadow", out2["LGCL"].get("vision_shadow", {}).get("break") == 1.85)

# ── R3: kev-over-kev replaces (the morning-update path itself) ────────────────
out3 = merge(s2, {"LGCL": {"break": 2.10, "src": "kev"}})
check("R3 kev write replaces kev entry (morning updates work)", out3["LGCL"]["break"] == 2.10)

# ── R4: explicit removal is the ONLY deletion path ────────────────────────────
out4 = merge(store36(), {}, remove=["T1", "t2 "])   # case/space-insensitive
check("R4 levels_remove deletes exactly the named", len(out4) == 34 and "T1" not in out4 and "T2" not in out4)
out4b = merge(store36(), {})
check("R4b empty write deletes NOTHING", len(out4b) == 36)

# ── R5: reader full-dict flow (GET->set->POST) with a clobbered kev name ──────
s5 = store36(); s5["LGCL"] = {"break": 2.0, "src": "kev"}
reader_post = dict(s5); reader_post["LGCL"] = {"break": 1.85, "src": "vision"}  # reader clobbers locally
out5 = merge(s5, reader_post)
check("R5 reader full-dict post: kev survives, all 36 names intact",
      len(out5) == 36 and out5["LGCL"]["src"] == "kev"
      and out5["LGCL"]["vision_shadow"]["break"] == 1.85)

# ── R6: junk-tolerance ────────────────────────────────────────────────────────
out6 = merge(store36(), {"BAD": "not-a-dict", " lgcl ": {"break": 2.2, "src": "kev"}})
check("R6 non-dict entries ignored; ticker keys normalized", "BAD" not in out6 and out6["LGCL"]["break"] == 2.2)

# ── ROUTE PINS: handler actually uses the merge (not the old wholesale replace) ─
check("P1 route: levels go through _merge_kev_levels", "_merge_kev_levels(cur" in SRC)
check("P2 route: levels_remove wired", 'd.get("levels_remove")' in SRC)
check("P3 old wholesale replace is GONE", '_kev_wl.setdefault("_levels", {})[date] = d["levels"]' not in SRC)

print(f"\n{'='*60}\nKEV MERGE-ONLY RIG: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", *FAIL, sep="\n  ")
sys.exit(1 if FAIL else 0)
