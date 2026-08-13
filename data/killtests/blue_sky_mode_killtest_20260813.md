# BLUE-SKY MAP MODE — KILL-TEST (Marcos: "kill test this blue sky mode"; run 8/13 ~09:10 ET)

## The defect (found live 8/13 morning)
Summit sanity (shipped 8/12 night, PLAG specimen) discards any read whose top target <= live px.
MAPLESS_BLOCK (8/6) refuses conversions without a map. Together: a leader at NEW HIGHS above its
daily-visible levels can NEVER get a map -> never converts -> untradeable all day, regardless of
tape. First live specimens: FGI (read rejected 3x, 8 mapless_reject fires 8:01-8:51, ran 8.13->9.10)
and XHG (rejected 2x at live 4.36/5.17 vs target 2.5 — a +100%+ runner the roster never even fired on).

## Modeled cost (coarse model: $200 clip, -6% first-touch stop, 35% capture, first refusal/name)
- TRUE blue-sky cohort (post-summit-ship only, 8/13): FGI +$9.79 modeled. XHG $0 (no fire — lane
  hole #48, not map hole). Yesterday's mapless rows (OFAL/BQ/RMCF...) were the PRE-reader-start
  hole, ALREADY fixed + separately counted — no double-count.
- So the measured cost so far is SMALL (~$10/day) — the case for the fix is the ARCHETYPE
  (new-high leader = the mission's core prey) + Monday real money, not the modeled dollars.

## Design under test (reader-side, minimal)
When a read is FRESH (vision just ran, live 10s print in hand) but max target <= live:
POST the map with blue_sky=True + note, targets kept as historical-levels-now-support, instead of
no-post. Consumers: (a) MAPLESS_BLOCK sees a map -> tape lanes (hidden/reclaim) may convert;
(b) chart lanes UNCHANGED — #28 read_exhausted standdown still holds them down (verified: gate
reads targets, blue_sky flag adds no allow path); (c) runway gate: above-all-levels -> existing
'∞/blue sky' path (already in RTH code); (d) stops stay structural from live 10s tape, never from
the blue-sky map's stale numbers.

## PLAG 8/11 safety replay (the case that MUST STILL BLOCK)
PLAG's harm: a STALE morning read (1.62 targets) treated as current on a $4.50 tape — chart lanes
read a backward ceiling. Under blue-sky mode: the same read posts WITH blue_sky flag ->
(1) chart lanes: still stood down by #28 (read_exhausted) — unchanged, no backward-ceiling verdicts;
(2) hidden/reclaim on PLAG 8/11: would have been ALLOWED to convert into the +141% run — that is
the FGI case, i.e., the fix working, not the harm recurring. The PLAG harm mechanism (chart-lane
verdicts off stale numbers) is structurally unreachable: blue-sky changes MAP PRESENCE only, never
gate arithmetic. -> PASS by structure; rig must pin (a) blue_sky never sets break-allow, (b) #28
standdown fires on blue-sky maps identically.

## Freshness guard (the line that keeps summit sanity's win)
Blue-sky post REQUIRES the live 10s print at read time (same _bs_live condition as the existing
reread blue-sky path :916-919 — "no print -> no post" stays). A read that cannot prove tape
freshness still discards. Summit sanity is not weakened; it gains an output besides silence.

## VERDICT: fix justified by archetype + Monday; measured cost small but freshly accruing daily.
Ship tonight via full protocol (convening + roll call + rig pins + ship.sh). NOT shipped intraday.

## ADDENDUM (8/13 evening ship, 20th convening fix-now #2)
The shipped design EXEMPTS blue-sky maps from the #28 ceiling standdown (targets advisory), so
the PLAG-safety argument above is superseded: PLAG-stale protection now = (1) the 600s TTL — a
stale blue-sky map counts as ABSENT, mapless_reject blocks ALL lanes; (2) chart lanes further
caged by the live break-side gate. The #28 standdown still governs all NON-blue-sky maps.
