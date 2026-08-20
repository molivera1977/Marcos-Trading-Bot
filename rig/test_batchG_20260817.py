#!/usr/bin/env python3
"""FOUNDATION BATCH G — A FIRE BAR FOR THE LAST THREE LANES (8/17). Gate-5 acceptance tests.

FAILURE CONDITION, WRITTEN FIRST
--------------------------------
This file is WRONG if it can go green while ANY of these is true:
  * a stamped `fire_k` is NOT a real bar epoch from the series the detector read — i.e. it is
    derived from time.time(), from log time, or from a bar the detector never consumed. A
    synthetic bucket is worse than no bucket: it makes tomorrow's age measurement measure the
    logger. The specs below assert each fire_k's PROVENANCE expression, not merely its presence;
  * an age guard is ARMED by default. `LANE_FIRE_AGE_GUARD` must stay empty in the shipped
    source, and every new `_lane_fire_stale` call must therefore be inert on the live path;
  * hidden's `price` field changed. Today's archive and batch E's 5.8% must stay reproducible;
  * `triggered_ma_pullback`'s stamped stop is anything other than the variable the ticket is
    built from (a recomputed or defaulted stop would re-create the phantom-stop defect the
    stamp exists to kill);
  * the EG1 pins for flat_top / crown_seam / halt_ladder were flipped to True without the
    property actually changing — the NEGATIVE CONTROL below grades the PARENT source with the
    SAME computer and requires (b) and (c) to be FALSE there.

Usage (spec_gate contract):
    python3 rig/test_batchG_20260817.py                 run every spec (exit 0 = green)
    python3 rig/test_batchG_20260817.py SPEC_<name>     run one named spec
"""
import os
import re
import subprocess
import sys

os.environ.setdefault("DRY_RUN", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []

# The tree batch G branched from (merge of agent/F, 2026-08-17) — the last commit in which
# flat_top / crown_seam / halt_ladder had no fire bar.  Pinned, never HEAD-relative: see
# SPEC_eg1_pins_flipped_for_a_real_reason.
PRE_G = "3d60126"


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)
    return bool(cond)


def bot_src():
    return open(os.path.join(ROOT, "marcos_trading_bot.py")).read()


def _seg(src, needle, back=1200, fwd=1600):
    i = src.index(needle)
    return src[max(0, i - back): i + fwd]


