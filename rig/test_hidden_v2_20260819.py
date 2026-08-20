#!/usr/bin/env python3
"""
RIG GATE 25 — HIDDEN v2 LANE (8/19, Marcos: "lock the new hidden. build it and ship live
for tomorrow.")

Spec source: data/killtests/hidden_v2_simple_20260819.py + the in-session 8/19 ladders.
Locked config: ARM 25-60% day-gain above VWAP (RTH 09:30-15:30) · pullback <= 50% of the
rolling-5-min-low->high leg · trigger = HIGH breaks the pullback high within 6 bars ·
stop = pullback low -1% · exits HV2 (25% @ +1R -> BE-or-better, 15-min no-new-high) ·
NO day caps · min-stop 4% ON (measured: survivors +$41.60/tr OOS vs +$6.80/tr refused).

SECTION A — the detector EXECUTED on synthetic tape (not regex): arm gating, pullback
            depth, trigger, stop math, cool-off, day reset.
SECTION B — _hv2_eval EXECUTED: stop-first, new-high clock reset, 15-min time fire.
SECTION C — wiring pins: tape class, RTH whitelist, exit_mode plumbing, 25%@+1R tier,
            age guard armed at birth, NOT min-stop exempt, NO day cap, refusal visibility.
"""
import datetime as _dt
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "marcos_trading_bot.py").read_text()
FAIL = []


def check(n, ok):
    print(("  ok  " if ok else "  XX  ") + n)
    if not ok:
        FAIL.append(n)


def _lift(name):
    i = SRC.find(f"\ndef {name}(")
    j = SRC.find("\ndef ", i + 1)
    return SRC[i:j]


# ── SECTION A: detector on synthetic tape ────────────────────────────────────────────────
class _ZI(_dt.tzinfo):                         # minimal EASTERN stand-in
    def utcoffset(self, dt): return _dt.timedelta(hours=-4)
    def tzname(self, dt): return "ET"
    def dst(self, dt): return _dt.timedelta(0)


_ns = {"datetime": _dt.datetime, "EASTERN": _ZI(), "_hv2_state": {}}
exec(compile(_lift("hidden_v2_step"), "hv2", "exec"), _ns)
step = _ns["hidden_v2_step"]

# epoch for a given ET wall time today (the detector formats k via EASTERN)


def at(hh, mm, ss=0):
    d = _dt.datetime.now(_ZI()).replace(hour=hh, minute=mm, second=ss, microsecond=0)
    return int(d.timestamp())


PDC = 10.0
VWAP = 12.0
K0 = at(10, 0)


def bars(seq, k0=K0):
    """seq of (o,h,l,c) -> [(k,o,h,l,c,v)] at 10s spacing."""
    return [(k0 + 10 * i, o, h, l, c, 1000) for i, (o, h, l, c) in enumerate(seq)]


def run(seq, vwap=VWAP, pdc=PDC, k0=K0):
    _ns["_hv2_state"].clear()
    fires = []
    for nb in [bars(seq, k0)[i:i + 1] for i in range(len(seq))]:   # bar-at-a-time feed
        f = step("T", nb, vwap, pdc)
        if f:
            fires.append(f)
    return fires


# a clean setup: base ~13 (30% over pdc=10, above vwap=12), run to 14, 3-bar pullback to
# 13.5 (leg from ~13 low, depth 0.5 <= 50% of ~1.0 leg), then a bar breaks the pullback high
BASE = [(13.0, 13.1, 12.95, 13.05)] * 31                    # fills the 31-bar leg window
RUN = [(13.1, 13.6, 13.05, 13.55), (13.55, 14.0, 13.5, 13.95)]
PULL = [(13.95, 13.95, 13.75, 13.8), (13.8, 13.82, 13.6, 13.65), (13.65, 13.66, 13.5, 13.55)]
BREAK = [(13.6, 14.05, 13.55, 14.0)]

f = run(BASE + RUN + PULL + BREAK)
check("A1 clean setup fires exactly once", len(f) == 1)
check("A2 stop = pullback low -1%", bool(f) and abs(f[0]["stop"] - 13.5 * 0.99) < 1e-6)
check("A3 fire px = the TRIGGER BAR'S TRADED CLOSE, never a level",
      bool(f) and f[0]["px"] == 14.0)

check("A4 below-VWAP arm refuses (same tape, vwap above price)",
      run(BASE + RUN + PULL + BREAK, vwap=15.0) == [])
check("A5 day-gain 20% (below 25 floor) refuses",
      run(BASE + RUN + PULL + BREAK, pdc=11.2) == [])
check("A6 day-gain 80% (above 60 cap) refuses",
      run(BASE + RUN + PULL + BREAK, pdc=7.6) == [])
check("A7 out-of-window (09:10) refuses", run(BASE + RUN + PULL + BREAK, k0=at(9, 10)) == [])

DEEP = [(13.95, 13.95, 13.3, 13.4), (13.4, 13.42, 13.0, 13.1), (13.1, 13.12, 12.98, 13.0)]
check("A8 pullback deeper than 50% of leg refuses",
      run(BASE + RUN + DEEP + [(13.1, 14.05, 13.05, 14.0)]) == [])

# cool-off: an identical second setup immediately after the fire must NOT fire again (<300s)
f2 = run(BASE + RUN + PULL + BREAK + PULL + BREAK)
check("A9 300s cool-off: immediate re-setup does not re-fire", len(f2) == 1)

