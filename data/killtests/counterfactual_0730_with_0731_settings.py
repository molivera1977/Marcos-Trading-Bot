"""7/30's TRADES RE-RUN UNDER 7/31's SHIPPED SETTINGS (Marcos: "can we run yesterday's trades with
today's new settings for comparison").

WHAT SHIPPED THE NIGHT OF 7/30 (all live 7/31):
  ENTRY-SIDE (these REMOVE trades):   HIDDEN_EXT_GATE 3-10% · IGNITION_CONVERT_MULT 4.5x ·
                                      ZONEFLIP_CONVERT=0 (shadow) · RECLAIM_FIREVOL 2.0x
  EXIT-SIDE  (these RE-PRICE trades): RESTING_BANK (tier fills at TIER PRICE on tape-through) ·
                                      VRIDE_EXEMPT=hidden_entry · HIDDEN_SCALEBAR_STOP
  ORDERING:                           PULLBACK_FIRST (NOT modelled — see LIMITS)

METHOD — three arms on 7/30's 27 real closed trades:
  A  ACTUAL      what the book recorded live on 7/30 (the trade store)
  B  EXITS-ONLY  same 27 entries, re-priced through the honest harness with resting-bank tier
                 semantics (a tier fills when the tape trades THROUGH it, booked AT tier price) +
                 BE after the first scale. This isolates the EXIT changes.
  C  FULL        arm B, then REMOVE the trades today's entry gates would have refused.

PRE-REGISTERED HONESTY LIMITS (written before running):
  1. This is NOT a clean experiment. Arm B's harness prices EVERY trade on the same ladder, while
     7/30 live ran two ladders (kev25 R-tiers and hidden's %-tiers). Read arm B as "resting-bank
     mechanics applied uniformly", not as a faithful replay of each lane's live ladder.
  2. PULLBACK_FIRST is NOT modelled — it changes WHICH detector claims a name, which cannot be
     reconstructed from closed trades (it needs the full scan-loop re-run). Any effect it had on
     7/31 is absent here. This understates the change-set.
  3. The entry gates are applied with the data the ARCHIVE carries. Where a field is missing
     (e.g. a fire's volmult on 7/30 — the stamp shipped 7/30 NIGHT, so 7/30's rows predate it),
     the trade is KEPT and counted as "ungradeable", never silently dropped. Reported explicitly.
  4. Slippage is the calibrated 1.477%; the live book's fills already contain real slippage. Arm A
     vs B therefore mixes two friction models. Directional read only.
  5. n=27. One day. This CANNOT establish that the change-set works — at best it shows the
     mechanics move the number on a day we know was bad.
FAILURE CONDITION: if arm C is not better than arm A, the change-set did not help on 7/30 and that
is reported as-is.
"""
import json, urllib.request, collections, datetime, pathlib
import harness

U = harness.U
DAY = "2026-07-30"

T = json.load(urllib.request.urlopen(f"{U}/api/trades?date={DAY}&limit=500", timeout=30))
trades = [t for t in (T.get("trades") or T.get("rows") or []) if t.get("date") == DAY]
D = json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={DAY}&limit=50000",
                                     timeout=60)).get("rows") or []

def et(s):
    try: return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

trig = [r for r in D if str(r.get("status", "")).startswith("triggered")]
rows = []
for t in trades:
    ref = et(t.get("entry_ts_utc")) or et(t.get("recorded_at"))
    c = [r for r in trig if r["ticker"] == t["ticker"] and et(r.get("recorded_at"))
         and et(r["recorded_at"]) <= ref]
    near = max(c, key=lambda r: et(r["recorded_at"])) if c else None
    lane = near["status"].replace("triggered_", "").replace("_kev3gate", "") if near else "?"
    rows.append({**t, "lane": lane, "fire": near, "ts": ref})

print(f"7/30 closed trades: n={len(rows)}  ACTUAL total ${sum(r['pnl'] for r in rows):+.2f}\n")

# ── ARM B: re-price every entry through the harness (resting-bank tier semantics) ─────────────
def reprice(r):
    e, s = r.get("entry"), r.get("stop_loss")
    if not (e and s and e > s and r.get("ts")):
        return None, "no ticket"
    hm = r["ts"].astimezone(harness.ET).strftime("%H:%M:%S")
    rep = harness.replay(r["ticker"], DAY, e, s, entry_hm=hm, shares=r.get("shares"))
    if not rep:
        return None, "no tape"
    return rep["pnl"], None

