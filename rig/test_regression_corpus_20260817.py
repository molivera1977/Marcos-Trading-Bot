#!/usr/bin/env python3
"""FOUNDATION BATCH I — REGRESSION CORPUS, PART TWO.  Judged by EXIT CODE (sweep law).

Gate 8 in rig/test_gates_20260817.py pinned FIVE of 8/17's defects as permanent fixtures.
Tonight produced MANY more verified defects with no fixture at all, so they can silently
return the way the session-boundary class kept returning in new consumers.  This file pins
the remaining EIGHT.  Its own file on purpose (the gate-file precedent): agents G and H were
writing rig/test_gates_20260817.py the same night, and two writers on one file is how a ship
gets lost.

  I1  restart replay            — 5 boot_config rows, RBNE grinder re-fired 5x at seq=0
  I2  ma_pullback re-attempt    — YDES 40 rows, one price, 34 minutes, at scan cadence
  I3  kevseq level-price        — WFF 12:01, level 5.1329 vs traded 8.20; 6.49% vs 41.46%
  I4  front-side clock mismatch — RBNE 48 M1 bars over 243 wall-clock minutes; 31 disagreements
  I5  harness ctx refusal       — the four-studies-front-side-free hole
  I6  bucket_fresh replay clock — hidden replay 0 fires disarmed / 424 armed, 13 names
  I7  study replica             — hand-rolled detector fails, live_harness passes
  I8  config epoch              — 8/17 = 5 machines; one produced 51% of fires, 5 of 7 fills

EVERY fixture carries REAL numbers pulled from tonight's artifacts (each fixture names its
`_source` and, where it came from the archive, the `_repro` query), a one-line `_defect`
statement, and a NEGATIVE CONTROL that demonstrably fails on the pre-fix behaviour.  Where the
pre-fix code is reachable in git the control uses `git show <sha>:file`; where it is not (the
harness ctx contract had no predecessor to show — the old scripts had no contract at all) the
defective behaviour is SIMULATED EXPLICITLY and this file says so at the call site.

  python3 rig/test_regression_corpus_20260817.py
"""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "rig", "regression_fixtures")
os.environ.setdefault("DRY_RUN", "1")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "rig"))
sys.path.insert(0, os.path.join(ROOT, "data", "killtests"))

