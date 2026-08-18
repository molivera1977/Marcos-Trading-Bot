#!/usr/bin/env python3
"""GATE 8 — THE ARTIFACT-CLAIM VERIFICATION GATE (built 8/17, batch H).

WHY THIS EXISTS
---------------
Three false load-bearing claims shipped on 8/17.  Every one of them lived in a **killtest
artifact**, not in chat, and every one was caught only by a LATER agent reading the doc:

  1. `harness_lift_remaining_20260817.md` — "Same 11 harness fires — but on **entirely
     different names** (was RPGL/WFF, now IPST/IVF/PFSA)."  FALSE.  The bisect showed the
     same 11 names, same 11 bar epochs, same 11 stops.  Only the PRICE moved.
  2. same doc — "**Proven independent of batch E.**  The identical 0.0% comes out running the
     same script against the **HEAD bot source**..."  That run is IMPOSSIBLE as described:
     `_install_bar_clock()` at HEAD raises `NotIsolable` against any pre-E tree.  Conclusion
     right, stated evidence fabricated.
  3. `breakattack_extraction_20260817.md` (batch D) — a mechanism stated from READING code
     rather than executing it.

GATE 6 (`claim_audit.py`) catches this class in CHAT TRANSCRIPTS at 3/4.  Nothing checked
ARTIFACTS, which is where all three of these lived.

THE MECHANISM: PARAGRAPH-SCOPED EVIDENCE, AND ONLY *NAMED* EVIDENCE COUNTS
--------------------------------------------------------------------------
Gate 6 grounds a NUMBER against tool output from the same turn.  An artifact has no turns, so
the analogue here is: does the claim's own paragraph NAME the thing that produced it?

  * A **reproduce command** (`python3 data/killtests/x.py`, `pytest`, `curl /api/...`)
  * A **runnable script or output artifact** by path (`..._out.json`, `..._run.txt`, `*.py`)
  * A **rig spec name** (`SPEC_foo`, `rig/test_bar.py`)
  * A **commit sha** in backticks
  * An **adjacent table or code fence** (the numbers are literally shown)

What deliberately does NOT count: a bare `.md` filename, a vague noun phrase ("the cohort-1
parity script", "the same script", "the HEAD bot source").  That distinction is the whole
gate.  Instance 1 and instance 2 above both said "the script" without naming it; the true,
bisected paragraph three inches below names commit `2d0a6cb` and grounds cleanly.  The gate is
literally the difference between naming your evidence and gesturing at it.

FOUR CLAIM CLASSES
------------------
  (a) NUMERIC       N, %, $, counts, parity rates                      report-only
  (b) EQUIVALENCE   "identical", "byte-identical", "unchanged",        GATED
                    "entirely different", "same X"
  (c) PROVENANCE    "proven", "verified", "measured", "confirmed",     GATED
                    "independent of X"
  (d) NEGATIVE      "no X exists", "zero", "never"                     report-only

Only (b) and (c) are gated — they are the two that burned us, and they are the two where
"name the command" is an unambiguous, arguable-with-nobody requirement.  (a) and (d) are far
noisier in this corpus (every LIMITS section is full of honest negatives) and gating them
would produce a gate people route around.  Precision over recall, same doctrine as Gate 6.

THREE VERDICTS
--------------
  GROUNDED      named evidence in scope
  ASSERTED      no named evidence in scope — "produce the command or tag it [UNVERIFIED]"
  CONTRADICTED  the sentence says identical/unchanged while carrying two DIFFERENT numbers
                joined by vs/versus/against/→ (rare, high-signal, report-only)

SCOPE RULES (why they are what they are)
----------------------------------------
Evidence scope is the claim's own paragraph block, plus any code fence or table IMMEDIATELY
adjacent to it (before or after).  Not the whole section: instance 1 sits in a section that
later acquired a superseding blockquote carrying a commit sha, and a section-wide scope would
let that sha launder the false paragraph three blocks above it.

ONE EXCEPTION — RESTATEMENT SECTIONS.  Headings matching VERDICT / SUMMARY / LIMITS / CAVEATS
/ FAILURE CONDITION / WHAT REMAINS restate what the body already proved; requiring them to
re-cite is pure noise.  There, evidence may come from ANYWHERE in the document.  They are
still checked — a doc with no named evidence anywhere still fails there — just not required
to repeat the citation.

EXEMPTIONS
----------
  * an explicit `[UNVERIFIED]` tag on the sentence or its paragraph
  * a hedge/conditional ("if", "would", "must", "should", "if someone can") — FAILURE
    CONDITION sections are written entirely in the conditional and are not assertions
  * a strikethrough / SUPERSEDED / RESOLVED marker on the paragraph
  * blockquoted text that quotes a prior document

USAGE
-----
    python3 data/audits/artifact_claims.py <doc.md> [more.md ...]
    python3 data/audits/artifact_claims.py <doc.md> --json out.json
    python3 data/audits/artifact_claims.py <doc.md> --classes b,c
    python3 data/audits/artifact_claims.py --self-test     # the three known instances
    python3 data/audits/artifact_claims.py --gate <doc.md> ...   # exit 1 on ASSERTED (b)/(c)

Exit 0 for a scan (it is a REPORT).  `--gate` exits 1 on any ASSERTED equivalence/provenance
claim.  `--self-test` exits non-0 if the validated catch rate regresses.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# ── (b) EQUIVALENCE / DIFFERENCE ────────────────────────────────────────────────────────
EQUIV = re.compile(
    r"\b(byte-identical|byte-for-byte|identical|unchanged|untouched|equivalent|equivalence|"
    r"entirely different|no different|indistinguishable|exactly the same|"
    # "the same X" is only an EQUIVALENCE CLAIM when it compares two things.  Bare "the same
    # trailing p75" in a variant DEFINITION is not a claim about anything, and gating it was
    # the single false positive the control docs produced.  Require a comparison marker.
    r"(?:the )?same (?:\d+ )?\w+(?=[^.]{0,120}\b(?:as|versus|vs\.?|under both|across both|"
    r"both trees|both|either)\b)|"
    r"matches? exactly|equals? exactly|reproduces? exactly|"
    r"never moved|did not (?:move|change|differ)|"
    r"differs? from|diverges? from|disagrees? with)\b", re.I)

# ── (c) PROVENANCE ──────────────────────────────────────────────────────────────────────
PROV = re.compile(
    r"\b(proven|proved|proves|verified|validated|measured|confirmed|demonstrated|"
    r"observed to be|independent of|independently (?:computed|verified|confirmed)|"
    r"reproduced|pinned by|bisected|established that)\b", re.I)

# ── (a) NUMERIC (report-only) ───────────────────────────────────────────────────────────
NUMERIC = re.compile(
    r"(?:[-+]?\$\s?[0-9][0-9,]*(?:\.[0-9]+)?"
    r"|[0-9][0-9,]*(?:\.[0-9]+)?\s*%"
    r"|\b[0-9][0-9,]*\s*(?:of|/)\s*[0-9][0-9,]*\b"
    r"|\bn\s*=\s*[0-9]+)", re.I)

# ── (d) NEGATIVE (report-only) ──────────────────────────────────────────────────────────
NEGATIVE = re.compile(
    r"\b(no [a-z_]+ (?:exists?|was|were|is|are)|never (?:fires?|fired|ran|runs|calls?|called|"
    r"touch(?:es|ed)?|happens?)|zero\b|not one\b|nothing (?:here|in|else)\b|"
    r"no such\b|does not exist)", re.I)

# ── assertive voice: a claim must be STATED, not proposed ───────────────────────────────
HEDGE = re.compile(
    r"\b(if\b|would|should\b|could\b|might|may\b|maybe|probably|likely|perhaps|suppose|"
    r"assume|propose|recommend|suggest|plan to|let me|i'll|going to|about to|intend|"
    r"unless|whether|unclear|unknown|guess|hypothes|owed:|owed\b|"
    r"must\b|needs? to\b|cannot be made|is wrong if|are wrong if|turns out)", re.I)

# an [UNVERIFIED] tag, or a marker saying this text is dead
UNVERIFIED = re.compile(r"\[UNVERIFIED\]", re.I)
DEAD = re.compile(r"(~~|SUPERSEDED|RESOLVED|RETRACTED|WITHDRAWN|WRONG;|is WRONG\b)", re.I)

# ── EVIDENCE: only NAMED things count ───────────────────────────────────────────────────
EVIDENCE_PATTERNS = [
    # a runnable command
    ("command", re.compile(r"(?:python3?|pytest|bash|sh|\./|curl\s+|git\s+(?:diff|log|show|bisect))\s+\S")),
    # a script or output artifact by path (NOT a bare .md — a doc is not evidence)
    ("artifact", re.compile(r"\b[\w./-]+\.(?:py|json|jsonl|txt|csv|sh)\b")),
    # a rig spec name / rig test file
    ("rigspec",  re.compile(r"\bSPEC_[A-Za-z0-9_]+|\brig/test_[A-Za-z0-9_]+\.py|::[A-Za-z0-9_]+")),
    # a commit sha in backticks or bare (7-40 hex, must contain a digit AND a letter to avoid
    # matching words like "added" or plain numbers)
    ("sha",      re.compile(r"`?\b(?=[0-9a-f]{7,40}\b)(?=[a-f0-9]*[0-9])(?=[a-f0-9]*[a-f])[0-9a-f]{7,40}\b`?")),
    # an API endpoint the reader can hit
    ("endpoint", re.compile(r"/api/[\w/?=&.-]+")),
]

# sections that RESTATE rather than establish — evidence may come from anywhere in the doc
RESTATEMENT = re.compile(
    r"\b(VERDICT|SUMMARY|LIMITS|CAVEATS?|FAILURE CONDITION|WHAT REMAINS|CONCLUSION|"
    r"DEFAULT POSTURE|FILES|WHAT THIS IS NOT)\b", re.I)

# CONTRADICTED: "identical/unchanged/same" carrying two different numbers across a vs/→
CONTRA_JOIN = re.compile(
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:%|)\s*(?:vs\.?|versus|against|→|->)\s*"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:%|)", re.I)
CONTRA_WORD = re.compile(r"\b(identical|unchanged|the same|equal|no change)\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?:])\s+(?=[A-Z*`\[(#—-])|\n(?=[-*|>])")


# ── document parsing ────────────────────────────────────────────────────────────────────
def parse_blocks(text):
    """-> [ {kind, text, section, line} ]  kind in para|fence|table|heading."""
    lines = text.split("\n")
    blocks, buf, start, section, in_fence = [], [], 0, "", False

    def flush(kind=None):
        nonlocal buf, start
        if not buf or not any(l.strip() for l in buf):
            buf = []
            return
        body = "\n".join(buf)
        k = kind or ("table" if _is_table(buf) else "para")
        blocks.append({"kind": k, "text": body, "section": section, "line": start + 1})
        buf = []

    for i, ln in enumerate(lines):
        if ln.strip().startswith("```"):
            if in_fence:
                buf.append(ln)
                flush("fence")
                in_fence = False
            else:
                flush()
                start = i
                buf = [ln]
                in_fence = True
            continue
        if in_fence:
            buf.append(ln)
            continue
        if ln.startswith("#"):
            flush()
            section = ln.lstrip("#").strip()
            blocks.append({"kind": "heading", "text": ln.strip(), "section": section,
                           "line": i + 1})
            continue
        if not ln.strip():
            flush()
            continue
        if not buf:
            start = i
        buf.append(ln)
    flush()
    return blocks


def _is_table(buf):
    piped = [l for l in buf if l.strip().startswith("|")]
    return len(piped) >= 2 and len(piped) >= len([l for l in buf if l.strip()]) - 1


def evidence_in(text):
    """-> [(kind, literal)] named evidence tokens."""
    out = []
    for kind, pat in EVIDENCE_PATTERNS:
        for m in pat.finditer(text):
            lit = m.group(0).strip("`")
            if kind == "artifact" and lit.lower().endswith(".md"):
                continue
            out.append((kind, lit))
    return out


def scope_for(blocks, idx):
    """Evidence scope: the block itself + immediately adjacent fences/tables.

    A RESTATEMENT section widens the scope to the whole document (it restates; it does not
    establish).  Everything else is deliberately tight — a superseding blockquote further down
    the same section must not be able to launder a false paragraph above it.
    """
    b = blocks[idx]
    if RESTATEMENT.search(b["section"] or ""):
        return "\n".join(x["text"] for x in blocks), "document (restatement section)"
    parts, why = [b["text"]], ["paragraph"]
    # the block IMMEDIATELY BEFORE (any kind) — a lead-in sentence that names the script, and
    # the table/fence a claim sits on top of, are both real citations.  Deliberately NOT the
    # block after (except a fence/table the claim introduces): instance E-2's grounding, had
    # we allowed it, would have come from a superseding blockquote written hours later.
    if idx - 1 >= 0 and blocks[idx - 1]["kind"] != "heading":
        parts.append(blocks[idx - 1]["text"])
        why.append("preceding " + blocks[idx - 1]["kind"])
    if idx + 1 < len(blocks) and blocks[idx + 1]["kind"] in ("fence", "table"):
        parts.append(blocks[idx + 1]["text"])
        why.append("following " + blocks[idx + 1]["kind"])
    return "\n".join(parts), " + ".join(why)


def _strip(s):
    return re.sub(r"[*_`~]", "", s).strip()


def classify_sentence(s):
    """-> set of class letters present."""
    cls = set()
    if EQUIV.search(s):
        cls.add("b")
    if PROV.search(s):
        cls.add("c")
    if NUMERIC.search(s):
        cls.add("a")
    if NEGATIVE.search(s):
        cls.add("d")
    return cls


def scan_doc(path, classes=("a", "b", "c", "d")):
    with open(path, errors="replace") as fh:
        text = fh.read()
    blocks = parse_blocks(text)
    findings = []
    for i, b in enumerate(blocks):
        if b["kind"] in ("heading", "fence", "table"):
            continue
        blk_unverified = bool(UNVERIFIED.search(b["text"]))
        blk_dead = bool(DEAD.search(b["text"]))
        ev_text, ev_why = scope_for(blocks, i)
        ev = evidence_in(ev_text)
        # A table or code fence the claim sits directly on top of / underneath IS the evidence:
        # the numbers being compared are literally displayed.  (The zone_flip MATCH table in
        # harness_lift_remaining is the canonical honest case.)  None of the three known-false
        # instances is adjacent to one, which is why this costs no recall.
        for j in (i - 1, i + 1):
            if 0 <= j < len(blocks) and blocks[j]["kind"] in ("table", "fence"):
                ev.append(("shown", "adjacent " + blocks[j]["kind"]))
        for raw in SENT_SPLIT.split(b["text"]):
            s = _strip(raw)
            if len(s) < 30 or len(s) > 700:
                continue
            if s.startswith(">") and not s.startswith(">>"):
                # a blockquote quoting another document is not this doc's claim
                if not re.search(r"\b(RESOLVED|SUPERSEDED)\b", s, re.I):
                    continue
            cls = classify_sentence(s) & set(classes)
            if not cls:
                continue
            gated = cls & {"b", "c"}
            hedged = bool(HEDGE.search(s))
            if hedged:
                continue
            if UNVERIFIED.search(s) or blk_unverified:
                verdict, reason = "EXEMPT_UNVERIFIED", "[UNVERIFIED] tag"
            elif DEAD.search(s) or blk_dead:
                verdict, reason = "EXEMPT_SUPERSEDED", "struck / superseded"
            elif _contradicted(s):
                verdict, reason = "CONTRADICTED", _contradicted(s)
            elif ev:
                verdict = "GROUNDED"
                reason = ", ".join(sorted({"%s:%s" % (k, v) for k, v in ev})[:4])
            else:
                verdict, reason = "ASSERTED", "no named evidence in %s" % ev_why
            findings.append({
                "doc": os.path.basename(path),
                "line": b["line"],
                "section": b["section"],
                "classes": "".join(sorted(cls)),
                "gated": bool(gated),
                "verdict": verdict,
                "why": reason,
                "scope": ev_why,
                "sentence": re.sub(r"\s+", " ", s)[:300],
            })
    return findings


def _contradicted(s):
    if not CONTRA_WORD.search(s):
        return None
    for m in CONTRA_JOIN.finditer(s):
        a, b = m.group(1).replace(",", ""), m.group(2).replace(",", "")
        try:
            if float(a) != float(b):
                return "says %s but carries %s vs %s" % (
                    CONTRA_WORD.search(s).group(0), a, b)
        except ValueError:
            pass
    return None


# ── the gate ────────────────────────────────────────────────────────────────────────────
GRANDFATHER = os.path.join(HERE, "ARTIFACT_CLAIMS_GRANDFATHER.json")
GATE_FROM = "20260818"


def doc_date(path):
    m = re.search(r"_(\d{8})\.md$", os.path.basename(path))
    return m.group(1) if m else None


def load_grandfather():
    try:
        with open(GRANDFATHER) as fh:
            return set(json.load(fh).get("grandfathered", []))
    except (OSError, ValueError):
        return set()


def gate(paths, verbose=True):
    """Exit 1 if any doc dated >= GATE_FROM carries an ASSERTED (b) or (c) claim."""
    gf = load_grandfather()
    bad = []
    for p in paths:
        name = os.path.basename(p)
        d = doc_date(p)
        if name in gf:
            if verbose:
                print("  ⏭  %-52s GRANDFATHERED" % name)
            continue
        if d is None:
            if verbose:
                print("  ⏭  %-52s no date in filename — not gated" % name)
            continue
        if d < GATE_FROM:
            if verbose:
                print("  ⏭  %-52s dated %s < %s" % (name, d, GATE_FROM))
            continue
        f = [x for x in scan_doc(p) if x["gated"] and x["verdict"] == "ASSERTED"]
        if f:
            bad.extend(f)
            if verbose:
                print("  ❌ %-52s %d ungrounded equivalence/provenance claim(s)" % (name, len(f)))
                for x in f[:6]:
                    print("       L%-5d %s" % (x["line"], x["sentence"][:110]))
        elif verbose:
            print("  ✅ %-52s clean" % name)
    return 1 if bad else 0, bad


# ── validation against the three known instances ────────────────────────────────────────
KNOWN = [
    ("E-1  'entirely different names'", "harness_lift_remaining_20260817.md",
     re.compile(r"entirely different", re.I), "ASSERTED"),
    ("E-2  'PROVEN INDEPENDENT of batch E'", "harness_lift_remaining_20260817.md",
     re.compile(r"independent of batch E", re.I), "ASSERTED"),
    ("D-3  batch-D read-not-executed", "breakattack_extraction_20260817.md",
     re.compile(r"byte-for-byte|moved, not rewritten", re.I), "ASSERTED"),
]
CONTROLS = ["burst_saturation_20260817.md", "breakattack_extraction_20260817.md"]
EXPECTED_CATCHES = 2       # measured floor; see the doc's MEASURED section


def self_test(verbose=True):
    kt = os.path.join(REPO, "data", "killtests")
    caught = 0
    for label, doc, sig, want in KNOWN:
        p = os.path.join(kt, doc)
        if not os.path.exists(p):
            print("  ⏭  %-40s doc absent" % label)
            continue
        hits = [f for f in scan_doc(p) if sig.search(f["sentence"]) and f["gated"]]
        got = [h for h in hits if h["verdict"] == want]
        caught += bool(got)
        if verbose:
            state = "✅ CAUGHT " if got else ("❌ MISSED " if not hits else "⚠️  SEEN   ")
            detail = (got or hits or [{"verdict": "—", "sentence": "no claim-shaped sentence matched"}])[0]
            print("  %s %-40s %s: %s" % (state, label, detail["verdict"],
                                         detail["sentence"][:95]))
    print("  CATCH RATE: %d of %d known instances" % (caught, len(KNOWN)))

    print("\n  FALSE-POSITIVE CHECK on well-evidenced docs:")
    for doc in CONTROLS:
        p = os.path.join(kt, doc)
        if not os.path.exists(p):
            continue
        f = [x for x in scan_doc(p) if x["gated"]]
        a = [x for x in f if x["verdict"] == "ASSERTED"]
        print("    %-46s %3d gated claims, %2d ASSERTED (%.0f%%)"
              % (doc, len(f), len(a), 100.0 * len(a) / max(1, len(f))))
    ok = caught >= EXPECTED_CATCHES
    print("\n  SELF-TEST %s (floor %d)" % ("PASS" if ok else "REGRESSED", EXPECTED_CATCHES))
    return 0 if ok else 1


ORDER = ["ASSERTED", "CONTRADICTED", "GROUNDED", "EXEMPT_UNVERIFIED", "EXEMPT_SUPERSEDED"]


def report(findings, out=sys.stdout, only=None):
    counts = {c: len([f for f in findings if f["verdict"] == c]) for c in ORDER}
    print("ARTIFACT CLAIM AUDIT — %d claim-shaped sentences  (%s)"
          % (len(findings), ", ".join("%s %d" % (c, counts[c]) for c in ORDER if counts[c])),
          file=out)
    for f in sorted(findings, key=lambda f: (ORDER.index(f["verdict"]), f["line"])):
        if only and f["verdict"] != only:
            continue
        print("\n  [%s:%d] %s  class=%s%s\n    %s\n    %s"
              % (f["doc"], f["line"], f["verdict"], f["classes"],
                 "  (GATED)" if f["gated"] else "", f["why"], f["sentence"]), file=out)


def main():
    ap = argparse.ArgumentParser(description="GATE 8 — artifact-claim verification")
    ap.add_argument("docs", nargs="*")
    ap.add_argument("--json")
    ap.add_argument("--classes", default="abcd", help="which claim classes to scan")
    ap.add_argument("--only", help="print only this verdict")
    ap.add_argument("--gate", action="store_true", help="exit 1 on ASSERTED (b)/(c) claims")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.docs:
        ap.error("give one or more .md paths (or --self-test)")
    if a.gate:
        rc, _bad = gate(a.docs)
        return rc
    findings = []
    for p in a.docs:
        findings.extend(scan_doc(p, classes=tuple(a.classes)))
    report(findings, only=a.only)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(findings, fh, indent=1)
        print("\n  wrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
