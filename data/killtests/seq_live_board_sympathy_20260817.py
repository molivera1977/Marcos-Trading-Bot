#!/usr/bin/env python3
"""LIVE-BOARD SYMPATHY STUDY 8/17 — remove the runner-filter caveat from H1.

Prior study (seq_cross_ticker_20260817.py) graded H1 LEADER-FOLLOWER = BOARD-SIGNAL on a
WITHIN-UNIVERSE proxy board (gain>=40% runners only). This study rebuilds the board from
the dashboard's durable decisions archive — the bot's REAL-BOARD view — and re-runs H1.

Board source: GET /api/decisions_archive?date=YYYY-MM-DD (X-Dashboard-Secret), cached in
data/killtests/archive_cache/. Fires/prices/pnl: unchanged engine chain via
sequence_mining_pilot_20260817.py (break_attack + grinder, E3 $500 live-parity).

Analysis only. No bot edits, no env changes.
"""
import importlib.util, os, json, random, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = HERE + "/archive_cache"
spec = importlib.util.spec_from_file_location("PILOT", HERE + "/sequence_mining_pilot_20260817.py")
PILOT = importlib.util.module_from_spec(spec); spec.loader.exec_module(PILOT)
S = PILOT.S; E = S.E

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

SENTINEL = ("_BOOT", "_KEV", "_EOD", "_GATE", "__LENS__", "_HEALTH", "_BOARD", "_exec_health")

# per-scan-cycle statuses: emitted by the bot's loop over the names it is WATCHING.
CYCLE = {"consolidating", "watching", "break_armed", "orb_break_armed", "broke_below_vwap",
         "lens_focus", "lens_unfocus", "pullback_timeout", "orb_pullback_timeout",
         "daily_loaded", "halt_suspect", "broke_not_flat"}
# real-board BREAK events (the bot's own live break detection on the real board)
BREAK = {"break_armed", "orb_break_armed"}

def sec_utc_from_et(tstr):
    """archive 'HH:MM:SS AM' (ET, EDT all season) -> seconds since UTC midnight."""
    hh = int(tstr[0:2]) % 12
    if tstr[9:11].upper() == "PM": hh += 12
    return hh * 3600 + int(tstr[3:5]) * 60 + int(tstr[6:8]) + 4 * 3600

def sec(hh):  # bars "HH:MM:SS" UTC -> seconds
    return int(hh[0:2]) * 3600 + int(hh[3:5]) * 60 + int(hh[6:8])

RTH0 = sec("13:30:00")   # 09:30 ET in UTC seconds

# ---------------- archive load ----------------
def load_archive():
    days = {}
    for f in sorted(os.listdir(CACHE)):
        if not f.endswith(".json"): continue
        j = json.load(open(CACHE + "/" + f))
        if j.get("total", 0) < 500: continue      # weekend/empty stubs
        date = f[:-5]
        seen = defaultdict(list)     # ticker -> [utc sec of any cycle row]
        firstrow = {}                # ticker -> first utc sec of ANY row
        breaks = defaultdict(list)   # ticker -> [utc sec of break event, post-09:30]
        for r in j["rows"]:
            tk = r.get("ticker") or ""
            if not tk or tk in SENTINEL or tk.startswith("_"): continue
            try: t = sec_utc_from_et(r["time"])
            except Exception: continue
            st = r.get("status")
            if tk not in firstrow or t < firstrow[tk]: firstrow[tk] = t
            if st in CYCLE: seen[tk].append(t)
            if st in BREAK and t >= RTH0: breaks[tk].append(t)
        for tk in seen: seen[tk].sort()
        days[date] = dict(seen=dict(seen), firstrow=firstrow,
                          breaks={k: sorted(v) for k, v in breaks.items()},
                          allnames=set(firstrow))
    return days

# ---------------- board reconstruction ----------------
PRESENCE = 3600   # a name counts as "on the board" from its first row until 60 min after its last cycle row

