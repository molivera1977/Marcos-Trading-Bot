"""Move-quality metrics -> CSV (Saturday prep, Opus 7/15). STEP 2: compute + write.
Mechanical only. NO conclusions — Sunday's Fable session judges the table.
Anchors every metric at the fill; same-day bar filter (multi-day trap); AM/PM-safe."""
import json, urllib.request, pathlib, statistics as st, csv
from datetime import datetime

BASE="https://zestful-intuition-production-b16a.up.railway.app"
IC=pathlib.Path("/Users/marcosolivera/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/bars_1min")
OUT=pathlib.Path("/Users/marcosolivera/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/warehouse/movequal/movequal_20260715.csv")
def get(u): return json.load(urllib.request.urlopen(BASE+u,timeout=30))
DAYS=("2026-07-13","2026-07-14","2026-07-15")
# contamination ledger (7/15 bug-decided outcomes) — flag, don't drop
CONTAM={("2026-07-15","XCUR"),("2026-07-15","UBXG"),("2026-07-15","VTAK"),("2026-07-15","VMAR")}

def et_secs_clock(t):           # "10:59:06 AM" -> ET seconds-of-day
    dt=datetime.strptime(t.strip(),"%I:%M:%S %p"); return dt.hour*3600+dt.minute*60+dt.second
def et_secs_bar(b):             # ISO-UTC bar -> ET seconds-of-day
    t=str(b.get("time","")); return ((int(t[11:13])-4)%24)*3600+int(t[14:16])*60+int(t[17:19]), t[:10]
def fv(b,k): return float(b.get(k) or b.get(k[0]) or 0)

def load_1min(d,tk):
    if d=="2026-07-15":
        try:
            j=get(f"/api/bars?date={d}&ticker={tk}"); bs=j.get("bars",j) if isinstance(j,dict) else j
        except Exception: bs=None
    else:
        p=IC/f"{d}_{tk}__ext.json"; p=p if p.exists() else IC/f"{d}_{tk}.json"
        if not p.exists(): return None
        j=json.load(open(p)); bs=j.get("bars",j) if isinstance(j,dict) else j
    if not isinstance(bs,list): return None
    out=[]
    for b in bs:
        s,day=et_secs_bar(b)
        if day==d: out.append((s,fv(b,"open"),fv(b,"high"),fv(b,"low"),fv(b,"close"),fv(b,"volume")))
    return sorted(out) or None

def load_10s(d,tk):
    if d!="2026-07-15": return None
    try:
        j=get(f"/api/bars?date={d}&ticker={tk}~10s"); bs=j.get("bars",j) if isinstance(j,dict) else j
    except Exception: return None
    if not isinstance(bs,list) or not bs: return None
    out=[]
    for b in bs:
        s,day=et_secs_bar(b)
        if day==d: out.append((s,fv(b,"open"),fv(b,"high"),fv(b,"low"),fv(b,"close"),fv(b,"volume")))
    return sorted(out) or None

# ---- entries + distinct-fill assignment ----
trades=[t for t in get("/api/trades").get("trades",[]) if t.get("date") in DAYS and t.get("planned_risk")]
fills={}
for d in DAYS:
    for r in get(f"/api/decisions_archive?date={d}&status=filled&limit=1000").get("rows",[]):
        if r.get("price"): fills.setdefault((d,r.get("ticker")),[]).append([et_secs_clock(r["time"]),float(r["price"]),False])
def assign_fill(d,tk,e):
    fl=fills.get((d,tk),[])
    best=None;bd=1e9
    for f in fl:
        if f[2]: continue
        pd=abs(f[1]-e)
        if pd<bd and pd/e<0.03: bd=pd;best=f
    if best: best[2]=True; return best[0]
    return None

