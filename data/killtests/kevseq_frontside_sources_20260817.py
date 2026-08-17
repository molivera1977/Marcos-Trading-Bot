#!/usr/bin/env python3
"""8/17 — WHY THE TWO 1-MINUTE FRONT-SIDE SOURCES DISAGREE (31 canary rows).

Analysis only. No bot edits, no deploy, no env change.

The live lane computes front_side = EMA9 > EMA20 on 1-min closes from TWO sources:
  (a) caller  — cache[t]["bars"]: the M1 broker/Alpaca fetch, count=50, RTH-session
                filtered, then [:-1] (drop the in-progress minute) -> ~49 closes.
  (b) self    — kevseq_feed_1m(): OUR aggregate of the fed 10s bars. Day-wide (whatever
                the stream fed us, PRE included), uncapped up to 240, completed buckets only.
Both are "1-minute". They disagreed 31 times on 8/17. This script reconstructs BOTH from the
SIP tape for the exact clock minute of each canary row and prints the EMAs side by side, so
the cause is read off data instead of asserted.

Usage: python3 data/killtests/kevseq_frontside_sources_20260817.py
"""
import os, sys, json, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
import requests
S = requests.Session()
_KEY = _SEC = None


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


DAY = "2026-08-17"


def bars_1m(sym):
    """Every 1-min SIP bar of DAY, 04:00-20:00 ET, oldest first: [(et_hhmm, close)]."""
    out, tok = [], None
    while True:
        p = {"timeframe": "1Min", "start": DAY + "T08:00:00Z", "end": DAY + "T23:59:00Z",
             "feed": "sip", "limit": 10000, "adjustment": "raw"}
        if tok:
            p["page_token"] = tok
        r = S.get("https://data.alpaca.markets/v2/stocks/%s/bars" % sym, headers=H(), params=p, timeout=60)
        r.raise_for_status()
        j = r.json()
        for b in (j.get("bars") or []):
            t = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")) - dt.timedelta(hours=4)  # EDT
            out.append((t.strftime("%H:%M"), float(b["c"])))
        tok = j.get("next_page_token")
        if not tok:
            break
    return out


def ema(closes, p):
    if len(closes) < p:
        return 0.0
    k = 2 / (p + 1)
    e = sum(closes[:p]) / p
    for c in closes[p:]:
        e = c * k + e * (1 - k)
    return e


def side(closes):
    e9, e20 = ema(closes, 9), ema(closes, 20)
    return (bool(e9 > e20 > 0) if (e9 and e20) else None), e9, e20


def main():
    rows = json.load(open(os.path.join(HERE, "kevseq_frontside_disagree_20260817.json")))
    OUT = []

    def say(s=""):
        print(s)
        OUT.append(s)

    say("SOURCE-DISAGREEMENT RECONSTRUCTION — %s" % DAY)
    say("caller = RTH-only, last 50 M1 bars, drop in-progress  |  self = last N day-wide 1-min buckets")
    say("")
    cache = {}
    agree_c = agree_s = 0
    for r in rows:
        sym, hm = r["ticker"], r["hm"]
        if sym not in cache:
            try:
                cache[sym] = bars_1m(sym)
            except Exception as e:
                say("  %s FETCH FAIL %s" % (sym, e))
                cache[sym] = []
        allb = [b for b in cache[sym] if b[0] < hm]            # completed minutes only
        rth = [b for b in allb if b[0] >= "09:30"]
        cal = rth[-50:][:-1] if len(rth) >= 2 else []          # the caller's exact shape
        slf = allb[-int(r["self_n"]):] if r["self_n"] else []  # the self aggregate's window
        cv, ce9, ce20 = side([c for _, c in cal])
        sv, se9, se20 = side([c for _, c in slf])
        agree_c += int(cv == r["caller"])
        agree_s += int(sv == r["self_agg"])
        say("%s %s  LOGGED caller=%s(n=%s) self=%s(n=%s)"
            % (hm, sym.ljust(5), r["caller"], r["caller_n"], r["self_agg"], r["self_n"]))
        say("      caller rebuild: n=%-3d %s..%s  e9=%.4f e20=%.4f -> %s %s"
            % (len(cal), cal[0][0] if cal else "-", cal[-1][0] if cal else "-", ce9, ce20, cv,
               "MATCH" if cv == r["caller"] else "differs"))
        say("      self   rebuild: n=%-3d %s..%s  e9=%.4f e20=%.4f -> %s %s"
            % (len(slf), slf[0][0] if slf else "-", slf[-1][0] if slf else "-", se9, se20, sv,
               "MATCH" if sv == r["self_agg"] else "differs"))
        say("      spread e9-e20: caller %+.4f (%.2f%%)  self %+.4f (%.2f%%)   window Δ = %d min, "
            "self starts %s the caller's first bar"
            % (ce9 - ce20, (ce9 - ce20) / ce20 * 100 if ce20 else 0,
               se9 - se20, (se9 - se20) / se20 * 100 if se20 else 0,
               len(slf) - len(cal),
               "BEFORE" if (slf and cal and slf[0][0] < cal[0][0]) else "at/after"))
        say("      self window includes premarket (<09:30): %s"
            % bool([b for b in slf if b[0] < "09:30"]))
        say("")
    say("reconstruction fidelity: caller sign reproduced %d/%d, self sign reproduced %d/%d"
        % (agree_c, len(rows), agree_s, len(rows)))
    say("")
    say("=== THE MECHANISM: TRADED-MINUTE GRID (caller) vs CONTIGUOUS-MINUTE GRID (self) ===")
    say("sym   SIP 1-min bars ALL DAY   max self_n logged   caller 49-bar window spans (min)")
    for sym in sorted({r["ticker"] for r in rows}):
        allb = cache.get(sym) or []
        srows = [r for r in rows if r["ticker"] == sym]
        spans = []
        for r in srows:
            b = [x for x in allb if x[0] < r["hm"]][-50:][:-1]
            if len(b) >= 2:
                h0, m0 = b[0][0].split(":")
                h1, m1 = b[-1][0].split(":")
                spans.append((int(h1) * 60 + int(m1)) - (int(h0) * 60 + int(m0)))
        say("%-5s %-24d %-19d %s"
            % (sym, len(allb), max(r["self_n"] for r in srows),
               ("%d-%d" % (min(spans), max(spans))) if spans else "-"))
    say("")
    say("READ: where the ALL-DAY SIP bar count is BELOW the logged self_n, the self aggregate is")
    say("holding minute buckets for minutes in which NO TRADE PRINTED — i.e. it is a contiguous")
    say("wall-clock minute grid built from the 10s stream (flat carry on quiet minutes), while the")
    say("caller's M1 fetch returns TRADED minutes only and its 49-bar window therefore stretches")
    say("backwards over hours on a thin name. Same nominal timeframe, different clocks.")
    open(os.path.join(HERE, "kevseq_frontside_sources_20260817_run.txt"), "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
