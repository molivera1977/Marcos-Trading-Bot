"""RECLAIM LEG-COST REPLAY (7/28) — does the 3-gate confirmation cost the leg?

Question (Marcos, 7/28): vwap_reclaim trades are INERT — median peak 0.57R vs 1.07R for every
other lane, 26% reach +1R vs 53%, 34% die at the 3:45 flat. Hypothesis under test: the
extend -> retest -> curl sequence fires so late that the bounce is already spent.

METHOD — the bot's OWN detector (kev_reclaim_step) walked over REAL captured 10s bars, IN ORDER
(sim integrity: no lookahead, bars fed one at a time, session VWAP accumulated progressively).
For every fire we measure, from the tape:
  cross_px / cross_t   the seek->extend transition (price crossing the session line on 2x volume)
  fire_px  / fire_t    the curl that actually triggers the entry
  cost_pct             (fire_px - cross_px)/cross_px  -> how much of the move the gates ate
  peak_after_fire      MFE in R from the fire, using the detector's own stop
  peak_after_cross     MFE in R had we entered at the cross with the same stop
The comparison is the point: if entering at the cross captures materially more R than entering
at the fire, the confirmation sequence is the defect. If not, the hypothesis is refuted and the
lane's inertness lives somewhere else.

NOT a recommendation. Entering at the cross is NOT a proposal - the cross has no confirmation
and would fire on every failed poke through the line. This measures the COST of confirmation
only; the count of cross-signals that never reached a fire is reported as the price of removing it.
"""
import json, sys, urllib.request, urllib.parse, statistics as st
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot()

U = "https://zestful-intuition-production-b16a.up.railway.app"
ET = timezone(timedelta(hours=-4))

# Replay must not be suppressed by the live stale-fire guard (it exists to stop REPLAY from
# ACTING; here replay IS the point and nothing trades). Guard has its own suite.
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9


def fetch10s(date, ticker):
    for suf in ("~ALP10S", "~10s"):
        try:
            r = json.load(urllib.request.urlopen(
                f"{U}/api/bars?date={date}&ticker={urllib.parse.quote(ticker + suf)}"))
            b = r.get("bars") or []
            if b:
                return b, suf
        except Exception:
            pass
    return [], None


def norm(bars):
    """-> sorted [(epoch, o, h, l, c, v)] in ET, RTH only (09:30-16:00)."""
    out = []
    for x in bars:
        t = x.get("time") or x.get("t")
        if not t:
            continue
        try:
            dt = datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ET)
        except Exception:
            continue
        hm = dt.strftime("%H:%M")
        if hm < "09:30" or hm >= "16:00":
            continue
        out.append((int(dt.timestamp()), float(x.get("open") or x.get("o")), float(x.get("high") or x.get("h")),
                    float(x.get("low") or x.get("l")), float(x.get("close") or x.get("c")),
                    float(x.get("volume") or x.get("v") or 0), dt))
    return sorted(out)


def replay(sym, bars):
    """Walk bar-by-bar. Returns list of fire dicts with cross context."""
    bot._reclaim_st.pop(sym, None)
    pv = vol = 0.0
    fires, crosses = [], 0
    pending_cross = None          # (px, dt) of the most recent seek->extend transition
    prev_phase = "seek"
    for i, (k, o, h, l, c, v, dt) in enumerate(bars):
        tp = (h + l + c) / 3.0
        pv += tp * v
        vol += v
        vwap = (pv / vol) if vol > 0 else 0.0
        if not vwap:
            continue
        f = bot.kev_reclaim_step(sym, [(k, o, h, l, c, v)], vwap)
        ph = bot._reclaim_st[sym]["phase"]
        if prev_phase == "seek" and ph == "extend":
            pending_cross = (c, dt, i)
            crosses += 1
        prev_phase = ph
        if f:
            fires.append({"fire_px": f["px"], "fire_dt": dt, "fire_i": i, "stop": f["stop"],
                          "seq": f["seq"], "vwap": vwap,
                          "cross_px": pending_cross[0] if pending_cross else None,
                          "cross_dt": pending_cross[1] if pending_cross else None,
                          "cross_i": pending_cross[2] if pending_cross else None})
            pending_cross = None
    return fires, crosses


RISK = float(__import__("os").environ.get("RISK_PER_TRADE", "30"))
NOTIONAL_CAP = 1000.0


def walk(bars, i0, entry, stop):
    """Walk FORWARD bar-by-bar from the entry. The stop is checked on every bar BEFORE the high
    is credited — a stop swept on the way up ends the trade there. Returns (peak_pct, stopped,
    peak_R, bars_held). Without this, 'peak after entry' silently counts moves the trade was
    never alive for (sim integrity: bars walked in order, no lookahead)."""
    r = entry - stop
    if r <= 0:
        return None
    peak = entry
    for b in bars[i0 + 1:]:
        if b[3] <= stop:                       # low took the stop out -> dead here
            return ((peak - entry) / entry * 100, True, (peak - entry) / r, bars.index(b) - i0)
        peak = max(peak, b[2])
    return ((peak - entry) / entry * 100, False, (peak - entry) / r, len(bars) - i0)


def dollars(entry, stop, peak_pct):
    """Peak $ through the REAL sizing chain: shares = RISK/risk_per_share, capped at $1k notional.
    R alone is fiction here — a tighter entry inflates R and the notional cap eats the benefit."""
    rps = entry - stop
    if rps <= 0:
        return None, None
    sh = int(min(RISK / rps, NOTIONAL_CAP / entry))
    return sh, sh * entry * (peak_pct / 100.0)