# ── SPEC 1 (THE GATE-5 ACCEPTANCE) ───────────────────────────────────────────────────────
def SPEC_lane_fire_bars_stamped():
    """Each of the three lanes stamps a REAL fire bar, with its age measured from the bar's
    CLOSE, and calls the shared (disarmed) staleness guard with that same close epoch.

    This is the acceptance: it FAILS at the parent (none of these lanes had a fire bar; batch B
    recorded all three as unstampable) and PASSES at the commit."""
    s = bot_src()
    ok = True

    # ── flat_top: bar = the last completed 3-min SESSION bar the base is read off ──
    ok &= check("flat_top: fire_k is _bar_epoch of the base's last bar (a real bar, not a clock)",
                "_ft_k     = _bar_epoch(_sess3[-1])" in s)
    ok &= check("flat_top: age measured from the bar's CLOSE (+ SETUP_TF_MIN*60), not its open",
                "_ft_kc    = (_ft_k + SETUP_TF_MIN * 60)" in s
                and "_ft_age   = round(time.time() - _ft_kc, 1)" in s)
    ok &= check("flat_top: NO invented fire_px — the bar close is stamped, named for what it is",
                "fire_bar_close=_ft_close" in s and "fire_px=_ft_" not in s)
    ok &= check("flat_top: both fire rows carry age + drift",
                s.count("fire_age_s=_ft_age, drift_pct=_ft_drift") == 2
                and '"break_attack", price=price' in s and '"triggered_flat_top"' in s)
    ok &= check("flat_top: guard wired with the CLOSE epoch",
                '_lane_fire_stale(t, "flat_top", _ft_kc, price)' in s)

    # ── crown_seam: bar = the last 5s bar _seam5_check itself read ──
    ok &= check("crown_seam: detector returns the real last-5s-bar epoch",
                '"fire_k": _ks5[-1], "bar_secs": 5' in s)
    ok &= check("crown_seam: _ks5 IS the sorted key list of the 5s feed the detector priced off",
                "_ks5 = sorted(_f5)" in s and "px = cl[-1]" in s
                and 'cl = [_f5[k]["c"] for k in _ks5]' in s)
    ok &= check("crown_seam: age from the bar close (fire_k + bar_secs)",
                "_ss_age = (round(time.time() - (_ss_k + _ss.get(\"bar_secs\", 5)), 1)" in s)
    ok &= check("crown_seam: row carries fire_px + age + drift; guard wired",
                'fire_px=_ss["price"], fire_age_s=_ss_age' in s
                and '_lane_fire_stale(t, "crown_seam"' in s)

    # ── halt_ladder: bar = the last bar of whichever feed armed the ladder ──
    ok &= check("halt_ladder: fire_k is the last key of the fed bar dict",
                "_hl_k = _hl_ks[-1]" in s and "_hl_ks = sorted(_hl_d10)" in s)
    ok &= check("halt_ladder: cadence MEASURED from the feed (5s vs 10s), never assumed",
                "_hl_cad = (_hl_ks[-1] - _hl_ks[-2]) if len(_hl_ks) >= 2 else 10" in s)
    ok &= check("halt_ladder: age from the bar close; cadence + feed source stamped for audit",
                "_hl_age = round(time.time() - (_hl_k + _hl_cad), 1)" in s
                and "bar_secs=_hl_cad, feed_src=_hl_src" in s)
    ok &= check("halt_ladder: both arm rows stamped; guard wired with the close epoch",
                s.count("fire_age_s=_hl_age, drift_pct=_hl_drift") == 2
                and '_lane_fire_stale(t, "halt_ladder", _hl_k + _hl_cad' in s)
    return ok


# ── SPEC 2 — the guards must be INERT on the live path ───────────────────────────────────
def SPEC_new_guards_are_disarmed_by_default():
    """Every guard added by batch G routes through the ONE shared switch batch B built, and that
    switch ships empty. An age guard REMOVES TRADES; arming one whose cost has never been
    measured is a silent tightening (batch B's stated precedent, held to here)."""
    s = bot_src()
    # 8/19 AMENDMENT: the default arms exactly ONE lane — hidden_v2, armed AT BIRTH per the
    # NEW-LANE CHECKLIST (Marcos 8/17: kevseq shipped without the age guard and cost a full
    # session). Batch B's precedent (never arm a MATURE lane whose suppression cost is
    # unmeasured) is intact: a lane born with the guard removes no trade it ever had. Any
    # OTHER lane appearing in this default is still a RED.
    ok = check("the shared env default arms hidden_v2 at birth and NOTHING else",
               'LANE_FIRE_AGE_GUARD = os.environ.get("LANE_FIRE_AGE_GUARD", "hidden_v2")' in s)
    ok &= check("batch G added no second age env",
                not re.search(r'(FLAT_TOP|FLATTOP|SEAM|CROWN_SEAM|HALT_LADDER)_FIRE_MAX_AGE', s))
    # the mechanism itself: an unarmed lane returns False before it can suppress anything
    blk = _seg(s, "def _lane_fire_stale", back=0, fwd=1400)
    ok &= check("_lane_fire_stale returns False for a lane not named in the guard (unchanged)",
                "if lane not in _LANE_AGE_GUARD:" in blk and "return False" in blk)
    ok &= check("all three new calls are guarded by a real bar epoch (no epoch -> no suppression)",
                '_ft_kc and _lane_fire_stale(t, "flat_top"' in s
                and '_ss_k and _lane_fire_stale(t, "crown_seam"' in s
                and '_hl_k and _lane_fire_stale(t, "halt_ladder"' in s)
    return ok