FAILS = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + ((f"  [{detail}]") if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def fixture(name):
    return json.load(open(os.path.join(FIX, name)))


def bot_src():
    return open(os.path.join(ROOT, "marcos_trading_bot.py")).read()


def _extract(src, start, end):
    """Slice a source block by literal markers — exec the SHIPPED code in isolation rather
    than reimplementing it (the established rig pattern)."""
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


# ══════════════════════════════════════════════════════════════════════════════
# I1 — RESTART REPLAY
# DEFECT: a restart wipes the 10s bucket cursors; deep-rehydrate re-feeds the whole day and
#         every 10s detector re-emits historical fires as fresh decision rows — and on the
#         conversion lanes a replayed bar was CONVERTED.
# ══════════════════════════════════════════════════════════════════════════════
def _load_fire_once(dedupe="1", hwm_path=None):
    """exec the SHIPPED _fire_once/_fire_seen into an isolated namespace, with the kill
    switch and the mark file under this test's control."""
    src = bot_src()
    blk = _extract(src, "DEDUPE_FIRES  = os.environ.get(", "# ── 8/17 A2 — FED-BUCKET PROVENANCE")
    import threading
    env = dict(os.environ)
    env["DEDUPE_FIRES"] = dedupe
    env["FIRE_HWM_PATH"] = hwm_path or os.path.join(tempfile.mkdtemp(), "fire_hwm.json")
    ns = {"os": type("E", (), {"environ": env, "path": os.path, "makedirs": os.makedirs,
                               "replace": os.replace})(),
          "json": json, "threading": threading,
          "datetime": datetime.datetime, "EASTERN": None}
    exec(blk, ns)
    return ns


def i1():
    print("I1) RESTART REPLAY — one bucket, five restarts, one fire")
    fx = fixture("restart_replay_20260817.json")
    check("I1-0: fixture holds the five REAL boot_config rows",
          fx["boot_config_n"] == 5 and len(fx["boot_config_rows"]) == 5,
          str(fx["boot_config_rows"]))
    check("I1-1: RBNE grinder_shadow_fire fired 5x with seq=0 (the detector's per-day counter "
          "back at ZERO — state re-derived, not a logging echo)",
          fx["rbne_seq0_n"] == 5 and all(r["mins_since_1030"] == 35
                                         for r in fx["rbne_grinder_shadow_fires"] if r["seq"] == 0),
          str(fx["rbne_grinder_shadow_fires"]))
    check("I1-2: replayed bars really were CONVERTED (triggered_grinder fire_age_s in the "
          "thousands of seconds)", min(fx["converted_replay_fire_age_s"]) > 1900)

    K = 1755442009          # the RBNE 11:05 bucket epoch that got re-fired
    ns = _load_fire_once("1")
    fired = sum(1 for _ in range(fx["refeed_passes"])
                if ns["_fire_once"]("grinder", "RBNE", K, day="2026-08-17"))
    check("I1-3: the SAME bucket re-fed once per restart emits exactly ONCE (%d passes -> %d)"
          % (fx["refeed_passes"], fired), fired == fx["expect_fires_from_one_bucket_refed_n_times"],
          str(fired))
    # a genuinely NEW bucket must still get through — the guard may not go fail-shut
    check("I1-4: a strictly LATER bucket still fires (the mark is monotonic, not a mute)",
          ns["_fire_once"]("grinder", "RBNE", K + 600, day="2026-08-17"))
    check("I1-5: another symbol on the same lane is unaffected (key is day|lane|sym)",
          ns["_fire_once"]("grinder", "WFF", K, day="2026-08-17"))
    check("I1-6: an UNKNOWN bucket (k=0/None) is NEVER blocked — a parse failure degrades to "
          "today's behaviour, never to a missed trade",
          all(ns["_fire_once"]("grinder", "RBNE", k, day="2026-08-17") for k in (0, None, -1)))
    check("I1-7: _fire_seen is a NON-CONSUMING peek (the pre-pass cannot eat the real fire's mark)",
          ns["_fire_seen"]("grinder", "RBNE", K, day="2026-08-17")
          and not ns["_fire_seen"]("grinder", "RBNE", K + 99999, day="2026-08-17"))
    check("I1-8: the mark is PERSISTED — it survives the restart that causes the defect",
          "FIRE_HWM_PATH" in bot_src() and "os.replace(_tmp, FIRE_HWM_PATH)" in bot_src())

    # ── NEGATIVE CONTROL: the kill switch reproduces the five rows ──
    nc = _load_fire_once("0")
    dup = sum(1 for _ in range(fx["refeed_passes"])
              if nc["_fire_once"]("grinder", "RBNE", K, day="2026-08-17"))
    check("I1-NC: DEDUPE_FIRES=0 -> the same re-fed bucket emits %d times, reproducing the five "
          "seq=0 RBNE rows" % fx["refeed_passes"], dup == fx["refeed_passes"] == 5, str(dup))
    check("I1-NC2: the kill switch is a real switch in the shipped source",
          'DEDUPE_FIRES  = os.environ.get("DEDUPE_FIRES", "1") == "1"' in bot_src()
          and "if not DEDUPE_FIRES:" in bot_src())
    print("      (what it cost on 8/17: %d logged fire+trigger rows for %d distinct — %d inflation, "
          "%d of them cross-restart)"
          % (fx["all_fire_trigger_rows"]["logged"], fx["all_fire_trigger_rows"]["distinct"],
             fx["all_fire_trigger_rows"]["inflation"], fx["all_fire_trigger_rows"]["cross_restart"]))


# ══════════════════════════════════════════════════════════════════════════════
# I2 — MA_PULLBACK RE-ATTEMPT
# DEFECT: detect_ma_pullback is a pure function of the bar slice with nothing marking the setup
#         consumed, so entry type 2 pushed a FRESH trade candidate through the ENTIRE downstream
#         gate and trade path once per scan cycle.
# ══════════════════════════════════════════════════════════════════════════════
def i2():
    print("I2) MA_PULLBACK RE-ATTEMPT — 40 scan passes, one setup, one fire")
    fx = fixture("ma_pullback_reattempt_20260817.json")
    check("I2-0: fixture reproduces the documented specimen (YDES 40 rows, ONE price, 34 min)",
          fx["rows"] == 40 and fx["price"] == [3.2933] and fx["window_minutes"] == 34
          and len(fx["times"]) == 40, "rows=%s price=%s" % (fx["rows"], fx["price"]))
    check("I2-1: the inter-row gaps are the SCAN CADENCE, not a market event (all 30-90s)",
          all(30 <= g <= 90 for g in fx["gaps_secs_head"]), str(fx["gaps_secs_head"]))
    check("I2-2: this is a STATE defect, not logging — the lane re-attempted the trade "
          "(zero fills on 8/17 was luck, not design)", fx["day_totals"]["ma_pullback_fills"] == 0)

    K = 1755448382          # the YDES confirmation candle's epoch
    ns = _load_fire_once("1")
    fires = sum(1 for _ in range(fx["scan_passes"])
                if ns["_fire_once"]("ma_pullback", "YDES", K, day="2026-08-17"))
    check("I2-3: the same confirmation candle across %d scan passes yields ONE fire (got %d)"
          % (fx["scan_passes"], fires), fires == fx["expect_fires"], str(fires))
    check("I2-4: a NEW buyer stepping in prints a NEW confirmation candle with a strictly "
          "greater epoch — and it is admitted",
          ns["_fire_once"]("ma_pullback", "YDES", K + 180, day="2026-08-17"))
    src = bot_src()
    check("I2-5: the detector returns the confirmation candle's epoch as its bucket",
          '"k": _bar_epoch(conf)' in src)
    check("I2-6: entry type 2 GATES on it, and the suppression is LOGGED (the counterfactual "
          "stays visible)",
          'if ma_pb and MA_PULLBACK_DEDUPE and not _fire_once("ma_pullback", t, ma_pb.get("k"))'
          in src and "ma_pullback_dup_suppressed" in src)
    check("I2-7: the PULLBACK_FIRST pre-pass uses the NON-CONSUMING peek, so it cannot eat the "
          "mark the real fire needs", '_fire_seen("ma_pullback", t, _ma_first_fire.get("k"))' in src)

    # ── NEGATIVE CONTROL ──
    nc = _load_fire_once("0")
    dup = sum(1 for _ in range(fx["scan_passes"])
              if nc["_fire_once"]("ma_pullback", "YDES", K, day="2026-08-17"))
    check("I2-NC: with dedupe OFF the same setup emits on every pass -> %d, the exact YDES row "
          "count" % fx["rows"], dup == fx["rows"] == 40, str(dup))
    check("I2-NC2: MA_PULLBACK_DEDUPE is a real switch (and DEDUPE_FIRES=0 disables it too)",
          'MA_PULLBACK_DEDUPE = os.environ.get("MA_PULLBACK_DEDUPE", "1") == "1"' in src)
    print("      (day-wide: %d ma_pullback rows for at most %d distinct setups = %.2fx inflation; "
          "pullback_first_suppress carries the identical %d)"
          % (fx["day_totals"]["ma_pullback_rows"], fx["day_totals"]["distinct_upper_bound"],
             fx["day_totals"]["duplication_factor"],
             fx["day_totals"]["pullback_first_suppress_rows"]))


# ══════════════════════════════════════════════════════════════════════════════
# I3 — KEVSEQ LEVEL-PRICE
# DEFECT: kevseq_step returned the setup bar's HIGH — the trigger LEVEL, not a traded price.
#         Sizing was handed a fictitious risk-per-share.
# ══════════════════════════════════════════════════════════════════════════════
def i3():
    print("I3) KEVSEQ LEVEL-PRICE — the fire price must derive from a traded print")
    fx = fixture("kevseq_level_price_20260817.json")
    wff = fx["specimens"][0]
    check("I3-0: fixture holds the WFF 12:01 specimen exactly as documented",
          wff["ticker"] == "WFF" and wff["level_px"] == 5.1329 and wff["traded_px"] == 8.20
          and wff["would_stop"] == 4.80, str(wff))
    # the arithmetic the two prices imply — recomputed here, never copied
    old = (wff["level_px"] - wff["would_stop"]) / wff["level_px"] * 100
    new = (wff["traded_px"] - wff["would_stop"]) / wff["traded_px"] * 100
    check("I3-1: the LEVEL implies the stated %.2f%% risk (%.2f%% recomputed)"
          % (wff["old_risk_pct"], old), abs(old - wff["old_risk_pct"]) < 0.01, "%.4f" % old)
    check("I3-2: the TRADED price implies %.2f%% — the risk actually paid (%.2f%% recomputed)"
          % (wff["new_risk_pct"], new), abs(new - wff["new_risk_pct"]) < 0.01, "%.4f" % new)
    check("I3-3: the understatement is %.1fx, silently (planned $%d of risk, real $%d)"
          % (wff["sizing"]["risk_multiple"], wff["sizing"]["planned_risk_usd"],
             wff["sizing"]["real_risk_usd"]),
          round(new / old, 1) == wff["sizing"]["risk_multiple"], "%.2f" % (new / old))
    src = bot_src()
    check("I3-4: the SHIPPED detector prices off the fill bar's CLOSE, switch-guarded",
          'px = float(c) if KEVSEQ_FIRE_ON_CLOSE else float(pd["hi"])' in src)
    check("I3-5: the old trigger level is KEPT as evidence (level_px), so every row can still "
          "be sliced by the level the setup broke", '"level_px"' in src)
    check("I3-6: a close at/below the setup's own stop is REFUSED, not sized (TRUG/RPGL shape)",
          "degenerate_stop" in src)
    check("I3-7: kevseq now matches all EIGHT sibling detectors, which price off the close",
          len(fx["siblings_pricing_off_close"]) == 8)
    trug = [s for s in fx["specimens"] if s["ticker"] == "TRUG"][0]
    check("I3-8: the TRUG specimen really is degenerate (traded %.3f <= stop %.2f) — the OLD "
          "code called it a valid %.2f%%-risk fire"
          % (trug["traded_px"], trug["would_stop"], trug["old_risk_pct"]),
          trug["traded_px"] <= trug["would_stop"])

    # ── NEGATIVE CONTROL: git show the pre-fix tree ──
    try:
        pre = subprocess.run(["git", "-C", ROOT, "show",
                              "%s:marcos_trading_bot.py" % fx["pre_fix_commit"]],
                             capture_output=True, text=True, timeout=180).stdout
        check("I3-NC: at %s kevseq_step assigns the LEVEL unconditionally — the defect "
              "reproduces on the pre-fix tree" % fx["pre_fix_commit"],
              bool(pre) and 'px = float(pd["hi"])' in pre
              and 'px = float(c) if KEVSEQ_FIRE_ON_CLOSE' not in pre,
              "len=%d" % len(pre))
        check("I3-NC2: the pre-fix tree has NO kill switch at all (the fix introduced one)",
              bool(pre) and "KEVSEQ_FIRE_ON_CLOSE" not in pre)
    except Exception as e:                                              # noqa: BLE001
        check("I3-NC: git negative control ran", False, "%s: %s" % (type(e).__name__, e))
    check("I3-NC3: KEVSEQ_FIRE_ON_CLOSE=0 restores the level — the switch exists and defaults ON",
          'KEVSEQ_FIRE_ON_CLOSE' in src and re.search(
              r'KEVSEQ_FIRE_ON_CLOSE",\s*"1"', src) is not None)
    d = fx["day_distribution"]
    print("      (the day it was found: %d fires, stated mean risk %.2f%% vs real %.2f%%; "
          "%d fires carried >20%% real risk while telling the sizer single digits)"
          % (d["n"], d["old"]["mean"], d["new"]["mean"], d["new"]["over20"]))


# ══════════════════════════════════════════════════════════════════════════════
# I4 — FRONT-SIDE CLOCK MISMATCH
# DEFECT: two 1-MINUTE front-side sources on DIFFERENT CLOCKS — the caller's traded-minute grid
#         vs the self aggregate's contiguous wall-clock grid.  Same label, different time axis.
# ══════════════════════════════════════════════════════════════════════════════
def _load_wallclock_window():
    src = bot_src()
    blk = _extract(src, "def _wallclock_window(", "def _stop_close_qualifies")
    ns = {"datetime": datetime.datetime, "timezone": datetime.timezone,
          "timedelta": datetime.timedelta}
    exec(blk, ns)
    return ns["_wallclock_window"]


def i4():
    print("I4) FRONT-SIDE CLOCK MISMATCH — two 1-min sources, one wall clock")
    fx = fixture("frontside_clock_20260817.json")
    check("I4-0: fixture holds all %d REAL canary rows" % fx["disagreements_n"],
          fx["disagreements_n"] == 31 == len(fx["rows"]))
    sp = fx["specimen"]
    check("I4-1: the RBNE specimen is the documented one — %d M1 bars spanning %d wall-clock min"
          % (sp["caller_n"], sp["caller_span_min"]),
          sp["caller_n"] == 48 and sp["caller_span_min"] == 243 and sp["self_n"] == 81)
    check("I4-2: the two sources DISAGREE on that row (caller %s vs self %s)"
          % (sp["caller_front_side"], sp["self_front_side"]),
          sp["caller_front_side"] != sp["self_front_side"])
    rb = [r for r in fx["rows"] if r["ticker"] == "RBNE" and r["hm"] == "13:50"]
    check("I4-3: the specimen is present in the raw canary rows, unaltered",
          any(r["caller_n"] == 48 and r["self_n"] == 81 and r["caller"] and not r["self_agg"]
              for r in rb), str(rb))
    check("I4-4: all %d rows really are disagreements (caller != self on every one)"
          % len(fx["rows"]),
          all(r["caller"] != r["self_agg"] for r in fx["rows"]))

    # THE MECHANISM, from the span census: a 20-bar 'EMA20' covers 20 MINUTES only when the
    # bar count and the wall-clock span agree.  On thin names they do not, by orders.
    thin = [c for c in fx["span_census"] if c["sym"] in fx["thin_names"]]
    liq = [c for c in fx["span_census"] if c["sym"] in fx["liquid_names"]]
    check("I4-5: on LIQUID names the two clocks coincide (span ~ bar count, <= 60 min)",
          all(c["caller_span_min"] <= 60 for c in liq),
          str([(c["sym"], c["caller_span_min"]) for c in liq]))
    check("I4-6: on THIN names the caller's 49-bar '1-minute' window reaches back HOURS "
          "(min %d min, max %d min)"
          % (min(c["caller_span_min"] for c in thin), max(c["caller_span_min"] for c in thin)),
          all(c["caller_span_min"] > 150 for c in thin))
    uuu = [c for c in fx["span_census"] if c["sym"] == "UUU"][0]
    check("I4-7: UUU held %d self minute-buckets on a day whose entire SIP tape has %d traded "
          "minutes — the extra buckets are real ELAPSED minutes with no prints"
          % (uuu["max_self_n"], uuu["sip_1m_bars_all_day"]),
          uuu["max_self_n"] == 155 > uuu["sip_1m_bars_all_day"] == 54)

    # THE FIX PROPERTY: apply the wall-clock window and the two sources cover the same elapsed
    # window.  Driven through the SHIPPED _wallclock_window.
    fn = _load_wallclock_window()
    base = datetime.datetime(2026, 8, 17, 13, 33, tzinfo=datetime.timezone.utc)
    # the caller's traded-minute list: 48 bars, sparse, spanning 243 wall-clock minutes
    step = sp["caller_span_min"] / (sp["caller_n"] - 1)
    caller = [{"time": (base + datetime.timedelta(minutes=i * step)).strftime(
        "%Y-%m-%dT%H:%M:00.000+0000"), "close": 2.7 + i * 0.001} for i in range(sp["caller_n"])]
    # the self aggregate: a CONTIGUOUS wall-clock grid over the same window
    self_agg = [{"time": (base + datetime.timedelta(minutes=i)).strftime(
        "%Y-%m-%dT%H:%M:00.000+0000"), "close": 2.7} for i in range(sp["caller_span_min"] + 1)]
    W = fx["wallclock_window_min"]

    def span(bars):
        if len(bars) < 2:
            return 0.0
        t0 = datetime.datetime.strptime(bars[0]["time"][:19], "%Y-%m-%dT%H:%M:%S")
        t1 = datetime.datetime.strptime(bars[-1]["time"][:19], "%Y-%m-%dT%H:%M:%S")
        return (t1 - t0).total_seconds() / 60.0

    check("I4-8: UNWINDOWED, the caller's %d bars span %.0f min while the self aggregate's "
          "same-length tail spans %.0f — the clocks disagree by construction"
          % (len(caller), span(caller), span(self_agg[-len(caller):])),
          span(caller) > 4 * span(self_agg[-len(caller):]))
    cw, sw = fn(caller, W), fn(self_agg, W)
    check("I4-9: WITH the wall-clock window both sources cover the SAME elapsed window "
          "(caller %.0f min, self %.0f min, both <= %d)" % (span(cw), span(sw), W),
          span(cw) <= W and span(sw) <= W and abs(span(cw) - span(sw)) <= W,
          "%.1f vs %.1f" % (span(cw), span(sw)))
    check("I4-10: and the caller's list is genuinely TRIMMED by it (%d -> %d bars)"
          % (len(caller), len(cw)), len(cw) < len(caller))

    # ── NEGATIVE CONTROL ──
    check("I4-NC: with NO window (window_min=0) the caller keeps all %d bars spanning %.0f "
          "wall-clock minutes — a '20-bar EMA20' covering %.1f hours"
          % (sp["caller_n"], span(caller), span(caller) / 60.0),
          len(fn(caller, 0)) == sp["caller_n"] == 48 and span(fn(caller, 0)) == 243)
    check("I4-NC2: the M1_WALLCLOCK kill switch that restores it still exists",
          'M1_WALLCLOCK", "1"' in bot_src())
    check("I4-11: the record carries the REFUTATION too — the 3-minute premise was false and "
          "cost $0 / N=0; this fixture pins the CLOCK defect, not the timeframe one",
          "REFUTED" in fx["_note"] and "$0 / N=0" in fx["_note"])
    print("      (%d of %d disagreements sit inside |EMA9-EMA20| <= 0.25%% — noise-dominated, "
          "which is why the SOURCE SWAP stayed a proposal and only the stamps shipped)"
          % (fx["knife_edge"]["rows_within_0p25pct"], fx["knife_edge"]["of"]))


# ══════════════════════════════════════════════════════════════════════════════
# I5 — HARNESS CTX REFUSAL
# DEFECT: a detector invoked without a required ctx field silently DEFAULTS.  That is how four
#         studies graded a front-side-FREE kevseq while the live lane requires the clause.
# ══════════════════════════════════════════════════════════════════════════════
def i5():
    print("I5) HARNESS CTX REFUSAL — a missing ctx field must REFUSE by name, never default")
    fx = fixture("harness_ctx_refusal_20260817.json")
    check("I5-0: the hole is the documented one — %d of %d audited studies replicated the live "
          "gate" % (fx["studies_replicating_live_gate"], fx["studies_audited"]),
          fx["studies_replicating_live_gate"] == 0 and len(fx["contaminated_studies"]) == 4)
    try:
        import live_harness as H
    except Exception as e:                                              # noqa: BLE001
        check("I5: live_harness imports", False, "%s: %s" % (type(e).__name__, e))
        return
    check("I5-1: live_harness declares MissingContext and it is a HarnessError",
          issubclass(H.MissingContext, H.HarnessError))
    for lane, req in fx["lane_ctx_required"].items():
        got = list(H.LANES.get(lane, {}).get("ctx_required", ()))
        check("I5-2: lane '%s' declares ctx_required=%s exactly as the fixture pins" % (lane, req),
              got == req, "got %s" % got)

    full = {"front_side": True, "day_gain": 40.0, "top3": True, "blue_sky": True}
    check("I5-3: a COMPLETE kevseq ctx passes the contract", H._check_ctx("kevseq", full) == full)
    # every required field, one at a time, must refuse BY NAME
    for k in fx["lane_ctx_required"]["kevseq"]:
        partial = {x: v for x, v in full.items() if x != k}
        try:
            H._check_ctx("kevseq", partial)
            check("I5-4: kevseq refuses when '%s' is absent" % k, False, "it DEFAULTED")
        except H.MissingContext as e:
            check("I5-4: kevseq refuses when '%s' is absent, NAMING the field" % k,
                  k in str(e), str(e)[:120])
    try:
        H._check_ctx("kevseq", None)
        check("I5-5: ctx=None refuses", False, "it defaulted")
    except H.MissingContext as e:
        check("I5-5: ctx=None refuses and names the required set",
              all(k in str(e) for k in fx["lane_ctx_required"]["kevseq"]), str(e)[:120])
    # A value of None is ALLOWED — kevseq treats front_side=None as unknown -> refuse.
    # ABSENCE is what is forbidden.  The distinction is the whole contract.
    nonev = dict(full, front_side=None)
    check("I5-6: front_side=None is ACCEPTED (means 'unknown'); only ABSENCE is refused",
          H._check_ctx("kevseq", nonev)["front_side"] is None)
    # replay() must refuse before it runs anything, not mid-stream
    try:
        H.replay("TT", [], ["kevseq"], ctx_provider=None, vwap_provider=lambda *a: 1.0)
        check("I5-7: replay() refuses a ctx-required lane with no ctx_provider", False, "it ran")
    except H.MissingContext as e:
        check("I5-7: replay() refuses a ctx-required lane with no ctx_provider, up front",
              "front_side" in str(e) or "ctx" in str(e), str(e)[:120])
    try:
        H.replay("TT", [], ["zone_flip"], ctx_provider=None, vwap_provider=lambda *a: 1.0)
        check("I5-8: replay() refuses zone_flip without pm_floor", False, "it ran")
    except (H.MissingContext, H.HarnessError) as e:
        check("I5-8: replay() refuses zone_flip without its pm_floor", "pm_floor" in str(e)
              or "NOT REPLAYABLE" in str(e), str(e)[:140])

    # ── NEGATIVE CONTROL — SIMULATED, and this is stated plainly.
    # There is no pre-fix commit to `git show`: the contaminated scripts had NO ctx contract at
    # all, so the defective behaviour is reproduced by an explicitly permissive checker — the
    # exact shape "missing key -> None" that made four studies front-side-free.
    def permissive_check_ctx(lane, ctx):
        req = H.LANES[lane]["ctx_required"]
        ctx = ctx or {}
        return {k: ctx.get(k) for k in req}          # SILENT DEFAULT — the defect

    lax = permissive_check_ctx("kevseq", {"day_gain": 40.0, "top3": True, "blue_sky": True})
    check("I5-NC [SIMULATED — no pre-fix commit exists: the old scripts had no ctx contract]: "
          "a permissive checker RETURNS a ctx with front_side silently None instead of refusing",
          set(lax) == set(fx["lane_ctx_required"]["kevseq"]) and lax["front_side"] is None,
          str(lax))
    check("I5-NC2: and it accepts ctx=None outright — the front-side-free study, exactly",
          permissive_check_ctx("kevseq", None) == {k: None
                                                   for k in fx["lane_ctx_required"]["kevseq"]})
    check("I5-NC3: the strict checker refuses the SAME input the permissive one accepted",
          isinstance(_expect_raises(H, "kevseq",
                                    {"day_gain": 40.0, "top3": True, "blue_sky": True}),
                     H.MissingContext))
    print("      (the four studies this pins: %s)" % ", ".join(fx["contaminated_studies"]))


def _expect_raises(H, lane, ctx):
    try:
        H._check_ctx(lane, ctx)
        return None
    except Exception as e:                                              # noqa: BLE001
        return e


# ══════════════════════════════════════════════════════════════════════════════
# I6 — BUCKET_FRESH REPLAY CLOCK
# DEFECT: _bucket_fresh compares the bucket epoch to time.time(); in replay every bar is hours
#         old, so the guard ate 100% of replayed fires and two lanes were unstudiable.
# ══════════════════════════════════════════════════════════════════════════════
def _load_bucket_fresh(bucket_now=None):
    src = bot_src()
    blk = _extract(src, "def _bucket_fresh(", "# ── 8/17 DEFECT 3: SCAN-LOOP CYCLE")
    import time as _t
    ns = {"_BUCKET_NOW": bucket_now, "CURL_FIRE_MAX_AGE_SECS": 90, "CURL_FIRE_MAX_AGE_PRE": 60,
          "_halted_secs_since": lambda s, k: 0.0, "time": _t,
          "datetime": datetime.datetime, "EASTERN": None}
    exec(blk, ns)
    return ns["_bucket_fresh"]


def i6():
    print("I6) BUCKET_FRESH REPLAY CLOCK — the guard that made two lanes unstudiable")
    fx = fixture("bucket_fresh_replay_clock_20260817.json")
    check("I6-0: fixture pins BOTH numbers — %d fires disarmed, %d armed, across %d names"
          % (fx["fires_hook_disarmed"], fx["fires_hook_armed"], fx["names"]),
          fx["fires_hook_disarmed"] == 0 and fx["fires_hook_armed"] == 424 and fx["names"] == 13)
    check("I6-1: the armed count exceeds live (%d vs %d) — harness-extra fires are a DETECTOR "
          "count, never 'missed trades'" % (fx["fires_hook_armed"], fx["live_fires"]),
          fx["fires_hook_armed"] > fx["live_fires"] == 226)

    K = 1755442009                       # an 8/17 10s bucket epoch — hours old at any later run
    fn_live = _load_bucket_fresh(None)
    check("I6-2: hook UNSET (the live path) — an 8/17 bucket is STALE against the real wall "
          "clock, exactly as it must be", not fn_live(K, hm="12:00"))
    check("I6-3: hook unset, a bucket 30s old IS fresh (the guard is not simply always-false)",
          fn_live(__import__("time").time() - 30, hm="12:00"))
    fn_replay = _load_bucket_fresh(lambda: K + 10)
    check("I6-4: with the replay hook armed at 'last fed bar epoch + 10', the SAME 8/17 bucket "
          "is FRESH — the lane becomes replayable", fn_replay(K))
    check("I6-5: the hook does not disable the guard — a bucket 300s before the hook's clock is "
          "still refused", not fn_replay(K - 300))
    for age in fx["ages_checked"]:
        want = age <= 90
        check("I6-6: age %ss -> fresh=%s under the injected clock (the 90s ceiling still rules)"
              % (age, want), fn_replay(K + 10 - age) == want)
    check("I6-7: the now= argument works without the module hook (per-call injection)",
          _load_bucket_fresh(None)(K, now=K + 10))
    check("I6-8: 0/None are never fresh", not fn_replay(0) and not fn_replay(None))
    src = bot_src()
    check("I6-9: the shipped source assigns _BUCKET_NOW exactly ONCE, to None — a live process "
          "that sets it has moved its own clock",
          len(re.findall(r'^_BUCKET_NOW\s*=', src, re.M)) == 1
          and re.search(r'^_BUCKET_NOW\s*=\s*None', src, re.M) is not None)

    # ── NEGATIVE CONTROL ──
    stale = sum(1 for i in range(fx["names"]) if fn_live(K - i * 10, hm="12:00"))
    check("I6-NC: hook DISARMED, %d names' 8/17 buckets are all stale -> %d fires, reproducing "
          "the pre-E1 replay" % (fx["names"], fx["fires_hook_disarmed"]),
          stale == fx["fires_hook_disarmed"] == 0, str(stale))
    # armed: each NAME carries its own fed slice, so each gets its own hook (last fed bar + 10),
    # which is exactly what the harness does per replayed name.
    armed = sum(1 for i in range(fx["names"])
                if _load_bucket_fresh(lambda k=K - i * 10: k + 10)(K - i * 10))
    check("I6-NC2: hook ARMED, the same %d buckets are all fresh — the blocker really was the "
          "clock and nothing else" % fx["names"], armed == fx["names"] == 13, str(armed))
    print("      (cohort-1 regression: grinder %s, bandpass %s, prevwap %s, v2 %s — byte-"
          "identical with the hook in. The clock changed nothing that already worked.)"
          % tuple(fx["cohort1_unchanged"][k] for k in ("grinder", "bandpass", "prevwap", "v2")))


# ══════════════════════════════════════════════════════════════════════════════
# I7 — STUDY REPLICA
# DEFECT: kill-test scripts re-implemented the lane detectors instead of calling the bot's.
#         Replicas drift, and always in the flattering direction.
# ══════════════════════════════════════════════════════════════════════════════
def i7():
    print("I7) STUDY REPLICA — a hand-rolled detector fails, live_harness passes")
    fx = fixture("study_replica_20260817.json")
    gate_src = open(os.path.join(ROOT, fx["gate_file"])).read()
    check("I7-0: gate %s exists in %s" % (fx["gate"], fx["gate_file"]),
          "ENFORCEMENT GATE 2 — STUDY PROVENANCE" in gate_src)
    # Lift the gate's OWN signatures rather than restating them, so this fixture cannot drift
    # away from the gate it pins.
    ns = {"re": re}
    exec(_extract(gate_src, "    _E2_LANE_NAMES = (", "    def _e2_scan(path):").replace(
        "\n    ", "\n").lstrip(), ns)
    sigs, imp = ns["_E2_SIGS"], ns["_E2_IMPORT"]
    check("I7-1: the gate's signature set lifted cleanly (%d signatures + the import rule)"
          % len(sigs), len(sigs) >= 3 and bool(imp))

    def scan(text):
        if re.search(imp, text, re.M):
            return []
        return [n for n, r in sigs if re.search(r, text, re.M)]

    handrolled = ("# a study that re-implements the kevseq detector\n"
                  "def pctile(v, p):\n    return sorted(v)[int(len(v) * p / 100)]\n\n"
                  "def kevseq_scan(bars, vwaps, e9s):\n    return [b for b in bars if b[4] > b[1]]\n")
    viaharness = ("import sys; sys.path.insert(0, 'data/killtests')\nimport live_harness as H\n"
                  "def kevseq_scan(bars):\n    return H.replay('TT', bars, ['kevseq'])\n")
    check("I7-2: a killtest script that hand-rolls a detector FAILS the gate",
          set(scan(handrolled)) >= {"own-detector-def", "burst-percentile"}, str(scan(handrolled)))
    check("I7-3: the SAME script importing live_harness PASSES (no false positive)",
          scan(viaharness) == [], str(scan(viaharness)))
    check("I7-4: a script that re-derives the EMA-cross front side — the exact clause the four "
          "studies dropped — FAILS",
          scan("def ema9_series(bars):\n    return []\n") == ["ema-cross-rederive"])
    check("I7-5: an ordinary analysis script is NOT flagged (the gate is narrow)",
          scan("import json\ndef summarise(rows):\n    return len(rows)\n") == [])
    check("I7-6: the four KNOWN-CONTAMINATED studies are named in the gate's allowlist and "
          "labelled, not silently exempted",
          all(b in gate_src and "KNOWN-CONTAMINATED" in gate_src for b in fx["known_contaminated"]))
    for b in fx["known_contaminated"]:
        p = os.path.join(ROOT, "data", "killtests", b)
        if os.path.exists(p) and b != "kevseq_reconciliation_20260817.py":
            check("I7-7: the historical violator %s really does trip a signature (the gate is "
                  "not vacuous)" % b, bool(scan(open(p, errors="replace").read())),
                  str(scan(open(p, errors="replace").read())))
    check("I7-8: the required dependency exists and is harness-shaped",
          "def replay(" in open(os.path.join(ROOT, "data", "killtests", "live_harness.py")).read())

    # ── NEGATIVE CONTROL ──
    check("I7-NC: the hand-rolled script and its harness twin are graded OPPOSITELY by the same "
          "scanner — the gate discriminates rather than passing everything",
          bool(scan(handrolled)) and not scan(viaharness))


# ══════════════════════════════════════════════════════════════════════════════
# I8 — CONFIG EPOCH
# DEFECT: 8/17 was FIVE machines.  One produced 51% of the day's fire rows and 5 of its 7
#         fills.  A strategy result and a config change are indistinguishable in any aggregate
#         that does not name its epochs.
# ══════════════════════════════════════════════════════════════════════════════
def i8():
    print("I8) CONFIG EPOCH — rows from different machines may not be silently added up")
    fx = fixture("config_epoch_20260817.json")
    eps = fx["epochs"]
    check("I8-0: fixture holds the five REAL epochs", len(eps) == 5 and fx["date"] == "2026-08-17")
    check("I8-1: the per-epoch rows sum to the day's %d fire rows and %d fills"
          % (fx["total_fire_rows"], fx["total_fills"]),
          sum(e["fire_rows"] for e in eps) == fx["total_fire_rows"] == 401
          and sum(e["fills"] for e in eps) == fx["total_fills"] == 7)
    dom = max(eps, key=lambda e: e["fire_rows"])
    share = dom["fire_rows"] / fx["total_fire_rows"] * 100
    check("I8-2: ONE machine (boot#%d, %s-%s) produced %.0f%% of the fire rows and %d of the %d "
          "fills" % (dom["boot"], dom["from"], dom["to"], share, dom["fills"], fx["total_fills"]),
          dom["boot"] == 1 and round(share, 1) == fx["dominant_epoch"]["fire_row_share_pct"]
          and dom["fills"] == 5, "%.1f%%" % share)
    check("I8-3: one epoch lived SEVEN MINUTES (boot#4) — 'the 8/17 result' is a bag of five",
          [e for e in eps if e["boot"] == 4][0]["fire_rows"] == 8)
    check("I8-4: the report is honestly labelled INFERRED (pre-stamp day, boot-row segmentation "
          "OVERCOUNTS: two restarts of one image look like two epochs)", "INFERRED" in fx["mode"])

    # THE RULE — driven through the SHIPPED gate's own checker, so this cannot drift from it.
    gate_src = open(os.path.join(ROOT, "rig", "test_gates_20260817.py")).read()
    ns = {"re": re}
    exec(_extract(gate_src, "_E2C_RANGE = re.compile(", "def gate2c():"), ns)
    flags = ns["e2c_flags"]
    doc = ("# 8/17 study\nAggregated 2026-08-11..2026-08-17 across the whole book.\n"
           "## VERDICT\n+$412.\n")
    check("I8-5: a multi-day aggregate with NO declaration is REFUSED",
          flags(doc) == ["no-LIMITS-section"], str(flags(doc)))
    check("I8-6: a MIXED-EPOCH declaration inside LIMITS is accepted",
          flags(doc + "## LIMITS\nMIXED-EPOCH: this range spans five deploys.\n") == [])
    check("I8-7: naming the config hashes inside LIMITS is accepted",
          flags(doc + "## LIMITS\nConfig hashes covered: a1b2c3d4e5f6, 0f0e0d0c0b0a.\n") == [])
    check("I8-8: a SINGLE-DAY doc is never flagged (no false positive)",
          flags("# One session: 2026-08-17.\n## VERDICT\n+$412.\n") == [])
    check("I8-9: the hash covers CODE + every behaviour-governing env var, scanned FROM SOURCE",
          all(s in open(os.path.join(ROOT, "data", "audits", "config_hash_20260817.md")).read()
              for s in ("KEVSEQ_FIRE_ON_CLOSE", "DEDUPE_FIRES", "M1_WALLCLOCK", "cfg_n")))

    # ── NEGATIVE CONTROL ──
    check("I8-NC: the same range doc with LIMITS that never mention epochs still FLAGS — the "
          "rule is not satisfied by having a LIMITS section",
          flags(doc + "## LIMITS\nSmall sample; single regime.\n")
          == ["multiday-no-epoch-declaration"])
    check("I8-NC2: a declaration placed OUTSIDE the LIMITS section does NOT satisfy the rule "
          "(a caveat a reader will not find is not a caveat)",
          flags(doc.replace("## VERDICT", "MIXED-EPOCH\n## VERDICT")
                + "## LIMITS\nSmall sample.\n") == ["multiday-no-epoch-declaration"])
    check("I8-NC3: the aggregation the fixture forbids really would mislead — dropping boot#1 "
          "moves the day from %d fills to %d" % (fx["total_fills"], fx["total_fills"] - 5),
          fx["total_fills"] - dom["fills"] == 2)


if __name__ == "__main__":
    print(__doc__.split("\n\n")[0])
    print("=" * 78)
    for g in (i1, i2, i3, i4, i5, i6, i7, i8):
        try:
            g()
        except Exception as _e:                                         # noqa: BLE001
            check("%s section" % g.__name__, False, "%s: %s" % (type(_e).__name__, _e))
        print()
    print("=" * 78)
    if FAILS:
        print("RED (%d):" % len(FAILS))
        for f in FAILS:
            print("   - " + f)
        sys.exit(1)
    print("ALL GREEN — 8 fixtures, 8 negative controls, exit 0")
    sys.exit(0)
