#!/usr/bin/env python3
"""GATE 6 — CLAIM-WITHOUT-CHECK DETECTOR (built 8/17).

WHAT IT DOES
------------
Scans a Claude Code session transcript (JSONL) and flags assistant statements that assert a
NUMERIC FACT ABOUT THE SYSTEM whose number appears NOWHERE in the evidence the same turn
actually produced.

THE MECHANISM: TOKEN GROUNDING (not "was a tool called?")
---------------------------------------------------------
The naive detector — "flag claims with no preceding tool_use" — is useless here.  Measured on
the 8/17 transcript, every one of the four known-false claims had tool calls earlier in its
turn (1 to 7 of them).  Tool-call PRESENCE proves nothing.

So the check is stronger and much more precise: for every claim-shaped numeric token in an
assistant text block, ask whether THAT LITERAL NUMBER appears anywhere in the tool_use inputs
or tool_result outputs produced EARLIER IN THE SAME TURN.  A number that never came out of a
tool this turn was carried in from memory or invented.  That is a claim without a check.

Grounding is deliberately GENEROUS (the number need only appear somewhere in the turn's
evidence, in any context) because the goal is precision: a flag should be very hard to argue
with.  Recall is knowingly sacrificed.

TWO CLASSES, REPORTED SEPARATELY
--------------------------------
  UNGROUNDED_NUMBER  (high confidence)  — the number is absent from the turn's evidence.
  CAUSAL_DIAGNOSIS   (low confidence)   — a named mechanism is asserted to be the CAUSE of an
                                          outcome ("the runway gate is the villain", "X killed
                                          the trade") with no decision-row evidence in the turn.
                                          Advisory only; noisier by construction, and labelled so.

WHAT IT CANNOT CATCH (stated honestly — see the validation block at the bottom of this file)
--------------------------------------------------------------------------------------------
It catches WRONG NUMBERS, not WRONG MEANINGS.  The 8/17 "$604 balance" claim quoted a number
that WAS in the tool output — `ACCOUNT_BALANCE=604.16` really is in the deployed env.  The
error was semantic: DRY_RUN uses SIM_ACCOUNT_BALANCE=3000 instead, so the right number was
attached to the wrong variable.  No grounding detector can see that.  Gate 5 (spec-as-failing-
test) and Gate 7 (decision reconciler) are the mechanisms for that failure class.

USAGE
-----
    python3 data/audits/claim_audit.py <transcript.jsonl>
    python3 data/audits/claim_audit.py <transcript.jsonl> --day 2026-08-17
    python3 data/audits/claim_audit.py <transcript.jsonl> --day 2026-08-17 --json out.json
    python3 data/audits/claim_audit.py <transcript.jsonl> --day 2026-08-17 --include-diagnosis
    python3 data/audits/claim_audit.py --self-test          # the 8/17 validation, no args

Transcripts live at ~/.claude/projects/<slug>/*.jsonl.
Exit 0 always for a scan (it is a REPORT, not a gate on the build); --self-test exits non-0 if
the validated catch rate regresses.
"""
import argparse
import json
import os
import re
import sys

# ── system vocabulary: a claim must be ABOUT THE MACHINE, not about the world ────────────
SYSTEM_NOUNS = re.compile(
    r"\b(bot|machine|gate|gates|lane|lanes|slot|slots|entry|entries|exit|exits|trade|trades|"
    r"fill|fills|trigger|triggers|fire|fires|bar|bars|tick|ticks|row|rows|cap|caps|balance|"
    r"position|positions|deployed|env|config|rig|commit|code|line|lines|stop|stops|runway|"
    r"chart|crown|halt|halts|read|reads|map|maps|session|sessions|refus|reject|veto|"
    r"kevseq|ignition|prevwap|grinder|bandpass|v2conv|hidden|reclaim|zone_flip|dip_rip|"
    r"vwap|ema|premarket|RTH|PRE|P&L|expectancy|median|mean|win rate|R\b)", re.I)

# hedges / non-assertions — a sentence carrying one of these is NOT a stated fact
HEDGE = re.compile(
    r"\b(if|would|should|could|might|may|maybe|probably|likely|perhaps|suppose|assume|"
    r"propose|proposal|recommend|suggest|plan|let me|i'll|i will|going to|next|tonight|"
    r"tomorrow|queued|pending|draft|about to|intend|want to|need to|unless|whether|"
    r"question|unclear|unknown|unverified|guess|hypothes|estimat|roughly|approx|~|"
    r"i was wrong|i'm wrong|retract|correct(ing|ion|ed)? myself|my error|i said .* wrong|"
    r"you're right|apolog)", re.I)

# a claim must SOUND stated-as-fact
ASSERTIVE = re.compile(
    r"\b(is|are|was|were|has|have|had|does|did|shows?|showed|ran|runs|fired|filled|took|"
    r"consumed|spent|blocked|refused|rejected|passed|failed|verified|confirmed|proven|"
    r"deployed|live|set to|equals?|totall?ed|came to|means?|because|so\b)", re.I)

