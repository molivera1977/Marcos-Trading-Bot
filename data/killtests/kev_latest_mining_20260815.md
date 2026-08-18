# Kev Latest Mining — 2026-08-15 (overnight 8/14) — Kev Librarian

**VERDICT QUALIFIER (LIMITS, added 2026-08-17):** the staleness verdict is a COUNT of what the sweep was missing, not an evaluation. Several dates in this doc are marked [UNVERIFIED] — inferred from weekday and ticker internal evidence rather than sourced — so any lesson keyed to a specific date inherits that flag.

Ordered by Marcos 8/14: "delve into his latest videos and shorts to find the latest strategies," plus two
testimony lenses added mid-session (afternoon exception; "pre-market has been big for him lately").
Officers convened/touched: Kev Librarian (owner), Hidden Entry Architect, Rocket Rider, Trade Manager,
First Hour, Opening Bell, Side Marshal, Seam Scientist (flags below). Historian: date inferences marked.

## 1. Corpus freshness (before tonight)
- `all_transcripts.md` master file: last touched 8/4; long-form store `transcripts/` ended at
  dC3ytDNSC0U "Is NOW The Best Time To Trade" (pulled 8/3). Shorts store ended at the 8/6 09:29 sweep
  (content through TOP 3 WEDNESDAY 8/5/26).
- Verdict: corpus was ~9 days stale on long-form, ~8 days on shorts. Channel had **9 long videos and
  ~38 shorts we did not have.**

## 2. What was pulled tonight (all new, none previously on file)
Long-form (fetched via youtube-transcript-api + Webshare proxy; yt-dlp anonymous AND proxied both
blocked by YouTube bot-check "page needs to be reloaded" — vendor note for Feed Engineer):
| id | title | date |
|---|---|---|
| ZSTaBPLMFFI | There is a HALT epidemic... This is MY plan. | ~8/5 [UNVERIFIED date] |
| AIKDZG5v-ns | Literally Just WAIT For THIS CANDLE | 8/6 (WYHG/CLRB/CELZ day) |
| M6PyfdmWgeY | How To ACTUALLY Use VWAP | ~8/7 [UNVERIFIED date] |
| VhH6-u9POsk | Spot SHORT Traps Before The SQUEEZE | ~8/8-9 [UNVERIFIED date] |
| ulOfwyRAs1o | 230% in 5 SECONDS (SCKT) | 8/10 Mon |
| DSy3y9xAXxc | When Should You SIT.. and When Should You TRADE? | 8/11 Tue |
| uDJ22ntH1II | This is getting RIDICULOUS.. (OFAL) | 8/12 Wed |
| zi5PWC2IJ7k | A 1,300% SQUEEZE in 5 seconds (XHD) | 8/13 Thu |
| -5kFWl15nb0 | EVERY Trader Needs To Know When To Step Away | 8/14 Fri (tonight) |

All 9 appended to `all_transcripts.md` as a clearly-headed 2026-08-14 merge-only section (backup of the
pre-append file in session scratchpad). Shorts: kev_sweep.sh was run this session; ~37 new shorts through
8/14 landed in `shorts/transcripts/` (TOP-3 lists 8/10–8/13, PBL trail, share-size, halt-epidemic, etc.).
TikTok @momentum.official: not swept tonight (YouTube covered the gap; TikTok pass remains queued per
project_kev_tiktok_surface).

## 3. Theme findings (verbatim, recency-weighted)

### (a) EXITS — scale into strength by structure, PBL trail, never fixed %
No fixed-% banking anywhere. His system: sell fractions into strength at structure (prior highs /
supply / topping tails / halt levels), trail the remainder by **prior-bar-low**, full-exit on topping-tail
rejection.
- 8/11 short (BBlvqwlpfWM, STOP turning GREEN trades RED): "the way that I trail my stop loss to keep my
  green trades green and maximize my profit is using a simple one minute PBL strategy. PBL meaning prior
  bar low... as the next candle breaks over the previous candle's high, my stop loss then gets raised to
  the next candle's low and so on... until eventually you're out full with your profit... completely
  systemize it."
- ~8/5 (ZSTaBPLMFFI): "I get a half sold up here underneath 630, beneath this previous high. We get the
  break higher, quarter left, and then of course runners left out full off the high." (half → quarter →
  runners ladder, sells placed UNDER prior highs, not at them)
- 8/11 short (pEOCflRPBLE): "of course, topping tail rejection, full exit before the reversal."
- 7/31 (OSgAqbaZED0): "even my runners, I sold over a dollar above entry."
- 8/13 short (AWCqE5Lwkxs): "I get my stop loss raised, trimming into strength."
- Risk-free rule (7/1 premarket video R2d9j7pQIAU): "once they break the previous candle's high, that's
  where I then I'm risking my entry... from then on it's essentially a risk-free setup."

