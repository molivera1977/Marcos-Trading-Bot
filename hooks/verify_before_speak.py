#!/usr/bin/env python3
"""
VERIFY-BEFORE-SPEAK ENFORCER — a Stop hook that BLOCKS the turn (8/19)

Marcos: "we need a program in the code that forbids you to speak before verifying."

WHY THIS EXISTS. The STANDING VERIFICATION CONTRACT has been injected on every user message
since 7/16 as ADVISORY TEXT. On 8/19 it failed exactly as advisory rules do: asked for the
day's "biggest misses", the assistant named TNON/CDTG runway refusals as costing money — from
watching them run, with no replay. Hours later the measured answer was the opposite (runway
SAVES ~$528 over 6 sessions). Marcos: "you say one thing and you reverse later." The rule was
never the problem; the ENFORCEMENT was. This makes it mechanical.

WHAT IT DOES. On Stop, read the transcript, isolate THIS turn (everything after the last user
message), and ask two questions:
  1. Does the assistant's final message make a QUANTITATIVE or VERDICT claim?
     (dollar figures, per-trade stats, R-multiples, %s tied to outcome words, or verdict
     language: biggest miss/cost us/saved/wins/loses/is the problem/...)
  2. Did ANY tool call run in this turn (Bash/Read/Grep/...) or is the claim explicitly
     hedged ([UNVERIFIED], "I don't know yet", "HYPOTHESIS", "eyeball", "not measured")?
If (1) and not (2) -> BLOCK with a reason naming the offending sentence. The model cannot end
the turn; it must run the check or hedge the claim.

DELIBERATELY NARROW. It cannot catch a wrong claim that carries a tool call, or a purely
qualitative misstatement. It catches the specific 8/19 failure class: asserting numbers or
verdicts about money with nothing run this turn. False positives are cheap (hedge or check);
false negatives are the status quo. Kill: VERIFY_HOOK=0 in the environment.

SAFETY: honors stop_hook_active (never loops), fails OPEN on any internal error (a broken
enforcer must never wedge the session), and never blocks a turn that ran tools.
"""
import json
import os
import re
import sys

# claims about money/outcomes
NUM = re.compile(r"""(
    \$\s?-?\d[\d,]*(\.\d+)?          # $123.45  -$1,584
  | -?\d+(\.\d+)?\s?R\b              # 3.02R
  | \d+(\.\d+)?\s?%\s?(green|win|WR) # 71% green
  | \d+\s*/\s*\d+\s+(green|win)      # 13/30 green
)""", re.X | re.I)

VERDICT = re.compile(r"""\b(
    biggest\s+(miss|misses|save|saves)
  | cost(s|ing)?\s+(us|you|money)
  | (saved|saving|losing|lost)\s+(us|you|money)
  | (is|was)\s+the\s+(problem|culprit|issue)
  | (net[- ])?(winner|loser)\b
  | (out)?earn(s|ed)?\b
  | expectancy\s+(is|was)
  | (beats|loses\s+to)\s+the\s+(baseline|control)
)\b""", re.X | re.I)

# language that makes a claim honest without a check
HEDGE = re.compile(r"""(
    \[UNVERIFIED\]
  | \bHYPOTHESIS\b
  | don't\s+know\s+yet
  | not\s+(yet\s+)?(measured|verified|priced|replayed|tested)
  | eyeball(ed|ing)?
  | haven't\s+(measured|run|checked)
  | before\s+I\s+(measure|check|price)
  | needs?\s+(the\s+)?(replay|sweep|kill-test|measurement)
)""", re.X | re.I)


def main():
    if os.environ.get("VERIFY_HOOK", "1") != "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                                   # fail open
    if payload.get("stop_hook_active"):
        return 0                                   # never loop
    path = payload.get("transcript_path")
    if not path or not os.path.exists(path):
        return 0

    try:
        lines = [json.loads(l) for l in open(path) if l.strip()]
    except Exception:
        return 0

    # isolate this turn: everything after the last human message
    start = 0
    for i, ev in enumerate(lines):
        if ev.get("type") == "user" and not _is_tool_result(ev):
            start = i
    turn = lines[start + 1:]
    if not turn:
        return 0

    ran_tool = any(
        blk.get("type") == "tool_use"
        for ev in turn if ev.get("type") == "assistant"
        for blk in _content(ev)
    )
    if ran_tool:
        return 0                                   # something was checked this turn

    text = ""
    for ev in reversed(turn):
        if ev.get("type") == "assistant":
            text = " ".join(b.get("text", "") for b in _content(ev) if b.get("type") == "text")
            if text.strip():
                break
    if not text.strip():
        return 0

    if HEDGE.search(text):
        return 0                                   # claim is explicitly unverified — allowed

    hit = NUM.search(text) or VERDICT.search(text)
    if not hit:
        return 0

    sentence = _sentence_around(text, hit.start())
    reason = (
        "VERIFY-BEFORE-SPEAK (Stop hook): this turn ran NO tool calls but makes a "
        "quantitative/verdict claim about money or outcomes:\n\n"
        f"    “{sentence}”\n\n"
        "Marcos 8/19 (“you say one thing and you reverse later”) after the runway "
        "'biggest misses' reversal. Do ONE of these before ending the turn:\n"
        "  1. RUN THE CHECK (replay/query/grep) and restate the claim with the result, or\n"
        "  2. tag it [UNVERIFIED] / HYPOTHESIS and say what check would settle it, or\n"
        "  3. quote a check that already ran EARLIER IN THIS SESSION and cite it inline.\n"
        "Do not restate the claim unchanged."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def _content(ev):
    msg = ev.get("message") or {}
    c = msg.get("content")
    return c if isinstance(c, list) else []


def _is_tool_result(ev):
    return any(b.get("type") == "tool_result" for b in _content(ev))


def _sentence_around(text, idx):
    lo = max(text.rfind(".", 0, idx), text.rfind("\n", 0, idx)) + 1
    hi = min([x for x in (text.find(".", idx), text.find("\n", idx)) if x != -1] or [len(text)])
    return re.sub(r"\s+", " ", text[lo:hi + 1]).strip()[:300]


if __name__ == "__main__":
    sys.exit(main())
