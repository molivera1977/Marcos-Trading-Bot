"""READER-START COUNTERFACTUAL (8/12 night, Marcos: "run the counterfactual now").
QUESTION: if the reader started ~08:00 (maps for board names by ~08:05) instead of 08:50, what
would the mapless-PRE refusals have become?
HONEST MECHANICS: a map alone converts NOTHING — the conversion also needs cum session dvol
>= $250k and time < 09:25. So per mapless-PRE-refused name-day (era 8/10-8/12):
  counterfactual entry = first 1-min bar T where T >= max(first_refusal, 08:05) AND
  cum dvol(04:00..T) >= 250k AND T < 09:25   (fires recur on these names — every one drew
  repeated mapless rows, so signal availability at T is assumed; stated).
SIM: entry at bar close; -6% first-touch stop (-$12 @ $200 clip); flatten 09:25; 35% capture
of MFE >= 8%; <4% = -$6; 4-8% flat. Same family as prior models — ranking, not promise.
Also reported: refusals where dvol was ALREADY >= 250k at refusal (map was the sole blocker).
"""
import json, os, datetime, urllib.request, urllib.parse

DASH = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-08-10", "2026-08-11", "2026-08-12"]
AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]

def aget(url):
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def bars_1m(tk, day):
    out, tok = [], None
    while True:
        u = (f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&feed=sip"
             f"&start={day}T08:00:00Z&end={day}T13:30:00Z&limit=10000&adjustment=raw")
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

firsts = {}
for day in DAYS:
    rows = json.loads(urllib.request.urlopen(
        f"{DASH}/api/decisions_archive?date={day}&status=mapless_reject&limit=50000",
        timeout=30).read()).get("rows") or []
    for r in rows:
        try: tm = t24(r["time"])
        except Exception: continue
        if tm >= "09:25": continue
        k = (day, r.get("ticker"))
        if k not in firsts:
            firsts[k] = tm
print(f"{len(firsts)} mapless-PRE first-refusals (era {DAYS[0][-5:]}..{DAYS[-1][-5:]})")

res, map_only = [], 0
for (day, tk), tm in sorted(firsts.items()):
    try:
        bs = bars_1m(tk, day)
        cum = 0.0; entry = None; cum_at_refusal = None
        for b in bs:
            hm = et_hm(b["t"])
            cum += (b["c"] or 0) * (b["v"] or 0)
            if hm == tm and cum_at_refusal is None:
                cum_at_refusal = cum
            if entry is None and hm >= max(tm, "08:05") and hm < "09:25" and cum >= 250000:
                entry = (hm, b["c"])
        if cum_at_refusal and cum_at_refusal >= 250000:
            map_only += 1
        if not entry:
            res.append({"day": day, "tk": tk, "tm": tm, "note": "floor never met pre-9:25", "usd": 0.0})
            continue
        ehm, px = entry
        aft = [b for b in bs if ehm < et_hm(b["t"]) < "09:25"]
        stop = px * 0.94; mfe_px = px; kind = "ran"
        for b in aft:
            if b["l"] <= stop and mfe_px < px * 1.08:
                kind = "stopped"; break
            mfe_px = max(mfe_px, b["h"])
        mfe = (mfe_px / px - 1) * 100
        usd = -12.0 if kind == "stopped" else (200*0.35*mfe/100 if mfe >= 8 else (0.0 if mfe >= 4 else -6.0))
        res.append({"day": day, "tk": tk, "tm": tm, "entry": f"{ehm}@{px}", "mfe": round(mfe,1),
                    "usd": round(usd,2), "kind": kind})
    except Exception as e:
        print(f"  ERR {day} {tk}: {str(e)[:50]}")

tot = sum(x["usd"] for x in res)
print(f"map-was-sole-blocker at refusal moment: {map_only}/{len(firsts)}")
for x in sorted(res, key=lambda x: -x["usd"]):
    print(f'  {x["day"][-5:]} {x["tk"]:6s} refused {x["tm"]}  ' +
          (f'cf-entry {x["entry"]} mfe {x["mfe"]}% ${x["usd"]:+.2f} {x["kind"]}' if "entry" in x
           else x["note"]))
print(f"TOTAL modeled: ${tot:+.2f} across {len(res)} name-days "
      f"({sum(1 for x in res if x['usd']>0)} winners, {sum(1 for x in res if x.get('kind')=='stopped')} stopped)")
print("Assumptions: fires recur (all names drew repeated mapless rows); reader-at-8:00 => maps by 08:05;"
      " $200 clip, -6% stop, 35% MFE capture, 09:25 flatten.")
