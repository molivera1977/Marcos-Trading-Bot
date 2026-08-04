"""VERIFICATION RERUN — zone reclassification on FULL SIP tape (8/3 ~01:00, Marcos: "rerun the
test to verify"). Independent re-execution of the corrected dead-zone classification, persisted
with a full per-trade audit trail so the verdict is hand-checkable, plus one named end-to-end
trace (dollars law): MGRX 7/31 premarket.

Zone rule (same as live gate): entry below the sheet break -> "pre_break" if the SIP day-high
BEFORE entry never touched the break, else "retest". Day-high window starts 04:00 ET.
"""
import json, urllib.request, datetime, time, pathlib, collections

V = json.load(open("/tmp/rv7.json"))
HDR = {"APCA-API-KEY-ID": V["ALPACA_KEY"], "APCA-API-SECRET-KEY": V["ALPACA_SECRET"]}
U = "https://zestful-intuition-production-b16a.up.railway.app"
CHART = {"flat_top", "ma_pullback", "orb", "ema_bounce", "dip_rip"}
DAYS = ["2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03"]

def sip_hi_before(day, tk, endhm):
    url = (f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&start={day}T04:00:00-04:00"
           f"&end={day}T{endhm}:00-04:00&limit=1000&feed=sip")
    try:
        rows = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30)).get("bars") or []
    except Exception:
        return None, 0
    time.sleep(0.3)
    if not rows: return None, 0
    return max(float(r["h"]) for r in rows), len(rows)

levels = {d: (json.load(urllib.request.urlopen(f"{U}/api/kev_watchlist?date={d}", timeout=30)).get("levels") or {}) for d in DAYS}
trades = [t for t in json.load(urllib.request.urlopen(f"{U}/api/trades", timeout=60))["trades"] if t.get("date") in DAYS]

audit = []
for t in trades:
    rec = levels[t["date"]].get(t["ticker"]) or {}
    try: B = float(rec.get("break") or 0)
    except Exception: B = 0.0
    e = float(t.get("entry") or 0)
    if B <= 0 or e <= 0 or e >= B: continue
    try:
        dt_ = datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z", "+00:00"))
        hm = (dt_ - datetime.timedelta(hours=4)).strftime("%H:%M")
    except Exception: continue
    hb, nb = sip_hi_before(t["date"], t["ticker"], hm)
    if hb is None:
        audit.append({"d": t["date"], "tk": t["ticker"], "lane": t.get("entry_type"), "hm": hm,
                      "e": e, "B": B, "dayhi": None, "nbars": 0, "zone": "UNCLASSIFIABLE",
                      "pnl": float(t.get("pnl") or 0)})
        continue
    zone = "retest" if hb >= B else "pre_break"
    grp = "chart" if t.get("entry_type") in CHART else ("ignition" if t.get("entry_type") == "ignition" else "tape")
    audit.append({"d": t["date"], "tk": t["ticker"], "lane": t.get("entry_type"), "grp": grp,
                  "hm": hm, "e": e, "B": B, "dayhi": round(hb, 4), "nbars": nb, "zone": zone,
                  "pnl": float(t.get("pnl") or 0)})

print(f"below-break trades: {len(audit)}  (unclassifiable: {sum(1 for a in audit if a['zone']=='UNCLASSIFIABLE')})\n")
print("== FULL AUDIT (every below-break trade) ==")
for a in sorted(audit, key=lambda x: (x["d"], x["hm"])):
    print(f"  {a['d']} {a['hm']} {a['tk']:<6} {a['lane']:<13} entry={a['e']:<8.4g} break={a['B']:<8.4g} "
          f"dayhi_before={a['dayhi'] if a['dayhi'] is not None else '—':<9} bars={a['nbars']:<4} "
          f"{a['zone']:<10} ${a['pnl']:>+8.2f}")

def agg(g, lab):
    n = len(g)
    if not n: print(f"  {lab:<26} n=0"); return
    p = sum(x["pnl"] for x in g); w = sum(1 for x in g if x["pnl"] > 0)
    print(f"  {lab:<26} n={n:>2}  ${p:>8.2f}  mean ${p/n:>7.2f}  win {100*w/n:.0f}%")

print("\n== VERDICT TABLE ==")
for grp in ("tape", "ignition", "chart"):
    for z in ("pre_break", "retest"):
        agg([a for a in audit if a.get("grp") == grp and a["zone"] == z], f"{grp} {z}")
agg([a for a in audit if a["zone"] == "pre_break"], "ALL pre_break")
agg([a for a in audit if a["zone"] == "retest"], "ALL retest")

print("\n== NAMED TRACE (dollars law): MGRX 2026-07-31 premarket ==")
for a in audit:
    if a["tk"] == "MGRX" and a["d"] == "2026-07-31":
        blocked = a["zone"] == "pre_break" and a.get("grp") == "tape"
        print(f"  entry {a['hm']} ET at ${a['e']} | sheet break ${a['B']} | SIP day-high before entry "
              f"${a['dayhi']} ({a['nbars']} bars from 04:00) -> {a['zone'].upper()}")
        print(f"  live gate (TAPE_PREBREAK) would block: {blocked} | actual result ${a['pnl']:+.2f}")
json.dump(audit, open(pathlib.Path(__file__).with_name("zone_reclass_audit_20260803.json"), "w"), indent=1)
print("\naudit rows -> zone_reclass_audit_20260803.json")
