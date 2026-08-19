#!/usr/bin/env python3
"""
MA_PULLBACK — IS THERE ANY SEPARATOR BETWEEN ITS WINNERS AND ITS LOSERS? (8/19)

Marcos: "run the study."

WHY THIS EXISTS, AND WHY IT IS NOT A THRESHOLD HUNT
  ma_pullback's held-MA test has NO ceiling on how far above the MA the close may finish, so a
  vertical expansion bar passes it (DEFECT_20260819_ma_pullback_no_pullback.md): CDTG 8/18 bought
  $7.78 after +57% in 11 minutes with no retrace, and the "dip" and the "reclaim" were the low and
  close of ONE +36% candle 40% apart.

  I called the fix "obvious — an extension ceiling." MARCOS KILLED THAT with one counterexample:
      CDTG  +40% above the 9-EMA  ->  LOST $26.76
      PFSA  +18% above the 9-EMA  ->  WON  $48.76
  A naive cap trades the day's second-best trade for its third-worst. So this study does not
  assume extension is the answer. It asks whether ANY of six candidate separators splits the
  population, and it is prepared to answer "none of them do."

DRIVER: data/killtests/ma_pullback_driver.py, whose selftest() asserts it reproduces both known
8/18 live fires on the same confirmation candle. THIS SCRIPT REFUSES TO RUN IF THAT FAILS —
grading with an unverified driver is what voided the lane-reorder study on 8/18.

CANDIDATE SEPARATORS, measured at the fire:
  ext_ma_pct     (price - held_ma) / held_ma            "how extended above the MA it held"
  conf_range_pct (conf.high - conf.low) / conf.low      "was the confirmation candle itself vertical"
  vwap_dist_pct  (price - vwap) / vwap                  "how far from the session line"
  run_15m_pct    price vs the close 15 min earlier      "did it already run into this"
  bars_since_dn  3-min bars since the last down-close   "was there an actual pullback at all"
  lowclose_pct   (conf.close - conf.low) / conf.low     "dip and reclaim inside one candle"

EXITS: E3 via F.sim_var (bank 1/2 at +10%, trail 10%-off-run-high, stop-first INTRABAR), the
detector's own stop, -1% entry slip, -0.5% exit slip. Identical for every fire, so the split is
the only thing being tested.

PRE-REGISTERED (written before the run)
  * A separator is REAL only if, splitting at its MEDIAN, the two halves differ by >= $8/trade on
    the HOLD-OUT and the sign of that difference matches the TRAIN half. Same-direction on both
    halves or it is noise.
  * Any cut is priced BOTH ways: dollars saved on the losers it blocks AND dollars lost on the
    winners it blocks. A cut that is net-positive only by refusing more trades than it improves
    is reported as such.
  * If no separator clears the bar, SAY SO. "ma_pullback buys extension by design" is a valid
    finding and turns the question into whether the lane is wanted, not what number to tune.
  * Chronological split: earliest 44 dates train, last 19 unseen. Both reported.

LIMITS: detector-only — no PULLBACK_FIRST, no price>vwap precondition, no chart gate, day-gain,
momentum, slots or capital. Fire counts far exceed live. The driver passes an EMPTY warm-up seed
and needs >=25 completed 3-min bars, so the first ~75 minutes of each session are invisible to
it; the live path sees them via MA_WARMUP_SEED. Nothing ships from this script.
"""
import importlib.util
import json
import os
import sys
import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ET = datetime.timezone(datetime.timedelta(hours=-4))


def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