### (b) MULTIPLE CHUNKS / ADDING
He does NOT pyramid a winner. He exits full or to runners, then takes **fresh re-entries on the next
pullback** — rinse-repeat off supply-turned-demand — and occasionally re-adds "runners" after a full exit
(and criticizes himself for it):
- 7/1 (R2d9j7pQIAU): "I'm just sort of rinsing and repeating off those pullbacks to those past areas of
  supply which have now become areas of demand."
- 7/30 (d1_aPoPmZUg): "I put some runners back into this thing. And I know looking back, it's like, did it
  really make any sense?... just to have some meat back in the game." (re-add = small, optional, judged
  marginal by Kev himself)
- 8/11 short (LDfsNgRe9t4): serial re-entry on dips through a halt sequence: "Watch dips. Watch dips.
  Watch the pullback. Took it back there at 270... perfect dip and rip."
Bot translation: multiple sequential trades per name (our slots/crown model), not size-adds into an open
position.

### (c) ATTACKING BREAKS vs WAITING FOR RETESTS
Doctrine is **confirmation-first**: no-break-no-trade at the watchlist level; at the trade level he waits
for the failed-breakdown / snap-back candle, and only "punches" proactively in one place — anticipating
the VWAP reclaim before the crowd:
- ~8/5 (ZSTaBPLMFFI): "this is how I trade pullbacks with confirmation... it pulls back beneath this
  previous candle... I wait for that candle to get bought back up to tell me, hey... buyers have stepped
  back in. Let's try it here for that next leg."
- 8/6 short (WnoJ_x51cro): "wait for the current one minute candle to break beneath the previous one
  minute candle's low and get instantly bought back up, showing that it's grabbing liquidity... this is
  your entry. Stop loss goes at the bottom of that wick low."
- 8/8 short (t-W8pGYw87U): "that never happened. So, no break, no trade" (x3 in one video; repeated 8/5,
  8/6, 8/13).
- THE ANTICIPATION EXCEPTION — 8/5 short (-FSJ20n1lX8): "we anticipate the break of VWAP because we know
  little Timmy on Robinhood's going to go buy as soon as it snaps over VWAP... you know little Timmy's
  going to be your exit liquidity." → the one sanctioned attack-not-wait entry, and it is exactly the
  flush-under-VWAP → buy-before-the-reclaim shape.
- Anti-chase constant (7/29 uxdFKpYQC2o, reaffirmed 8/12): "no desire to chase up into the halt."

### (d) AFTERNOON — the tension, graded (Marcos lens #1)
Doctrine (standing, multiple videos): "That period of time from 9:30 to 10:30 is where you have to
capitalize most. That's where I take 95% of my trades... regardless of where I'm at at 11, I just make
myself step away... if I was going to get where I wanted to be, it would have happened that first hour."
And the self-flagellation when he breaks it: "I usually never trade after 11: today I did trade after
11:00 and what do you know break even break even break even no reason for me to be trading in the
afternoon Point Blank freaking period."
BUT Marcos is right — the exception exists, in Kev's own words, and he names its criteria:
- (older recap, corpus): "the few gappers that did hold their gains through the afternoon they were
  squeezing into the afternoon big time... it held its gains into the afternoon and then it went to NEW
  HIGHS in the afternoon." (his qualifying signature: gap holds gains + afternoon new highs)
- (older recap): "sometimes we'll get lucky and catch something like LHDX in the afternoon which is
  fantastic but... more often than not you're not going to get clean price action in the afternoons."
