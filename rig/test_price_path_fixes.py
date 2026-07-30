"""Rig: PRICE-PATH FIX SET (7/29 evening, Fable-approved spec FIX_SPECS_20260729.md).

Four fixes, one subsystem. Every pin includes its gauntlet case (the real 7/29 trade that bled) and
a MUTANT direction (what must go RED if the guard rots).

  P0-A  ticket sanity   — stop >= entry refused UNCONDITIONALLY (AMIX 09:32: stop 4.6512 > px 4.62)
  P0-B  swap rebuild    — divergence is not staleness. RTH: NEVER swap (NCRA 09:31 / AMIX 10:05 /
                          MSS 10:14 all die). PM: swap only when our own tick is old + bar fresh.
                          SWAP_MODE=off kills all; independent of lane flags.
  P0-C  fix B           — extend_hour_last_price serves premarket ONLY when its trade_time is fresh;
                          never `close`; PM_EXT_QUOTE=0 kills.
  P1-F  clear/orphan    — hollow orphan rows discarded, never "recovered".
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot

bot = load_bot()
fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


# ══ P0-B: the swap decision table ═══════════════════════════════════════════════════════════════
print("== P0-B swap: RTH never substitutes (the 7/29 damage class) ==")
# gauntlet: NCRA 09:31 stream 3.5399 / bar 3.6214 — divergence 2.3%, RTH, tick fresh
bot._price_registry["NCRA"] = {"p": 3.5399, "t": time.time()}
ok, why = bot._swap_price_ok("NCRA", 3.5399, 3.6214, int(time.time()) - 5, hm="09:31")
check("NCRA 09:31 class: RTH + fresh tick -> REFUSED", not ok and why == "rth_quote_trusted", why)
# gauntlet: AMIX 10:05 stream 5.451 / bar 5.61 — RTH, tick STALE (worst case: even then, RTH refuses)
bot._price_registry["AMIX"] = {"p": 5.451, "t": time.time() - 900}
ok, why = bot._swap_price_ok("AMIX", 5.451, 5.61, int(time.time()) - 5, hm="10:05")
check("AMIX 10:05 class: RTH + STALE tick -> still REFUSED", not ok, why)
# gauntlet: MSS 10:14 downward swap (2.2706 -> 2.17) — direction is irrelevant, RTH refuses
ok, why = bot._swap_price_ok("MSS", 2.2706, 2.17, int(time.time()) - 5, hm="10:14")
check("MSS 10:14 class: downward swap in RTH -> REFUSED", not ok, why)

print("== P0-B swap: premarket behavior (the mechanism's legitimate home) ==")
bot._price_registry["PMX"] = {"p": 2.00, "t": time.time() - 600}      # tick 10 min old
ok, why = bot._swap_price_ok("PMX", 2.00, 2.10, int(time.time()) - 15, hm="08:05")
check("PM + stale tick + fresh bar -> ALLOWED", ok and why == "pm_quote_stale", why)
bot._price_registry["PMY"] = {"p": 2.00, "t": time.time() - 2}        # tick 2s old = fresh
ok, why = bot._swap_price_ok("PMY", 2.00, 2.10, int(time.time()) - 15, hm="08:05")
check("PM + FRESH tick -> refused (trust our own tick)", not ok and why == "tick_fresh", why)
bot._price_registry["PMZ"] = {"p": 2.00, "t": time.time() - 600}
ok, why = bot._swap_price_ok("PMZ", 2.00, 2.10, int(time.time()) - 5000, hm="08:05")
check("PM + stale tick + STALE bar -> refused (no good price exists)", not ok and why == "bar_stale_too", why)
ok, why = bot._swap_price_ok("NOTICK", 2.00, 2.10, int(time.time()) - 15, hm="08:05")
check("PM + no tick ever -> allowed (age None = not fresh)", ok, why)

print("== P0-B kill switch + independence from lane flags ==")
_saved = bot.SWAP_MODE
bot.SWAP_MODE = "off"
ok, why = bot._swap_price_ok("PMX", 2.00, 2.10, int(time.time()) - 15, hm="08:05")
check("SWAP_MODE=off -> never substitutes, even in PM", not ok and why == "swap_off", why)
bot.SWAP_MODE = "legacy"
ok, why = bot._swap_price_ok("NCRA", 3.5399, 3.6214, int(time.time()) - 5, hm="09:31")
check("SWAP_MODE=legacy -> old behavior available for rollback", ok and why == "legacy", why)
bot.SWAP_MODE = _saved
check("default mode is pm_stale", bot.SWAP_MODE == "pm_stale", bot.SWAP_MODE)
src = pathlib.Path(bot.__file__).read_text()
i = src.find("def _swap_price_ok")
check("swap guard consults NO lane flag (independence)",
      i > 0 and not any(f in src[i:i + 1600] for f in
                        ("RECLAIM_LIVE", "HIDDEN_ENTRY", "ZONEFLIP_KEV", "IGNITION_10S")))
check("both conversion sites route through _swap_price_ok", src.count("_swap_price_ok(") >= 3)
check("refusals leave a decision row", "stale_swap_refused" in src)

# ══ P0-A: ticket sanity ═════════════════════════════════════════════════════════════════════════
print("== P0-A ticket sanity (AMIX 09:32: stop above entry is never sizeable) ==")
j = src.find("bad_stop_skip")
seg = src[max(0, j - 700):j]
check("guard is UNCONDITIONAL (no RISK_BASED_SIZING qualifier)",
      "RISK_BASED_SIZING and stop_loss >= entry_price" not in src
      and "if stop_loss >= entry_price:" in src)
check("guard still refuses BEFORE any share computation",
      src.find("if stop_loss >= entry_price:") < src.find("_sh_risk = int(_risk_i"))

# ══ P0-C: fix B ═════════════════════════════════════════════════════════════════════════════════
print("== P0-C fix B: extend_hour_last_price with trade-time freshness ==")
now_ms = time.time() * 1000
def q(pre=None, ext=None, ext_t=None, close=4.00):
    d = {"close": close, "last_price": close}
    if pre is not None:   d["pre_market_price"] = pre
    if ext is not None:   d["extend_hour_last_price"] = ext
    if ext_t is not None: d["extend_hour_last_trade_time"] = ext_t
    return d
# The normalizer lives inside _get_webull_quote; test through the raw-field logic via _session_price
# on a synthesized normalized quote — plus source-level pins on the normalizer itself.
check("normalizer reads extend_hour_last_price", "extend_hour_last_price" in src)
check("freshness gate on extend_hour_last_trade_time", "extend_hour_last_trade_time" in src
      and "PM_EXT_QUOTE_MAX_AGE_S" in src)
check("kill switch PM_EXT_QUOTE exists (default on)", bot.PM_EXT_QUOTE is True)
check("age cap default 120s", bot.PM_EXT_QUOTE_MAX_AGE_S == 120.0)
k = src.find("FIX B (Fable-approved spec P0-C)")
seg_c = src[k:k + 1400] if k > 0 else ""
check("fires ONLY when pre_market_price is absent (raw field wins)",
      "_raw_pre is None and PM_EXT_QUOTE" in seg_c)
check("never falls back to `close` in the ext branch", "close" not in seg_c.replace("yesterday — the known trap", "")
      or 'd.get("close")' not in seg_c)
# behavioral: _session_price still serves NO-PRICE when raw is absent (the trap-guard survives)
check("premarket with no live field still = NO-PRICE",
      bot._session_price({"last_price": 4.00, "pre_market_price_raw": None}, hm="08:00") == 0.0)
check("premarket with a live raw field serves it",
      bot._session_price({"last_price": 4.00, "pre_market_price_raw": 4.41}, hm="08:00") == 4.41)
check("RTH path unchanged (last_price)",
      bot._session_price({"last_price": 4.00, "pre_market_price_raw": 4.41}, hm="10:00") == 4.00)

# ══ P1-F: verified clear + hollow-orphan guard ══════════════════════════════════════════════════
print("== P1-F clear verification + hollow orphans ==")
m = src.find("def _clear_open_trade")
seg_f = src[m:m + 1800]
check("clear checks the HTTP status", "status_code" in seg_f)
check("clear re-reads the store to verify", "/api/open_trades" in seg_f)
check("clear retries once then logs loudly", "GIVING UP" in seg_f and "SURVIVE" in seg_f)
n = src.find("HOLLOW-ROW GUARD")
seg_o = src[n:n + 900] if n > 0 else ""
check("orphan recovery discards all-null rows", "orphan_row_invalid" in seg_o)
check("discard only when ALL identifiers null (real positions still recover)",
      'o.get("entry_price") or o.get("entry_date") or o.get("trade_id")' in seg_o)

print()
if fails:
    print(f"RED — {len(fails)} failing: {fails}")
    sys.exit(1)
print("GREEN — RTH never trades a substituted price; PM substitutes only when truly blind; "
      "invalid tickets refused; hollow orphans discarded")
