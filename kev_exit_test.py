# ── Kev exit system (locked from 3 recap videos) vs the old fixed-% tiers ──
# Kev (R-based):  stop = bottom of zone/prev-candle-low (defines R) → SELL HALF at +1R (risk-free)
#                 → trim 25% more into strength (at the supply ceiling, or ~85% to the high if open room)
#                 → final 25% runner exits on the reversal (instant-exit: new high fails back below prior bar)
# Old (%-based):  25%@+8%, 50%@+12%, 100%@+20% (AM tiers); remainder trails 5% below the high AFTER a partial;
#                 if +8% never reached → no partial → no trail → rides to the initial stop.

def kev_exit(entry, stop, supply, high, reversal_exit):
    R = entry - stop
    pnl = 0.0; legs = []
    # leg 1: sell 50% at +1R (only if the move reached it; all our cases do)
    t1 = entry + R
    if high >= t1:
        pnl += 0.50*(t1-entry); legs.append(("50%@+1R", t1))
    else:  # never reached +1R → whole position rides to stop
        return (high - entry) if False else (stop-entry), [("100%@stop", stop)]
    # leg 2: trim 25% into strength — at the supply ceiling if into-supply, else ~85% to the high
    t2 = min(supply, high) if supply else entry + 0.85*(high-entry)
    pnl += 0.25*(t2-entry); legs.append(("25%@trim", round(t2,4)))
    # leg 3: 25% runner exits on the reversal off the high
    pnl += 0.25*(reversal_exit-entry); legs.append(("25%@runner", reversal_exit))
    return pnl, legs

def old_exit(entry, stop, high, reversal_exit, tiers=((0.08,0.25),(0.12,0.50),(0.20,1.00)), trail=0.05):
    R = entry - stop; pnl=0.0; sold=0.0; legs=[]; any_partial=False; last_fill=entry
    for pct,cum in tiers:
        tgt = entry*(1+pct)
        if high >= tgt:
            qty = cum - sold
            pnl += qty*(tgt-entry); sold=cum; any_partial=True; last_fill=tgt
            legs.append((f"{int(qty*100)}%@+{int(pct*100)}%", round(tgt,4)))
            if cum>=1.0: return pnl, legs
    rem = 1.0 - sold
    if any_partial:                       # remainder trails 5% below the high
        tstop = max(high*(1-trail), entry)
        exit_px = max(tstop, reversal_exit)   # whichever the runner actually hits
        pnl += rem*(exit_px-entry); legs.append((f"{int(rem*100)}%@trail", round(exit_px,4)))
    else:                                 # NO tier hit → no trail → rides to initial stop
        pnl += rem*(stop-entry); legs.append((f"{int(rem*100)}%@STOP", stop))
    return pnl, legs

# (name, entry, stop=zone/base low, supply ceiling or None=open room, high, runner-reversal-exit)
trades = [
 ("ILLR", 5.00, 4.70, None,  5.48, 5.25),   # base 4.7-5.0 → 5.48 → faded; runner out ~5.25 on reversal
 ("BDRX", 2.95, 2.88, None,  3.07, 3.00),   # base ~2.90 → 3.07 → slammed to 2.70; runner out ~3.00
 ("AZI",  1.84, 1.80, 1.95,  1.93, 1.90),   # base 1.76-1.82 → 1.93 into ~1.95 supply → chopped
 ("IVF",  2.16, 2.00, None,  3.08, 2.90),   # 4h base 2.0-2.15 → 3.08 → faded; runner out ~2.90
 ("SDOT",15.00,13.00, None, 22.75,21.00),   # base ~13-15 → 22.75 → 19; runner out ~21 (caveat: halt-y)
]
print(f"{'name':5} {'R':>5} {'high':>6} {'highR':>6} | {'KEV %':>7} {'OLD %':>7} | verdict")
print("-"*72)
for nm,e,s,sup,hi,rev in trades:
    R=e-s; hiR=(hi-e)/R; hipct=(hi-e)/e*100
    kp,kl = kev_exit(e,s,sup,hi,rev); op,ol = old_exit(e,s,hi,rev)
    kpct=kp/e*100; opct=op/e*100
    v = "KEV banks it, OLD misses" if (kpct>0 and opct<=0.3) else ("both win" if opct>0.3 else "")
    print(f"{nm:5} {R:5.2f} {hi:6.2f} {hiR:5.1f}R | {kpct:+6.1f}% {opct:+6.1f}% | {v}")
print("\nLeg detail:")
for nm,e,s,sup,hi,rev in trades:
    kp,kl=kev_exit(e,s,sup,hi,rev); op,ol=old_exit(e,s,hi,rev)
    print(f"  {nm}: KEV {kl}")
    print(f"  {' '*len(nm)}  OLD {ol}")
