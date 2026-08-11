"""PRE-SCALE STOP KILL TEST (registered 8/5 night, rules frozen pre-run; Marcos: "run the
kill test now"). QUESTION: on hidden_entry trades, the live stop trails the latest 10s
scale-bar low from entry (ratchet-up, touch exit) — that shook the bot out of INLF/YXT in
7-81s today before monster legs. Candidate: HOLD THE PLANNED STOP static until the +1R half
books; post-scale identical in both arms (BE + rolling prev-minute-low touch trail) so the
ONLY variable is the pre-scale stop.
ARMS: A = live (scale-bar trail pre-scale) | B_all = planned-stop-held, all hidden trades |
B_crown = planned-stop-held only when day_gain_at_entry >= 40 (crown proxy; violence test
not replayed — CAVEAT), others behave as A.
COHORT: every closed hidden_entry trade since lane went live 7/24 with 10s coverage.
Entry/shares real from records; planned stop = entry - risk_per_share.
COST STRUCTURE NAMED FIRST: B converts small shakeout losses into potential FULL planned-stop
losses; it wins only if the monsters it stays in outweigh the deeper stops.
FROZEN VERDICT: an arm is ship-candidate iff it beats A by >= $75 total AND wins/ties on
>= 60% of trades AND worst single-trade degradation vs A <= $35 (one full band-priced stop).
Else -> Friday table. WRONG-WHEN: B is wrong if hidden names routinely flush through the
full planned stop before running (then A's fast exit is protection, not shakeout).
"""
import json, urllib.request, urllib.parse, datetime, pathlib
U = "https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u, timeout=60))
_b = {}
def bars10(tk, d):
    if (tk,d) in _b: return _b[(tk,d)]
    try:
        r = get(f"{U}/api/bars?date={d}&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    except Exception:
        r = []
    out = []
    for x in r:
        try:
            ts = str(x.get("time"))[11:19]
            sec = int(ts[:2])*3600 + int(ts[3:5])*60 + int(ts[6:8])
            out.append((sec, float(x.get("high") or 0), float(x.get("low") or 0), float(x.get("close") or 0)))
        except Exception: continue
    _b[(tk,d)] = out
    return out
def sim(B, i0, e, s_planned, prescale):  # prescale: "trail" (A) or "hold" (B)
    pnl=0.0; rem=1.0; sc=False; stop=s_planned; lows=[]
    for j in range(i0, len(B)):
        sec,h,l,c = B[j]
        if not sc:
            if h >= e + (e - s_planned):
                pnl += 0.5*(e - s_planned); rem=0.5; sc=True; stop=e; continue
            if l <= stop:
                return pnl + rem*(max(stop,l) - e)
            if prescale == "trail" and j > i0:
                stop = max(stop, B[j-1][2])   # ratchet to prior completed 10s bar low
        else:
            lows.append(l)
            if len(lows) > 6: lows.pop(0)
            if len(lows) == 6: stop = max(stop, min(lows))
            if l <= stop:
                return pnl + rem*(max(stop,l) - e)
    return pnl + (rem*(B[-1][3] - e) if B else 0)
trades = [t for t in get(U+"/api/trades")["trades"]
          if t.get("entry_type") == "hidden_entry" and str(t.get("date") or "") >= "2026-07-24"
          and t.get("entry_ts_utc")]
rows=[]
for t in trades:
    d=t["date"]; tk=t["ticker"]
    e=float(t.get("entry") or 0); rps=float(t.get("risk_per_share") or 0); sh=int(t.get("shares") or 0)
    if not (e>0 and rps>0 and sh>0): continue
    s=e-rps
    dt_=datetime.datetime.fromisoformat(str(t["entry_ts_utc"]).replace("Z","+00:00"))
    esec=dt_.hour*3600+dt_.minute*60+dt_.second
    B=bars10(tk,d)
    i0=next((j for j,x in enumerate(B) if x[0]>=esec), None)
    if i0 is None or len(B)<30: continue
    crown = float(t.get("day_gain_at_entry") or 0) >= 40
    a=round(sim(B,i0,e,s,"trail")*sh,2); b=round(sim(B,i0,e,s,"hold")*sh,2)
    rows.append({"d":d,"tk":tk,"t":(dt_-datetime.timedelta(hours=4)).strftime("%H:%M"),
                 "crown":crown,"actual":float(t.get("pnl") or 0),"A":a,"B":b,
                 "Bc": b if crown else a})
print(f"hidden trades replayed: {len(rows)}  (crowned: {sum(1 for x in rows if x['crown'])})\n")
print(f"{'when':<18}{'crown':<6}{'actual':>9}{'A_trail':>9}{'B_hold':>9}{'B_crown':>9}")
for x in sorted(rows,key=lambda z:(z["d"],z["t"])):
    print(f"{x['d'][5:]} {x['t']} {x['tk']:<6}{'👑' if x['crown'] else '':<5}{x['actual']:>+9.2f}{x['A']:>+9.2f}{x['B']:>+9.2f}{x['Bc']:>+9.2f}")
tot={k:sum(x[k] for x in rows) for k in ("A","B","Bc")}
print(f"\nTOTALS: A ${tot['A']:+.2f}  B_all ${tot['B']:+.2f}  B_crown ${tot['Bc']:+.2f}")
for k,nm in (("B","B_all"),("Bc","B_crown")):
    wins=sum(1 for x in rows if x[k] >= x["A"]-0.01)
    worst=max((x["A"]-x[k] for x in rows), default=0)
    ok=(tot[k]-tot["A"])>=75 and rows and wins/len(rows)>=0.6 and worst<=35
    print(f"  {nm}: delta ${tot[k]-tot['A']:+.2f}  wins/ties {wins}/{len(rows)}  worst-degradation ${worst:.2f}  {'SHIP-CANDIDATE' if ok else 'NOT MET'}")
json.dump(rows, open(pathlib.Path(__file__).with_name("prescale_stop_rows_20260805.json"),"w"), indent=1)
