# MANUAL CLOSE CONTROL — failure condition written FIRST (8/17)

**Why it exists.** Marcos said "close it" on a live position (DFSC) and there was no mechanism.
The only options were (a) wait for the stop or (b) restart — and since the 8/9 painless-restart
work, a restart RESUMES positions instead of closing them. For go-live, "kill this one trade,
now" is a required operator safety control.

**What it is.** Operator-initiated, one position at a time, through the SAME exit choke point the
stop and the 15:45 flatten use. It is NOT an autonomous behavior: the bot never originates a
close request, it only obeys one an operator created.

## THIS CONTROL IS WRONG IF:

1. **A stale request closes a LATER position in the same name.** Marcos asks to close DFSC at
   10:02, the position stops out on its own at 10:03, the bot re-enters DFSC at 10:20, and the
   still-pending request kills the new trade. Two independent guards must both hold:
   the 10-minute server-side expiry, AND the entry_ts guard (a request whose timestamp is OLDER
   than the position's entry_ts_utc is ignored outright).
2. **An unreachable dashboard triggers a close.** The poll must fail CLOSED for closing — i.e.
   an error, a timeout, a 401, or malformed JSON must produce NO close. Only the explicit
   presence of a matching, fresh request may sell. (Note this is the opposite polarity from
   `_entries_paused`, which keeps last-known state; a close is irreversible, so "unknown" must
   mean "do nothing" and the cache must never retain a request across a failed poll.)
3. **A double-delivered request double-sells.** One request must produce exactly one market
   sell of the remaining shares. If the ack POST fails, the idempotency guard (the monitor has
   already broken out of its loop / the position is gone) must still prevent a second sell.
4. **An unauthenticated caller can close a position.** The POST endpoint must require the
   dashboard secret. GET is read-only.
5. **A close request wipes other pending requests.** Merge-only semantics (the 7/24 wipe law).
   Two positions can be queued for close simultaneously; posting the second must not drop the
   first.
6. **It writes a parallel exit path.** The exit must route through `_safety_close` ->
   ladder cancel -> stop cancel -> `close_position`, and be recorded/cleared exactly as a normal
   exit (trade_id-keyed clear, per the 8/11 ghost fix). A second exit code path would drift from
   the real one and is itself the defect.
7. **It cannot be turned off.** `MANUAL_CLOSE=0` must make the bot ignore the channel entirely
   (no poll, no close), without a code change.

## Known limits (stated, not hidden)
- The close fires on the monitor's own cadence (>=5s cached poll), so worst-case latency is a
  few seconds, not instant.
- If no monitor is running for that position (crashed process, pre-monitor window), nothing
  consumes the request and it expires harmlessly after 10 minutes. This control is not a
  substitute for broker-side flattening.
- The request is per-position. There is no "close everything" verb by design.
