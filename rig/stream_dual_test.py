"""Dual-stream session test (go-live recorder design, 7/15).

QUESTION: does a 2nd concurrent Webull streaming session on the same app key coexist
with the bot's live session, or kick it?

RUN (only when a kicked stream costs nothing — after the 16:02 EOD dump):
    railway run python3 rig/stream_dual_test.py
Then check the BOT's Railway logs for the same window: reconnect/fallback prints = kicked.

VERDICTS
  A) this script receives ticks AND the bot's stream stays healthy → dual sessions OK
     → recorder can be a thread in the dashboard service (Option B, cleanest).
  B) this script connects but the bot drops/reconnects → single-session feed
     → at go-live the recorder OWNS the stream; the bot consumes prices from it.
  C) this script gets no ticks/refused → per-session subscribe cap or connect limit
     → same consequence as B, plus quota planning.
"""
import os, sys, time, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from webull.core.utils.common import get_uuid
from webull.data.data_streaming_client import DataStreamingClient as WebullStreamingClient

KEY, SEC = os.environ["WEBULL_APP_KEY"], os.environ["WEBULL_APP_SECRET"]
TOK = os.environ.get("WEBULL_ACCESS_TOKEN", "")
td = pathlib.Path("/tmp/webull_token2"); td.mkdir(parents=True, exist_ok=True)
if TOK:
    (td / "token.txt").write_text(TOK + "\n" + str(int(time.time() * 1000) + 999999999) + "\nNORMAL\n")

TICKS = []
def on_msg(*a, **k):
    TICKS.append(time.time())

client = WebullStreamingClient(KEY, SEC, "us", get_uuid())   # OWN uuid = session #2
client._api_client.set_token_dir(str(td))
if TOK:
    client._api_client.set_token(TOK)
client.on_quotes_message = on_msg
client.on_quotes_subscribe = lambda *a, **k: None
client.connect_and_loop_async(timeout=1, thread_daemon=True)
time.sleep(3)

SYMS = sys.argv[1:] or ["SOBR", "LEDS", "TGHL"]
try:
    client.subscribe(SYMS, "US_STOCK", ["SNAPSHOT"])   # mirrors the bot's exact call
    print(f"session-2 subscribed: {SYMS}")
except Exception as e:
    print(f"session-2 subscribe failed: {e}")

t0 = time.time()
while time.time() - t0 < 60:
    time.sleep(5)
    print(f"  t+{time.time()-t0:4.0f}s  ticks={len(TICKS)}")

print(f"\nRESULT: {len(TICKS)} ticks in 60s on session #2.")
print("Now check the bot's Railway logs 📡/⚠️ lines for this window: quiet = VERDICT A; reconnect/fallback = VERDICT B.")
