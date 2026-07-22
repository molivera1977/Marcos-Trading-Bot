"""FULL-PANEL AS-DEPLOYED REPLAY — 7/20 + 7/21 through the machine set at commit 56d585d.

Order-dependent portfolio sim (sim-integrity law): global minute clock, exits evaluated
before targets bank, capital ledger enforced, no silent cohort exclusion (all exclusions
declared in the APPROX block printed at the end).

Machines: ignition, rocket_catcher (Kev-spec 3-phase), flat_top (wick-aware #73),
orb (wick-aware #73), ma_pullback.  EXCLUDED: vwap_reclaim/zone_flip (need the 10s
recorder stream, not in the 1m cache; both fired 0 live on these days pre-#67), bounce
(filtered out of breakouts by the live code itself).

Gates: chart gate ENFORCE w/ the day's REAL posted levels (kevlv_*.json), vel5 floor,
extension guard (rocket exempt), momentum gate (expansion>=1.5 + peak_rel>=0.30 +
10k liquidity floor + topping tail; ignition exempt), risk sizing $30/(entry-stop),
$1k notional cap, 5% volume guard, $3k capital ledger.
Fail-open (no offline data): daily-first veto, spread, L2  — all declared.

Exits: kev25 R-tiers (+1R 50% / +2R 75%) or rocket %-tiers (1.5x 33% / 2.0x 67%),
velocity-ride defer, BE floor after scale 2, 3-min close-based stop, health trail
(close < ema9(3m) AND < session VWAP after a partial), 15:45 force close.
Bot functions imported byte-identical via rig/loader."""
import json, os, sys, hashlib, urllib.parse, pathlib, statistics as st

sys.path.insert(0, "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/rig")
from loader import load_bot
bot = load_bot()

U = "https://zestful-intuition-production-b16a.up.railway.app"
HERE = pathlib.Path(__file__).resolve().parent
def get(u):
    k = HERE / "mcache" / (hashlib.md5(u.encode()).hexdigest() + ".json")
    return json.load(open(k)) if k.exists() else {}

TRACE = os.environ.get("TRACE", "")          # ticker to bar-trace (hand-trace mode)
CAP_MODE = os.environ.get("CAP_MODE", "burn")   # burn = as-deployed (curl counts); refund = only survived entries count
CPHI_FIX = os.environ.get("CPHI_FIX", "0") == "1"  # 7/21 CPHI break -> 1.07 (the live morning map; 9.25 = tonight's re-read)
RANK_RESERVE = float(os.environ.get("RANK_RESERVE", "0"))   # $ non-top names must leave free (0 = FCFS as-deployed)
RANK_TOP = int(os.environ.get("RANK_TOP", "3"))             # K: rank cutoff for reserve exemption

def roster(d):
    names = set(get(f"{U}/api/watching?date={d}").get("tickers") or [])
    for r in (get(f"{U}/api/decisions_archive?date={d}&limit=12000").get("rows") or []):
        names.add((r.get("ticker") or "").upper())
    return sorted(n for n in names if n and n != "N/A")

def day_bars(t, d):
    """(prior_rth, today_rth, today_pre) 1m bars for ticker t on day d, time-sorted."""
    allb = get(f"{U}/api/minute_ext?ticker={urllib.parse.quote(t)}&count=1200").get("bars") or []
    allb.sort(key=lambda x: str(x.get("time", "")))
    prior = [x for x in allb if str(x.get("time", ""))[:10] < d and x.get("session") == "RTH"]
    today = [x for x in allb if str(x.get("time", "")).startswith(d) and x.get("session") == "RTH"]
    pre   = [x for x in allb if str(x.get("time", "")).startswith(d) and x.get("session") == "PRE"]
    return prior, today, pre

def et_min(b):
    s = str(b.get("time", ""))[11:16]
    try: return int(s[:2]) * 60 + int(s[3:])
    except Exception: return None

BH, BL, BC = bot._bar_high, bot._bar_low, bot._bar_close
def BV(b): return float(b.get("volume") or b.get("v") or 0)
def BO(b): return float(b.get("open") or b.get("o") or 0)