NAMES = [("2026-07-27", t) for t in ("BIYA", "LGHL", "VEEE", "JZXN", "KIDZ", "MTNB")]

print("RECLAIM LEG-COST REPLAY — bot's own detector over real 10s tape, bars walked in order")
print("=" * 108)
rows, tot_cross = [], 0
for date, tk in NAMES:
    raw, suf = fetch10s(date, tk)
    bars = norm(raw)
    if len(bars) < 60:
        print(f"{tk}: insufficient RTH 10s bars ({len(bars)}) — SKIPPED")
        continue
    fires, crosses = replay(tk, bars)
    tot_cross += crosses
    print(f"\n{tk} {date}  [{suf}] {len(bars)} RTH 10s bars   VWAP crosses: {crosses}   fires: {len(fires)}")
    if not fires:
        print("   no fire — every cross died before the curl")
        continue
    print(f"   {'seq':>3} {'cross':>8} {'fire':>8} {'gap':>6} {'cost%':>7} │"
          f" {'FIRE: pk%':>10} {'stpd':>5} {'pk$':>8} │ {'CROSS: pk%':>11} {'stpd':>5} {'pk$':>8}")
    for f in fires:
        if f["cross_px"] is None:
            continue
        gap = (f["fire_dt"] - f["cross_dt"]).total_seconds()
        cost = (f["fire_px"] - f["cross_px"]) / f["cross_px"] * 100
        wf = walk(bars, f["fire_i"], f["fire_px"], f["stop"])
        # the cross entry gets the SAME structural stop; its risk-per-share is smaller, so R is
        # not comparable — dollars through the sizing chain are.
        wc = walk(bars, f["cross_i"], f["cross_px"], f["stop"])
        if not wf or not wc:
            continue
        shf, df = dollars(f["fire_px"], f["stop"], wf[0])
        shc, dc = dollars(f["cross_px"], f["stop"], wc[0])
        print(f"   {f['seq']:>3} {f['cross_px']:8.4f} {f['fire_px']:8.4f} {gap:5.0f}s {cost:6.2f}% │"
              f" {wf[0]:9.2f}% {('YES' if wf[1] else '-'):>5} {df:8.2f} │"
              f" {wc[0]:10.2f}% {('YES' if wc[1] else '-'):>5} {dc:8.2f}")
        rows.append({"tk": tk, "seq": f["seq"], "gap_s": gap, "cost_pct": cost,
                     "fire_pk_pct": wf[0], "fire_stopped": wf[1], "fire_pk_$": df, "fire_sh": shf,
                     "cross_pk_pct": wc[0], "cross_stopped": wc[1], "cross_pk_$": dc, "cross_sh": shc,
                     "cross": f["cross_px"], "fire": f["fire_px"], "stop": f["stop"]})

print("\n" + "=" * 108)
if not rows:
    print("NO FIRES — nothing to conclude."); sys.exit(0)
print(f"fires with cross context: {len(rows)}   (day-first, seq=0: {sum(1 for r in rows if r['seq'] == 0)})")
print(f"total VWAP crosses across names: {tot_cross}  ->  fires: {len(rows)}"
      f"   ({len(rows)/tot_cross*100:.0f}% of crosses ever reach a curl)")
print(f"\nconfirmation gap   median {st.median([r['gap_s'] for r in rows]):6.0f}s"
      f"   range {min(r['gap_s'] for r in rows):.0f}-{max(r['gap_s'] for r in rows):.0f}s")
print(f"price given up     median {st.median([r['cost_pct'] for r in rows]):6.2f}%"
      f"   range {min(r['cost_pct'] for r in rows):.2f}-{max(r['cost_pct'] for r in rows):.2f}%")
print(f"\n{'':18}{'FIRE (as built)':>18}{'CROSS (no confirm)':>20}")
print(f"  median peak %   {st.median([r['fire_pk_pct'] for r in rows]):17.2f}%"
      f"{st.median([r['cross_pk_pct'] for r in rows]):19.2f}%")
print(f"  median peak $   {st.median([r['fire_pk_$'] for r in rows]):17.2f}"
      f"{st.median([r['cross_pk_$'] for r in rows]):20.2f}")
print(f"  total peak $    {sum(r['fire_pk_$'] for r in rows):17.2f}"
      f"{sum(r['cross_pk_$'] for r in rows):20.2f}")
print(f"  stopped out     {sum(1 for r in rows if r['fire_stopped']):13}/{len(rows)}"
      f"{sum(1 for r in rows if r['cross_stopped']):17}/{len(rows)}")
print(f"  median shares   {st.median([r['fire_sh'] for r in rows]):17.0f}"
      f"{st.median([r['cross_sh'] for r in rows]):20.0f}   <- notional cap binds the tighter entry")
better = sum(1 for r in rows if r["cross_pk_$"] > r["fire_pk_$"])
print(f"\ncross beat fire in DOLLARS on {better}/{len(rows)} fires")
print("\nCOST OF REMOVING CONFIRMATION (the other side of the ledger):")
print(f"  {tot_cross} VWAP crosses produced only {len(rows)} curls — entering at EVERY cross means"
      f" {tot_cross - len(rows)} extra entries")
print("  those non-firing crosses are UNMEASURED here (no stop is defined without a curl wick).")
print("  -> this replay measures ONLY what confirmation costs on the fires it produced.")
print("     It does NOT show cross-entry is profitable. That needs the failed crosses priced.")
json.dump(rows, open("/tmp/reclaim_leg_cost.json", "w"), default=str)
print("\nrows -> /tmp/reclaim_leg_cost.json")