# ── SPEC 3 — hidden's price stamp (G2) ───────────────────────────────────────────────────
def SPEC_hidden_shadow_fire_stamps_detector_px():
    """hidden_shadow_fire gains the DETECTOR's price as a distinct field while `price` keeps
    carrying the live quote — so batch E's 5.8% stays reproducible against today's archive and
    tomorrow's parity can key on price+stop+time."""
    s = bot_src()
    row = _seg(s, '_log_decision(t, "hidden_shadow_fire"', back=200, fwd=1400)
    ok = check("the row still stamps price=_hpx (the LIVE QUOTE) — unchanged",
               '_log_decision(t, "hidden_shadow_fire", price=_hpx,' in s
               and '_hpx = price if price and price > 0 else _he_fire.get("px") or 0' in s)
    ok &= check("fire_px is the detector's own output, not the quote",
                'fire_px=_he_fire.get("px")' in row)
    ok &= check("hidden_entry_step's px IS the fed bar's close (the provenance that makes it valid)",
                '"px": round(c, 4), "k": k' in s)
    ok &= check("age + drift stamped alongside, from the detector's bucket",
                'fire_k=_he_fire.get("k")' in row and "fire_age_s=" in row and "drift_pct=" in row)
    ok &= check("the lane's other two rows still carry fire_px (this was a ONE-ROW defect)",
                'fire_px=_her.get("px")' in s and "fire_px=he.get(\"px\")" in s)
    return ok


# ── SPEC 4 — ma_pullback's stop (G3) ─────────────────────────────────────────────────────
def SPEC_ma_pullback_row_stamps_its_stop():
    """triggered_ma_pullback logged NO stop, which is why the 8/17 exit study invented one and
    produced 17 phantom 'bad stop' fires. The stamp must be the SAME variable the ticket is
    built from — a recomputed value would re-create the defect in a subtler form."""
    s = bot_src()
    row = _seg(s, '_log_decision(t, "triggered_ma_pullback"', back=100, fwd=900)
    ok = check("the row now stamps a stop", "stop=ma_stop," in row)
    ok &= check("it is the ticket's own variable", 'ma_stop = ma_pb["stop"]' in s
                and '"ema_stop": ma_stop' in s)
    ok &= check("no stop is recomputed or defaulted at the row",
                "stop=round(" not in row and "stop=ma_pb" not in row)
    ok &= check("fire_age_s rides the existing C1 bucket, measured from the candle's CLOSE",
                'ma_pb["k"] + SETUP_TF_MIN * 60' in row)
    return ok


# ── SPEC 5 — THE NEGATIVE CONTROL for the EG1 pin flips ──────────────────────────────────
def SPEC_eg1_pins_flipped_for_a_real_reason():
    """Grade the PARENT source with the SAME property computer the shipset gate uses. The three
    lanes' (b) and (c) must be FALSE there and TRUE at HEAD. Without this, flipping a pin from
    OPEN to True is an unfalsifiable edit."""
    try:
        # A PINNED SHA, not HEAD / HEAD~1. This control must name the exact pre-batch-G tree, or
        # it stops meaning anything the moment another commit lands on top: HEAD~1 quietly
        # becomes batch G itself and the control inverts. 3d60126 is the base batch G branched
        # from (the agent/F merge) — the last tree in which none of these lanes had a fire bar.
        parent = subprocess.run(["git", "-C", ROOT, "show", f"{PRE_G}:marcos_trading_bot.py"],
                                capture_output=True, text=True, check=True).stdout
    except Exception as e:                                              # noqa: BLE001
        return check("parent source retrievable", False, f"{type(e).__name__}: {e}")

    # the shipset's computer, reduced to the two properties this batch closed, verbatim in form
    def props(src, lane, token, has_fn):
        b = (not has_fn) and (f'_lane_fire_stale(t, "{lane}"' in src)
        c = False
        for m in re.finditer(r"fire_age_s", src):
            seg = src[max(0, m.start() - 700): m.start() + 700]
            if "drift_pct" in seg and token in seg:
                c = True
                break
        return b, c

    LANES = {"flat_top": "_ft_age", "crown_seam": "_ss[", "halt_ladder": "_hl_px"}
    head = bot_src()
    ok = True
    for lane, tok in LANES.items():
        pb, pc = props(parent, lane, tok, has_fn=False)
        hb, hc = props(head, lane, tok, has_fn=False)
        ok &= check(f"{lane}: (b) fire-age guard was ABSENT at the parent", not pb)
        ok &= check(f"{lane}: (c) drift+age stamps were ABSENT at the parent", not pc)
        ok &= check(f"{lane}: (b) present at HEAD", hb)
        ok &= check(f"{lane}: (c) present at HEAD", hc)
    # and the pins in the shipset actually say True now (the two halves must agree)
    pin = open(os.path.join(ROOT, "rig", "test_shipset_20260804.py")).read()
    for lane in LANES:
        ok &= check(f"{lane}: EG1 pin updated (b/c True, a/g still None)",
                    re.search(r'"%s":\s*\{"a": None, "b": True, "c": True, .*"g": None\}' % lane,
                              pin) is not None)
    return ok