def sess_vwap(pre, today, upto):
    pv = vol = 0.0
    for b in pre + today[:upto + 1]:
        v = BV(b)
        tp = (BH(b) + BL(b) + BC(b)) / 3
        pv += tp * v; vol += v
    return pv / vol if vol > 0 else 0.0

def confirm_reclaim(today, i, level):
    """Port of _confirm_reclaim on completed bars (bar i = last completed)."""
    b = today[i]
    o, c, h, l = BO(b), BC(b), BH(b), BL(b)
    if c <= level: return False
    rng = h - l
    green = c > o
    wick = rng > 0 and (min(o, c) - l) / rng >= bot.BOTTOM_TAIL_RATIO
    return bool(green or wick)

def momentum_ok(today, i):
    """Port of check_momentum on completed bars (bar i = break bar). Returns (ok, reason)."""
    comp = today[:i + 1]
    if len(comp) < bot.MOMENTUM_BARS: return True, "fail_open_few_bars"
    peak = max(BV(b) for b in comp)
    last3 = comp[-bot.MOMENTUM_BARS:]
    avg_vol = sum(BV(b) for b in last3) / len(last3)
    if avg_vol < bot.MOMENTUM_MIN_AVG_VOL:
        return False, f"illiquid {int(avg_vol)}/bar"
    brk = BV(comp[-1])
    pvs = [BV(b) for b in comp[-(bot.MOMENTUM_BARS + 1):-1]]
    pav = sum(pvs) / len(pvs) if pvs else 0
    if pav > 0:
        expansion = brk / pav
        peak_rel = brk / peak if peak > 0 else 1.0
        if not (expansion >= bot.EXPANSION_MIN and peak_rel >= bot.PEAK_REL_MIN):
            return False, f"no build {expansion:.1f}x/{peak_rel*100:.0f}%peak"
    if bot.is_topping_tail(comp[-1]):
        return False, "topping tail"
    return True, "ok"

def chart_gate(levels, t, entry):
    lv = levels.get(t) or {}
    note = str(lv.get("note") or "").lower()
    if lv.get("veto") or "do-not-trade" in note or "do not trade" in note or note.strip() == "pass":
        return "skip", "veto"
    try: brk = float(lv.get("break") or 0)
    except (TypeError, ValueError): brk = 0.0
    if brk <= 0: return "skip", "no_marked_level"
    return ("allow", "broke_level") if entry >= brk else ("block", "below_level")

class Pos:
    __slots__ = ("t","machine","entry","stop0","stop","sh0","sh","tiers","ti","partial",
                 "fills","emin","reserved","last3close","entry_i")
    def __init__(self, t, machine, entry, stop, sh, tiers, emin, entry_i, reserved):
        self.t, self.machine, self.entry, self.stop0, self.stop = t, machine, entry, stop, stop
        self.sh0 = self.sh = sh; self.tiers, self.ti, self.partial = tiers, 0, False
        self.fills = []; self.emin, self.entry_i, self.reserved = emin, entry_i, reserved
        self.last3close = None   # time-key of last completed 3m bar already evaluated

