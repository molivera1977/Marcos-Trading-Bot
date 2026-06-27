import json,datetime as dt
from kevlib import (_bar_high,_bar_low,_bar_close,is_topping_tail,find_next_supply,compute_room,
                    FLAT_TOP_WINDOW,FLAT_TOP_MAX_RANGE,STOP_LOSS_PCT,MIN_ROOM_RR)
def parse_t(b):
    t=b.get("time")
    if not t: return None
    try:   # ISO "2026-06-26T19:50:00.000+0000" (UTC) -> ET
        return dt.datetime.fromisoformat(str(t)[:19])-dt.timedelta(hours=4)
    except: return None
def load(sym):
    bars=json.load(open(f"/tmp/bars_{sym}.json"))
    for b in bars: b["_dt"]=parse_t(b)
    bars=[b for b in bars if b["_dt"]]; bars.sort(key=lambda b:b["_dt"])
    return [b for b in bars if b["_dt"].date()==dt.date(2026,6,26)]
def vwap_run(bars):
    pv=v=0;o=[]
    for b in bars:
        px=(_bar_high(b)+_bar_low(b)+_bar_close(b))/3 or _bar_close(b);vol=float(b.get("volume") or 0)
        pv+=px*vol;v+=vol;o.append(pv/v if v else 0)
    return o
def detect(bars):
    vw=vwap_run(bars)
    for i in range(FLAT_TOP_WINDOW,len(bars)):
        win=bars[i-FLAT_TOP_WINDOW:i];hs=[_bar_high(b) for b in win];ls=[l for l in (_bar_low(b) for b in win) if l>0]
        if not ls:continue
        wh=max(hs);wl=min(ls);rng=(wh-wl)/wl;price=_bar_high(bars[i]);vwap=vw[i]
        if price>wh and rng<=FLAT_TOP_MAX_RANGE:
            if vwap>0 and price<vwap:continue
            stop=round(price*(1-STOP_LOSS_PCT),4);room=compute_room(price,stop,bars[:i+1]);rr=room["rr_to_supply"]
            if rr is not None and rr<MIN_ROOM_RR:continue
            return i,round(price,4),room
    return None,None,None
def exit_sim(bars,i0,entry,room,instant):
    R=max(entry*STOP_LOSS_PCT,0.01);ns=room.get("next_supply") if room else None
    sc2=ns if (ns and ns>entry+R) else entry+2*R;tiers=[(round(entry+R,4),0.50),(round(sc2,4),0.75)]
    rem=1.0;sold=0.0;tier=0;stop=round(entry*(1-STOP_LOSS_PCT),4);pt=False;fills=[];hod=entry;reason="3:45"
    for j in range(i0+1,len(bars)):
        b=bars[j];bh=_bar_high(b);bl=_bar_low(b);bc=_bar_close(b);pb=bars[j-1];hod=max(hod,bh)
        if tier<2 and bh>=tiers[tier][0]:
            cum=tiers[tier][1];q=cum-sold;fills.append((q,tiers[tier][0]));sold=cum;rem=1-sold;tier+=1;pt=True;stop=entry
        fi=(instant=="always") or (instant=="post_scale" and pt) or (instant=="post_scale_hod" and pt and bh>=hod*0.999)
        if rem>0 and fi and bh>_bar_high(pb)>0 and 0<bc<_bar_high(pb): fills.append((rem,bc));rem=0;reason="instant";break
        if rem>0 and pt and 0<bc<_bar_low(pb): fills.append((rem,bc));rem=0;reason="prevbarlow";break
        if rem>0 and bc>entry and is_topping_tail(b) and bh>=hod*0.99: fills.append((rem,bc));rem=0;reason="toptail";break
        if rem>0 and bl<=stop: fills.append((rem,stop));rem=0;reason=("BE" if pt else "7%");break
    if rem>0: fills.append((rem,_bar_close(bars[-1])))
    return round(sum(q*(px-entry) for q,px in fills)/entry*100,2),reason
syms=["SDOT","IVF","BDRX","AZI"]; D={}
for s in syms:
    bars=load(s); i,e,room=detect(bars); D[s]=(bars,i,e,room,max(_bar_high(b) for b in bars))
print("entry / day-high:  "+" | ".join(f"{s} in ${D[s][2]} hi ${D[s][4]:.2f}" for s in syms))
print(f"\n{'instant policy':16}"+"".join(f"{s:>16}" for s in syms))
for pol in ["always","post_scale","post_scale_hod","off"]:
    cells=[]
    for s in syms:
        bars,i,e,room,_=D[s]
        if i is None: cells.append("no-entry"); continue
        pnl,why=exit_sim(bars,i,e,room,pol); cells.append(f"{pnl:+.1f}% {why}")
    print(f"{pol:16}"+"".join(f"{c:>16}" for c in cells))
