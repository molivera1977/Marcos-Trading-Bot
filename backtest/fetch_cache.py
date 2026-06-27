import os,time,pathlib,datetime as dt,json
from webull.core.client import ApiClient
from webull.data.data_client import DataClient
td="/tmp/webull_token"; pathlib.Path(td).mkdir(parents=True,exist_ok=True)
(pathlib.Path(td)/"token.txt").write_text(f"{os.environ['WEBULL_ACCESS_TOKEN']}\n{int(time.time()*1000)+14*24*3600*1000}\nNORMAL\n")
api=ApiClient(os.environ["WEBULL_APP_KEY"],os.environ["WEBULL_APP_SECRET"],"us",token_check_duration_seconds=60,token_check_interval_seconds=5)
api.set_token_dir(td); api.add_endpoint("us","api.webull.com"); dc=DataClient(api)
def fetch(sym):
    for a in range(6):
        try:
            r=dc.market_data.get_history_bar(symbol=sym,category="US_STOCK",timespan="M1",count="1200")
            raw=r.json(); bars=raw if isinstance(raw,list) else (raw.get("data") if isinstance(raw.get("data"),list) else raw.get("data",{}).get("items",[]))
            if bars and len(bars)>100: return bars
        except Exception as e: pass
        time.sleep(2)
    return []
for sym in ["SDOT","IVF","ILLR","BDRX","AZI","ZDAI","QCY","CANF"]:
    bars=fetch(sym)
    json.dump(bars, open(f"/tmp/bars_{sym}.json","w"))
    print(f"  {sym}: cached {len(bars)} bars")
    time.sleep(1.5)