# ── claim-shaped numeric tokens ─────────────────────────────────────────────────────────
TOKEN_PATTERNS = [
    ("money",   re.compile(r"[-+−]?\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|K|m|M)?")),
    ("percent", re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*%")),
    ("ofN",     re.compile(r"\b([0-9][0-9,]*)\s*(?:of|/)\s*([0-9][0-9,]*)\b")),
    ("assign",  re.compile(r"\b([A-Z][A-Z0-9_]{3,})\s*=\s*([0-9][0-9,]*(?:\.[0-9]+)?)")),
    ("counted", re.compile(r"\b([0-9][0-9,]*(?:\.[0-9]+)?)[\s-]+(?=" + SYSTEM_NOUNS.pattern[2:] + r")", re.I)),
]
# integers this small are ordinals, list markers, "1-min", "two of three" prose — never claims
TRIVIAL = {"0", "1", "2", "3"}
# ...unless the sentence attaches them to a countable system resource, which is exactly the
# shape of the 8/17 "2 slots" error.  These nouns re-admit small integers.
SMALL_OK = re.compile(r"\b(slot|slots|position|positions|fill|fills|trade|trades|"
                      r"minute|minutes|min\b|cap|caps|concurrent)\b", re.I)

CAUSAL = re.compile(
    r"\b(villain|culprit|to blame|the cause|caused|killed (it|the|this)|blocked (it|the|this)|"
    r"is why|that's why|the reason (it|the|this)|responsible for)\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*`\[#—-])|\n+")


def _num(s):
    return (s or "").replace(",", "").rstrip(".").lstrip("0") or "0"


# ── transcript parsing ───────────────────────────────────────────────────────────────────
def _is_human(rec):
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return True
    if isinstance(c, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
    return False


def _flat(x):
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return " ".join(_flat(i) for i in x)
    if isinstance(x, dict):
        return " ".join(_flat(v) for v in x.values())
    return str(x)


def load_turns(path, day=None):
    """-> [ {ts, blocks:[(kind, payload)]} ] where kind is 'text' | 'evidence'."""
    recs = []
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except (ValueError, TypeError):
                continue
            if d.get("type") in ("user", "assistant"):
                recs.append(d)
    turns, cur = [], None
    for d in recs:
        if _is_human(d):
            cur = {"ts": str(d.get("timestamp") or ""), "blocks": []}
            turns.append(cur)
        if cur is None:
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            k = b.get("type")
            if k == "text" and d.get("type") == "assistant":
                cur["blocks"].append(("text", b.get("text") or "", str(d.get("timestamp") or "")))
            elif k == "tool_use":
                cur["blocks"].append(("evidence", _flat(b.get("input")), ""))
            elif k == "tool_result":
                cur["blocks"].append(("evidence", _flat(b.get("content")), ""))
    if day:
        keep = []
        for t in turns:
            if any(ts.startswith(day) for (_k, _p, ts) in t["blocks"] if _k == "text"):
                keep.append(t)
        turns = keep
    return turns


# ── the scan ─────────────────────────────────────────────────────────────────────────────
def _tokens(sentence):
    """-> [(kind, literal, normalized)] claim-shaped numbers in this sentence."""
    out = []
    for kind, pat in TOKEN_PATTERNS:
        for m in pat.finditer(sentence):
            groups = [g for g in m.groups() if g and re.match(r"^[0-9]", g)]
            for g in groups:
                n = _num(g)
                if n in TRIVIAL and not SMALL_OK.search(sentence):
                    continue
                if len(n) == 1 and kind == "counted" and not SMALL_OK.search(sentence):
                    continue
                out.append((kind, m.group(0).strip(), n))
    return out


def scan(turns, include_diagnosis=False):
    findings = []
    for ti, turn in enumerate(turns):
        evidence = []
        for kind, payload, ts in turn["blocks"]:
            if kind == "evidence":
                evidence.append(payload)
                continue
            blob = "\n".join(evidence)
            nums_seen = set(_num(x) for x in re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?", blob))
            for sent in SENT_SPLIT.split(payload):
                s = sent.strip()
                if len(s) < 25 or len(s) > 600:
                    continue
                if not SYSTEM_NOUNS.search(s) or not ASSERTIVE.search(s):
                    continue
                if HEDGE.search(s):
                    continue
                if s.lstrip().startswith(">"):          # quoting the user
                    continue
                bad = []
                for kind_t, lit, n in _tokens(s):
                    if n in nums_seen:
                        continue
                    # a decimal is grounded if its integer part is present (rounding in prose)
                    if "." in n and _num(n.split(".")[0]) in nums_seen:
                        continue
                    bad.append((kind_t, lit, n))
                if bad:
                    findings.append({
                        "class": "UNGROUNDED_NUMBER", "turn": ti, "ts": ts,
                        "tokens": [{"kind": k, "literal": l, "value": n} for k, l, n in bad],
                        "n_evidence_blocks": len(evidence),
                        "sentence": re.sub(r"\s+", " ", s)[:400],
                    })
                elif include_diagnosis and CAUSAL.search(s) and not bad:
                    if not re.search(r"decision|_log_decision|row|rows|query|grep|ledger", blob[-20000:], re.I):
                        findings.append({
                            "class": "CAUSAL_DIAGNOSIS", "turn": ti, "ts": ts, "tokens": [],
                            "n_evidence_blocks": len(evidence),
                            "sentence": re.sub(r"\s+", " ", s)[:400],
                        })
    return findings


def report(findings, out=sys.stdout):
    hi = [f for f in findings if f["class"] == "UNGROUNDED_NUMBER"]
    lo = [f for f in findings if f["class"] == "CAUSAL_DIAGNOSIS"]
    print("CLAIM AUDIT — %d flagged (%d ungrounded-number, %d causal-diagnosis)"
          % (len(findings), len(hi), len(lo)), file=out)
    for f in findings:
        toks = ", ".join("%s=%s" % (t["kind"], t["literal"]) for t in f["tokens"]) or "—"
        print("\n  [turn %d] %s  %s\n    ungrounded: %s  (evidence blocks in turn: %d)\n    %s"
              % (f["turn"], f["ts"][:19], f["class"], toks, f["n_evidence_blocks"], f["sentence"]),
              file=out)


# ── VALIDATION against the 8/17 transcript (the four known-false claims) ─────────────────
# Ground truth, from Claude's own retractions on 8/17:
#   1. "$604 balance"                 — 14:34:11  claimed ACCOUNT_BALANCE=604.16 governs sizing
#   2. "2 slots"                      — 14:30:42  claimed the machine runs a 2-slot book
#   3. "3-minute front-side defect"   — 18:23:53  claimed the kevseq caller feeds a 3-min front side
#   4. "the runway gate is the villain" — 16:00:03 causal diagnosis, later refuted
KNOWN_FALSE = [
    ("$604 balance",                 "2026-08-17T14:34:11"),
    ("2 slots",                      "2026-08-17T14:30:42"),
    ("3-minute front-side defect",   "2026-08-17T18:23:53"),
    ("runway gate is the villain",   "2026-08-17T16:00:03"),
]
DEFAULT_TRANSCRIPT = os.path.expanduser(
    "~/.claude/projects/-Users-marcosolivera-Desktop-website-data/"
    "add2ac85-fd80-47f7-b583-bda802f0544d.jsonl")
# Measured 8/17 (see BUILD_GATES_20260817.md). Regression floor for --self-test.
EXPECTED_CATCHES = 2


def self_test(path=None, verbose=True):
    path = path or DEFAULT_TRANSCRIPT
    if not os.path.exists(path):
        print("SELF-TEST SKIPPED — transcript not present: %s" % path)
        return 0
    turns = load_turns(path, day="2026-08-17")
    findings = scan(turns, include_diagnosis=True)
    caught = 0
    for label, ts in KNOWN_FALSE:
        hits = [f for f in findings if f["ts"].startswith(ts)]
        got = bool(hits)
        caught += got
        if verbose:
            print("  %s %-30s %s" % ("✅ CAUGHT " if got else "❌ MISSED ", label,
                                     (hits[0]["class"] + ": " + hits[0]["sentence"][:110]) if got else ""))
    print("  CATCH RATE: %d of %d known-false claims" % (caught, len(KNOWN_FALSE)))
    print("  total flags on 8/17: %d over %d turns" % (len(findings), len(turns)))
    ok = caught >= EXPECTED_CATCHES
    print("  SELF-TEST %s (floor %d)" % ("PASS" if ok else "REGRESSED", EXPECTED_CATCHES))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="GATE 6 — claim-without-check detector")
    ap.add_argument("transcript", nargs="?")
    ap.add_argument("--day", help="restrict to assistant turns on this YYYY-MM-DD")
    ap.add_argument("--json", help="write findings to this path")
    ap.add_argument("--include-diagnosis", action="store_true",
                    help="also emit the low-confidence CAUSAL_DIAGNOSIS class")
    ap.add_argument("--self-test", action="store_true",
                    help="run the 8/17 validation and report the catch rate")
    a = ap.parse_args()
    if a.self_test:
        return self_test(a.transcript)
    if not a.transcript:
        ap.error("transcript path required (or use --self-test)")
    turns = load_turns(a.transcript, day=a.day)
    findings = scan(turns, include_diagnosis=a.include_diagnosis)
    report(findings)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(findings, fh, indent=1)
        print("\n  wrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