# ── SPEC 6 — nothing here is a behaviour change on the default path ─────────────────────
def SPEC_no_default_behaviour_change():
    """The whole batch is row fields plus disarmed guards. The gates, levels, stops and
    conversion conditions of all five touched lanes must be textually untouched."""
    s = bot_src()
    ok = check("flat_top: the attack condition and stop are unchanged",
               '_ft_attack = (_ftd["action"] == "attack")' in s
               and "_stop = _ft_attack_stop(w_low)" in s)
    ok &= check("crown_seam: the convert condition is unchanged",
                "if SEAM_CONVERT and float(_ss['stop']) < float(_ss['price']):" in s)
    ok &= check("halt_ladder: the convert condition is unchanged",
                "if HALT_LANE_CONVERT and _hl_go and _hl_stop and _hl_stop < _hl_px:" in s)
    ok &= check("hidden: the shadow row still writes nothing but a row",
                "_log_decision(t, \"hidden_shadow_fire\"" in s)
    ok &= check("ma_pullback: the ticket is built from the same values",
                '"ema_stop": ma_stop, "prior_high": target' in s)
    ok &= check("no new env var was introduced by batch G",
                not re.search(r'os\.environ\.get\("(LANE_FIRE_BAR|FIRE_BAR|G1_|G2_|G3_)', s))
    return ok


SPECS = {
    "SPEC_lane_fire_bars_stamped": SPEC_lane_fire_bars_stamped,
    "SPEC_new_guards_are_disarmed_by_default": SPEC_new_guards_are_disarmed_by_default,
    "SPEC_hidden_shadow_fire_stamps_detector_px": SPEC_hidden_shadow_fire_stamps_detector_px,
    "SPEC_ma_pullback_row_stamps_its_stop": SPEC_ma_pullback_row_stamps_its_stop,
    "SPEC_eg1_pins_flipped_for_a_real_reason": SPEC_eg1_pins_flipped_for_a_real_reason,
    "SPEC_no_default_behaviour_change": SPEC_no_default_behaviour_change,
}


def run_one_spec(name):
    fn = SPECS.get(name)
    if fn is None:
        print("UNKNOWN SPEC %r — registered: %s" % (name, ", ".join(sorted(SPECS))))
        return 2
    try:
        ok = bool(fn())
    except Exception as e:                                              # noqa: BLE001
        print("%s RAISED %s: %s" % (name, type(e).__name__, e))
        return 1
    print("%s: %s" % (name, "PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("SPEC_"):
        return run_one_spec(sys.argv[1])
    print("=" * 78)
    print("FOUNDATION BATCH G — fire bars for flat_top / crown_seam / halt_ladder (8/17)")
    print("=" * 78)
    for n, f in SPECS.items():
        print(n)
        try:
            check(n, bool(f()))
        except Exception as e:                                          # noqa: BLE001
            check(n, False, "%s: %s" % (type(e).__name__, e))
    print("BATCH G: " + ("ALL GREEN" if not FAILS else "RED: " + ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
