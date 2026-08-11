"""FRESHNESS CONTRACT ACCEPTANCE REPLAY (weekend rock validation; spec in task #36).
Replays the SHIPPED _effective_map/_auto_map/_map_freshness (imported from the live module,
not reimplemented) against 8/7's recorded reality for the three named specimens:
  YJ   — the +545% runner the gates map-starved (breakside rejects at 09:52/10:23/10:33 ET)
  CELZ — the 8/6 frozen-break class
  NAMI — the crowned gapper with the killed read
At each real gate-decision moment: feed the bot's _curl_feed from recorded ~ALP10S bars up to
that instant, feed _fetch_kev_levels with the map AS IT STOOD then (from the rec's history),
crown state from leader_armed times. Output per moment: stored break vs CONTRACT break, and the
breakside verdict THEN vs UNDER THE CONTRACT. Acceptance: contract break within 15% of live px
at every moment on YJ (no dead maps), and the 09:52 $1.70 fire's verdict."""
import json, urllib.request, urllib.parse, importlib, sys, types, os, time
sys.path.insert(0, "/Users/marcosolivera/Desktop/Marcos-Trading-Bot")
os.environ.setdefault("DRY_RUN", "1")
U="https://zestful-intuition-production-b16a.up.railway.app"
def get(u): return json.load(urllib.request.urlopen(u,timeout=60))
sys.path.insert(0, "/Users/marcosolivera/Desktop/Marcos-Trading-Bot/rig")
from loader import load_bot
bot = load_bot()
def bars10(tk):
    r=get(f"{U}/api/bars?date=2026-08-07&ticker={urllib.parse.quote(tk)}~ALP10S").get("bars") or []
    out={}
    for x in r:
        ts=str(x.get("time"))[11:19]
        sec=int(ts[:2])*3600+int(ts[3:5])*60+int(ts[6:8])
        out[sec]={"o":float(x.get("open") or 0),"h":float(x["high"]),"l":float(x["low"]),
                  "c":float(x["close"]),"v":float(x.get("volume") or 0)}
    return out
# YJ's map history (recorded in the rec 8/7): (read_at ET "HH:MM", break)
YJ_MAPS=[("09:52",1.69),("10:25",3.96),("10:34",3.98),("10:59",5.29),("11:01",6.37),("11:14",8.25)]
def map_at(hhmm, maps):
    cur=None
    for t,b in maps:
        if t<=hhmm: cur=(t,b)
    return cur
CASES=[("YJ","09:52:53",1.70),("YJ","10:23:19",3.96),("YJ","10:33:39",3.98),
       ("YJ","11:20:00",7.50),("YJ","11:51:02",10.95)]
B=bars10("YJ")
for tk,ts,px in CASES:
    hh,mm,ss=int(ts[:2]),int(ts[3:5]),int(ts[6:8])
    sec_utc=(hh+4)*3600+mm*60+ss
    hist={k:v for k,v in B.items() if k<=sec_utc}
    m=map_at(ts[:5],YJ_MAPS)
    stored_break=m[1] if m else 0
    stored_age=( (hh*60+mm) - (int(m[0][:2])*60+int(m[0][3:5])) ) if m else 999
    # feed the SHIPPED functions
    bot._curl_feed=lambda t,n=90,_h=hist: dict(list(sorted(_h.items()))[-n:])
    bot._fetch_kev_levels=lambda _b=stored_break: {"YJ":{"break":_b,"targets":[_b],"src":"kev","_ts":"2026-08-07T00:00:00-04:00"}}
    bot._is_leader=lambda t: True
    bot._log_decision=lambda *a,**k: None
    bot._effmap_cache.clear(); bot._fresh_breach_t.clear()
    eff=bot._effective_map("YJ", px)
    nb=eff.get("break")
    old_gap=(px-stored_break)/stored_break*100 if stored_break else 0
    new_gap=(px-nb)/nb*100 if nb else 0
    BS_MAX=6.0  # BREAKSIDE_MAX_PCT current
    print(f"{ts} px ${px:<6} stored brk ${stored_break:<5} (age {stored_age}m, gap {old_gap:+.0f}%) "
          f"-> CONTRACT brk ${nb} (gap {new_gap:+.1f}%) auto={bool(eff.get('auto_map'))} "
          f"breakside: was {'REJECT' if old_gap>BS_MAX else 'pass'} -> now {'REJECT' if new_gap>BS_MAX else 'PASS'}")
