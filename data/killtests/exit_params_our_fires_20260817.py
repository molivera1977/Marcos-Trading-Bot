#!/usr/bin/env python3
"""8/17 STOP/TRAIL SWEEP ON OUR OWN REAL FIRES.

Marcos: "we don't randomly enter at certain times!" — the runner_model_test used CLOCK
entries. This study replaces them with the bot's ACTUAL fire points from today's
decision archive, and varies ONLY the exit.

Analysis only. No bot edits, no deploy, no env change.
"""
import os, sys, json, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runner_model_test_20260817 as R   # tape builder + key plumbing reuse

HERE = os.path.dirname(os.path.abspath(__file__))
ARCH = os.path.join(HERE, "exit_params_our_fires_20260817_arch.json")
OUT = os.path.join(HERE, "exit_params_our_fires_20260817_out.json")

DAY = "2026-08-17"
POS = 500.0
MKT = 0.005            # market-exit slip
SLIP = 0.01            # entry slip (arm default = today's model)
FLAT = 15 * 3600 + 45 * 60
OPEN_S = 9 * 3600 + 30 * 60
SETUP_TF = 3 * 60
ZONE_BUF = 0.003
STOP_LOSS_PCT = 0.07
MA_STOP_BUF = 0.01

# widen tape window to cover premarket fires (04:00 ET = 08:00Z)
R.B10 = os.path.join(HERE, "bars10s_0817_full")
os.makedirs(R.B10, exist_ok=True)
_orig_build = R.build_10s


def build_10s(t):
    p = os.path.join(R.B10, t + ".json")
    if os.path.exists(p):
        return json.load(open(p))["bars"]
    import requests, collections as _c
    url = "https://data.alpaca.markets/v2/stocks/trades"
    params = {"symbols": t, "start": f"{DAY}T08:00:00Z", "end": f"{DAY}T20:00:00Z",
              "limit": 10000, "feed": "sip"}
    buckets = _c.OrderedDict()
    tok, ntr = None, 0
    while True:
        q = dict(params)
        if tok:
            q["page_token"] = tok
        r = R.S.get(url, headers=R.H(), params=q, timeout=90)
        if r.status_code != 200:
            print(f"  !! {t} HTTP {r.status_code} {r.text[:150]}")
            return []
        j = r.json()
        for tr in (j.get("trades") or {}).get(t, []):
            ts = tr["t"]
            sec = int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + int(float(ts[17:23]))
            k = sec // 10 * 10
            px, sz = float(tr["p"]), int(tr["s"])
            b = buckets.get(k)
            if b is None:
                buckets[k] = {"utc": k, "open": px, "high": px, "low": px, "close": px,
                              "volume": sz, "pv": px * sz}
            else:
                b["high"] = max(b["high"], px); b["low"] = min(b["low"], px)
                b["close"] = px; b["volume"] += sz; b["pv"] += px * sz
            ntr += 1
        tok = j.get("next_page_token")
        if not tok:
            break
    bars = [buckets[k] for k in sorted(buckets)]
    json.dump({"bars": bars}, open(p, "w"))
    print(f"  {t}: {ntr} trades, {len(bars)} 10s bars")
    return bars


R.build_10s = build_10s
R._bars = {}
bars = R.bars
bsec = R.bsec


# ---------------- fire set ----------------
LANE = {
    "triggered_flat_top": "flat_top", "triggered_ma_pullback": "ma_pullback",
    "triggered_ignition": "ignition", "triggered_kevseq": "kevseq",
    "triggered_v2conv": "v2conv", "triggered_grinder": "grinder",
    "triggered_vwap_reclaim_kev3gate": "vwap_reclaim", "triggered_orb": "orb",
    "triggered_dip_rip": "dip_rip", "triggered_prevwap": "prevwap",
    "triggered_bounce": "bounce", "hidden_shadow_fire": "hidden_shadow",
}


def et_sec(rec):
    # recorded_at "2026-08-17T04:05:14.231460-04:00"
    return int(rec[11:13]) * 3600 + int(rec[14:16]) * 60 + int(rec[17:19])


def idx_at(t, s):
    B = bars(t)
    for i, b in enumerate(B):
        if bsec(b) >= s:
            return i
    return None


