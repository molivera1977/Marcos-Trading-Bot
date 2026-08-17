#!/usr/bin/env python3
"""KEVSEQ RECONCILIATION 8/17 — why study (A) says +$340 and study (B) says -$3.54.

Analysis only.  No bot edits.  Engine imported UNCHANGED from
sunday_afternoon_studies_20260816 (-> G -> F -> C -> B -> E), same as
entry_drift_20260817.py, so the two studies share one exit model.

Three arms on ONE fire-set, ONE exit model (E3 live-parity, $500):
  ARM-SPEC : entry at the detector's fire price, structural stop   (what study A assumed)
  ARM-LIVE : entry at the drifted live-quote proxy (fill-bar close) (what the code did)
  ARM-F3   : resting limit at fire_px*1.005, unfilled = no trade    (the 8/17 fix)

Cohorts: universe cache (MINE / HOLD-OUT split), the 8/16 fast-chart 197 name-days
(intersected with the cache), and the NON-fast-chart complement (the selection test).
"""
import importlib.util, os, json, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec2 = importlib.util.spec_from_file_location("D", HERE + "/entry_drift_20260817.py")
D = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(D)
# ONE engine instance, D's — importing sunday_afternoon_studies twice would give two
# separate E.DAYS caches and silently grade against an empty one.
S = D.S; G = S.G; F = S.F; C = S.C; B = S.B; E = S.E

MINE_LO, MINE_HI = "2026-05-18", "2026-07-21"
HOLD_LO, HOLD_HI = "2026-07-22", "2026-08-14"

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)


def sim(f, entry_px, stop, i=None):
    if not (stop and 0 < stop < entry_px): return None
    rb, emas, gaps = E.DAYS[(f["sym"], f["date"])]
    ii = f["i"] if i is None else i
    if ii >= len(rb) - 2: return None
    pnl, why, xi = F.sim_var(rb, emas, gaps, ii, entry_px, stop, "E3", "kevseq", True)
    return dict(pnl=pnl, why=why, sym=f["sym"], date=f["date"])


def arm_spec(fires):
    return [x for x in (sim(f, f["fire_px"], f["stop"]) for f in fires) if x]

def arm_live(fires):
    return [x for x in (sim(f, f["fill_px"], f["stop"]) for f in fires) if x]

def arm_f3(fires, tol=0.005, nbars=0):
    out = []
    for f in fires:
        lim = round(f["fire_px"] * (1 + tol), 4)
        rb = E.DAYS[(f["sym"], f["date"])][0]
        fi = None
        if f["bar_lo"] <= lim:
            fi = f["i"]
        else:
            for j in range(f["i"] + 1, min(f["i"] + 1 + nbars, len(rb))):
                if rb[j]["l"] <= lim: fi = j; break
                if rb[j]["l"] <= f["stop"]: break
        if fi is None: continue
        x = sim(f, lim, f["stop"], i=fi)
        if x: out.append(x)
    return out


def row(name, tr):
    if not tr:
        P(f"| {name} | 0 | — | — | — | — |"); return dict(N=0, tot=0.0, dtr=0.0, win=0.0, worst=0.0)
    n = len(tr); tot = sum(x["pnl"] for x in tr)
    win = 100.0 * sum(1 for x in tr if x["pnl"] > 0) / n
    worst = min(x["pnl"] for x in tr)
    P(f"| {name} | {n} | ${tot:+.2f} | ${tot/n:+.2f} | {win:.0f}% | ${worst:+.2f} |")
    return dict(N=n, tot=tot, dtr=tot / n, win=win, worst=worst)


def grid(label, fires, res):
    P("")
    P(f"### {label}  (fires={len(fires)})")
    P("| arm | N | total | $/tr | win | worst |")
    P("|---|---|---|---|---|---|")
    res[label] = {
        "ARM-SPEC": row("ARM-SPEC entry@fire_px, structural stop", arm_spec(fires)),
        "ARM-LIVE": row("ARM-LIVE entry@drifted quote, same stop", arm_live(fires)),
        "ARM-F3":   row("ARM-F3 limit@fire+0.5%, unfilled=no trade", arm_f3(fires)),
    }
    return res[label]


