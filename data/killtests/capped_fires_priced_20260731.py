"""PRICE THE CAPPED HIDDEN FIRES (7/31 — Marcos: "price those 60 fires and we will know";
Fable: "FCUV is a loud MOTIVATION for the I3 study; it is not a verdict that the caps cost us").

THE QUESTION: hidden fired ~91 times today and converted a handful; the rest logged
`hidden_capped` (daily cap 3 / name cap 2). Did the caps refuse MONEY or refuse NOISE?

DATA: `hidden_shadow_fire` rows carry price, STOP, anchor, ext_vwap and seq — a complete ticket.
The paired `hidden_capped` row (same ticker+timestamp) marks the ones the caps refused. So every
refused fire is priceable through the honest harness exactly as if it had converted.

FABLE'S I3 LABELS applied here for the first time — the distinction that decides whether the fix
is "raise the cap" or "require a new setup":
  NEW-SETUP : the fire's anchor moved materially AND price moved materially since the prior fire
              on that name (a genuinely different pullback at a different level)
  RE-ARM    : same anchor / same price zone, minutes apart — the machine re-firing on unchanged
              structure. Kev re-enters on NEW setups; a detector in a loop produces RE-ARMs.

APPLIED FILTERS (7/30-night gates, so the counterfactual is what TODAY's bot would do):
  HIDDEN_EXT_GATE 3-10% — refused fires are excluded from the "would have taken" set, since the
  shipped bot would refuse them regardless of any cap.

PRE-REGISTERED, before the numbers:
  1. Report NEW-SETUP and RE-ARM cohorts SEPARATELY. A blended number cannot answer the question.
  2. Report FCUV separately from the rest — it is the motivating case and must not be allowed to
     carry the whole result silently.
  3. Slippage/sizing = the honest harness (real chain, 1.477%). Downstream gates other than the
     ext gate are NOT applied — read as an upper bound on what the caps refused.
  4. FAILURE CONDITION: if the refused cohort is NEGATIVE, the caps SAVED money and the §I1
     complaint is answered — report that plainly and close it.
"""
import json, urllib.request, collections, pathlib
import harness

U = harness.U
DAY = "2026-07-31"
EXT_LO, EXT_HI = 3.0, 10.0

D = json.load(urllib.request.urlopen(f"{U}/api/decisions_archive?date={DAY}&limit=50000",
                                     timeout=60)).get("rows") or []
fires  = [r for r in D if r.get("status") == "hidden_shadow_fire"]
capped = {(r.get("ticker"), r.get("time")) for r in D if r.get("status") == "hidden_capped"}
took   = {(r.get("ticker"), r.get("time")) for r in D if r.get("status") == "triggered_hidden_entry"}
extrej = {(r.get("ticker"), r.get("time")) for r in D if r.get("status") == "hidden_ext_reject"}
print(f"hidden fires today: {len(fires)} | capped: {len(capped)} | converted: {len(took)} | "
      f"ext-rejected: {len(extrej)}\n")

def hhmmss(t):
    try:
        import datetime as dt
        return dt.datetime.strptime(t, "%I:%M:%S %p").strftime("%H:%M:%S")
    except Exception:
        return None

rows = []
prev = {}
for f in sorted(fires, key=lambda r: (r.get("ticker"), r.get("time"))):
    tk, tm = f.get("ticker"), f.get("time")
    e, s = f.get("price"), f.get("stop")
    ev = f.get("ext_vwap")
    was_capped = (tk, tm) in capped
    # I3 label vs the PRIOR fire on this name
    p = prev.get(tk)
    if p is None:
        lab = "FIRST"
    else:
        d_anchor = abs((f.get("anchor") or 0) - (p.get("anchor") or 0)) / max(p.get("anchor") or 1, 1e-9)
        d_px     = abs((e or 0) - (p.get("price") or 0)) / max(p.get("price") or 1, 1e-9)
        lab = "NEW-SETUP" if (d_anchor >= 0.02 and d_px >= 0.02) else "RE-ARM"
    prev[tk] = f
    if not was_capped:
        continue                      # only price what the CAPS refused
    if ev is not None and EXT_LO <= float(ev) < EXT_HI:
        rows.append({"tk": tk, "tm": tm, "lab": "ext_refused", "pnl": None, "ext": ev}); continue
    if not (e and s and e > s):
        rows.append({"tk": tk, "tm": tm, "lab": lab, "pnl": None, "why": "bad ticket"}); continue
    hm = hhmmss(tm)
    rep = harness.replay(tk, DAY, e, s, entry_hm=hm) if hm else None
    rows.append({"tk": tk, "tm": tm, "lab": lab, "ext": ev, "entry": e, "stop": s,
                 "pnl": (rep["pnl"] if rep and rep.get("shares") else None),
                 "shares": (rep or {}).get("shares")})