_ns["_hv2_state"].clear()
step("T", bars(BASE), VWAP, PDC)
_ns["_hv2_state"]["T"]["day"] = "1999-01-01"
step("T", bars(RUN, K0 + 310), VWAP, PDC)
check("A10 day rollover resets state (run_hi rebuilt, no stale carry)",
      _ns["_hv2_state"]["T"]["run_hi"] <= 14.0 and _ns["_hv2_state"]["T"]["day"] != "1999-01-01")

# ── SECTION B: _hv2_eval executed ────────────────────────────────────────────────────────
_nse = {}
exec(compile(_lift("_hv2_eval"), "hv2e", "exec"), _nse)
ev = _nse["_hv2_eval"]
check("B1 stop-first tie", ev(10.0, 11.0, 100, 10.0, 12.0, 200, 900)[2] == "stop")
rh, hk, act = ev(9.0, 11.0, 100, 10.5, 11.5, 200, 900)
check("B2 new high resets the clock", rh == 11.5 and hk == 200 and act is None)
check("B3 15 min without a new high -> time", ev(9.0, 11.0, 100, 10.5, 10.8, 1000, 900)[2] == "time")
check("B4 14m59s without a new high -> hold", ev(9.0, 11.0, 100, 10.5, 10.8, 999, 900)[2] is None)

# ── SECTION C: wiring pins ───────────────────────────────────────────────────────────────
check("C1 lane registered TAPE", '"hidden_v2":      "tape"' in SRC)
check("C2 RTH whitelist default includes hidden_v2",
      re.search(r'"RTH_LANES",\s*(#[^\n]*\n\s*)*"[^"]*hidden_v2', SRC) is not None)
check("C3 v1 hidden_entry NOT in the RTH default (stays restricted)",
      re.search(r'"RTH_LANES",\s*(#[^\n]*\n\s*)*"[^"]*hidden_entry', SRC) is None)
check("C4 convert appends exit_mode HV2", '"exit_mode": "HV2"' in SRC)
check("C5 monitor: HV2 is E3-family with its own flag",
      '_hv2_mode = bool(exit_mode == "HV2")' in SRC
      and '_e3_mode  = bool(E3_EXITS and exit_mode == "E3") or _hv2_mode' in SRC)
check("C6 tier = 25% at +1.0R",
      "kev_tiers = [(round(entry_price + 1.0 * R, 4), 0.25)]" in SRC)
check("C7 time stop default 900s env-tunable",
      'HIDDENV2_TIME_STOP = int(os.environ.get("HIDDENV2_TIME_STOP", "900"))' in SRC)
check("C8 age guard armed at birth",
      'os.environ.get("LANE_FIRE_AGE_GUARD", "hidden_v2")' in SRC)
check("C9 NOT min-stop exempt (measured: the gate pays)",
      "hidden_v2" not in re.search(r'"MIN_STOP_EXEMPT", "([^"]*)"', SRC).group(1))
check("C10 NO day cap on the lane (Marcos: eliminate the day caps)",
      "hv2_capped" not in SRC and "HIDDENV2_DAILY_CAP" not in SRC)
check("C11 missing day-gain basis logs a row, never dies silently",
      '"hiddenv2_no_daygain_basis"' in SRC)
check("C12 fire honors the stale-bucket verdict",
      re.search(r'_hv2f and _lane_fire_stale\(t, "hidden_v2".*\):\s*\n\s*_hv2f = None', SRC))
check("C13 drift + fire_px stamps on the conversion row",
      '"fire_px": _hv2f["px"], "fire_k": _hv2f["k"]' in SRC)
# C14 — Blast Radius Auditor finding #1 (8/19 pre-ship): the shared BE floor defaults to
# after-2nd-scale, but HV2's ladder is ONE tier — without the branch below, the "stop -> BE"
# half of the spec NEVER executes and the runner carries full pullback-low risk. Gate 25's
# first version pinned the tier (C6) but not the floor; this pin closes that exact gap.
check("C14 BE floor arrives after HV2's single tier",
      "if tier_idx >= (1 if _hv2_mode else BE_FLOOR_AFTER_SCALE):" in SRC)
# C15 — Marcos ruling 8/19 22:4x ET: "in the life of the ticker and the life of the move,
# hidden should be right after ignition at #2."
check("C15 LANE_RANK: hidden_v2 at #2, right after ignition",
      '"LANE_RANK", "ignition,hidden_v2,ema9x90,ma_pullback"' in SRC)
# C16/C17 — Marcos ruling 8/19 ~23:5x ET: "if hidden has no need for a map or runway, then
# why gate it to them in any way shape or form" / "hidden by design is its own gate".
check("C16 pattern-gate switch exists, default ON",
      'HV2_PATTERN_GATE = os.environ.get("HV2_PATTERN_GATE", "1") == "1"' in SRC)
check("C17 exempt from BOTH blanket map gates (mapless-block + external runway)",
      "MAPLESS_BLOCK and not _ml_has_map and not (\n"
      "                            HV2_PATTERN_GATE and entry_type == \"hidden_v2\")" in SRC
      and 'and not (HV2_PATTERN_GATE and entry_type == "hidden_v2")' in SRC)
check("C18 min-stop still ON for hidden_v2 (measured to pay — C9 re-checked)",
      "hidden_v2" not in re.search(r'"MIN_STOP_EXEMPT", "([^"]*)"', SRC).group(1))

print("=" * 74)
print("GREEN" if not FAIL else f"RED — {FAIL}")
sys.exit(1 if FAIL else 0)
