#!/usr/bin/env python3
"""
RIG GATE 29 — THE READ-BUDGET MATERIAL-CHANGE GATE (8/20)

Marcos: "i dont mind rereads but if we are printing the same info then what's the point.
Come up with a solution, reasoning, and build and i will have fable audit it."

MEASURED FIRST (8/20 reader log, 52 parsed rereads): 12 (23%) returned a map IDENTICAL to
the previous read of the same name; 43 (83%) returned SKIP; 2 of 23 reread markers were
followed by a fill within 30 min. Specimens: JZ v2-v7 = 2.62 six times (all near_map_exhaust);
HUIZ v6-v13 = eight reads wobbling 2.29/2.25/2.29/2.22/2.11/2.22/2.22.

TWO DEFECTS THIS CLOSES
  D1 SELF-DEFEATING DEDUP. Every trigger dedups on the MAP VERSION, and a reread POSTS A NEW
     MAP — so a read invalidates the very key that was meant to suppress the next one
     (`_nme_fired[tk] != lastT`). The new gate keys on the WORLD (price / day high / external
     map edits) as of OUR last read, never on our own output.
  D2 THE GUARD THAT LIED. The stale-chart check printed "no budget burned" while sitting
     AFTER client.messages.create() — the call was already paid; it only stopped the POST.
     Moved above both the render and the call.

PINS (the gate is EXECUTED here, not grepped — gate 28's string-match version shipped green
while a swallowed NameError kept its branch from ever running)
  B1  ordering: both guards are physically ABOVE the billed messages.create in reread_one
  B2  first read of a name is always news (nothing to compare)
  B3  identical map + flat tape  -> NOT news (the JZ/HUIZ class)
  B4  price move >= RR_NEWS_PX_PCT -> news
  B5  new high beyond RR_NEWS_HI_PCT -> news  (the runner case: PCLA 9.13 -> 12.87)
  B6  externally-edited map -> news (Kev sheet / another poster moved it)
  B7  FAIL-OPEN: unknown tape (0/0) -> news; an unreadable store must never mute reads
  B8  the fingerprint is order-insensitive and None-safe
  B9  kill switch RR_MATERIAL_GATE=0 present; thresholds env-tunable
  B10 the recorded fingerprint is of the map WE POSTED (rd), on the tape we read it at
"""
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "newcomer_vision_reader.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


# ── B1: ordering, measured by byte offset in the real file ──
i_news = SRC.find("SKIP no-news")
i_stale = SRC.find("skipping BEFORE the call")
i_call = SRC.find("msg = client.messages.create(model=MODEL, max_tokens=1100")
check("B1 both guards sit ABOVE the billed vision call in reread_one",
      0 < i_news < i_call and 0 < i_stale < i_call)
check("B1b the old post-call duplicate is gone (single stale-chart site)",
      SRC.count("STALE CHART") == 1)
check("B10 fingerprint records the POSTED map (rd) on the read's tape",
      '_rr_seen[ticker] = {"fp": _map_fp(rd), "px": (_live or 0.0), "hi": (_dayhi or 0.0)' in SRC)
check("B9 kill switch + env-tunable thresholds",
      'RR_MATERIAL_GATE = os.environ.get("RR_MATERIAL_GATE", "1") == "1"' in SRC
      and 'RR_NEWS_PX_PCT   = float(os.environ.get("RR_NEWS_PX_PCT", "3.0"))' in SRC
      and 'RR_NEWS_HI_PCT   = float(os.environ.get("RR_NEWS_HI_PCT", "0.5"))' in SRC)

# ── lift the pure functions and EXECUTE them ──
ns = {"os": __import__("os")}
for fn in ("_map_fp", "_reread_is_news"):
    a = SRC.find(f"\ndef {fn}(")
    b = SRC.find("\ndef ", a + 1)
    exec(compile(SRC[a:b], fn, "exec"), ns)
ns["RR_NEWS_PX_PCT"] = 3.0     # the shipped defaults, exercised as shipped
ns["RR_NEWS_HI_PCT"] = 0.5
ns["_rr_seen"] = {}
fp, is_news = ns["_map_fp"], ns["_reread_is_news"]

MAP = {"break": 2.62, "stop": 2.40, "targets": [2.76, 2.82]}
RAW = {"break_level": 2.62, "stop_level": 2.40, "targets": [2.76, 2.82]}   # the model's shape
check("B8 fingerprint order-insensitive + None-safe",
      fp(MAP) == fp({"break": 2.62, "stop": 2.40, "targets": [2.82, 2.76]})
      and fp({"break": None, "stop": None, "targets": None}) == (None, None, ()))
# FABLE AUDIT (8/20): rd carries break_level/stop_level; the stored map carries break/stop
# (post_level :542). The first build fingerprinted rd on the stored keys -> (None,None,...)
# on every record -> "map_changed_externally" on every compare -> the gate NEVER saved a
# read while showing green. This pin executes the exact cross-shape compare that failed.
check("B8b RAW read shape and STORED map shape fingerprint IDENTICALLY (the audit bug)",
      fp(RAW) == fp(MAP))
check("B8c an actually-different map still differs across shapes",
      fp({"break_level": 2.70, "stop_level": 2.40, "targets": [2.76, 2.82]}) != fp(MAP))

check("B2 first read of a name is always news",
      is_news("JZ", MAP, 2.60, 2.70) == (True, "first_read"))

# seed: our last read of JZ posted MAP while price 2.60 / high 2.70  (the JZ v2 moment)
ns["_rr_seen"]["JZ"] = {"fp": fp(MAP), "px": 2.60, "hi": 2.70, "t": 0}
check("B3 identical map + flat tape -> NOT news (the JZ v3-v7 class, 6 reads of '2.62')",
      is_news("JZ", MAP, 2.61, 2.70) == (False, "no_material_change"))
check("B4 a >=3.0% price move IS news (2.60 -> 2.69)",
      is_news("JZ", MAP, 2.69, 2.70)[1] == "price_moved")
check("B4b a 2% move is NOT news at the shipped threshold",
      is_news("JZ", MAP, 2.653, 2.70)[1] == "no_material_change")
check("B5 a new high beyond 0.5% IS news (the PCLA runner case)",
      is_news("JZ", MAP, 2.60, 2.72) == (True, "new_high"))
check("B6 an externally-edited map IS news",
      is_news("JZ", dict(MAP, targets=[2.90]), 2.60, 2.70) == (True, "map_changed_externally"))
check("B7 FAIL-OPEN on unknown tape (store down -> still read)",
      is_news("JZ", MAP, 0.0, 0.0) == (True, "tape_unknown"))
check("B7b downward move of >=3.0% is also news (symmetric, not just rallies)",
      is_news("JZ", MAP, 2.51, 2.70)[1] == "price_moved")

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
