#!/usr/bin/env python3
"""
RIG GATE 32 — THE REAL-COST ROSTER (8/21 ~03:0x, Marcos: "roster according to this last
competition and ship. Who's getting benched.")

EVIDENCE: block_competition_real_20260821 — the 8/20 competition re-run at real NBBO spreads
(15,041 fills, 14,958 quotes, 0 gaps). Rank = TOTAL DOLLARS at $5,000 (the 8/20 metric law).
  PRE  ignition +$4,961.61 only positive seat · v2conv -$1,559.31 BOTH halves neg -> BENCHED
  OPEN ignition +$21,866.17 > ema9x90 +$2,234.56 > kevseq +$909.09 > hidden_v2 +$485.09 >
       v2conv +$208.43 (window seat survives R2)
  MID  ignition +$10,319.04 > grinder +$7,376.68 > hidden_v2 > ema9x90 > kevseq

PINS (EXECUTED via the injectable clock, gate-28 discipline)
  T1  PRE_LANE_RANK default = ignition, ma_pullback (v2conv and vwap_reclaim GONE)
  T2  OPEN_LANE_RANK default = ignition, ema9x90, kevseq, hidden_v2, v2conv, ma_pullback
  T3  MID_LANE_RANK default = ignition, grinder, hidden_v2, ema9x90, kevseq, ma_pullback
  T4  v2conv PRE membership now requires V2_PRE=1 (default benched) AND V2_CONVERT — and the
      OPEN window seat does NOT ride V2_PRE (LANE_WINDOWS default still carries v2conv)
  T5  _lane_rank EXECUTED at a pre / open / mid clock returns the new orders
  T6  no rank list references vwap_reclaim or dip_rip (benched/restricted lanes never rank)
"""
import os, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []
def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok: FAIL.append(n)

check("T1 PRE rank default", '"PRE_LANE_RANK", "ignition,ma_pullback"' in SRC)
check("T2 OPEN rank default",
      '"OPEN_LANE_RANK", "ignition,ema9x90,kevseq,hidden_v2,v2conv,ma_pullback"' in SRC)
check("T3 MID rank default",
      '"MID_LANE_RANK", "ignition,grinder,hidden_v2,ema9x90,kevseq,ma_pullback"' in SRC)
check("T4 v2conv PRE bench switch",
      'if V2_CONVERT and os.environ.get("V2_PRE", "0") == "1":' in SRC
      and '"v2conv:09:30-10:30"' in SRC)
for name in ("PRE_LANE_RANK", "OPEN_LANE_RANK", "MID_LANE_RANK"):
    m = re.search(name + r' = \[[^]]+os\.environ\.get\(\s*"' + name + r'", "([^"]+)"', SRC)
    lst = m.group(1) if m else ""
    check(f"T6 {name} seats no benched/restricted lane",
          "vwap_reclaim" not in lst and "dip_rip" not in lst and "prevwap" not in lst)

# T5 — execute _lane_rank with the injectable clock against a scratch env
import subprocess
code = r'''
import os
os.environ.pop("PRE_LANE_RANK", None); os.environ.pop("OPEN_LANE_RANK", None)
os.environ.pop("MID_LANE_RANK", None)
import re, sys
src = open("marcos_trading_bot.py").read()
ns = {"os": os}
for pat in (r"\nLANE_RANK = \[.*?\]", r"\nPRE_LANE_RANK = \[.*?\]",
            r"\nOPEN_LANE_RANK = \[.*?\]", r"\nMID_LANE_RANK = \[.*?\]",
            r"\nOPEN_BLOCK = \(.*?\)\n", r"\nMID_BLOCK = \(.*?\)\n"):
    m = re.search(pat, src, re.S)
    exec(m.group(0), ns)
a = src.find("\ndef _lane_rank(")
b = src.find("\ndef ", a + 1)
fn = src[a:b]
ns["_in_premkt_now"] = lambda: False
ns["_bump"] = lambda *x, **k: None
ns["ENTRY_OPEN_ET"] = "07:00"     # the scratch ns lacked this -> NameError -> LANE_RANK
                                   # fallback fired (by design); T5 must feed the real bound
pre_first = None
exec(fn, ns)
lr = ns["_lane_rank"]
open_order = [lr(x, "09:45") for x in ("ignition","ema9x90","kevseq","hidden_v2","v2conv")]
mid_first = lr("ignition", "12:00")
mid_grind = lr("grinder", "12:00")
assert open_order == sorted(open_order), open_order
assert mid_first < mid_grind, (mid_first, mid_grind)
assert lr("ignition", "08:00") == 0 and lr("v2conv", "08:00") > 1, "pre bench"
print("T5-EXEC-OK")
'''
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
check("T5 _lane_rank EXECUTED returns the new orders (open monotone; mid ignition<grinder)",
      "T5-EXEC-OK" in r.stdout)
if "T5-EXEC-OK" not in r.stdout:
    print(r.stdout[-500:], r.stderr[-500:])
print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
