"""D1 PROVING DRILL (8/16): stop-coherence floor exercised on the REAL bot namespace.

Loads marcos_trading_bot.py via the rig loader (real _log_decision, real _slot_refund,
real _decision_queue), extracts the exact STOP-COHERENCE block out of _trade_worker
(text-identical, exec'd in the module dict with synthetic worker locals) and pushes a
0.3%-wide synthetic trade through it. Asserts:
  1) refuse row 'stop_coherence_refused' lands in _decision_queue with width_pct=0.3
  2) refund path executed: real _slot_refund decremented the vwap_reclaim RTH ticket
     and wrote 'slot_refunded'
  3) worker RETURNED before sizing (sentinel after the block never reached)
  4) a 6% stop passes through untouched (no refuse row)
Exit code 0 = PROVEN. Never touches the network (SCREENER_URL faked, queue read in-proc).
"""
import os, sys, pathlib, datetime as _dt
os.environ["SCREENER_URL"] = "http://rig.invalid"   # _log_decision requires a URL to enqueue
os.environ.setdefault("STOP_COHERENCE_MIN_PCT", "0.5")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()

fails = 0
def check(name, cond, note=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"  [{note}]" if note else ""))
    if not cond: fails += 1

src = pathlib.Path(bot.__file__).read_text()
i0 = src.index("            # ── 8/13 STOP-COHERENCE FLOOR (see STOP_COHERENCE_MIN_PCT def)")
i1 = src.index("            # B: Kev short-003 sizing (LIVE 7/11)", i0)
block = "\n".join(l[12:] for l in src[i0:i1].splitlines())   # dedent worker body -> function body
fn = ("def _drill_worker(ticker, entry_price, stop_loss, entry_type):\n"
      + "\n".join("    " + l for l in block.splitlines())
      + "\n    return 'REACHED_SIZING'\n")
import threading
if not hasattr(bot, 'trade_lock'):
    bot.trade_lock = threading.Lock()   # main()-local in production; same semantics
exec(fn, bot.__dict__)
check("real block extracted (refuse row + refund + return present)",
      '"stop_coherence_refused"' in block and "_slot_refund(ticker, entry_type)" in block and "return" in block)

# seed a spent vwap_reclaim RTH ticket so the refund has something real to give back
now = _dt.datetime.now(bot.EASTERN)
day, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
sess = "PRE" if hm < "09:30" else "RTH"
key = (day, "DRILL", "vr", sess)
bot._curl_rth_n[key] = 1
bot.reentry["held"].add("DRILL")
bot._decision_queue.clear(); bot._decision_last.clear()

# 1) 0.3% wide -> refuse
r = bot._drill_worker("DRILL", 10.00, 9.97, "vwap_reclaim")
rows = [x for x in bot._decision_queue if x["ticker"] == "DRILL"]
st = [x["status"] for x in rows]
ref = next((x for x in rows if x["status"] == "stop_coherence_refused"), None)
check("worker returned before sizing", r is None, repr(r))
check("stop_coherence_refused row written", ref is not None, str(st))
check("row carries width_pct=0.3 / stop / machine", ref and ref.get("width_pct") == 0.3
      and ref.get("stop") == 9.97 and ref.get("machine") == "vwap_reclaim", str(ref))
check("refund path executed: ticket returned", key not in bot._curl_rth_n, str(bot._curl_rth_n.get(key)))
check("slot_refunded row written", "slot_refunded" in st, str(st))
check("held released", "DRILL" not in bot.reentry["held"])

# 2) 6% wide -> passes through
bot._decision_queue.clear(); bot._decision_last.clear()
r2 = bot._drill_worker("DRILL2", 10.00, 9.40, "vwap_reclaim")
check("6% stop passes to sizing", r2 == "REACHED_SIZING", repr(r2))
check("no refuse row on 6%", not any(x["status"] == "stop_coherence_refused" for x in bot._decision_queue))

# 3) boundary: exactly 0.5% passes (floor is strict <)
r3 = bot._drill_worker("DRILL3", 10.00, 9.95, "vwap_reclaim")
check("exactly 0.5% passes (strict <)", r3 == "REACHED_SIZING", repr(r3))

print("STOP-COHERENCE DRILL:", "PROVEN" if fails == 0 else f"FAILED ({fails})")
print("rows:", [ (x["status"], x.get("width_pct")) for x in rows ])
sys.exit(1 if fails else 0)