def window(bars,lo,hi):   return [b for b in bars if lo<=b[0]<hi]
def m1(bars,fs):
    # minute containing fill = [floor-min, +60); prior 5 min; next 1-2 min
    m0=(fs//60)*60
    trig=window(bars,m0,m0+60); prior=window(bars,m0-300,m0)
    nxt1=window(bars,m0+60,m0+120); nxt2=window(bars,m0+60,m0+180)
    pre =window(bars,m0-180,m0)
    thin=False
    if not trig:                      # illiquid: no bar in the fill minute — widen +-2min, FLAG (a hollow-tape signal)
        trig=window(bars,m0-120,m0+120); thin=True
        if not trig: return {"thin_tape":True,"abs_vol_trig":0,"abs_dollar_trig":0,"vol_ratio":"","ft1_pct":"","ft2_pct":"","pre_run_pct":"","prior_close_pos":""}
    absv=sum(b[5] for b in trig)
    dollarv=sum(b[5]*b[4] for b in trig)
    pvol=[sum(b[5] for b in window(bars,m0-60*k,m0-60*(k-1))) for k in range(1,6)]
    pvol=[v for v in pvol if v>0]
    ratio=absv/st.median(pvol) if pvol else None
    fill_px=trig[-1][4]
    ft1=(max((b[2] for b in nxt1),default=fill_px)-fill_px)/fill_px*100 if fill_px else None
    ft2=(max((b[2] for b in nxt2),default=fill_px)-fill_px)/fill_px*100 if fill_px else None
    prun=((fill_px-min((b[3] for b in pre),default=fill_px))/fill_px*100) if (pre and fill_px) else None
    pb=prior[-1] if prior else None
    pcp=((pb[4]-pb[3])/(pb[2]-pb[3])) if (pb and pb[2]>pb[3]) else None
    return dict(thin_tape=thin, abs_vol_trig=round(absv), abs_dollar_trig=round(dollarv), vol_ratio=round(ratio,2) if ratio else "",
                ft1_pct=round(ft1,2) if ft1 is not None else "", ft2_pct=round(ft2,2) if ft2 is not None else "",
                pre_run_pct=round(prun,2) if prun is not None else "", prior_close_pos=round(pcp,2) if pcp is not None else "")
def m10(bars,fs):
    if not bars: return {}
    at=window(bars,fs-10,fs+10); trig=window(bars,(fs//10)*10,(fs//10)*10+10)
    p30=window(bars,fs,fs+30); p60=window(bars,fs,fs+60)
    fill_px=(at or trig or [[0,0,0,0,0,0]])[-1][4]
    av=sum(b[5] for b in trig) if trig else ""
    adv=round(sum(b[5]*b[4] for b in trig)) if trig else ""
    f30=(max((b[2] for b in p30),default=fill_px)-fill_px)/fill_px*100 if (p30 and fill_px) else ""
    f60=(max((b[2] for b in p60),default=fill_px)-fill_px)/fill_px*100 if (p60 and fill_px) else ""
    return dict(abs_vol_10s=round(av) if av!="" else "", abs_dollar_10s=adv, ft30s_pct=round(f30,2) if f30!="" else "", ft60s_pct=round(f60,2) if f60!="" else "")

COLS=["date","ticker","etype","fill_time","R","contaminated","has_10s","thin_tape",
      "abs_vol_trig","abs_dollar_trig","vol_ratio","ft1_pct","ft2_pct","pre_run_pct","prior_close_pos",
      "abs_vol_10s","abs_dollar_10s","ft30s_pct","ft60s_pct"]
rows=[]; gaps=[]
for t in trades:
    d,tk,e=t["date"],t["ticker"],float(t["entry"]); R=round(t["pnl"]/t["planned_risk"],2)
    fs=assign_fill(d,tk,e)
    b1=load_1min(d,tk)
    if fs is None or not b1: gaps.append(f"{d[5:]} {tk} (fill={fs is not None},bars={b1 is not None})"); continue
    r={"date":d,"ticker":tk,"etype":t.get("entry_type",""),"fill_time":fs,"R":R,
       "contaminated":(d,tk) in CONTAM}
    mm=m1(b1,fs)
    if not mm: gaps.append(f"{d[5:]} {tk} (no trig min)"); continue
    r.setdefault("thin_tape",False); r.update(mm)
    b10=load_10s(d,tk); r["has_10s"]=bool(b10)
    r.update(m10(b10,fs) if b10 else {})
    rows.append(r)

OUT.parent.mkdir(parents=True,exist_ok=True)
with open(OUT,"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=COLS); w.writeheader()
    for r in rows: w.writerow({c:r.get(c,"") for c in COLS})
print(f"WROTE {len(rows)} rows -> {OUT.name}  ({sum(r['has_10s'] for r in rows)} with 10s)  gaps:{len(gaps)}")
if gaps: print("  gaps:", ", ".join(gaps))
# ---- validation spot-check: WAI 12:04 must match the hand-analysis (hollow ~few hundred/10s) ----
wai=[r for r in rows if r["ticker"]=="WAI"]
if wai:
    r=wai[0]
    print(f"\nVALIDATION WAI: abs_vol_trig(1m)={r['abs_vol_trig']} vol_ratio={r['vol_ratio']} abs_vol_10s={r.get('abs_vol_10s')} ft30s={r.get('ft30s_pct')} (hand-analysis: hollow, ~560/10s)")
