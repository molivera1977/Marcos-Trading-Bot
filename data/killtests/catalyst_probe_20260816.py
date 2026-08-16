#!/usr/bin/env python3
"""CATALYST PROBE 8/16 (Sunday agenda item 8) — READ-ONLY research + kill-test. No bot edits.
Probe 1: Alpaca News REST access + coverage census (top-12 runners x last 10 manifest dates).
Probe 2: point-in-time catalyst stamp on the champion lanes (36-date window, live-parity chain
from flatten_parity_20260816.py: BA in-window, grinder1030 re-attack, E3 exits, 15:45 flatten).
catalyst=True iff a headline with created_at in (prior business day 20:00Z, signal time] and the
symbol in the article's symbols list. KIND by keyword. Digest-type ("N Stocks Moving...") flagged.
"""
import importlib.util, os, sys, json, time, re, datetime as dt, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = HERE + "/catalyst_probe_20260816_news_cache.json"
KEY = os.environ["ALPACA_KEY"]; SEC = os.environ["ALPACA_SECRET"]
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); OUT.append(s)

# ---------- news fetch ----------
RATE = {"n": 0, "429": 0, "last_hdr": None}
def fetch_news(sym, start, end):
    """All articles for sym in [start,end], paginated. Returns list of dicts (created_at, headline, symbols, source)."""
    arts = []; tok = None
    while True:
        q = {"symbols": sym, "start": start, "end": end, "limit": 50, "sort": "asc", "include_content": "false"}
        if tok: q["page_token"] = tok
        req = urllib.request.Request("https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(q),
                                     headers={"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SEC})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    RATE["n"] += 1
                    RATE["last_hdr"] = {k: v for k, v in r.headers.items() if "ratelimit" in k.lower()}
                    d = json.load(r); break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    RATE["429"] += 1; time.sleep(2 + attempt * 2); continue
                raise
        else:
            raise RuntimeError("429 storm")
        for a in d.get("news", []):
            arts.append({"created_at": a["created_at"], "headline": a["headline"], "symbols": a["symbols"],
                         "source": a["source"], "n_syms": len(a["symbols"])})
        tok = d.get("next_page_token")
        time.sleep(0.34)
        if not tok: break
    return arts

def prior_bday_close_z(date):
    d = dt.date.fromisoformat(date) - dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d.isoformat() + "T20:00:00Z"

def load_cache():
    return json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def news_for(cache, sym, date):
    k = f"{sym}|{date}"
    if k not in cache:
        cache[k] = fetch_news(sym, prior_bday_close_z(date), date + "T20:00:00Z")
        json.dump(cache, open(CACHE, "w"))
    return cache[k]

DIGEST = re.compile(r"stocks moving|movers|top gainers|top losers|biggest|pre-market|premarket session|"
                    r"after-market session|intraday session|dow |nasdaq |s&p |us stocks|market open|midday|"
                    r"crypto|bitcoin", re.I)
KINDS = [
    ("offering", r"offering|pricing of|priced|direct offering|private placement|registered direct|at-the-market|"
                 r"warrant|dilut|reverse split|shelf|convertible|units? at"),
    ("earnings", r"earnings|eps|revenue|q[1-4]|quarter|fiscal|guidance|results|sales \$"),
    ("fda_clinical", r"fda|clinical|phase|trial|approval|ind |orphan|breakthrough|patient|dosing|efficacy"),
    ("merger", r"merger|acqui|to be acquired|buyout|takeover|letter of intent|loi |combination|spac|de-spac"),
    ("contract", r"contract|partnership|agreement|collaborat|award|order|deal|launch|deploy|mou|customer|distribution"),
    ("analyst", r"analyst|upgrade|downgrade|price target|initiat|rating|maintains|reiterat"),
    ("halt", r"halt|circuit breaker|resume"),
    ("crypto_ai", r"crypto|bitcoin|ethereum|treasury|ai |artificial intelligence|blockchain|token"),
]
def kind_of(h):
    for k, rx in KINDS:
        if re.search(rx, h, re.I): return k
    return "other"

# ---------- Probe 1 ----------
def probe1(cache):
    P("# CATALYST PROBE 8/16 — Alpaca News REST (v1beta1/news), read-only")
    P(f"run at {dt.datetime.now().isoformat(timespec='seconds')} local")
    P("\n## Probe 1a — access check: XHG,DFSC,MF,WETO,LBGJ 8/13-8/14")
    arts = fetch_news("XHG,DFSC,MF,WETO,LBGJ", "2026-08-13T00:00:00Z", "2026-08-15T00:00:00Z")
    P(f"HTTP 200 on our plan; {len(arts)} articles; fields: author, content, created_at, headline, id, images, source, summary, symbols, updated_at, url")
    P("| created_at (UTC) | symbols | source | headline | digest? |"); P("|---|---|---|---|---|")
    for a in arts:
        P(f"| {a['created_at']} | {','.join(a['symbols'][:6])}{'…' if len(a['symbols'])>6 else ''} | {a['source']} | {a['headline'][:80]} | {'Y' if DIGEST.search(a['headline']) else ''} |")
    m = json.load(open(ROOT + "/data/universe/manifest.json"))
    dates = sorted(m)[-10:]
    P(f"\n## Probe 1b — coverage census: top-12 by gain, last 10 manifest dates {dates[0]}..{dates[-1]}")
    P("window per name-day = (prior business day 20:00Z, day 20:00Z]; 'pre-open' = created_at < 13:30Z (09:30 ET)")
    P("| date | names | any headline | non-digest headline | pre-open non-digest | names w/ ANY |"); P("|---|---|---|---|---|---|")
    tot = dict(n=0, any=0, nd=0, pre=0)
    for d in dates:
        rows = sorted(m[d], key=lambda r: -r["gain"])[:12]
        c_any = c_nd = c_pre = 0; who = []
        for r in rows:
            arts = news_for(cache, r["sym"], d)
            nd = [a for a in arts if not DIGEST.search(a["headline"]) and a["n_syms"] <= 5]
            pre = [a for a in nd if a["created_at"] < d + "T13:30:00Z"]
            c_any += bool(arts); c_nd += bool(nd); c_pre += bool(pre)
            if arts: who.append(r["sym"] + ("*" if pre else ""))
        tot["n"] += len(rows); tot["any"] += c_any; tot["nd"] += c_nd; tot["pre"] += c_pre
        P(f"| {d} | {len(rows)} | {c_any} | {c_nd} | {c_pre} | {' '.join(who)} |")
    P(f"| **TOTAL** | {tot['n']} | {tot['any']} ({100*tot['any']/tot['n']:.0f}%) | {tot['nd']} ({100*tot['nd']/tot['n']:.0f}%) | {tot['pre']} ({100*tot['pre']/tot['n']:.0f}%) | * = pre-open non-digest |")
    P(f"rate-limit: {RATE['n']} requests so far, {RATE['429']} x HTTP 429 (pace 0.34s/req); headers seen: {RATE['last_hdr']}")
    return tot

# ---------- Probe 2 ----------
def probe2(cache):
    spec = importlib.util.spec_from_file_location("FP", HERE + "/flatten_parity_20260816.py")
    FP = importlib.util.module_from_spec(spec); spec.loader.exec_module(FP)
    S, G, F, B, E = FP.S, FP.G, FP.F, FP.B, FP.E
    dates, gsig, fsig, fbrk = FP.build_36()
    P(f"\n## Probe 2 — point-in-time catalyst kill-test, {len(dates)} dates {dates[0]}..{dates[-1]}, LIVE-parity chain (15:45 flatten, 15:30 cutoff, E3)")
    FP.set_mode(True)
    solo = {}
    solo["BA in-window (solo)"] = S.run(FP.cut(fbrk))
    solo["grinder1030 (solo)"] = S.run(FP.cut(gsig))
    solo["flat_top retest (solo)"] = S.run(FP.cut(fsig))
    kept_n = FP.reattack(FP.cut(gsig))
    strip = lambda kept: [{kk: s[kk] for kk in ("sym","date","det","i","t","key","entry","stop")} for s in kept]
    combN = sorted(strip(kept_n) + FP.cut(fbrk), key=lambda s: (s["key"], s["sym"], s["det"]))
    resOn, _ = FP.quiet(B.pipeline, combN, dates, G.exec_e3, "O NEW")
    port = resOn["h4"]
    P(f"reconcile vs flatten_parity NEW: O-config H4 N={len(port)} total ${sum(x['pnl'] for x in port):+.2f}; "
      f"BA solo N={len(solo['BA in-window (solo)'])}; grinder solo N={len(solo['grinder1030 (solo)'])}")
    # fetch news for every name-day touched
    keys = sorted({(x["sym"], x["date"]) for tr in list(solo.values()) + [port] for x in tr})
    P(f"name-days needing news: {len(keys)}")
    for i, (sym, d) in enumerate(keys):
        news_for(cache, sym, d)
    P(f"rate-limit after probe 2 fetch: {RATE['n']} requests, {RATE['429']} x 429; headers: {RATE['last_hdr']}")

    def stamp(x):
        sig_z = x["date"] + "T" + x["t"] + "Z"
        arts = [a for a in cache[f"{x['sym']}|{x['date']}"] if a["created_at"] <= sig_z]
        nd = [a for a in arts if not DIGEST.search(a["headline"]) and a["n_syms"] <= 5]
        x["cat_any"] = bool(arts); x["cat"] = bool(nd)
        x["kind"] = kind_of(" ".join(a["headline"] for a in nd)) if nd else ("digest_only" if arts else "none")
        x["first_kind"] = kind_of(nd[0]["headline"]) if nd else x["kind"]
        return x

    def grp(name, tr):
        tr = [stamp(dict(x)) for x in tr]
        def row(lbl, sub):
            n = len(sub); tot = sum(x["pnl"] for x in sub)
            w = 100 * sum(1 for x in sub if x["pnl"] > 0) / n if n else 0
            dd = {}
            for x in sub: dd[x["date"]] = dd.get(x["date"], 0) + x["pnl"]
            dv = sorted(dd.values()); dm = (sum(dv) / len(dv)) if dv else 0
            dmed = (dv[len(dv)//2] if len(dv) % 2 else (dv[len(dv)//2-1]+dv[len(dv)//2])/2) if dv else 0
            g = sum(1 for v in dv if v > 0)
            P(f"| {lbl} | {n} | {w:.0f}% | ${tot:+.2f} | ${(tot/n if n else 0):+.2f} | {len(dv)} | ${dm:+.2f} | ${dmed:+.2f} | {g}/{len(dv)} |")
            return dict(n=n, win=w, tot=tot, per=(tot/n if n else 0), days=len(dv), dmean=dm)
        P(f"\n### {name}")
        P("| split | N | win | total | $/trade | days | day mean | day median | green |"); P("|---|---|---|---|---|---|---|---|---|")
        r = {}
        r["all"] = row("ALL", tr)
        r["cat"] = row("catalyst (non-digest, pt-in-time)", [x for x in tr if x["cat"]])
        r["nocat"] = row("no catalyst", [x for x in tr if not x["cat"]])
        r["digest_only"] = row("  digest-only headline (Benzinga movers)", [x for x in tr if x["cat_any"] and not x["cat"]])
        r["nothing"] = row("  nothing at all", [x for x in tr if not x["cat_any"]])
        P("| by KIND (first non-digest headline) | | | | | | | | |")
        kinds = {}
        for x in tr:
            if x["cat"]: kinds.setdefault(x["first_kind"], []).append(x)
        for k in sorted(kinds, key=lambda k: -len(kinds[k])):
            r["kind_" + k] = row(f"  {k}", kinds[k])
        # verdict
        c, nc = r["cat"], r["nocat"]
        disc = "n/a"
        if c["n"] >= 15 and nc["n"] >= 15:
            disc = f"catalyst {c['per']:+.2f} vs none {nc['per']:+.2f} $/trade (delta {c['per']-nc['per']:+.2f}); win {c['win']:.0f}% vs {nc['win']:.0f}%"
        P(f"verdict-input: {disc}")
        return r, tr
    R = {}
    for nm, tr in solo.items(): R[nm] = grp(nm, tr)[0]
    R["O-config portfolio (BA+grinder re-attack, 2-slot)"], port_st = grp("O-config portfolio (BA+grinder re-attack, 2-slot, H4)", port)
    for det in ("flat_top", "grinder"):
        R[f"O-config {det} leg"] = grp(f"O-config {det} leg", [x for x in port if x["det"] == det])[0]
    # per-trade dump of catalyst trades (portfolio) for tracing
    P("\n### O-config portfolio: catalyst trades (for the one-trade trace rule)")
    P("| date | sym | det | sig(UTC) | pnl | kind | first headline (created_at) |"); P("|---|---|---|---|---|---|---|")
    for x in port_st:
        if not x["cat"]: continue
        sig_z = x["date"] + "T" + x["t"] + "Z"
        nd = [a for a in cache[f"{x['sym']}|{x['date']}"] if a["created_at"] <= sig_z and not DIGEST.search(a["headline"]) and a["n_syms"] <= 5]
        P(f"| {x['date']} | {x['sym']} | {x['det']} | {x['t']} | ${x['pnl']:+.2f} | {x['first_kind']} | {nd[0]['headline'][:70]} ({nd[0]['created_at']}) |")
    return R

def main():
    cache = load_cache()
    t1 = probe1(cache)
    R = probe2(cache)
    P(f"\nTOTAL requests {RATE['n']}, 429s {RATE['429']}")
    json.dump({"coverage": t1, "lanes": R, "rate": RATE}, open(HERE + "/catalyst_probe_20260816.json", "w"), indent=1, default=str)
    open(HERE + "/catalyst_probe_20260816_raw.md", "w").write("\n".join(OUT))

if __name__ == "__main__":
    main()
