"""8/12 ~00:05 KILL-TEST (sitting item #2, Marcos: "let's do #2 right now with kill test").
HYPOTHESIS: day-gain floor exemption for RED-TO-GREEN DAY-2 leaders.
TRIGGER (all three, at refusal moment, from tape the gate can see):
  (a) day_gain < 0 (stamped on the reject row)
  (b) price > session VWAP (1-min approx: sum(c*v)/sum(v) from 04:00)
  (c) price >= LOW_PCT off the session low  (intraday leadership bar; sensitivity 10/15/20)
SIM per first-reject with dg<0: entry at reject px, stop -6% FIRST-TOUCH on 1-min bars
(low<=stop before high>=+8% => loser -$12 at $200 clip); else winner = $200 * 35% * MFE(15:30).
Same coarse capture model as the 8/11 regrade for comparability — ranking tool, not a promise.
DISCRIMINATION REQUIREMENT: pass-cohort pays AND fail-cohort stays dead, else NO SHIP.
"""
import json, os, datetime, urllib.request, urllib.parse

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

def et_hm(ts):
    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (dt - datetime.timedelta(hours=4)).strftime("%H:%M")

def t24(t12):
    return datetime.datetime.strptime(t12, "%I:%M:%S %p").strftime("%H:%M")

rows = []
for day in DAYS:
    j = json.loads(urllib.request.urlopen(
        f"{DASH}/api/decisions_archive?date={day}&status=daygain_reject&limit=50000",
        timeout=30).read())
    rows += j.get("rows") or []
firsts = {}
for r in rows:
    k = (r.get("date"), r.get("ticker"))
    if k not in firsts and r.get("day_gain") is not None and float(r["day_gain"]) < 0:
        firsts[k] = r
print(f"{len(firsts)} first-rejects with dg<0 across {len(DAYS)} days")

def sim(bs_after, px):
    stop = px * 0.94
    mfe_px = px
    for b in bs_after:
        hm = et_hm(b["t"])
        if hm > "15:30": break
        if b["l"] <= stop and mfe_px < px * 1.08:
            return -12.0, (mfe_px / px - 1) * 100, "stopped"
        mfe_px = max(mfe_px, b["h"])
    mfe = (mfe_px / px - 1) * 100
    return (200 * 0.35 * mfe / 100 if mfe >= 8 else (0.0 if mfe >= 4 else -6.0)), mfe, "ran"

results = []
for (day, tk), r in sorted(firsts.items()):
    try:
        px = float(r["price"]); tm = t24(r["time"])
        bs = bars_1m(tk, day)
        pre = [b for b in bs if et_hm(b["t"]) <= tm]
        aft = [b for b in bs if et_hm(b["t"]) > tm]
        if not pre or not aft: continue
        vol = sum(b["v"] for b in pre) or 1
        vwap = sum(b["c"] * b["v"] for b in pre) / vol
        lo = min(b["l"] for b in pre)
        off_low = (px / lo - 1) * 100
        usd, mfe, kind = sim(aft, px)
        results.append({"day": day, "tk": tk, "px": px, "dg": float(r["day_gain"]),
                        "above_vwap": px > vwap, "off_low": round(off_low, 1),
                        "usd": round(usd, 2), "mfe": round(mfe, 1), "kind": kind,
                        "machine": r.get("machine")})
    except Exception as e:
        print(f"  ERR {day} {tk}: {str(e)[:60]}")

for LOW_PCT in (10.0, 15.0, 20.0):
    pas = [x for x in results if x["above_vwap"] and x["off_low"] >= LOW_PCT]
    fail = [x for x in results if not (x["above_vwap"] and x["off_low"] >= LOW_PCT)]
    def agg(g):
        if not g: return "n=0"
        s = sum(x["usd"] for x in g); w = sum(1 for x in g if x["usd"] > 0)
        return f"n={len(g)} sum ${s:+.2f} (${s/len(g):+.2f}/name) winners {w}/{len(g)}"
    print(f"\n== LOW_PCT={LOW_PCT:.0f}%: EXEMPTED(pass) {agg(pas)} | STILL-BLOCKED(fail) {agg(fail)}")
    if LOW_PCT == 15.0:
        for x in sorted(pas, key=lambda x: -x["usd"]):
            print(f'   PASS {x["day"]} {x["tk"]:6s} @{x["px"]:<8} dg={x["dg"]:<7} off_low={x["off_low"]:>5}% '
                  f'mfe={x["mfe"]:>6}% ${x["usd"]:+8.2f} {x["kind"]} [{x["machine"]}]')
        for x in sorted(fail, key=lambda x: -x["usd"])[:8]:
            print(f'   fail {x["day"]} {x["tk"]:6s} off_low={x["off_low"]:>5}% above_vwap={x["above_vwap"]} '
                  f'mfe={x["mfe"]:>6}% ${x["usd"]:+8.2f}')
print("\nModel: $200 clip, -6% first-touch stop (-$12), 35% capture of MFE>=8%, <4% = -$6, 4-8% flat.")
