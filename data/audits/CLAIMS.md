# CLAIMS LEDGER — append-only

**Marcos 8/17: "fucking fix what you are constantly saying wrong."** Prose rules are advisory and
get violated under pressure. A claim in this file is not prose: it carries the exact command that
reproduces it, and `data/audits/verify_claims.py` re-runs every command and reports
PASS / CHANGED / FAILED / NO-COMMAND. Rig section **EG3** goes RED if any row lacks a command or
if the seeded rows do not verify.

**APPEND-ONLY.** Never delete or rewrite a row. When a fact changes, append a new row with the new
date and add `SUPERSEDED by <date>` to the `claim` cell of the old one — the history of what we
believed and when is the point.

## ROW FORMAT (strict — the verifier parses these four columns and nothing else)

`| date | claim (ONE line) | command | expected |`

- **date** — `YYYY-MM-DD`, the day the claim was verified.
- **claim** — one line, no pipes. What is true.
- **command** — a shell or `python3 -c` one-liner, run with cwd = repo root, that PRODUCES the
  claim. No pipes inside the cell: write `{PIPE}` where a shell pipe is needed; the verifier
  substitutes it back. A row with an empty command is NO-COMMAND and is a rig failure.
- **expected** — the exact stdout the command produces, whitespace-stripped. Multi-line expected
  values use `{NL}` as the line separator.

| date | claim | command | expected |
|---|---|---|---|
| 2026-08-17 | SUPERSEDED by 2026-08-21 — Sim account balance is $3,000 — hardcoded SIM_ACCOUNT_BALANCE, NOT the ACCOUNT_BALANCE env (which is a LIVE-only fallback) | `grep -oE 'SIM_ACCOUNT_BALANCE +=  *[0-9.]+' marcos_trading_bot.py {PIPE} head -1 {PIPE} tr -s ' '` | `SIM_ACCOUNT_BALANCE = 3000.0` |
| 2026-08-17 | There is NO concurrent-position cap in the bot; concurrency is emergent from settled capital | `grep -cE 'MAX_CONCURRENT{PIPE}max_open_positions{PIPE}MAX_OPEN_POSITIONS{PIPE}CONCURRENT_POSITION' marcos_trading_bot.py` | `0` |
| 2026-08-17 | Concurrency's real limiter is the settled-capital reservation in the trade worker, not a slot count: a fire fills iff settled_remaining >= its reservation | `grep -oE 'if settled_remaining < _reserved:' marcos_trading_bot.py {PIPE} head -1` | `if settled_remaining < _reserved:` |
| 2026-08-17 | LEADER_CURL_SLOTS=3 is curl-lane FIRE slots for crowned names — it is NOT position capacity | `grep -oE 'LEADER_CURL_SLOTS +=  *int\(os.environ.get\("LEADER_CURL_SLOTS", "[0-9]+"' marcos_trading_bot.py {PIPE} tr -s ' '` | `LEADER_CURL_SLOTS = int(os.environ.get("LEADER_CURL_SLOTS", "3"` |
| 2026-08-17 | Sizing chain: RISK_PER_TRADE=30 ceiling, then 70% of balance capped at MAX_TRADE_DOLLARS=1000, then 5% of avg recent 1-min volume | `grep -oE '^(RISK_PER_TRADE{PIPE}MAX_POSITION_SIZE{PIPE}MAX_POS_VOL_PCT) += +[0-9.]+' marcos_trading_bot.py {PIPE} tr -s ' ' {PIPE} sort` | `MAX_POSITION_SIZE = 0.70{NL}MAX_POS_VOL_PCT = 0.05{NL}RISK_PER_TRADE = 30.0` |
| 2026-08-17 | The dollar cap in that chain is MAX_TRADE_DOLLARS=1000 (env-overridable since 8/13) | `grep -oE 'MAX_TRADE_DOLLARS += +float\(os.environ.get\("MAX_TRADE_DOLLARS", "[0-9]+"' marcos_trading_bot.py {PIPE} tr -s ' '` | `MAX_TRADE_DOLLARS = float(os.environ.get("MAX_TRADE_DOLLARS", "1000"` |
| 2026-08-17 | kevseq's front_side is computed on the 1-MINUTE aggregate and stamped caller_1m — SETUP_TF_MIN=3 governs the 3-min setup chart, not this lane | `grep -c 'caller_1m' marcos_trading_bot.py` | `2` |
| 2026-08-17 | The M1 traded-minute defect is REAL and fixed for the kevseq caller only, via the M1_WALLCLOCK window | `grep -c 'M1_WALLCLOCK' marcos_trading_bot.py` | `7` |
| 2026-08-21 | Sim account balance is $5,000 — the DRY_RUN frame now MODELS THE GO-LIVE ACCOUNT (Marcos 8/21 after the close); still hardcoded, still DRY_RUN-only, ACCOUNT_BALANCE env untouched | `grep -oE 'SIM_ACCOUNT_BALANCE +=  *[0-9.]+' marcos_trading_bot.py {PIPE} head -1 {PIPE} tr -s ' '` | `SIM_ACCOUNT_BALANCE = 5000.0` |
| 2026-08-21 | The $5,000 frame is CAPACITY-ONLY: R stays $30 and the position clamp stays min(70% x bal, $1000) — the $1,000 cap binds at BOTH books, so no ticket sizes differently | `python3 -c "print(min(0.70*3000,1000)==1000 and min(0.70*5000,1000)==1000)"` | `True` |
