#!/usr/bin/env python3
"""
RIG GATE 21 — FIRE-TIME RVOL, THE APPROVED MEASURE (8/19)

Marcos: "i okayed the relvol number not what it was measured against" -> "i do want it
rechecked at fire time." The measure is Webull's 10-day same-time relative volume — the
scanner's number, the one on the board — NOT any homemade session-self baseline. This gate
pins: (a) the ledger is fed at the board-funnel choke point from `relative_volume`;
(b) the fire-time check refuses below IGNITION_RVOL10D with a stamped row carrying the value,
its AGE, and the STOP (the runway-replay lesson: refusal rows without stops can't be graded);
(c) missing or stale (>600s) ledger value FAILS OPEN — absent context never fail-closes;
(d) the refusal does NOT consume the once-per-ticker ammo (attempt-is-not-a-trade; a name
refused for DECAYED rvol may recover and re-fire) — unlike the disarmed session-relvol sibling;
(e) the homemade gate stays default-OFF (IGNITION_RELVOL=0) until Marcos approves a baseline.
"""
import pathlib
import re
import sys

SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


check("ledger declared: _rvol10d sym -> (value, epoch)", "_rvol10d: dict = {}" in SRC)
check("fed at the BOARD FUNNEL choke point from relative_volume",
      '_rvol10d[c["symbol"]] = (float(_rv), time.time())' in SRC)
check("env: IGNITION_RVOL10D default 2.0 (Marcos-approved number), 0 = off",
      'IGNITION_RVOL10D     = float(os.environ.get("IGNITION_RVOL10D", "2.0"))' in SRC)
check("fire-time refusal row carries value + AGE + STOP",
      '"ignition_rvol10d_reject"' in SRC and "rvol10d_age_s=_rv10_age" in SRC
      and 'stop=round(ign["stop"], 4)' in SRC)
check("stale ledger (>600s) -> no opinion, fail open", "_rv10_age > 600" in SRC)
check("gate only refuses when a value EXISTS (missing -> fail open)",
      "_rv10 is not None and _rv10 < IGNITION_RVOL10D" in SRC)
# (d) the rvol10d refusal must NOT consume ammo: no ignition_fired=True between its
# _log_decision and its continue.
m = re.search(r'"ignition_rvol10d_reject".{0,900}?continue', SRC, re.S)
check("refusal does NOT consume the once-per-ticker ammo",
      bool(m) and "ignition_fired" not in m.group(0))
check("homemade session-relvol stays default OFF pending an approved baseline",
      'IGNITION_RELVOL      = float(os.environ.get("IGNITION_RELVOL", "0"))' in SRC)

# behavioral spot-check of the decision logic, standalone
def decide(rv_entry, now, need=2.0):
    _rv10 = None
    if rv_entry:
        _rv10 = float(rv_entry[0])
        if now - rv_entry[1] > 600:
            _rv10 = None
    return "refuse" if (need > 0 and _rv10 is not None and _rv10 < need) else "pass"

check("fresh 1.3x -> refuse", decide((1.3, 1000), 1100) == "refuse")
check("fresh 4.1x -> pass", decide((4.1, 1000), 1100) == "pass")
check("stale 1.3x (11 min) -> fail open", decide((1.3, 1000), 1700) == "pass")
check("missing -> fail open", decide(None, 1700) == "pass")

print("=" * 70)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