- He also keeps an "afternoon session" stream slot (8/14 sign-off: "I will see you for the afternoon
  session") — he WATCHES afternoons even when not trading them.
VERDICT: our afternoon vertical-grinder spec (new session high post-10:30, above VWAP, sustained climb,
no 3% pullback in 15 min) is a near-exact mechanical restatement of Kev's own exception criteria
("held its gains... went to new highs in the afternoon," clean PA). NOT a contradiction of doctrine —
it is his exception, systematized. The doctrine's true content is "don't grind chop to force a comeback";
our lane only fires on the names he'd call the exception. Tension: RESOLVED-COMPATIBLE, with the caveat
that Kev treats these as rare gifts ("sometimes we'll get lucky"), so lane frequency should stay low —
which matches its selective design.

### (e) PREMARKET — recency-weighted (Marcos lens #2): CONFIRMED, he just re-pivoted INTO it
Marcos: "Pre-market has been big for him lately." TRUE and now explicit doctrine:
- ~8/5 (ZSTaBPLMFFI): "I'm going to start trading 8:00 a.m. starting tomorrow. So, we're going to go back
  to doing some pre-market stuff... because there's been too many halts after open lately. I know I
  started focusing on the open again because July pre-market was so slow, but now I think it makes more
  sense to dive back into pre-market because the halts have been ridiculous."
- 8/14 Fri (-5kFWl15nb0): "Today was easy pre-market. Really, really fruitful... how I knew to step away
  at market open." (premarket = the profit; the open = what he stepped away FROM)
- 8/10 Mon (ulOfwyRAs1o): "I came in at 8:00 a.m. and I caught a good play on the pullback to VWAP."
- The canonical premarket setup (7/1 R2d9j7pQIAU, "working the last month or so"; mechanics unchanged in
  August tape): news catalyst → first 1-min candle spike → "wait for the candle to close and then I take
  that confirmed pullback over VWAP... it pulls back, retests VWAP... as it pulls back and finds a buyer
  ... that's where I take my entry" — risk at VWAP, risk-free once prior-candle high breaks, "you play
  that front side and then you dump it and let it go."
- Premarket liquidity guard (8/14): "the first trade I took on this was the break of 450 once the spread
  tightened up. The spread was kind of gross at first." → spread-tightening is his premarket go-signal.
GRADE vs tonight's kill-test: his premarket trade IS a VWAP-pullback/reclaim (hold or reclaim of VWAP
with a buyer confirming), NOT a flat-top break. Tonight's finding (premarket vwap-reclaim +$7.56/trade,
flat-top bleeding) independently reproduces Kev's stated preference. Build the reclaim, drop the flat-top.

### Genuinely NEW in the latest content
1. **Instant-squeeze regime** ("5-second" moves): SCKT 8/10 +230%, XHD 8/13 +1,300% "in less than 5
   seconds." His playbook: study the day-1 blowoff → wait for full giveback → double-wick low at the
   90MA/VWAP shelf → enter with risk under the wick, PBL-trail the reload leg. "This is happening more
   than I thought that it would." → Rocket Rider / Seam Scientist: a repeating specimen class, and a 1-min
   feed cannot even see the trigger — 5s/10s data mandatory (consistent with lean-on-10s law).
2. **Serial-halt AVOIDANCE (new, 8/12 X7PDYxBAtlY)**: "just stop trading the halts... out of any of these
   halts, this could have resumed down 40, 50% and you have no way to get out... When something starts to
   halt like this, it's time for you to get the heck out." Distinct from his 7/29 dip-and-rip (post-halt
   pullback entry, still valid): the NEW rule is against chasing serial-halter leading gappers (OFAL 10
   halts). → Halt-lane officers: arm-only + crowns is compatible, but a serial-halt counter (N halts in M
   minutes → stand down/exit) is Kev-grounded and we don't have one.
3. **Premarket re-pivot as regime response** (see (e)) — he moves his session window to follow cleanliness:
   July = open-focused, August = premarket-focused. Session-window itself is a tunable, not doctrine.
4. **Ascending-channel aversion (8/13)**: "My least favorite setup is an ascending channel... you're
   buying up into ascending resistance." (FGI — the very name that caged our bot 8/13.)
5. **Anti-halt distance rule reaffirmed live (8/11 short)**: "148 is the new halt level, so we have
   distance now. That is key." → halt-band distance as an entry precondition, in his words.

## 4. Flags to owning officers
- **Hidden Entry Architect**: the little-Timmy VWAP-anticipation quote (8/5) + premarket flush→reclaim
  mechanics (7/1, live-confirmed 8/10-8/14) are the v2 spec's grounding text. Anticipation is sanctioned
  ONLY at the VWAP reclaim with a confirmed buyer (wick/snap-back), never at highs.
- **Rocket Rider**: instant-squeeze (5-second) regime playbook above; needs 5s/10s detection; day-1
  blowoff names go on a day-2 reload watchlist (SCT→XHD pattern-matching is exactly our character-book
  shape).
- **Trade Manager**: PBL (prior-bar-low) 1-min trail is Kev's exact exit spec — candidate kill-test vs
  our current exit stack; plus "full exit on topping-tail rejection" and sells placed slightly UNDER
  prior highs.
- **First Hour / Opening Bell**: Kev's own window moved to 8:00 a.m. this month; spread-tightening as
  premarket go-signal; 9:25 flatten unaffected (he "dumps it and lets it go" into/at the bell on
  premarket fronts).
- **Side Marshal**: 8/11 PLAG quote — "this was backside. I was looking for a possible squeeze over VWAP"
  → he trades backside names ONLY via the VWAP-squeeze shape; failed = "stuck in a range... thick."
- **Historian**: dates marked [UNVERIFIED] above were inferred from weekday+ticker internal evidence;
  ZSTaBPLMFFI/M6PyfdmWgeY/VhH6-u9POsk need stamped upload dates when a metadata path is available.
