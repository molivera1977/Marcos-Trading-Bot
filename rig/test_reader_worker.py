#!/usr/bin/env python3
"""Rig: reader cron→always-on-worker conversion (7/24, Marcos: "why do we still have crons????
put in the time like other services").  Proves — with SYNTHETIC clocks, no network — that the
new time gates are correct and the module still boots clean.  Mirrors the bot's window-fn tests.

Run:  python3 rig/test_reader_worker.py
"""
import os, sys, datetime as dt
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Pin the gate to its defaults so the test is independent of any local env override.
os.environ.pop("NEWCOMER_START_HHMM", None)
os.environ.pop("NEWCOMER_STOP_HHMM", None)

import newcomer_vision_reader as R   # ← also the offline "boots clean" proof (import must not raise)

ET = ZoneInfo("America/New_York")
def t(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET)

# Anchor weekdays (verified: 2026-07-20 Mon … 26 Sun; 22 Wed)
MON, WED, FRI, SAT, SUN = 20, 22, 24, 25, 26
fails = []
def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got={got!r} want={want!r}")
    if not ok: fails.append(name)

print("== boot / structure ==")
check("START_HHMM default", R.START_HHMM, "08:50")
check("STOP_HHMM default",  R.STOP_HHMM,  "15:30")
for fn in ("in_read_window", "next_read_open", "_run_session", "_sleep_then_reexec", "main"):
    check(f"{fn} defined", callable(getattr(R, fn, None)), True)

print("== in_read_window (weekday Mon) ==")
check("Mon 07:00 pre-open",  R.in_read_window(t(2026,7,MON,7,0)),   False)
check("Mon 08:49 just-before",R.in_read_window(t(2026,7,MON,8,49)), False)
check("Mon 08:50 at-open",   R.in_read_window(t(2026,7,MON,8,50)),  True)
check("Mon 12:00 midday",    R.in_read_window(t(2026,7,MON,12,0)),  True)
check("Mon 15:29 last-min",  R.in_read_window(t(2026,7,MON,15,29)), True)
check("Mon 15:30 at-stop",   R.in_read_window(t(2026,7,MON,15,30)), False)   # exclusive
check("Mon 15:31 after",     R.in_read_window(t(2026,7,MON,15,31)), False)
check("Mon 20:00 evening",   R.in_read_window(t(2026,7,MON,20,0)),  False)

print("== in_read_window (weekend never) ==")
check("Sat 12:00", R.in_read_window(t(2026,7,SAT,12,0)), False)
check("Sun 12:00", R.in_read_window(t(2026,7,SUN,12,0)), False)

print("== next_read_open ==")
check("Mon 07:00 -> Mon 08:50",  R.next_read_open(t(2026,7,MON,7,0)),   t(2026,7,MON,8,50))
check("Mon 08:50 -> Tue 08:50",  R.next_read_open(t(2026,7,MON,8,50)),  t(2026,7,MON+1,8,50))
check("Mon 09:00 -> Tue 08:50",  R.next_read_open(t(2026,7,MON,9,0)),   t(2026,7,MON+1,8,50))
check("Wed 12:00 -> Thu 08:50",  R.next_read_open(t(2026,7,WED,12,0)),  t(2026,7,WED+1,8,50))
check("Fri 16:00 -> Mon 08:50",  R.next_read_open(t(2026,7,FRI,16,0)),  t(2026,7,MON+7,8,50))
check("Fri 08:50 -> Mon 08:50",  R.next_read_open(t(2026,7,FRI,8,50)),  t(2026,7,MON+7,8,50))
check("Sat 10:00 -> Mon 08:50",  R.next_read_open(t(2026,7,SAT,10,0)),  t(2026,7,MON+7,8,50))
check("Sun 10:00 -> Mon 08:50",  R.next_read_open(t(2026,7,SUN,10,0)),  t(2026,7,MON+7,8,50))

print("== round-trip invariant: a wake time is always in-window at its own instant ==")
for probe in (t(2026,7,FRI,16,0), t(2026,7,SAT,10,0), t(2026,7,MON,7,0), t(2026,7,WED,12,0)):
    w = R.next_read_open(probe)
    check(f"in_window(next_open({probe:%a %H:%M}))", R.in_read_window(w), True)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}"); sys.exit(1)
print("GREEN — all reader-worker gate checks pass"); sys.exit(0)
