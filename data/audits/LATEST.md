# CONVENING ARTIFACT — 8/18 INTRADAY: IGNITION'S TWO CONDITIONS

covers: a53e45506f1d — RTH deploy on Marcos's explicit override, book NOT flat (EJH, XOS open).

## The change
Ignition was the only converting lane with NO VWAP requirement and NO EMA-stack requirement.
Three back-side entries on 8/18 proved it: SXTC -11.41% under a declining VWAP (9<20, -$7.62),
EJH -9.28% under VWAP (9<20<90, red). Now: below VWAP allowed ONLY inside a 2% approach band
AND only with the 9 over the 20; beyond the band, refused regardless.

**Marcos's nuance, and it is the load-bearing part:** a hard side-of-VWAP line would refuse
IPST (-1.03%, 9 over 20) — the day's winner, +$57.41 on a name that reached $20.25. Distance
AND direction, not side. Verified on all four of today's ignition specimens.

## Findings
1. **The rig caught a real bug in the first version.** The refusal path bumped `ignition_n`,
   spending a leader-ammo refire ticket on an ATTEMPT — the 7/29 doctrine violation and the
   ghost-cap defect in a new lane. Fixed; the counter-bump is pinned to the 2 real fire paths.
2. Refusals emit an attributed `ignition_kev_gate_reject` row (lane, price, vwap_dist_pct,
   ema9/ema20, reason), so the gate is priceable from tomorrow's rows.
3. Independent kill switches: `IGNITION_VWAP_GATE`, `IGNITION_STACK_GATE`, band
   `IGNITION_VWAP_TOL` (0.02).

## BEHAVIOR CHANGE — Marcos's call, made explicitly
This refuses ignition entries that would fill today. Marcos directed it in-session after the
SXTC/EJH specimens and set the nuance himself. It enforces doctrine already ruled (Kev's "at
or above VWAP" + the 9/20), on the one lane exempt by omission.

## LIMITS — stated, not buried
* **The 2% band is fit to four specimens from one session.** The RULE is doctrine; the NUMBER
  is not measured. Tonight's wall tests 1%/2%/3%/no-band plus the 9-over-90-on-10s arm over
  the 63-date cache with the full ignition era as cohort. The band may move.
* No kill-test has run on this gate. It ships on Marcos's authority as doctrine enforcement,
  not on measured expectancy. MIXED-EPOCH: it lands mid-session.
* Deploying with an open book (EJH, XOS). Resume proven twice today (10:07 and 10:54 restarts;
  IPST survived the first and closed +$57.41).

## DOCTRINE-INVERSION SWEEP
Doctrine touched: none inverted — this RESTORES "at or above VWAP" and the 9/20 to a lane that
never had them. Swept for other lanes lacking both: dip_rip (chart-class, has the extension
guard — separate open defect), grinder/v2/kevseq (tape lanes, own burst gates). No lane
encodes a contradictory "ignore VWAP" premise. doctrine-inversion sweep: no inversion found.

## ROLL CALL
- **Blast Radius Auditor** — TOUCHED. Caught the ignition_n ghost-ticket before deploy.
- **Momentum Operator** — TOUCHED. This is his standing objection satisfied: the lane that
  bought weakness now must show strength.
- **Strength Ombudsman** — TOUCHED, and cautions the reverse risk: a VWAP gate can refuse a
  strong name that dipped. The 2% band is the concession; the reject rows will price it.
- **Trade Manager** — TOUCHED. Notes the day's larger leak is EXITS: IPST captured $57 of a
  ~$684 move. Ships tonight, not now.
- **Execution Surgeon** — CLEAN. Gate is two comparisons on values already computed at the
  fire site; no added latency, no new fetch.
- **Historian** — records: first intraday RTH code deploy of the proving week, on Marcos's
  override, with two positions open.
- **Reclaim Architect** — CLEAN on this diff, but TOUCHED today: `kev_reclaim_step` was
  registered in the harness LANES for the first time and returns 0 replay fires — a wall-clock
  staleness guard, the same class batch E1 fixed for hidden. The reclaim wall is BLOCKED on it.
- **Convexity Trader** — CLEAN on this diff (no exit-tier or runner math changes), and states
  the day's biggest number for the record: IPST captured $57.41 of a ~$684 move because the
  ladder banked 74% by +9.2%. Exits are tonight's work, not this deploy's.
- **Cartographer / Feed Engineer / Quartermaster / Kev Librarian / First Hour / Opening Bell /
  Seam Scientist / Forward Architect / Crown Steward / Side Marshal / Webull Broker Desk /
  Dashboard Curator / Systems Quant / Pit Crew Chief / Integrator / Tape Veteran / Handicapper / Rocket Rider / Wind Tunnel Engineer / Statistician / Curl Mechanic / Project Manager / Hidden Entry Architect / Opening Bell** — CLEAN:
  no map, feed, storage, corpus, session-boundary, seam, crown, side, broker, dashboard,
  parity, latency, merge, tape, reclaim, sizing, rocket, rig, statistics, exit-tier, curl,
  schedule or hidden-lane path is touched by this diff. Hidden Entry Architect additionally
  notes the construction sweep (VWAP-stop +$5.75/tr, 9/20 +$1.19) as the v2 rebuild spec.

## DAY-ONE WALKTHROUGH
Next ignition fire: `_e9/_e20/vwap` are already computed at the fire site. If price >= vwap*0.98
AND 9 >= 20 -> unchanged path, `breakouts.append`. Else -> `ignition_kev_gate_reject` row +
console line, `ignition_fired` set (no counter bump), `continue`. Observable within minutes of
the next ignition setup; the 12:48 duty-watch checkpoint will show ignition fires vs fills and
name this gate if it starts refusing.
