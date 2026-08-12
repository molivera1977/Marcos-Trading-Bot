"""CAP COST KILL-TEST (8/12 evening; Marcos: "we might need to up the limit of 6").
Both binding caps, era 8/5-8/12:
  A) hidden_capped rows (hidden lane per-session cap, non-crowned names)
  B) shadow rows carrying _pm_why/premkt reasons == premkt_capped (the PRE 6-cap — CORRECTION:
     it DID fire, 8/12 09:23 OFAL #7; my 8/12-morning "never fired" claim was wrong)
SIM per refusal (first per ticker-day-cap): entry at refusal price; -6% first-touch stop (-$12
at $200 clip); else 35% capture of MFE. PRE-time refusals flatten at 09:25 (the window's own
law); RTH refusals run to 15:30. Same coarse model as prior re-grades — ranking, not promise.
"""
import json, os, datetime, urllib.request, urllib.parse

DASH = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11", "2026-08-12"]
AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]

def aget(url):
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def bars_1m(tk, day):
    out, tok = [], None
    while True:
        u = (f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&feed=sip"
             f"&start={day}T08:00:00Z&end={day}T20:00:00Z&limit=10000&adjustment=raw")
        if tok: u += "&page_token=" + urllib.parse.quote(tok)
        j = aget(u); out += j.get("bars") or []
        tok = j.get("next_page_token")
        if not tok: break
    return out

def et_hm(tstr):
    dt = datetime.datetime.fromisoformat(tstr.replace("Z", "+00:00"))
    return (dt - datetime.timedelta(hours=4)).strftime("%H:%M")

def t24(t12):
    return datetime.datetime.strptime(t12, "%I:%M:%S %p").strftime("%H:%M")

refusals = []
for day in DAYS:
    rows = json.loads(urllib.request.urlopen(
        f"{DASH}/api/decisions_archive?date={day}&limit=50000", timeout=30).read()).get("rows") or []
    for r in rows:
        st = r.get("status") or ""
        why = str(r.get("_pm_why") or r.get("pm_why") or "")
        if st == "hidden_capped":
            refusals.append((day, r.get("ticker"), t24(r["time"]), float(r.get("price") or 0), "hidden_cap"))
        elif "shadow" in st and why == "premkt_capped":
            refusals.append((day, r.get("ticker"), t24(r["time"]), float(r.get("price") or 0), "pre6_cap"))
        elif st == "premkt_capped":
            refusals.append((day, r.get("ticker"), t24(r["time"]), float(r.get("price") or 0), "pre6_cap"))

firsts = {}
for day, tk, tm, px, kind in refusals:
    k = (day, tk, kind)
    if k not in firsts and px > 0:
        firsts[k] = (tm, px)
print(f"{len(refusals)} refusal rows -> {len(firsts)} first-refusals")

res = {"hidden_cap": [], "pre6_cap": []}
for (day, tk, kind), (tm, px) in sorted(firsts.items()):
    try:
        bs = bars_1m(tk, day)
        end = "09:25" if tm < "09:25" else "15:30"
        aft = [b for b in bs if tm < et_hm(b["t"]) <= end]
        if not aft: continue
        stop = px * 0.94; mfe_px = px; kind2 = "ran"
        for b in aft:
            if b["l"] <= stop and mfe_px < px * 1.08:
                kind2 = "stopped"; break
            mfe_px = max(mfe_px, b["h"])
        mfe = (mfe_px / px - 1) * 100
        usd = -12.0 if kind2 == "stopped" else (200*0.35*mfe/100 if mfe >= 8 else (0.0 if mfe >= 4 else -6.0))
        res[kind].append({"day": day, "tk": tk, "tm": tm, "px": px, "mfe": round(mfe,1),
                          "usd": round(usd,2), "k": kind2, "end": end})
    except Exception as e:
        print(f"  ERR {day} {tk}: {str(e)[:50]}")

for kind, rs in res.items():
    tot = sum(x["usd"] for x in rs); w = sum(1 for x in rs if x["usd"] > 0)
    print(f"\n== {kind}: n={len(rs)} modeled ${tot:+.2f} winners {w} stopped {sum(1 for x in rs if x['k']=='stopped')}")
    for x in sorted(rs, key=lambda x: -x["usd"]):
        print(f'   {x["day"][-5:]} {x["tk"]:6s} @{x["px"]:<8} {x["tm"]} (to {x["end"]}) mfe {x["mfe"]:>6}% ${x["usd"]:+8.2f} {x["k"]}')
print("\nModel: $200 clip, -6% first-touch stop, 35% capture of MFE>=8%, PRE refusals flatten 09:25.")
