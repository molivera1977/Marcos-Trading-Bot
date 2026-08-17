#!/usr/bin/env python3
"""8/17 RUNNER MODEL TEST — is the negativity the MODEL or the TAPE?

Marcos's challenge: "IPST went +228% today. If you can't make money on a stock that
goes up 228%, the model is wrong, not the market."

Analysis only. No bot edits, no deploy, no env change.

Tape: SIP 10s bars rebuilt from /v2/stocks/trades (feed=sip), 13:25-19:55Z.
E3 live-parity: $500 clip, +1% entry slip, -0.5% exit slip, intrabar stop FIRST,
bank 1/2 at +10%, 10% trail off run-high on CLOSES after scale, 15:45 flatten.
"""
import os, sys, json, subprocess, collections, datetime as dt
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B10 = os.path.join(HERE, "bars10s_0817")
os.makedirs(B10, exist_ok=True)
S = requests.Session()
_KEY = _SEC = None

DAY = "2026-08-17"
TICKERS = ["IPST", "WETO", "IVF", "TRUG", "WFF", "CDTG", "SLE", "XPON",
           "RETO", "NIVF", "DFSC"]

POS, SLIP, MKT = 500.0, 0.01, 0.005
MIN_STOP_PCT = 0.04
OPEN_S = 9 * 3600 + 30 * 60
FLAT = 15 * 3600 + 45 * 60


def keys():
    global _KEY, _SEC
    if _KEY:
        return _KEY, _SEC
    _KEY, _SEC = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
    if not _KEY:
        kv = subprocess.run(["railway", "variables", "--service", "Marcos-Trading-Bot", "--kv"],
                            capture_output=True, text=True, cwd=ROOT).stdout
        for ln in kv.splitlines():
            if ln.startswith("ALPACA_KEY="):
                _KEY = ln.split("=", 1)[1].strip()
            if ln.startswith("ALPACA_SECRET="):
                _SEC = ln.split("=", 1)[1].strip()
    return _KEY, _SEC


def H():
    k, s = keys()
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}


