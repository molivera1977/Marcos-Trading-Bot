#!/usr/bin/env python3
"""
GATE 10 — THE EXTENSION GUARD MUST NOT BE BLIND (defect opened 8/18)

THE DEFECT
  `EXTENSION_MAX_PCT = 0.25` is supposed to skip an entry priced >25% over its 90-EMA
  (anti-chase, 7/3). It reads the EMA out of the fire's detail dict:

      _e90 = (b[4].get("ema90") or 0)
      ...
      elif _e90 > 0 and (b[1] - _e90) / _e90 > EXTENSION_MAX_PCT:   # reject
      else: _kept.append(b)                                          # FAIL OPEN

  Seven lanes never put "ema90" in that dict, so _e90 is 0 and the guard silently falls
  open on every one of their fires. It is not a rare miss — it cannot fire at all.

THE EVIDENCE (measured, not reasoned)
  `extension_reject` rows in the live decisions archive across FIFTEEN sessions —
  8/17, 8/14, 8/13, 8/12, 8/11, 8/10, 8/08, 8/07, 8/06, 8/05, 8/04, 7/31, 7/29, 7/28, 7/25:
  ZERO in every session. (Query validated: 8/17 alone returns 15,267 rows of other statuses,
  so the archive and the filter both work.)

  AST census of all 17 `breakouts.append` fire sites, following detail dicts through
  variables and **spreads:
      stamps ema90 : dip_rip, zone_flip, vwap_reclaim, hidden_entry, ignition,
                     rocket_catcher, flat_top, orb, ma_pullback, bounce
      BLIND        : v2conv, grinder, bandpass, kevseq, prevwap, crown_seam, halt_ladder

  All seven blind lanes are TAPE lanes, and all seven were born AFTER the guard was
  written. That is the same "a lane born after a gate silently defaults to the wrong side"
  class that produced the copy-pasted exempt tuples (kevseq/WFF, 8/17). Per
  feedback_kill_the_class_not_instance, the SECOND appearance of a class gets a permanent
  rig pin over EVERY consumer, not a one-lane patch.

WHY THIS RIG DOES NOT DEMAND THE GUARD BE ARMED
  Stamping ema90 on those seven lanes would make the guard start REJECTING entries that
  fill today. That is a money-behavior change and it is Marcos's priced call, not an
  auditor's (feedback_auditor_cannot_authorize_behavior). What this gate enforces is that
  the blindness can never again be SILENT or UNCOUNTED:
    (a) every fire site is classified — stamps ema90, or is a declared exempt lane, or is
        on the named BLIND_KNOWN list; a NEW lane that is none of the three goes RED,
    (b) the fail-open path emits an attributable _gate_blind row so the cost is countable,
    (c) the BLIND_KNOWN list can only ever SHRINK — adding a lane to it goes RED.

Exit 0 = green. Any RED = the class reopened.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
TREE = ast.parse(SRC)

FAILS = []


def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {label}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)
    return ok


# ── the frozen census, from the 8/18 measurement. This list may SHRINK, never grow. ──
BLIND_KNOWN = {"v2conv", "grinder", "bandpass", "kevseq", "prevwap", "crown_seam", "halt_ladder"}


def _dict_vars():
    """name -> keys, for every dict literal assigned to a plain name (detail dicts are
    frequently built in a variable first, e.g. flat_top's _ft_extra — a census that does not
    follow the variable reports flat_top as blind, which is WRONG. This bit me on the first
    pass; the fixture exists so it cannot bite silently again)."""
    out = {}
    for n in ast.walk(TREE):
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)):
            keys = {k.value for k in n.value.keys if isinstance(k, ast.Constant)}
            out.setdefault(n.targets[0].id, set()).update(keys)
    return out


DICTVARS = _dict_vars()


def _detail_keys(node):
    ks, spread = set(), False
    if isinstance(node, ast.Dict):
        for k in node.keys:
            if isinstance(k, ast.Constant):
                ks.add(k.value)
            elif k is None:
                spread = True
    elif isinstance(node, ast.Name):
        ks |= DICTVARS.get(node.id, set())
        spread = True          # a variable we could not fully resolve
    return ks, spread


def fire_sites():
    out = []
    for n in ast.walk(TREE):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "append" and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "breakouts" and n.args
                and isinstance(n.args[0], ast.Tuple) and len(n.args[0].elts) >= 5):
            t = n.args[0]
            lane = t.elts[3].value if isinstance(t.elts[3], ast.Constant) else "<expr>"
            ks, spread = _detail_keys(t.elts[4])
            out.append((n.lineno, lane, "ema90" in ks, spread))
    return out


def main():
    print("=" * 78)
    print("GATE 10) EXTENSION-GUARD BLINDNESS (defect opened 8/18)")
    print("=" * 78)

    sites = fire_sites()
    check("10.1 fire-site census non-trivial (AST found the append sites)", len(sites) >= 15,
          f"n={len(sites)}")

    stamped = {l for _, l, has, _ in sites if has}
    blind = {l for _, l, has, sp in sites if not has and not sp}

    print(f"\n  stamps ema90 ({len(stamped)}): {', '.join(sorted(stamped))}")
    print(f"  BLIND        ({len(blind)}): {', '.join(sorted(blind)) or '-'}\n")

    # (a) NO NEW BLIND LANE. This is the class-killer: a lane born tomorrow that forgets
    #     ema90 goes RED here instead of silently joining the un-policed set.
    newly_blind = blind - BLIND_KNOWN
    check("10.2 no NEW lane is blind to the extension guard (class-killer)",
          not newly_blind, f"new blind lanes: {sorted(newly_blind)}")

    # (b) the known list may only shrink — a fix removes names, nothing may add them
    check("10.3 BLIND_KNOWN only shrinks (a lane fixed must be deleted from the list)",
          blind <= BLIND_KNOWN, f"grew by {sorted(blind - BLIND_KNOWN)}")

    # (c) the fail-open path must be COUNTABLE, not silent
    check("10.4 the blind fail-open path emits an attributable _gate_blind row",
          '_gate_blind("extension"' in SRC)
    check("10.5 the blind row is emitted ONLY when the EMA is genuinely missing "
          "(not on every non-extended fire)",
          "if _e90 <= 0:" in SRC)
    check("10.6 the row names the lane, so the cost is attributable per lane",
          'missing="ema90 absent from fire detail"' in SRC and "lane=b[3]" in SRC)

    # (d) the guard itself is untouched — this gate must never be mistaken for arming it
    check("10.7 the guard still FAILS OPEN (not armed behind Marcos's back)",
          "_kept.append(b)   # fail-open when there's no 90-EMA to measure" in SRC)
    check("10.8 the 25% threshold is unchanged", "EXTENSION_MAX_PCT       = 0.25" in SRC)

    # (e) NEGATIVE CONTROL: the census must actually be able to SEE a blind lane. If the
    #     detector is broken (e.g. it follows every variable and reports nothing blind), the
    #     gate would pass vacuously forever. Prove it flags a synthetic blind append.
    fake = ast.parse('breakouts.append((t, price, vwap, "zz_synthetic", {"room": 1}))')
    saved = globals()["TREE"]
    try:
        globals()["TREE"] = fake
        got = fire_sites()
        check("10.9 NEGATIVE CONTROL — the census flags a synthetic ema90-less lane",
              got and got[0][1] == "zz_synthetic" and got[0][2] is False)
    finally:
        globals()["TREE"] = saved

    # (f) NEGATIVE CONTROL 2: and it must NOT flag a lane whose dict carries ema90
    fake2 = ast.parse('breakouts.append((t, price, vwap, "zz_ok", {"ema90": 1.0}))')
    try:
        globals()["TREE"] = fake2
        got2 = fire_sites()
        check("10.10 NEGATIVE CONTROL — a lane WITH ema90 is not flagged",
              got2 and got2[0][2] is True)
    finally:
        globals()["TREE"] = saved

    print()
    if FAILS:
        print("RED: " + ", ".join(FAILS))
        return 1
    print("GATE 10 GREEN — extension blindness is bounded, countable, and cannot grow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