def run_day(d, levels, out_rows, rej):
    R = roster(d)
    data = {}
    for t in R:
        prior, today, pre = day_bars(t, d)
        if len(today) >= 10:
            data[t] = (prior, today, pre, {et_min(b): i for i, b in enumerate(today) if et_min(b) is not None})
    names = sorted(data)
    ref = {}   # day-change reference: prior-day last RTH close, else today's first open
    for t in names:
        prior, today, pre, idx = data[t]
        ref[t] = BC(prior[-1]) if prior else (BO(today[0]) or BC(today[0]))
    lastpx = {}   # rolling last close per name
    S = {t: {} for t in names}          # per-name machine state (the live cache[t])
    positions, capital = {}, 3000.0
    rocket_n = 0
    day_pnl = 0.0

    for minute in range(810, 1201):   # UTC minutes (13:30-20:00 UTC = 9:30-16:00 ET)
        # ── 1) manage open positions ──
        for t in sorted(positions):
            prior, today, pre, idx = data[t]
            if minute not in idx: continue
            i = idx[minute]; p = positions[t]
            if i <= p.entry_i: continue
            bar = today[i]; hi, lo, cl = BH(bar), BL(bar), BC(bar)
            exited = False
            # 15:45 force close
            if minute >= 1185:   # 15:45 ET = 19:45 UTC
                p.fills.append((p.sh, cl, "3:45pm time stop", minute)); p.sh = 0; exited = True
            if not exited:
                # (a) 3m close-based stop + (b) health trail — on a NEWLY completed 3m bar
                rth_all = prior + today[:i + 1]
                comp3 = bot.aggregate_bars(rth_all, bot.SETUP_TF_MIN)[:-1]
                if comp3:
                    k3 = str(comp3[-1].get("time", ""))
                    if k3 != p.last3close and str(comp3[-1].get("time",""))[:10] == d:
                        # only 3m bars completed after entry qualify
                        m3 = et_min(comp3[-1])
                        if m3 is not None and m3 > p.emin:
                            p.last3close = k3
                            c3 = BC(comp3[-1])
                            if 0 < c3 <= p.stop:
                                p.fills.append((p.sh, c3, "3m close stop", minute)); p.sh = 0; exited = True
                            elif p.partial and p.sh > 0:
                                e9 = bot.calculate_ema9(comp3)
                                vw = sess_vwap(pre, today, i)
                                if c3 > 0 and e9 > 0 and vw > 0 and c3 < e9 and c3 < vw:
                                    p.fills.append((p.sh, c3, "health fold", minute)); p.sh = 0; exited = True
            if not exited and p.sh > 0:
                # (c) tier fills on the bar high (stop had first claim above)
                while p.ti < len(p.tiers) and p.sh > 0:
                    tp, cum = p.tiers[p.ti]
                    if hi < tp: break
                    # velocity-ride defer (live: 3-bar gain >= 12% -> ride)
                    if i >= 3:
                        c_ago = BC(today[i - bot.VELO_BARS])
                        if getattr(bot, "VELOCITY_RIDE", False) and c_ago > 0 and (cl - c_ago) / c_ago >= bot.VELO_RIDE_PCT:
                            break
                    sold = p.sh0 - p.sh
                    want = int(p.sh0 * cum) - sold
                    q = max(1, min(want, p.sh)) if cum < 1.0 else p.sh
                    p.fills.append((q, tp, f"scale{p.ti+1}", minute))
                    p.sh -= q; p.ti += 1; p.partial = True
                    if p.ti >= bot.BE_FLOOR_AFTER_SCALE:
                        p.stop = max(p.stop, p.entry)
                if p.sh == 0: exited = True
            if exited or p.sh == 0:
                pnl = sum(q * (px - p.entry) for q, px, *_ in p.fills)
                day_pnl += pnl
                capital += p.reserved
                out_rows.append({"day": d, "t": t, "machine": p.machine, "emin": p.emin,
                                 "entry": p.entry, "stop": p.stop0, "sh": p.sh0,
                                 "fills": p.fills, "pnl": round(pnl, 2),
                                 "R": round(pnl / (p.sh0 * (p.entry - p.stop0)), 2) if p.entry > p.stop0 else None})
                del positions[t]

        # rank update: day-change desc among names with a print so far
        for t in names:
            _pr, _td, _pe, _ix = data[t]
            if minute in _ix: lastpx[t] = BC(_td[_ix[minute]])
        _rk = sorted((x for x in lastpx if ref.get(x)), key=lambda x: -(lastpx[x] / ref[x] - 1))
        topK = set(_rk[:RANK_TOP])
        # ── 2) scan flat names for entries ──
        for t in names:
            if t in positions: continue
            prior, today, pre, idx = data[t]
            if minute not in idx: continue
            i = idx[minute]
            if i < 1: continue
            price = BC(today[i])
            if price <= 0: continue
            st_ = S[t]
            vwap = sess_vwap(pre, today, i)
            cand = None    # (machine, entry, stop, extra)

            # -- ignition (once) --
            if not st_.get("ignition_fired"):
                ign = None
                try: ign = bot.detect_ignition(today[:i + 1], price)
                except Exception: pass
                if ign:
                    st_["ignition_fired"] = True
                    cand = ("ignition", price, ign["stop"], {})

            # -- rocket catcher (once, 3-phase) --
            if cand is None and not st_.get("rocket_fired"):
                sess1 = today[:i + 1]
                if not st_.get("rocket_armed"):
                    rk = None
                    try: rk = bot.detect_rocket(sess1, price)
                    except Exception: pass
                    if rk:
                        st_["rocket_armed"] = True; st_["rocket_vel"] = rk["vel"]
                        st_["rocket_plow"] = price; st_["rocket_touched"] = False
                        if t == TRACE: print(f"TRACE {t} {minute//60}:{minute%60:02d} ROCKET ARMED vel {rk['vel']}")
                elif len(sess1) >= 2:
                    lb, pb_ = sess1[-1], sess1[-2]
                    lo, cl = BL(lb), BC(lb)
                    if lo > 0: st_["rocket_plow"] = min(st_.get("rocket_plow") or lo, lo)
                    closes = [BC(b) for b in sess1 if BC(b) > 0]
                    e20 = 0.0
                    if len(closes) >= 3:
                        e20 = closes[0]
                        for c in closes[1:]: e20 = c * (2 / 21) + e20 * (1 - 2 / 21)
                    if e20 > 0 and lo <= e20: st_["rocket_touched"] = True
                    if st_.get("rocket_touched") and cl > BH(pb_) and cl > 0:
                        if rocket_n >= bot.ROCKET_DAILY_CAP:
                            st_["rocket_fired"] = True
                            rej.append((d, t, "rocket_capped", minute))
                        else:
                            st_["rocket_fired"] = True
                            if CAP_MODE == "burn":
                                rocket_n += 1
                            cand = ("rocket_catcher", price, st_.get("rocket_plow") or price * 0.75, {})

            # 3m aggregates (multi-day, like live full_bars)
            rth_all = prior + today[:i + 1]
            comp3 = bot.aggregate_bars(rth_all, bot.SETUP_TF_MIN)[:-1]
            warm = len(comp3) >= bot.EMA20_PERIOD + 2
            ema9 = bot.calculate_ema9(comp3) if warm else 0.0
            ema20 = bot.calculate_ema20(comp3) if warm else 0.0
            ema90 = bot.calculate_ema90(comp3) if warm else 0.0

            # -- flat top (pullback state machine, wick-aware #73) --
            if cand is None and warm:
                sess3 = [b for b in comp3 if str(b.get("time", ""))[:10] == d]
                if len(sess3) >= bot.FLAT_TOP_WINDOW:
                    w = sess3[-bot.FLAT_TOP_WINDOW:]
                    highs = [BH(b) for b in w if BH(b) > 0]; lows = [BL(b) for b in w if BL(b) > 0]
                    if highs and lows:
                        wh, wl = max(highs), min(lows)
                        rng = (wh - wl) / wl if wl > 0 else 9
                        is_flat = rng <= bot.FLAT_TOP_MAX_RANGE
                        pb = st_.get("pb")
                        if is_flat and price > wh and not pb:
                            st_["pb"] = {"level": wh, "zone": wl, "m": minute, "dipped": False}
                        elif pb:
                            if minute - pb["m"] > bot.PULLBACK_TIMEOUT_SECS / 60:
                                st_["pb"] = None
                            else:
                                if price <= pb["level"] * (1 + bot.PULLBACK_TOL) or bot._recent_low_dip(today[:i + 1], pb["level"]):
                                    pb["dipped"] = True
                                if pb["dipped"] and price > pb["level"] and confirm_reclaim(today, i, pb["level"]):
                                    if vwap > 0 and price > vwap:
                                        zst = max(round(pb["zone"] * (1 - bot.ZONE_STOP_BUFFER), 4),
                                                  round(price * (1 - bot.STOP_LOSS_PCT), 4))
                                        cand = ("flat_top", price, zst, {})
                                        st_["pb"] = None

            # -- orb (once, pullback state machine, wick-aware #73) --
            if cand is None and vwap > 0 and price > vwap and minute >= 815 and not st_.get("orb_fired"):   # 9:35 ET = 13:35 UTC
                if "orb" not in st_:
                    st_["orb"] = bot.opening_range(today[:i + 1])
                orb = st_["orb"]
                if orb:
                    ohi, olo = orb
                    po = st_.get("pb_orb")
                    if price > ohi and not po:
                        st_["pb_orb"] = {"level": ohi, "zone": olo, "m": minute, "dipped": False}
                    elif po:
                        if minute - po["m"] > bot.PULLBACK_TIMEOUT_SECS / 60:
                            st_["pb_orb"] = None
                        else:
                            if price <= po["level"] * (1 + bot.PULLBACK_TOL) or bot._recent_low_dip(today[:i + 1], po["level"]):
                                po["dipped"] = True
                            if po["dipped"] and price > po["level"] and confirm_reclaim(today, i, po["level"]):
                                ost = max(round(olo * (1 - bot.ZONE_STOP_BUFFER), 4),
                                          round(price * (1 - bot.STOP_LOSS_PCT), 4))
                                cand = ("orb", price, ost, {})
                                st_["orb_fired"] = True; st_["pb_orb"] = None

            # -- ma pullback --
            if cand is None and warm and vwap > 0 and price > vwap:
                mp = None
                try: mp = bot.detect_ma_pullback(comp3, price)
                except Exception: pass
                if mp and mp["stop"] < price:
                    cand = ("ma_pullback", price, mp["stop"], {})

            if cand is None: continue
            machine, entry, stop, _x = cand
            if t == TRACE: print(f"TRACE {t} {minute//60}:{minute%60:02d} CAND {machine} entry {entry} stop {stop}")

            # ── pipeline gates (live order): vel5 floor → extension → chart gate → sizing → momentum ──
            v5 = None
            if i >= bot.ROCKET_VEL_BARS:
                c0 = BC(today[i - bot.ROCKET_VEL_BARS])
                if c0 > 0: v5 = round((price - c0) / c0 * 100, 2)
            if machine in ("ignition", "flat_top", "ma_pullback", "orb", "ema_bounce") and v5 is not None and v5 < 0:
                rej.append((d, t, f"vel5_reject {machine} {v5:+.1f}", minute)); continue
            if machine != "rocket_catcher" and ema90 > 0 and (entry - ema90) / ema90 > bot.EXTENSION_MAX_PCT:
                rej.append((d, t, f"extension_reject {machine} +{(entry-ema90)/ema90*100:.0f}%", minute)); continue
            cg, cgr = chart_gate(levels, t, entry)
            if cg != "allow":
                rej.append((d, t, f"chart_gate_{cg} {machine} ({cgr})", minute)); continue
            if stop >= entry:
                rej.append((d, t, f"bad_stop {machine}", minute)); continue
            pos_size = min(3000 * bot.MAX_POSITION_SIZE, bot.MAX_TRADE_DOLLARS)
            sh = max(1, min(int(bot.RISK_PER_TRADE / (entry - stop)), int(pos_size / entry)))
            v3 = [BV(b) for b in today[max(0, i - 2):i + 1]]
            vav = sum(v3) / len(v3) if v3 else 0
            if vav > 0: sh = min(sh, max(1, int(vav * bot.MAX_POS_VOL_PCT)))
            reserved = round(sh * entry, 2)
            if RANK_RESERVE and t not in topK and (capital - reserved) < RANK_RESERVE:
                rej.append((d, t, f"rank_reserve_skip {machine} rank>{RANK_TOP} needs {reserved:.0f}", minute)); continue
            if capital < reserved:
                rej.append((d, t, f"no_capital {machine} needs {reserved:.0f}", minute)); continue
            if machine not in ("vwap_reclaim", "bounce", "ignition"):
                ok, why = momentum_ok(today, i)
                if not ok:
                    rej.append((d, t, f"momentum_reject {machine} ({why})", minute)); continue
            capital -= reserved
            Rps = entry - stop
            if machine == "rocket_catcher":
                tiers = [(round(entry * 1.50, 4), 0.33), (round(entry * 2.00, 4), 0.67)]
            else:
                tiers = [(round(entry + rm * Rps, 4), cum) for rm, cum in bot.SCALE_TIERS]
            if machine == "rocket_catcher" and CAP_MODE == "refund":
                rocket_n += 1
            positions[t] = Pos(t, machine, entry, stop, sh, tiers, minute, i, reserved)
            if t == TRACE: print(f"TRACE {t} ENTERED {machine} {sh}sh @{entry} stop {stop} tiers {tiers}")

    # close anything still open at end-of-data
    for t, p in list(positions.items()):
        prior, today, pre, idx = data[t]
        cl = BC(today[-1])
        p.fills.append((p.sh, cl, "eod", 960))
        pnl = sum(q * (px - p.entry) for q, px, *_ in p.fills)
        day_pnl += pnl
        out_rows.append({"day": d, "t": t, "machine": p.machine, "emin": p.emin, "entry": p.entry,
                         "stop": p.stop0, "sh": p.sh0, "fills": p.fills, "pnl": round(pnl, 2),
                         "R": round(pnl / (p.sh0 * (p.entry - p.stop0)), 2) if p.entry > p.stop0 else None})
    return day_pnl

