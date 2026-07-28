# P0 — PREMARKET PRICE IS YESTERDAY'S CLOSE (found 7/28 06:45 by Marcos, from the dashboard)

**Proposal for Fable to confirm. Nothing shipped. Evidence first, then the fix, then what could go wrong.**

## The defect, proven three ways

Marcos, reading the live Fires panel: *"the prices showing are the end of day prices for each ticker
not the current live pre-market price."* Confirmed:

1. **Ground truth (Marcos):** DFNS closed 7/27 at **13.10**. Every DFNS fire row today reads 13.10.
2. **Frozen across time:** DFNS logged `price 13.10` at 04:33 **and** 05:21 — 48 minutes apart — while
   the `vwap` field in the same rows moved (15.4809 → 15.6388). VWAP comes from bars (live); price does not.
3. **Live comparison, 06:52 (`/api/scan`, `market_state: premarket`):**

| ticker | fire rows used | actually trading | error |
|---|---|---|---|
| DFNS | 13.10 | **16.02** | −18% |
| FIRY | 8.36 | **11.29** | −26% |
| POLA | 1.47 | **1.86** | −21% |
| EHGO | 2.11 | 2.36 | −11% |

The inverted stops Marcos saw (`price 13.10, stop 15.48`) are the tell: the stop is VWAP, computed
from **real** bars; the price is yesterday's. A "reclaim" fire is comparing a stale price to a live VWAP.

## Root cause — two stale paths, one correct path

- **REST path, `_get_webull_quote` :2995:**
  `last = float(d.get("close") or d.get("last_price") or d.get("lastPrice") or d.get("c") or 0)`
  Premarket, the Webull snapshot's **`close` is the prior session's official close**. It is taken
  FIRST, so `last_price` — which `_get_price_rest` returns — is yesterday's close until 09:30.
- **Stream path, `_on_msg` :1233:**
  `px = payload.price or payload.ext_price or payload.ovn_price` — `price` preferred over the
  extended-session fields, the wrong order premarket. [UNVERIFIED which field the snapshot populates
  premarket — needs a live payload dump; the frozen-value signature is consistent with either path.]
- **The scanner is CORRECT** and proves the right data is in the same payload: it reads
  `pre_market_price` (`ah_price`), which showed DFNS 15.83 / INLF 4.57 live at 06:52.

So the bot already receives the live premarket price and throws it away everywhere except the scanner.

## Blast radius

- **No money at risk right now:** `ENTRY_OPEN_ET=09:30` — premarket entries are disabled (the 7/27
  mitigation). **RTH is unaffected**: after 09:30 the snapshot's `close` IS the live last trade,
  which is why RTH has worked all along.
- **Today's premarket study data is garbage** — all 22 shadow fires priced on yesterday's close.
- **This is a hard blocker on the premarket re-enable** scheduled for this week on the Aug-20 runway.
- **The lens inherits it** premarket (my 7/28 00:20 REST→registry write-back now caches the stale
  price). Fixing the source fixes the lens automatically.
- Everything premarket computed off `price` is affected: day-gain, room, extension, curl gates.

## Proposed fix — 3 parts, ordered by how much each is trusted

### A. Session-correct price at the source (the actual fix)
Add a session-aware price to the quote contract and serve it from `_get_price_rest`:
- premarket → `pre_market_price` when > 0, else `close`
- RTH → `close` (unchanged — the path that works)
- after-hours → `post_market_price` when present, else `close`

Leave `last_price` untouched so no other caller's semantics move (`prev_close` uses it as a fallback).

### B. Stream field ordering, session-aware
Premarket/after-hours, prefer `ext_price`/`ovn_price` over `price`. **Gate this on a live payload
dump** — I cannot verify the field's premarket content from here, and guessing wrong swaps one stale
source for another.

### C. Bar-vs-quote reconciliation at the source (the safety net — and the one I'd argue matters most)
The bot **already has this fix, applied too narrowly**: `stale_price_fix` (:5324, :5431) discards a
stream price that disagrees with the fire bar by >2% and uses the bar price. It fired **88 times on
7/27 alone** — the bug has been shouting for weeks and we only ever muffled it lane-by-lane.
Promote it to the price source: if the served price disagrees with the most recent 10s/1-min bar
close by >2%, prefer the bar and log `price_source_disagree`. Session-agnostic, self-correcting,
and it would have caught this defect the day it appeared — the same shape as the off-tape exit
guard, applied at the input instead of the output.

## Risks / what Fable should attack

1. **RTH regression risk** — the working path must not move. A is additive; C could change RTH
   behavior if bars lag a fast tape. Mitigation: C prefers the bar only when the disagreement
   exceeds 2% AND the bar is fresh (≤120s), never on stale bars.
2. **B is unverified** — do not ship it on inference. Dump a live premarket payload first.
3. **`pre_market_price` trust** — verified populated and sane at 06:52 for 6 names, one moment in
   time; it is not verified across a full session, on halts, or on thin names.
4. **Fallback ordering** — if `pre_market_price` is 0/absent on a thin premarket name, falling back
   to `close` restores the bug for that name. Should the fallback instead be "no price" (fail-safe,
   consistent with B16 no-data-no-decision)? My inclination: yes, prefer no-price over wrong-price,
   because a wrong price fires detectors while a missing price simply skips.
5. **Kill switch + canary**: `PRICE_SESSION_AWARE=0` reverts; log every premarket substitution for
   the first week so the change is auditable rather than assumed.

## What I would test before shipping (rig)
- Quote parser: premarket payload → returns premarket price; RTH payload → returns close; missing
  premarket field → fails to "no price", not to yesterday's close.
- Reconciliation: 2% disagreement prefers the fresh bar; stale bar (>120s) never overrides; RTH
  fast-tape case (bar lags, quote ahead) does NOT get clamped.
- Replay: today's 22 fires re-priced against real premarket bars — how many would still have fired?
  That number is the honest measure of what this defect cost in study data.
