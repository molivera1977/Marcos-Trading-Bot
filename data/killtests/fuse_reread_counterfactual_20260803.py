"""FUSE 8/3 COUNTERFACTUAL: what map would the FIXED re-read pipeline have drawn, and would the
two afternoon chart-lane losers have fired?

METHOD (no hindsight): rebuild FUSE's 1-min chart from the ALP10S 10s store TRUNCATED at the
re-read moments (10:40 = first past-map probe with working eyes; 14:39 = last probe before the
14:42 flat_top fire), run the REAL reread vision call on each truncated chart with the real prior
map as context, and evaluate the actual 14:42 ($1.465 flat_top) and 15:19 ($1.4611 ma_pullback)
fires against the 14:39 map: chart gate (price must have BROKEN the fresh break), runway >=1R to
the fresh targets. Two billed vision calls; results printed, humans judge.
"""
import os, sys, json, urllib.request, pathlib, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import newcomer_vision_reader as R

U = "https://zestful-intuition-production-b16a.up.railway.app"
R.DAY = "2026-08-03"

full = R._min1_from_10s("FUSE")
print(f"10s-store 1-min bars: {len(full)}  (first {full[0]['time'][11:16]}, last {full[-1]['time'][11:16]})")

PRIOR = {"break": 1.03, "confirm": 1.04, "targets": [1.08, 1.15], "stop": 0.97}

def read_at(cut_hm):
    R._min1 = lambda tk, _c=cut_hm: [b for b in full if b["time"][11:16] <= _c]
    png, meta = R.render_intraday_png("FUSE")
    if not png:
        return None, meta
    import anthropic, base64
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    since = f"day high {meta['day_high']}, last {meta['last']}, vwap {meta['vwap']}"
    prompt = R.REREAD_PROMPT.format(ticker="FUSE", prior=json.dumps(PRIOR), since=since,
                                    meta=json.dumps(meta))
    img = base64.standard_b64encode(png).decode()
    msg = client.messages.create(model=R.MODEL, max_tokens=1100, messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}},
        {"type": "text", "text": prompt}]}])
    raw = "".join(bl.text for bl in msg.content if getattr(bl, "type", None) == "text").strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "", 1).strip() if "```json" in raw else raw.split("```")[1].strip()
    rd = json.loads(raw)
    ok, why = R.validate_read(rd, meta["last"])
    return rd, {"meta": meta, "valid": ok, "why": why}

for cut in ("10:40", "14:39"):
    rd, info = read_at(cut)
    print(f"\n== re-read with chart truncated at {cut} ==")
    if rd is None:
        print("render failed:", info); continue
    print(f"  chart last: {info['meta']['last']}  day high so far: {info['meta']['day_high']}")
    print(f"  MAP: break {rd.get('break_level')} confirm {rd.get('confirm_level')} "
          f"stop {rd.get('stop_level')} targets {rd.get('targets')} [{rd.get('verdict')}/{rd.get('confidence')}]")
    print(f"  validate vs live: {info['valid']} ({info['why']})")
    if cut == "14:39" and info["valid"]:
        brk = float(rd.get("break_level") or 0)
        tgts = sorted(float(x) for x in (rd.get("targets") or []))
        for label, e, s in (("14:42 flat_top", 1.465, 1.3624), ("15:19 ma_pullback", 1.4611, 1.3662)):
            gate = "ALLOW" if (brk > 0 and e > brk) else "BLOCK (no break of fresh level)"
            up = [t for t in tgts if t > e]
            rw = (up[0] - e) / (e - s) if up else None
            rw_v = "fail-open (above all targets)" if rw is None else f"{rw:.2f}R " + ("PASS" if rw >= 1 else "REJECT")
            print(f"  {label} @ {e}: chart_gate={gate} | runway={rw_v}")