rows, rejects = [], []
totals = {}
for d in ["2026-07-20", "2026-07-21"]:
    levels = (json.load(open(HERE / f"kevlv_{d}.json")).get("levels") or {})
    if CPHI_FIX and d == "2026-07-21" and "CPHI" in levels:
        levels["CPHI"] = dict(levels["CPHI"], **{"break": 1.07, "targets": [1.4, 1.8]})
    totals[d] = run_day(d, levels, rows, rejects)

print("=" * 100)
print("FULL-PANEL AS-DEPLOYED REPLAY (56d585d) — every simulated trade")
print("=" * 100)
for d in ["2026-07-20", "2026-07-21"]:
    dr = [r for r in rows if r["day"] == d]
    print(f"\n───── {d}: {len(dr)} trades, sim P&L {totals[d]:+.2f} ─────")
    for r in sorted(dr, key=lambda x: x["emin"]):
        em = r["emin"] - 240; et = f"{em//60}:{em%60:02d}"
        fl = " | ".join(f"{q}sh@{px:.2f} {why} {(m-240)//60}:{(m-240)%60:02d}" for q, px, why, m in r["fills"])
        print(f"{r['t']:6s} {r['machine']:14s} in {et} @{r['entry']:.2f} stop {r['stop']:.2f} "
              f"{r['sh']}sh → {fl}  P&L {r['pnl']:+.2f}" + (f"  ({r['R']:+.2f}R)" if r["R"] is not None else ""))