def tf_bars_before(t, s, n, tf=SETUP_TF):
    """last n completed setup-TF bar lows before s (built from the 10s tape)."""
    B = [b for b in bars(t) if bsec(b) < s]
    if not B:
        return []
    agg = collections.OrderedDict()
    for b in B:
        k = bsec(b) // tf * tf
        a = agg.get(k)
        if a is None:
            agg[k] = {"lo": b["low"], "hi": b["high"], "close": b["close"], "k": k}
        else:
            a["lo"] = min(a["lo"], b["low"]); a["hi"] = max(a["hi"], b["high"])
            a["close"] = b["close"]
    ks = sorted(agg)
    return [agg[k] for k in ks[-n:]]


def orb_low(t):
    B = [b for b in bars(t) if OPEN_S <= bsec(b) < OPEN_S + 300]
    return min((b["low"] for b in B), default=None)


def derive_stop(lane, row, t, s, entry_ref):
    """Returns (stop, how) or (None, reason). Derivations mirror the bot's own code."""
    st = row.get("stop") or row.get("would_stop") or row.get("zone_stop")
    if st:
        return float(st), "logged"
    if lane == "flat_top":
        tb = tf_bars_before(t, s, 4)
        if not tb:
            return None, "no_tape_window"
        w_low = min(b["lo"] for b in tb)
        if row.get("break_attack"):
            return round(w_low, 4), "derived:break_attack w_low exact"
        return max(round(w_low * (1 - ZONE_BUF), 4),
                   round(entry_ref * (1 - STOP_LOSS_PCT), 4)), "derived:max(w_low-0.3%, -7%)"
    if lane == "ma_pullback":
        tb = tf_bars_before(t, s, 1)
        if not tb:
            return None, "no_tape_window"
        # bot: stop = min(ma, confirmation-candle low) * (1-1%). The wick low is
        # ~always the min (the pullback dips through the MA), so the confirmation
        # bar low is the faithful reconstruction.
        return round(tb[-1]["lo"] * (1 - MA_STOP_BUF), 4), "derived:conf-bar low -1%"
    if lane == "ignition":
        tb = tf_bars_before(t, s, 5)
        if not tb:
            return None, "no_tape_window"
        base_lo = min(b["lo"] for b in tb)
        return round(base_lo * (1 - ZONE_BUF), 4), "derived:base_lo -0.3%"
    if lane == "orb":
        ol = orb_low(t)
        if not ol:
            return None, "no_or_window"
        return max(round(ol * (1 - ZONE_BUF), 4),
                   round(entry_ref * (1 - STOP_LOSS_PCT), 4)), "derived:max(OR-low-0.3%, -7%)"
    if lane == "vwap_reclaim":
        v = row.get("vwap")
        tb = tf_bars_before(t, s, 1)
        if not (v and tb):
            return None, "no_vwap_or_tape"
        return round(min(tb[-1]["close"], float(v)) * 0.99, 4), "derived:min(close,vwap)-1%"
    if lane == "bounce":
        tb = tf_bars_before(t, s, 1)
        if not tb:
            return None, "no_tape_window"
        return round(tb[-1]["lo"] * 0.99, 4), "derived:conf-bar low -1%"
    return None, "no_rule"


def load_fires():
    d = json.load(open(ARCH))
    rows = d["rows"]
    fires, excl = [], collections.Counter()
    for r in rows:
        lane = LANE.get(r.get("status"))
        if not lane:
            continue
        t = r.get("ticker")
        ra = r.get("recorded_at")
        px = r.get("price")
        if not (t and ra and px):
            excl[lane + ":no_fields"] += 1
            continue
        s = et_sec(ra)
        if s >= FLAT:
            excl[lane + ":after_flatten"] += 1
            continue
        if not bars(t):
            excl[lane + ":no_tape"] += 1
            continue
        i0 = idx_at(t, s)
        if i0 is None or i0 >= len(bars(t)) - 2:
            excl[lane + ":no_tape_at_fire"] += 1
            continue
        entry_ref = float(px)
        st, how = derive_stop(lane, r, t, s, entry_ref)
        if st is None:
            excl[lane + ":" + how] += 1
            continue
        if not (0 < st < entry_ref):
            excl[lane + ":bad_stop"] += 1
            continue
        fires.append({"t": t, "lane": lane, "sec": s, "ref": entry_ref,
                      "stop": float(st), "how": how})
    fires.sort(key=lambda f: f["sec"])
    return fires, excl


