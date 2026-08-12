"""v2 (~00:15): v1 REFUTED the refusal-moment spec (early rejects predate the intraday move —
leadership proof can't exist yet; big winners all sat in still-blocked). The SHIPPED mechanism
evaluates every rescan, so v2 tests the STANDING exemption: walk each dg<0 name's tape forward
from first reject; ENTER at the FIRST minute where ALL hold:
  dg(px vs prior close) < 0  AND  px > running session VWAP  AND  px >= 1.15 * session_low
Then the same bracket sim (-6% first-touch = -$12; 35% capture of MFE>=8% to 15:30; <4% = -$6).
Also reports never-qualified names (exemption correctly never fires) and a 1.10 sensitivity.
"""
import json, os, datetime, urllib.request, urllib.parse

DASH = "https://zestful-intuition-production-b16a.up.railway.app"
DAYS = ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11"]
PREV = {"2026-08-05": "2026-08-04", "2026-08-06": "2026-08-05", "2026-08-07": "2026-08-06",
        "2026-08-10": "2026-08-07", "2026-08-11": "2026-08-10"}
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

def prev_close(tk, day):
    j = get(f"https://data.alpaca.markets/v2/stocks/{tk}/bars?timeframe=1Day&feed=sip"
            f"&start={PREV[day]}T00:00:00Z&end={PREV[day]}T23:59:59Z&limit=2&adjustment=raw")
    bs = j.get("bars") or []
    return bs[-1]["c"] if bs else None

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

OFF_LOW = float(os.environ.get("R2G_OFFLOW", "1.15"))
qualified, never = [], []
for (day, tk), r in sorted(firsts.items()):
    try:
        pc = prev_close(tk, day)
        if not pc: continue
        bs = bars_1m(tk, day)
        tm0 = t24(r["time"])
        cumv = cumpv = 0.0; lo = None
        entry = None
        for i, b in enumerate(bs):
            hm = et_hm(b["t"])
            cumv += b["v"]; cumpv += b["c"] * b["v"]
            lo = b["l"] if lo is None else min(lo, b["l"])
            if hm <= tm0 or hm > "15:30":   # trigger can only fire after the first refusal
                continue
            px = b["c"]; vwap = cumpv / (cumv or 1)
            dg = (px / pc - 1) * 100
            if dg < 0 and px > vwap and px >= lo * OFF_LOW:
                entry = (i, hm, px); break
        if not entry:
            never.append((day, tk)); continue
        i0, ehm, px = entry
        stop = px * 0.94; mfe_px = px; kind = "ran"
        for b in bs[i0+1:]:
            hm = et_hm(b["t"])
            if hm > "15:30": break
            if b["l"] <= stop and mfe_px < px * 1.08:
                kind = "stopped"; break
            mfe_px = max(mfe_px, b["h"])
        mfe = (mfe_px / px - 1) * 100
        usd = -12.0 if kind == "stopped" else (200*0.35*mfe/100 if mfe >= 8 else (0.0 if mfe >= 4 else -6.0))
        qualified.append({"day": day, "tk": tk, "t": ehm, "px": round(px,4), "mfe": round(mfe,1),
                          "usd": round(usd,2), "kind": kind})
    except Exception as e:
        print(f"  ERR {day} {tk}: {str(e)[:60]}")

print(f"OFF_LOW={OFF_LOW}: {len(firsts)} dg<0 names -> {len(qualified)} qualified, {len(never)} never fired")
tot = sum(x["usd"] for x in qualified); w = sum(1 for x in qualified if x["usd"] > 0)
st = sum(1 for x in qualified if x["kind"] == "stopped")
for x in sorted(qualified, key=lambda x: -x["usd"]):
    print(f'  {x["day"]} {x["tk"]:6s} entry {x["t"]} @{x["px"]:<8} mfe {x["mfe"]:>6}%  ${x["usd"]:+8.2f}  {x["kind"]}')
print(f"TOTAL: ${tot:+.2f} ({(tot/len(qualified)) if qualified else 0:+.2f}/name) winners {w}/{len(qualified)} stopped {st}")
print("never-qualified:", ", ".join(f"{d[-5:]}:{t}" for d, t in never))