P = _load("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
D = _load("DRV", HERE + "/ma_pullback_driver.py")
H = _load("H", HERE + "/live_harness.py")
S, E, F = P.S, P.E, P.F
OUT = []


def W(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def et(t):
    return datetime.datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).astimezone(ET)


def main():
    W("=" * 104)
    W("MA_PULLBACK — IS THERE ANY SEPARATOR?   (driver self-test first; no self-test, no study)")
    W("=" * 104)
    if not D.selftest(verbose=True):
        W("DRIVER SELF-TEST FAILED — refusing to grade anything."); return 1
    W("driver OK\n")

    S.load_all()
    dates = sorted({d for (_, d) in E.DAYS})
    agg = H.fn("aggregate_bars")
    rows = []
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        raw = [{"time": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]
        try:
            fs = D.fires(sym, date, bars=raw)
        except Exception:
            continue
        if not fs:
            continue
        cpv = cv = 0.0
        vw = []
        for b in bars:
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += tp * b["v"]; cv += b["v"]
            vw.append(cpv / cv if cv else b["c"])
        m3 = agg(raw, 3)
        for f in fs:
            i = f["i"]
            if i >= len(bars) - 2:
                continue
            px, stop = float(f["price"]), float(f["stop"] or 0)
            if stop <= 0 or stop >= px:
                continue
            # the confirmation candle = the last completed 3-min bar at the fire
            conf = None
            for cb in m3:
                if H.fn("_bar_epoch")(cb) == f["k"]:
                    conf = cb; break
            if not conf:
                continue
            ch, cl_, cc = (H.fn("_bar_high")(conf), H.fn("_bar_low")(conf), H.fn("_bar_close")(conf))
            if cl_ <= 0:
                continue
            ma = float(f["ma"] or 0)
            back = max(i - 90, 0)                       # 15 min = 90 ten-second bars
            try:
                pnl, _ex, _xi = F.sim_var(bars, emas, gaps, i, px, stop, "E3", "ma_pullback",
                                          halt_rule=True)
            except Exception:
                continue
            # bars since the last DOWN-closing 3-min candle before the confirmation bar
            dn = 0
            for cb in reversed(m3):
                if H.fn("_bar_epoch")(cb) >= f["k"]:
                    continue
                if H.fn("_bar_close")(cb) < H.fn("_bar_open")(cb):
                    break
                dn += 1
            rows.append({
                "sym": sym, "date": date, "pnl": pnl, "hms": f["hms"],
                "ext_ma_pct":     (px / ma - 1) * 100 if ma > 0 else None,
                "conf_range_pct": (ch / cl_ - 1) * 100,
                "vwap_dist_pct":  (px / vw[i] - 1) * 100 if vw[i] > 0 else None,
                "run_15m_pct":    (px / bars[back]["c"] - 1) * 100 if bars[back]["c"] > 0 else None,
                "bars_since_dn":  float(dn),
                "lowclose_pct":   (cc / cl_ - 1) * 100,
            })

    W(f"ma_pullback fires graded: {len(rows)}   over {len(dates)} dates\n")
    if len(rows) < 100:
        W("TOO FEW FIRES to split anything honestly."); return 1

    tr, ho = set(dates[:44]), set(dates[44:])

    def half(rs, key):
        v = sorted(r[key] for r in rs if r.get(key) is not None)
        if not v:
            return None, None, None
        med = v[len(v) // 2]
        lo = [r for r in rs if r.get(key) is not None and r[key] <= med]
        hi = [r for r in rs if r.get(key) is not None and r[key] > med]
        return med, lo, hi

    def per(rs):
        return (sum(r["pnl"] for r in rs) / len(rs)) if rs else None

    KEYS = ["ext_ma_pct", "conf_range_pct", "vwap_dist_pct", "run_15m_pct",
            "bars_since_dn", "lowclose_pct"]
    W(f"{'separator':16s} {'median':>9s} | {'TRAIN low':>10s} {'TRAIN high':>10s} {'Δ':>8s} "
      f"| {'HO low':>9s} {'HO high':>9s} {'Δ':>8s}  {'n(ho)':>6s}  verdict")
    results = {}
    for k in KEYS:
        med, _lo_all, _hi_all = half(rows, k)
        if med is None:
            continue
        trr = [r for r in rows if r["date"] in tr]
        hor = [r for r in rows if r["date"] in ho]
        _, tl, th = half(trr, k)
        _, hl, hh = half(hor, k)
        tdl, tdh = per(tl), per(th)
        hdl, hdh = per(hl), per(hh)
        if None in (tdl, tdh, hdl, hdh):
            continue
        td, hd = (tdh - tdl), (hdh - hdl)
        real = abs(hd) >= 8.0 and (td * hd > 0)
        results[k] = {"med": med, "train_d": td, "ho_d": hd, "real": real,
                      "hl": hdl, "hh": hdh, "n": len(hl) + len(hh)}
        W(f"{k:16s} {med:9.2f} | {tdl:10.2f} {tdh:10.2f} {td:8.2f} "
          f"| {hdl:9.2f} {hdh:9.2f} {hd:8.2f}  {len(hl)+len(hh):6d}  "
          f"{'SEPARATES' if real else '-'}")

    W("\n" + "=" * 104)
    W("PRE-REGISTERED VERDICT")
    W("=" * 104)
    winners = [k for k, v in results.items() if v["real"]]
    if not winners:
        W("  NO SEPARATOR CLEARS THE BAR (hold-out |Δ| >= $8/trade AND same sign as train).")
        W("  On this evidence ma_pullback's winners and losers are NOT distinguishable by how")
        W("  extended the entry is, how vertical the confirmation candle is, distance from VWAP,")
        W("  the prior run, whether a real pullback preceded it, or the dip-and-reclaim spread.")
        W("")
        W("  => THE EXTENSION CEILING IS REFUTED as stated. Marcos's PFSA counterexample was not")
        W("     an exception — it is the rule: this lane buys extension, and the extension does")
        W("     not predict the outcome. The honest question becomes whether the LANE is wanted,")
        W("     not what number to tune. Any cut here is a coin-flip that costs winners.")
    else:
        W(f"  {len(winners)} separator(s) clear the bar: {winners}")
        for k in winners:
            v = results[k]
            W(f"    {k}: hold-out low-half ${v['hl']:+.2f}/tr vs high-half ${v['hh']:+.2f}/tr "
              f"(Δ ${v['ho_d']:+.2f}, train Δ ${v['train_d']:+.2f}, n={v['n']}) median {v['med']:.2f}")
        W("\n  A cut must still be PRICED BOTH WAYS before it is proposed — dollars saved on the")
        W("  losers it blocks AND dollars lost on the winners it blocks. Not done here.")
    W("\nLIMITS: detector-only, no funnel; empty warm-up seed so the first ~75 min of each session")
    W("are invisible; fire counts far exceed live. Nothing ships from this script.")
    json.dump({"out": OUT}, open(HERE + "/ma_pullback_separator_20260819_out.json", "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