# ---------------- exit engine ----------------
def sim(f, stop_mult=1.0, stop_floor10=False, trail=0.10, bank=0.10, slip=SLIP):
    """Returns dict with pnl, reason, exit_sec, exit_px, mfe, recovered."""
    t = f["t"]
    entry = f["ref"] * (1 + slip)
    dist = entry - f["stop"] * (f["stop"] / f["stop"])   # keep float
    dist = entry - f["stop"]
    stop = entry - dist * stop_mult
    if stop_floor10:
        stop = min(stop, entry * 0.90)
    if stop <= 0:
        stop = entry * 0.01
    B = bars(t)
    i0 = idx_at(t, f["sec"])
    sh = POS / entry
    rem, pnl = sh, 0.0
    scaled = False
    banksh = sh * 0.5
    target = entry * (1 + bank) if bank else None
    run_hi = entry
    mfe = entry
    out = None
    for i in range(i0 + 1, len(B)):
        b = B[i]
        if bsec(b) >= FLAT:
            break
        mfe = max(mfe, b["high"])
        if b["low"] <= stop:                       # intrabar stop FIRST (ties against us)
            px = stop * (1 - MKT)
            pnl += rem * (px - entry)
            out = (pnl, "stop", bsec(b), px, i)
            break
        if target and not scaled and b["high"] >= target:
            pnl += banksh * (target - entry)
            rem -= banksh
            scaled = True
            continue
        run_hi = max(run_hi, b["high"])
        if trail and (scaled or not target) and b["close"] < run_hi * (1 - trail):
            px = b["close"] * (1 - MKT)
            pnl += rem * (px - entry)
            out = (pnl, "trail", bsec(b), px, i)
            break
    if out is None:
        last, li = None, None
        for i, b in enumerate(B):
            if bsec(b) < FLAT:
                last, li = b, i
        px = last["close"] * (1 - MKT)
        pnl += rem * (px - entry)
        out = (pnl, "flatten", FLAT, px, li)
    pnl, reason, xs, xpx, xi = out
    rec = False
    if reason == "stop":
        for j in range(xi + 1, len(B)):
            if bsec(B[j]) >= FLAT:
                break
            if B[j]["high"] >= entry:
                rec = True
                break
    return {"pnl": pnl, "ppd": pnl / POS, "stop_used": stop,
            "reason": reason, "exit_sec": xs, "exit_px": xpx,
            "mfe": mfe, "entry": entry, "recovered": rec,
            "tts": (xs - f["sec"]) if reason == "stop" else None,
            "cap": ((xpx - entry) / (mfe - entry)) if mfe > entry else None}


# ---------------- capital ledger (THE REAL CONSTRAINT) ----------------
SIM_BAL = 3000.0
MAX_POSITION_SIZE = 0.70
MAX_TRADE_DOLLARS = 1000.0
RISK_PER_TRADE = 30.0
RISK_PROP_REF = 0.06
MAX_POS_VOL_PCT = 0.05


def vol_cap_shares(t, s):
    """5% of avg last-3 COMPLETED 1-min bar volume before the fire (from the 10s tape)."""
    agg = collections.OrderedDict()
    for b in bars(t):
        k = bsec(b) // 60 * 60
        if k >= s // 60 * 60:
            break
        agg[k] = agg.get(k, 0) + b["volume"]
    ks = sorted(agg)[-3:]
    if not ks:
        return None
    av = sum(agg[k] for k in ks) / len(ks)
    return max(1, int(av * MAX_POS_VOL_PCT)) if av > 0 else None


_VC = {}