priced = [r for r in rows if isinstance(r.get("pnl"), (int, float))]
print(f"capped fires: {len(rows)} | priceable: {len(priced)} | "
      f"ext-refused-anyway: {sum(1 for r in rows if r['lab']=='ext_refused')} | "
      f"unpriceable: {sum(1 for r in rows if r.get('pnl') is None and r['lab']!='ext_refused')}\n")

def agg(g, lab):
    if not g:
        print(f"  {lab:<26} n=  0"); return 0.0
    p = sum(x["pnl"] for x in g)
    print(f"  {lab:<26} n={len(g):>3}  total ${p:>9.2f}  mean ${p/len(g):>7.2f}  "
          f"win {100*sum(1 for x in g if x['pnl']>0)/len(g):>5.1f}%")
    return p

print("=" * 88)
print("WHAT THE CAPS REFUSED (priced through the honest harness)")
print("=" * 88)
tot = agg(priced, "ALL capped fires")
print()
for lab in ("NEW-SETUP", "RE-ARM", "FIRST"):
    agg([r for r in priced if r["lab"] == lab], lab)

print("\n" + "=" * 88)
print("FCUV ALONE vs EVERYTHING ELSE  (gate 2: the motivating case must not carry the result)")
print("=" * 88)
agg([r for r in priced if r["tk"] == "FCUV"], "FCUV capped fires")
agg([r for r in priced if r["tk"] != "FCUV"], "all other names")

print("\nby ticker (top 8 by |total|):")
g = collections.defaultdict(list)
for r in priced: g[r["tk"]].append(r)
for tk, v in sorted(g.items(), key=lambda kv: -abs(sum(x["pnl"] for x in kv[1])))[:8]:
    p = sum(x["pnl"] for x in v)
    print(f"  {tk:<6} n={len(v):>3}  ${p:>9.2f}  "
          f"(NEW-SETUP {sum(1 for x in v if x['lab']=='NEW-SETUP')} / "
          f"RE-ARM {sum(1 for x in v if x['lab']=='RE-ARM')})")

print("\n" + "=" * 88)
print("VERDICT")
print("=" * 88)
if tot < 0:
    print(f"  The refused cohort is NEGATIVE (${tot:.2f}). THE CAPS SAVED MONEY on 7/31.")
    print("  -> FAILURE CONDITION MET: the §I1 complaint is answered for this day. Caps hold.")
else:
    ns = sum(x["pnl"] for x in priced if x["lab"] == "NEW-SETUP")
    ra = sum(x["pnl"] for x in priced if x["lab"] == "RE-ARM")
    print(f"  The refused cohort is POSITIVE (${tot:.2f}): NEW-SETUP ${ns:.2f} / RE-ARM ${ra:.2f}.")
    print("  -> If NEW-SETUP carries it, the fix is a STRUCTURE-CHANGE REQUIREMENT, not a bigger cap.")
print("\n  ONE DAY, n=%d. Not a verdict on the caps — a first pricing." % len(priced))

json.dump(rows, open(pathlib.Path(__file__).with_name("capped_fires_priced_20260731.json"), "w"), indent=1)
print("  rows -> capped_fires_priced_20260731.json")
