#!/usr/bin/env python3
"""
GATE 18 — LANE RANK IS DATA, AND ONE TICKER TAKES ONE POSITION (8/19)

Marcos: "i want my best lanes and best tested lanes first" / "do it the right way and not some
fucked up add on" / "right now i dont trust the other lanes like these three. I will work on
those one at a time."

BEFORE: a lane's turn at capital was decided by NESTING DEPTH in the scan loop — the order the
lanes happened to be written in. Measured 8/18: the live order sat at p18 of a 200-shuffle null
(82% of RANDOM orders beat it), with `hidden` (wall FAILED, -$10.21/tr) ahead of `ema9x90` (wall
PASSED, p=0.0005).

AFTER: lanes PROPOSE into `breakouts`; ONE arbiter disposes. Rank is a list, so promoting a lane
as Marcos reviews it is an edit to data — never a restructure.

ALSO FIXED HERE: CDTG 8/18 14:16:43, where kevseq AND ma_pullback filled the same name in the
same second (-$59.63, capital split into $225 and $93 clips). One-position-per-ticker is enforced
at the same arbiter, so it holds for every lane pair at once.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "marcos_trading_bot.py")).read()
FAILS = []
def chk(c, label, detail=""):
    print(f"  {'PASS' if c else 'FAIL'}  {label}" + (f"   {detail}" if detail and not c else ""))
    if not c: FAILS.append(label)

print("GATE 18 — lane rank is data; one ticker, one position")
print("=" * 76)
m = re.search(r'LANE_RANK = \[s\.strip\(\) for s in os\.environ\.get\(\s*\n?\s*"LANE_RANK",\s*"([^"]+)"', SRC)
chk(bool(m), "A1 LANE_RANK exists and is env-overridable")
order = [x.strip() for x in m.group(1).split(",")] if m else []
chk(order[:3] == ["ignition", "ema9x90", "ma_pullback"],
    "A2 Marcos's order: ignition, ema9x90, ma_pullback", f"got {order[:3]}")
r = re.search(r'LANE_RANK_SORT = os\.environ\.get\(\s*"LANE_RANK_SORT",\s*"(\d)"\s*\)', SRC)
chk(bool(r) and r.group(1) == "1", "A3 rank sort defaults ON")
chk("def _lane_rank(lane):" in SRC, "B1 rank lookup exists")
chk("return len(LANE_RANK) + 1" in SRC,
    "B2 UNRANKED lanes sort AFTER every ranked one, order otherwise unchanged "
    "(Marcos reviews them one at a time; none are demoted below each other)")
chk("return (_lane_rank(b[3]), _mvk, _tier)" in SRC,
    "C1 rank is PRIMARY in the arbiter; Move % still decides between names inside a rank")
chk(SRC.index("if LANE_RANK_SORT:") < SRC.index("if KEV_TIER_FIRST:"),
    "C2 rank short-circuits BEFORE the expectancy sort Marcos told me to drop")
o = re.search(r'ONE_PER_TICKER = os\.environ\.get\(\s*"ONE_PER_TICKER",\s*"(\d)"\s*\)', SRC)
chk(bool(o) and o.group(1) == "1", "D1 one-position-per-ticker exists and defaults ON")
chk("breakouts.sort(key=_entry_priority)" in SRC and
    SRC.index("breakouts.sort(key=_entry_priority)") < SRC.index("if ONE_PER_TICKER:"),
    "D2 SORT FIRST, then keep one per ticker — so RANK decides the winner, not arrival order")
chk('"lane_outranked"' in SRC, "D3 the losing lane is LOGGED, never silently dropped")

# the real CDTG pair, through the real rank function
g = {"os": os}
exec(compile(SRC[SRC.index("LANE_RANK = ["):SRC.index("LANE_EXPECTANCY = {")], "<r>", "exec"), g)
rank = g["_lane_rank"]
cand = [("CDTG", 7.76, 0, "kevseq", {}), ("CDTG", 7.78, 0, "ma_pullback", {})]
cand.sort(key=lambda b: (rank(b[3]), 0, 0))
seen, kept = set(), []
for b in cand:
    if b[0] in seen: continue
    seen.add(b[0]); kept.append(b)
chk(len(kept) == 1, "E1 the CDTG double-fill resolves to ONE position", f"got {len(kept)}")
chk(kept and kept[0][3] == "ma_pullback",
    "E2 the higher-ranked lane wins the name", f"got {kept[0][3] if kept else None}")
chk(rank("ignition") < rank("ema9x90") < rank("ma_pullback") < rank("kevseq"),
    "E3 rank order holds end to end")
print("=" * 76)
if FAILS:
    print(f"GATE 18 FAILED ({len(FAILS)}): " + "; ".join(FAILS)); sys.exit(1)
print("GATE 18 PASSED"); sys.exit(0)