def on_board(ad, sym, t):
    """membership at time t: first row <= t and a cycle row within the trailing PRESENCE window
    (or any cycle row later that day — the bot was still cycling it)."""
    if sym not in ad["firstrow"] or ad["firstrow"][sym] > t: return False
    ts = ad["seen"].get(sym)
    if not ts: return False
    return any(t - PRESENCE <= x <= t + PRESENCE for x in ts)

def real_board_leader(ad):
    """first REAL-BOARD name after 09:30 ET to print a break event in the archive."""
    ev = sorted((t, tk) for tk, ts in ad["breaks"].items() for t in ts)
    return (ev[0][1], ev[0][0]) if ev else (None, None)

# ---------------- bars-side burst-break leader restricted to real-board names ----------------
def bars_bursts(dates):
    bursts = defaultdict(lambda: defaultdict(list))
    for (sym, date), (bars, emas, gaps) in E.DAYS.items():
        if date not in dates: continue
        full = S.FULL.get((sym, date), [])
        pre = [b for b in full if E.hhmm_b(b) < "13:30:00"]
        sess_hi = max((b["h"] for b in pre), default=bars[0]["h"])
        vols = [b["v"] for b in bars]
        for i, b in enumerate(bars):
            if b["h"] > sess_hi:
                t = sec(E.hhmm_b(b))
                if i >= 12 and t >= RTH0:
                    prior = vols[max(0, i - 30):i]
                    if prior and b["v"] >= 3.0 * (sum(prior) / len(prior)):
                        bursts[date][sym].append(t)
                sess_hi = b["h"]
    return bursts

