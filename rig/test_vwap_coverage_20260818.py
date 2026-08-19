#!/usr/bin/env python3
"""
GATE 15 — A SESSION VWAP MUST SPAN THE SESSION (8/18)

THE CLASS: `_tick_vwap_ok` adjudicated the tick line against the bar line by comparing them ONLY
to each other and to price. On CDTG 14:16:43 the BAR line was the corrupt one (7.11 = a ~2.5-min
rolling average, verified against 310,022 harvested SIP ticks), so the 5% clamp REJECTED the
CORRECT tick line (4.6719, matching the tape to 4dp) for diverging from it. kevseq gated on 7.11,
read "+9.12% above VWAP" where the truth was ~66%, and took a trade it should have refused.
Any adjudicator that ranks two sources by mutual agreement follows whichever is wrong when the
REFERENCE is broken. The fix adds a third opinion that is not another price: whether the bar set
actually spans the session it claims to price.
"""
import importlib.util
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "marcos_trading_bot.py")).read()
sp = importlib.util.spec_from_file_location("H", os.path.join(HERE, "..", "data", "killtests", "live_harness.py"))
H = importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
ok, cov, tru = H.fn("_tick_vwap_ok"), H.fn("_vwap_coverage_min"), H.fn("_vwap_bar_trusted")
FAILS = []


def chk(c, label, detail=""):
    print(f"  {'PASS' if c else 'FAIL'}  {label}" + (f"   {detail}" if detail and not c else ""))
    if not c:
        FAILS.append(label)


def mk(n, start):
    h, m = int(start[:2]), int(start[3:])
    return [{"time": (datetime.datetime(2026, 8, 18, h, m) + datetime.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "open": 7.7, "high": 7.8, "low": 7.6, "close": 7.75, "volume": 1000} for i in range(n)]


print("GATE 15 — a session VWAP must span the session")
print("=" * 76)
m = re.search(r'VWAP_COVERAGE_GUARD\s*=\s*os\.environ\.get\(\s*"VWAP_COVERAGE_GUARD",\s*"(\d)"\s*\)', SRC)
chk(bool(m), "A1 VWAP_COVERAGE_GUARD kill switch exists")
chk(bool(m) and m.group(1) == "1", "A2 guard defaults ON")
chk("VWAP_MIN_SPAN_MIN" in SRC, "A3 minimum-span threshold is configurable")

NOW = datetime.datetime(2026, 8, 18, 14, 16, tzinfo=datetime.timezone(datetime.timedelta(hours=-4)))
sp3, f3 = cov(mk(3, "18:14"))
sp400, f400 = cov(mk(400, "13:30"))
chk(abs(sp3 - 2.0) < 0.6, "B1 coverage measures a truncated set in minutes", f"got {sp3}")
chk(sp400 > 300, "B2 coverage measures a full session", f"got {sp400}")
chk(tru(sp3, f3, NOW) is False, "B3 a 2-minute bar set is NOT trusted as a session line")
chk(tru(sp400, f400, NOW) is True, "B4 a session-spanning bar set IS trusted")

T, B, P = 4.6719, 7.11, 7.78                       # the real CDTG values
chk(ok(T, B, P, False) is True,
    "C1 THE FIX: with an untrusted bar line, the correct tick line SURVIVES")
chk(ok(T, B, P, True) is False,
    "C2 NO-OP: with a trusted bar line, the 5% clamp still fires (old protection intact)")
chk(ok(T, B, P) is False,
    "C3 default arg keeps legacy behaviour for any un-migrated caller")
chk(ok(2_000_000.0, 4.67, P, False) is False,
    "C4 the catastrophe band still kills unit-scale junk even when bar is untrusted")
chk(ok(0, B, P, False) is False, "C5 a missing tick line is still rejected")

chk("_vwap_bar_trusted(cache[t].get(\"vwap_span_min\")" in SRC,
    "D1 the selection site consults the trust verdict")
# exactly TWO write sites — the PRE+RTH path and the RTH-only path — and the selection site
# reads via .get(). An earlier draft of this pin demanded >=3 occurrences and failed on its own
# arithmetic, not on the code: the read is `.get("vwap_span_min")`, which does not match.
_n_write = SRC.count('cache[t]["vwap_span_min"] = _vcov')
chk(_n_write == 2, "D2 coverage is stamped at BOTH vwap compute sites",
    "got %d write sites" % _n_write)
chk('cache[t].get("vwap_span_min")' in SRC,
    "D2b the selection site READS the stamped span")
chk('"vwap_untrusted" + ("_skip" if VWAP_UNTRUSTED_SKIP' in SRC,
    "D3 both-lines-unusable is LOGGED with its reason (span/first/need/enforced)")
_sk = re.search(r'VWAP_UNTRUSTED_SKIP\s*=\s*os\.environ\.get\(\s*"VWAP_UNTRUSTED_SKIP",\s*"(\d)"\s*\)', SRC)
chk(bool(_sk), "D4 the SKIP is a separate flag from the guard")
chk(bool(_sk) and _sk.group(1) == "0",
    "D5 the skip ships OBSERVE-ONLY (its live frequency is unmeasured); the measured half is ON")
print("=" * 76)
if FAILS:
    print(f"GATE 15 FAILED ({len(FAILS)}): " + "; ".join(FAILS)); sys.exit(1)
print("GATE 15 PASSED"); sys.exit(0)