print("\n" + "=" * 100)
print("REJECT LOG (why candidate entries died) — grouped")
import collections
cnt = collections.Counter()
for d, t, why, m in rejects: cnt[why.split(" ")[0]] += 1
for k, v in cnt.most_common(): print(f"  {k:22s} {v}")
print("\nNotable rejects on movers (full rows):")
MOVERS = {"ZYBT","GMM","CPHI","DFNS","VIVK","JZXN","IPW","NIPG","BIYA"}
for d, t, why, m in rejects:
    if t in MOVERS: print(f"  {d[5:]} {t:6s} {(m-240)//60}:{(m-240)%60:02d}  {why}")

# actual live comparison
print("\n" + "=" * 100)
for d in ["2026-07-20", "2026-07-21"]:
    j = json.load(open(HERE / f"trades_{d}.json"))
    ts = [t for t in (j if isinstance(j, list) else j.get("trades", [])) if t.get("date") == d]
    pl = sum(float(t.get("pnl") or 0) for t in ts)
    print(f"{d}: SIM {totals[d]:+8.2f} ({len([r for r in rows if r['day']==d])} trades)   vs   "
          f"ACTUAL LIVE {pl:+8.2f} ({len(ts)} trades)")

json.dump([{"d":d,"t":t,"why":w,"m":m} for d,t,w,m in rejects], open("rejects_dump.json","w"))
print("""
APPROXIMATIONS (declared):
- Price = 1m bar closes (live polls ~2s); tier fills at tier price when the bar high reaches it.
- vwap_reclaim/zone_flip machines EXCLUDED (10s stream not in cache; live fired 0 both days pre-#67).
- daily-first veto, spread gate, L2 gate: FAIL-OPEN (no offline data).
- Roster = names with cached recorder bars (>=10 RTH 1m bars) — the recorder's watch, close to live's.
- Capital fixed $3k basis; balance not compounded intraday.
- Failed-breakout + early-VWAP-fade cuts OFF (live: disabled under EXITS_ON_3MIN=True) — faithful.
- Chart-gate levels = the day's REAL posted sheet (same source live used).""")
