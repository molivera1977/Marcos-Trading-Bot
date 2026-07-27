"""KILL-TEST — MINIMUM STOP WIDTH as an entry gate.

Hypothesis under test (from tonight's floor work): the -2R/-3R losses concentrate in trades whose
stop was too tight to be real. Risk-based sizing divides the dollar risk by a tiny per-share risk,
so those trades also get the largest share counts — a normal wiggle becomes a large dollar loss.

Rule: refuse the entry unless the stop is at least X wide. Two ways to express X:
   SPREAD-RELATIVE   risk_per_share >= k x entry_l1_spread   (a stop inside the spread is not a stop)
   PERCENT-OF-PRICE  risk_per_share / entry >= p

This is a SELECTION rule, so the counterfactual is clean: the rejected trades simply don't happen.
No bars and no entry timestamps needed — so unlike the intrabar test this runs on the FULL era
(n=144 ex-PRE) instead of 20 trades.

Judged on: P&L of what it REJECTS (that is the money saved), what it KEEPS, and — because one
trade carried the last kill-test — the same figures with the single worst rejected trade removed.
"""
import json, pathlib, statistics as st

S = pathlib.Path("/private/tmp/claude-501/-Users-marcosolivera-Desktop-website-data/add2ac85-fd80-47f7-b583-bda802f0544d/scratchpad")
tr = json.loads((S / "trades.json").read_text())
tr = tr if isinstance(tr, list) else tr.get("trades", [])

# Era 7/13+, PRE quarantined (off-tape blind-stop exits — verified tonight).
era = [t for t in tr if (t.get("date") or "") >= "2026-07-13"
       and (t.get("entry_session") or "") != "PRE"]

def f(t, k, d=None):
    v = t.get(k)
    try:
        return float(v)
    except (TypeError, ValueError):
        return d

usable = [t for t in era if f(t, "entry") and f(t, "risk_per_share") is not None]
print(f"era 7/13+ ex-PRE: n={len(era)}, P&L {sum(f(t,'pnl',0) for t in era):+.2f}")
print(f"  usable (entry + risk_per_share present): n={len(usable)}, "
      f"P&L {sum(f(t,'pnl',0) for t in usable):+.2f}")
missing = [t for t in era if t not in usable]
if missing:
    print(f"  EXCLUDED for missing fields: n={len(missing)}, "
          f"P&L {sum(f(t,'pnl',0) for t in missing):+.2f} "
          f"({', '.join(sorted({t['ticker'] for t in missing}))[:90]})")


def report(title, keyfn, thresholds, label):
    print(f"\n{'='*104}\n{title}\n{'='*104}")
    print(f"{label:>14}{'kept n':>8}{'kept P&L':>11}{'kept win%':>11}"
          f"{'rejected n':>12}{'rejected P&L':>14}{'rej win%':>10}{'ex-worst rej':>14}")
    for x in thresholds:
        keep, rej = [], []
        for t in usable:
            v = keyfn(t)
            (rej if (v is not None and v < x) else keep).append(t)
        kp = sum(f(t, "pnl", 0) for t in keep); rp = sum(f(t, "pnl", 0) for t in rej)
        kw = (sum(1 for t in keep if f(t, "pnl", 0) > 0) / len(keep) * 100) if keep else 0
        rw = (sum(1 for t in rej if f(t, "pnl", 0) > 0) / len(rej) * 100) if rej else 0
        worst = min((f(t, "pnl", 0) for t in rej), default=0.0)
        print(f"{x:>14.2f}{len(keep):8}{kp:+11.2f}{kw:10.0f}%{len(rej):12}{rp:+14.2f}{rw:9.0f}%"
              f"{rp - worst:+14.2f}")


# (a) stop vs the L1 spread — needs entry_l1_spread
sp = [t for t in usable if f(t, "entry_l1_spread")]
print(f"\nspread field present on {len(sp)}/{len(usable)} usable rows")
def spread_ratio(t):
    s = f(t, "entry_l1_spread")
    r = f(t, "risk_per_share")
    return (r / s) if (s and s > 0 and r is not None) else None
report("(a) STOP WIDTH AS A MULTIPLE OF THE BID-ASK SPREAD  — reject below the threshold",
       spread_ratio, [1.0, 1.5, 2.0, 3.0, 4.0, 5.0], "min x spread")

# (b) stop as a percent of entry price
def pct_of_entry(t):
    e = f(t, "entry"); r = f(t, "risk_per_share")
    return (r / e * 100) if (e and e > 0 and r is not None) else None
report("(b) STOP WIDTH AS A PERCENT OF ENTRY PRICE — reject below the threshold",
       pct_of_entry, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "min stop %")

# What the tight-stop cohort looks like — the trades the rule would remove
print(f"\n{'='*104}\nTHE TIGHT-STOP COHORT (stop < 2x the spread) — what the rule actually removes\n{'='*104}")
tight = sorted([t for t in sp if (spread_ratio(t) or 9) < 2.0], key=lambda t: f(t, "pnl", 0))
print(f"{'date':11}{'ticker':7}{'lane':14}{'entry':>8}{'stop w':>8}{'spread':>8}{'x spr':>7}"
      f"{'shares':>8}{'P&L':>9}")
for t in tight:
    print(f"{(t.get('date') or ''):11}{t['ticker']:7}{(t.get('entry_type') or '?'):14}"
          f"{f(t,'entry',0):8.3f}{f(t,'risk_per_share',0):8.4f}{f(t,'entry_l1_spread',0):8.4f}"
          f"{(spread_ratio(t) or 0):7.2f}{int(f(t,'shares',0)):8}{f(t,'pnl',0):+9.2f}")
if tight:
    pnls = [f(t, "pnl", 0) for t in tight]
    print(f"\n  n={len(tight)}  total {sum(pnls):+.2f}  median {st.median(pnls):+.2f}  "
          f"winners {sum(1 for p in pnls if p>0)}/{len(pnls)}  worst {min(pnls):+.2f}")
    print(f"  median share count {st.median([f(t,'shares',0) for t in tight]):.0f} vs "
          f"{st.median([f(t,'shares',0) for t in usable]):.0f} for the era")