# ---------------- tape builder: /v2/stocks/trades -> 10s OHLCV ----------------
def build_10s(t):
    p = os.path.join(B10, t + ".json")
    if os.path.exists(p):
        return json.load(open(p))["bars"]
    url = "https://data.alpaca.markets/v2/stocks/trades"
    params = {"symbols": t, "start": f"{DAY}T13:25:00Z", "end": f"{DAY}T19:55:00Z",
              "limit": 10000, "feed": "sip"}
    buckets = collections.OrderedDict()
    tok, npages, ntr = None, 0, 0
    while True:
        q = dict(params)
        if tok:
            q["page_token"] = tok
        r = S.get(url, headers=H(), params=q, timeout=60)
        if r.status_code != 200:
            print(f"  !! {t} HTTP {r.status_code} {r.text[:200]}")
            return []
        j = r.json()
        for tr in (j.get("trades") or {}).get(t, []):
            ts = tr["t"]
            hh, mm, ss = int(ts[11:13]), int(ts[14:16]), int(float(ts[17:23]))
            sec = hh * 3600 + mm * 60 + ss
            k = sec // 10 * 10
            px, sz = float(tr["p"]), int(tr["s"])
            b = buckets.get(k)
            if b is None:
                buckets[k] = {"utc": k, "open": px, "high": px, "low": px,
                              "close": px, "volume": sz, "pv": px * sz}
            else:
                b["high"] = max(b["high"], px)
                b["low"] = min(b["low"], px)
                b["close"] = px
                b["volume"] += sz
                b["pv"] += px * sz
            ntr += 1
        tok = j.get("next_page_token")
        npages += 1
        if not tok:
            break
    bars = []
    for k in sorted(buckets):
        b = buckets[k]
        b["time"] = "%s%02d:%02d:%02dZ" % (DAY + "T", k // 3600, (k % 3600) // 60, k % 60)
        bars.append(b)
    json.dump({"bars": bars}, open(p, "w"))
    print(f"  {t}: {ntr} trades, {npages} pages, {len(bars)} 10s bars")
    return bars


_bars = {}


def bars(t):
    if t not in _bars:
        _bars[t] = build_10s(t)
    return _bars[t]


def bsec(b):  # UTC -> ET seconds (EDT = UTC-4)
    return b["utc"] - 4 * 3600


def idx_at(t, s):
    """first bar index at/after s"""
    B = bars(t)
    for i, b in enumerate(B):
        if bsec(b) >= s:
            return i
    return None


# ---------------- exit engines ----------------
def sim_e3(t, i0, entry_px, stop, use_stop=True, use_trail=True, use_scale=True,
           exit_slip=MKT, flat=FLAT):
    """E3 live-parity. Returns (pnl, reason, exit_sec, exit_px, mfe_px)."""
    B = bars(t)
    sh = POS / entry_px
    rem = sh
    pnl = 0.0
    scaled = False
    bank = sh * 0.5
    target = entry_px * 1.10
    run_hi = entry_px
    mfe = entry_px
    for i in range(i0 + 1, len(B)):
        b = B[i]
        if bsec(b) >= flat:
            break
        mfe = max(mfe, b["high"])
        if use_stop and b["low"] <= stop:
            px = stop * (1 - exit_slip)
            pnl += rem * (px - entry_px)
            return pnl, "stop", bsec(b), px, mfe
        if use_scale and not scaled and b["high"] >= target:
            pnl += bank * (target - entry_px)
            rem -= bank
            scaled = True
            continue
        run_hi = max(run_hi, b["high"])
        if use_trail and scaled and b["close"] < run_hi * 0.90:
            px = b["close"] * (1 - exit_slip)
            pnl += rem * (px - entry_px)
            return pnl, "trail", bsec(b), px, mfe
    last = None
    for b in B:
        if bsec(b) < flat:
            last = b
    if last is None:
        return 0.0, "no_tape", flat, entry_px, mfe
    px = last["close"] * (1 - exit_slip)
    pnl += rem * (px - entry_px)
    return pnl, "flatten", flat, px, mfe


def stop_from_tape(t, s, entry):
    B = [b for b in bars(t) if s - 60 <= bsec(b) <= s]
    if B:
        lo = min(b["low"] for b in B)
        if 0 < lo < entry:
            return lo
    return entry * 0.94


def hhmm(s):
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def session_vwap_touch(t):
    """first bar at/after 09:45 whose low<=running RTH vwap<=high"""
    B = bars(t)
    pv = vol = 0.0
    for i, b in enumerate(B):
        s = bsec(b)
        if s < OPEN_S:
            continue
        pv += b["pv"]
        vol += b["volume"]
        if vol <= 0:
            continue
        v = pv / vol
        if s >= 9 * 3600 + 45 * 60 and b["low"] <= v <= b["high"]:
            return i, v
    return None, None


# ---------------- run ----------------
def entry_at(t, s):
    i = idx_at(t, s)
    if i is None:
        return None, None
    return i, bars(t)[i]["open"]


def main():
    print("=== building SIP 10s tape ===")
    for t in TICKERS:
        bars(t)

    rows = []
    for t in TICKERS:
        B = bars(t)
        if not B:
            print(f"SKIP {t}: no tape")
            continue
        rth = [b for b in B if OPEN_S <= bsec(b) < FLAT]
        if not rth:
            print(f"SKIP {t}: no RTH tape")
            continue
        dayhi = max(b["high"] for b in rth)
        r = {"ticker": t, "open_px": rth[0]["open"], "day_hi": dayhi,
             "flat_px": rth[-1]["close"], "arms": {}}

        # (a) 09:30 open, E3
        i0, px = entry_at(t, OPEN_S)
        e = px * (1 + SLIP)
        st = max(stop_from_tape(t, OPEN_S, e), e * (1 - MIN_STOP_PCT)) if (e - stop_from_tape(t, OPEN_S, e)) / e > MIN_STOP_PCT else e * (1 - MIN_STOP_PCT)
        st = stop_from_tape(t, OPEN_S, e)
        if (e - st) / e < MIN_STOP_PCT:
            st = e * (1 - MIN_STOP_PCT)
        r["arms"]["a"] = dict(zip(("pnl", "why", "xs", "xpx", "mfe"), sim_e3(t, i0, e, st)),
                              entry=e, stop=st, i0=i0, sec=OPEN_S)

        # (b) 10:00, E3
        i1, px1 = entry_at(t, 10 * 3600)
        if i1 is not None:
            e1 = px1 * (1 + SLIP)
            s1 = stop_from_tape(t, 10 * 3600, e1)
            if (e1 - s1) / e1 < MIN_STOP_PCT:
                s1 = e1 * (1 - MIN_STOP_PCT)
            r["arms"]["b"] = dict(zip(("pnl", "why", "xs", "xpx", "mfe"), sim_e3(t, i1, e1, s1)),
                                  entry=e1, stop=s1, i0=i1, sec=10 * 3600)

        # (c) VWAP first touch after 09:45, E3
        iv, v = session_vwap_touch(t)
        if iv is not None:
            ev = v * (1 + SLIP)
            sv = stop_from_tape(t, bsec(B[iv]), ev)
            if (ev - sv) / ev < MIN_STOP_PCT:
                sv = ev * (1 - MIN_STOP_PCT)
            r["arms"]["c"] = dict(zip(("pnl", "why", "xs", "xpx", "mfe"), sim_e3(t, iv, ev, sv)),
                                  entry=ev, stop=sv, i0=iv, sec=bsec(B[iv]))

        # (d) 09:30 buy & hold to flatten, no stop no trail no scale
        r["arms"]["d"] = dict(zip(("pnl", "why", "xs", "xpx", "mfe"),
                                  sim_e3(t, i0, e, 0.0, use_stop=False, use_trail=False,
                                         use_scale=False)), entry=e, stop=None, sec=OPEN_S)

        # (e) 09:30 with hard 10% stop only, no trail, no scale
        r["arms"]["e"] = dict(zip(("pnl", "why", "xs", "xpx", "mfe"),
                                  sim_e3(t, i0, e, e * 0.90, use_stop=True, use_trail=False,
                                         use_scale=False)), entry=e, stop=e * 0.90, sec=OPEN_S)

        # --- TRUE MFE: full window entry -> 15:45, independent of when the arm exited ---
        fwd = [b for b in B if i0 is not None and bsec(b) > bsec(B[i0]) and bsec(b) < FLAT]
        r["true_mfe"] = max((b["high"] for b in fwd), default=r["arms"]["a"]["entry"])
        r["true_mae"] = min((b["low"] for b in fwd), default=r["arms"]["a"]["entry"])
        # premarket context: 07:00-09:30 range on the fetched tape
        pre = [b for b in B if bsec(b) < OPEN_S]
        r["pre_lo"] = min((b["low"] for b in pre), default=None)
        r["pre_hi"] = max((b["high"] for b in pre), default=None)

        # --- slippage decomposition on arm (a) ---
        raw = px
        dec = {}
        dec["i_current"] = r["arms"]["a"]["pnl"]
        st2 = stop_from_tape(t, OPEN_S, raw)
        if (raw - st2) / raw < MIN_STOP_PCT:
            st2 = raw * (1 - MIN_STOP_PCT)
        dec["ii_no_entry_slip"] = sim_e3(t, i0, raw, st2)[0]
        dec["iii_no_slip_either"] = sim_e3(t, i0, raw, st2, exit_slip=0.0)[0]
        # (iv) mid-price fills: approximate mid as bar midpoint (h+l)/2 at entry, exits at bar mid
        mid = (bars(t)[i0]["high"] + bars(t)[i0]["low"]) / 2.0
        st3 = stop_from_tape(t, OPEN_S, mid)
        if (mid - st3) / mid < MIN_STOP_PCT:
            st3 = mid * (1 - MIN_STOP_PCT)
        dec["iv_mid_fills"] = sim_e3(t, i0, mid, st3, exit_slip=0.0)[0]
        r["slip"] = dec

        # --- stopped-then-recovered on arm (a) ---
        a = r["arms"]["a"]
        if a["why"] == "stop":
            after = [b for b in B if a["xs"] < bsec(b) < FLAT]
            hi_after = max((b["high"] for b in after), default=0.0)
            r["recover"] = {"stopped_at": a["xs"], "hi_after": hi_after,
                            "recovered": hi_after > a["entry"]}
            # 2x wider stop
            wide = a["entry"] - 2 * (a["entry"] - a["stop"])
            if wide > 0:
                p2, w2, x2, xp2, m2 = sim_e3(t, i0, a["entry"], wide)
                r["wide"] = dict(pnl=p2, why=w2, xs=x2, xpx=xp2, stop=wide)
        rows.append(r)

    json.dump(rows, open(os.path.join(HERE, "runner_model_test_20260817_out.json"), "w"),
              indent=1, default=str)

    # ---------------- report ----------------
    print("\n=== ARMS (a)-(e), $500 clip, E3 live-parity, 15:45 flatten ===")
    hdr = f"{'TKR':6s} {'ARM':3s} {'ENTRY':>9s} {'EXIT':>9s} {'REASON':9s} {'TIME':>9s} {'$':>9s}"
    print(hdr)
    tot = collections.defaultdict(float)
    n = collections.Counter()
    for r in rows:
        for k in "abcde":
            a = r["arms"].get(k)
            if not a:
                continue
            print(f"{r['ticker']:6s} {k:3s} {a['entry']:9.4f} {a['xpx']:9.4f} "
                  f"{a['why']:9s} {hhmm(a['xs']):>9s} {a['pnl']:9.2f}")
            tot[k] += a["pnl"]
            n[k] += 1
        print()
    print("--- ARM TOTALS ---")
    for k in "abcde":
        print(f"  ({k}) n={n[k]:2d}  total ${tot[k]:9.2f}   avg ${tot[k]/max(n[k],1):8.2f}")

    print("\n=== MFE CAPTURE (arm a vs buy&hold vs perfect) ===")
    print(f"{'TKR':6s} {'ENTRY':>9s} {'MFE':>9s} {'MFE%':>8s} {'MFE$':>9s} "
          f"{'a$':>9s} {'cap%':>7s} {'d$':>9s} {'dcap%':>7s}")
    caps = []
    for r in rows:
        a, d = r["arms"]["a"], r["arms"]["d"]
        MFE = r["true_mfe"]
        mfe_pct = (MFE - a["entry"]) / a["entry"] * 100
        mfe_d = POS * (MFE - a["entry"]) / a["entry"]
        cap = (a["pnl"] / mfe_d * 100) if mfe_d > 0 else float("nan")
        dcap = (d["pnl"] / mfe_d * 100) if mfe_d > 0 else float("nan")
        caps.append((r["ticker"], cap, dcap, mfe_d, a["pnl"], d["pnl"]))
        print(f"{r['ticker']:6s} {a['entry']:9.4f} {MFE:9.4f} {mfe_pct:8.1f} {mfe_d:9.2f} "
              f"{a['pnl']:9.2f} {cap:7.1f} {d['pnl']:9.2f} {dcap:7.1f}")
    good = [c for c in caps if c[3] > 0]
    if good:
        print(f"  mean MFE capture: E3(a) {sum(c[1] for c in good)/len(good):.1f}%   "
              f"hold(d) {sum(c[2] for c in good)/len(good):.1f}%")

    print("\n=== WHERE THE MOVE HAPPENED: premarket vs RTH ===")
    print(f"{'TKR':6s} {'preLO':>9s} {'preHI':>9s} {'0930op':>9s} {'rthHI':>9s} {'1545':>9s} "
          f"{'RTHop->hi%':>11s} {'RTHop->cl%':>11s}")
    for r in rows:
        o, h, c = r["open_px"], r["day_hi"], r["flat_px"]
        pl = r.get("pre_lo") or 0.0
        ph = r.get("pre_hi") or 0.0
        print(f"{r['ticker']:6s} {pl:9.4f} {ph:9.4f} {o:9.4f} {h:9.4f} {c:9.4f} "
              f"{(h-o)/o*100:11.1f} {(c-o)/o*100:11.1f}")

    print("\n=== SLIPPAGE DECOMPOSITION (arm a) ===")
    print(f"{'TKR':6s} {'i_cur':>9s} {'ii_noEnt':>9s} {'iii_noBoth':>11s} {'iv_mid':>9s}")
    ss = collections.defaultdict(float)
    for r in rows:
        d = r["slip"]
        print(f"{r['ticker']:6s} {d['i_current']:9.2f} {d['ii_no_entry_slip']:9.2f} "
              f"{d['iii_no_slip_either']:11.2f} {d['iv_mid_fills']:9.2f}")
        for k, v in d.items():
            ss[k] += v
    print(f"{'TOTAL':6s} {ss['i_current']:9.2f} {ss['ii_no_entry_slip']:9.2f} "
          f"{ss['iii_no_slip_either']:11.2f} {ss['iv_mid_fills']:9.2f}")
    print(f"  delta i->ii  (entry slip): ${ss['ii_no_entry_slip']-ss['i_current']:+.2f}")
    print(f"  delta ii->iii (exit slip): ${ss['iii_no_slip_either']-ss['ii_no_entry_slip']:+.2f}")
    print(f"  delta iii->iv (mid fills): ${ss['iv_mid_fills']-ss['iii_no_slip_either']:+.2f}")

    print("\n=== STOPPED-THEN-RECOVERED (arm a) ===")
    nrec = 0
    wtot = 0.0
    atot = 0.0
    for r in rows:
        rc = r.get("recover")
        if not rc:
            continue
        a = r["arms"]["a"]
        w = r.get("wide")
        print(f"{r['ticker']:6s} stopped {hhmm(rc['stopped_at'])} @{a['stop']:.4f} "
              f"(entry {a['entry']:.4f}, ${a['pnl']:.2f})  hi_after {rc['hi_after']:.4f}  "
              f"recovered={rc['recovered']}"
              + (f"   2x-stop {w['stop']:.4f} -> {w['why']:8s} ${w['pnl']:.2f}" if w else ""))
        nrec += 1 if rc["recovered"] else 0
        if w:
            wtot += w["pnl"]
            atot += a["pnl"]
    print(f"  stopped-and-recovered: {nrec} of {sum(1 for r in rows if r.get('recover'))} stops")
    print(f"  same set: current-stop ${atot:.2f} -> 2x-wider-stop ${wtot:.2f} "
          f"(delta ${wtot-atot:+.2f})")


if __name__ == "__main__":
    main()
