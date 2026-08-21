#!/usr/bin/env python3
"""
VWAP_RECLAIM — THE FULL RE-EXAMINATION (8/21, Marcos: "let's talk vwap reclaim" -> "build it")

THE AGENDA ITEM: reclaim was benched to shadow 8/19 and the docket says "examine vwap_reclaim".
Three facts from tonight's census (live archive 7/28-8/20) reframe it:

  1. THE BENCH WAS DECIDED ON THE WRONG 26%. The benching evidence split the lane at a 4% stop
     floor and studied the >=4% "fillable" slice (TRAIN +$14.66 -> OOS -$0.64, sign-unstable).
     Measured over 794 stamped fires the width distribution is: <1% 130 (17%) · 1-4% 457 (58%)
     · >=4% 207 (26%). The lane's CENTRE OF MASS was the refused slice. The floor became 1%
     today (Addendum 14), so that 58% is now takeable and has never been priced.
  2. THE REAL GATEKEEPER IS FIREVOL, NOT MIN-STOP. reclaim_firevol_reject killed 339 of 934
     fires (36%) — ten times min-stop's 29. marcos_trading_bot.py:7149 already records the
     suspicion that the REJECTED firevol cohort outperforms the ACCEPTED one, with the kill
     switch RECLAIM_FIREVOL=0 sitting unused. A backwards gate is worth more than any exit tweak.
  3. "WHAT KILLED IT" IS MOSTLY MEANINGLESS WHILE BENCHED. 412 of 934 fires have no gate row at
     all (181 PRE / 231 RTH) — they are followed by `consolidating`/`watching`. The bench, not a
     gate, is what stopped them. So this file grades EVERY fire as a counterfactual trade
     instead of grading refusals.

WHAT THIS RUNS — every reclaim_shadow_fire 7/28-8/20 with a stamped price and stop, walked on
the real tape at real NBBO spreads under TODAY's shipped config (1% floor, k=1 spread guard),
$30 risk / 70%/$1000 clamp, capital-aware at $3,000 and $5,000, TOTAL DOLLARS as the verdict
(the 8/20 law). Tape is fetched ONCE per (day, ticker) and reused across that name's fires.

THE CUTS (each answers a live question, none is decoration)
  SESSION     PRE vs RTH, reported separately — Marcos's standing doctrine (RTH is the headline,
              premarket its own line). The opening-hour claim that survived the bench
              (+$17.20/fill, n=306, #2 in the block) lives inside the RTH cut.
  FIREVOL     accepted vs rejected cohorts priced side by side. If the rejected set wins, the
              gate is backwards and :7149's suspicion becomes a measured fact.
  WIDTH BAND  <1% / 1-4% / >=4% — the 4% line is exactly where the bench was decided, so this
              is the reconciliation the RECONCILE-BEFORE-REPORTING law demands: the old verdict
              and the new one must be visible on the same axis.
  EXIT        E3 (baseline) · POP5 · POP8 · HALF5 · T10 · T20 · VWAP (stop rides session VWAP —
              the lane's own thesis, the arm that asks whether reclaim needs its OWN engine
              rather than a min-stop exemption).

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  A. The lane earns an UNBENCH ARGUMENT iff, under the best exit, the RTH cut is positive in
     total dollars at BOTH books AND survives dropping its single best trade.
  B. FIREVOL is declared backwards iff the REJECTED cohort beats the ACCEPTED cohort in total
     dollars on the same exit AND that holds in both halves (even/odd dates).
  C. The 1-4% band is the bench reconciliation: if it is positive, the bench rested on a slice
     that was never the lane; if negative, the bench was right for a reason nobody had measured.
  D. Nothing ships from this file. It writes JSON and prints.

LIMITS: entry/stop AS STAMPED by the lane (no hindsight re-derivation); median-of-minute spread;
no slot contention beyond capital; PRE walks flatten 09:25 and RTH 15:45 per live doctrine; a
name-day whose tape is thin (<50 prints) is skipped and counted.
"""
import collections
import datetime as dt
import importlib.util
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = "https://zestful-intuition-production-b16a.up.railway.app"
RISK = 30.0
BOOKS = (3000.0, 5000.0)
MIN_STOP_PCT, SPREAD_K = 1.0, 1.0

sp = importlib.util.spec_from_file_location("HF", os.path.join(HERE, "halt_arm_feed_20260820.py"))
HF = importlib.util.module_from_spec(sp)
sp.loader.exec_module(HF)

ARMS = ("E3", "POP5", "POP8", "HALF5", "T10", "T20", "VWAP")


