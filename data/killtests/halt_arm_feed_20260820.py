#!/usr/bin/env python3
"""
HALT LANE — THE SEAT QUESTION AND THE FEED QUESTION, ANSWERED BY ONE RUN (8/20 night)

Marcos: "let's jump into halt lanes topic" -> "build it".

TWO FACTS THAT FORCED THIS FILE (both verified 8/20 night, live rows):
  (A) THE SEAT. halt_ladder is RESTRICTED since 8/19 (marcos_trading_bot.py:16683, RTH_LANES) —
      it detects and logs, cannot take capital. Live record before the restriction: 16 arms,
      all stamped convert=True, 2 fills EVER (BOXL +$34.34, GIPR -$37.89, net -$3.55) against
      a settled 8/8 era-replay seat of +$840.93. That contradiction has never been reconciled.
  (B) THE FEED. Railway runs HALT_ARM_5S=0 — the KILL VALUE of Marcos's own 8/8 ruling
      ("go with 1"), which was made on a reconciled full-day head-to-head reading 10s arm
      -$13.91 vs 5s arm +$216.35 on identical exits. Every arm since 8/18 stamps feed_src
      alp-hot (10s). The lane has been arming on the refuted feed.

WHY BOTH IN ONE RUN: the seat is worthless to price under a feed the ruling already refuted,
and the feed is worthless to price without dollars for the seat. Same cohort, same exits, same
costs — the only difference between the two arms is the bar cadence the detector sees.

METHOD
  Universe    every (day, ticker) with >=2 halt_suspect rows in the live archive, 8/10-8/20 —
              the detector's OWN candidates, not a hand-picked list. Window = first suspect
              -20 min to +120 min.
  Bars        BUILT FROM TRADES (Alpaca /v2/stocks/{sym}/trades, SIP). The historical bars
              endpoint has NO sub-minute timeframe (probed 8/20: 5Sec/10Sec -> HTTP 400), and
              the 10s cache cannot answer a 5s question at all. Trades are the same source the
              live feeds aggregate, so both arms are built from one tape, one way.
  Detector    the live arm math, transcribed from marcos_trading_bot.py:11010-11045 —
              5-min mean reference, LULD band by price (0.10 / 0.20 / 0.75), prox >= 0.7,
              vel1m >= 5.0%, 60s per-name throttle, stop = min low of the prior 120s.
  Exits       E3 (the house exit): +10% tier trims half and moves the stop to entry, 10%
              give-back off the running high, 15:45 flat.
  Costs       REAL sampled NBBO spread of the fire minute, charged on entry and on stop/market
              exits (limit tiers free) — same walker as spread_floor_20260820.py. The k=1
              spread-relative stop guard SHIPPED tonight, so it is applied here: this prices
              the lane as it would actually trade now, not as it traded in August.
  Sizing      $30 risk, 70%/$1000 share clamp, capital-aware; reported at BOTH books —
              $3,000 (sim today) and $5,000 (Marcos's stated go-live account).
  Verdict     TOTAL DOLLARS (the 8/20 law). $/trade is printed as a diagnostic only.

DISCLOSED LIMITS — read before quoting any number
  * NO CROWN GATE. Live arms require _is_leader(t); crown state is not reconstructible from the
    archive. Every count here is therefore a SUPERSET of what the live lane would have armed.
    The 16 actually-logged arms are reported as their own line — that subset IS crown-true.
  * Median-of-minute spread, no sub-minute quote dynamics, no queue position.
  * Trades tape includes odd lots and corrections as delivered; no condition filtering beyond
    dropping zero/negative prices.
  * mins_since_halt is recomputed from the reconstructed tape, not from the live stamp (which
    is blank on 6 of 16 arms — "no gap in window" and "no halt" are recorded identically).
  * n is SMALL by nature (halts are rare). A dollar difference that rests on one trade is
    reported as such — the per-arm dump exists so the tail is visible, not hidden in a mean.

PRE-REGISTERED, WRITTEN BEFORE THE RUN
  1. FEED: 5s beats 10s iff it wins TOTAL DOLLARS on the full cohort AND does not owe that win
     to a single arm (drop-the-best-arm check reported for both).
  2. SEAT: the lane earns a re-seat argument iff its total dollars are positive at BOTH books
     under the WINNING feed, with the k=1 guard applied. Otherwise the restriction stands and
     the 8/8 +$840.93 claim is formally retired as unreproducible under live conditions.
  3. Neither result ships anything. This file writes JSON and prints; it changes no live code.
"""
import collections
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = "https://zestful-intuition-production-b16a.up.railway.app"
RISK = 30.0
BOOKS = (3000.0, 5000.0)
ARM_PROX = 0.7
ARM_VEL = 5.0
THROTTLE = 60
SPREAD_K = 1.0          # shipped tonight (Addendum 18)
MIN_STOP_PCT = 1.0      # shipped today (Addendum 14)