def main():
    fires, dates = D.collect()
    for f in fires:
        f["drift"] = (f["fill_px"] - f["fire_px"]) / f["fire_px"]
    P(f"universe kevseq fires: {len(fires)} over {len(dates)} dates {dates[0]}..{dates[-1]}")

    ds = sorted(f["drift"] * 100 for f in fires)
    P(f"modelled drift: median {statistics.median(ds):+.2f}%  p90 {D.pctile(ds,90):+.2f}%  "
      f"max {max(ds):+.2f}%   (live-stamped: median +5.02%, p90 +7.09%, max +28.87%, N=13)")
    P("NOTE: the replay's drift proxy is the FILL-BAR CLOSE, which UNDERSTATES the live "
      "quote drift.  ARM-SPEC vs ARM-LIVE therefore LOWER-BOUNDS the drift damage.")

    fc_nd = {(a, b) for a, b in json.load(open(HERE + "/_fc_nd.json"))}
    cache_nd = set(E.DAYS.keys())
    ov = fc_nd & cache_nd
    P("")
    P(f"COHORT OVERLAP: fast-chart cohort {len(fc_nd)} name-days, universe cache {len(cache_nd)}, "
      f"intersection {len(ov)} ({100.0*len(ov)/len(fc_nd):.0f}% of A's cohort, "
      f"{100.0*len(ov)/len(cache_nd):.0f}% of B's)")
    fc_dates = {d for _, d in fc_nd}; un_dates = {d for _, d in cache_nd}
    P(f"dates: A {len(fc_dates)} ({min(fc_dates)}..{max(fc_dates)}), "
      f"B {len(un_dates)} ({min(un_dates)}..{max(un_dates)}), shared {len(fc_dates & un_dates)}")

    mine = [f for f in fires if MINE_LO <= f["date"] <= MINE_HI]
    hold = [f for f in fires if HOLD_LO <= f["date"] <= HOLD_HI]
    fc   = [f for f in fires if (f["sym"], f["date"]) in fc_nd]
    nfc  = [f for f in fires if (f["sym"], f["date"]) not in fc_nd]
    fc_mine = [f for f in fc if MINE_LO <= f["date"] <= MINE_HI]
    fc_hold = [f for f in fc if HOLD_LO <= f["date"] <= HOLD_HI]
    nfc_mine = [f for f in nfc if MINE_LO <= f["date"] <= MINE_HI]
    nfc_hold = [f for f in nfc if HOLD_LO <= f["date"] <= HOLD_HI]

    res = {}
    grid("UNIVERSE-MINE (05-18..07-21)", mine, res)
    grid("UNIVERSE-HOLDOUT (07-22..08-14)", hold, res)
    grid("FASTCHART-COHORT-MINE", fc_mine, res)
    grid("FASTCHART-COHORT-HOLDOUT", fc_hold, res)
    grid("FASTCHART-COHORT-ALL", fc, res)
    grid("NON-FASTCHART-MINE (selection control)", nfc_mine, res)
    grid("NON-FASTCHART-HOLDOUT (selection control)", nfc_hold, res)
    grid("NON-FASTCHART-ALL (selection control)", nfc, res)

    # per-name-day fire rate, the density comparison
    P("")
    P(f"fire density: fast-chart cohort {len(fc)}/{len(ov)} name-days = "
      f"{len(fc)/max(1,len(ov)):.2f} fires/nd ; non-fast-chart {len(nfc)}/"
      f"{len(cache_nd)-len(ov)} = {len(nfc)/max(1,len(cache_nd)-len(ov)):.2f} fires/nd")
    P(f"study A's SEQ arm density: 79 fires / 198 name-days = 0.40 fires/nd "
      f"(det-B subset: 59/198 = 0.30)")

    json.dump({"res": res, "overlap": len(ov), "fc_nd": len(fc_nd), "cache_nd": len(cache_nd),
               "drift_median": statistics.median(ds)},
              open(HERE + "/kevseq_reconciliation_20260817_out.json", "w"), indent=1)
    open(HERE + "/kevseq_reconciliation_20260817_run.txt", "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