def fires():
    """Every stamped reclaim fire, tagged with whether firevol rejected it."""
    out = []
    for i in range(0, 25):
        d = (dt.date(2026, 8, 20) - dt.timedelta(days=i)).isoformat()
        try:
            rows = json.load(urllib.request.urlopen(
                f"{BOARD}/api/decisions_archive?date={d}&limit=50000&key=marcos2026",
                timeout=45)).get("rows") or []
        except Exception:
            continue
        for t in [r for r in rows if r.get("status") == "reclaim_shadow_fire"]:
            tk, ts = t.get("ticker"), str(t.get("recorded_at") or "")
            px, stp = t.get("price"), t.get("stop")
            if not (tk and ts and px and stp):
                continue
            px, stp = float(px), float(stp)
            if px <= stp or stp <= 0:
                continue
            nxt = [r for r in rows if r.get("ticker") == tk
                   and str(r.get("recorded_at") or "") >= ts][:8]
            fv = any(r.get("status") == "reclaim_firevol_reject" for r in nxt)
            hhmm = ts[11:16]
            out.append({"d": d, "tk": tk, "ts": ts[11:19], "hhmm": hhmm, "px": px, "stop": stp,
                        "firevol_rejected": fv,
                        "sess": "PRE" if hhmm < "09:30" else "RTH",
                        "w": (px - stp) / px * 100})
    return out