# ---------------- liquidity floor (live parity: median $vol of trailing 10 bars >= 15 x $500) ----------------
NEED = 15.0 * 500.0
def liquid(sym, date, i):
    bars = E.DAYS[(sym, date)][0]
    comp = bars[max(0, i - 10):i]
    if len(comp) < 5: return None          # fail-open in live; counted separately here
    dv = sorted(b["v"] * b["c"] for b in comp)
    return dv[len(dv) // 2] >= NEED

def mstat(rows):
    n = len(rows)
    if n == 0: return dict(N=0, dtr=0.0, win=0.0, tot=0.0, med=0.0)
    tot = sum(r["pnl"] for r in rows)
    pl = sorted(r["pnl"] for r in rows)
    return dict(N=n, dtr=tot / n, win=100 * sum(1 for r in rows if r["win"]) / n, tot=tot,
                med=pl[n // 2])

HDR = "| side | N | win | $/tr | median $ | total |"
SEP = "|---|---|---|---|---|---|"
def fmt(nm, s):
    return f"| {nm} | {s['N']} | {s['win']:.0f}% | ${s['dtr']:+.2f} | ${s['med']:+.2f} | ${s['tot']:+.2f} |"

def daystats(rows):
    by = defaultdict(list)
    for r in rows: by[r["date"]].append(r["pnl"])
    d = sorted(sum(v) for v in by.values())
    if not d: return 0.0, 0.0, 0.0, 0
    return sum(d) / len(d), d[len(d) // 2], d[0], len(d)

def null_shuffle(fires, arch, flagfn, iters=5000, seed=17):
    """within each date, shuffle (sym, time) across that date's fires; recompute the flag."""
    rnd = random.Random(seed)
    bydate = defaultdict(list)
    for r in fires: bydate[r["date"]].append(r)
    obs = [r for r in fires if flagfn(arch[r["date"]], r["sym"], r["tsec"])]
    obs_mean = sum(r["pnl"] for r in obs) / len(obs) if obs else 0.0
    ge = 0; means = []
    for _ in range(iters):
        gp = []
        for date, rs in bydate.items():
            ad = arch[date]
            pairs = [(r["sym"], r["tsec"]) for r in rs]
            rnd.shuffle(pairs)
            for r, (sym, t) in zip(rs, pairs):
                if flagfn(ad, sym, t): gp.append(r["pnl"])
        mu = sum(gp) / len(gp) if gp else 0.0
        means.append(mu); ge += (mu >= obs_mean)
    return dict(p=ge / iters, rand_mean=sum(means) / len(means), obs=obs_mean, iters=iters)


def main():
    P("# LIVE-BOARD SYMPATHY STUDY — 8/17/26")
    P("H1 re-run with the bot's REAL board (dashboard decisions archive) instead of the")
    P("gain>=40% runner-filtered universe proxy. Engine chain UNCHANGED (E3 $500 live-parity).")
    P("Analysis only — no bot edits, no env changes.")
    P("")

    nf, nd, udates = S.load_all()
    arch = load_archive()
    P(f"Universe bars cache: {nf} files, {nd} name-days, {len(udates)} dates {udates[0]}..{udates[-1]}.")
    P(f"Archive: {len(arch)} substantive days {min(arch)}..{max(arch)}.")

    # ---------- SCHEMA INVENTORY ----------
    P("\n---\n\n## 1. ARCHIVE SCHEMA INVENTORY")
    stat_keys = defaultdict(lambda: defaultdict(int)); stat_n = defaultdict(int)
    for f in sorted(os.listdir(CACHE)):
        if not f.endswith(".json"): continue
        j = json.load(open(CACHE + "/" + f))
        if j.get("total", 0) < 500: continue
        for r in j["rows"]:
            stat_n[r["status"]] += 1
            for k in r: stat_keys[r["status"]][k] += 1
    P(f"Distinct statuses across all cached days: {len(stat_n)}. Every row carries "
      f"`date`, `recorded_at`, `status`, `ticker`, `time` (ET, 12-hour).")
    P("\nBoard-relevant statuses (fields beyond the universal five):\n")
    P("| status | rows (all days) | extra fields | what it reconstructs |")
    P("|---|---|---|---|")
    ROLE = {
        "consolidating": "per-cycle scan tick on a watched name -> MEMBERSHIP",
        "watching": "per-cycle scan tick -> MEMBERSHIP",
        "break_armed": "live break detection on a real-board name -> LEADER/BREAK events",
        "orb_break_armed": "ORB break detection -> LEADER/BREAK events",
        "daily_loaded": "name's daily bars loaded -> board JOIN time",
        "lens_focus": "lens attention on a name -> membership + attention",
        "lens_unfocus": "lens attention released -> membership",
        "halt_suspect": "feed-gap stamp on a watched name -> membership",
        "broke_below_vwap": "per-cycle structural stamp -> membership",
        "leader_armed": "explicit LEADER/CROWN arm event (why=fresh_highs etc.)",
        "crown_eod_report": "EOD crown scorecard per crowned name",
        "board_funnel_fallback": "board funnel fell back (sentinel _BOARD; no membership list)",
        "lens_dark": "lens dark, count only (sentinel __LENS__; no per-name list)",
    }
    for st in ["consolidating", "watching", "break_armed", "orb_break_armed", "daily_loaded",
               "lens_focus", "lens_unfocus", "halt_suspect", "broke_below_vwap",
               "leader_armed", "crown_eod_report", "board_funnel_fallback", "lens_dark"]:
        if st not in stat_n: continue
        extra = sorted(k for k in stat_keys[st] if k not in ("date", "recorded_at", "status", "ticker", "time"))
        P(f"| `{st}` | {stat_n[st]} | {', '.join('`'+e+'`' for e in extra) or '(none)'} | {ROLE.get(st,'')} |")

    P("\n**HONEST SCHEMA FINDING — there is NO board-snapshot row.** No status emits the")
    P("scanner's membership list at a point in time (`board_funnel_fallback` and `lens_dark`")
    P("are counters on sentinel tickers, not rosters). Board membership must be INFERRED from")
    P("per-name rows. The bot cycles every watched name through `consolidating`/`watching`/")
    P("`break_armed`/`daily_loaded` etc., so the defensible reconstruction is:")
    P("")
    P("  * BOARD MEMBERSHIP (coarse, minute-resolution NOT guaranteed): a name is on the board")
    P("    at time t if it has a per-cycle row and one of those rows falls within +/-60 min of t.")
    P("    LIMITATION: a name the bot loaded but that emitted no cycle row in a given hour is")
    P("    invisible; membership is a LOWER BOUND, and its resolution is the cycle cadence, not")
    P("    the minute. The coarsest defensible fallback (used as a robustness arm) is the SET of")
    P("    names with any row that day.")
    P("  * REAL-BOARD BREAK EVENTS: `break_armed` / `orb_break_armed` are the bot's own live")
    P("    break detections on real-board names, timestamped. These are used for the LEADER.")
    P("    LIMITATION: they carry `price`/`w_high` but NO volume, so the prior study's")
    P("    burst-volume qualifier cannot be applied to non-universe board names. Arm B below")
    P("    keeps burst-volume by restricting the bars-side leader to real-board names.")
    P("  * LEADER/CROWN: `leader_armed` (with `why`) and `crown_eod_report` are the explicit")
    P("    real-board leader events; `leader_armed` is sparse (14 rows on 8/14) and mostly")
    P("    PREMARKET, so it is reported, not used as the H1 leader.")

    # ---------- OVERLAP + SPLIT ----------
    P("\n---\n\n## 2. OVERLAP AND OOS SPLIT")
    overlap = sorted(set(udates) & set(arch))
    P(f"Dates in BOTH the archive and the bars10s universe cache: **{len(overlap)}** "
      f"({overlap[0]}..{overlap[-1]}).")
    P(f"Archive-only dates (no bars): {sorted(set(arch)-set(udates))}")
    P(f"Bars-only dates (pre-archive): {len(set(udates)-set(arch))} dates "
      f"{sorted(set(udates)-set(arch))[0]}..{sorted(set(udates)-set(arch))[-1]}")
    if len(overlap) < 12:
        P("\n**UNDERPOWERED** — fewer than 12 overlap dates; descriptive only, no wall.")
        underpowered = True
    else:
        underpowered = False
    n_hold = len(overlap) // 3
    mine_dates = set(overlap[:-n_hold]); hold_dates = set(overlap[-n_hold:])
    P(f"\nChronological split (same discipline as the prior study, 1/3 held out):")
    P(f"- MINE: {len(mine_dates)} dates {overlap[0]}..{sorted(mine_dates)[-1]}")
    P(f"- HOLD-OUT: {len(hold_dates)} dates {sorted(hold_dates)[0]}..{overlap[-1]}")
    P(f"- BOUNDARY: **{sorted(mine_dates)[-1]} | {sorted(hold_dates)[0]}**")

    # ---------- BOARD COVERAGE ----------
    P("\n### Board coverage on the overlap dates")
    P("| date | board names (archive) | universe names (bars) | on both | real-board leader | leader time ET |")
    P("|---|---|---|---|---|---|")
    unames = defaultdict(set)
    for (sym, date) in E.DAYS: unames[date].add(sym)
    leaders = {}
    for d in overlap:
        ad = arch[d]
        ld, lt = real_board_leader(ad)
        leaders[d] = (ld, lt)
        both = unames[d] & ad["allnames"]
        et = f"{(lt-14400)//3600:02d}:{((lt-14400)%3600)//60:02d}" if lt else "-"
        P(f"| {d} | {len(ad['allnames'])} | {len(unames[d])} | {len(both)} | {ld or '-'} | {et} |")
    nb = sum(len(arch[d]['allnames']) for d in overlap) / len(overlap)
    nu = sum(len(unames[d]) for d in overlap) / len(overlap)
    ncov = sum(1 for d in overlap if leaders[d][0])
    P(f"\nMean real board = **{nb:.1f} names/day** vs universe proxy **{nu:.1f} names/day** "
      f"({nb/nu:.1f}x wider). {ncov}/{len(overlap)} dates have a post-09:30 real-board break leader.")
    inuniv = sum(1 for d in overlap if leaders[d][0] in unames[d])
    P(f"On **{inuniv}/{ncov}** of those dates the real-board leader is ALSO a universe (40%+ runner) "
      f"name — i.e. the proxy would have found a DIFFERENT leader on {ncov-inuniv} dates.")

    # ---------- FIRES ----------
    rows = []
    for key in ("break_attack", "grinder"):
        for r in PILOT.grade(PILOT.gen_lane(key)):
            r["lane"] = key; r["tsec"] = sec(r["t"])
            rows.append(r)
    P(f"\nFires: {len(rows)} total (break-attack + grinder, E3-graded, deduped) across all "
      f"{len(udates)} bars dates.")
    ov_rows = [r for r in rows if r["date"] in set(overlap)]
    P(f"Fires on the {len(overlap)} OVERLAP dates: **{len(ov_rows)}**.")

    # ---------- H1 ARMS ----------
    def flag_A(ad, sym, t):
        ld, lt = ad["_leaderA"]
        return (ld is not None and sym != ld and lt <= t <= lt + 1800)
    def flag_B(ad, sym, t):
        ld, lt = ad["_leaderB"]
        return (ld is not None and sym != ld and lt <= t <= lt + 1800)

    bb = bars_bursts(set(overlap))
    for d in overlap:
        ad = arch[d]
        ad["_leaderA"] = leaders[d]
        # Arm B: burst-volume leader from bars, restricted to names ON the real board
        ev = sorted((t, s2) for s2, ts in bb[d].items() for t in ts if s2 in ad["allnames"])
        ad["_leaderB"] = (ev[0][1], ev[0][0]) if ev else (None, None)
    nB = sum(1 for d in overlap if arch[d]["_leaderB"][0])
    P(f"Arm B (burst-volume leader restricted to real-board names): leader found on {nB}/{len(overlap)} dates.")

    results = {}
    for arm, flagfn, desc in [
        ("A", flag_A, "LEADER = first REAL-BOARD name to print a break event (`break_armed`/"
                      "`orb_break_armed`) after 09:30 ET. No volume qualifier available."),
        ("B", flag_B, "LEADER = first name that is ON THE REAL BOARD to print a burst-volume "
                      "(>=3x prior-30-bar mean) new session high after 09:30 ET, prices from bars10s."),
    ]:
        P(f"\n---\n\n## 3{arm}. REAL-BOARD H1 — ARM {arm}")
        P(desc)
        P("SYMPATHY WINDOW = fire on a DIFFERENT real-board name within 30 min after the leader's break.")
        q = [r for r in ov_rows if arch[r["date"]][f"_leader{arm}"][0] is not None
             and on_board(arch[r["date"]], r["sym"], r["tsec"])]
        P(f"\nQualifying fires (date has a leader AND the fire's name was ON the real board at "
          f"fire time): **{len(q)}** of {len(ov_rows)} overlap fires.")
        for r in q: r["_f"] = flagfn(arch[r["date"]], r["sym"], r["tsec"])
        mT = [r for r in q if r["date"] in mine_dates and r["_f"]]
        mF = [r for r in q if r["date"] in mine_dates and not r["_f"]]
        hT = [r for r in q if r["date"] in hold_dates and r["_f"]]
        hF = [r for r in q if r["date"] in hold_dates and not r["_f"]]
        sT, sF, hS, hO = mstat(mT), mstat(mF), mstat(hT), mstat(hF)
        P(f"\n### MINE ({len(mT)+len(mF)} fires)")
        P(HDR); P(SEP); P(fmt("sympathy window", sT)); P(fmt("outside window", sF))
        mine_lift = sT["dtr"] - sF["dtr"]
        P(f"MINE lift: **${mine_lift:+.2f}/tr**.")
        P(f"\n### HOLD-OUT ({len(hT)+len(hF)} fires) — window definition FROZEN from MINE")
        P(HDR); P(SEP); P(fmt("sympathy window", hS)); P(fmt("outside window", hO))
        hold_lift = hS["dtr"] - hO["dtr"]
        P(f"HOLD-OUT lift: **${hold_lift:+.2f}/tr**.")
        for nm, rs in (("sympathy", hT), ("outside", hF)):
            mu, md, worst, ndays = daystats(rs)
            P(f"- HOLD-OUT {nm}: day mean ${mu:+.2f}, day median ${md:+.2f}, WORST day ${worst:+.2f} ({ndays} days)")
        allT = mT + hT; allF = mF + hF
        aT, aF = mstat(allT), mstat(allF)
        P(f"\n### POOLED (all {len(overlap)} overlap dates, descriptive)")
        P(HDR); P(SEP); P(fmt("sympathy window", aT)); P(fmt("outside window", aF))
        P(f"Pooled lift: **${aT['dtr']-aF['dtr']:+.2f}/tr**.")

        nr = None
        if hS["N"] >= 10:
            nr = null_shuffle(hT + hF, arch, flagfn)
            P(f"\nNULL (within-date shuffle of the (sym,time) board context, {nr['iters']}x, hold-out): "
              f"observed sympathy $/tr ${nr['obs']:+.2f} vs random-mean ${nr['rand_mean']:+.2f}, "
              f"**p={nr['p']:.3f}**.")
            nrp = null_shuffle(allT + allF, arch, flagfn)
            P(f"NULL (pooled, all overlap dates, {nrp['iters']}x): observed ${nrp['obs']:+.2f} vs "
              f"random-mean ${nrp['rand_mean']:+.2f}, **p={nrp['p']:.3f}**.")
        else:
            P(f"\nNULL skipped — hold-out sympathy side carries only {hS['N']} fires (<10).")
        results[arm] = dict(mine=(sT, sF, mine_lift), hold=(hS, hO, hold_lift),
                            pooled=(aT, aF), null=nr, q=len(q), rowsT=allT, rowsF=allF)

    # ---------- TRADEABLE FRACTION ----------
    P("\n---\n\n## 4. TRADEABLE FRACTION")
    P("A sympathy-window fire is TRADEABLE only if (a) the name was on the bot's real board at")
    P("fire time and (b) it passes the live liquidity floor `_ambient_dvol_ok`: median $-volume")
    P(f"of the trailing 10 completed bars >= AMBIENT_DVOL_MULT(15) x MAX_TRADE_DOLLARS($500) = "
      f"${NEED:,.0f}. NOTE: applied to 10s bars, so this is a ~6x STRICTER floor than the live "
      f"1-min version — the tradeable fraction below is a conservative LOWER bound.")
    for arm in ("A", "B"):
        flagfn = flag_A if arm == "A" else flag_B
        allw = [r for r in ov_rows
                if arch[r["date"]][f"_leader{arm}"][0] is not None
                and flagfn(arch[r["date"]], r["sym"], r["tsec"])]
        onb = [r for r in allw if on_board(arch[r["date"]], r["sym"], r["tsec"])]
        liq = [r for r in onb if liquid(r["sym"], r["date"], r["i"]) is True]
        fo = [r for r in onb if liquid(r["sym"], r["date"], r["i"]) is None]
        P(f"\n**Arm {arm}**: window fires (any name) {len(allw)} -> on real board at fire time "
          f"{len(onb)} ({100*len(onb)/max(1,len(allw)):.0f}%) -> also passing the 10s liquidity "
          f"floor **{len(liq)} ({100*len(liq)/max(1,len(allw)):.0f}% of window fires, "
          f"{100*len(liq)/max(1,len(onb)):.0f}% of on-board ones)**; {len(fo)} fail-open (<5 bars).")
        if liq:
            s = mstat(liq)
            P(f"  tradeable-only sympathy cohort: N={s['N']} win {s['win']:.0f}% $/tr ${s['dtr']:+.2f} "
              f"median ${s['med']:+.2f} total ${s['tot']:+.2f}")

    json.dump({k: dict(q=v["q"],
                       mine_lift=v["mine"][2], hold_lift=v["hold"][2],
                       mine_T=v["mine"][0], mine_F=v["mine"][1],
                       hold_T=v["hold"][0], hold_F=v["hold"][1],
                       pooled_T=v["pooled"][0], pooled_F=v["pooled"][1],
                       null=v["null"]) for k, v in results.items()},
              open(HERE + "/seq_live_board_sympathy_20260817_out.json", "w"), indent=1, default=str)
    open(HERE + "/seq_live_board_sympathy_20260817_run.txt", "w").write("\n".join(OUT) + "\n")
    return results

if __name__ == "__main__":
    main()
