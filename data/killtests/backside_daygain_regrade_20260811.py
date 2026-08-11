"""8/11 RE-GRADES (Marcos: "run replays") — two blocking gates vs the era tape.

A) backside_reject (live 8/5): H = the gate's premise EXPIRES when price later RECLAIMS the
   reference high (high implied from the row's own dd_pct stamp). Split refused pile by
   reclaimed-vs-not; price both in offered % and $ at clip.
B) daygain_reject: H = the floor refuses pre-proof leaders (morning-snapshot bias); grade the
   refused pile's post-reject offers. Board-membership split NOT computable historically
   (no dated board archive) — stated limitation, composition judged by eye at the sitting.

Method: per ticker-day, FIRST reject row only (spam rows counted separately). Tape = Alpaca
1-min SIP (law: feed=sip, complete any-day tape). Offered = max high after reject time, rest of
session incl. AH to 20:00 (entries realistically end 15:30 -> also report 15:30-capped offer).
$ frame assumptions (stated, not hidden): $200 clip, 35% capture of offered move on names
offering >= +8%; names offering < +4% modeled as -3% scratch/stop; 4-8% = flat. This is a
COARSE counterfactual for ranking gates, not a P&L promise.
"""
import json, os, sys, datetime, urllib.request, urllib.parse

DASH = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11"]
AK, AS_ = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]

def get(url):
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": AK, "APCA-API-SECRET-KEY": AS_})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def bars_1m(tk, day):
    out, tok = [], None
    while True:
        u = (f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Min&feed=sip"
             f"&start={day}T08:00:00Z&end={day}T23:59:00Z&limit=10000&adjustment=raw")
        if tok: u += "&page_token=" + urllib.parse.quote(tok)
        j = get(u); out += j.get("bars") or []
        tok = j.get("next_page_token")
        if not tok: break
    return out

def et_hm(ts):  # RFC3339 Z -> ET HH:MM
    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (dt - datetime.timedelta(hours=4)).strftime("%H:%M")

def t24(t12):   # "10:04:30 AM" -> "10:04"
    dt = datetime.datetime.strptime(t12, "%I:%M:%S %p")
    return dt.strftime("%H:%M")

def model_dollars(off_pct):
    if off_pct >= 8:  return 200 * 0.35 * off_pct / 100
    if off_pct >= 4:  return 0.0
    return -6.0   # $200 * -3%

rows_all = {"backside_reject": [], "daygain_reject": []}
for day in DAYS:
    j = json.loads(urllib.request.urlopen(
        f"{DASH}/api/decisions_archive?date={day}&status=backside_reject,daygain_reject&limit=50000",
        timeout=30).read())
    for r in j.get("rows") or []:
        if r.get("status") in rows_all: rows_all[r["status"]].append(r)

for gate, rows in rows_all.items():
    firsts, spam = {}, 0
    for r in rows:
        k = (r.get("date"), r.get("ticker"))
        if k in firsts: spam += 1
        else: firsts[k] = r
    print(f"\n===== {gate}: {len(rows)} rows -> {len(firsts)} first-rejects ({spam} repeats) =====")
    res = []
    for (day, tk), r in sorted(firsts.items()):
        try:
            px = float(r.get("price") or 0)
            if px <= 0: continue
            bs = bars_1m(tk, day)
            after = [b for b in bs if et_hm(b["t"]) >= t24(r["time"])]
            cap = [b for b in after if et_hm(b["t"]) <= "15:30"]
            if not after: continue
            hi_all = max(b["h"] for b in after)
            hi_cap = max((b["h"] for b in cap), default=px)
            off = (hi_cap / px - 1) * 100
            rec = None
            if gate == "backside_reject" and r.get("dd_pct"):
                ref_hi = px / (1 - float(r["dd_pct"]) / 100.0)
                rec = hi_all > ref_hi
            res.append({"day": day, "tk": tk, "px": px, "off_1530": round(off, 1),
                        "off_eod": round((hi_all / px - 1) * 100, 1), "reclaimed": rec,
                        "dg": r.get("day_gain"), "machine": r.get("machine"),
                        "usd": round(model_dollars(off), 2)})
        except Exception as e:
            print(f"  ERR {day} {tk}: {str(e)[:60]}")
    res.sort(key=lambda x: -x["off_1530"])
    for x in res:
        print(f'  {x["day"]} {x["tk"]:6s} @{x["px"]:<8} off(15:30) {x["off_1530"]:+6.1f}%  '
              f'eod {x["off_eod"]:+6.1f}%  ${x["usd"]:+7.2f}'
              + (f'  reclaimed={x["reclaimed"]}' if x["reclaimed"] is not None else '')
              + (f'  dg={x["dg"]}' if x.get("dg") is not None else '') + f'  [{x["machine"]}]')
    n = len(res); tot = round(sum(x["usd"] for x in res), 2)
    big = [x for x in res if x["off_1530"] >= 8]
    print(f"  TOTAL modeled: {n} first-rejects, sum ${tot:+.2f}, offers>=8%: {len(big)}/{n}")
    if gate == "backside_reject":
        for flag in (True, False):
            grp = [x for x in res if x["reclaimed"] is flag]
            if grp:
                print(f"  reclaimed={flag}: n={len(grp)} sum ${sum(x['usd'] for x in grp):+.2f} "
                      f"median offer {sorted(x['off_1530'] for x in grp)[len(grp)//2]:+.1f}%")
print("\nAssumptions: $200 clip, 35% capture of >=8% offers, <4% offers = -$6 stop, 4-8% flat. "
      "Daygain board-split NOT computable historically (no dated board archive) — limitation.")