for r in rows:
    r["b_pnl"], r["b_why"] = reprice(r)

ok = [r for r in rows if r["b_pnl"] is not None]
print(f"ARM B (exit mechanics only): n={len(ok)} repriced, {len(rows)-len(ok)} unpriceable")
print(f"  ACTUAL on those {len(ok)}: ${sum(r['pnl'] for r in ok):+.2f}")
print(f"  ARM B  on those {len(ok)}: ${sum(r['b_pnl'] for r in ok):+.2f}")

# ── ARM C: apply 7/31's ENTRY gates ───────────────────────────────────────────────────────────
def gate_verdict(r):
    """Would 7/31's shipped entry gates have REFUSED this trade? -> (refused, reason)"""
    lane, f = r["lane"], r.get("fire") or {}
    if lane == "zone_flip":
        return True, "ZONEFLIP_CONVERT=0 (shadow)"
    if lane == "hidden_entry":
        ev = f.get("ext_vwap")
        if ev is None:
            return False, "hidden: ext_vwap MISSING (ungradeable, kept)"
        if 3.0 <= float(ev) < 10.0:
            return True, f"HIDDEN_EXT_GATE ({ev}% in 3-10 band)"
        return False, f"hidden ext {ev}% outside band"
    if lane == "ignition":
        vx = f.get("volx")
        if vx is None:
            return False, "ignition: volx MISSING (ungradeable, kept)"
        if float(vx) < 4.5:
            return True, f"IGNITION_CONVERT_MULT (volx {vx} < 4.5)"
        return False, f"ignition volx {vx} >= 4.5"
    if lane.startswith("vwap_reclaim"):
        return False, "reclaim: fire-bar volmult NOT STAMPED on 7/30 (ungradeable, kept)"
    return False, "lane not gated by the 7/30 change-set"

for r in rows:
    r["refused"], r["why"] = gate_verdict(r)

kept = [r for r in ok if not r["refused"]]
cut  = [r for r in ok if r["refused"]]
print(f"\nARM C (entry gates applied): refused {len(cut)}, kept {len(kept)}")
print(f"  refused trades' ACTUAL P&L: ${sum(r['pnl'] for r in cut):+.2f}  "
      f"(this is what the gates would have avoided)")
for r in sorted(cut, key=lambda x: x["pnl"]):
    print(f"    CUT  {r['ticker']:<6}{r['lane']:<14}${r['pnl']:>8.2f}  {r['why']}")

print("\n" + "=" * 92)
print("THREE ARMS, 7/30's TAPE")
print("=" * 92)
a = sum(r["pnl"] for r in ok)
b = sum(r["b_pnl"] for r in ok)
c = sum(r["b_pnl"] for r in kept)
print(f"  A  ACTUAL (live 7/30)                  n={len(ok):>3}   ${a:>9.2f}")
print(f"  B  + resting-bank exit mechanics       n={len(ok):>3}   ${b:>9.2f}   ({b-a:+.2f} vs A)")
print(f"  C  + 7/31 entry gates                  n={len(kept):>3}   ${c:>9.2f}   ({c-a:+.2f} vs A)")

ung = [r for r in ok if "ungradeable" in r["why"]]
print(f"\n  UNGRADEABLE (kept in C, gate data absent on 7/30): {len(ung)} trades, "
      f"${sum(r['pnl'] for r in ung):+.2f} actual")
for r in ung:
    print(f"    {r['ticker']:<6}{r['lane']:<16}{r['why']}")

print("\nby lane (ACTUAL vs ARM B):")
g = collections.defaultdict(list)
for r in ok: g[r["lane"]].append(r)
for lane, v in sorted(g.items(), key=lambda kv: sum(x["pnl"] for x in kv[1])):
    print(f"  {lane:<16} n={len(v):>2}  actual ${sum(x['pnl'] for x in v):>8.2f}   "
          f"armB ${sum(x['b_pnl'] for x in v):>8.2f}")

json.dump([{k: r[k] for k in ("ticker","lane","entry","stop_loss","exit","shares","pnl",
                              "b_pnl","refused","why")} for r in ok],
          open(pathlib.Path(__file__).with_name("counterfactual_0730_rows.json"), "w"), indent=1)
print("\nrows -> counterfactual_0730_rows.json")