def size_shares(f, entry, stop, balance):
    """Bot sizing chain: risk-based -> notional cap -> volume cap.
    (VWAP-side halving omitted: needs live vwap+crown state; fail-open = full size.
     Omission is documented in the .md — it would only shrink field positions.)"""
    pos_size = min(balance * MAX_POSITION_SIZE, MAX_TRADE_DOLLARS)
    w = (entry - stop) / entry
    risk_i = RISK_PER_TRADE * min(1.0, w / RISK_PROP_REF) if w > 0 else RISK_PER_TRADE
    sh_risk = int(risk_i / (entry - stop)) if entry > stop else 0
    sh_not = int(pos_size / entry)
    sh = max(1, min(sh_risk, sh_not))
    clamp = "risk" if sh_risk <= sh_not else "notional"
    k = (f["t"], f["sec"] // 60)
    if k not in _VC:
        _VC[k] = vol_cap_shares(f["t"], f["sec"])
    vc = _VC[k]
    if vc and sh > vc:
        sh, clamp = vc, "volume"
    return sh, clamp


def capital_book(fires, res, balance0=SIM_BAL, one_per_ticker=True):
    """Chronological capital ledger. Returns (keep[], stats)."""
    balance = balance0
    open_pos = []      # (exit_sec, reserved, pnl, ticker)
    keep, sizes, clamps = [], [], collections.Counter()
    peak_conc, peak_dep = 0, 0.0
    skipped_cap = 0
    for f, r in zip(fires, res):
        # release finished positions
        still = []
        for xs, rv, pl, tk in open_pos:
            if xs <= f["sec"]:
                balance += pl
            else:
                still.append((xs, rv, pl, tk))
        open_pos = still
        held = {tk for _, _, _, tk in open_pos}
        reserved_now = sum(rv for _, rv, _, _ in open_pos)
        if one_per_ticker and f["t"] in held:
            keep.append(False); sizes.append(0.0); continue
        entry = r["entry"]
        stop_used = r["stop_used"]
        sh, clamp = size_shares(f, entry, stop_used, balance)
        reserved = round(sh * entry, 2)
        free = balance - reserved_now
        if free < reserved:
            keep.append(False); sizes.append(0.0); skipped_cap += 1; continue
        pnl = r["ppd"] * reserved
        open_pos.append((r["exit_sec"], reserved, pnl, f["t"]))
        keep.append(True); sizes.append(reserved); clamps[clamp] += 1
        peak_conc = max(peak_conc, len(open_pos))
        peak_dep = max(peak_dep, reserved_now + reserved)
    for xs, rv, pl, tk in open_pos:
        balance += pl
    return keep, {"peak_concurrent": peak_conc, "peak_deployed": round(peak_dep, 2),
                  "no_capital_skip": skipped_cap, "clamps": dict(clamps),
                  "avg_size": round(sum(s for s in sizes if s) / max(1, sum(1 for s in sizes if s)), 2),
                  "end_balance": round(balance, 2), "sizes": sizes}


def slot_filter(fires, res, slots=2):
    busy = []   # list of free-at times
    keep = []
    for f, r in zip(fires, res):
        busy = [b for b in busy if b > f["sec"]]
        if len(busy) < slots:
            keep.append(True)
            busy.append(r["exit_sec"])
        else:
            keep.append(False)
    return keep


def maxdd(seq):
    """seq of (exit_sec, pnl) -> max drawdown of the realized equity curve"""
    peak = eq = 0.0
    dd = 0.0
    for _, p in sorted(seq):
        eq += p
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return dd


def cell(fires, **kw):
    res = [sim(f, **kw) for f in fires]
    n = len(res)
    st = sum(1 for r in res if r["reason"] == "stop")
    wins = sum(1 for r in res if r["pnl"] > 0)
    tot = sum(r["pnl"] for r in res)                     # (b) unconstrained, $500 clip
    # (a) CAPITAL-CONSTRAINED at $3,000 — the decision-relevant book
    ckeep, cstat = capital_book(fires, res)
    csizes = cstat.pop("sizes")
    cap_pnls = [r["ppd"] * sz for r, k, sz in zip(res, ckeep, csizes) if k]
    cap_seq = [(r["exit_sec"], r["ppd"] * sz) for r, k, sz in zip(res, ckeep, csizes) if k]
    cap_tot = sum(cap_pnls)
    # (c) 2-slot — the WRONG constraint, kept only for comparability
    skeep = slot_filter(fires, res)
    sc = [(r["exit_sec"], r["pnl"]) for r, k in zip(res, skeep) if k]
    recs = [r for r in res if r["reason"] == "stop" and r["recovered"]]
    tts = sorted(r["tts"] for r in res if r["reason"] == "stop")
    return {
        "n": n, "n_stopped": st, "win_pct": round(100.0 * wins / n, 1) if n else 0,
        # (a)
        "cap_n": sum(ckeep), "cap_total": round(cap_tot, 2),
        "cap_per_trade": round(cap_tot / max(sum(ckeep), 1), 2),
        "cap_worst": round(min(cap_pnls or [0]), 2),
        "cap_win_pct": round(100.0 * sum(1 for p in cap_pnls if p > 0) / max(len(cap_pnls), 1), 1),
        "cap_stopped": sum(1 for r, k in zip(res, ckeep) if k and r["reason"] == "stop"),
        "cap_maxdd": round(maxdd(cap_seq), 2), **cstat,
        # (b)
        "total": round(tot, 2), "per_trade": round(tot / n, 2) if n else 0,
        "worst": round(min((r["pnl"] for r in res), default=0), 2),
        # (c)
        "slot2_n": sum(skeep), "slot2_total_WRONG_CONSTRAINT": round(sum(p for _, p in sc), 2),
        "slot2_maxdd": round(maxdd(sc), 2),
        "recovered": len(recs), "recov_pct": round(100.0 * len(recs) / st, 1) if st else None,
        "median_tts_s": (tts[len(tts) // 2] if tts else None),
        "_res": res, "_keep": ckeep, "_sizes": csizes,
    }


def lane_table(fires, res, keep=None, sizes=None):
    by = collections.defaultdict(list)
    for i, (f, r) in enumerate(zip(fires, res)):
        if keep is not None and not keep[i]:
            continue
        pnl = (r["ppd"] * sizes[i]) if sizes is not None else r["pnl"]
        by[f["lane"]].append((f, r, pnl))
    out = {}
    for ln, v in sorted(by.items()):
        caps = [r["cap"] for _, r, _ in v if r["cap"] is not None]
        tot = sum(p for _, _, p in v)
        out[ln] = {"n": len(v), "total": round(tot, 2),
                   "per_trade": round(tot / len(v), 2),
                   "stopped": sum(1 for _, r, _ in v if r["reason"] == "stop"),
                   "trailed": sum(1 for _, r, _ in v if r["reason"] == "trail"),
                   "flatten": sum(1 for _, r, _ in v if r["reason"] == "flatten"),
                   "mfe_capture": round(sum(caps) / len(caps), 3) if caps else None}
    return out


def main():
    fires, excl = load_fires()
    print(f"FIRE SET: {len(fires)}")
    per_lane = collections.Counter(f["lane"] for f in fires)
    print(per_lane.most_common())
    print("EXCLUDED:", dict(excl))

    O = {"fire_set": dict(per_lane), "n_fires": len(fires), "excluded": dict(excl),
         "derivations": dict(collections.Counter((f["lane"], f["how"]) for f in fires).items()
                             ) and {f"{k[0]}|{k[1]}": v for k, v in
                                    collections.Counter((f["lane"], f["how"]) for f in fires).items()},
         "A_stop": {}, "B_trail": {}, "C_bank": {}, "D_corners": {}, "slip": {}}

    def line(tag, c):
        print(f"  {tag:10s} N={c['n']:>3} | CAP(N={c['cap_n']:>3})=${c['cap_total']:>9} "
              f"worst=${c['cap_worst']:>8} dd=${c['cap_maxdd']:>9} "
              f"peak={c['peak_concurrent']}/${c['peak_deployed']:.0f} capskip={c['no_capital_skip']} "
              f"| unc=${c['total']:>9} | 2slot(WRONG)=${c['slot2_total_WRONG_CONSTRAINT']:>9} "
              f"| stop={c['n_stopped']} recov={c['recovered']} medTTS={c['median_tts_s']}s")

    print("\n== A. STOP WIDTH (trail 10%, bank +10%) ==")
    for m in [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
        c = cell(fires, stop_mult=m)
        O["A_stop"][f"x{m}"] = {k: v for k, v in c.items() if not k.startswith("_")}
        line(f"x{m}", c)
    c = cell(fires, stop_mult=1.0, stop_floor10=True)
    O["A_stop"]["floor10"] = {k: v for k, v in c.items() if not k.startswith("_")}
    line("floor10", c)

    print("\n== B. TRAIL WIDTH (stop x1.0, bank +10%) ==")
    for tr in [0.10, 0.15, 0.20, 0.25, None]:
        c = cell(fires, trail=tr)
        O["B_trail"][str(tr)] = {k: v for k, v in c.items() if not k.startswith("_")}
        line(f"trail{tr}", c)

    print("\n== C. BANK POINT (stop x1.0, trail 10%) ==")
    for bk in [0.10, 0.20, 0.30, None]:
        c = cell(fires, bank=bk)
        O["C_bank"][str(bk)] = {k: v for k, v in c.items() if not k.startswith("_")}
        line(f"bank{bk}", c)

    # D corners: best individual settings vs today's — ranked on the CAPITAL book
    bestA = max(O["A_stop"].items(), key=lambda kv: kv[1]["cap_total"])
    bestB = max(O["B_trail"].items(), key=lambda kv: kv[1]["cap_total"])
    bestC = max(O["C_bank"].items(), key=lambda kv: kv[1]["cap_total"])
    print(f"\nbest A={bestA[0]} B={bestB[0]} C={bestC[0]}")
    sm = 1.0 if bestA[0] == "floor10" else float(bestA[0][1:])
    fl = bestA[0] == "floor10"
    tb = None if bestB[0] == "None" else float(bestB[0])
    cb = None if bestC[0] == "None" else float(bestC[0])
    print("\n== D. 2x2x2 CORNERS ==")
    for a, (m_, f_) in [("today", (1.0, False)), ("best", (sm, fl))]:
        for b, tv in [("today", 0.10), ("best", tb)]:
            for cc, bv in [("today", 0.10), ("best", cb)]:
                c = cell(fires, stop_mult=m_, stop_floor10=f_, trail=tv, bank=bv)
                k = f"stop:{a}/trail:{b}/bank:{cc}"
                O["D_corners"][k] = {kk: v for kk, v in c.items() if not kk.startswith("_")}
                print(f"  {k:38s} CAP(N={c['cap_n']:>3})=${c['cap_total']:>9} "
                      f"worst=${c['cap_worst']:>8} dd=${c['cap_maxdd']:>9} "
                      f"peak={c['peak_concurrent']}/${c['peak_deployed']:.0f} "
                      f"unc=${c['total']:>9} 2slot=${c['slot2_total_WRONG_CONSTRAINT']:>9}")

    best_key = max(O["D_corners"].items(), key=lambda kv: kv[1]["cap_total"])
    print(f"\nBEST CELL: {best_key[0]} CAP=${best_key[1]['cap_total']}")
    O["best_cell"] = {"key": best_key[0], **best_key[1]}

    # per-lane at today vs best
    ct = cell(fires)
    O["lane_today_unconstrained"] = lane_table(fires, ct["_res"])
    O["lane_today_capital"] = lane_table(fires, ct["_res"], ct["_keep"], ct["_sizes"])
    parts = best_key[0].split("/")
    m_ = 1.0 if parts[0] == "stop:today" else sm
    f_ = False if parts[0] == "stop:today" else fl
    tv = 0.10 if parts[1] == "trail:today" else tb
    bv = 0.10 if parts[2] == "bank:today" else cb
    cb_ = cell(fires, stop_mult=m_, stop_floor10=f_, trail=tv, bank=bv)
    O["lane_best_unconstrained"] = lane_table(fires, cb_["_res"])
    O["lane_best_capital"] = lane_table(fires, cb_["_res"], cb_["_keep"], cb_["_sizes"])
    print("\n== PER-LANE (today, unconstrained) ==")
    for ln, v in O["lane_today_unconstrained"].items():
        print(f"  {ln:14s} n={v['n']:>3} tot=${v['total']:>8} stop={v['stopped']:>3} "
              f"trail={v['trailed']:>3} flat={v['flatten']:>3} mfecap={v['mfe_capture']}")
    print("\n== PER-LANE (best cell, unconstrained) ==")
    for ln, v in O["lane_best_unconstrained"].items():
        print(f"  {ln:14s} n={v['n']:>3} tot=${v['total']:>8} stop={v['stopped']:>3} "
              f"trail={v['trailed']:>3} flat={v['flatten']:>3} mfecap={v['mfe_capture']}")

    print("\n== ENTRY-SLIP SENSITIVITY (best cell) ==")
    for sl in [0.01, 0.0]:
        c = cell(fires, stop_mult=m_, stop_floor10=f_, trail=tv, bank=bv, slip=sl)
        O["slip"][str(sl)] = {k: v for k, v in c.items() if not k.startswith("_")}
        print(f"  slip={sl}: CAP(N={c['cap_n']})=${c['cap_total']} unc=${c['total']} "
              f"worst=${c['cap_worst']}")
    ctoday_slip0 = cell(fires, slip=0.0)
    O["slip"]["today_0"] = {k: v for k, v in ctoday_slip0.items() if not k.startswith("_")}

    json.dump(O, open(OUT, "w"), indent=1, default=str)
    print("\nwrote " + OUT)


if __name__ == "__main__":
    main()