def walk(b10, k0, entry, stop, spr, arm, pre, vwap=None):
    ks = [x for x in sorted(b10) if x >= k0]
    if len(ks) < 2:
        return None
    half = (spr / 2) if spr else entry * 0.0025
    px = entry + half
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(max(BOOKS) * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    flat = "09:25" if pre else "15:45"
    t0 = ks[0]
    for k in ks[1:]:
        x = b10[k]
        if HF.hm_k(k) >= flat:
            return banked + rem * ((x["c"] - half) - px), sh * px, k
        if arm == "VWAP" and vwap is not None:
            v = vwap.get(k)
            if v and x["c"] < v * 0.997:            # thesis dead: closed back under VWAP
                return banked + rem * ((x["c"] - half) - px), sh * px, k
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, k
        runhi = max(runhi, x["h"])
        if arm in ("POP5", "POP8", "HALF5"):
            tgt = 1.05 if arm in ("POP5", "HALF5") else 1.08
            if not tiered and x["h"] >= px * tgt:
                if arm in ("POP5", "POP8"):
                    return banked + rem * (px * tgt - px), sh * px, k
                n = rem // 2 or rem
                banked += n * (px * tgt - px)
                rem -= n
                tiered, stop = True, px
                if rem == 0:
                    return banked, sh * px, k
        if arm in ("E3", "VWAP") and not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked, sh * px, k
        if arm in ("T10", "T20") and k - t0 >= (600 if arm == "T10" else 1200):
            return banked + rem * ((x["c"] - half) - px), sh * px, k
        if arm in ("E3", "HALF5") and tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, k
    lk = ks[-1]
    return banked + rem * ((b10[lk]["c"] - half) - px), sh * px, lk


def vwap_series(b10):
    """Running session VWAP over the reconstructed buckets (typical price x volume)."""
    out, pv, vv = {}, 0.0, 0.0
    for k in sorted(b10):
        x = b10[k]
        tp = (x["h"] + x["l"] + x["c"]) / 3.0
        pv += tp * x["v"]
        vv += x["v"]
        out[k] = (pv / vv) if vv else None
    return out


def book(fl, bal, key="pnl"):
    byday = collections.defaultdict(list)
    for f in fl:
        byday[f["d"]].append(f)
    tot = n = 0
    for d, l in byday.items():
        op = []
        for f in sorted(l, key=lambda x: x["ti"]):
            op = [o for o in op if o[0] > f["ti"]]
            if f["n"] > bal - sum(o[1] for o in op):
                continue
            op.append((f["tx"], f["n"]))
            tot += f[key]
            n += 1
    return tot, n


def main():
    fl = fires()
    print(f"stamped reclaim fires 7/28-8/20: {len(fl)}")
    bynd = collections.defaultdict(list)
    for f in fl:
        bynd[(f["d"], f["tk"])].append(f)
    print(f"name-days to fetch: {len(bynd)}\n")

    res, skipped = [], 0
    for i, ((d, tk), l) in enumerate(sorted(bynd.items()), 1):
        lo = min(x["ts"] for x in l)
        tr = HF.trades(tk, d, lo, "15:50:00")
        print(f"  [{i}/{len(bynd)}] {d} {tk} fires={len(l)} trades={len(tr)}", flush=True)
        if len(tr) < 50:
            skipped += len(l)
            continue
        b10 = HF.bars(tr, 10)
        vw = vwap_series(b10)
        ks = sorted(b10)
        for f in l:
            if f["w"] < MIN_STOP_PCT:
                f["today_ok"] = False
            spr = HF.spread_at(tk, d, f["ts"][:5])
            f["spr"] = spr
            if f.get("today_ok") is not False:
                f["today_ok"] = not (SPREAD_K > 0 and spr
                                     and (f["px"] - f["stop"]) < SPREAD_K * spr)
            t_ep = dt.datetime.fromisoformat(f"{d}T{f['ts']}+00:00").timestamp() + 4 * 3600
            k0 = min((x for x in ks if x >= t_ep), default=None)
            if k0 is None:
                skipped += 1
                continue
            f["ti"] = k0
            for arm in ARMS:
                r = walk(b10, k0, f["px"], f["stop"], spr, arm, f["sess"] == "PRE", vw)
                if r is None:
                    continue
                f[f"pnl_{arm}"] = r[0]
                f["n"], f["tx"] = r[1], r[2]
            if "pnl_E3" in f:
                res.append(f)
    print(f"\nwalked {len(res)} | skipped {skipped} | quotes {HF._qgap[1]} gaps {HF._qgap[0]}")

    live = [f for f in res if f.get("today_ok")]
    print(f"takeable under TODAY's gates (1% floor, k=1): {len(live)} of {len(res)}\n")

    def table(title, rows):
        print(f"\n=== {title}  (n={len(rows)}) ===")
        if not rows:
            print("   (empty)")
            return
        print(f"{'exit':>6s} {'taken':>6s} {'$5,000':>11s} {'$/tr':>8s} {'w/o best':>10s} "
              f"{'TRAIN':>9s} {'OOS':>9s} {'win%':>5s}")
        for arm in ARMS:
            k = f"pnl_{arm}"
            sub = [r for r in rows if k in r]
            if not sub:
                continue
            t5, n5 = book(sub, 5000.0, k)
            tr_ = sum(r[k] for r in sub if int(r["d"][-2:]) % 2 == 0)
            oo = sum(r[k] for r in sub if int(r["d"][-2:]) % 2 == 1)
            p = sorted((r[k] for r in sub), reverse=True)
            win = 100 * sum(1 for x in p if x > 0) / len(p)
            print(f"{arm:>6s} {n5:6d} {t5:+11.2f} {(t5/n5 if n5 else 0):+8.2f} "
                  f"{t5-(p[0] if p else 0):+10.2f} {tr_:+9.2f} {oo:+9.2f} {win:4.0f}%")

    table("ALL TAKEABLE", live)
    table("RTH ONLY (the headline cut)", [f for f in live if f["sess"] == "RTH"])
    table("PRE ONLY (its own line, per doctrine)", [f for f in live if f["sess"] == "PRE"])
    table("OPENING HOUR 09:30-10:30 (the claim that survived the bench)",
          [f for f in live if f["sess"] == "RTH" and "09:30" <= f["hhmm"] < "10:30"])
    table("FIREVOL **ACCEPTED**", [f for f in live if not f["firevol_rejected"]])
    table("FIREVOL **REJECTED** (:7149 says this one wins — testing it)",
          [f for f in live if f["firevol_rejected"]])
    table("WIDTH 1-4% (the band the bench never priced)",
          [f for f in live if 1.0 <= f["w"] < 4.0])
    table("WIDTH >=4% (the slice the bench WAS decided on)", [f for f in live if f["w"] >= 4.0])

    t3, n3 = book(live, 3000.0, "pnl_E3")
    print(f"\ncapital check — ALL TAKEABLE on E3: $3,000 {t3:+.2f}/{n3} vs "
          f"$5,000 {book(live,5000.0,'pnl_E3')[0]:+.2f}/{book(live,5000.0,'pnl_E3')[1]}")
    json.dump(res, open(os.path.join(HERE, "reclaim_full_20260821_out.json"), "w"), default=str)
    print("\nPRE-REGISTERED: (A) unbench argument needs RTH positive at BOTH books under the best")
    print("exit AND drop-best-positive. (B) firevol is backwards iff REJECTED beats ACCEPTED in")
    print("both halves. (C) the 1-4% band is the bench reconciliation. Nothing ships here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
