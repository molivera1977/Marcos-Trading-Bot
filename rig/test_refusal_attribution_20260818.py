#!/usr/bin/env python3
"""
GATE 11 — EVERY REFUSAL ROW MUST NAME ITS LANE (defect opened 8/18)

THE DEFECT
  `momentum_reject` rows carried exactly these fields:
      ['date','price','reason','recorded_at','side','status','ticker','time']
  No lane. No entry_type. So "which lanes is the momentum gate refusing?" could not be
  answered from the archive AT ALL.

WHY IT MATTERED, CONCRETELY
  Ship-review item #3 (TAPE_LANE_SCALAR_EXEMPT) rests on a kill-test of N=1. Measuring the
  archive across 14 sessions (8/17,8/14,8/13,8/12,8/11,8/10,8/08,8/07,8/06,8/05,8/04,7/31,
  7/29,7/28) found 95 momentum_reject rows, of which SEVEN carried the "no momentum build"
  reason the exemption bypasses — PFSA, WETO, MSGY, LZMH, ZCMD, SCYX, FCHL. Six of the seven
  could not be assigned to a lane, and the only one that could (WETO -> kevseq) was
  identifiable solely because a human wrote it into a code comment. The kill-test is N=1
  because of MISSING ATTRIBUTION, not because the population is one.

  A gate whose refusals cannot be attributed cannot be graded, and a gate that cannot be
  graded gets argued about instead of measured. That is the whole pattern this rebuild exists
  to end.

THE CLASS (feedback_kill_the_class_not_instance)
  An AST census of all 47 refusal-row call sites found 28 of 45 refusal STATUSES with no
  lane/machine/entry_type field. momentum_reject was one instance of a wide class. This gate
  pins the class: the unattributed set is FROZEN and may only SHRINK.

WHAT THIS GATE DOES NOT DO
  It does not require attribution where the lane genuinely is not in scope (e.g. _gate_blind's
  own cap row, _reread_on_reject). Those are named in ALLOWED_UNATTRIBUTED with a reason.
  Adding to that list goes RED — a new name requires editing this file, deliberately.

Exit 0 = green.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
TREE = ast.parse(SRC)

LANE_KEYS = {"lane", "machine", "entry_type"}
REFUSAL_WORDS = ("reject", "skip", "block", "refus", "suppress", "denied", "capped", "paused")

# Statuses that legitimately cannot name a lane, each with the reason. MAY ONLY SHRINK.
ALLOWED_UNATTRIBUTED = {
    "gate_blind_capped":   "emitted by _gate_blind itself about its own daily cap — no fire in scope",
    "reread_on_reject":    "map-reread bookkeeping in _reread_on_reject; no entry is being judged",
    "dup_entry_reject":    "execute_trade dedupe — fires before the lane is bound to the ticket",
    "perimeter_refused":   "execute_trade perimeter — same pre-binding position as dup_entry_reject",
}

# The lane-named statuses: the STATUS ITSELF names the lane, so a lane field is redundant.
# (kevseq_reject is a kevseq row by construction.) These are attributable, just not via a field.
SELF_NAMING = ("kevseq", "hidden", "ignition", "grinder", "v2conv", "bandpass", "rocket",
               "ma_pullback", "reclaim", "premkt", "pre_", "stale_swap")

FAILS = []


def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {label}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)
    return ok


def census(tree=None):
    """(lineno, status, has_lane_field) for every refusal-ish _log_decision call."""
    out = []
    for n in ast.walk(tree if tree is not None else TREE):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_log_decision" and len(n.args) >= 2):
            st = n.args[1].value if isinstance(n.args[1], ast.Constant) else None
            if not isinstance(st, str) or not any(w in st for w in REFUSAL_WORDS):
                continue
            kw = {k.arg for k in n.keywords if k.arg}
            out.append((n.lineno, st, bool(kw & LANE_KEYS)))
    return out


def main():
    print("=" * 78)
    print("GATE 11) REFUSAL-ROW LANE ATTRIBUTION (defect opened 8/18)")
    print("=" * 78)

    sites = census()
    check("11.1 census non-trivial", len(sites) >= 40, f"n={len(sites)}")

    by_status = {}
    for ln, st, has in sites:
        by_status.setdefault(st, []).append((ln, has))

    unattributed = {s: [ln for ln, h in v if not h]
                    for s, v in by_status.items() if not all(h for _, h in v)}

    # a status whose NAME contains the lane is attributable without a field
    def self_named(s):
        return any(t in s for t in SELF_NAMING)

    hard = {s: ls for s, ls in unattributed.items()
            if s not in ALLOWED_UNATTRIBUTED and not self_named(s)}

    print(f"\n  refusal statuses: {len(by_status)}   sites: {len(sites)}")
    print(f"  unattributed by field: {len(unattributed)}  "
          f"(self-naming: {sum(1 for s in unattributed if self_named(s))}, "
          f"allow-listed: {sum(1 for s in unattributed if s in ALLOWED_UNATTRIBUTED)})")
    if hard:
        for s, ls in sorted(hard.items()):
            print(f"      UNATTRIBUTED: {s} at {ls}")
    print()

    # (a) THE CLASS-KILLER
    check("11.2 no refusal status is unattributable (class-killer)", not hard,
          f"{sorted(hard)}")

    # (b) the specific rows this defect was opened for
    for st, anchor in [
        ("momentum_reject", '"momentum_reject", price=entry_price, lane=entry_type'),
        ("extension_reject", '"extension_reject", price=b[1], lane=b[3]'),
        ("spread_reject", '"spread_reject", price=entry_price, lane=entry_type'),
        ("l2_reject", '"l2_reject", price=entry_price, lane=entry_type'),
        ("balance_skip", '"balance_skip", price=entry_price, lane=entry_type'),
        ("bad_stop_skip", '"bad_stop_skip", price=entry_price, lane=entry_type'),
        ("wide_stop_reject", '"wide_stop_reject", price=entry_price, lane=entry_type'),
        ("chart_gate_blocked_trade", '"chart_gate_blocked_trade", lane=entry_type'),
        ("pre_capped_at_exec", '"pre_capped_at_exec", price=entry_price, lane=entry_type'),
    ]:
        check(f"11.3 {st} names its lane", anchor in SRC)

    # (c) check_momentum has no lane arg by design — the thread-local must carry it
    check("11.4 ambient_reject (check_momentum twin) carries the thread-local lane",
          'src="check_momentum",\n                          lane=_blind_lane()' in SRC)

    # (d) the allow-list may only shrink
    stale = set(ALLOWED_UNATTRIBUTED) - set(unattributed)
    check("11.5 allow-list has no stale entries (a fixed row must leave the list)",
          not stale, f"now attributed, delete from ALLOWED_UNATTRIBUTED: {sorted(stale)}")

    # (e) NEGATIVE CONTROL — the census must be able to SEE an unattributed row, or this
    #     gate would pass vacuously forever.
    bad = ast.parse('_log_decision(ticker, "zz_synth_reject", price=1.0)')
    got = census(bad)
    check("11.6 NEGATIVE CONTROL — census flags a synthetic unattributed refusal",
          got and got[0][1] == "zz_synth_reject" and got[0][2] is False)
    good = ast.parse('_log_decision(ticker, "zz_synth_reject", price=1.0, lane="grinder")')
    got2 = census(good)
    check("11.7 NEGATIVE CONTROL — an attributed row is not flagged",
          got2 and got2[0][2] is True)

    print()
    if FAILS:
        print("RED: " + ", ".join(FAILS))
        return 1
    print("GATE 11 GREEN — every refusal row can be assigned to a lane.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
