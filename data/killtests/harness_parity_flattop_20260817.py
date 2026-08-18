#!/usr/bin/env python3
"""FLAT_TOP / BREAK-ATTACK PARITY — 2026-08-17 (batch D).

Measures the extracted break-attack core (marcos_trading_bot.flat_top_step, driven through
live_harness.replay_flat_top) against what the LIVE bot actually did on 8/17, the same way
the other lanes were measured in harness_parity_20260817.py: same name, |dt| <= 300s.

LIVE TRUTH  data/killtests/flattop_live_0817.json — the decisions_archive rows with
            status='break_attack' (the row the live loop writes at the moment of the attack
            verdict, carrying price/w_high/w_low/time_hm). Pulled 2026-08-17 night from
            /api/decisions_archive?date=2026-08-17&status=break_attack.
TAPE        data/killtests/bars10s_0817_full/*.json (Alpaca SIP 10s).

METHOD BOUND, stated not hidden: 8/17 predates the A2 provenance stamps, so this is a
time+level APPROXIMATION, not an exact-fed-stream equivalence — the same bound every other
lane's 8/17 number carries. Additionally the live M1 bars came from the broker while the
replay rolls its 1-min bars from our 10s SIP capture; where the two tapes disagree on a
base's extremes, the levels differ (IPST below) and that is a FEED difference, not a
detector difference. It cannot be attributed from this day's data.

    python3 data/killtests/harness_parity_flattop_20260817.py
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_harness as H          # noqa: E402

DAY = "2026-08-17"
TAPE = HERE / "bars10s_0817_full"
LIVE_F = HERE / "flattop_live_0817.json"
TOL_SECS = 300


def main():
    live = json.loads(LIVE_F.read_text())
    live_by_sym = {}
    for r in live:
        live_by_sym.setdefault(r["ticker"], []).append(r)

    rows, matched, extra_names = [], 0, []
    for f in sorted(TAPE.glob("*.json")):
        sym = f.stem
        raw = json.loads(f.read_text())
        try:
            vw = H.running_vwap(raw)
        except H.HarnessError:
            continue
        fires = H.replay_flat_top(
            sym, raw, DAY,
            vwap_provider=lambda s, i, b, l, vw=vw: vw[i],
            ctx_provider=lambda s, i, b, l: {"armed": False, "time_hm": H.et_hm(b[0]),
                                             "ma_first": False, "ma_only_window": False})
        att = [x for x in fires if x["action"] == "attack" and x["ok"]]
        if not att:
            continue
        if sym not in live_by_sym:
            extra_names.append((sym, len(att), H.et_hm(att[0]["bar"][0])))
            continue
        for lr in live_by_sym[sym]:
            hh, mm, ss = (int(x) for x in lr["time"][:8].split(":"))
            # archive 'time' is ET 12-hour with an AM/PM suffix; every break-attack row is AM
            live_secs = hh * 3600 + mm * 60 + ss
            best = None
            for a in att:
                import datetime as dt
                t = dt.datetime.fromtimestamp(a["bar"][0], H.EASTERN)
                d = abs(t.hour * 3600 + t.minute * 60 + t.second - live_secs)
                if best is None or d < best[0]:
                    best = (d, a)
            d, a = best
            hit = d <= TOL_SECS
            matched += 1 if hit else 0
            rows.append({
                "ticker": sym, "live_time": lr["time"], "live_price": lr["price"],
                "live_w_high": lr["w_high"], "live_w_low": lr["w_low"],
                "replay_time": H.et_hm(a["bar"][0]), "replay_price": round(a["price"], 4),
                "replay_w_high": round(a["w_high"], 4), "replay_w_low": round(a["w_low"], 4),
                "replay_stop": a["stop"], "dt_secs": d, "matched": hit,
                "w_high_exact": abs(a["w_high"] - lr["w_high"]) < 0.005,
                "w_low_exact": abs(a["w_low"] - lr["w_low"]) < 0.005,
                "replay_attacks_on_name": len([x for x in att]),
            })

    n = len(live)
    out = {
        "lane": "flat_top", "day": DAY, "live_fires": n, "matched": matched,
        "parity_pct": round(100.0 * matched / n, 1) if n else None,
        "w_high_exact": sum(1 for r in rows if r["w_high_exact"]),
        "w_low_exact": sum(1 for r in rows if r["w_low_exact"]),
        "method": "time_and_price_approximation",
        "tolerance_secs": TOL_SECS,
        "names_with_replay_attacks_and_no_live_row": extra_names,
        "rows": rows,
    }
    print(json.dumps(out, indent=1))
    (HERE / "harness_parity_flattop_20260817_out.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