AK = os.environ.get("AK", "")
AS = os.environ.get("AS", "")
if not AK:
    kv = subprocess.run(["railway", "variables", "--service", "Marcos-Trading-Bot", "--kv"],
                        capture_output=True, text=True).stdout
    for ln in kv.splitlines():
        if ln.startswith("ALPACA_KEY="):
            AK = ln.split("=", 1)[1].strip()
        if ln.startswith("ALPACA_SECRET="):
            AS = ln.split("=", 1)[1].strip()
HDR = {"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=45))


def et(ts):
    return dt.datetime.fromisoformat(str(ts)[:19]) - dt.timedelta(hours=4)


def hm(ts):
    return et(ts).strftime("%H:%M")


def hm_k(k):
    """ET HH:MM from a true UTC epoch — the ONE clock conversion (positive control 8/20)."""
    return (dt.datetime.utcfromtimestamp(k) - dt.timedelta(hours=4)).strftime("%H:%M")


# ── universe: the detector's own candidates ──────────────────────────────────
def universe():
    days = [(dt.date(2026, 8, 20) - dt.timedelta(days=i)).isoformat() for i in range(0, 11)]
    out, armset = [], []
    for d in days:
        try:
            rows = json.load(urllib.request.urlopen(
                f"{BOARD}/api/decisions_archive?date={d}&limit=50000&key=marcos2026",
                timeout=45)).get("rows") or []
        except Exception:
            continue
        sus = collections.defaultdict(list)
        for r in rows:
            if r.get("status") == "halt_suspect":
                sus[r.get("ticker")].append(r)
            if r.get("status") == "halt_arm":
                armset.append((d, r.get("ticker"), r.get("time")))
        for tk, rs in sus.items():
            if not tk or len(rs) < 2:
                continue
            t0 = min(str(x.get("recorded_at") or "")[11:19] for x in rs if x.get("recorded_at"))
            if not t0:
                continue
            out.append((d, tk, t0))
    return out, armset


# ── bars built from the trades tape, at any cadence ──────────────────────────
def trades(sym, day, t_from, t_to):
    """Raw trades in [t_from, t_to] ET on `day`. Paginates. Returns [(epoch, px, sz)]."""
    s = (dt.datetime.fromisoformat(f"{day}T{t_from}") + dt.timedelta(hours=4)).isoformat() + "Z"
    e = (dt.datetime.fromisoformat(f"{day}T{t_to}") + dt.timedelta(hours=4)).isoformat() + "Z"
    out, page = [], None
    for _ in range(40):
        q = {"start": s, "end": e, "limit": 10000, "feed": "sip"}
        if page:
            q["page_token"] = page
        try:
            r = get(f"https://data.alpaca.markets/v2/stocks/{sym}/trades?"
                    + urllib.parse.urlencode(q))
        except Exception:
            break
        for x in r.get("trades") or []:
            p = float(x.get("p") or 0)
            if p > 0:
                out.append((dt.datetime.fromisoformat(str(x["t"])[:19] + "+00:00").timestamp(),
                            p, float(x.get("s") or 0)))
        page = r.get("next_page_token")
        if not page:
            break
    out.sort()
    return out


def bars(tr, cad):
    """Aggregate a trades tape into OHLCV buckets of `cad` seconds. Keyed by bucket epoch."""
    b = {}
    for ts, p, sz in tr:
        k = int(ts // cad) * cad
        d = b.get(k)
        if d is None:
            b[k] = {"o": p, "h": p, "l": p, "c": p, "v": sz}
        else:
            d["h"] = max(d["h"], p)
            d["l"] = min(d["l"], p)
            d["c"] = p
            d["v"] += sz
    return b


# ── the live arm math, transcribed (bot :11010-11045) ────────────────────────
def arms(bk, cad):
    ks = sorted(bk)
    need = 24 if cad == 5 else 12
    fired, last = [], -1e9
    for n in range(need, len(ks)):
        k = ks[n]
        px = bk[k]["c"]
        if px <= 0:
            continue
        w5 = [bk[x] for x in ks[:n + 1] if x >= k - 300]
        ref = sum(x["c"] for x in w5) / max(len(w5), 1)
        band = 0.10 if px >= 3 else (0.20 if px >= 0.75 else 0.75)
        prox = (px / ref - 1) / band if ref else 0
        w1 = [bk[x] for x in ks[:n + 1] if x >= k - 60]
        v0 = w1[0]["c"] if w1 else 0
        vel = (px / v0 - 1) * 100 if v0 else 0
        if prox >= ARM_PROX and vel >= ARM_VEL and k - last >= THROTTLE:
            last = k
            stop = min((bk[x]["l"] for x in ks[:n + 1]
                        if x >= k - 120 and bk[x]["l"] > 0), default=0)
            if stop and stop < px:
                fired.append({"k": k, "px": px, "stop": stop,
                              "prox": round(prox, 2), "vel": round(vel, 1)})
    return fired


# ── costs: the real NBBO spread of the fire minute ───────────────────────────
_qc = {}
_qgap = [0, 0]


def spread_at(sym, day, hhmm):
    key = (sym, day, hhmm)
    if key in _qc:
        return _qc[key]
    _qgap[1] += 1
    h, m = int(hhmm[:2]) + 4, hhmm[3:5]
    v = None
    try:
        qs = get(f"https://data.alpaca.markets/v2/stocks/{sym}/quotes"
                 f"?start={day}T{h:02d}:{m}:00Z&limit=60&feed=sip").get("quotes") or []
        sp = sorted(x["ap"] - x["bp"] for x in qs
                    if x.get("ap", 0) > 0 and x.get("bp", 0) > 0 and x["ap"] > x["bp"])
        v = sp[len(sp) // 2] if sp else None
    except Exception:
        v = None
    if v is None:
        _qgap[0] += 1
    _qc[key] = v
    return v


# ── E3 walk on the 10s tape (one exit engine for both arms) ──────────────────
def walk(bk10, k0, entry, stop, spr, bal):
    ks = [x for x in sorted(bk10) if x >= k0]
    if len(ks) < 2:
        return None
    half = (spr / 2) if spr else entry * 0.0025
    px = entry + half
    rps = px - stop
    if rps <= 0:
        return None
    sh = max(1, min(int(RISK / rps), int(bal * 0.70 / px), int(1000 / px)))
    rem, banked, tiered, runhi = sh, 0.0, False, px
    for k in ks[1:]:
        x = bk10[k]
        if hm_k(k) >= "15:45":
            return banked + rem * ((x["c"] - half) - px), sh * px, k
        if x["l"] <= stop:
            return banked + rem * ((stop - half) - px), sh * px, k
        runhi = max(runhi, x["h"])
        if not tiered and x["h"] >= px * 1.10:
            n = rem // 2 or rem
            banked += n * (px * 1.10 - px)
            rem -= n
            tiered, stop = True, px
            if rem == 0:
                return banked, sh * px, k
        if tiered and x["c"] <= runhi * 0.90:
            return banked + rem * ((x["c"] - half) - px), sh * px, k
    lastk = ks[-1]
    return banked + rem * ((bk10[lastk]["c"] - half) - px), sh * px, lastk


def main():
    uni, logged = universe()
    print(f"universe: {len(uni)} (day,ticker) with >=2 halt_suspect rows 8/10-8/20 "
          f"| live-logged arms in that window: {len(logged)}")
    armnames = {(d, t) for d, t, _ in logged}
    fills = {5: [], 10: []}
    for i, (d, tk, t0) in enumerate(uni, 1):
        base = dt.datetime.fromisoformat(f"{d}T{t0}")
        lo = max(base - dt.timedelta(minutes=20),
                 dt.datetime.fromisoformat(f"{d}T09:30:00"))
        hi = min(base + dt.timedelta(minutes=120),
                 dt.datetime.fromisoformat(f"{d}T15:50:00"))
        if hi <= lo:
            continue
        tr = trades(tk, d, lo.strftime("%H:%M:%S"), hi.strftime("%H:%M:%S"))
        print(f"  [{i}/{len(uni)}] {d} {tk} trades={len(tr)}", flush=True)
        if len(tr) < 200:
            continue
        b10 = bars(tr, 10)
        for cad in (5, 10):
            for a in arms(bars(tr, cad) if cad != 10 else b10, cad):
                t = hm_k(a["k"])
                if not ("09:30" <= t < "15:30"):
                    continue
                w = (a["px"] - a["stop"]) / a["px"] * 100
                if w < MIN_STOP_PCT:                       # shipped floor
                    continue
                spr = spread_at(tk, d, t)
                if SPREAD_K > 0 and spr and (a["px"] - a["stop"]) < SPREAD_K * spr:
                    continue                               # shipped k=1 guard
                k0 = min((x for x in sorted(b10) if x >= a["k"]), default=None)
                if k0 is None:
                    continue
                r = walk(b10, k0, a["px"], a["stop"], spr, max(BOOKS))
                if r is None:
                    continue
                pnl, notional, kx = r
                fills[cad].append({"d": d, "tk": tk, "t": t, "pnl": pnl, "n": notional,
                                   "ti": a["k"], "tx": kx, "prox": a["prox"], "vel": a["vel"],
                                   "spr": spr, "logged": (d, tk) in armnames})
    print(f"\nquote queries {_qgap[1]} | gaps {_qgap[0]}")

    def book(fl, bal):
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
                tot += f["pnl"]
                n += 1
        return tot, n

    print(f"\n{'feed':>5s} {'arms':>5s} {'$3,000 total':>13s} {'n':>4s} "
          f"{'$5,000 total':>13s} {'n':>4s} {'$/trade@5k':>11s} {'drop-best@5k':>13s}")
    out = {}
    for cad in (5, 10):
        fl = fills[cad]
        t3, n3 = book(fl, 3000.0)
        t5, n5 = book(fl, 5000.0)
        best = max((f["pnl"] for f in fl), default=0.0)
        db = t5 - best
        out[cad] = {"arms": len(fl), "t3": t3, "n3": n3, "t5": t5, "n5": n5, "drop_best": db}
        print(f"{cad:4d}s {len(fl):5d} {t3:+13.2f} {n3:4d} {t5:+13.2f} {n5:4d} "
              f"{(t5/n5 if n5 else 0):+11.2f} {db:+13.2f}")

    sub = [f for f in fills[10] if f["logged"]]
    ts, ns = book(sub, 5000.0)
    print(f"\nCROWN-TRUE SUBSET (names that actually armed live, 10s): "
          f"{len(sub)} arms, {ns} taken, {ts:+.2f} @ $5,000")

    print(f"\n{'feed':>4s} {'date':>10s} {'tkr':>6s} {'time':>6s} {'prox':>5s} {'vel':>5s} "
          f"{'spread':>7s} {'P&L':>9s} {'live?':>6s}")
    for cad in (5, 10):
        for f in sorted(fills[cad], key=lambda x: -abs(x["pnl"]))[:12]:
            print(f"{cad:3d}s {f['d']:>10s} {f['tk']:>6s} {f['t']:>6s} {f['prox']:5.2f} "
                  f"{f['vel']:5.1f} {(f['spr'] or 0):7.4f} {f['pnl']:+9.2f} "
                  f"{'LIVE' if f['logged'] else '-':>6s}")

    json.dump({"summary": out, "fills": fills},
              open(os.path.join(HERE, "halt_arm_feed_20260820_out.json"), "w"), default=str)
    print("\nPRE-REGISTERED: (1) 5s wins only if it takes TOTAL DOLLARS and survives drop-best.")
    print("(2) the seat needs positive totals at BOTH books under the winning feed, else the")
    print("restriction stands and +$840.93 is retired as unreproducible. Nothing ships here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
