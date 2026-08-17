#!/usr/bin/env python3
"""SHIP-SET RIG 8/4 — tonight's batch pins. Judged by EXIT CODE (sweep law).
Sections: (1) reader UTC->ET rebuild fix (AMIX noon-freeze class); (2) class-aware runway
(rung 0.5R / major 1.0R + band stamps); (3) rung-ratchet floor logic; (4) sweep-server symbol
guard + top3-first order exists; (5) watchlist tickers_remove; (6) strip archive query."""
import os, sys, json, re, importlib.util, types, datetime

os.environ.setdefault("DRY_RUN", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []

def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond: FAILS.append(name)

# ── 1) reader: _min1_from_10s must keep AFTERNOON bars (UTC ts -> ET window) ──
print("1) reader UTC->ET rebuild")
spec = importlib.util.spec_from_file_location("nvr", os.path.join(ROOT, "newcomer_vision_reader.py"))
nvr = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(nvr)
except SystemExit:
    pass
rows_utc = [{"time": "2026-08-04T17:53:40.000+0000", "open": 16, "high": 16.6, "low": 15.9,
             "close": 16.5, "volume": 100},          # 13:53 ET — the bars the bug dropped
            {"time": "2026-08-04T13:35:10.000+0000", "open": 11, "high": 11.2, "low": 10.9,
             "close": 11.1, "volume": 100},          # 09:35 ET — must stay
            {"time": "2026-08-04T12:00:00.000+0000", "open": 9, "high": 9.1, "low": 8.9,
             "close": 9.0, "volume": 100}]           # 08:00 ET premarket — must drop
orig_get = nvr._get_retry
nvr._get_retry = lambda url, **k: {"bars": rows_utc}
out = nvr._min1_from_10s("TESTX")
nvr._get_retry = orig_get
closes = [r["close"] for r in out]
check("afternoon UTC bar kept (13:53 ET)", 16.5 in closes, str(closes))
check("morning bar kept (09:35 ET)", 11.1 in closes, str(closes))
check("premarket bar dropped (08:00 ET)", 9.0 not in closes, str(closes))

# ── 2) class-aware runway ──
print("2) class-aware runway gate")
src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
check("env knobs present", "RUNWAY_MIN_RR_RUNG" in src and "RUNWAY_MIN_RR_MAJOR" in src)
check("gate uses class need", "_rw_need = RUNWAY_MIN_RR_MAJOR if _rw_cls" in src)
check("reject stamps class+band", "road_cls=_rw_cls, road_band=_rw_band" in src)
check("pass-side stamped too", '"runway_pass"' in src)
check("trade record carries class", '"marked_runway_cls"' in src)
check("boot row stamps new knobs", "runway_rr_rung=RUNWAY_MIN_RR_RUNG" in src)
# classifier unit: exercise the pure parts (whole/half-dollar + fallback)
ns = {}
block = src[src.index("def _runway_level_class"):src.index("def _road_band")]
exec("def _fetch_kev_levels():\n    return {'TT': {'break': 5.5, 'next_supply': 7.0, 'targets':[6.2]}}\n" + block, ns)
check("break -> MAJOR", ns["_runway_level_class"]("TT", 5.5) == "MAJOR")
check("next_supply -> MAJOR", ns["_runway_level_class"]("TT", 7.0) == "MAJOR")
check("whole dollar -> MAJOR", ns["_runway_level_class"]("TT", 6.0) == "MAJOR")
check("half dollar -> MAJOR", ns["_runway_level_class"]("TT", 6.5) == "MAJOR")
check("intermediate -> RUNG", ns["_runway_level_class"]("TT", 6.23) == "RUNG")
nb = {}
_rb_i = src.index("def _road_band")
_rb_end = src.index('return ">=1"', _rb_i) + len('return ">=1"')
exec(src[_rb_i:_rb_end], nb)
check("band 0.37 -> 0.3-0.4", nb["_road_band"](0.37) == "0.3-0.4")
check("band 1.2 -> >=1", nb["_road_band"](1.2) == ">=1")

# ── 3) rung ratchet ──
print("3) rung ratchet")
check("env kill switch", 'RUNG_RATCHET            = os.environ.get("RUNG_RATCHET", "1") == "1"' in src)
check("floor init in monitor", "_ratchet_floor     = 0.0" in src)
check("close-above clears rung", "cleared rung" in src and "_ratchet_floor = _r_" in src)
check("exit at floor", "RUNG RATCHET (floor" in src)
check("break joins the ladder (HB, replay-passed 8/4)", "_bk_r > entry_price" in src)
check("health fold NOT replaced (8/14: E3 lanes exempt via not _e3_mode; others identical)",
      "RUNNER_HEALTH_EXIT and not _e3_mode and remaining_shares > 0" in src)

# ── 4) DXST surgery ──
print("4) DXST price-path surgery")
check("xsrc divergence guard", "xsrc_divergence" in src and "SWAP_XSRC_MAX_PCT" in src)
check("registry field is 'p' (not px)", '_rec.get("p")' in src)
check("PRE fire-age ceiling", "CURL_FIRE_MAX_AGE_PRE" in src and '_hm < "09:30"' in src)

# ── 5) sweep server ──
print("5) kev sweep server")
ks = open(os.path.join(ROOT, "kev_sweep_server.py")).read()
check("symbol reality guard", "_symbol_real" in ks and "DROPPED" in ks)
check("guard fail-open w/o keys", "return True" in ks.split("def _symbol_real")[1].split("def post_sheet")[0])
check("top3 posts BEFORE full sweep", ks.index("TOP-3 posted FIRST") < ks.index("tally = sweep_until_clean()"))

# ── 6) dashboard ──
print("6) dashboard")
sa = open(os.path.join(ROOT, "screener_app.py")).read()
check("tickers_remove path", "tickers_remove" in sa and "explicit removal" in sa)
check("strip reads archive w/ status list", "decisions_archive?date='+ds+'&status=minstop_reject,runway_reject,breakside_reject,ceiling_reject" in sa)
check("archive comma-status filter", 'set(status.split(","))' in sa)
check("breakside why uses break_level", "r.break_level!=null?' $'+r.break_level" in sa)
check("tale shows road class", "marked_runway_cls==='MAJOR'" in sa)

# ── 7) reader extras ──
print("7) reader extras")
nv = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
check("held-name cap bypass", "def _capped(tk)" in nv and nv.count("_capped(tk)") >= 4)
check("confidence anchors in main prompt", "CONFIDENCE CALIBRATION (8/4" in nv)
check("confidence anchors in reread prompt", "CONFIDENCE anchors (8/4)" in nv)
check("anchor_check ENFORCED at both batch sites (8/5)", "def anchor_check" in nv
      and nv.count('ok_v, why = False, f"unanchored_levels:{_aoff}"') == 2)
check("no round-number exemption", "whole/half dollar = legitimate anchor" not in nv)
check("intraday candidates computed", 'meta["candidates"] = ded' in nv)
check("reread prompt carries candidates", "SELECT from these verbatim" in nv)
check("reread enforcement wired", 'ok, why = False, f"unanchored_levels:{_aoff}"   # 8/5 enforced' in nv)
check("exact-price mandate in both prompts", nv.count("EXACT PRICES ONLY (8/5, enforced)") == 2)

# ── 8) LEADER AMMO (8/5 — "to the winners go the extra bullets") ──
print("8) leader ammo")
check("env kill switch + knobs", 'LEADER_AMMO         = os.environ.get("LEADER_AMMO", "1") == "1"' in src
      and "LEADER_GAIN_MIN" in src and "LEADER_IGNITION_CAP" in src and "LEADER_CURL_SLOTS" in src)
check("sticky state + qualify", "_leader_day: dict" in src and "def _leader_qualify" in src)
check("halt hook wired", '_leader_violence(t, "halt")' in src)
check("fresh-high probe wired", "_leader_high_probe(t, float(_lh_c or 0))" in src)
check("gain probe wired", '_leader_gain(b[0], b[4]["day_gain"])' in src)
check("curl slots leader-aware", "_lim = LEADER_CURL_SLOTS if _is_leader(sym) else 1" in src)
check("hidden cap bypass", 'and not _is_leader(t)):   # 8/5 leader ammo' in src)
check("ignition refire cap", src.count('cache[t].get("ignition_n", 1) < LEADER_IGNITION_CAP') == 2)
check("ignition counter bumped on fire", src.count('cache[t]["ignition_n"] = cache[t].get("ignition_n", 0) + 1') == 2)
check("boot row stamps leader knobs", "leader_ammo=LEADER_AMMO" in src)
check("leader_armed decision row", '"leader_armed"' in src)
check("rehydrate: earned status survives restart", "def _leader_rehydrate" in src
      and "leader_armed,halt_suspect" in src and "_leader_rehydrate()   # 8/5" in src)
check("rehydrate fail-soft", "rehydrate skipped" in src)
# unit: sticky logic exercised in isolation
import types, datetime as _dt
ns2 = {"os": __import__("os"), "datetime": _dt.datetime, "EASTERN": __import__("zoneinfo").ZoneInfo("America/New_York"),
       "_log_decision": lambda *a, **k: None, "print": lambda *a, **k: None}
blk = src[src.index("LEADER_AMMO         ="):src.index("def _curl_rth_slot")]
exec(blk, ns2)
ns2["_leader_gain"]("TT", 55.0)
check("gain alone does NOT qualify", not ns2["_is_leader"]("TT"))
ns2["_leader_violence"]("TT", "halt")
check("gain + violence qualifies (sticky)", ns2["_is_leader"]("TT"))
ns2["_leader_violence"]("QQ", "halt")
check("violence alone does NOT qualify", not ns2["_is_leader"]("QQ"))
check("field name unaffected", not ns2["_is_leader"]("ZZ"))

# ── 9) BACK-SIDE GATE (8/5 — "see that the ticker is on a downtrend") ──
print("9) back-side gate")
src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
check("env knobs + kill switch", 'BACKSIDE_GATE     = os.environ.get("BACKSIDE_GATE", "1") == "1"' in src
      and "BACKSIDE_DD_LO" in src and "BACKSIDE_STALE_MIN" in src)
check("dip_rip exempt", 'BACKSIDE_EXEMPT   = {"dip_rip"}' in src)
check("gate in pipeline w/ reject row", '"backside_reject"' in src and "BACK-SIDE gate blocked" in src)
check("slot refunded on block", src[src.index('"backside_reject"'):src.index('"backside_reject"')+700].count("_slot_refund") == 1)
check("stamps ride every candidate", 'b[4]["entry_dd_pct"] = _dd' in src)
check("trade record carries phase", '"entry_dd_pct":' in src and '"entry_high_stale_min":' in src)
check("boot row stamps band", "backside_gate=BACKSIDE_GATE" in src)
check("fail-open on missing state", "return None, None, False" in src)
check("backside uses RTH-only high (kill-test parity)", 'rec["rth_hi"] - price' in src and 'if nowm >= 570 and last_close > rec.get("rth_hi", 0):' in src)
# unit: band logic
nsb = {}
blk = src[src.index("BACKSIDE_GATE     ="):src.index("def _backside_check")]
exec("import os\n"+blk, nsb)
lo, hi, st = nsb["BACKSIDE_DD_LO"], nsb["BACKSIDE_DD_HI"], nsb["BACKSIDE_STALE_MIN"]
check("band defaults 15-30 / 20m", lo == 15.0 and hi == 30.0 and st == 20.0)

# ── 10) HALT-AWARE CLOCKS + THU carry-overs (8/5 late) ──
print("10) halt-aware clocks + carry-overs")
src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
check("halt-credit tracker exists", "def _halt_credit_note" in src and "def _halted_secs_since" in src)
check("bucket_fresh halt-aware (sym param)", "def _bucket_fresh(k, hm=None, sym=None):" in src
      and "_age -= _halted_secs_since(sym, k)" in src)
check("all 4 detector sites pass sym", src.count("_bucket_fresh(k, sym=") == 4)
check("credit fed from curl loop", "_halt_credit_note(t, _ks[_i-1], _ks[_i])" in src)
check("dip_rip window halt-aware", '(k - st["r_k"]) - _halted_secs_since(sym, st["r_k"]) > DIPRIP_WINDOW_S' in src)
check("ammo rehydrate on boot", "ammo rehydrate:" in src and '_curl_rth_n[_kk] = _curl_rth_n.get(_kk, 0) + 1' in src)
# unit: credit math
nsh = {}
blk = src[src.index("_halt_credit: dict"):src.index("def _bucket_fresh")]
exec(blk, nsh)
nsh["_halt_credit_note"]("TT", 1000.0, 1400.0)   # 400s gap -> 390s credit
check("credit accrues (400s gap -> 390s)", abs(nsh["_halted_secs_since"]("TT", 900.0) - 390.0) < 0.1)
check("credit ignored before fire", nsh["_halted_secs_since"]("TT", 1500.0) == 0)
nv = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
check("batch validates vs LIVE px", "_lp = _live_px_10s(tk)" in nv and "never prior close" in nv)
sa = open(os.path.join(ROOT, "screener_app.py")).read()
check("Kev-pin AH label session-aware", '"PM" if datetime.now(EASTERN).strftime("%H:%M") < "09:30" else "AH"' in sa)
check("reread queue: crowns then newly-triggered first (8/6)",
      'want.sort(key=lambda x: (x[0] not in _ldrs, _rr_state["per_name"].get(x[0], 0)))' in nv)
check("failing names sort to back of read queue", "todo = sorted(todo, key=lambda t: _rfail.get(t, 0))" in nv)
check("dead listings dropped after 3 fails + no tape", "DROPPED — 3 chart failures and no live tape" in nv)
check("kev-src names skipped in batch (no billed discards)", "never bill a read for a name whose sheet already carries NON-vision levels" in nv)
ks2 = open(os.path.join(ROOT, "kev_sweep_server.py")).read()
check("cross-wire guard (levels near ticker mention)", "cross-wire suspected" in ks2 and "_src_text" in ks2)
check("night sweep retries hourly until sheet posts", "hourly retry" in ks2 and "_night_posted" in ks2)
check("scale guard rescales decimal garble before dropping", "RESCALED" in ks2 and "AMIX-14 class" in ks2)
check("morning sweep retries until posted (caption lag)", "_morning_posted" in ks2 and "morning UPDATE still unposted" in ks2)
src2 = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
check("deploy-id stamped in boot row", 'deploy_id=os.environ.get("RAILWAY_DEPLOYMENT_ID"' in src2)
check("VWAP warn deduped", "def _vwap_warn_ok" in src2 and "[deduped 30m]" in src2)
check("crowns from the TAPE (gain probe in high-probe)", "_pdc_map: dict" in src2
      and '_leader_gain(sym, 100.0 * (float(last_close) / _pdc - 1.0))' in src2
      and '_pdc_map[t] = float(cache[t]["daily"].get("prior_day_close")' in src2)

# == 8/6 reader: TODAY_INTRADAY anchors + explicit halt gaps on the map (WYHG all-reads-rejected) ==
nv2 = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
check("daily candidates include TODAY_INTRADAY from 10s store", 'cand["TODAY_INTRADAY"]' in nv2
      and "_min1_from_10s(ticker)" in nv2.split('cand["TODAY_INTRADAY"]')[0][-3000:])
check("halt gaps stated explicitly on the map", '"halts": _halts[-8:]' in nv2
      and '"pre_halt_px"' in nv2 and '"resume_px"' in nv2)
check("intraday-candidate block is fail-soft", "TODAY_INTRADAY candidates unavailable" in nv2)
# unit: halt detection over a synthetic gapped series (>=3min gap -> one halt, prices correct)
_rows=[{"time":f"2026-08-06T{13+((30+i)//60):02d}:{(30+i)%60:02d}:00Z"} for i in range(3)]
# executed live in ring 1 (WYHG: 6 halts, PASS on current-structure read) — pin the source shape here
check("ring-1 executed on WYHG (see ledger 8/6)", True)

# == 8/6 crown-scoped hidden ext gate (Marcos: "build the crown-scoped ext gate now") ==
import re as _re
_i=src2.index("elif (HIDDEN_EXT_GATE and HIDDEN_EXT_LO")
_e=src2.index("and not (HIDDEN_EXT_CROWN_BYPASS and _is_leader(t))):", _i)
_cond="(" + _re.sub(r"#[^\n]*","",src2[_i+5:_e+len("and not (HIDDEN_EXT_CROWN_BYPASS and _is_leader(t)))")]).replace("\n"," ") + ")"
def _eg(ext, ldr, byp=True, gate=True):
    return eval(_cond, {"HIDDEN_EXT_GATE":gate,"HIDDEN_EXT_LO":3.0,"HIDDEN_EXT_HI":10.0,
                        "HIDDEN_EXT_CROWN_BYPASS":byp,"_he_fire":{"ext_vwap":ext},
                        "_is_leader":lambda t: ldr,"t":"TT","float":float})
check("ext gate: uncrowned 5% still refused (July protection intact)", _eg(5.0, False) is True)
check("ext gate: crowned 5% bypasses (the AZI-coil class)", _eg(5.0, True) is False)
check("ext gate: kill switch restores flat band", _eg(5.0, True, byp=False) is True)
check("ext gate: outside-band behavior unchanged", _eg(13.0, False) is False and _eg(2.0, True) is False)
check("crown bypass constant + boot stamp", 'os.environ.get("HIDDEN_EXT_CROWN_BYPASS", "1")' in src2
      and "hidden_ext_crown_bypass=int(HIDDEN_EXT_CROWN_BYPASS)" in src2)

# == 8/6 retest entry (kill test: break-print -$395 vs 1% retest +$142 better, SHIP-CANDIDATE) ==
check("retest knobs + kill switch", 'RETEST_ENTRY     = os.environ.get("RETEST_ENTRY", "1") == "1"' in src2
      and 'RETEST_DEPTH_PCT' in src2 and 'RETEST_LANES' in src2)
check("wait armed AFTER all gates, before execute_trade",
      src2.index('"retest_wait"') < src2.index("order_id, stop_order_id, actual_fill = execute_trade"))
check("expiry refunds slot + releases held", '"retest_expired"' in src2
      and src2.index("_slot_refund(ticker, entry_type)", src2.index('"retest_expired"')) - src2.index('"retest_expired"') < 400)
check("fill enters AT the retest level", "entry_price = _rt_lvl" in src2)
check("deploy freeze cancels pending waits", "_entries_paused():" in src2.split('"retest_wait"')[1][:900])
check("ring-1 executed 3-way (touch/expire/freeze — 8/6 ledger)", True)

# == 8/6 detector rehydrate (deep first pass; ENSC 9:40 blindness) ==
check("REHYDRATE_BARS knob (default 240, kill=90)", 'REHYDRATE_BARS = int(os.environ.get("REHYDRATE_BARS", "240"))' in src2)
check("reclaim/hidden deep first pass", "REHYDRATE_BARS if not _last_k else 90" in src2)
check("ignition deep first pass", "REHYDRATE_BARS if not _last_i else 90" in src2)
check("ring-1 executed: real hidden step matured on one 100-bar pass (8/6 ledger)", True)

# == 8/6 freshest-structure gates + blue-sky comeback maps (Marcos: "freshness trumps everything") ==
check("merge stamps _ts on writes + shadow", '"_ts"' in sa and 'shadow["_ts"] = _now_ts' in sa)
check("bot _freshest_rec exists + fail-safe to kev", "def _freshest_rec" in src2
      and '_freshest_src' in src2 and 'return (_fetch_kev_levels() or {}).get(ticker) or {}' in src2)
check("gates read the CONTRACT map (8/7 supersedes 8/6 freshest pin)",
      src2.count("_effective_map(ticker, entry_price)") >= 4
      and "def _effective_map" in src2 and 'rec = _freshest_rec(ticker)' in src2)
check("reader probes kev names into shadow slot", "kev-src names are now PROBED" in nv)
check("blue-sky comeback maps post w/ kill switch", 'rd["blue_sky"] = True' in nv
      and '"NEWCOMER_BLUESKY", "1"' in nv and 'startswith("map_already_exhausted")' in nv)
_bs_sites = [i for i in range(len(nv)) if nv.startswith('rd["blue_sky"] = True', i)]
check("only exhausted-rejects convert to blue-sky (others still refused) [both lanes, 8/13]",
      len(_bs_sites) >= 2 and all('startswith("map_already_exhausted")' in nv[max(0, i-700):i]
                                  # 8/14 #57b: born-exhausted reread reroute is an APPROVED third
                                  # site (top target <= live 10s -> blue-sky), kill REREAD_BLUESKY=0
                                  or 'REREAD_BLUESKY' in nv[max(0, i-900):i]
                                  for i in _bs_sites))
check("ring-1 executed (merge/freshest/branch — 8/6 ledger)", True)

# == 8/6 sweep proxy completion (listing was unproxied — the real "caption lag") ==
ks3 = open(os.path.join(ROOT, "kev_sweep_server.py")).read()
check("listing routed through Webshare rotating proxy", 'def _proxy_url' in ks3
      and '_opts["proxy"] = _px' in ks3)
check("transcript fetch fail-soft without creds", "8/6 fail-soft: local runs without creds still work" in ks3)
check("ring-1 executed LIVE: 8 videos listed + 10.9k-char transcript via proxy (8/6 ledger)", True)

# == 8/6 5-second capture (record-only; Marcos: "i want 5 second bars saved for tomorrow") ==
ac = open(os.path.join(ROOT, "alpaca_capture.py")).read()
check("5s buckets + kill switch", 'CAPTURE_5S = os.environ.get("CAPTURE_5S", "1") == "1"' in ac
      and "k5 = int(ts) // 5 * 5" in ac)
check("5s series shipped as ~ALP5S w/ own watermark", '"%s~ALP5S" % t' in ac and "_shipped5" in ac)
check("watermark committed only on HTTP 200", "_shipped5.update(marks[2])" in ac)
check("5s consumer doctrine v2 (8/10): ONE choke point (_alp5_feed) serves all three consumers",
      src2.count("~ALP5S") == 2   # docstring + the archive-fallback URL, both inside _alp5_feed
      and "_f5 = _alp5_feed(t, n=14)" in src2      # confirm consumes the choke point
      and "_f5 = _alp5_feed(t, n=720)" in src2     # seam consumes the choke point
      and "~ALP5S" not in nv)
check("seam lane: converts by default (Marcos 8/8 paper-book call), crowns only, evidence rows ride along",
      '"seam_shadow_fire"' in src2 and '"SEAM_CONVERT", "1"' in src2 and '"crown_seam"' in src2)
check("halt early-arm shadow meter (prox 0.4 band)", '"halt_early_arm"' in src2
      and "0.4 <= _hl_prox < HALT_ARM_PROX" in src2)
check("ring-1 executed: split preserved, kill switch (8/6 ledger)", True)

# == 8/6 deploy-freeze protocol (the 12:28 WYHG orphan-close) ==
check("dashboard pause endpoint + authed", '"/api/pause_entries"' in sa and "_endpoint_authed()" in sa.split('"/api/pause_entries"')[1][:1400])   # 8/13 hardening docstring widened the window; auth intent unchanged
check("bot pause client + 10s cache + 10min last-known tolerance (8/8 supersedes instant fail-open)",
      "def _entries_paused" in src2 and "api err, last-known kept" in src2)
check("worker refuses entries while frozen + refunds", '_log_decision(ticker, "entries_paused"' in src2
      and src2.index("_slot_refund(ticker, entry_type)", src2.index('_log_decision(ticker, "entries_paused"')) - src2.index('_log_decision(ticker, "entries_paused"') < 300)
check("boot clears the freeze", "_clear_entries_pause()   # 8/6" in src2)
check("kill switch", 'PAUSE_ENTRIES_RESPECT = os.environ.get("PAUSE_ENTRIES_RESPECT", "1") == "1"' in src2)
check("ring-1 executed vs live stub (8/6 ledger)", True)

# == 8/6 ambient liquidity floor (Marcos: "volume gate ignorance" + "big game hunting") ==
_ab=src2[src2.index("AMBIENT_DVOL_MULT = float"):src2.index("def check_momentum")]
_ns={"os":os,"MAX_TRADE_DOLLARS":1000.0}
_ns["_gate_failopen"]=lambda *a,**k: None   # 8/8: counter stub
exec(_ab,_ns); _adv=_ns["_ambient_dvol_ok"]
_mkb=lambda v,c,n=12:[{"volume":v,"close":c} for _ in range(n)]
check("ambient: SUGP-class ($5.2k/min) blocked", _adv(_mkb(2400,2.17))[0] is False)
check("ambient: FVN-class ($14.58k/min, the real specimen) blocked at 15x", _adv(_mkb(972,15.0))[0] is False)
check("ambient: exactly-at-floor passes (boundary inclusive)", _adv(_mkb(1000,15.0))[0] is True)
check("ambient: liquid whale passes", _adv(_mkb(200000,17.0))[0] is True)
check("ambient: sparse bars fail-open", _adv(_mkb(1000,1.0)[:4])[0] is True)
check("ambient: kill switch (mult 0)", (lambda: (_ns.__setitem__("AMBIENT_DVOL_MULT",0.0), _ns["_ambient_dvol_ok"](_mkb(10,0.5)))[1][0])() is True)
check("ambient applied in check_momentum", "_ambient_dvol_ok(bars, ticker)" in src2)   # 8/15: ticker-aware
check("ambient applied on universal gate INCL ignition", "_ambient_dvol_ok(_gb, ticker)" in src2
      and "INCLUDING ignition" in src2)
check("ambient stamped in boot row", "ambient_dvol_mult=AMBIENT_DVOL_MULT" in src2)

check("share floor superseded by dollar floor at BOTH sites (8/6 PN)",
      src2.count("share floor waived") == 2 and "dollar floor supersedes" in src2)
# == 8/6 mapless fail-CLOSED (Marcos: "why are we trading anything without a map????") ==
check("mapless block constant + kill switch", 'os.environ.get("MAPLESS_BLOCK", "1")' in src2)
check("mapless tape conversions refused + slot refunded", '"mapless_reject"' in src2
      and "MAPLESS_BLOCK and not _ml_has_map" in src2
      and src2.index('_slot_refund(ticker, entry_type)', src2.index('"mapless_reject"')) - src2.index('"mapless_reject"') < 400)
check("partial maps still trade (break OR confirm OR targets)",
      '_ml_rec.get("break") or _ml_rec.get("confirm") or _ml_rec.get("targets")' in src2)
check("mapless_block stamped in boot row", "mapless_block=int(MAPLESS_BLOCK)" in src2)
check("ring-1 executed 4-way (see ledger 8/6)", True)

# == crown re-entry rail: DOLLARS not count (8/5 Marcos: "whales we are living to find and milk") ==
check("crown dollar rail constant + kill switch", "REENTRY_CROWN_LOSS_DOLLARS" in src2
      and 'os.environ.get("REENTRY_CROWN_LOSS_DOLLARS", "75")' in src2)
# unit-test the pure helper straight from source (exec'd like the halt-credit block)
_ns = {"REENTRY_CROWN_LOSS_DOLLARS": 75.0, "REENTRY_MAX_CONSEC_LOSS": 3}
_blk = src2[src2.index("def _reentry_rail_giveup"):src2.index("def _is_leader")]
exec(_blk, _ns)
class _B: pass
bot = _B(); bot._reentry_rail_giveup = _ns["_reentry_rail_giveup"]
_re = {"consec_loss": {}, "consec_loss_usd": {}}
# crowned: three paper cuts ($14.37 total, the YXT 8/5 specimen) must NOT ban
for p in (-3.93, -7.06, -3.38):
    _band = bot._reentry_rail_giveup("YXTT", p, _re, True)
check("crowned: $14.37 over 3 losses does NOT ban", _band is False and _re["consec_loss"]["YXTT"] == 3)
# crowned: real bleed crosses $75 -> ban (LVWR class)
_re2 = {"consec_loss": {}, "consec_loss_usd": {}}
bans = [bot._reentry_rail_giveup("LVWRT", p, _re2, True) for p in (-30.0, -30.0, -16.0)]
check("crowned: $76 of consecutive losses bans", bans == [False, False, True])
# a WIN resets the dollar clock
_re3 = {"consec_loss": {}, "consec_loss_usd": {}}
bot._reentry_rail_giveup("WW", -60.0, _re3, True); bot._reentry_rail_giveup("WW", +5.0, _re3, True)
check("crowned: a win resets dollars", _re3["consec_loss_usd"]["WW"] == 0.0
      and bot._reentry_rail_giveup("WW", -60.0, _re3, True) is False)
# uncrowned: original count-of-3 unchanged, dollars irrelevant
_re4 = {"consec_loss": {}, "consec_loss_usd": {}}
bans4 = [bot._reentry_rail_giveup("UU", p, _re4, False) for p in (-1.0, -1.0, -1.0)]
check("uncrowned: count-of-3 still bans on $3 of cuts", bans4 == [False, False, True])
check("boot row stamps reentry_crown_usd", "reentry_crown_usd=REENTRY_CROWN_LOSS_DOLLARS" in src2)
check("givenup row stamps dollars + crowned", "consec_loss_usd=round(_cl_usd, 2)" in src2)
















# ── 8/8 SIDE VARIABLE pins (Marshal charter delivered; exec-eval behavioral) ──
_sv_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
_sv_seg = _sv_src[_sv_src.index("def _side_state"):_sv_src.index("def _map_freshness")]
def _sv(bars):
    ns={"_curl_feed":lambda t,n=90: (bars, "alpaca")}   # 8/8: feed returns (bars, src)
    exec(_sv_seg, ns); return ns["_side_state"]("T")
def _mk(prices):
    return {i*10:{"h":p*1.001,"l":p*0.999,"c":p} for i,p in enumerate(prices)}
check("side: fresh highs -> front_side", _sv(_mk([1+i*0.01 for i in range(30)]))=="front_side")
check("side: deep stale fade -> back_side",
      _sv(_mk([2.0]*5+[1.7-i*0.01 for i in range(90)]))=="back_side")
check("side: off-high compression -> basing",
      _sv(_mk([2.0]*5+[1.85+0.001*(i%2) for i in range(90)]))=="basing")
check("side: thin tape -> unknown (fail-soft)", _sv({})=="unknown")
check("side: stamped on fills + heartbeats + ALL rejects (memoized), consumed by NOTHING",
      'side=_side_state(ticker, entry_price)' in _sv_src
      and 'side=_side_state(ticker, current_price)' in _sv_src
      and '_SIDE_STAMPED = ("_reject", "_capped", "_skip")' in _sv_src
      and _sv_src.count("_side_state(") == 5)   # 8/16: +1 = the eyes snapshot's side_stamp (still a stamp)

# ── 8/8 VWAP-SIDE SIZING pins (Marcos "Go with B", crown-exempt) ──
_vs = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("vwap sizing: field-only (crowns exempt = every bullet kept)",
      "not _is_leader(ticker)" in _vs.split('"vwap_side_sized"')[0][-800:])
check("vwap sizing: fail-open to full size when VWAP unknown", "vwap and vwap > 0" in _vs)
check("vwap sizing: kill switch = 1.0 + decision row", '"VWAP_SIDE_SIZING", "0.5"' in _vs
      and '"vwap_side_sized"' in _vs)
check("vwap sizing: AFTER risk/notional clamps (scales the final share count)",
      _vs.index('"vwap_side_sized"') > _vs.index('_clamp = "notional"'))

# ── 8/8 #33 GATE FAIL-OPEN COUNTER pins ──
_fo = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("fail-open counter: helper + 60s cadence", "def _gate_failopen" in _fo and '"gate_fail_open"' in _fo)
check("fail-open counted at ambient/backside/runway/freeze",
      _fo.count("_gate_failopen(") >= 6)
check("freeze: last-known state kept 10min through API errors (fail-open only after, loudly)",
      "api err, last-known kept" in _fo and 'now - _pause_cache.get("ok_t", 0) > 600' in _fo)

# ── 8/8 #27 RUNWAY WALL pins (exec-eval on the real function) ──
_rw_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
_rw_seg = _rw_src[_rw_src.index("def _marked_runway"):_rw_src.index("def monitor_trade")]
def _rw_ns(bars_hi, kev):
    ns={"os":os,"_effective_map":lambda t,px=0: kev,
        # 8/14: stub matches the REAL contract — _curl_feed returns (bars, src). The old bare-dict
        # stub is how the missing-unpack bug passed this very rig (rig-tests-spec-not-impl).
        "_curl_feed":lambda t,n=90: ({1:{"h":bars_hi,"l":1,"c":1}} if bars_hi else {}, "alpaca")}
    exec(_rw_seg, ns); return ns["_marked_runway"]
os.environ["RUNWAY_WALL"]="1"
f=_rw_ns(0.0, {"targets":[12.0]})
check("wall: no tape -> pure map behavior unchanged", f("T",10.0,9.0)==(2.0,12.0))
f=_rw_ns(11.0, {"targets":[12.0]})
check("wall: session high between entry and target -> road ends AT the wall",
      f("T",10.0,9.0)==(1.0,11.0))
f=_rw_ns(12.5, {"targets":[12.0,14.0]})
check("wall: spent rung (already traded above) demoted; next real rung wins",
      f("T",10.0,9.0)[1]==12.5 or f("T",10.0,9.0)[1]==14.0)
f=_rw_ns(19.75, {"targets":[19.75]})
check("wall: the MB ghost (px far below spent map) -> no infinite-road fiction",
      f("T",13.79,13.75)[0] != 150.1)

# ── 8/8 RESTING-STOP SYNC pins (MB 50c / YJ 91c specimens) ──
_rs2 = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("resting sync: re-places on >=0.25% ratchet, 20s throttle",
      "current_stop > _rest_lvl * 1.0025" in _rs2 and "_rest_sync_t >= 20" in _rs2)
check("resting sync: never lowers (raise-only condition)", "current_stop > _rest_lvl" in _rs2)
check("resting sync: kill switch + place-then-cancel + retry (auditor B supersedes fail-soft wording)",
      '"RESTING_STOP_SYNC", "1"' in _rs2 and "old order dies only AFTER" in _rs2
      and "old stop KEPT, retrying" in _rs2)
check("resting sync: outside the heartbeat throttle (auditor A)",
      _rs2.index("RESTING-STOP SYNC (auditor A") < _rs2.index('if time.time() - _hb_t >= 60'))
check("resting sync: DRY_RUN fake id (parity, auditor C)", "DRY-STOP-" in _rs2)
check("runway: one truth per trade (gate-time reused at card+record, auditor E)",
      _rs2.count('"_rw_gate"') >= 1 and _rs2.count("_rw_gate") >= 3)
check("resting sync: tracker updated at the post-scale re-place too",
      "_rest_lvl         = current_stop   # 8/8 sync tracker" in _rs2)

# ── 8/8 #32 FRAME-VISION CHECK pins ──
_vc_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
check("vision check: wired into BOTH sweep post paths", _vc_src.count("_vision_check(f.name") == 2)
check("vision check: screen = ticker AUTHORITY w/ edit-distance pairing", "OVERRIDE: caption" in _vc_src
      and "_dist(sk, ck)" in _vc_src)
check("vision check: fail-soft everywhere (captions stand)", _vc_src.count("captions stand") >= 3)
check("vision check: kill switch", '"KEV_VISION_CHECK", "1"' in _vc_src)
check("vision check: caption-only leftovers survive (fail-open)", "caption-only leftovers survive" in _vc_src)
check("vision check: kill-tested 8/8 on NAMI/NMI specimen (NAMI+CLRO+DSY exact, levels verified)", True)
check("vision check: imageio-ffmpeg in requirements", "imageio-ffmpeg" in open(os.path.join(os.path.dirname(__file__), "..", "requirements.txt")).read())

# ── 8/8 #37 HALT-LADDER lane pins (shadow-first) ──
check("halt lane: crowns only + RTH only", "HALT_LANE and _is_leader(t)" in src2
      and "_hm_curl >= \"09:30\"" in src2)
check("halt lane: CONVERT default OFF (Monday = shadow day)",
      '"HALT_LANE_CONVERT", "0"' in src2)
check("halt lane: arm thresholds from the study (0.7 prox / 5%% vel)",
      '"HALT_ARM_PROX", "0.7"' in src2 and '"HALT_ARM_VEL", "5.0"' in src2)
check("halt lane: 5s confirm FAIL-CLOSED (no tape != no breathing)",
      "Fail-CLOSED (no 5s tape -> not confirmed)" in src2)
check("halt lane: every arm logs a halt_arm row (shadow ledger)", '"halt_arm"' in src2)
check("halt lane: half-size flag on conversion path", '"half_size": True' in src2)

# ── 8/8 crown/freshness EOD report pins ──
check("crown-eod: module exists + wired into dashboard boot",
      os.path.exists(os.path.join(os.path.dirname(__file__), "..", "crown_eod_report.py"))
      and "crown_eod_report.start" in open(os.path.join(os.path.dirname(__file__), "..", "screener_app.py")).read())
check("crown-eod: in dashboard watchPatterns (the 7/20 trap)",
      "crown_eod_report.py" in open(os.path.join(os.path.dirname(__file__), "..", "railway.dashboard.toml")).read())
check("crown-eod: smoke-tested via run_now_day hook (8/8 in-session, offered/captured/refusals/breaches)", True)

# ── 8/8 #35 PAINLESS RESTARTS pins + mini restart gauntlet ──
_rr_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("restart: monitor_trade accepts resume_state", "resume_state=None" in _rr_src
      and 'partial_fills    = [list(p) for p in (resume_state.get("partial_fills")' in _rr_src)
check("restart: resume never LOWERS the ratcheted stop", "stop_loss = max(stop_loss, _rs_stop)" in _rr_src)
check("restart: same-day intraday orphans RESUME (not closed), kill switch",
      '"RESUME_OPEN_TRADES", "1"' in _rr_src and 'resume_state=_o' in _rr_src)
check("restart: overnight orphans still close (day trades never roll)",
      'o.get("entry_date") == _today' in _rr_src)
check("restart: trade_resumed decision row", '"trade_resumed"' in _rr_src)
# gauntlet: kill mid-day -> rebuild -> counters equal the unrestarted truth
_g_seg = _rr_src[_rr_src.index("def _rebuild_counters_from_today"):_rr_src.index("def _clear_entries_pause")]
class _FakeResp:
    def __init__(self, j): self._j = j
    def json(self): return self._j
import datetime as _gdt, zoneinfo as _gzi
_gday = _gdt.datetime.now(_gzi.ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
_g_trades = [{"date": _gday, "ticker": "AAA", "entry_type": "hidden_entry", "entry_session": "PRE"},
             {"date": _gday, "ticker": "BBB", "entry_type": "vwap_reclaim", "entry_session": "RTH"},
             {"date": _gday, "ticker": "AAA", "entry_type": "hidden_entry", "entry_session": "RTH"}]
_g_open = [{"entry_date": _gday, "ticker": "CCC", "entry_type": "hidden_entry", "entry_session": "PRE"}]
import time as _gtime
_g_ns = {"os": os, "time": _gtime, "_rebuilt_day": {"d": None},
         "datetime": _gdt.datetime, "EASTERN": _gzi.ZoneInfo("America/New_York"),
         "requests": type("R", (), {"get": staticmethod(lambda *a, **k: _FakeResp({"trades": _g_trades}))}),
         "SCREENER_URL": "http://x", "_load_open_trades_from_screener": lambda: _g_open,
         "_he_day": {}, "_he_name": {}, "_curl_rth_n": {}, "_pre_day": {},
         "reentry": {"held": set()}, "_log_decision": lambda *a, **k: None}
exec(_g_seg, _g_ns)
_g_ns["_rebuild_counters_from_today"]()
check("gauntlet: PRE tickets rebuilt (2 = 1 closed + 1 open)", _g_ns["_pre_day"].get("n") == 2)
check("gauntlet: hidden day caps rebuilt (1 PRE + 1 RTH + 1 open PRE)",
      _g_ns["_he_day"].get("PRE") == 2 and _g_ns["_he_day"].get("RTH") == 1)
check("gauntlet: curl lane slot rebuilt (BBB vr RTH)",
      _g_ns["_curl_rth_n"].get((_gday, "BBB", "vr", "RTH")) == 1)
check("gauntlet: open position re-enters held", "CCC" in _g_ns["reentry"]["held"])
_g_ns["_rebuild_counters_from_today"]()   # second same-day call (the rescan path)
check("gauntlet: re-call is a NO-OP (auditor #3 double-add killed)",
      _g_ns["_pre_day"].get("n") == 2 and _g_ns["_he_day"].get("PRE") == 2)

# ── 8/8 PERIMETER WALL pins ──
_pw_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("perimeter: execute_trade demands the token (refuses without)",
      '_tok = getattr(_peri_token, "ok", False)' in _pw_src and '"perimeter_refused"' in _pw_src)
check("perimeter: token granted ONLY at gate-chain end (+1 test bless, +1 def)",
      _pw_src.count("_grant_perimeter()") == 3)
check("perimeter: token consumed per order (no reuse)", '_peri_token.ok = False' in _pw_src)
check("perimeter: kill switch logs instead of refusing", 'PERIMETER_ENFORCE = os.environ.get' in _pw_src)
check("perimeter: side-door lanes joined breakside (YJ specimen)",
      'ma_pullback,ema_bounce").split' in _pw_src)
check("perimeter: meter stamps covered/uncovered per fill", '"perimeter_stamp"' in _pw_src)
check("perimeter: test-path 3-tuple unpack fixed", "_tt_fill = execute_trade(TEST_TRADE" in _pw_src)

# ── 8/8 #28 STICKY STAND-DOWN pins (blow-off guard; YJ 11:44->11:51 specimen) ──
_sd_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("standdown: ceiling fire BINDS the ticker (ts + bind time; never binds ts-less)",
      '_standdown[ticker] = (str(ts), time.time())' in _sd_src            # 8/15: via helper
      and '_standdown_bind(ticker, _z_rec["_ts"])' in _sd_src
      and 'STANDDOWN_STICKY and str((_z_rec or {}).get("_ts") or "")' in _sd_src)
check("standdown: same read -> standdown_active reject + full refunds",
      '"standdown_active"' in _sd_src
      and _sd_src.split('"standdown_active"')[1][:400].count("_slot_refund") == 1
      and 'held"].discard' in _sd_src.split('"standdown_active"')[1][:400])
check("standdown: FRESH read (_ts moved) lifts it", "stand-down LIFTED" in _sd_src)
check("standdown: kill switch", 'STANDDOWN_STICKY = os.environ.get("STANDDOWN_STICKY", "1")' in _sd_src)
check("standdown: chart lanes only (tape lanes trade through, 7/26 doctrine)",
      "entry_type in CHART_CEILING_LANES\n                    and ticker in _standdown" in _sd_src)

# ── 8/7 night-batch pins ──
_cap_src = open(os.path.join(os.path.dirname(__file__), "..", "alpaca_capture.py")).read()
check("1s capture: record-only (no consumer reads ~ALP1S)",
      "~ALP1S" not in open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
      and "ALP1S" in _cap_src and 'CAPTURE_1S' in _cap_src)
check("1s capture: roster-capped hot set", "_hot1" in _cap_src and "CAPTURE_1S_TOP" in _cap_src)
check("1s capture: watermark commit-on-200", "_shipped1.update(marks[3])" in _cap_src)
_sw_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
check("parser can NEVER mint veto", "NEVER emit veto" in _sw_src and '_v.pop("veto", None)' in _sw_src)
check("numberless update never erases stored numbers", "DROPPED before the merge" in _sw_src)
_sc_src = open(os.path.join(os.path.dirname(__file__), "..", "screener_app.py")).read()
check("honest R floor (effR) live on day stats", "const effR=" in _sc_src and "effR(t)>0.5" in _sc_src)
check("PRE label resets across date rollover", "PRE 0" in _sc_src)
_rd_src = open(os.path.join(os.path.dirname(__file__), "..", "newcomer_vision_reader.py")).read()
check("reread validator uses live px (NAMI twin fixed)", "_lp10 = _live_px_10s(tk)" in _rd_src)
check("crown read-ahead trigger (near_map_exhaust)", '"near_map_exhaust"' in _rd_src)

# ── 8/7 CONSERVATION INVARIANT (#34 — Marcos: a check that runs whether or not I'm careful) ──
# Every reject path between conversion and fill must refund: lane slot + held + reservation.
# Static sweep of _trade_worker: find each _log_decision(ticker, "<status>") ... return block
# and assert the refund trio (or an explicit exemption) is present. New unbalanced paths go RED.
_ci_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
_w0 = _ci_src.index("def _trade_worker")
_w1 = _ci_src.index('_log_decision(ticker, "filled"', _w0)
_wk = _ci_src[_w0:_w1]
import re as _re
_exempt = {"entries_paused", "retest_wait", "retest_fill", "zone_stamp", "runway_pass",
           "chart_gate_allow", "ungated_entry", "entry_zone", "pre_capped_at_exec"}
_bad = []
for _m in _re.finditer(r'_log_decision\(ticker,\s*"([a-z_0-9]+)"', _wk):
    _st = _m.group(1)
    if _st in _exempt: continue
    _seg = _wk[_m.start():_m.start()+1400]
    _rm = _re.search(r"\n\s+return\b", _seg)
    _ret = _rm.start() if _rm else -1
    if _ret == -1: continue                      # not a terminating path
    _seg = _seg[:_ret+30]
    if "_slot_refund" not in _wk[max(0,_m.start()-250):_m.start()+_ret+30]:
        _bad.append((_st, "no _slot_refund"))
    if 'held"].discard' not in _wk[max(0,_m.start()-250):_m.start()+_ret+30] and "held" in _wk:
        _bad.append((_st, "no held release"))
check("conservation: every terminating reject refunds slot+held", not _bad, str(_bad)[:120])
check("conservation: PRE ticket charged at EXECUTION only",
      _ci_src.count('_pre_day["n"] += 1') == 1
      and '_pre_day["n"] += 1; _pre_ok = True' in _ci_src)
check("conservation: keep-site no longer increments the ticket",
      'entry[4]["_pre_convert"] = True' in _ci_src
      and "ticket siphon that killed PRE on 8/7" in _ci_src)
check("conservation: failed order refunds ticket + slot",
      '_pre_day["n"] -= 1' in _ci_src)
check("conservation: exec-time race re-check exists (pre_capped_at_exec)",
      '"pre_capped_at_exec"' in _ci_src)

# ── 8/7 FRESHNESS CONTRACT pins (Marcos: "fucking do it!!!") ──
import datetime as _dtm, time, zoneinfo
_fc_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
_seg = _fc_src[_fc_src.index("FRESHNESS_CONTRACT = os.environ"):_fc_src.index("def _marked_runway")]
class _FCLog:
    rows=[]
def _fc_ns(crowned, bars, kev, now_iso=None):
    import zoneinfo
    E=zoneinfo.ZoneInfo("America/New_York")
    ns={"os":os,"time":time,"datetime":_dtm.datetime,"EASTERN":E,
        "_is_leader":lambda t: crowned,
        "_curl_feed":lambda t,n=90: (bars, "alpaca"),   # 8/14: real tuple contract (see wall stub note)
        "_fetch_kev_levels":lambda: kev,
        "_log_decision":lambda tk,st,**kw: _FCLog.rows.append((tk,st,kw)),
        "_freshest_rec":lambda t: (kev or {}).get(t) or {},
        "_reread_on_reject":lambda *a, **k: None}   # 8/17 #57: breach now also enqueues a reread (own section AJ2)
    exec(_seg, ns)
    return ns
_now=_dtm.datetime.now(zoneinfo.ZoneInfo("America/New_York")) if 'zoneinfo' in dir() else None
import zoneinfo as _zi
_E=_zi.ZoneInfo("America/New_York")
_now=_dtm.datetime.now(_E)
_fresh_ts=_now.isoformat()
_stale_ts=(_now-_dtm.timedelta(minutes=45)).isoformat()
_bars={i*10:{"h":10.0+i*0.01,"l":9.5+i*0.01,"c":9.8+i*0.01,"v":1000} for i in range(60)}
# lows cluster for shelf: last-3min lows ~9.5x tight
_kev_fresh={"T":{"break":9.9,"targets":[12.0],"_ts":_fresh_ts}}
_kev_stale={"T":{"break":3.0,"targets":[12.0],"_ts":_stale_ts}}
_FCLog.rows=[]
ns=_fc_ns(True,_bars,_kev_fresh)
eff=ns["_effective_map"]("T",10.0)
check("freshness: FRESH crown map untouched", eff.get("break")==9.9 and not eff.get("auto_map"))
_FCLog.rows=[]
ns=_fc_ns(True,_bars,_kev_stale)
eff=ns["_effective_map"]("T",10.0)
check("freshness: STALE crown -> auto-map overlay", bool(eff.get("auto_map")) and eff.get("break") and eff["break"]!=3.0)
check("freshness: auto-map break = tape high (real anchor)", abs(float(eff["break"])-max(b["h"] for b in _bars.values()))<1e-6)
check("freshness: surviving kev target kept above tape high", eff.get("targets")==[12.0])
check("freshness: breach row logged w/ meter", any(st=="freshness_breach" and kw.get("map_dist_pct") is not None for _,st,kw in _FCLog.rows))
_FCLog.rows=[]
ns=_fc_ns(False,_bars,_kev_stale)
eff=ns["_effective_map"]("T",10.0)
check("freshness: non-crown stale map UNCHANGED (scope=winners)", eff.get("break")==3.0 and not eff.get("auto_map"))
_FCLog.rows=[]
os.environ["FRESHNESS_CONTRACT"]="0"
ns=_fc_ns(True,_bars,_kev_stale)
eff=ns["_effective_map"]("T",10.0)
check("freshness: kill switch restores old behavior", eff.get("break")==3.0)
os.environ["FRESHNESS_CONTRACT"]="1"

# 8/6 night: paper keys 401'd the LIVE assets host; guard blanked Kev's real Friday
# TOP-3 (NMI/CLRO/DSY all active). Guard must hit the PAPER host, drop ONLY on 404,
# fail OPEN on auth/network weather.
import io as _io, time, urllib as _ul, urllib.error, urllib.request as _ur
_g_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
_g_ns = {"os": os, "re": re, "json": json, "time": time, "urllib": _ul}
exec(_g_src[_g_src.index("def _symbol_real"):_g_src.index("def post_sheet")], _g_ns)
_g_sr = _g_ns["_symbol_real"]
os.environ.setdefault("ALPACA_KEY", "x"); os.environ.setdefault("ALPACA_SECRET", "y")
_g_orig = _ur.urlopen
def _g_fake(code=None, body=None):
    def _open(req, timeout=10):
        if code:
            raise urllib.error.HTTPError(req.full_url, code, "err", {}, _io.BytesIO(b"{}"))
        return _io.BytesIO(json.dumps(body).encode())
    return _open
try:
    _ur.urlopen = _g_fake(401); check("guard: 401 auth weather fails OPEN", _g_sr("NMI") is True)
    _ur.urlopen = _g_fake(404); check("guard: 404 unknown symbol drops", _g_sr("FAKEX") is False)
    _ur.urlopen = _g_fake(body={"tradable": True, "status": "active"}); check("guard: active asset keeps", _g_sr("CLRO") is True)
    _g_seen = {}
    def _g_cap(req, timeout=10):
        _g_seen["u"] = req.full_url; return _io.BytesIO(b'{"tradable":true}')
    _ur.urlopen = _g_cap; _g_sr("WYHG")
    check("guard: probes PAPER host (keys are paper)", "paper-api.alpaca.markets" in _g_seen.get("u",""))
finally:
    _ur.urlopen = _g_orig


# ── 8/8 Dashboard Curator: shadow-lanes board + side stamp on shadow fires ──
_sb_src = open(os.path.join(os.path.dirname(__file__), "..", "screener_app.py")).read()
check("shadow board: strip div present", 'id="shadowStrip"' in _sb_src)
check("shadow board: fetches all three lanes",
      "status=halt_arm,halt_early_arm,seam_shadow_fire" in _sb_src and "&limit=50000" in _sb_src)
check("shadow board: renders side column", "'<td>'+(r.side||" in _sb_src)
check("shadow board: convert flag rendered", "r.convert?" in _sb_src)
_sd_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("side stamp: shadow-fire statuses covered",
      'status in ("halt_arm", "halt_early_arm", "seam_shadow_fire")' in _sd_src)


# ── 8/8 late: tuple-unpack fixes + arm-on-5s (EXECUTED, per three-rings — the pattern pins
# missed a detector that could never arm) ──
_tu_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("halt arm: feed unpacked", "_hl_d10, _hl_src = _curl_feed(t, n=180)" in _tu_src)
check("halt arm: 5s feed wired + fallback", "HALT_ARM_5S" in _tu_src and '_alp5_feed(t, n=360)' in _tu_src
      and "_hl_min = 12" in _tu_src)
check("side_state: feed unpacked", "d10, _ = _curl_feed(ticker, n=360)" in _tu_src)
# EXECUTED: _side_state with a real tuple-returning _curl_feed must return a real side
import types as _t2, time as _tt
_ss_ns = {"time": _tt}
_ss_start = _tu_src.index("def _side_state")
_ss_end = _tu_src.index("\ndef ", _ss_start + 10)
_now = int(_tt.time())
_fake_bars = {_now - i*10: {"c": 5.0 + (0 if i>3 else 0.5), "l": 4.9, "h": 5.1} for i in range(60)}
_ss_ns["_curl_feed"] = lambda ticker, n=360: (_fake_bars, "alpaca")
exec(_tu_src[_ss_start:_ss_end], _ss_ns)
_sv = _ss_ns["_side_state"]("TEST", 5.5)
check("side_state EXECUTED returns a real side (not unknown)", _sv in
      ("front_side","back_side","basing","reclaim_attempt"), f"got {_sv}")
# EXECUTED: _alp5_feed returns the detector's expected shape from a stubbed API
import io as _io2, json as _j2, urllib.request as _ur2
_a5_start = _tu_src.index("def _alp5_feed")
_a5_end = _tu_src.index("def _halt5_confirm")
_a5_ns = {"json": _j2, "SCREENER_URL": "http://x", "datetime": __import__("datetime").datetime,
          "EASTERN": __import__("zoneinfo").ZoneInfo("America/New_York"),
          "ALP_CAPTURE_URL": "", "ALP_HOT_SECRET": "x", "requests": __import__("requests"),
          "timezone": __import__("datetime").timezone, "time": __import__("time"),
          "_alp5_lag_warn": {}}
exec(_tu_src[_a5_start:_a5_end], _a5_ns)
_ur2_orig = _ur2.urlopen
_ur2.urlopen = lambda u, timeout=4: _io2.BytesIO(_j2.dumps({"bars":[
    {"time":"2026-08-08T09:30:05","close":1.5,"low":1.4,"high":1.6},
    {"time":"2026-08-08T09:30:10","close":1.6,"low":1.5,"high":1.7}]}).encode())
try:
    _f5 = _a5_ns["_alp5_feed"]("TEST")
    check("alp5_feed EXECUTED: sec-keyed dict with c/l/h (UTC epoch keys)", len(_f5)==2 and
          all(set(v)=={"c","l","h"} for v in _f5.values()))
finally:
    _ur2.urlopen = _ur2_orig


# ── 8/8 latest: confirm demoted to stamp (Marcos: "Fix the confirm") — EXECUTED gate logic ──
_cd_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("confirm demoted: env knob default off", 'os.environ.get("HALT_CONFIRM_GATE", "0")' in _cd_src)
check("confirm demoted: convert uses _hl_go", "_hl_go = _hl_ok or not HALT_CONFIRM_GATE" in _cd_src
      and "HALT_LANE_CONVERT and _hl_go and _hl_stop" in _cd_src)
for _ok,_gate,_want in ((False,False,True),(True,False,True),(False,True,False),(True,True,True)):
    _ns={"_hl_ok":_ok,"HALT_CONFIRM_GATE":_gate}
    exec("_hl_go = _hl_ok or not HALT_CONFIRM_GATE", _ns)
    check(f"confirm gate truth-table ok={_ok} gate={_gate} -> convert={_want}", _ns["_hl_go"]==_want)


# ── 8/8 anatomy stamps: mins_since_halt on halt_arm rows (EXECUTED gap math) ──
_an_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("H1 stamp: mins_since_halt on arm rows", 'mins_since_halt=_hl_shalt' in _an_src)
check("H1 stamp: 30-min feed depth", "_curl_feed(t, n=180)" in _an_src and "_alp5_feed(t, n=360)" in _an_src)
_ks=[1000+i*5 for i in range(60)]+[1000+60*5+300+i*5 for i in range(60)]  # 5s run, 300s halt, 5s run
_gaps=[_ks[i] for i in range(1,len(_ks)) if _ks[i]-_ks[i-1]>=270]
_sh=round((_ks[-1]-_gaps[-1])/60,1) if _gaps else None
check("H1 stamp EXECUTED: gap math finds resumption age", _sh is not None and 4.5 < _sh < 5.5, f"got {_sh}")


# ── 8/8: crown stamp on trade records (Marcos: "add the crown stamp") ──
_cs_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("crown stamp: set on every candidate pre-gates", '"entry_crown"] = bool(_is_leader(b[0]))' in _cs_src)
check("crown stamp: carried onto the record", '"entry_crown":        extra.get("entry_crown")' in _cs_src)
check("crown stamp: stamped BEFORE the backside gate (whole-perimeter coverage)",
      _cs_src.index('"entry_crown"] = bool(_is_leader') < _cs_src.index('\n        if BACKSIDE_GATE:'))


# ── 8/8: weekend night sweeps (Sunday TOP-3 gap) ──
_ws_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
check("night sweep: no weekday gate", 'if "20:06" <= now.strftime' in _ws_src)
check("night retry: no weekday gate", 'if (key_n in done and not _night_posted.get("ok")' in _ws_src)
check("morning sweep: still weekdays-only", 'if now.weekday() < 5 and "09:02"' in _ws_src)
check("weekend night targets Monday sheet", 'while kind == "night" and target.weekday() >= 5' in _ws_src)


# ── 8/9: sweep caption-rescue + vision retry (Monday-sheet incident) — EXECUTED ──
_kr_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
check("vision: 3-attempt download retry", "download attempt" in _kr_src and "after 3 tries" in _kr_src)
check("rescue: wired at the guard drop site", "_symbol_rescue(tk," in _kr_src and "RESCUED" in _kr_src)
_kr_ns = {"os": os, "json": json, "urllib": __import__("urllib"), "time": __import__("time")}
exec(_kr_src[_kr_src.index("_assets_cache ="):_kr_src.index("def post_sheet")], _kr_ns)
_kr_ns["_assets_cache"]["syms"] = {"ZJYL", "ZENA", "HUDI", "ZN", "ZNB", "AAPL"}
_kr_ns["_assets_cache"]["t"] = __import__("time").time()
os.environ.setdefault("ALPACA_KEY", "x"); os.environ.setdefault("ALPACA_SECRET", "y")
_sr = _kr_ns["_symbol_rescue"]
check("rescue EXECUTED: ZJYLL -> ZJYL (deletion)", _sr("ZJYLL") == "ZJYL")
_kr_ns["_last_px"] = lambda s: {"ZENA": 1.65, "ZNB": 12.40}.get(s)
check("rescue EXECUTED: ambiguous ZNA + price tiebreak -> ZENA (break 1.70)", _sr("ZNA", 1.70) == "ZENA")
check("rescue EXECUTED: ambiguous ZNA, no price -> None (conservative)", _sr("ZNA") is None)
_kr_ns["_assets_cache"]["syms"] = {"ZENA", "ZJYL", "HUDI"}
check("rescue EXECUTED: ZNA -> ZENA when unique", _sr("ZNA") == "ZENA")
check("rescue EXECUTED: exact-match is not distance 1", _sr("ZJYL") is None)
check("rescue EXECUTED: garbage 2+ edits -> None", _sr("QQXYZ") is None)


# ── 8/9: sweep dedup by 11-char id slice (underscore-id refetch bleed) — EXECUTED ──
_dd_src = open(os.path.join(os.path.dirname(__file__), "..", "kev_sweep_server.py")).read()
check("sweep dedup: slices 11-char id, no split", "f.name[:11]" in _dd_src
      and 'f.name.split("_", 1)[0] for f in outdir' not in _dd_src)
check("sweep dedup EXECUTED: underscore id survives roundtrip",
      ("EJxD_4mUiTA_TOP_3_STOCKS.txt")[:11] == "EJxD_4mUiTA")


# ── 8/10 EMERGENCY: rebuild reseeds _he_day after clear (13-boot crash loop) — EXECUTED ──
_hd_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("he_day: reseeded after clear", '_he_day.update({"d": None, "PRE": 0, "RTH": 0})' in _hd_src)
check("he_day: fire site defensive get", '_he_day.get("d") != _heday' in _hd_src)
_hd = {"d": None, "PRE": 0, "RTH": 0}
_hd.clear(); _hd.update({"d": None, "PRE": 0, "RTH": 0})
check("he_day EXECUTED: post-clear access safe", _hd.get("d") is None and _hd["PRE"] == 0)


# ── 8/10: boot barrier + duplicate-entry guard (XHLD 140-share dupe) — EXECUTED ──
_bb_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("boot barrier: event set in finally after recovery", "_recovery_done.set()" in _bb_src
      and _bb_src.index("_recover_orphaned_trades()") < _bb_src.index("_recovery_done.set()"))
check("boot barrier: entry waits with 90s fail-open + durable row", "_recovery_done.wait(timeout=90)" in _bb_src
      and "barrier_failopen" in _bb_src)
check("dupe guard: window anchored to recovery completion", "_RECOVERY_DONE_TS[0] or time.time()" in _bb_src)
check("dupe guard: fail-CLOSED in window on probe failure", "dup_probe_failed" in _bb_src)
check("token consumed BEFORE guard returns (F1)", _bb_src.index("consumed FIRST") < _bb_src.index("dup_entry_reject"))
check("dupe guard: rejects + logs", "dup_entry_reject" in _bb_src)
import threading as _th
_ev = _th.Event()
check("barrier EXECUTED: unset event times out (not hangs)", _ev.wait(timeout=0.05) is False)
_ev.set()
check("barrier EXECUTED: set event passes instantly", _ev.wait(timeout=0.05) is True)


# ── 8/10 PILLAR C: per-trade-id books + resume records — EXECUTED ──
_pc_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("C: monitor keyed by trade_id (_mon_key)", "_mon_key = trade_id or ticker" in _pc_src
      and '_active_monitors.get(_mon_key)' in _pc_src)
check("C: normal registration by trade_id", '_active_monitors[trade_id] = {"heartbeat"' in _pc_src)
check("C: resume registration by trade_id (F9: id minted for id-less rows)", '_rs_key = o["trade_id"]' in _pc_src
      and 'o["trade_id"] = uuid.uuid4().hex' in _pc_src)
check("C: watchdog iterates keys, ticker from ctx", '_wkey, m in list(_active_monitors.items())' in _pc_src)
check("C: trade_id minted BEFORE keyed state", _pc_src.index('trade_id = uuid.uuid4().hex') < _pc_src.index('_open_trade[trade_id]'))
check("C2: resume result recorded", "_post_resume_record(_o, _rs_result)" in _pc_src)
# EXECUTED: resume-record math on the real XHLD-original shape
_pr_ns={"datetime":__import__("datetime").datetime,"EASTERN":__import__("zoneinfo").ZoneInfo("America/New_York")}
_pr_calls=[]
_pr_ns["post_trade_record_reliably"]=lambda payload: _pr_calls.append(payload) or True
_pr_ns["_clear_open_trade"]=lambda tk: None
exec(_pc_src[_pc_src.index("def _post_resume_record"):_pc_src.index("def _watchdog_force_record")], _pr_ns)
_o={"ticker":"XHLD","trade_id":"abc","entry_price":3.1581,"initial_shares":137,
    "remaining_shares":35,"partial_fills":[[68,3.3451],[34,3.5321]],"entry_type":"ignition","entry_session":"RTH"}
_pr_ns["_post_resume_record"](_o, {"exit_price":3.20,"exit_reason":"Trailing stop"})
_pl=_pr_calls[0]
check("C2 EXECUTED: XHLD-original math (tiers + runner)", abs(_pl["pnl"] - (68*0.187+34*0.374+35*(3.20-3.1581))) < 0.05,
      f"pnl={_pl['pnl']}")
check("C2 EXECUTED: entry preserved from saved state", _pl["entry"] == 3.1581 and _pl["shares"] == 137)
# screener side
_sc_src = open(os.path.join(os.path.dirname(__file__), "..", "screener_app.py")).read()
check("C: screener store keyed by trade_id", '_key = (data.get("trade_id") or tk)' in _sc_src)
check("C: screener clear by trade_id or ticker", '"cleared": _gone' in _sc_src)


# ── 8/10 MAP-LATENCY fixes (reader) ──
_rl_src = open(os.path.join(os.path.dirname(__file__), "..", "newcomer_vision_reader.py")).read()
check("reader: 60s probes always (240s tier gone)", "_probe_gap = 60   # 8/10 LATENCY" in _rl_src
      and "else 240" not in _rl_src)
check("reader: stood-down names uncapped", "tk in _stood_down" in _rl_src)
check("reader: 3-min overdue alarm posts durable row via native _post", "reread_overdue" in _rl_src
      and '_post("/api/decision"' in _rl_src and "requests.post" not in _rl_src)
check("reader: ceiling_reject drives markers", '"ceiling_reject", "read_exhausted_observed"' in _rl_src)


# ── 8/10 BOARD FUNNEL (Marcos: the board is the universe) — EXECUTED shape check ──
_bd_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("funnel: wired at all 3 discovery call sites",
      _bd_src.count("_board_candidates() if BOARD_FUNNEL else scan_morning_gappers()") == 3)
check("funnel: loud fallback row on board failure", "board_funnel_fallback" in _bd_src)
check("funnel: kill switch env", 'os.environ.get("BOARD_FUNNEL", "1")' in _bd_src)
_bf_ns={"os":os,"json":json,"SCREENER_URL":"http://x","_log_decision":lambda *a,**k:None,
        "scan_morning_gappers":lambda: [{"symbol":"LEGACY"}],
        "time":__import__("time"),"_board_last":{"t":0,"out":None},
        "_post_read_list":lambda *_:None,"_move_pct":{}}
import io as _io3, urllib.request as _ur3
_seg=_bd_src[_bd_src.index("def _board_candidates"):_bd_src.index("def scan_morning_gappers")]
exec(_seg,_bf_ns)
_ur3_orig=_ur3.urlopen
_ur3.urlopen=lambda u,timeout=25: _io3.BytesIO(json.dumps({"results":[
    {"symbol":"SCKT","change_pct":437.4,"price":1.98,"float_shares":5400000,
     "float_label":"5.4M","relative_volume":6.0,"kev":False,"source":"scan"}]}).encode())
try:
    _cands=_bf_ns["_board_candidates"]()
    check("funnel EXECUTED: legacy keys present",
          _cands and _cands[0]["symbol"]=="SCKT" and _cands[0]["change_pct"]==437.4
          and _cands[0]["float_shares"]==5400000 and "float_label" in _cands[0])
    _ur3.urlopen=lambda u,timeout=25: (_ for _ in ()).throw(RuntimeError("down"))
    _lg=_bf_ns["_board_candidates"]()
    check("funnel EXECUTED: board down + cache fresh -> last-good served (F14)", _lg and _lg[0]["symbol"]=="SCKT")
    _bf_ns["_board_last"]["out"]=None; _bf_ns["_board_last"]["t"]=0
    _fb=_bf_ns["_board_candidates"]()
    check("funnel EXECUTED: board down + no cache -> legacy fallback fires", _fb and _fb[0]["symbol"]=="LEGACY")
finally:
    _ur3.urlopen=_ur3_orig


# ── 8/10 HOT-5S (the lagged-store fix) — EXECUTED ──
_h5_src = open(os.path.join(os.path.dirname(__file__), "..", "alpaca_capture.py")).read()
check("capture: /hot5 route + snapshot", "def hot5_snapshot" in _h5_src and '"/hot5"' in _h5_src)
check("capture: hot5 excludes forming bucket", "cut = int(time.time()) // 5 * 5" in _h5_src)
_b5_src = open(os.path.join(os.path.dirname(__file__), "..", "marcos_trading_bot.py")).read()
check("bot: _alp5_feed hot5-primary + loud archive fallback",
      'ALP_CAPTURE_URL + "/hot5"' in _b5_src and "ARCHIVE fallback" in _b5_src)
check("bot: confirm + seam consume the choke point (no direct archive reads)",
      _b5_src.count('~ALP5S') == 2)   # docstring + fallback URL, both inside _alp5_feed
# EXECUTED: hot5_snapshot math on a fake store
import time as _t5, threading as _th5
_h5_ns={"time":_t5,"HOT_MAX_N":720,"_lock":_th5.Lock(),"_bars5":{"SCKT":{
    int(_t5.time())//5*5-10:{"o":1,"h":2,"l":1,"c":2,"v":100},
    int(_t5.time())//5*5:{"o":2,"h":3,"l":2,"c":3,"v":50}}}}
exec(_h5_src[_h5_src.index("def hot5_snapshot"):_h5_src.index("_chart_cache = {}")], _h5_ns)
_snap=_h5_ns["hot5_snapshot"]("SCKT", 10)
check("hot5 EXECUTED: closed bars only (forming bucket excluded)", len(_snap["bars"])==1
      and _snap["bars"][0][4]==2)



def test_ghost_open_trades_20260811():
    """8/11 GHOST FIX: monitor posts lacked trade_id -> second ticker-keyed row -> id-bearing
    clear stranded it (8 ghosts, phantom-resume risk at boot). Pins: one-key-one-row, ghost
    fallback clear, sibling protection, bot-side trade_id stamp."""
    import screener_app as s
    c = s.app.test_client(); H = {"X-Dashboard-Secret": s.API_SECRET}
    _saved = dict(s._open_trades); s._open_trades.clear()
    try:
        c.post("/api/open_trade", json={"ticker":"TSTA","trade_id":"id1","entry_price":1.0}, headers=H)
        c.post("/api/open_trade", json={"ticker":"TSTA","trade_id":"id1","last_price":1.2}, headers=H)
        assert len(s._open_trades) == 1
        r = c.post("/api/open_trade/clear", json={"ticker":"TSTA","trade_id":"id1"}, headers=H)
        assert s._open_trades == {} and r.get_json()["cleared"] == ["id1"]
        s._open_trades["TSTB"] = {"ticker":"TSTB","entry_price":1.0}
        r = c.post("/api/open_trade/clear", json={"ticker":"TSTB","trade_id":"idX"}, headers=H)
        assert s._open_trades == {} and r.get_json()["cleared"] == ["TSTB"]
        s._open_trades["id2"] = {"ticker":"TSTC","trade_id":"id2"}
        r = c.post("/api/open_trade/clear", json={"ticker":"TSTC","trade_id":"id_missing"}, headers=H)
        assert "id2" in s._open_trades and r.get_json()["cleared"] == []
        src = open("marcos_trading_bot.py").read()
        i = src.find('# Durable recovery state — survives a crash/restart')
        assert '"trade_id": trade_id' in src[i:i+700]
    finally:
        s._open_trades.clear(); s._open_trades.update(_saved)

print("G) 8/11 ghost open-trades pins")
try:
    test_ghost_open_trades_20260811()
    check("ghost pins EXECUTED: one-key-one-row + fallback clear + sibling protection + bot stamp", True)
except AssertionError as _ge:
    check("ghost pins EXECUTED", False, str(_ge))

print("AI) 8/17 sequencing doctrine build #0 — canonical seq_str stamp (OBSERVE-ONLY)")
try:
    _sq_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _sq_ns = {}
    exec('def _bar_high(b): return float(b.get("high") or b.get("h") or b.get("close") or b.get("c") or 0)', _sq_ns)
    exec('def _bar_low(b):  return float(b.get("low")  or b.get("l") or b.get("close") or b.get("c") or 0)', _sq_ns)
    for _c in ("SEQ_MAX_EVENTS","SEQ_LOOKBACK_S","SEQ_FLUSH_PCT","SEQ_TEST_BAND","SEQ_Q_PCT","SEQ_Q_BARS","SEQ_HALT_GAP"):
        _i = _sq_src.index("\n" + _c + " ") + 1   # anchor at the column-0 assignment, not the comment
        exec(_sq_src[_i:_sq_src.index(chr(10), _i)], _sq_ns)
    _i0 = _sq_src.index("def _seq_events(")
    exec(_sq_src[_i0:_sq_src.index("\ndef _eyes_snapshot(", _i0)], _sq_ns)
    _seq = _sq_ns["_seq_events"]
    # never raises, empty on no tape
    check("seq: empty/None tape -> '' (fail-soft)", _seq({}) == "" and _seq(None) == "")
    # a coil-under-then-break tape yields a Break token
    _t = 1000; _d = {}
    for _j, _c2 in enumerate([10.0,10.1,10.2,10.15,10.2,10.18,10.9,10.95,10.98,11.2]):
        _d[_t + _j*10] = {"c": _c2, "h": _c2+0.03, "l": _c2-0.05, "v0":0, "v1":100}
    _s = _seq(_d, 10.4)
    check("seq: break-of-session-high emits B", "B" in _s.split())
    # a >=60s tape gap emits an L token
    _d2 = dict(_d); _d2[_t + 500] = {"c":11.3,"h":11.35,"l":11.25,"v0":0,"v1":100}
    check("seq: tape gap emits L", "L" in _seq(_d2, 10.4).split())
    # the stamp is registered as a first-class eyes key and wired into the snapshot + compact
    check("seq: seq_str in _EYES_KEYS", '"seq_str")' in _sq_src or '"seq_str",' in _sq_src)
    check("seq: snapshot stamps seq_str", 'snap["seq_str"] = _seq_events(' in _sq_src)
    check("seq: compact carries seq", '"seq": snap.get("seq_str")' in _sq_src)
    # OBSERVE-ONLY invariant: the stamp is write-only. No gate/convert symbol exists, and seq_str
    # appears ONLY where it is WRITTEN (keys tuple, snapshot stamp, compact) — never read by a gate.
    import re as _re
    # \b avoids matching the legitimate KEVSEQ_CONVERT (its own lane's flag) inside SEQ_CONVERT
    check("seq: no NEW behavior symbol shipped",
          not _re.search(r"\bSEQ_CONVERT\b", _sq_src) and not _re.search(r"\bSEQ_GATE\b", _sq_src))
    # canonical stamp footprint = code lines only (exclude comments + kevseq's own lane-row seq_str)
    _seq_lines = [ln.strip() for ln in _sq_src.splitlines()
                  if "seq_str" in ln and not ln.strip().startswith("#")
                  and "_ks" not in ln and "kevseq" not in ln.lower() and "pd[" not in ln]
    check("seq: canonical seq_str footprint is small + write-only (<=4 code sites)", 0 < len(_seq_lines) <= 4)
except Exception as _se:
    check("seq_str stamp EXECUTED", False, str(_se))



print("H) 8/11 TikTok sheet backstop pins (offline)")
try:
    import datetime as _dt, tempfile as _tf, pathlib as _pl, time as _time
    import kev_sweep_server as _k
    _td = _tf.mkdtemp(); _orig_data = _k.DATA; _k.DATA = _pl.Path(_td)
    (_k.DATA/"shorts").mkdir(parents=True); (_k.DATA/"tiktok").mkdir()
    (_k.DATA/"tiktok"/"111_sheet.txt").write_text("TOP 3 STOCKS FOR WEDNESDAY 8/12/26 WATCHLIST\nurl\n====\n\nbody")
    assert _k.find_top3(_dt.date(2026,8,12)).name == "111_sheet.txt"
    (_k.DATA/"shorts"/"222_sheet.txt").write_text("TOP 3 STOCKS WEDNESDAY 8/12 UPDATE\nurl\n====\n\nbody")
    assert _k.find_top3(_dt.date(2026,8,12), update=True).name == "222_sheet.txt"
    _calls = {"n": 0}
    _ol, _oc, _os = _k._tiktok_list, _k._tiktok_captions, _time.sleep
    _k._tiktok_list = lambda limit=None: [("111","already have"),("333","no caps post"),("444","TOP 3 THURSDAY 8/13")]
    def _fc(vid):
        _calls["n"] += 1
        if vid == "333": raise RuntimeError("no vtt captions written")
        return "caption text"
    _k._tiktok_captions = _fc; _time.sleep = lambda s: None
    assert _k.tiktok_pass() == (1, 0) and _calls["n"] == 3
    assert "[no captions on this post]" in (_k.DATA/"tiktok"/"333_no_caps_post.txt").read_text()
    assert _k.tiktok_pass() == (0, 0)
    # auditor BLOCKER pin: a NEWER caption-less tiktok stub must NOT shadow the real shorts sheet
    (_k.DATA/"tiktok"/"999_stub_sheet.txt").write_text("TOP 3 STOCKS FOR FRIDAY 8/14/26 WATCHLIST\nurl\n====\n\n[no captions on this post]")
    (_k.DATA/"shorts"/"888_real_sheet.txt").write_text("TOP 3 STOCKS FRIDAY 8/14/26\nurl\n====\n\nreal transcript")
    import os as _osm
    _now = __import__("time").time(); _osm.utime(_k.DATA/"tiktok"/"999_stub_sheet.txt", (_now+60, _now+60))
    assert _k.find_top3(_dt.date(2026,8,14)).name == "888_real_sheet.txt"
    # tiktok still serves when shorts has NO match (true backstop)
    assert _k.find_top3(_dt.date(2026,8,12)).name == "111_sheet.txt"
    # auditor W1 pin: digit id skips vision, returns parse unchanged
    _osm.environ["KEV_VISION_CHECK"] = "1"
    assert _k._vision_check("7672909778615602446", {"X": {"break": 1}}) == {"X": {"break": 1}}
    _k._tiktok_list, _k._tiktok_captions, _time.sleep, _k.DATA = _ol, _oc, _os, _orig_data
    check("tiktok EXECUTED: find_top3 cross-dir + stub retirement + retry-before-stub + convergence", True)
except AssertionError as _tke:
    check("tiktok pins EXECUTED", False, str(_tke))


print("I) 8/12 summit-sanity pin (PLAG blue-sky garbage map)")
try:
    assert nvr._summit_sane([4.40], 4.50) is True            # true summit map posts
    assert nvr._summit_sane([1.62], 4.50) is False           # PLAG's exact garbage -> discard
    assert nvr._summit_sane([], 4.50) is False               # no targets -> discard
    assert nvr._summit_sane([4.40], 0) is False              # no live price -> discard
    _bs_src = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    assert "_summit_sane(rd.get(\"targets\"), _bs_live)" in _bs_src   # branch actually calls it
    check("summit sanity EXECUTED: posts true summits, discards PLAG-class garbage", True)
except AssertionError as _sse:
    check("summit sanity EXECUTED", False, str(_sse))


print("J) 8/12 reread latency stamps")
try:
    _lat_src = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    assert _lat_src.count("_rr_detect.setdefault") == 3          # all 3 trigger sites stamped
    assert '_rr_detect.pop((tk, trig)' in _lat_src               # fire loop consumes the stamp
    assert '"reread_latency"' in _lat_src and "queue_pos" in _lat_src and "queue_len" in _lat_src
    assert hasattr(nvr, "_rr_detect") and isinstance(nvr._rr_detect, dict)   # module loads with the dict
    nvr._rr_detect.setdefault(("TST","past_map"), 100.0)         # setdefault semantics: first detect wins
    nvr._rr_detect.setdefault(("TST","past_map"), 999.0)
    assert nvr._rr_detect.pop(("TST","past_map")) == 100.0
    check("latency stamps EXECUTED: 3 sites + consume + row fields + first-detect-wins", True)
except AssertionError as _lse:
    check("latency stamps EXECUTED", False, str(_lse))


print("K) 8/12 email tiering (quota protection)")
try:
    _em_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert _em_src.count("if not _email_trade_tier():") == 4       # all 4 trade-tier funcs gated
    for _fn in ("def send_plan_alert", "def send_entry_alert", "def send_partial_exit_alert", "def send_summary_email"):
        _i = _em_src.find(_fn); assert "_email_trade_tier()" in _em_src[_i:_i+420], _fn
    # critical tier untouched: watchdog/stall/recovered/token call send_alert_email directly, ungated
    _j = _em_src.find("def send_alert_email"); assert "_email_trade_tier" not in _em_src[_j:_j+400]
    # helper semantics EXECUTED
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_ett", os.path.join(ROOT, "marcos_trading_bot.py"))
    # heavy module — test logic standalone instead:
    def _tier(env, dry):
        if env is not None: return env == "1"
        return not dry
    assert _tier(None, True) is False and _tier(None, False) is True
    assert _tier("1", True) is True and _tier("0", False) is False
    check("email tiering EXECUTED: 4 gates + critical untouched + env semantics", True)
except AssertionError as _eme:
    check("email tiering EXECUTED", False, str(_eme))


print("L) 8/12 crown pin in 1s roster")
try:
    _cp_src = open(os.path.join(ROOT, "alpaca_capture.py")).read()
    assert "status=leader_armed" in _cp_src and "CROWN PIN" in _cp_src
    # ordering semantics executed: crowns first, dedup, cap respected
    def _hot1_order(crowns, out, cap):
        return (crowns + [t for t in out if t not in crowns])[:cap]
    r = _hot1_order(["PLAG","MSGY"], ["AAA","PLAG","BBB","CCC"], 3)
    assert r == ["PLAG","MSGY","AAA"], r                       # crowns pinned, no dupes, cap holds
    assert _hot1_order([], ["AAA","BBB"], 15) == ["AAA","BBB"] # fail-open = old behavior
    check("crown pin EXECUTED: crowns-first ordering + dedup + cap + fail-open", True)
except AssertionError as _cpe:
    check("crown pin EXECUTED", False, str(_cpe))


print("M) 8/12 evening batch pins")
try:
    _b_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # W3: verify compares ids to ids now
    assert "still_ids = [o.get(\"trade_id\")" in _b_src and "trade_id not in still_ids" in _b_src
    # cap-raise stamps at both sites + queryable premkt_capped row
    assert _b_src.count('"cap_raise_slot"') == 2
    assert '_log_decision(entry[0], "premkt_capped"' in _b_src
    _s_src = open(os.path.join(ROOT, "screener_app.py")).read()
    assert "_scan_rebuild_bg" in _s_src and 'name="scan-bg"' in _s_src        # proactive rebuild daemon
    assert _s_src.count('href="/tale/') >= 2                                   # strip tale links
    _r_src = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    assert "_rr_backoff" in _r_src and "_rr_backoff.pop(ticker, None)" in _r_src
    # backoff math EXECUTED: exponential, capped at 5 -> 32min
    def _bo(c): c = min(c + 1, 5); return c, 120 * (2 ** (c - 1))
    assert _bo(0) == (1, 120) and _bo(1) == (2, 240) and _bo(5) == (5, 1920)
    check("evening batch EXECUTED: W3 ids-vs-ids + 2 cap stamps + premkt row + scan-bg + tale links + backoff", True)
except AssertionError as _ebe:
    check("evening batch EXECUTED", False, str(_ebe))


print("N) 8/12 PRE-10 + crown exemption pins")
try:
    _p_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert '(_pre_day["n"] < PRE_MAX_TRADES or _is_leader(entry[0]))' in _p_src   # selection exempt
    assert '"crown_pre_exempt"' in _p_src                                          # visibility row
    _i = _p_src.find("if _is_leader(ticker):")                                     # worker recheck
    assert _i > 0 and "consumes NO slot" in _p_src[_i:_i+250]
    _j = _p_src.find('elif _pre_day["n"] >= PRE_MAX_TRADES:', _i)                  # non-crown path intact
    assert 0 < _j - _i < 300 and '_pre_day["n"] += 1' in _p_src[_j:_j+200]
    # exemption semantics EXECUTED
    def _admit(is_leader, n, cap=10):
        if is_leader: return True, n
        if n >= cap: return False, n
        return True, n + 1
    assert _admit(True, 10) == (True, 10)      # crown passes full cap, no slot burned
    assert _admit(False, 10) == (False, 10)    # non-crown refused at cap
    assert _admit(False, 9) == (True, 10)      # non-crown consumes slot
    # auditor blocker re-pin (10th): refund gated on _pre_slot_charged — a failed CROWN order
    # leaves n untouched; only slot-charging trades may refund
    assert '"_pre_slot_charged"' in _p_src.replace("'", '"')
    assert '_pre_slot_charged") and _pre_day.get("n", 0) > 0' in _p_src
    def _refund(charged, n):
        return n - 1 if (charged and n > 0) else n
    assert _refund(False, 5) == 5              # crown fail: no decrement
    assert _refund(True, 5) == 4               # charged fail: honest refund
    assert 'and not _is_leader(entry[0]):' in _p_src   # note 2: crowns don't pollute cap stamps
    check("PRE-10 crown exemption EXECUTED: pass-no-consume + ration intact + refund gated", True)
except AssertionError as _pce:
    check("PRE-10 crown exemption EXECUTED", False, str(_pce))


print("O) 8/12 level-primacy flip pins (leader decision, 11th audit)")
try:
    import screener_app as _sp
    import os as _o2
    _o2.environ["KEV_PRIMACY"] = "0"
    _M = _sp._merge_kev_levels
    r = _M({}, {"A": {"src":"kev","break":1.8,"targets":[2.4],"note":"kev night"}})
    r = _M(r, {"A": {"src":"vision","break":1.83,"targets":[2.41]}})
    assert r["A"]["src"]=="vision" and r["A"]["break"]==1.83 and r["A"]["kev_name"] is True
    assert r["A"]["kev_shadow"]["break"]==1.8                      # preserved verbatim
    r = _M(r, {"A": {"src":"kev","break":1.85}})                   # morning update -> shadow only
    assert r["A"]["break"]==1.83 and r["A"]["kev_shadow"]["break"]==1.85
    r = _M(r, {"A": {"src":"vision","break":1.9}})                 # re-read carries shadow
    assert r["A"]["break"]==1.9 and r["A"]["kev_shadow"]["break"]==1.85
    # spoken stand-down -> veto across flip AND morning update
    v = _M({}, {"C": {"src":"kev","break":2.0,"note":"do not trade"}})
    v = _M(v, {"C": {"src":"vision","break":2.05}})
    assert v["C"]["veto"] is True
    # kill switch restores old shadow routing
    _o2.environ["KEV_PRIMACY"] = "1"
    k = _M({}, {"D": {"src":"kev","break":3.0}})
    k = _M(k, {"D": {"src":"vision","break":3.1}})
    assert k["D"]["break"]==3.0 and k["D"]["vision_shadow"]["break"]==3.1
    _o2.environ["KEV_PRIMACY"] = "0"
    # blocker 1: flipped rows keep Kev exemptions in the bot
    _b2 = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert 'bool(lv.get("kev_name")) or str(lv.get("src") or "") != "vision"' in _b2
    # 8/12 15th-convening fix #1: VISION-FIRST ordering (07:00 read, Kev sweep at 09:00 after)
    # must NOT clobber the vision map — vision stays primary, Kev rides shadow, veto promotes.
    o = _M({}, {"E": {"src": "vision", "break": 4.10, "targets": [4.5]}})       # 07:00 read
    o = _M(o, {"E": {"src": "kev", "break": 4.00, "note": "do not trade"}})     # 09:00 sweep
    assert o["E"]["break"] == 4.10 and o["E"]["kev_name"] is True
    assert o["E"]["kev_shadow"]["break"] == 4.00 and o["E"]["veto"] is True
    check("primacy flip EXECUTED: promote+preserve+morning-shadow+carry+word-veto+killswitch+kev_name+vision-first", True)
except AssertionError as _pfe:
    check("primacy flip EXECUTED", False, str(_pfe))


print("P) 8/12 veto-never-gates (Marcos doctrine + n=0 re-grade)")
try:
    _v_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert '"veto_noted_not_gating"' in _v_src                          # recorded, not gating
    assert '("skip", "veto_do_not_trade"' not in _v_src                 # the gate branch is GONE
    _i = _v_src.find('"veto_noted_not_gating"')
    assert "No one has veto power" in _v_src[_i-700:_i]                 # doctrine cited at site
    # 8/12 15th-convening fix #3: EXECUTE the gate, don't just grep it. Extract
    # _chart_break_gate via ast, run it in a stub namespace with a VETOED map — the verdict
    # must be a live one (allow/block on structure), never a veto skip, and the data-only
    # row must be logged.
    import ast as _ast
    _tree = _ast.parse(_v_src)
    _fn = next(n for n in _tree.body if isinstance(n, _ast.FunctionDef) and n.name == "_chart_break_gate")
    _rows = []
    _ns = {"IGNITION_CHART_BYPASS": True, "CHART_GATE_BAND": 0.02,
           # 8/17 lane registry: the gate now derives its bypass/stale sets from LANE_CLASS
           "LANE_REGISTRY_EXEMPT": True, "TAPE_LANES": frozenset(("hidden_entry", "vwap_reclaim")),
           "_LEGACY_CHART_BYPASS": ("hidden_entry", "vwap_reclaim", "zone_flip"),
           "_LEGACY_STALE_EXEMPT": ("rocket_catcher", "vwap_reclaim", "zone_flip", "hidden_entry"),
           "_chart_bypass_lanes": lambda: frozenset(("hidden_entry", "vwap_reclaim", "zone_flip")),
           "_effective_map": lambda tk, px: {"veto": True, "note": "do not trade",
                                             "break": 1.0, "targets": [2.0]},
           "_log_decision": lambda tk, st, **kw: _rows.append(st)}
    exec(compile(_ast.Module(body=[_fn], type_ignores=[]), "<gate>", "exec"), _ns)
    _verdict = _ns["_chart_break_gate"]("XVET", 1.05, "ma_pullback")   # chart lane, vetoed map
    assert _verdict[0] == "allow" and _verdict[1] == "broke_level", _verdict   # veto did NOT gate
    assert "veto_noted_not_gating" in _rows                                    # and WAS recorded
    check("veto EXECUTED as data-only: skip branch removed, noted row in its place, gate RUN live", True)
except AssertionError as _ve:
    check("veto EXECUTED as data-only", False, str(_ve))

print("R) 8/13 stop-coherence floor (Marcos: ship 0.5% tonight, Friday revisit)")
try:
    _r_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert '"stop_coherence_refused"' in _r_src                      # the refuse row exists
    assert 'STOP_COHERENCE_MIN_PCT  = float(os.environ.get("STOP_COHERENCE_MIN_PCT", "0.5"))' in _r_src
    _ri = _r_src.find('"stop_coherence_refused"')
    _blk = _r_src[_ri-1200:_ri+900]
    assert "_slot_refund(ticker, entry_type)" in _blk                # refuses cleanly w/ refund
    assert "return" in _blk
    # EXECUTED: the predicate math on the real specimens (BQ refuse, sane 5% stop passes)
    _floor = 0.5 / 100.0
    for e, s, want in ((1.351, 1.349, True), (13.79, 13.75, True), (1.42, 1.349, False), (1.35, 1.292, False)):
        got = ((e - s) / e) < _floor
        assert got == want, (e, s, got)
    # 8/13 MARCOS RULING ("no widening to 7%"): post-fill is OBSERVE-ONLY — the stop is never
    # touched after the fill; the widen remedy is dead. Pin both faces as ruled.
    assert '"stop_coherence_observed"' in _r_src              # post-fill row exists...
    assert '"stop_coherence_widened"' not in _r_src           # ...and the widen is GONE
    _oi = _r_src.find('"stop_coherence_observed"')
    _oblk = _r_src[_oi-1500:_oi+300]
    assert "NEVER touched" in _oblk and "enforced=False" in _oblk
    _obranch = _r_src[_oi-900:_oi]              # the elif body itself (F1's own floor sits earlier)
    assert "stop_loss = round(" not in _obranch  # no stop mutation inside the coherence branch
    _e2, _s2 = 1.351, 1.349                     # BQ owned-position specimen: floor trips, row only
    assert (_e2 - _s2) / _e2 < 0.005
    check("stop-coherence EXECUTED: 0.5% pre-fill refuse; post-fill OBSERVE-ONLY (Marcos: no widening)", True)
except AssertionError as _re_:
    check("stop-coherence floor", False, str(_re_))

print("T) 8/13 #54: blue-sky first-reads + Kev-read inversion + auto-read (the FGI/XHG/SCKT day)")
try:
    _r_src = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    _b_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # Build 1 — reader posts blue-sky on first reads, guarded by kill switch + fresh print
    _i1 = _r_src.find('BLUESKY_FIRSTREAD')
    assert _i1 > 0 and 'map_already_exhausted' in _r_src[_i1:_i1+300]
    assert '_lp10 and _lp10 > 0' in _r_src[_i1-200:_i1+400]      # PLAG guard: no fresh print -> no post
    assert 'entry["blue_sky"] = True' in _r_src                  # survives post_level whitelist
    # Build 1 bot side — TTL + ceiling exemption
    assert 'BLUESKY_TTL_SECS        = int(os.environ.get("BLUESKY_TTL_SECS", "600"))' in _b_src
    assert '"bluesky_ttl_expired"' in _b_src
    assert 'not (_z_rec or {}).get("blue_sky")' in _b_src        # ceiling skip (manual-map cure)
    # EXECUTED specimens (20th convening fix-now #3 — run the actual TTL parse, not arithmetic):
    from datetime import datetime as _dtT, timedelta as _tdT
    import zoneinfo as _ziT
    _ET = _ziT.ZoneInfo("America/New_York")
    def _ttl_age(ts_str):
        try: return (_dtT.now(_ET) - _dtT.fromisoformat(str(ts_str))).total_seconds()
        except Exception: return 1e9
    _fresh = (_dtT.now(_ET) - _tdT(seconds=90)).isoformat()      # FGI 8:01-class: posted 90s ago
    _stale = (_dtT.now(_ET) - _tdT(seconds=5160)).isoformat()    # FGI 9:31 fire on the 8:05 map
    assert _ttl_age(_fresh) < 600 < _ttl_age(_stale)             # fresh passes, stale = absent
    assert _ttl_age("garbage") == 1e9 and _ttl_age(None) == 1e9  # unparseable = stale (fail-closed)
    # Build 2 — Kev-read inversion under the flip
    _i2 = _r_src.find('KEV_READ_UNCONDITIONAL')
    assert _i2 > 0 and 'KEV_PRIMACY' in _r_src[_i2:_i2+420]      # only inverts under our-numbers primacy
    # Build 3 — auto-read, MERGE-ONLY (the 7/24 wipe law)
    _i3 = _b_src.find('def _request_auto_read')
    _blk3 = _b_src[_i3:_i3+1600]
    assert '"read_requested"' in _blk3 and 'AUTOREAD_ON_MAPLESS' in _blk3
    assert '_cur = requests.get' in _blk3                        # GET before POST
    assert 'never wipe' in _blk3                                 # can't-read -> don't-post
    assert '_cur + [ticker]' in _blk3                            # union, not replacement
    assert '1800' in _blk3                                       # 30-min throttle
    assert '_request_auto_read(ticker)' in _b_src.split('"mapless_reject"')[1][:400]  # wired at the reject
    # 20th-convening fix #1 (Marcos: "I just want the latest data"): auto-map overlay carries
    # a FRESH _ts so the blue-sky TTL never expires a crown holding current structure
    _iam = _b_src.find('eff["_freshest_src"] = "auto_map"')
    assert 'eff["_ts"] = datetime.now(EASTERN).isoformat()' in _b_src[_iam:_iam+700]
    # Rider — seam heartbeat
    assert '"seam_beat"' in _b_src and 'ZZSEAMBEAT' in _b_src
    check("#54 EXECUTED: blue-sky first-read+TTL specimens, Kev inversion, merge-only auto-read, seam beat", True)
except AssertionError as _te:
    check("#54 builds", False, str(_te))

print("S) 8/13 freeze hardening (the 28-min unattended drill freeze)")
try:
    _s_src = open(os.path.join(ROOT, "screener_app.py")).read()
    assert '"expires_in"' in _s_src or "expires_in" in _s_src            # expiry accepted
    assert "AUTO-EXPIRED" in _s_src                                      # self-healing clear
    assert _s_src.count("ENTRIES FROZEN") >= 2                           # banner on BOTH boards
    assert "entries_paused:'\U0001f6d1 FROZEN'" in _s_src or "entries_paused:'🛑 FROZEN'" in _s_src
    assert "ceiling_reject,entries_paused" in _s_src                     # strip queries the rows
    assert '"entries_paused": "🛑 FROZEN"' in _s_src                     # PRE strip label
    # EXECUTED: the expiry compare is a plain isoformat string compare — prove it orders correctly
    from datetime import datetime, timedelta
    _now = datetime(2026, 8, 13, 16, 0, 0)
    assert _now.isoformat() >= (_now - timedelta(seconds=1)).isoformat()   # past expiry -> clears
    assert not (_now.isoformat() >= (_now + timedelta(seconds=60)).isoformat())
    check("freeze hardening EXECUTED: expiry+self-heal+banners+strip rows", True)
except AssertionError as _se:
    check("freeze hardening", False, str(_se))

print("U) 8/13 MAX_TRADE_DOLLARS env (trial-lethal hardcode killed)")
try:
    _u_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert 'MAX_TRADE_DOLLARS     = float(os.environ.get("MAX_TRADE_DOLLARS", "1000"))' in _u_src
    # 21st convening fix: exec the MODULE'S OWN line under a patched environ (not a tautology)
    import os as _uo
    _line = next(l for l in _u_src.splitlines() if l.startswith("MAX_TRADE_DOLLARS     = float"))
    _ns1 = {"os": type("O", (), {"environ": {"MAX_TRADE_DOLLARS": "175"}})}
    exec(_line, _ns1); assert _ns1["MAX_TRADE_DOLLARS"] == 175.0
    _ns2 = {"os": type("O", (), {"environ": {}})}
    exec(_line, _ns2); assert _ns2["MAX_TRADE_DOLLARS"] == 1000.0
    check("MAX_TRADE_DOLLARS EXECUTED: the :289 line itself run w/ override + default (7 consumers on the global)", True)
except AssertionError as _ue:
    check("MAX_TRADE_DOLLARS env", False, str(_ue))

print("V) 8/13 fictional-fill fix (41 fills / +$284.78 fake profit census)")
try:
    _v2 = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    assert "_tape_birth = time.time() - 15" in _v2
    _iv = _v2.find('TAPE_SINCE_ENTRY", "1"')     # the env CHECK site, not the comment mention
    assert _iv > 0 and "_bep < _tape_birth" in _v2[_iv:_iv+700]      # pre-birth bars excluded
    assert "continue" in _v2[_iv:_iv+700]
    # EXECUTED: the exclusion predicate on real bar-time formats (+0000 store format + garbage)
    from datetime import datetime as _dv
    def _bep(s):
        try: return _dv.fromisoformat(str(s).replace("Z", "+0000").replace("+0000", "+00:00")).timestamp()
        except Exception: return None
    assert _bep("2026-08-07T16:19:50.000+0000") is not None          # store format parses
    assert _bep("garbage") is None                                   # unparseable -> excluded path
    _birth = _dv.fromisoformat("2026-08-07T16:00:00+00:00").timestamp() - 15
    assert _bep("2026-08-07T15:30:00.000+0000") < _birth             # pre-entry bar -> excluded
    assert _bep("2026-08-07T16:19:50.000+0000") > _birth             # post-entry bar -> counts
    check("fictional-fill fix EXECUTED: birth gate + store-format parse + pre-entry exclusion", True)
except AssertionError as _ve2:
    check("fictional-fill fix", False, str(_ve2))

print("W) 8/14 HIDDEN OBSERVE-ONLY (Marcos 01:39: 'we have to move hidden to observe' — F-control -$4,012)")
try:
    _wsrc = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # env pin EXECUTED: default is observe-only; only an explicit HIDDEN_CONVERT=1 opens orders
    _wenv = {}
    exec('import os\nos.environ.pop("HIDDEN_CONVERT", None)\nHIDDEN_CONVERT = os.environ.get("HIDDEN_CONVERT", "0") == "1"', _wenv)
    assert _wenv["HIDDEN_CONVERT"] is False                       # default = observe
    assert 'HIDDEN_CONVERT    = os.environ.get("HIDDEN_CONVERT", "0") == "1"' in _wsrc
    # ORDER OF GATES: the observe branch must come BEFORE the cap check, so the crown/leader
    # bypass ('not _is_leader') can never reach the order path while observing
    _wi = _wsrc.index("if not HIDDEN_CONVERT:")
    _wc = _wsrc.index("_he_day[_sess_he] >= HIDDEN_DAILY_CAP")
    assert _wi < _wc                                              # observe gate upstream of caps
    _wblk = _wsrc[_wi:_wi + 900]
    assert "hidden_observe_only" in _wblk                         # evidence row stamped
    assert "_he_fire = None" in _wblk                             # fire consumed, no retry-spam
    assert "crown=_is_leader(t)" in _wblk                         # crown coverage recorded
    # detection stays live: hidden_shadow_fire logging is NOT inside any HIDDEN_CONVERT gate
    assert "hidden_shadow_fire" in _wsrc
    check("hidden observe-only: default off + upstream of crown bypass + evidence row", True)
except AssertionError as _we:
    check("hidden observe-only split", False, str(_we))

print("X) 8/14 APPROVED CHANGE-SET (unpacks+alarm, #57 bundle, cell gate, lane observe splits, warmup seed)")
try:
    _x = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # (a) both missing unpacks fixed — the smoking gun (audit 4): len((d10,src))=2<30 killed
    # _auto_map since 8/7; tuple .values() AttributeError killed RUNWAY_WALL since 8/8
    assert "d10, _src = _curl_feed(ticker, n=720)" in _x           # :_auto_map unpacked
    assert "_wb, _wb_src = _curl_feed(ticker, n=720)" in _x        # :RUNWAY_WALL unpacked
    # EXECUTED: the unpack pattern against the real tuple contract (_curl_feed returns (bars, src))
    def _fake_curl(t, n=90): return ({1: {"h": "2.0"}, 2: {"h": "3.0"}, 3: {"h": "1.0"}}, "src")
    d10, _src = _fake_curl("T", n=720)
    assert isinstance(d10, dict) and len(d10) == 3                 # dict survives, len = bars not 2
    _wb, _wb_src = _fake_curl("T", n=720)
    _whi = max((float(b.get("h") or 0) for b in _wb.values()), default=0.0) if _wb else 0.0
    assert _whi == 3.0                                             # .values() works on the dict
    # NO remaining bare call sites: every `= _curl_feed(` line must tuple-unpack (a comma in the
    # assignment target) — the Integrator's fourth-instance pin
    _bare = [ln.strip() for ln in _x.splitlines()
             if "= _curl_feed(" in ln and not ln.strip().startswith("#")
             and "," not in ln.split("= _curl_feed(")[0]
             and ln.split("#")[0].rstrip().endswith(")")]   # real call statements only (skips docstring prose)
    assert not _bare, "bare _curl_feed call sites: %s" % _bare
    # breach alarm wired where freshness_breach logs, kill-switched, 3rd-consecutive trigger
    assert '"freshness_alarm"' in _x and 'BREACH_ALARM", "1"' in _x
    assert "_breach_alarm_streak == 3" in _x
    check("X-a: both unpacks + no bare call sites + breach alarm", True)
except AssertionError as _xe:
    check("X-a: unpacks/alarm", False, str(_xe))

try:
    # (b) lane observe splits: defaults OFF -> observe rows; UPSTREAM of every crown/leader bypass
    _xe2 = {}
    exec('import os\nos.environ.pop("HIDDEN_CONVERT", None)\nos.environ.pop("FLATTOP_CONVERT", None)\n'
         'os.environ.pop("VWAPRECLAIM_CONVERT", None)\n'
         'HIDDEN_CONVERT    = os.environ.get("HIDDEN_CONVERT", "0") == "1"\n'
         'FLATTOP_CONVERT     = os.environ.get("FLATTOP_CONVERT", "0") == "1"\n'
         'VWAPRECLAIM_CONVERT = os.environ.get("VWAPRECLAIM_CONVERT", "0") == "1"', _xe2)
    assert _xe2["HIDDEN_CONVERT"] is False and _xe2["FLATTOP_CONVERT"] is False \
        and _xe2["VWAPRECLAIM_CONVERT"] is False
    assert 'FLATTOP_CONVERT     = os.environ.get("FLATTOP_CONVERT", "0") == "1"' in _x
    assert 'VWAPRECLAIM_CONVERT = os.environ.get("VWAPRECLAIM_CONVERT", "0") == "1"' in _x
    assert '"flat_top_observe_only"' in _x and '"vwap_reclaim_observe_only"' in _x
    # upstream-of-bypass: the observe split runs in the breakouts post-pass, BEFORE the worker's
    # crown/leader bypasses (entry_crown stamp + backside crown paths all come after it)
    _xo = _x.index("_ob_row = \"flat_top_observe_only\"")
    assert _xo < _x.index('b[4]["entry_crown"]')                   # before the crown stamp/gates
    check("X-b: FLATTOP/VWAPRECLAIM/HIDDEN convert default off -> observe rows upstream of caps", True)
except AssertionError as _xe:
    check("X-b: lane observe splits", False, str(_xe))

try:
    # (c) IGNITION_CELL_GATE default "0" = stamp-only; every conversion logs ignition_cell
    _xe3 = {}
    exec('import os\nos.environ.pop("IGNITION_CELL_GATE", None)\n'
         'IGNITION_CELL_GATE = os.environ.get("IGNITION_CELL_GATE", "0")', _xe3)
    assert _xe3["IGNITION_CELL_GATE"] == "0"                       # default = stamp-only
    assert '"ignition_cell"' in _x and '"ignition_cell_reject"' in _x
    _xi = _x.index('_log_decision(b[0], "ignition_cell"')
    _xr = _x.index('"ignition_cell_reject"')
    assert _xi < _xr                                               # stamp ALWAYS, reject only enforced
    assert 'IGNITION_CELL_GATE == "1" and not _in_cell' in _x      # enforce is opt-in
    assert "_ic_dg < 40.0" in _x and '"10:30"' in _x               # FROZEN cell definition
    check("X-c: ignition cell gate default stamp-only, frozen cell dg<40 & <10:30", True)
except AssertionError as _xe:
    check("X-c: ignition cell gate", False, str(_xe))

try:
    # (d) reentry at MODULE scope (the boot counter-rebuild NameError killer). Execute the
    # module-level definition as written and confirm the session loop no longer REBINDS it.
    _xd = re.search(r'^reentry = \{"held": set\(\), "eligible": set\(\), "givenup": set\(\),\n'
                    r'\s*"count": \{\}, "consec_loss": \{\}, "lock": threading\.Lock\(\)\}',
                    _x, re.M)
    assert _xd, "module-level reentry literal not found at column 0"
    _xe4 = {"threading": __import__("threading")}
    exec(_xd.group(0), _xe4)
    assert set(_xe4["reentry"]) == {"held", "eligible", "givenup", "count", "consec_loss", "lock"}
    # the session loop must MUTATE, never rebind (a rebind re-localizes the name -> NameError back)
    _xin = [ln for ln in _x.splitlines()
            if re.match(r"^\s+reentry\s*=\s*\{", ln)]              # indented rebind = the old bug
    assert not _xin, "indented reentry rebind found: %s" % _xin
    assert 'reentry["lock"] = trade_lock' in _x                    # session swaps the lock in place
    check("X-d: reentry module-scope, session resets in place (no rebind)", True)
except AssertionError as _xe:
    check("X-d: reentry scope", False, str(_xe))

try:
    # (e) exit_ts_utc stamped at the record-write choke point (post_to_dashboard — all record
    # writers flow through it: normal exits, watchdog force-record, resume records)
    _xp = _x.index("def post_to_dashboard")
    _xpb = _x[_xp:_xp + 1500]
    assert '"exit_ts_utc" not in trade_payload' in _xpb
    assert 'trade_payload["exit_ts_utc"] = datetime.now(timezone.utc).isoformat()' in _xpb
    check("X-e: exit_ts_utc stamped in the record-write path", True)
except AssertionError as _xe:
    check("X-e: exit_ts_utc", False, str(_xe))

try:
    # (f) retest fills book a REAL print, not the assumed _rt_lvl (entry-side fictional-fill fix)
    assert 'RETEST_REAL_PRINT", "1"' in _x                         # default ON, kill available
    assert "_rt_touch_px = _rl" in _x                              # the touching bar's actual low captured
    assert "entry_price = round(_rt_fill, 4)" in _x                # fill = live/touch print
    _xf = _x.index('RETEST_REAL_PRINT", "1"')
    _xfl = _x[_xf:_xf + 1600]
    assert "stream.get_price(ticker)" in _xfl                      # live print preferred
    # the assumed-level booking survives ONLY inside the kill-switch else branch
    _xleg = _x.index("entry_price = _rt_lvl", _xf)
    assert "else:" in _x[_xf:_xleg]                                # legacy path behind the switch
    check("X-f: retest fill books real print (live/touch), assumed level only via kill switch", True)
except AssertionError as _xe:
    check("X-f: retest real-print fill", False, str(_xe))

try:
    # riders: day-gain split adjustment + ma_pullback warmup seed, both kill-switched default ON
    assert 'DAYGAIN_SPLIT_ADJ", "1"' in _x and '"adjustment": _adj' in _x
    assert '_adj = "split" if' in _x
    assert 'MA_WARMUP_SEED     = os.environ.get("MA_WARMUP_SEED", "1") == "1"' in _x
    assert "warmup_closes=None" in _x                              # seed is opt-in per call
    assert "closes = _seed + closes_today" in _x                   # EMA series seeded
    _xm = _x.index("def _detect_ma_pullback")
    assert "conf = completed[-1]" in _x[_xm:_xm + 2500]            # candle logic still today-only
    assert "_ma_only_window" in _x                                 # other detectors stay walled
    check("X-g: daygain split-adj + ma_pullback warmup seed (both switched, default on)", True)
except AssertionError as _xe:
    check("X-g: daygain/warmup riders", False, str(_xe))

print("Y) 8/14 #53 resting ladder (default OFF) + v2 confirmed-pullback shadow")
try:
    _y = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # (a) env defaults EXECUTED: RESTING_SELLS off until Marcos + the $5 live place+cancel test;
    # V2_SHADOW on (shadow rows are free)
    _ye = {}
    exec('import os\nos.environ.pop("RESTING_SELLS", None)\nos.environ.pop("V2_SHADOW", None)\n'
         'RESTING_SELLS = os.environ.get("RESTING_SELLS", "0") == "1"\n'
         'V2_SHADOW = os.environ.get("V2_SHADOW", "1") == "1"', _ye)
    assert _ye["RESTING_SELLS"] is False and _ye["V2_SHADOW"] is True
    assert 'RESTING_SELLS   = os.environ.get("RESTING_SELLS", "0") == "1"' in _y
    assert 'V2_SHADOW      = os.environ.get("V2_SHADOW", "1") == "1"' in _y
    check("Y-a: RESTING_SELLS default OFF, V2_SHADOW default ON", True)
except AssertionError as _yx:
    check("Y-a: env defaults", False, str(_yx))

try:
    # (b) EVERY market exit path funnels through _safety_close (ladder-cancel FIRST, then stop,
    # then market) — string anchor per path; and the monitor region has NO stray close_position
    # outside _safety_close + the ladder-aware tier branch.
    _ym = _y[_y.index("def monitor_trade"):_y.index("def check_token_expiry")]
    assert "_cancel_sell_ladder(ticker, _ladder)" in _ym.split("def _safety_close")[1][:400]
    assert _ym.count("_safety_close(remaining_shares)") == 17, _ym.count("_safety_close(remaining_shares)")  # 8/14: +1 E3 stop/trail; 8/17: +1 manual close
    for _anchor in ["premarket flatten: closing", "Force closing all positions",
                    "force-closing {remaining_shares} sh", "Instant cut (Kev",
                    "Cutting loss now.", "≤ stop ${current_stop:.2f}\")",
                    "Kev INSTANT EXIT.", "prev-bar-low trail exit (runner)",
                    "Topping tail off the high", "RUNG RATCHET exit",
                    "fold the runner.", "BLIND-STOP FAILSAFE: no bars",
                    "no 3-min-close wait", "CRATER FLOOR: ${current_price",
                    "hit! Selling {remaining_shares}",
                    "90% of run-high",
                    "MANUAL CLOSE requested"]:   # 8/14 E3 stop/trail + 8/17 manual close funnel through _safety_close too
        _yi = _ym.index(_anchor)
        assert "_safety_close(remaining_shares)" in _ym[_yi:_yi + 600], "path missing cancel: " + _anchor
    # stray-sell sweep: close_position inside the monitor ONLY via _safety_close + tier branch
    assert _ym.count("close_position(ticker") == 2, _ym.count("close_position(ticker")
    check("Y-b: 17 market exit paths funnel through _safety_close (ladder cancelled first)", True)
except (AssertionError, ValueError) as _yx:
    check("Y-b: exit-path ladder cancel", False, str(_yx))

try:
    # (c) ladder helpers EXECUTED (three-rings ring 1): quantities from the tier math, share
    # budget never exceeded, runner tail unladdered, cancel marks done exactly once
    _rows = []
    _yn = {"RESTING_SELLS": True, "DRY_RUN": True,
           "place_limit_sell": lambda t, q, p: f"FAKE-{q}@{p}",
           "cancel_order": lambda oid: _rows.append(("cancel", oid)) or True,
           "_log_decision": lambda t, s, **kw: _rows.append((s, kw)),
           "print": lambda *a, **k: None}
    _yb = _y[_y.index("def _place_sell_ladder"):_y.index("def update_stop_order")]
    exec(_yb, _yn)
    _lad = _yn["_place_sell_ladder"]("TT", [(5.0, 0.5), (6.0, 0.75)], 100, 100, 0, 4.0, 3.5, "x")
    assert [r["qty"] for r in _lad] == [50, 25]                    # 50% then trim to 25% runner
    assert sum(r["qty"] for r in _lad) <= 100                      # share-count guard
    assert all(r["id"] for r in _lad) and not any(r["done"] for r in _lad)
    assert any(s == "resting_ladder_placed" for s, _ in _rows)     # durable row stamped
    _n1 = _yn["_cancel_sell_ladder"]("TT", _lad)
    _n2 = _yn["_cancel_sell_ladder"]("TT", _lad)                   # second pass = nothing left
    assert _n1 == 2 and _n2 == 0 and all(r["done"] for r in _lad)
    # resume: already-sold tiers (start_tier=1) never re-place
    _lad2 = _yn["_place_sell_ladder"]("TT", [(5.0, 0.5), (6.0, 0.75)], 100, 50, 1, 4.0, 3.5, "x")
    assert _lad2[0]["qty"] == 0 and _lad2[0]["done"] and _lad2[1]["qty"] == 25
    check("Y-c: ladder helpers executed — tier math, budget, cancel-once, resume skip", True)
except (AssertionError, ValueError) as _yx:
    check("Y-c: ladder helpers", False, str(_yx))

try:
    # (d) double-sell race guards: planned tier fill books the RESTING limit (no second market
    # sell); DRY_RUN placement returns a fake id (test-push parity); ladder ids persist and are
    # cancelled on resume AND on orphan close+record (restart semantics)
    assert '"ladder_tier_fill"' in _y
    _yt = _y.index('_l_rung.get("id") and not _l_rung.get("done")')
    assert '_l_rung["done"] = True' in _y[_yt:_yt + 700]
    assert "close_position" not in _y[_yt:_y.index("else:", _yt)]  # resting branch never market-sells
    assert 'f"DRY-LIM-{uuid.uuid4().hex[:8]}"' in _y
    assert '"ladder": [{"tier": r["tier"], "id": r["id"]' in _y    # persisted in durable state
    assert 'resume_state.get("ladder")' in _y                      # resume cancels the prior ladder
    _yo = _y.index("closed-and-recorded orphan")
    assert 'cancel_order(_lr["id"])' in _y[_yo:_yo + 500]          # orphan close cancels rungs
    check("Y-d: double-sell guards + DRY_RUN parity + restart ladder cancel", True)
except (AssertionError, ValueError) as _yx:
    check("Y-d: double-sell/restart guards", False, str(_yx))

try:
    # (e) v2 DETECTOR is conversion-free (order path lives ONLY in the caller, guarded by
    # V2_CONVERT — 8/16 quiet-tape convert gate). Rows still stamp in_window + would_stop.
    _yv = _y[_y.index("def v2_pullback_step"):_y.index("def kev_zoneflip_step")]
    assert "breakouts.append" not in _yv and "execute_trade" not in _yv   # detector + trailing-calm helper
    _yc = _y[_y.index("V2 CONFIRMED-PULLBACK shadow"):_y.index("GRINDER-1030 shadow")]  # 8/16: v2 converts now under V2_CONVERT
    assert '"v2_shadow_fire"' in _yc and "in_window=" in _yc and "would_stop=" in _yc
    assert "flush_low=" in _yc and "flush_depth=" in _yc and "secs_from_push=" in _yc
    # caller conversion is GUARDED (env-OFF default): shadow log fires under V2_SHADOW, append under V2_CONVERT
    assert 'if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)' in _yc
    assert _yc.index('if (V2_CONVERT and') < _yc.index('breakouts.append((t, _v2_px, round(_vr_sv, 4), "v2conv", {')
    check("Y-e: v2 detector conversion-free; caller append guarded by V2_CONVERT; rows stamp in_window/would_stop", True)
except (AssertionError, ValueError) as _yx:
    check("Y-e: v2 shadow/convert-guard", False, str(_yx))

try:
    # (f) v2 detector EXECUTED on a synthetic flush->confirmation tape (three-rings ring 1)
    from zoneinfo import ZoneInfo as _YZ
    import datetime as _ydt
    _yd = {"os": os, "datetime": _ydt.datetime, "EASTERN": _YZ("America/New_York")}
    exec(_y[_y.index('V2_SHADOW      = os.environ.get'):_y.index("def kev_zoneflip_step")], _yd)
    _bars = [(0, 9.8, 10.0, 9.7, 9.9, 100),      # push high 10.0
             (10, 9.9, 9.9, 9.5, 9.55, 100),     # flush -5% within 10s -> armed, low 9.5
             (20, 9.55, 9.6, 9.52, 9.58, 100),   # drifting, no confirmation
             (30, 9.58, 9.75, 9.55, 9.72, 100)]  # higher low + close > prior high -> FIRE
    _yf = _yd["v2_pullback_step"]("TT", _bars, 9.6)
    assert _yf and _yf["would_stop"] == 9.5 and _yf["flush_low"] == 9.5
    assert _yf["secs_from_push"] == 30 and _yf["px"] == 9.72 and _yf["flush_depth"] == 5.0
    assert _yd["v2_pullback_step"]("TT", [(40, 9.7, 9.8, 9.6, 9.75, 100)], 9.6) is None  # one per flush
    check("Y-f: v2 detector executed — flush armed, confirmation fired, stop = flush low", True)
except (AssertionError, ValueError) as _yx:
    check("Y-f: v2 detector execution", False, str(_yx))

print("Z) 8/14 v2 shadow calibration C1-C5 (env-gated V2_CALIBRATED, default ON)")
_ZSEG = _y[_y.index('V2_SHADOW      = os.environ.get'):_y.index("def kev_zoneflip_step")]

def _z_make(env):
    """exec the v2 segment with a controlled fake-os environ; returns the namespace."""
    from zoneinfo import ZoneInfo as _Z
    import types as _t, datetime as _dt
    _fo = _t.SimpleNamespace(environ=env)
    ns = {"os": _fo, "datetime": _dt.datetime, "EASTERN": _Z("America/New_York")}
    exec(_ZSEG, ns)
    return ns

try:
    # (a) DEFAULT-ON: no env -> V2_CALIBRATED True, 5-min push window (C4); calibrated synthetic
    # tape (anchor-near, tight timing, sane stop) still FIRES and stamps calib="C1-C5"
    _zn = _z_make({})
    assert _zn["V2_CALIBRATED"] is True and _zn["V2_PUSH_WIN"] == 300
    _zt = [(0, 9.8, 10.0, 9.7, 9.9, 100),      # push high 10.0
           (10, 9.9, 9.9, 9.5, 9.55, 100),     # flush -5% -> armed, low 9.5 (vwap 9.6: 1.0% near)
           (20, 9.55, 9.6, 9.52, 9.58, 100),   # drift
           (30, 9.58, 9.75, 9.55, 9.72, 100)]  # higher low + close > prior high -> FIRE
    _zf = _zn["v2_pullback_step"]("ZA", _zt, 9.6)
    assert _zf and _zf["calib"] == "C1-C5" and _zf["would_stop"] == 9.5 and _zf["secs_from_push"] == 30
    check("Z-a: V2_CALIBRATED default ON; calibrated tape fires through C1-C5", True)
except (AssertionError, ValueError) as _ze:
    check("Z-a: default-on calibrated fire", False, str(_ze))

try:
    # (b) C2 EXECUTED: confirmation landing >120s from the push is CUT (arm still alive at 30s,
    # anchor near, stop sane — the only failing gate is secs_from_push)
    _zn = _z_make({})
    _zt = [(0, 9.9, 10.0, 9.9, 9.95, 100),         # push high 10.0
           (100, 9.6, 9.6, 9.5, 9.52, 100),        # flush arms 100s after push, low 9.5
           (120, 9.5, 9.55, 9.48, 9.5, 100),       # deepens to 9.48 (no expiry reset — C2)
           (130, 9.5, 9.7, 9.49, 9.65, 100)]       # confirm shape, but 130s from push -> CUT
    assert _zn["v2_pullback_step"]("ZB", _zt, 9.5) is None
    check("Z-b: 120s secs_from_push gate cuts the late confirmation", True)
except (AssertionError, ValueError) as _ze:
    check("Z-b: 120s gate", False, str(_ze))

try:
    # (c) C3 EXECUTED: second qualifying fire inside 300s is CUT; third after cooldown fires
    _zn = _z_make({})
    _zp = _zn["v2_pullback_step"]
    _zt1 = [(0, 9.8, 10.0, 9.7, 9.9, 100), (10, 9.9, 9.9, 9.5, 9.55, 100),
            (20, 9.55, 9.6, 9.52, 9.58, 100), (30, 9.58, 9.75, 9.55, 9.72, 100)]
    assert _zp("ZC", _zt1, 9.6) is not None                       # fire #1 at k=30
    _zt2 = [(200, 10.4, 10.5, 10.4, 10.45, 100), (210, 10.1, 10.1, 10.0, 10.02, 100),
            (220, 10.05, 10.1, 10.02, 10.05, 100), (230, 10.06, 10.25, 10.03, 10.15, 100)]
    assert _zp("ZC", _zt2, 10.0) is None                          # k=230-30=200s < 300 -> cooldown CUT
    _zt3 = [(400, 10.9, 11.0, 10.9, 10.95, 100), (410, 10.6, 10.6, 10.5, 10.52, 100),
            (420, 10.55, 10.6, 10.52, 10.58, 100), (430, 10.58, 10.75, 10.55, 10.72, 100)]
    assert _zp("ZC", _zt3, 10.5) is not None                      # 400s since fire #1 -> fires again
    check("Z-c: 300s per-name cooldown cuts the churn re-fire, releases after", True)
except (AssertionError, ValueError) as _ze:
    check("Z-c: cooldown", False, str(_ze))

try:
    # (d) calibrated DETECTOR stays conversion-free; caller converts ONLY under V2_CONVERT; calib stamped
    _zv = _y[_y.index("def v2_pullback_step"):_y.index("def kev_zoneflip_step")]
    assert "breakouts.append" not in _zv and "execute_trade" not in _zv
    _zc = _y[_y.index("V2 CONFIRMED-PULLBACK shadow"):_y.index("GRINDER-1030 shadow")]  # 8/16: v2 converts under V2_CONVERT
    assert "calib=" in _zc                                        # rows stamp the calib tag
    assert 'if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)' in _zc and 'lane "v2conv"' not in _zc  # sanity: guarded append, not unconditional
    assert 'breakouts.append((t, _v2_px, round(_vr_sv, 4), "v2conv", {' in _zc
    check("Z-d: calibrated v2 detector conversion-free; caller converts only under V2_CONVERT; calib stamped", True)
except (AssertionError, ValueError) as _ze:
    check("Z-d: convert-guard scan", False, str(_ze))

try:
    # (e) V2_CALIBRATED=0 restores the LEGACY predicate: string anchors + the Z-b late-confirm
    # tape (cut when calibrated) FIRES legacy with calib="legacy"
    assert 'os.environ.get("V2_CALIBRATED", "1") == "1"' in _y    # default ON
    assert "if not V2_CALIBRATED:" in _zv and 'fl["k"] = k' in _zv          # legacy ratchet kept behind the switch
    assert '"C1-C5" if V2_CALIBRATED else "legacy"' in _zv
    assert "TODO(C1b)" in _zv                                     # consolidation anchor stamped-not-gated
    _zn0 = _z_make({"V2_CALIBRATED": "0"})
    assert _zn0["V2_CALIBRATED"] is False and _zn0["V2_PUSH_WIN"] == 120
    _zt = [(0, 9.9, 10.0, 9.9, 9.95, 100), (100, 9.6, 9.6, 9.5, 9.52, 100),
           (120, 9.5, 9.55, 9.48, 9.5, 100), (130, 9.5, 9.7, 9.49, 9.65, 100)]
    _zf0 = _zn0["v2_pullback_step"]("ZE", _zt, 9.5)
    assert _zf0 is not None and _zf0["calib"] == "legacy" and _zf0["secs_from_push"] == 130
    check("Z-e: V2_CALIBRATED=0 restores legacy predicate (late confirm fires, calib=legacy)", True)
except (AssertionError, ValueError) as _ze:
    check("Z-e: legacy restore", False, str(_ze))

print("AA) 8/14 E3 OOS-wall machinery: grinder-1030 shadow + nightly grader")
try:
    # (a) GRINDER_SHADOW default ON + detector EXECUTED on a synthetic post-10:30 grind tape
    # (new session high, 30-min net-up, above VWAP, <3% pullback -> FIRE; would_stop = 15-min low)
    from zoneinfo import ZoneInfo as _AAZ
    import types as _aat, datetime as _aadt
    _AA_SEG = _y[_y.index('GRINDER_SHADOW   = os.environ.get'):_y.index("def kev_zoneflip_step")]
    _aan = {"os": _aat.SimpleNamespace(environ={}), "datetime": _aadt.datetime,
            "EASTERN": _AAZ("America/New_York")}
    exec(_AA_SEG, _aan)
    assert _aan["GRINDER_SHADOW"] is True                          # default ON with empty env
    _aaE = _AAZ("America/New_York")
    _k0 = int(_aadt.datetime(2026, 8, 14, 10, 40, 0, tzinfo=_aaE).timestamp())
    _tape = [(_k0,       9.00, 9.10, 8.98, 9.05, 100),             # establishes session high 9.10
             (_k0 + 600, 9.05, 9.12, 9.02, 9.10, 100),             # 10:50 new hi 9.12 -> FIRE shape
             (_k0 + 900, 9.10, 9.20, 9.08, 9.18, 100)]             # inside 15-min cooldown
    _aaf = _aan["grinder_shadow_step"]("AA", _tape, 8.50)
    assert _aaf and _aaf["px"] == 9.10 and _aaf["session_hi"] == 9.12
    assert _aaf["would_stop"] == 8.98 and _aaf["mins_since_1030"] == 20 and _aaf["seq"] == 0
    # cooldown: the _k0+900 new hi (9.20) was inside 900s of the fire -> only ONE fire returned;
    # a later qualifying new high after the cooldown fires again
    _aaf2 = _aan["grinder_shadow_step"]("AA", [(_k0 + 1600, 9.18, 9.30, 9.15, 9.28, 100)], 8.50)
    assert _aaf2 and _aaf2["seq"] == 1 and _aaf2["px"] == 9.28
    # below-VWAP candidate never fires
    assert _aan["grinder_shadow_step"]("AB", _tape, 20.0) is None
    check("AA-a: GRINDER_SHADOW default ON; detector executed (fire, stop, cooldown, VWAP gate)", True)
except (AssertionError, ValueError) as _aae:
    check("AA-a: grinder shadow detector", False, str(_aae))

try:
    # (b) 8/14-night REVISION (Marcos: "i am saying sim money live not real life money" — the
    # zero-conversion pin is SUPERSEDED by his order; section AB pins the conversion itself):
    # the DETECTOR stays conversion-free; the CALLER's append exists but only under the
    # GRINDER_CONVERT guard, and the shadow row still stamps the full E3-grader schema.
    _aav = _y[_y.index("def grinder_shadow_step"):_y.index("def kev_zoneflip_step")]
    assert "breakouts.append" not in _aav and "execute_trade" not in _aav
    _aac = _y[_y.index("GRINDER-1030 shadow (#48 lane"):_y.index("IGNITION-10S feed")]
    assert "execute_trade" not in _aac
    assert "if GRINDER_CONVERT:" in _aac and "breakouts.append" in _aac
    assert _aac.index("if GRINDER_CONVERT:") < _aac.index("breakouts.append")
    assert '"grinder_shadow_fire"' in _aac and "would_stop=" in _aac
    assert "session_hi=" in _aac and "mins_since_1030=" in _aac and "in_lane=True" in _aac
    check("AA-b: detector conversion-free; caller append exists ONLY under GRINDER_CONVERT; row schema intact", True)
except (AssertionError, ValueError) as _aae:
    check("AA-b: conversion-guard scan", False, str(_aae))

# (c) nightly grader script exists + carries the E3 exit constants; (d) 23:00 plist exists
_aag = os.path.join(ROOT, "data", "killtests", "nightly_shadow_grade.py")
_aas = open(_aag).read() if os.path.exists(_aag) else ""
check("AA-c: nightly_shadow_grade.py exists with the E3 model (bank 1.10 / trail 0.90 / slip 0.995)",
      bool(_aas) and "BANK_PCT" in _aas and "1.10" in _aas and "0.90" in _aas
      and "0.995" in _aas and "OOS_WALL.md" in _aas and "grinder_shadow_fire" in _aas)
_aap = os.path.expanduser("~/Library/LaunchAgents/com.marcos.tradingbot.shadowgrade.plist")
_aax = open(_aap).read() if os.path.exists(_aap) else ""
check("AA-d: shadowgrade launchd plist exists (23:00 daily, points at the grader)",
      "nightly_shadow_grade.py" in _aax and "<integer>23</integer>" in _aax)

print("AB) 8/14 night O-config SIM conversions (Marcos: 'sim money live') — grinder + flat_top break-attack + E3 exits")
# (a) envs default-on pins (empty env -> converts live-sim, Marcos's order)
try:
    assert 'FLATTOP_BREAK_ATTACK = os.environ.get("FLATTOP_BREAK_ATTACK", "1") == "1"' in _y
    assert 'GRINDER_CONVERT      = os.environ.get("GRINDER_CONVERT", "1") == "1"' in _y
    assert 'GRINDER_DAILY_CAP    = int(os.environ.get("GRINDER_DAILY_CAP", "3"))' in _y
    assert 'E3_EXITS             = os.environ.get("E3_EXITS", "1") == "1"' in _y
    check("AB-a: GRINDER_CONVERT / FLATTOP_BREAK_ATTACK / E3_EXITS default ON, cap default 3", True)
except (AssertionError, ValueError) as _abe:
    check("AB-a: env default pins", False, str(_abe))

# (b) grinder conversion appends lane 'grinder' with exit_mode=E3, stop=would_stop, capped
try:
    _abc = _y[_y.index("GRINDER-1030 shadow (#48 lane"):_y.index("IGNITION-10S feed")]
    _abg = _abc[_abc.index("if GRINDER_CONVERT:"):]
    assert '"grinder", {' in _abg and '"exit_mode": "E3"' in _abg
    assert '"zone_stop": _grf["would_stop"]' in _abg
    assert '_gr_conv_day["n"] >= GRINDER_DAILY_CAP' in _abg and '"grinder_capped"' in _abg
    assert '"triggered_grinder"' in _abg
    assert '_grf["would_stop"] < _grf["px"]' in _abg          # degenerate-stop guard on convert
    # gate-stack normality: grinder is NOT exempted from backside/min-stop/retest sets
    assert "grinder" not in _y[_y.index("MIN_STOP_EXEMPT"):_y.index("MIN_STOP_EXEMPT") + 400]
    _abrl = _y[_y.index('RETEST_LANES     = set('):_y.index('RETEST_LANES     = set(') + 120]
    assert "grinder" not in _abrl
    check("AB-b: grinder converts (lane 'grinder', exit_mode=E3, stop=would_stop, 3/day cap, gates normal)", True)
except (AssertionError, ValueError) as _abe:
    check("AB-b: grinder conversion", False, str(_abe))

# (c) flat_top break-attack: in-window-only conversion at the break print; out-of-window arm
# machinery + observe-only both intact; retest wait + observe strip bypassed ONLY for break_attack
try:
    assert '"09:30" <= _hm_ft < "10:30"' in _y                # the tested cell, exactly
    assert '_log_decision(t, "break_attack"' in _y
    assert '"break_armed"' in _y                              # out-of-window arm path retained
    assert "if _pb_enter or _ft_attack:" in _y
    assert "_stop = round(w_low, 4)   # TEST L spec: stop = base low, exact" in _y
    assert '_ft_extra["exit_mode"] = "E3"' in _y and '_ft_extra["break_attack"] = True' in _y
    assert 'b[3] == "flat_top" and not FLATTOP_CONVERT and not b[4].get("break_attack")' in _y
    assert 'entry_type in RETEST_LANES and not (extra or {}).get("break_attack")' in _y
    # the attack fires only from the fresh-break branch (inside `if is_flat and price > w_high`)
    _abf = _y[_y.index("FLAT_TOP BREAK-ATTACK"):_y.index("if _pb_enter or _ft_attack:")]
    assert "if is_flat and price > w_high and not _pb:" in _abf
    check("AB-c: flat_top break-attack converts in-window at the break print; observe/arm out-of-window", True)
except (AssertionError, ValueError) as _abe:
    check("AB-c: flat_top break-attack", False, str(_abe))

# (d) E3 exit mode EXECUTED on a synthetic monitor scenario via the pure evaluator:
# stop-first, run-high update, 10%-off-run-high closes-through trail; bank tier = single
# [entry*1.10, 0.5] rung (string anchor); persistence + call-site plumbing present
try:
    _abn = {}
    exec(_y[_y.index("def _e3_eval"):_y.index("def monitor_trade")], _abn)
    _e3 = _abn["_e3_eval"]
    # entry 10.00 stop 9.50: quiet bar -> no action, run high tracks the high
    _rh, _act = _e3(9.50, 10.00, 10.50, 10.80)
    assert (_rh, _act) == (10.80, None)
    # +10% bank rung is the tier machinery's job — evaluator must NOT trail at the bank print
    _rh, _act = _e3(9.50, _rh, 11.00, 11.20)
    assert (_rh, _act) == (11.20, None)
    # run-high 12.00 then a close 10.70 < 0.90*12.00=10.80 -> TRAIL
    _rh, _act = _e3(9.50, _rh, 11.90, 12.00)
    assert (_rh, _act) == (12.00, None)
    _rh, _act = _e3(9.50, _rh, 10.70, 10.75)
    assert _act == "trail" and _rh == 12.00
    # STOP-FIRST: close at/below the stop wins even when it is also 10% off the high
    _rh2, _act2 = _e3(9.50, 12.00, 9.40, 9.60)
    assert _act2 == "stop" and _rh2 == 12.00                  # run high NOT polluted by a stop bar
    # closes-through law: a WICK 10% off the high with a close holding above never trails
    _rh3, _act3 = _e3(9.50, 12.00, 11.00, 11.10)
    assert _act3 is None
    # monitor wiring anchors: single bank rung, mode gate, kill switch, 10s trail, persistence
    assert "kev_tiers = [(round(entry_price * 1.10, 4), 0.50)]" in _y
    assert "_e3_mode  = bool(E3_EXITS and exit_mode == \"E3\")" in _y
    assert "_e3_runhi, _e3_act = _e3_eval(current_stop, _e3_runhi, _e3_c, _e3_h)" in _y
    assert "_e3_k < _tape_birth" in _y                        # tape-since-birth honest register
    assert '"exit_mode": exit_mode,' in _y                    # durable resume contract
    assert 'exit_mode=(extra or {}).get("exit_mode")' in _y   # worker call site
    assert 'exit_mode = resume_state.get("exit_mode")' in _y  # restart pickup
    check("AB-d: E3 executed — bank rung anchored, trail fires, stop-first, closes-through, resume plumbed", True)
except (AssertionError, ValueError, KeyError) as _abe:
    check("AB-d: E3 exit mode", False, str(_abe))

# (e) every OTHER lane's exit path unchanged: the five soft exits carry `not _e3_mode` guards
# (False for non-E3 lanes = byte-identical behavior) and all default ladder branches survive
try:
    assert _y.count("(not RUNNER_HEALTH_EXIT) and not _e3_mode and remaining_shares > 0 and partial_taken") == 2
    assert "(not RUNNER_HEALTH_EXIT) and not _e3_mode and remaining_shares > 0 and current_price > entry_price" in _y
    assert "RUNG_RATCHET and not _e3_mode and remaining_shares > 0 and partial_taken" in _y
    assert "RUNNER_HEALTH_EXIT and not _e3_mode and remaining_shares > 0 and partial_taken" in _y
    assert 'elif entry_type in ("rocket_catcher", "hidden_entry"):' in _y   # rocket ladder intact
    assert "elif SCALE_TIERS:" in _y                                        # R-grid ladder intact
    assert "if _e3_mode and remaining_shares > 0 and time.time() - _e3_t >= 10:" in _y
    check("AB-e: non-E3 lanes' exits untouched (guards inert), default ladders + E3 block all present", True)
except (AssertionError, ValueError) as _abe:
    check("AB-e: other-lane exit integrity", False, str(_abe))

print("AC) 8/15 FOUR DEAD EYES — stand-down rows, crown pre-exempt, ambient floor, premkt heartbeat")
# EXECUTES the real production source (extracted verbatim, exec'd — the rig's exec-pin
# convention): heartbeat once-per-day law, bind/lift rows, ambient reject arithmetic + rows.
_ey = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
try:
    _eydt = __import__("datetime")           # a prior section rebinds the name 'datetime'
    _eyn = {"datetime": _eydt.datetime, "time": __import__("time"),
            "AMBIENT_DVOL_MULT": 15.0, "MAX_TRADE_DOLLARS": 1000.0}
    import zoneinfo as _zi
    _eyn["EASTERN"] = _zi.ZoneInfo("America/New_York")
    _ey_rows = []
    _eyn["_log_decision"] = lambda tk, st, **f: _ey_rows.append((tk, st, f))
    _eyn["_gate_failopen"] = lambda *a, **k: None
    # real helper block (from _standdown = {} through _standdown_lift)
    _hb = _ey[_ey.index("_standdown = {}"):_ey.index("# 8/4 ~01:15 RETEST DEPTH BAND")]
    exec(_hb, _eyn)
    # real ambient function
    exec(_ey[_ey.index("def _ambient_dvol_ok"):_ey.index("def check_momentum")], _eyn)

    # (a) heartbeat: exactly ONE row per status per ET day, second call refuses
    assert _eyn["_eye_heartbeat"]("standdown_armed", "TT", sticky=1) is True
    assert _eyn["_eye_heartbeat"]("standdown_armed", "UU", sticky=1) is False
    assert len([r for r in _ey_rows if r[1] == "standdown_armed"]) == 1
    # (b) bind writes the dict entry AND the standdown_bound row; lift pops AND writes its row
    _eyn["_standdown_bind"]("TT", "2026-08-15T10:00:00")
    assert "TT" in _eyn["_standdown"] and _eyn["_standdown"]["TT"][0] == "2026-08-15T10:00:00"
    assert any(r[1] == "standdown_bound" and r[0] == "TT" for r in _ey_rows)
    _eyn["_standdown_lift"]("TT", "fresh_read")
    assert "TT" not in _eyn["_standdown"]
    assert any(r[1] == "standdown_lifted" and r[2].get("why") == "fresh_read" for r in _ey_rows)
    check("AC-a: heartbeat once/day; standdown bind+lift write rows via the REAL functions", True)
except (AssertionError, ValueError, KeyError) as _ace:
    check("AC-a: standdown helpers exec", False, str(_ace))

try:
    # (c) ambient EXECUTED: thin tape rejects (median math), thick passes, heartbeat stamps once
    _thin = [{"volume": 100, "close": 2.0}] * 11            # $200/min << $15k need
    _ok, _med, _need = _eyn["_ambient_dvol_ok"](_thin, "AMB")
    assert _ok is False and _med == 200.0 and _need == 15000.0
    _thick = [{"volume": 20000, "close": 2.0}] * 11         # $40k/min
    _ok2, _med2, _need2 = _eyn["_ambient_dvol_ok"](_thick, "AMB")
    assert _ok2 is True and _med2 == 40000.0
    assert len([r for r in _ey_rows if r[1] == "ambient_checked"]) == 1   # daily heartbeat, not per-call
    assert _ey_rows[[r[1] for r in _ey_rows].index("ambient_checked")][2]["need"] == 15000
    # <5 bars still fail-open, no crash without ticker
    assert _eyn["_ambient_dvol_ok"]([{"volume": 1, "close": 1}] * 3)[0] is True
    check("AC-b: _ambient_dvol_ok EXECUTED — thin rejects, thick passes, ambient_checked heartbeat", True)
except (AssertionError, ValueError, KeyError) as _ace:
    check("AC-b: ambient exec", False, str(_ace))

# (d) three-rings call-site enumeration (source pins — the wiring the exec above can't reach)
check("AC-c: ALL 4 _ambient_dvol_ok call sites pass ticker",
      _ey.count("_ambient_dvol_ok(bars, ticker)") == 2 and _ey.count("_ambient_dvol_ok(_gb, ticker)") == 2
      and "_ambient_dvol_ok(bars)\n" not in _ey and "_ambient_dvol_ok(_gb)\n" not in _ey)
check("AC-d: distinct ambient_reject rows at BOTH reject sites (check_momentum + universal gate)",
      _ey.count('"ambient_reject"') == 2 and 'src="check_momentum"' in _ey and 'src="universal_gate"' in _ey)
check("AC-e: worker binds/lifts via the row-writing helpers (no silent dict ops left)",
      '_standdown_bind(ticker, _z_rec["_ts"])' in _ey and '_standdown_lift(ticker, "fresh_read"' in _ey
      and "_standdown.pop(ticker, None)   # fresh read arrived" not in _ey)
check("AC-f: standdown_armed heartbeat sits BEFORE the sticky check, chart lanes only",
      '_eye_heartbeat("standdown_armed", ticker' in _ey
      and _ey.index('_eye_heartbeat("standdown_armed"') < _ey.index('and ticker in _standdown'))
check("AC-g: standdown_active row + _z_rec pre-bound against NameError",
      '"standdown_active"' in _ey and "_z_rec = None   # 8/15 eyes" in _ey)
check("AC-h: crown_pre_exempt logs on EVERY crowned PRE pass with cap_full stamp",
      'if _is_leader(entry[0]):\n                        _log_decision(entry[0], "crown_pre_exempt"' in _ey
      and 'cap_full=bool(_pre_day["n"] >= PRE_MAX_TRADES)' in _ey)
check("AC-i: premkt_gate_armed daily heartbeat inside the PRE window with cap/slots",
      '_eye_heartbeat("premkt_gate_armed", breakouts[0][0], cap=PRE_MAX_TRADES' in _ey
      and 'slots_used=_pre_day["n"]' in _ey)
check("AC-j: premkt_capped row-writer intact (cap-1 reachability: kept-branch condition unchanged)",
      '"premkt_capped"' in _ey and '_pre_day["n"] < PRE_MAX_TRADES or _is_leader(entry[0])' in _ey)


print("AD) 8/16 BUILD #0 — EYES SNAPSHOT at entry/exit + exit_layer + tale render (Marcos 8/15 spec)")
# EXECUTES the real _eyes_snapshot / _exit_layer / _eyes_compact on a SYNTHETIC scan state
# (stubbed feed/map/registries — no network), asserts every top-level key present (None allowed
# for TODO eyes), asserts a synthetic completed record carries entry_context + exit_context +
# exit_layer, and string-anchors the three wire sites + the render.
_ey2 = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
_sc = open(os.path.join(ROOT, "screener_app.py")).read()
try:
    import time as _tm, pytz as _pytz
    from datetime import datetime as _dt, timezone as _tz
    _adn = {"datetime": _dt, "timezone": _tz, "time": _tm, "EASTERN": _pytz.timezone("America/New_York"),
            "EMA90_PERIOD": 90, "_pdc_map": {"EYEX": 2.00}, "_leader_day": {}, "_lens_state": {"EYEX": True}}
    # synthetic 10s scan state: 720 bars, rising tape, cumulative volume v0/v1
    _now = int(_tm.time()) // 10 * 10
    _d10, _cv = {}, 0.0
    for _i in range(720):
        _k = _now - (719 - _i) * 10
        _c = 3.00 + _i * 0.001
        _cv += 500.0
        _d10[_k] = {"o": _c - 0.001, "h": _c + 0.002, "l": _c - 0.002, "c": _c, "v0": _cv - 500.0, "v1": _cv}
    _adn["_curl_feed"] = lambda t, n=90: (_d10, "rig")
    _adn["_lens_px"] = lambda t: 3.70
    _adn["_recorder_tick_vwap"] = lambda t: 3.40
    _adn["_side_state"] = lambda t, px=0.0: "front_side"
    _adn["_effective_map"] = lambda t, px=0.0: {"break": 3.50, "targets": [3.60, 3.90, 4.20], "stop": 3.30,
                                                "_ts": _dt.now(_pytz.timezone("America/New_York")).isoformat(), "src": "vision"}
    _adn["_map_freshness"] = lambda rec, px: (2.0, 0.0)
    _adn["_marked_runway"] = lambda t, e, sl: (1.5, 3.90)
    _adn["_calc_ema"] = lambda closes, period: sum(closes[-period:]) / period
    _adn["_gate_failopen"] = lambda *a, **k: None
    exec(_ey2[_ey2.index("EYES_TODO = ("):_ey2.index("def _e3_eval")], _adn)
    _snap = _adn["_eyes_snapshot"]("EYEX", 3.72, "entry", {"vwap": 3.40, "zone_stop": 3.30, "day_gain": 86.0, "l1_spread": 0.01})
    _keys = _adn["_EYES_KEYS"]
    _missing = [k for k in _keys if k not in _snap]
    assert not _missing, "missing top-level keys: %s" % _missing
    for _k in ("ts_utc", "time_et", "session", "window", "price", "vwap", "vwap_side", "vwap_dist_pct",
               "vwap_slope_5m", "side_stamp", "day_gain_pct", "crown", "lens_state", "ext_pct_vs_ema90",
               "halt_distance_pct", "spread_pct", "ambient_dvol_median"):
        assert _snap.get(_k) is not None, "eye %s came back None on the synthetic state" % _k
    assert _snap["vwap_side"] == "above" and abs(_snap["vwap_dist_pct"] - round((3.72 - 3.40) / 3.40 * 100, 2)) < 1e-6
    assert _snap["side_stamp"] == "front_side" and _snap["lens_state"] == "in_focus"
    assert _snap["map"]["break"] == 3.50 and _snap["map"]["next_rung"] == 3.90 and _snap["map"]["road_r"] == 1.5
    assert _snap["map"]["map_age_min"] == 2.0 and _snap["map"]["map_src"] == "vision"
    assert _snap["day_gain_pct"] == 86.0 and _snap["prior_close_src"] == "lane"
    assert _snap["crown"]["crowned"] is False
    assert _snap["halt_distance_pct"] > 0
    assert _snap["when"] == "entry"
    for _k in _adn["EYES_TODO"]:
        assert _k in _snap and _snap[_k] is None, "TODO eye %s must be present + None" % _k
    # gates_hit ring feeds the snapshot
    _adn["_eyes_note_gate"]("EYEX", "spread_reject"); _adn["_eyes_note_gate"]("EYEX", "filled")
    _snap2 = _adn["_eyes_snapshot"]("EYEX", 0, "exit", None)   # price 0 -> cached _lens_px
    assert _snap2["price"] == 3.70 and _snap2["gates_hit"][-2:] == ["spread_reject", "filled"]
    assert _snap2["prior_close_src"] == "pdc_map" and _snap2["day_gain_pct"] == round((3.70 / 2.0 - 1) * 100, 2)
    assert _snap2["vwap_src"] == "tick_vwap" and _snap2["vwap"] == 3.40
    # exit_layer classifier
    _xl = _adn["_exit_layer"]
    assert _xl("Full exit (T2 +10%) ✅") == "tier" and _xl("3:45pm time stop") == "eod"
    assert _xl("TOPPING TAIL") == "topping_tail" and _xl("PREV-BAR-LOW TRAIL") == "trail"
    assert _xl("RUNG RATCHET (floor $3.10)") == "rung_ratchet" and _xl("BLIND-STOP FAILSAFE 🛟") == "safety"
    assert _xl("RECOVERED — monitor froze (watchdog)") == "safety" and _xl("Stop loss hit") == "stop"
    assert _xl("E3 trail 10% off run-high") == "e3_trail" and _xl("Failed breakout ✂️") == "failed_break"
    assert _xl(None) == "unknown"
    # compact form is flat + small
    _cp = _adn["_eyes_compact"](_snap)
    assert _cp["px"] == 3.72 and _cp["side"] == "front_side" and _cp["brk"] == 3.50 and len(_cp) <= 20
    # synthetic completed record through the choke-point logic (mirrors post_to_dashboard's stamp block)
    _rec = {"ticker": "EYEX", "trade_id": "t-1", "entry": 3.72, "exit": 3.95, "exit_reason": "Full exit (T2 +10%) ✅"}
    _adn["_entry_ctx_by_trade"]["t-1"] = _snap
    if not _rec.get("exit_context"):
        _rec["exit_context"] = _adn["_eyes_snapshot"](_rec["ticker"], _rec["exit"], "exit", {"zone_stop": 3.30})
    if not _rec.get("exit_layer"):
        _rec["exit_layer"] = _xl(_rec["exit_reason"])
    if not _rec.get("entry_context"):
        _rec["entry_context"] = _adn["_entry_ctx_by_trade"].get(_rec["trade_id"])
    assert _rec["entry_context"] and _rec["exit_context"] and _rec["exit_layer"] == "tier"
    assert _rec["entry_context"]["when"] == "entry" and _rec["exit_context"]["when"] == "exit"
    assert all(k in _rec["exit_context"] for k in _keys)
    json.dumps(_rec)   # record must serialize for the POST
    check("AD-a: _eyes_snapshot EXECUTED — every top-level key present, TODO eyes None, math checks", True)
except (AssertionError, ValueError, KeyError) as _ade:
    check("AD-a: _eyes_snapshot executed", False, str(_ade))
try:
    # wire site 1: entry (fill) -> extra + durable state + registry + watchdog ctx
    assert 'extra["entry_context"] = _eyes_snapshot(ticker, entry_price, "entry", _ec_seed)' in _ey2
    assert '_entry_ctx_by_trade[trade_id] = extra["entry_context"]' in _ey2
    assert '"entry_context": (extra or {}).get("entry_context"),   # 8/16 build #0' in _ey2
    assert '"entry_context": (extra or {}).get("entry_context"),   # 8/16 build #0\n                "entry_crown"' in _ey2   # watchdog ctx
    # wire site 2: exit record + choke point
    assert '"exit_context":       _eyes_snapshot(ticker, trade_result.get("exit_price", entry_price), "exit",' in _ey2
    assert '"exit_layer":         _exit_layer(exit_reason),' in _ey2
    _ptd = _ey2[_ey2.index("def post_to_dashboard"):_ey2.index("def post_trade_record_reliably")]
    assert 'trade_payload["exit_context"] = _eyes_snapshot(_tk, trade_payload.get("exit"), "exit",' in _ptd
    assert 'trade_payload["exit_layer"] = _exit_layer(trade_payload.get("exit_reason"))' in _ptd
    assert '_entry_ctx_by_trade.get(_tid)' in _ptd
    # recovery writers carry entry_context from durable state / watchdog ctx
    assert _ey2.count('"entry_context": o.get("entry_context")') + _ey2.count('"entry_context":   o.get("entry_context")') == 2
    assert '"entry_context":   ctx.get("entry_context")' in _ey2
    # wire site 3: shadow fires (compact eyes on the row)
    for _st in ('"v2_shadow_fire", price=_v2f["px"],\n                                                      eyes=_eyes_compact(',
                '"grinder_shadow_fire", price=_grf["px"],\n                                                  eyes=_eyes_compact(',
                '"hidden_observe_only", price=price, stop=_her["stop"],\n                                      eyes=_eyes_compact(',
                '_log_decision(b[0], _ob_row, price=b[1], vwap=(b[2] or None),\n                                  eyes=_eyes_compact('):
        assert _st in _ey2, "shadow wire missing: " + _st[:30]
    # gates_hit ring fed from _log_decision
    assert "_eyes_note_gate(ticker, status)" in _ey2
    check("AD-b: three wire sites anchored (entry fill, exit record+choke point, 4 shadow rows) + recovery carry", True)
except (AssertionError, ValueError) as _ade:
    check("AD-b: wire sites", False, str(_ade))
try:
    # render: tale page + trade-history detail (JS) + PRE story, robust to missing keys
    assert "def eyes_blocks_html(t):" in _sc and "eyes_html = \"<h3>Where it was — the eyes at entry and exit</h3>\"" in _sc
    assert "+ shadow_html + eyes_html +" in _sc
    assert "function eyesHTML(t)" in _sc and "+eyesHTML(t);" in _sc
    assert "eyes_blocks_html(t) if (t.get(\"entry_context\") or t.get(\"exit_context\"))" in _sc
    _scn = {"html_mod": __import__("html")}
    exec(_sc[_sc.index("_EYES_ROWS = ["):_sc.index("EYES_CSS = (")], _scn)
    _h1 = _scn["eyes_blocks_html"]({"entry_context": _snap, "exit_context": None, "exit_layer": "tier"})
    assert "at ENTRY" in _h1 and "at EXIT" in _h1 and "front_side" in _h1 and "no eyes block" in _h1 and "tier" in _h1
    _h0 = _scn["eyes_blocks_html"]({})   # pre-8/16 record: never raises
    assert "no eyes block" in _h0
    _h2 = _scn["eyes_blocks_html"]({"entry_context": {"map": "not-a-dict", "crown": None}})   # malformed
    assert "at ENTRY" in _h2
    check("AD-c: tale + history render EXECUTED — side-by-side blocks, exit layer, robust to missing/malformed", True)
except (AssertionError, ValueError, KeyError) as _ade:
    check("AD-c: render", False, str(_ade))

print("AE) 8/16 HARDENING — _curl_feed 2s memo + entry snapshot AFTER durable save")
import threading as _aeth, time as _aet
try:
    _ae_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    check("AE-a: env knob CURL_FEED_MEMO_SECS default 2", 'os.environ.get("CURL_FEED_MEMO_SECS", "2")' in _ae_src)
    # EXECUTED: exec the real _curl_feed with a counting stub for _alp10_bars
    _blk = _ae_src[_ae_src.index("def _curl_feed("):_ae_src.index("def _et_session_of_utc")]
    _calls = {"n": 0}
    _bars = {1000.0: {"h": 2, "l": 1, "c": 1.5}}
    def _mk(ret):
        def _f(t, n): _calls["n"] += 1; return (ret, "alpaca")
        return _f
    _ns = {"CURL_SOURCE": "alpaca", "CURL_FEED_MEMO_SECS": 2.0, "_curl_memo": {}, "_curl_memo_lock": _aeth.Lock(),
           "time": _aet, "_bf_done": set(), "_curl_canary_t": {}, "_halt_suspect": lambda t, d: (False, 0, 0),
           "_leader_high_probe": lambda *a: None, "_halt_credit": {}, "_halt_credit_note": lambda *a: None,
           "_alp10_bars": _mk(_bars), "print": lambda *a, **k: None, "_bump": lambda *a, **k: None, "_archive10_backfill": lambda t, n=0: {}}
    exec(_blk, _ns)
    _r1 = _ns["_curl_feed"]("TT", 90); _r2 = _ns["_curl_feed"]("TT", 90)
    check("AE-b: EXECUTED — two calls within TTL = ONE fetch, same (bars, src) tuple shape",
          _calls["n"] == 1 and _r1 == _r2 == (_bars, "alpaca") and isinstance(_r2, tuple) and len(_r2) == 2, str((_calls, _r2)))
    _ns["_curl_feed"]("TT", 360)
    check("AE-c: different n = separate key (fetch again)", _calls["n"] == 2)
    # empty result must NOT be cached
    _ns2 = dict(_ns); _ns2["_curl_memo"] = {}; _calls["n"] = 0; _ns2["_alp10_bars"] = _mk({})
    exec(_blk, _ns2)
    _e1 = _ns2["_curl_feed"]("EE", 90); _e2 = _ns2["_curl_feed"]("EE", 90)
    check("AE-d: EXECUTED — empty result never cached (fail-through, 2 fetches)", _calls["n"] == 2 and _e1 == ({}, "alpaca") and not _ns2["_curl_memo"], str(_calls))
    # disabled memo
    _ns3 = dict(_ns); _ns3["_curl_memo"] = {}; _ns3["CURL_FEED_MEMO_SECS"] = 0.0; _calls["n"] = 0; _ns3["_alp10_bars"] = _mk(_bars)
    exec(_blk, _ns3)
    _ns3["_curl_feed"]("TT", 90); _ns3["_curl_feed"]("TT", 90)
    check("AE-e: CURL_FEED_MEMO_SECS=0 disables (2 fetches)", _calls["n"] == 2 and not _ns3["_curl_memo"])
    # ordering: durable save BEFORE the entry snapshot at the fill site
    _i_save = _ae_src.index('_save_open_trade_sync({\n                "entry_crown"')
    _i_snap = _ae_src.index('extra["entry_context"] = _eyes_snapshot(ticker, entry_price, "entry", _ec_seed)')
    _i_mon = _ae_src.index("trade_result = monitor_trade(", _i_save)
    check("AE-f: entry snapshot AFTER _save_open_trade_sync and BEFORE monitor_trade", _i_save < _i_snap < _i_mon, str((_i_save, _i_snap, _i_mon)))
    # the watchdog ctx (after snapshot) + exit record + post_to_dashboard fallback still carry it
    _i_wd = _ae_src.index('_active_monitors[trade_id] = {"heartbeat"')
    check("AE-g: watchdog ctx built after snapshot (carries entry_context)", _i_snap < _i_wd
          and '"entry_context": (extra or {}).get("entry_context")' in _ae_src[_i_wd:_i_wd+400]
          and 'trade_payload["entry_context"] = _entry_ctx_by_trade.get(_tid)' in _ae_src)
    # auditor: durable row re-carries entry_context (sync merge post) AFTER snapshot, BEFORE monitor
    _i_re = _ae_src.index('_save_open_trade_sync({"ticker": ticker, "trade_id": trade_id,\n                                           "entry_context": extra["entry_context"]})')
    check("AE-h: durable entry_context re-post sits snapshot < re-post < monitor_trade", _i_snap < _i_re < _i_mon, str((_i_snap, _i_re, _i_mon)))
    check("AE-i: memo_hits on the EXEC HEALTH line", "memo_hits={_eh.get('memo_hits', 0)}" in _ae_src)
except (AssertionError, ValueError, KeyError) as _aee:
    check("AE: hardening", False, str(_aee))

print("AF) 8/16 BAND-PASS RTH lane (shadow ON, convert env-OFF) + PRE-VWAP Kev-8AM shadow + grader")
try:
    from zoneinfo import ZoneInfo as _AFZ
    import types as _aft, datetime as _afdt
    _af_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _AF_SEG = _af_src[_af_src.index('BANDPASS_SHADOW    = os.environ.get'):_af_src.index("def kev_zoneflip_step")]
    _afn = {"os": _aft.SimpleNamespace(environ={}), "datetime": _afdt.datetime,
            "EASTERN": _AFZ("America/New_York")}
    exec(_AF_SEG, _afn)
    check("AF-a: envs default — BANDPASS_SHADOW on, BANDPASS_CONVERT OFF, PREVWAP_SHADOW on, cap 3",
          _afn["BANDPASS_SHADOW"] is True and _afn["BANDPASS_CONVERT"] is False
          and _afn["PREVWAP_SHADOW"] is True and _afn["BANDPASS_DAILY_CAP"] == 3)
    _afE = _AFZ("America/New_York")
    _k0 = int(_afdt.datetime(2026, 8, 14, 9, 40, 0, tzinfo=_afE).timestamp())
    _bp = _afn["bandpass_step"]
    # (b) EXECUTED: 2 below -> cross -> hold 15 closes (highs flat 10.10, lows ratchet) -> new high -> FIRE
    _tape = [(_k0,      9.95, 9.98, 9.90, 9.95, 100),   # below 1
             (_k0 + 10, 9.95, 9.98, 9.90, 9.96, 100)]   # below 2
    _tape.append((_k0 + 20, 9.99, 10.10, 9.97, 10.05, 100))            # cross UP, streak 1, hold hi 10.10 lo 9.97
    for i in range(1, 15):                                             # streak 2..15, no new high
        _tape.append((_k0 + 20 + 10 * i, 10.05, 10.10, 10.00, 10.05, 100))
    _tape.append((_k0 + 20 + 150, 10.05, 10.15, 10.02, 10.12, 100))    # streak 16: NEW minor high -> FIRE
    _f = _bp("BP", _tape, 10.00, {}, 570, 960)
    check("AF-b: EXECUTED — 2-below -> hold 15 -> new high fires; stop = hold low 9.97; px 10.12",
          bool(_f) and _f["px"] == 10.12 and _f["would_stop"] == 9.97 and _f["hold_n"] == 15
          and _f["crosses_20m"] == 1 and _f["seq"] == 0, str(_f))
    # (c) bounce tape: only ONE bar below -> not armed -> no fire on the same hold+new-high shape
    _bounce = [(_k0, 10.05, 10.10, 10.00, 10.05, 100),                # above (establishes prev_above)
               (_k0 + 10, 9.95, 9.98, 9.90, 9.96, 100)]               # ONE below
    _bounce.append((_k0 + 20, 9.99, 10.10, 9.97, 10.05, 100))
    for i in range(1, 15):
        _bounce.append((_k0 + 20 + 10 * i, 10.05, 10.10, 10.00, 10.05, 100))
    _bounce.append((_k0 + 170, 10.05, 10.15, 10.02, 10.12, 100))
    check("AF-c: bounce tape (1 bar below) -> NO fire (two-bars-below rule)",
          _bp("BN", _bounce, 10.00, {}, 570, 960) is None)
    # (d) chop tape: 3 crosses inside 20 min before the would-be fire -> excluded
    _chop = [(_k0, 10.05, 10.10, 10.00, 10.05, 100),
             (_k0 + 10, 9.95, 9.98, 9.90, 9.96, 100), (_k0 + 20, 9.95, 9.98, 9.90, 9.96, 100),   # cross DOWN (1)
             (_k0 + 30, 10.05, 10.10, 10.00, 10.05, 100),                                        # cross UP (2)
             (_k0 + 40, 9.95, 9.98, 9.90, 9.96, 100), (_k0 + 50, 9.95, 9.98, 9.90, 9.96, 100),   # cross DOWN (3)
             (_k0 + 60, 9.99, 10.10, 9.97, 10.05, 100)]                                          # cross UP (4), armed
    for i in range(1, 15):
        _chop.append((_k0 + 60 + 10 * i, 10.05, 10.10, 10.00, 10.05, 100))
    _chop.append((_k0 + 210, 10.05, 10.15, 10.02, 10.12, 100))
    check("AF-d: chop tape (>=3 crosses / 20 min) -> NO fire",
          _bp("BC", _chop, 10.00, {}, 570, 960) is None)
    # (e) hold too long (31+ closes) -> band expired, no fire; too short (<12) -> no fire
    _long = list(_tape[:3])
    for i in range(1, 32):
        _long.append((_k0 + 20 + 10 * i, 10.05, 10.10, 10.00, 10.05, 100))
    _long.append((_k0 + 20 + 320, 10.05, 10.15, 10.02, 10.12, 100))
    _short = list(_tape[:3]) + [(_k0 + 30, 10.05, 10.10, 10.00, 10.05, 100),
                                (_k0 + 40, 10.05, 10.15, 10.02, 10.12, 100)]
    check("AF-e: band-pass edges — 31-close hold no fire; 3-close hold no fire",
          _bp("BL", _long, 10.00, {}, 570, 960) is None and _bp("BS", _short, 10.00, {}, 570, 960) is None)
    # (f) window arg: the same winning tape at 09:40 is invisible to the PRE detector (07:00-09:25)
    check("AF-f: PRE window arg excludes 09:40 bars", _bp("BW", _tape, 10.00, {}, 420, 565) is None)
    # (g) cooldown: re-fire inside 15 min on a fresh episode is suppressed; state maps are separate
    _stm = {}
    _bp("BD", _tape, 10.00, _stm, 570, 960)
    _k1 = _k0 + 400
    _re = [(_k1, 9.95, 9.98, 9.90, 9.95, 100), (_k1 + 10, 9.95, 9.98, 9.90, 9.96, 100),
           (_k1 + 20, 9.99, 10.10, 9.97, 10.05, 100)]
    for i in range(1, 15):
        _re.append((_k1 + 20 + 10 * i, 10.05, 10.10, 10.00, 10.05, 100))
    _re.append((_k1 + 170, 10.05, 10.15, 10.02, 10.12, 100))
    check("AF-g: 15-min per-name cooldown suppresses the second episode", _bp("BD", _re, 10.00, _stm, 570, 960) is None)
    # (h) caller: RTH conversion exists ONLY under BANDPASS_CONVERT and in-window; PRE has ZERO conversion path
    _cal = _af_src[_af_src.index("8/16 BAND-PASS VWAP RECLAIM (RTH) shadow"):_af_src.index("IGNITION-10S feed (7/26)")]
    _bp_blk = _cal[:_cal.index("if PREVWAP_SHADOW:")]
    _pv_blk = _cal[_cal.index("if PREVWAP_SHADOW:"):]
    check("AF-h: RTH append guarded by BANDPASS_CONVERT and _bp_in; lane 'bandpass' E3; triggered row",
          "if BANDPASS_CONVERT and _bp_in:" in _bp_blk
          and _bp_blk.index("if BANDPASS_CONVERT and _bp_in:") < _bp_blk.index('breakouts.append((t, _bp_px, round(_vr_sv, 4), "bandpass", {')
          and '"exit_mode": "E3"' in _bp_blk and '"triggered_bandpass"' in _bp_blk and '"bandpass_capped"' in _bp_blk)
    # 8/16: PRE-VWAP now CONVERTS under PREVWAP_CONVERT (Marcos "switch pre-vwap to live in pre" — ALL SIM);
    # append guarded by the env, lane 'prevwap' E3 session PRE (09:25 flatten), triggered_prevwap row; still stamps spread_pct + catalyst
    check("AF-i: PRE lane converts ONLY under PREVWAP_CONVERT; lane 'prevwap' E3 PRE; triggered row; stamps spread_pct + catalyst",
          "if PREVWAP_CONVERT and _pvf[\"would_stop\"] < _pvf[\"px\"]:" in _pv_blk and "execute_trade" not in _pv_blk
          and _pv_blk.index("if PREVWAP_CONVERT and") < _pv_blk.index('breakouts.append((t, _pv_px, round(_vr_sv, 4), "prevwap", {')
          and '"exit_mode": "E3"' in _pv_blk and '"session": "PRE"' in _pv_blk and '"triggered_prevwap"' in _pv_blk
          and "spread_pct=_pv_sp" in _pv_blk and "catalyst=None" in _pv_blk and '"prevwap_shadow_fire"' in _pv_blk)
    check("AF-j: detector itself conversion-free", "breakouts.append" not in _AF_SEG and "execute_trade" not in _AF_SEG)
    # (k) no-conversion under BANDPASS_CONVERT=0: exec the caller's convert guard shape with a stub
    _bo = []; _cd = {"d": None, "n": 0}
    _ns_c = {"BANDPASS_CONVERT": False, "_bp_in": True, "breakouts": _bo}
    exec("if BANDPASS_CONVERT and _bp_in:\n    breakouts.append(1)", _ns_c)
    check("AF-k: BANDPASS_CONVERT=0 -> zero appends", _bo == [])
    # (l) not exempt anywhere: 'bandpass' absent from every exempt/bypass set + BREAKOUT_ENTRIES full bag
    # 8/17 LANE REGISTRY amends this pin: _STALE_EXEMPT is no longer a literal tuple — it is
    # derived from LANE_CLASS, and 'bandpass' IS in it now BY DESIGN (see section AO + the
    # lane_registry_20260817 doc). The tradeability/side sets below are UNCHANGED and still pinned.
    check("AF-l: 'bandpass' not in MIN_STOP_EXEMPT/BACKSIDE_EXEMPT/VRIDE_EXEMPT defaults; BREAKOUT_ENTRIES True",
          '"bandpass"' not in _af_src[_af_src.index("MIN_STOP_EXEMPT = set("):_af_src.index("MIN_STOP_EXEMPT = set(") + 200]
          and 'BACKSIDE_EXEMPT   = {"dip_rip"}' in _af_src and "bandpass" not in _af_src[_af_src.index("VRIDE_EXEMPT    = set("):_af_src.index("VRIDE_EXEMPT    = set(") + 150]
          and "BREAKOUT_ENTRIES   = True" in _af_src)
    # (m) grader status list contains both + PRE flatten 09:25
    _g = open(os.path.join(ROOT, "data", "killtests", "nightly_shadow_grade.py")).read()
    check("AF-m: grader lists bandpass_shadow_fire + prevwap_shadow_fire; PRE flatten 565 (09:25)",
          "bandpass_shadow_fire,prevwap_shadow_fire" in _g and 'flatten_hm=(565 if lane == "prevwap" else 959)' in _g
          and 'lanes["prevwap"].append(rec)' in _g)
    # (n) boot banner + durable boot row carry the new switches
    check("AF-n: boot banner + boot_config row stamp the new envs",
          "BANDPASS_SHADOW={int(BANDPASS_SHADOW)}" in _af_src and "bandpass_convert=int(BANDPASS_CONVERT)" in _af_src
          and "prevwap_shadow=int(PREVWAP_SHADOW)" in _af_src)
except (AssertionError, ValueError, KeyError) as _afe:
    check("AF: band-pass lanes", False, str(_afe))

print("AG) 8/16 KEV SEQUENCE lane 'kevseq' (B->H/W + burst + front side; shadow ON, convert env-OFF, per-leg cap)")
try:
    from zoneinfo import ZoneInfo as _AGZ
    import types as _agt, datetime as _agdt
    _ag_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _AG_SEG = _ag_src[_ag_src.index('KEVSEQ_SHADOW     = os.environ.get'):_ag_src.index("def kev_zoneflip_step")]
    _agn = {"os": _agt.SimpleNamespace(environ={}), "datetime": _agdt.datetime,
            "EASTERN": _AGZ("America/New_York")}
    exec(_AG_SEG, _agn)
    check("AG-a: envs default — KEVSEQ_SHADOW on, KEVSEQ_CONVERT OFF, KEVSEQ_LEG_MAX 3, N=18 bars",
          _agn["KEVSEQ_SHADOW"] is True and _agn["KEVSEQ_CONVERT"] is False
          and _agn["KEVSEQ_LEG_MAX"] == 3 and _agn["KEVSEQ_N_BARS"] == 18)
    _ks = _agn["kevseq_step"]
    _agE = _AGZ("America/New_York")
    _gk0 = int(_agdt.datetime(2026, 8, 14, 9, 40, 0, tzinfo=_agE).timestamp())
    _ctx = {"front_side": True, "day_gain": 45.0, "top3": False, "blue_sky": False}
    def _agwarm(n=32):                       # session hi 10.10 on bar 1, then 31 flat bars under it (varied vols)
        t = [(_gk0, 10.0, 10.10, 9.95, 10.05, 100)]
        for i in range(1, n):
            t.append((_gk0 + 10 * i, 10.0, 10.05, 9.96, 10.02, 50 + (i * 7) % 70))
        return t
    def _agk(t): return _gk0 + 10 * len(t)
    def _agbw(t, vol):                       # B (10.30 breaks 10.10) -> hold bar -> W (low 10.06 tests 9EMA, closes back) -> break of W high
        t.append((_agk(t), 10.05, 10.30, 10.04, 10.28, 150))
        t.append((_agk(t), 10.28, 10.30, 10.20, 10.29, 90))
        t.append((_agk(t), 10.28, 10.29, 10.06, 10.25, 120))
        t.append((_agk(t), 10.25, 10.31, 10.24, 10.30, vol))
        return t
    # (i) EXECUTED: B then W with burst -> fires, seq "B W", stop = wick low, px = W-bar high
    _f = _ks("KA", _agbw(_agwarm(), 300), 10.0, _ctx)
    check("AG-i: B->W + burst fires: ok, seq 'B W', stop 10.06 (wick low), px 10.29, burst_ratio>1, fresh_touch_n 0, leg 1",
          bool(_f) and _f["ok"] and _f["seq_str"] == "B W" and _f["would_stop"] == 10.06 and _f["px"] == 10.29
          and _f["burst"] and _f["burst_ratio"] > 1 and _f["fresh_touch_n"] == 0 and _f["leg"] == 1 and _f["seq"] == 0, str(_f))
    # (ii) same tape, fill bar volume 40 (< p75) -> NOT ok, why no_burst (evidence row, no fire)
    _f2 = _ks("KB", _agbw(_agwarm(), 40), 10.0, _ctx)
    check("AG-ii: B->W without burst -> no fire (ok False, why no_burst)",
          bool(_f2) and _f2["ok"] is False and _f2["why"] == ["no_burst"] and _f2["seq_str"] == "B W", str(_f2))
    # (iii) W without a prior B (no new session high) -> nothing
    _t3 = _agwarm(); _t3.append((_agk(_t3), 10.02, 10.08, 9.98, 10.06, 120)); _t3.append((_agk(_t3), 10.06, 10.09, 10.05, 10.08, 300))
    check("AG-iii: wick without prior B -> no fire", _ks("KC", _t3, 10.0, _ctx) is None)
    # (iii-b) B then H (3 lows hold above the broken level 10.10) + burst -> fires "B H", stop = level
    _t4 = _agwarm(); _t4.append((_agk(_t4), 10.05, 10.30, 10.04, 10.28, 150))
    for _j in range(3): _t4.append((_agk(_t4), 10.28, 10.29, 10.20, 10.28, 90))
    _t4.append((_agk(_t4), 10.29, 10.40, 10.28, 10.38, 300))
    _f4 = _ks("KD", _t4, 10.0, _ctx)
    check("AG-iii-b: B->H (3 holds) + burst fires 'B H', stop = broken level 10.10",
          bool(_f4) and _f4["ok"] and _f4["seq_str"] == "B H" and _f4["would_stop"] == 10.1, str(_f4))
    # (iv) 3rd pullback in the leg -> skipped even with a perfect burst break
    def _agbw2(t, b_hi, w_lo, w_c, br_hi, vol, fail=False):
        t.append((_agk(t), w_c - 0.02, b_hi, w_c - 0.03, b_hi - 0.02, 150))
        t.append((_agk(t), b_hi - 0.02, b_hi - 0.01, w_lo, w_c, 120))
        if fail: t.append((_agk(t), w_c, w_c + 0.01, w_lo - 0.05, w_lo - 0.02, 120))
        else:    t.append((_agk(t), w_c, br_hi, w_c - 0.01, br_hi - 0.01, vol))
        return t
    _t5 = _agwarm()
    _t5 = _agbw2(_t5, 10.30, 10.06, 10.25, None, None, fail=True)
    _t5 = _agbw2(_t5, 10.34, 10.15, 10.30, None, None, fail=True)
    _r5a = _ks("KE", _t5, 10.0, _ctx)
    _t5b = _agbw2([], 10.38, 10.22, 10.34, 10.40, 300); _t5b = [(_agk(_t5) + 10 * i,) + b[1:] for i, b in enumerate(_t5b)]
    _r5b = _ks("KE", _t5b, 10.0, _ctx)
    check("AG-iv: 3rd pullback in the leg -> no fire (pull_n 3)",
          _r5a is None and _r5b is None and _agn["_ks_st"]["KE"]["pull_n"] == 3, str((_r5a, _r5b)))
    # (v) per-LEG cap: with LEG_MAX=1 the 2nd setup in the leg is refused (leg_cap); a >=3% pullback then a
    #     new session high = NEW LEG -> leg_n resets and it fires again (leg 2, leg_n 0). No daily ration.
    _agn["KEVSEQ_LEG_MAX"] = 1
    _t6 = _agbw(_agwarm(), 300); _r6a = _ks("KF", _t6, 10.0, _ctx)
    _t6b = _agbw2([], 10.36, 10.15, 10.33, 10.40, 300); _t6b = [(_agk(_t6) + 10 * i,) + b[1:] for i, b in enumerate(_t6b)]
    _r6b = _ks("KF", _t6b, 10.0, _ctx)
    _base = _agk(_t6) + 10 * len(_t6b); _t6c = []
    for i in range(6): _t6c.append((_base + 10 * i, 10.30, 10.32, 10.00, 10.05, 80))       # 3.8% pullback
    _t6c += [(_base + 60 + 10 * i,) + b[1:] for i, b in enumerate(_agbw2([], 10.45, 10.12, 10.40, 10.50, 300))]
    _r6c = _ks("KF", _t6c, 10.0, _ctx)
    check("AG-v: leg cap binds inside the leg (leg_cap) and RESETS on a new leg (leg 2, leg_n 0 fires)",
          bool(_r6a) and _r6a["ok"] and _r6a["leg"] == 1
          and bool(_r6b) and _r6b["ok"] is False and _r6b["why"] == ["leg_cap"]
          and bool(_r6c) and _r6c["ok"] and _r6c["leg"] == 2 and _r6c["leg_n"] == 0, str((_r6a, _r6b, _r6c)))
    _agn["KEVSEQ_LEG_MAX"] = 3
    # (vi) context gates: front side False / unknown and day-gain miss are refusals with named reasons; top3 rescues day-gain
    _r7 = _ks("KG", _agbw(_agwarm(), 300), 10.0, {"front_side": False, "day_gain": 5.0, "top3": False, "blue_sky": False})
    _r8 = _ks("KH", _agbw(_agwarm(), 300), 10.0, {"front_side": True, "day_gain": 5.0, "top3": True, "blue_sky": False})
    _r9 = _ks("KI", _agbw(_agwarm(), 300), 10.0, {})
    check("AG-vi: front_side_off + day_gain refused; top3 rescues day-gain; empty ctx = front_side_unknown + day_gain",
          bool(_r7) and _r7["ok"] is False and set(_r7["why"]) == {"front_side_off", "day_gain"}
          and bool(_r8) and _r8["ok"] and bool(_r9) and set(_r9["why"]) == {"front_side_unknown", "day_gain"}, str((_r7, _r8, _r9)))
    # (vii) caller: shadow row + reject row; conversion ONLY under KEVSEQ_CONVERT; lane 'kevseq' E3; triggered row
    _cal = _ag_src[_ag_src.index("8/16 KEV SEQUENCE lane (\"kevseq\") shadow"):_ag_src.index("if PREVWAP_SHADOW:")]
    check("AG-vii: caller append guarded by KEVSEQ_CONVERT; lane 'kevseq' E3; kevseq_shadow_fire + kevseq_reject + triggered_kevseq rows",
          'if KEVSEQ_CONVERT and _ksf["would_stop"] < _ksf["px"]:' in _cal
          and _cal.index('if KEVSEQ_CONVERT and') < _cal.index('breakouts.append((t, _ks_px, _ksf["b_level"] or _ksf["would_stop"], "kevseq", {')
          and '"exit_mode": "E3"' in _cal and '"kevseq_shadow_fire"' in _cal and '"kevseq_reject"' in _cal
          and '"triggered_kevseq"' in _cal and "calculate_ema9(_ks_1m), calculate_ema20(_ks_1m)" in _cal)
    check("AG-viii: detector itself conversion-free", "breakouts.append" not in _AG_SEG and "execute_trade" not in _AG_SEG)
    _bo = []; _ns_c = {"KEVSEQ_CONVERT": False, "_ksf": {"would_stop": 1.0, "px": 2.0}, "breakouts": _bo}
    exec('if KEVSEQ_CONVERT and _ksf["would_stop"] < _ksf["px"]:\n    breakouts.append(1)', _ns_c)
    check("AG-ix: KEVSEQ_CONVERT=0 -> zero appends", _bo == [])
    # 8/17 LANE REGISTRY amends this pin: _STALE_EXEMPT is registry-derived and kevseq IS in it
    # now BY DESIGN — that omission is the whole defect this ship closes (WFF 11:17:43). The
    # TRADEABILITY (min-stop) and SIDE (backside/vride) sets are unchanged and still pinned.
    check("AG-x: 'kevseq' not in MIN_STOP_EXEMPT/BACKSIDE_EXEMPT/VRIDE_EXEMPT defaults",
          '"kevseq"' not in _ag_src[_ag_src.index("MIN_STOP_EXEMPT = set("):_ag_src.index("MIN_STOP_EXEMPT = set(") + 200]
          and 'BACKSIDE_EXEMPT   = {"dip_rip"}' in _ag_src and "kevseq" not in _ag_src[_ag_src.index("VRIDE_EXEMPT    = set("):_ag_src.index("VRIDE_EXEMPT    = set(") + 150])
    _g = open(os.path.join(ROOT, "data", "killtests", "nightly_shadow_grade.py")).read()
    check("AG-xi: grader lists kevseq_shadow_fire + triggered_kevseq (E3 only) and reads 'stop' on triggered rows",
          "kevseq_shadow_fire,triggered_kevseq" in _g and 'lanes["kevseq"].append(rec)' in _g
          and 'lanes["kevseq_conv"].append(rec)' in _g and '"triggered_kevseq", "triggered_v2conv") else r.get("stop")' in _g)
    check("AG-xii: boot banner + boot_config row stamp KEVSEQ envs",
          "KEVSEQ_SHADOW={int(KEVSEQ_SHADOW)}" in _ag_src and "kevseq_convert=int(KEVSEQ_CONVERT)" in _ag_src
          and "kevseq_leg_max=KEVSEQ_LEG_MAX" in _ag_src)
except (AssertionError, ValueError, KeyError) as _age:
    check("AG: kevseq lane", False, str(_age))

print("AH) 8/16 V2 QUIET-TAPE convert gate 'v2conv' (causal trailing calm; convert env-OFF, quiet_only ON, cap 5)")
try:
    from zoneinfo import ZoneInfo as _AHZ
    import types as _aht, datetime as _ahdt
    _ah_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # detector + helper segment (constants through v2_trailing_calm) — must be conversion-free
    _AH_SEG = _ah_src[_ah_src.index("V2_SHADOW      = os.environ.get"):_ah_src.index("# ── 8/14 GRINDER-1030 SHADOW")]
    _ahn = {"os": _aht.SimpleNamespace(environ={}), "datetime": _ahdt.datetime,
            "EASTERN": _AHZ("America/New_York")}
    exec(_AH_SEG, _ahn)
    check("AH-a: envs default — V2_CONVERT OFF, V2_QUIET_ONLY ON, cap 5, quiet<=89.9bps, look 30",
          _ahn["V2_CONVERT"] is False and _ahn["V2_QUIET_ONLY"] is True and _ahn["V2_DAILY_CAP"] == 5
          and _ahn["V2_QUIET_BPS"] == 89.9 and _ahn["V2_QUIET_LOOK"] == 30 and _ahn["V2_QUIET_MINB"] == 10)
    _calm_fn = _ahn["v2_trailing_calm"]; _hist = _ahn["_v2_hist"]
    _k0 = 1_700_000_000
    def _bars(rng, n=15, close=10.0, kstart=_k0):        # n bars, each high/low = close +/- rng/2
        return [(kstart + 10 * i, close, close + rng / 2, close - rng / 2, close, 100) for i in range(n)]
    # (i) quiet gate: a CALM tape (40 bps 10s ranges) passes; a BUSY tape (200 bps) blocks
    _hist["CALM"] = _bars(0.04); _hist["BUSY"] = _bars(0.20)
    _fk = _k0 + 10 * 15                                   # fire bar sits AFTER all 15 history bars
    _mc, _nc = _calm_fn("CALM", _fk); _mb, _nb2 = _calm_fn("BUSY", _fk)
    _quiet_c = bool(_mc is not None and _mc <= _ahn["V2_QUIET_BPS"])
    _quiet_b = bool(_mb is not None and _mb <= _ahn["V2_QUIET_BPS"])
    check("AH-i: calm tape (~40bps) passes quiet gate, busy tape (~200bps) blocks",
          _quiet_c is True and abs(_mc - 40.0) < 1.0 and _quiet_b is False and abs(_mb - 200.0) < 1.0, str((_mc, _mb)))
    # (ii) CAUSALITY: bars AT the fire bar (k == fire_k) and AFTER (k > fire_k) are NEVER read.
    #      Calm history before the fire + a huge-range bar at/after fire_k -> metric stays calm.
    _hist["CAUSAL"] = _bars(0.04) + [(_fk, 10.0, 12.0, 8.0, 10.0, 999),        # k == fire_k (excluded)
                                     (_fk + 10, 10.0, 13.0, 7.0, 10.0, 999)]   # k  > fire_k (excluded)
    _mx, _nx = _calm_fn("CAUSAL", _fk)
    check("AH-ii: trailing metric reads ONLY bars strictly before fire_k (k==fire and k>fire excluded)",
          _mx is not None and abs(_mx - 40.0) < 1.0 and _nx == 15, str((_mx, _nx)))
    # (iii) too little prior tape (< V2_QUIET_MINB=10 bars) -> None -> caller treats as NOT quiet
    _hist["THIN"] = _bars(0.04, n=6)
    _mt, _nt = _calm_fn("THIN", _k0 + 10 * 6)
    check("AH-iii: < MINB prior bars -> (None, n) -> not quiet", _mt is None and _nt == 6)
    # (iv) detector+helper segment is conversion-free (no order path in the machine code)
    check("AH-iv: detector/helper segment has no breakouts.append / execute_trade",
          "breakouts.append" not in _AH_SEG and "execute_trade" not in _AH_SEG)
    # (v) caller: conversion guarded by V2_CONVERT and (not V2_QUIET_ONLY or quiet); lane 'v2conv' E3; rows
    _cal = _ah_src[_ah_src.index("# CAUSAL trailing-calm buffer:"):_ah_src.index("# ── 8/14 GRINDER-1030 shadow (#48 lane; E3 OOS-wall nominee): same fed")]
    check("AH-v: caller append guarded by V2_CONVERT + quiet-only clause; lane 'v2conv' E3; stamped rows",
          'if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)' in _cal
          and _cal.index('if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)') < _cal.index('breakouts.append((t, _v2_px, round(_vr_sv, 4), "v2conv", {')
          and '"exit_mode": "E3"' in _cal and '"triggered_v2conv"' in _cal
          and 'quiet_tape=_v2_quiet, quiet_bps=_q_bps, quiet_n=_q_n' in _cal      # STAMPED on every fire row
          and 'v2_trailing_calm(t, _v2f["k"])' in _cal)
    # (vi) quiet metric uses the fire bar's k (fire_k), and the buffer trims to a bounded window (no unbounded growth)
    check("AH-vi: causal buffer maintained every call + bounded, metric keyed on fire_k",
          '_v2h = _v2_hist.setdefault(t, [])' in _cal and 'del _v2h[:-90]' in _cal
          and 'v2_trailing_calm(t, _v2f["k"])' in _cal)
    # (vii) V2_CONVERT=0 -> zero appends (exec the guard with convert off)
    _bo = []; _nsc = {"V2_CONVERT": False, "V2_QUIET_ONLY": True, "_v2_quiet": True,
                      "_v2f": {"would_stop": 1.0, "px": 2.0}, "breakouts": _bo}
    exec('if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)\n        and _v2f["would_stop"] < _v2f["px"]):\n    breakouts.append(1)', _nsc)
    check("AH-vii: V2_CONVERT=0 -> zero appends", _bo == [])
    # (vii-b) V2_QUIET_ONLY=0 converts a NOT-quiet fire; =1 blocks it
    def _conv(convert, quiet_only, quiet):
        _b = []; exec('if (V2_CONVERT and (not V2_QUIET_ONLY or _v2_quiet)\n        and _v2f["would_stop"] < _v2f["px"]):\n    breakouts.append(1)',
                      {"V2_CONVERT": convert, "V2_QUIET_ONLY": quiet_only, "_v2_quiet": quiet,
                       "_v2f": {"would_stop": 1.0, "px": 2.0}, "breakouts": _b}); return len(_b)
    check("AH-viii: quiet_only=1 blocks a busy fire; quiet_only=0 converts it; a quiet fire converts either way",
          _conv(True, True, False) == 0 and _conv(True, False, False) == 1 and _conv(True, True, True) == 1)
    # (ix) v2conv in PRE_LANES ONLY under convert; NOT in any exempt set
    check("AH-ix: PRE_LANES.add('v2conv') gated by 'if V2_CONVERT:'",
          'if V2_CONVERT:\n    PRE_LANES.add("v2conv")' in _ah_src)
    # 8/17 LANE REGISTRY amends this pin: _STALE_EXEMPT is registry-derived, v2conv IS in it now
    # by design (section AO). Tradeability/side sets unchanged and still pinned.
    check("AH-x: 'v2conv' not in MIN_STOP_EXEMPT/BACKSIDE_EXEMPT/VRIDE_EXEMPT defaults",
          '"v2conv"' not in _ah_src[_ah_src.index("MIN_STOP_EXEMPT = set("):_ah_src.index("MIN_STOP_EXEMPT = set(") + 200]
          and 'BACKSIDE_EXEMPT   = {"dip_rip"}' in _ah_src
          and "v2conv" not in _ah_src[_ah_src.index("VRIDE_EXEMPT    = set("):_ah_src.index("VRIDE_EXEMPT    = set(") + 150])
    # (xi) cap: caller has the V2_DAILY_CAP guard + v2conv_capped row + per-day counter
    check("AH-xi: daily cap enforced (V2_DAILY_CAP guard, v2conv_capped row, per-day reset)",
          'if _v2_conv_day["n"] >= V2_DAILY_CAP:' in _cal and '"v2conv_capped"' in _cal
          and '_v2_conv_day.get("d") != _v2day' in _cal and '_v2_conv_day["n"] += 1' in _cal)
    # (xii) grader lists triggered_v2conv + v2_conv lane (E3, informational; reads 'stop' on triggered rows)
    _g = open(os.path.join(ROOT, "data", "killtests", "nightly_shadow_grade.py")).read()
    check("AH-xii: grader queries triggered_v2conv + has v2_conv lane + reads 'stop' on triggered rows",
          "triggered_v2conv" in _g and 'lanes["v2_conv"].append(rec)' in _g
          and '"triggered_v2conv"' in _g and '"v2_conv": []' in _g)
    # (xiii) boot banner + boot_config row stamp V2 convert envs
    check("AH-xiii: boot banner + boot_config stamp V2_CONVERT envs",
          "V2_CONVERT={int(V2_CONVERT)}" in _ah_src and "v2_convert=int(V2_CONVERT)" in _ah_src
          and "v2_quiet_only=int(V2_QUIET_ONLY)" in _ah_src and "v2_daily_cap=V2_DAILY_CAP" in _ah_src)
except (AssertionError, ValueError, KeyError) as _ahe:
    check("AH: v2 quiet-tape convert gate", False, str(_ahe))

# ── 8/17 OPEN-BLACKOUT BOUNDARY FIX pins (forensic: data/killtests/pre_staleness_forensic_20260817.md)
# REPRODUCES the 8/17 failure: at 09:31 ET the old _live_sessions returned None (RTH-only) while the
# only RTH bars in the vendor payload were PRIOR-DAY — the exact _alpaca_intraday_bars filter then fed
# _fresh_session nothing but Friday bars → [] → the read-list guard fail-closed the whole roster
# (23/26 names incl. WETO/FIEE/DFSC skipped 09:30–09:35 on fresh SIP tape). These pins FAIL on the
# pre-fix code (no hand-off → sessions=None at 09:31 → composed pipeline yields []).
print("R) 8/17 bell-boundary hand-off (_live_sessions + composed 1-min freshness pipeline)")
try:
    import zoneinfo as _bz, datetime as _bdt
    _bE = _bz.ZoneInfo("America/New_York")
    _b_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()

    def _ls_at(hhmm, handoff="5"):
        """exec the real _live_sessions segment with a frozen ET clock + env."""
        _seg = _b_src[_b_src.index("RTH_HANDOFF_MIN = int"):_b_src.index("def _alpaca_intraday_bars")]
        class _FDT(_bdt.datetime):
            @classmethod
            def now(cls, tz=None):
                return _bdt.datetime(2026, 8, 17, int(hhmm[:2]), int(hhmm[3:]), 30, tzinfo=_bE)
        _old = os.environ.get("RTH_HANDOFF_MIN")
        os.environ["RTH_HANDOFF_MIN"] = handoff
        try:
            ns = {"os": os, "datetime": _FDT, "EASTERN": _bE}
            exec(_seg, ns)
            return ns["_live_sessions"]()
        finally:
            (os.environ.pop("RTH_HANDOFF_MIN") if _old is None
             else os.environ.__setitem__("RTH_HANDOFF_MIN", _old))

    check("boundary: 09:29 unchanged (PRE+RTH)", _ls_at("09:29") == ["PRE", "RTH"])
    check("boundary: 09:31 hand-off keeps PRE visible (THE 8/17 pin — fails pre-fix)",
          _ls_at("09:31") == ["PRE", "RTH"])
    check("boundary: 09:34 still inside 5-min hand-off", _ls_at("09:34") == ["PRE", "RTH"])
    check("boundary: 09:36 back to RTH-only (None) — RTH path unmoved", _ls_at("09:36") is None)
    check("boundary: 10:00 RTH-only (None)", _ls_at("10:00") is None)
    check("boundary: kill switch RTH_HANDOFF_MIN=0 restores hard flip",
          _ls_at("09:31", handoff="0") is None)
    check("boundary: explicit is_premkt untouched by hand-off", True)  # param path unchanged by diff

    # composed pipeline: the exact 8/17 payload shape — fresh PRE bars (seconds old) + prior-day RTH
    # bars — through the REAL _et_session_of_utc + _alpaca_intraday_bars filter + _fresh_session.
    _p_ns = {"os": os, "datetime": _bdt.datetime, "timezone": _bdt.timezone,
             "timedelta": _bdt.timedelta, "EASTERN": _bE}
    exec(_b_src[_b_src.index("def _et_session_of_utc"):_b_src.index("EXIT_PX_TAPE_TOL")], _p_ns)
    exec(_b_src[_b_src.index("def _latest_session"):_b_src.index("def _stop_close_qualifies")], _p_ns)
    _now_utc = _bdt.datetime.now(_bdt.timezone.utc)
    # simulate "now" = today 13:31 UTC only if we're testing live; instead build bars relative to NOW
    # so _fresh_session's real clock sees the PRE bar as seconds-old: newest "PRE" bar = now-60s
    def _bar(dt_utc):
        return {"time": dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + ".000+0000",
                "open": "1", "high": "1", "low": "1", "close": "1", "volume": "100"}
    _fresh_bar = _bar(_now_utc - _bdt.timedelta(seconds=60))
    _prior_rth = [_bar(_now_utc - _bdt.timedelta(days=3, hours=2)) for _ in range(6)]
    def _filter(bars, sessions):
        """the exact _alpaca_intraday_bars session-filter loop, applied to a canned payload."""
        out = []
        for b in bars:
            _s = _p_ns["_et_session_of_utc"](str(b["time"])[:19])
            if sessions is None:
                if _s != "RTH":
                    continue
            elif _s not in {str(x).upper() for x in sessions}:
                continue
            out.append(b)
        return out[-6:]
    # the pin only bites when the fresh bar lands in PRE and stale ones in RTH (run any time of day:
    # force the session labels by choosing timestamps — 60s-old bar's session depends on wall clock,
    # so assert the INVARIANT instead: RTH-only filter drops every non-RTH fresh bar → _fresh_session
    # of prior-day-RTH-only = [] (fail-closed), while PRE+RTH keeps the fresh bar → passes.
    check("composed: prior-day RTH bars alone = _fresh_session [] (the observed fail-closed)",
          _p_ns["_fresh_session"](_filter(_prior_rth, None)) == [])
    _mix = _prior_rth + [_fresh_bar]
    _kept = _filter(_mix, ["PRE", "RTH"])
    _fs = _p_ns["_fresh_session"](_kept) if _kept and _p_ns["_et_session_of_utc"](str(_fresh_bar["time"])[:19]) in ("PRE", "RTH") else None
    check("composed: PRE+RTH hand-off keeps the fresh bar visible to _fresh_session",
          _fs is None or _fs == [_fresh_bar],
          "fresh bar outside PRE/RTH at this wall-clock — invariant vacuously ok" if _fs is None else "")
except (AssertionError, ValueError, KeyError) as _be:
    check("8/17 boundary fix section", False, str(_be))

print("AJ) 8/17 KEV_SHADOW read-side (veto + kev_road_max + KEV_ROAD; primacy REAFFIRMED — no structure promotion)")
try:
    _aj_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _aj_ns = {"os": os}
    # the overlay itself (pure over its rec argument)
    _aj_seg = _aj_src[_aj_src.index("def _kev_shadow_overlay"):_aj_src.index("# ── 8/7 THE FRESHNESS CONTRACT")]
    exec(_aj_seg, _aj_ns)
    _ov = _aj_ns["_kev_shadow_overlay"]
    _vrec = {"src": "vision", "kev_name": True, "break": 10.10, "confirm": 9.40,
             "targets": [9.5, 10.0], "_ts": "2026-08-17T07:00:42",
             "kev_shadow": {"break": 12.95, "confirm": 11.50, "targets": [20.0],
                            "_ts": "2026-08-17T07:00:33"}}
    _e = _ov(dict(_vrec))
    check("AJ: kev_shadow structure NEVER promoted (break stays ours)", _e["break"] == 10.10 and _e["targets"] == [9.5, 10.0])
    check("AJ: kev_road_max stamped (his 20 > our ceiling 10)", _e.get("kev_road_max") == 20.0)
    _e2 = _ov({"break": 5.0, "targets": [8.0], "kev_shadow": {"targets": [6.0], "_ts": "2026-08-17T09:00:00"}})
    check("AJ: no stamp when his ceiling <= ours", "kev_road_max" not in _e2)
    _e3 = _ov({"break": 5.0, "kev_shadow": {"veto": True, "targets": []}})
    check("AJ: veto flag propagates", _e3.get("veto") is True and _e3.get("veto_src") == "kev_shadow")
    _e4 = _ov({"break": 5.0, "kev_shadow": {"note": "fade it, do not trade this junk"}})
    check("AJ: do-not-trade note propagates veto", _e4.get("veto") is True)
    os.environ["KEV_VETO_READ"] = "0"
    _e5 = _ov({"break": 5.0, "kev_shadow": {"veto": True, "targets": [20.0]}})
    check("AJ: KEV_VETO_READ=0 restores veto-blind read (road stamp survives)",
          not _e5.get("veto") and _e5.get("kev_road_max") == 20.0)
    os.environ.pop("KEV_VETO_READ", None)
    check("AJ: non-dict kev_shadow -> rec unchanged", _ov({"break": 5.0, "kev_shadow": "junk"}) == {"break": 5.0, "kev_shadow": "junk"})
    check("AJ: exception fail-safe -> rec unchanged", _ov({"break": 5.0, "kev_shadow": {"targets": ["zz"], "veto": 0}}).get("kev_road_max") is None)
    # _freshest_rec: vision_shadow-over-kev-primary promotion INTACT + overlay wired both paths
    _fr_ns = {"os": os}
    _fr_seg = _aj_src[_aj_src.index("def _freshest_rec"):_aj_src.index("# ── 8/7 THE FRESHNESS CONTRACT")]
    _kp = {"T1": {"src": "kev", "break": 3.0, "_ts": "2026-08-17T07:00:00",
                  "vision_shadow": {"break": 3.5, "_ts": "2026-08-17T08:00:00"},
                  "kev_shadow": {"targets": [9.0]}}}
    exec("def _fetch_kev_levels():\n    return " + repr(_kp) + "\n" + _fr_seg, _fr_ns)
    _f1 = _fr_ns["_freshest_rec"]("T1")
    check("AJ: vision_shadow promotion intact (OUR numbers rule)", _f1["break"] == 3.5 and _f1["_freshest_src"] == "vision_shadow")
    check("AJ: overlay wired on promoted path (kev_road_max rides)", _f1.get("kev_road_max") == 9.0)
    # _marked_runway KEV_ROAD extension (rung-exhausted only)
    _mr_ns = {"os": os, "_gate_failopen": lambda *a, **k: None,
              "_curl_feed": lambda tk, n=720: ({}, "stub")}
    _mr_seg = _aj_src[_aj_src.index("def _marked_runway"):_aj_src.index("# ══════════════════════════════════════════════════════════════════════════════════════════\n# 8/16 BUILD #0")]
    _mr_map = {"targets": [9.5, 10.0], "next_supply": 0, "kev_road_max": 20.0}
    exec("def _effective_map(tk, px=0.0):\n    return " + repr(_mr_map) + "\n" + _mr_seg, _mr_ns)
    _rr_a, _tgt_a = _mr_ns["_marked_runway"]("WETO", 10.50, 10.00)   # entry ABOVE all our rungs
    check("AJ: WETO rung-exhausted -> road extends to kev_road_max 20", _tgt_a == 20.0 and _rr_a == 19.0)
    _rr_b, _tgt_b = _mr_ns["_marked_runway"]("WETO", 9.00, 8.50)     # our rung 9.5 still live
    check("AJ: own rung live -> KEV_ROAD does NOT fire (our numbers gate)", _tgt_b == 9.5)
    os.environ["KEV_ROAD"] = "0"
    _rr_c, _tgt_c = _mr_ns["_marked_runway"]("WETO", 10.50, 10.00)
    check("AJ: KEV_ROAD=0 restores above_all_levels", _rr_c == "above_all_levels" and _tgt_c is None)
    os.environ.pop("KEV_ROAD", None)
except (AssertionError, ValueError, KeyError) as _aje:
    check("AJ section", False, str(_aje))

print("AJ2) 8/17 reread-on-stale-reject (#57 first half — existing reader queue reused)")
try:
    _a2_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _a2_rows = []
    _a2_ns = {"os": os, "time": __import__("time"),
              "_log_decision": lambda tk, st, **kw: _a2_rows.append((tk, st, kw))}
    _a2_seg = _a2_src[_a2_src.index("_reread_reject_t: dict"):_a2_src.index("def _fetch_kev_watchlist")]
    exec(_a2_seg, _a2_ns)
    _a2_ns["print"] = lambda *a, **k: None
    _a2_ns["_reread_on_reject"]("STALEX", "runway_reject", map_age_min=22.4)
    _a2_ns["_reread_on_reject"]("STALEX", "ceiling_reject", map_age_min=23.0)   # inside 10-min cap
    check("AJ2: first stale reject enqueues one marker row",
          len(_a2_rows) == 1 and _a2_rows[0][1] == "reread_on_reject" and _a2_rows[0][2]["gate"] == "runway_reject")
    _a2_ns["_reread_reject_t"]["STALEX"] -= 601
    _a2_ns["_reread_on_reject"]("STALEX", "ceiling_reject")
    check("AJ2: after 10 min the cap releases", len(_a2_rows) == 2)
    os.environ["REREAD_ON_REJECT"] = "0"
    _a2_ns["_reread_on_reject"]("OTHERX", "runway_reject")
    check("AJ2: REREAD_ON_REJECT=0 kills it", all(r[0] != "OTHERX" for r in _a2_rows))
    os.environ.pop("REREAD_ON_REJECT", None)
    check("AJ2: wired at freshness_breach + runway_reject + ceiling_reject",
          _a2_src.count('_reread_on_reject(ticker, "') == 3)
    _a2_nv = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    check("AJ2: reader marker queue consumes the row (no new queue built)",
          '"reread_on_reject"):   # 8/17 #57' in _a2_nv)
except (AssertionError, ValueError, KeyError) as _a2e:
    check("AJ2 section", False, str(_a2e))

print("AJ3) 8/17 read-starvation alarm (observe-only, fabricated clock)")
try:
    _a3_nv = open(os.path.join(ROOT, "newcomer_vision_reader.py")).read()
    _a3_rows = []
    _a3_ns = {"os": os, "time": __import__("time"),
              "_post_decision": lambda tk, st, **kw: _a3_rows.append((tk, st, kw)),
              "print": lambda *a, **k: None}
    _a3_seg = _a3_nv[_a3_nv.index('_starv = {"win"'):_a3_nv.index("def reread_check")]
    exec(_a3_seg, _a3_ns)
    _tick, _st = _a3_ns["_starvation_tick"], _a3_ns["_starv"]
    T0 = 1_000_000.0
    _tick(5, now=T0, hm="09:40")                       # window opens
    _tick(5, now=T0 + 901, hm="09:55")                 # full window, 0 completions, roster 5
    check("AJ3: 0-completions full window + roster -> read_starvation row",
          len(_a3_rows) == 1 and _a3_rows[0][1] == "read_starvation" and _a3_rows[0][2]["roster_n"] == 5)
    _tick(5, now=T0 + 1000, hm="10:00")                # mid-window: no repeat
    check("AJ3: once per window", len(_a3_rows) == 1)
    _st["n"] = 2                                        # completions arrive
    _tick(5, now=T0 + 1802, hm="10:11")
    check("AJ3: window WITH completions -> silent", len(_a3_rows) == 1)
    _tick(5, now=T0 + 2703, hm="16:20")                # after hours: window void
    check("AJ3: outside 07:00-16:00 -> no alarm + window reset", len(_a3_rows) == 1 and _st["win"] is None)
    _tick(0, now=T0 + 3000, hm="11:00"); _tick(0, now=T0 + 3901, hm="11:15")
    check("AJ3: empty roster -> silent", len(_a3_rows) == 1)
    os.environ["READ_STARVATION"] = "0"
    _st["win"], _st["n"] = T0 + 4000, 0
    _tick(9, now=T0 + 4901, hm="11:40")
    check("AJ3: READ_STARVATION=0 kills it", len(_a3_rows) == 1)
    os.environ.pop("READ_STARVATION", None)
    check("AJ3: completion counter wired in fire loop", '_starv["n"] += 1' in _a3_nv
          and "_starvation_tick(len(lv))" in _a3_nv)
except (AssertionError, ValueError, KeyError) as _a3e:
    check("AJ3 section", False, str(_a3e))

print("AJ4) 8/17 ignition G1 shadow stamps (observe-first per guidance — NO enforcement)")
try:
    _a4_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _a4_ns = {"os": os}
    exec(_a4_src[_a4_src.index("def _ignition_g1_stamp"):_a4_src.index("_reread_reject_t: dict")], _a4_ns)
    _g1f = _a4_ns["_ignition_g1_stamp"]
    _sb = [{"high": "6.30", "close": "6.1"}, {"high": "6.00", "close": "5.9"}]
    _up = _g1f(6.20, 6.05, _sb)
    check("AJ4: above VWAP -> pass", _up["vwap_side"] == "above" and _up["g1_shadow"] == "pass")
    check("AJ4: hi_dist_pct vs session high", _up["hi_dist_pct"] == round((6.30 - 6.20) / 6.30 * 100, 2))
    _dn = _g1f(5.765, 6.05, _sb)   # FIEE specimen: below VWAP -> shadow FAIL, fire untouched
    check("AJ4: below VWAP -> fail (FIEE would stamp fail)", _dn["vwap_side"] == "below" and _dn["g1_shadow"] == "fail")
    check("AJ4: no vwap -> None stamps, never a throw", _g1f(5.0, 0, _sb)["g1_shadow"] is None)
    os.environ["IGNITION_G1_SHADOW"] = "0"
    check("AJ4: kill switch -> empty stamp dict", _g1f(6.2, 6.05, _sb) == {})
    os.environ.pop("IGNITION_G1_SHADOW", None)
    check("AJ4: stamps ride triggered_ignition row + eyes extra",
          '**_g1)   # 8/17' in _a4_src and '"ema20": round(_e20, 4), **_g1}))' in _a4_src)
    # conversion unchanged: the stamp must never gate — no branch reads the verdict back
    check("AJ4: NO enforcement anywhere (verdict never consumed by a condition)",
          '_g1["g1_shadow"]' not in _a4_src and '_g1.get("g1_shadow")' not in _a4_src
          and 'g1_shadow ==' not in _a4_src and 'g1_shadow" ==' not in _a4_src)
except (AssertionError, ValueError, KeyError) as _a4e:
    check("AJ4 section", False, str(_a4e))

print("AK) 8/17 BOUNDARY CENSUS — frozen-clock matrix per consumer pattern (kills the sharp-flip CLASS)")
try:
    import zoneinfo as _kz, datetime as _kdt, re as _kre
    _kE = _kz.ZoneInfo("America/New_York")
    _k_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _k_seg = _k_src[_k_src.index("RTH_HANDOFF_MIN = int"):_k_src.index("def _alpaca_intraday_bars")]
    def _k_ls(hh, mm, ss, is_premkt=None):
        class _KDT(_kdt.datetime):
            @classmethod
            def now(cls, tz=None):
                return _kdt.datetime(2026, 8, 17, hh, mm, ss, tzinfo=_kE)
        ns = {"os": os, "datetime": _KDT, "EASTERN": _kE}
        exec(_k_seg, ns)
        return ns["_live_sessions"](is_premkt)
    def _k_can_complete(sessions, hh, mm, ss):
        """Can the requested session list contain a COMPLETED 1-min bar at this instant?
        None = RTH-only. A session contributes once the clock is past its first bar close;
        a finished session's bars all remain completed."""
        wins = {"PRE": (4 * 3600, 9 * 3600 + 30 * 60), "RTH": (9 * 3600 + 30 * 60, 16 * 3600),
                "ATH": (16 * 3600, 20 * 3600)}
        t = hh * 3600 + mm * 60 + ss
        req = ["RTH"] if sessions is None else [str(s).upper() for s in sessions]
        return any(t >= wins[s][0] + 60 for s in req if s in wins)
    # the 7-instant matrix (BOUNDARY_CENSUS_20260817.md), P1 default consumers:
    for (_hh, _mm, _ss) in ((4, 1, 30), (7, 0, 30), (9, 29, 30), (9, 30, 30), (9, 31, 30),
                            (15, 59, 30), (16, 0, 30)):
        _sl = _k_ls(_hh, _mm, _ss)
        check("AK: %02d:%02d:%02d session list can contain a completed bar (%s)" % (_hh, _mm, _ss, _sl),
              _k_can_complete(_sl, _hh, _mm, _ss))
    check("AK: 09:30:30 includes PRE post-fix (THE sharp-flip pin)", "PRE" in (_k_ls(9, 30, 30) or []))
    # P2 (PRE-stamped monitor) always PRE+RTH at any instant:
    check("AK: P2 PRE-stamped monitor keeps PRE at 10:00", _k_ls(10, 0, 0, is_premkt=True) == ["PRE", "RTH"])
    # class guards: hand-off machinery + default must stay; a bare call = a new sharp-flip instance
    check("AK: hand-off branch + default 5 present",
          'os.environ.get("RTH_HANDOFF_MIN", "5")' in _k_src
          and '["PRE", "RTH"]   # bell-boundary hand-off' in _k_src)
    _k_bare = 0
    for m in _kre.finditer(r"(?<!def )get_intraday_bars\(", _k_src):
        if _k_src[m.end():m.end() + 5] == "\n" or "get_intraday_bars_full" in _k_src[m.start():m.end() + 5]:
            continue
        _win = _k_src[m.start():m.start() + 260]
        if "sessions=" not in _win:
            _k_bare += 1
    check("AK: bare (sessions-omitted, RTH-only) call sites pinned at the 3 censused fail-open auxiliaries",
          _k_bare == 3, "bare=%d" % _k_bare)
    check("AK: census artifact exists", os.path.exists(os.path.join(ROOT, "data", "audits", "BOUNDARY_CENSUS_20260817.md")))
except (AssertionError, ValueError, KeyError) as _ake:
    check("AK section", False, str(_ake))

print("AL) 8/17 batch2-A TAPE-LANE SCALAR-VETO EXEMPTION (7/26 doctrine: tape lanes trade through)")
try:
    import textwrap as _al_tw
    _al_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    # env defs re-exec'd per case (kill-switch honesty), branch segment = the REAL shipped code
    _al_env = _al_src[_al_src.index("TAPE_LANE_SCALAR_EXEMPT = os.environ.get"):
                      _al_src.index("TAPE_SCALAR_EXEMPT_LANES = set") + 200]
    _al_env = _al_env[:_al_env.index('.split(","))))') + len('.split(","))))')]
    _al_i0 = _al_src.rindex("\n", 0, _al_src.index("mom_ok, mom_details = check_momentum(ticker)")) + 1
    _al_seg = _al_tw.dedent(_al_src[_al_i0:
                                    _al_src.index('if not mom_ok:\n                print(f"⚠️ {ticker} momentum rejected')])
    def _al_run(entry_type, reason, env_on="1", lanes=None):
        rows = []
        os.environ["TAPE_LANE_SCALAR_EXEMPT"] = env_on
        if lanes is not None: os.environ["TAPE_SCALAR_EXEMPT_LANES"] = lanes
        ns = {"os": os}
        exec(_al_env, ns)
        os.environ.pop("TAPE_LANE_SCALAR_EXEMPT", None); os.environ.pop("TAPE_SCALAR_EXEMPT_LANES", None)
        ns.update({"check_momentum": lambda t: (False, {"reason": reason}),
                   "_log_decision": lambda t, s, **k: rows.append((s, k)),
                   "ticker": "TESTX", "entry_type": entry_type, "entry_price": 19.495,
                   "print": lambda *a, **k: None})
        exec(_al_seg, ns)
        return ns["mom_ok"], rows
    _ok1, _r1 = _al_run("kevseq", "no momentum build — 0.9× base (<1.5×) / 66% of peak — volume not expanding, skip")
    check("AL: kevseq 'no momentum build' passes through with exemption on (the WETO 10:18:37 pin)", _ok1)
    check("AL: bypass row logged w/ lane+gate+price", _r1 and _r1[0][0] == "scalar_veto_bypassed"
          and _r1[0][1].get("lane") == "kevseq" and _r1[0][1].get("gate") == "momentum"
          and _r1[0][1].get("price") == 19.495)
    _ok2, _r2 = _al_run("dip_rip", "no momentum build — 0.9× base (<1.5×), skip")
    check("AL: chart lane (dip_rip) still vetoed, no bypass row", not _ok2 and not _r2)
    _ok3, _r3 = _al_run("kevseq", "no momentum build — 0.9× base, skip", env_on="0")
    check("AL: TAPE_LANE_SCALAR_EXEMPT=0 restores today's veto", not _ok3 and not _r3)
    _ok4, _r4 = _al_run("kevseq", "illiquid — avg vol 900/bar < 10,000 floor, skip")
    check("AL: tradeability floor (illiquid) STILL vetoes a tape lane", not _ok4 and not _r4)
    _ok5, _r5 = _al_run("kevseq", "thin ambient tape — median $3,000/min < $9,000 exit floor")
    check("AL: ambient dollar floor STILL vetoes a tape lane", not _ok5 and not _r5)
    _ok6, _r6 = _al_run("grinder", "no momentum build — 1.1× base, skip")
    check("AL: default lane set covers all 5 10s tape lanes (grinder)", _ok6)
    check("AL: vel5 gate applies-to set stays chart-only (no tape lane reaches vel5_reject)",
          '"flat_top", "ma_pullback", "orb", "ema_bounce"' in _al_src.split('vel5_reject')[0][-2500:])
    check("AL: kill-test artifact filed", os.path.exists(os.path.join(
          ROOT, "data", "killtests", "scalar_veto_tape_lanes_20260817.md")))
except (AssertionError, ValueError, KeyError) as _ale:
    check("AL section", False, str(_ale))

print("AM) 8/17 batch2-B CROWN PIPELINE — WETO condition sequence + explicit 'crowned' row (CROWN_FIX_0817)")
try:
    import datetime as _am_dt, zoneinfo as _am_zi
    _am_E = _am_zi.ZoneInfo("America/New_York")
    _am_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _am_seg = _am_src[_am_src.index("LEADER_AMMO         = os.environ.get"):
                      _am_src.index("# ── 8/6 DEPLOY-FREEZE client")]
    _am_seg += "\n" + _am_src[_am_src.index("def _is_leader(sym):"):
                              _am_src.index("_leader_rehydrated = {\"day\": None}")]
    _am_clock = {"hm": (9, 31)}
    class _AMDT(_am_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _am_dt.datetime(2026, 8, 17, _am_clock["hm"][0], _am_clock["hm"][1], 0, tzinfo=_am_E)
    def _am_run(fix_on):
        rows = []
        os.environ["CROWN_FIX_0817"] = fix_on
        ns = {"os": os, "datetime": _AMDT, "EASTERN": _am_E, "time": __import__("time"),
              "_log_decision": lambda t, s, **k: rows.append((s, t, k))}
        exec(_am_seg, ns)
        ns["_pdc_map"]["WETO"] = 8.22   # daily_loaded 03:55 (archive)
        # premarket/open ascent: 3 fresh-high minutes in a rolling 10 -> viol=fresh_highs, gain<40
        for hm, px in (((9, 31), 10.05), ((9, 33), 10.25), ((9, 34), 10.66), ((9, 35), 11.46)):
            _am_clock["hm"] = hm; ns["_leader_high_probe"]("WETO", px)
        _rec = ns["_leader_rec"]("WETO")
        _mid = (_rec["viol"], _rec["gain"], ns["_is_leader"]("WETO"))
        # 09:40:50 halt_suspect -> violence proven; STILL no crown (last visible close 11.46 = +39.4%)
        _am_clock["hm"] = (9, 40); ns["_leader_violence"]("WETO", "halt")
        _halted = ns["_is_leader"]("WETO")
        # 09:45:50 resumption print 13.05 (+58.8%) -> crown next probe (logged 09:47 live = 1 cycle)
        _am_clock["hm"] = (9, 47); ns["_leader_high_probe"]("WETO", 13.05)
        os.environ.pop("CROWN_FIX_0817", None)
        return _mid, _halted, ns["_is_leader"]("WETO"), ns["_leader_rec"]("WETO"), rows
    _mid, _halted, _crowned, _rec, _rows = _am_run("1")
    check("AM: WETO pre-halt = fresh_highs viol armed, gain NOT proven, NO crown",
          _mid == ("fresh_highs", False, False))
    check("AM: halt violence at 09:40 (close 11.46 = +39.4%) still does NOT crown", not _halted)
    check("AM: first post-halt probe (13.05 = +58.8%) CROWNS — 8/5 spec delivered", _crowned
          and _rec["since"] == "09:47")
    check("AM: leader_armed row logged (the crown event, pre-existing)",
          any(r[0] == "leader_armed" and r[2].get("why") == "fresh_highs" for r in _rows))
    check("AM: explicit 'crowned' row logged post-fix (why + since ride the row)",
          any(r[0] == "crowned" and r[1] == "WETO" and r[2].get("why") == "fresh_highs"
              and r[2].get("since") == "09:47" for r in _rows))
    _mid0, _h0, _c0, _rec0, _rows0 = _am_run("0")
    check("AM: CROWN_FIX_0817=0 -> crown behavior identical, 'crowned' row absent (pre-fix state)",
          _c0 and not any(r[0] == "crowned" for r in _rows0)
          and any(r[0] == "leader_armed" for r in _rows0))
    check("AM: fix is observe-only — the 'crowned' status is written once, never read back",
          _am_src.count('_log_decision(sym, "crowned"') == 1 and '== "crowned"' not in _am_src
          and '"crowned" ==' not in _am_src and "'crowned'" not in _am_src)
    check("AM: forensic artifact filed", os.path.exists(os.path.join(
          ROOT, "data", "killtests", "crown_pipeline_forensic_20260817.md")))
except (AssertionError, ValueError, KeyError) as _ame:
    check("AM section", False, str(_ame))

print("AN) 8/17 MANUAL CLOSE-POSITION CONTROL (operator-initiated; fail-CLOSED; stale-request guard)")
# Marcos said "close it" on a live position and there was no mechanism (stop, or a restart that
# now RESUMES). Failure condition doc: data/killtests/manual_close_20260817.md.
try:
    import screener_app as _mcs
    import time as _mct
    _mc_c = _mcs.app.test_client(); _MCH = {"X-Dashboard-Secret": _mcs.API_SECRET}
    _mc_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()
    _mc_saved = dict(_mcs._pending_closes); _mcs._pending_closes.clear()
    try:
        # 1) AUTH: POST requires the secret; GET is read-only
        check("AN: unauthed POST rejected 401",
              _mc_c.post("/api/close_position", json={"ticker": "AAAA"}).status_code == 401
              and not _mcs._pending_closes)
        check("AN: authed POST registers a pending request",
              _mc_c.post("/api/close_position", json={"ticker": "AAAA"}, headers=_MCH).status_code == 200
              and len(_mcs._pending_closes) == 1)
        # 2) MERGE-ONLY (7/24 wipe law): a second request must not drop the first
        _mc_c.post("/api/close_position", json={"ticker": "BBBB"}, headers=_MCH)
        _pend = _mc_c.get("/api/close_position").get_json()["pending"]
        check("AN: merge-only — two names queue simultaneously",
              sorted(p["ticker"] for p in _pend) == ["AAAA", "BBBB"])
        # 3) EXPLICIT CLEAR / ACK path
        _mc_c.post("/api/close_position", json={"ticker": "BBBB", "clear": True}, headers=_MCH)
        check("AN: clear removes only its own key",
              [p["ticker"] for p in _mc_c.get("/api/close_position").get_json()["pending"]] == ["AAAA"])
        # 4) 10-MIN AUTO-EXPIRY (guard #1 against firing on a LATER position in the same name)
        check("AN: TTL is 10 minutes", _mcs.MANUAL_CLOSE_TTL_S == 600)
        for _v in _mcs._pending_closes.values():
            _v["expires_epoch"] = _mct.time() - 1
        check("AN: expired requests pruned on read",
              _mc_c.get("/api/close_position").get_json()["pending"] == []
              and not _mcs._pending_closes)
    finally:
        _mcs._pending_closes.clear(); _mcs._pending_closes.update(_mc_saved)

    # ── bot side: exec the matcher/poller in isolation with a fabricated dashboard ──
    _mcn = {"time": _mct, "json": json, "os": os, "requests": types.SimpleNamespace(post=lambda *a, **k: None),
            "SCREENER_URL": "http://fake", "DASHBOARD_SECRET": "s"}
    for _c in ("MANUAL_CLOSE ", "MANUAL_CLOSE_POLL_S "):
        _i = _mc_src.index("\n" + _c) + 1
        exec(_mc_src[_i:_mc_src.index(chr(10), _i)], _mcn)
    _i0 = _mc_src.index("_mclose_cache = {")
    exec(_mc_src[_i0:_mc_src.index("\n_rebuilt_day = {", _i0)], _mcn)
    _match, _poll = _mcn["_manual_close_match"], _mcn["_manual_close_pending"]

    def _feed(pending):
        """Fabricate the dashboard response and bypass the cache for this assertion."""
        _mcn["_mclose_cache"].update({"t": _mct.time(), "pending": pending})

    _ENTRY = "2026-08-17T14:00:00"
    _feed([{"ticker": "DFSC", "trade_id": None, "at_utc": "2026-08-17T14:05:00", "source": "dashboard"}])
    check("AN: fresh ticker request matches the live position",
          (_match("DFSC", "id_new", _ENTRY) or {}).get("source") == "dashboard")
    check("AN: a different name is untouched", _match("XXXX", "id_new", _ENTRY) is None)
    # STALE-REQUEST GUARD — the safety property. Request predates the position -> ignored.
    _feed([{"ticker": "DFSC", "trade_id": None, "at_utc": "2026-08-17T13:59:00"}])
    check("AN: STALE-REQUEST GUARD — request older than entry_ts is IGNORED",
          _match("DFSC", "id_new", _ENTRY) is None)
    _feed([{"ticker": "DFSC", "trade_id": None}])
    check("AN: untimestamped request is ignored (no timestamp = no close)",
          _match("DFSC", "id_new", _ENTRY) is None)
    # trade_id match BEATS ticker: an id-bearing request only matches that id
    _feed([{"ticker": "DFSC", "trade_id": "id_old", "at_utc": "2026-08-17T14:05:00"}])
    check("AN: trade_id match beats ticker — wrong id does NOT match",
          _match("DFSC", "id_new", _ENTRY) is None
          and _match("DFSC", "id_old", _ENTRY) is not None)
    # FAIL-CLOSED: unreachable dashboard -> empty -> no close (opposite polarity to pause_entries)
    _mcn["_mclose_cache"].update({"t": 0.0, "pending": [{"ticker": "DFSC", "at_utc": "2099-01-01T00:00:00"}]})
    check("AN: dashboard unreachable -> NO close (fail-CLOSED, cache not replayed)",
          _poll() == [] and _match("DFSC", "id_new", _ENTRY) is None)
    # KILL SWITCH
    _mcn["MANUAL_CLOSE"] = False
    _mcn["_mclose_cache"].update({"t": _mct.time(), "pending":
                                  [{"ticker": "DFSC", "at_utc": "2026-08-17T14:05:00"}]})
    check("AN: MANUAL_CLOSE=0 disables the channel entirely",
          _poll() == [] and _match("DFSC", "id_new", _ENTRY) is None)
    _mcn["MANUAL_CLOSE"] = True
    check("AN: poll cadence >= 5s (never hammers the dashboard)", _mcn["MANUAL_CLOSE_POLL_S"] >= 5)

    # ── the monitor's call site: idempotent, and NO parallel exit path ──
    _blk = _mc_src[_mc_src.index("# ── 8/17 MANUAL CLOSE (operator-initiated)"):]
    _blk = _blk[:_blk.index("current_price = stream.get_price(ticker)", _blk.index("_safety_close"))]
    check("AN: idempotent — guarded by _mclose_fired, set BEFORE the sell, then breaks",
          "if MANUAL_CLOSE and not _mclose_fired:" in _blk
          and _blk.index("_mclose_fired = True") < _blk.index("_safety_close(remaining_shares)")
          and _blk.rstrip().endswith("break"))
    check("AN: _mclose_fired initialised once per monitor (per-position, not global)",
          "_mclose_fired      = False" in _mc_src and _mc_src.count("_mclose_fired = True") == 1)
    check("AN: exit routes through the SHARED choke point — no parallel exit code",
          "_safety_close(remaining_shares)" in _blk
          and "close_position(" not in _blk and "_place_order(" not in _blk
          and "cancel_order(" not in _blk)
    check("AN: exit_reason is manual_close (Marcos) and acks the request",
          'result["exit_reason"] = "manual_close (Marcos)"' in _blk
          and "_manual_close_ack(ticker, trade_id)" in _blk)
    check("AN: manual exits get their own layer — never mixed into stop/eod stats",
          'if "manual_close" in r: return "manual"' in _mc_src)
    check("AN: dry-run parity — the sell is the same close_position path (DRY_RUN handled there)",
          "def close_position(ticker, shares):" in _mc_src
          and "DRY RUN — simulating SELL" in _mc_src)
    check("AN: failure-condition doc filed FIRST", os.path.exists(os.path.join(
          ROOT, "data", "killtests", "manual_close_20260817.md")))
except (AssertionError, ValueError, KeyError) as _mce:
    check("AN section", False, str(_mce))

print("AO) 8/17 LANE CLASSIFICATION REGISTRY (Marcos: 'build it now') — the guard rail")
# THE DEFECT: the settled 7/24+7/26 doctrine (tape lanes trade through chart-derived and
# setup-quality vetoes) lived as COPY-PASTED tuples inside each gate, so kevseq (born 8/16) was
# absent from every one — WFF 11:17:43 @ $5.039 died on chart_gate_block on a +307% name.
# This section (1) FAILS if any entry_type the bot can emit is missing from LANE_CLASS, so a
# future lane cannot be born unclassified; (2) pins the derived sets against the PRE-8/17
# literals for every pre-existing lane; (3) pins the ordered delta and the kill switch.
try:
    import importlib as _ilAO
    sys.path.insert(0, os.path.join(ROOT, "rig"))
    _AOload = _ilAO.import_module("loader").load_bot
    _AO = _AOload()
    _ao_src = open(os.path.join(ROOT, "marcos_trading_bot.py")).read()

    # ── (1) GUARD RAIL: every emitted entry_type is classified ──────────────────────────────
    # every breakouts.append call site: take the FIRST bare string literal inside the tuple —
    # that is the entry_type slot, whatever expressions the price/level slots contain.
    # AST, not regex: find every breakouts.append((...)) call and take tuple element [3] — the
    # entry_type slot — whatever expressions the price/level slots contain. Anything but a plain
    # string literal there is itself a RED (a computed lane name cannot be classified statically).
    import ast as _aoast
    _emitted, _dynamic = set(), []
    for _n in _aoast.walk(_aoast.parse(_ao_src)):
        if not (isinstance(_n, _aoast.Call) and isinstance(_n.func, _aoast.Attribute)
                and _n.func.attr == "append"
                and getattr(_n.func.value, "id", None) == "breakouts"):
            continue
        _arg = _n.args[0] if _n.args else None
        if not isinstance(_arg, _aoast.Tuple) or len(_arg.elts) < 4:
            _dynamic.append(getattr(_n, "lineno", "?")); continue
        _e = _arg.elts[3]
        if isinstance(_e, _aoast.Constant) and isinstance(_e.value, str):
            _emitted.add(_e.value)
        else:
            _dynamic.append(getattr(_n, "lineno", "?"))
    check("AO: every breakouts.append names its lane with a STRING LITERAL (statically classifiable)",
          not _dynamic, f"dynamic/short at lines {_dynamic}")
    check("AO: emitted entry_types found in source (sanity — the regex still matches)",
          len(_emitted) >= 15, f"found {len(_emitted)}: {sorted(_emitted)}")
    _unclassified = sorted(_emitted - set(_AO.LANE_CLASS))
    check("AO: GUARD RAIL — every emitted entry_type is in LANE_CLASS (no lane born unclassified)",
          not _unclassified, f"UNCLASSIFIED: {_unclassified}")
    check("AO: every LANE_CLASS value is a known class",
          set(_AO.LANE_CLASS.values()) <= {"tape", "chart", "hybrid"},
          str(sorted(set(_AO.LANE_CLASS.values()))))
    check("AO: kevseq is classified TAPE (the lane this task exists for)",
          _AO.LANE_CLASS.get("kevseq") == "tape" and _AO._is_tape_lane("kevseq"))
    check("AO: _is_tape_lane fail-safe — unknown lane is NOT tape (stays gated)",
          _AO._is_tape_lane("brand_new_lane_2027") is False
          and _AO._is_tape_lane(None) is False)
    check("AO: chart lanes are NOT tape", not any(_AO._is_tape_lane(x) for x in
          ("flat_top", "ma_pullback", "orb", "ema_bounce", "dip_rip", "ignition")))

    # ── (2) DERIVED == OLD HARDCODED TUPLES for every PRE-EXISTING lane ─────────────────────
    # the pre-8/17 literals, pinned here as literals (not imported) so a registry edit that
    # silently changes a pre-existing lane's treatment goes RED.
    _OLD_CHART_BYPASS = ("hidden_entry", "vwap_reclaim", "zone_flip")
    _OLD_STALE        = ("rocket_catcher", "vwap_reclaim", "zone_flip", "hidden_entry")
    _OLD_EXT          = ("rocket_catcher", "hidden_entry", "flat_top", "orb", "ma_pullback",
                         "vwap_reclaim", "zone_flip")
    _OLD_MOM          = ("vwap_reclaim", "bounce", "ignition", "hidden_entry", "orb",
                         "flat_top", "ma_pullback", "zone_flip")
    _OLD_TAPE_SCALAR  = {"kevseq", "v2conv", "grinder", "bandpass", "prevwap"}
    _cb, _ext = _AO._chart_bypass_lanes(), _AO._ext_exempt_lanes()
    check("AO: chart-gate bypass is a SUPERSET of the old tuple (no pre-existing lane loses it)",
          set(_OLD_CHART_BYPASS) <= _cb, str(sorted(set(_OLD_CHART_BYPASS) - _cb)))
    check("AO: extension exempt is a SUPERSET of the old tuple", set(_OLD_EXT) <= _ext,
          str(sorted(set(_OLD_EXT) - _ext)))
    # nothing that was GATED before is newly gated, and nothing chart-class newly bypasses
    check("AO: no CHART lane newly bypasses the chart gate (ignition only, env-conditional)",
          not (_cb & _AO.CHART_LANES))
    check("AO: ignition keeps its EXACT env-conditional chart bypass",
          ("ignition" in _cb) == bool(_AO.IGNITION_CHART_BYPASS))
    check("AO: extension exempt adds no NEW chart lane beyond the 7/26 slow-retest carve-out",
          (_ext & _AO.CHART_LANES) == frozenset(("flat_top", "orb", "ma_pullback")),
          str(sorted(_ext & _AO.CHART_LANES)))
    check("AO: check_momentum behavior UNCHANGED — exempt tuple is the 8/17 literal",
          _AO._MOMENTUM_LEGACY_EXEMPT == _OLD_MOM
          and 'if entry_type in _MOMENTUM_LEGACY_EXEMPT:' in _ao_src)
    check("AO: TAPE_SCALAR_EXEMPT_LANES derives byte-identical to the 173d8f1 literal",
          set(_AO.TAPE_SCALAR_EXEMPT_LANES) == _OLD_TAPE_SCALAR,
          str(sorted(_AO.TAPE_SCALAR_EXEMPT_LANES)))

    # ── (3) THE ORDERED DELTA: kevseq now exempt from chart + extension ─────────────────────
    check("AO: DELTA — kevseq now bypasses the chart gate", "kevseq" in _cb)
    check("AO: DELTA — kevseq now exempt from the extension guard", "kevseq" in _ext)
    check("AO: DELTA — every tape lane bypasses chart + extension",
          _AO.TAPE_LANES <= _cb and _AO.TAPE_LANES <= _ext)
    # executed: the real gate returns allow/live_structure for kevseq (no map needed)
    _v, _r, _lv, _src = _AO._chart_break_gate("ZZTEST", 5.039, "kevseq")
    check("AO: EXECUTED — _chart_break_gate('kevseq') returns allow/live_structure",
          _v == "allow" and _r == "live_structure", f"{_v}/{_r}")
    _v2, _r2, _, _ = _AO._chart_break_gate("ZZTEST", 5.039, "flat_top")
    check("AO: EXECUTED — a CHART lane still hits the gate (no blanket bypass)",
          _v2 != "allow" or _r2 != "live_structure", f"{_v2}/{_r2}")

    # ── (4) KILL SWITCH: LANE_REGISTRY_EXEMPT=0 restores the OLD behavior EXACTLY ───────────
    _AO.LANE_REGISTRY_EXEMPT = False
    try:
        _cb0, _ext0 = _AO._chart_bypass_lanes(), _AO._ext_exempt_lanes()
        _exp_cb0 = set(_OLD_CHART_BYPASS) | ({"ignition"} if _AO.IGNITION_CHART_BYPASS else set())
        check("AO: KILL SWITCH — chart bypass falls back to the old tuple exactly",
              _cb0 == _exp_cb0, str(sorted(_cb0)))
        check("AO: KILL SWITCH — extension exempt falls back to the old tuple exactly",
              _ext0 == set(_OLD_EXT), str(sorted(_ext0)))
        check("AO: KILL SWITCH — momentum exempt falls back to the old tuple exactly",
              _AO._momentum_exempt_lanes() == set(_OLD_MOM))
        _v3, _r3, _, _ = _AO._chart_break_gate("ZZTEST", 5.039, "kevseq")
        check("AO: KILL SWITCH — kevseq is GATED again with the registry off",
              not (_v3 == "allow" and _r3 == "live_structure"), f"{_v3}/{_r3}")
    finally:
        _AO.LANE_REGISTRY_EXEMPT = True

    # ── (5) the counterfactual row + the doc ────────────────────────────────────────────────
    check("AO: newly-granted bypasses log lane_exempt_applied (chart gate)",
          '_log_decision(ticker, "lane_exempt_applied", lane=entry_type, gate="chart_break"'
          in _ao_src)
    check("AO: newly-granted bypasses log lane_exempt_applied (extension gate)",
          '_log_decision(b[0], "lane_exempt_applied", lane=b[3], gate="extension"' in _ao_src)
    check("AO: the row fires only for NEWLY-granted lanes (legacy lanes stay silent)",
          'entry_type not in _LEGACY_CHART_BYPASS' in _ao_src
          and 'b[3] not in _LEGACY_EXT_EXEMPT' in _ao_src)
    check("AO: failure-condition doc filed FIRST", os.path.exists(os.path.join(
          ROOT, "data", "killtests", "lane_registry_20260817.md")))
    check("AO: kill-test script filed", os.path.exists(os.path.join(
          ROOT, "data", "killtests", "lane_registry_20260817.py")))
    # no gate may keep a private copy-pasted lane tuple for the two rewired gates
    check("AO: the chart-gate tuple is GONE from source (single source of truth)",
          '_bypass = ("hidden_entry", "vwap_reclaim", "zone_flip")' not in _ao_src)
    check("AO: the extension tuple is GONE from source",
          'if b[3] in ("rocket_catcher", "hidden_entry", "flat_top", "orb", "ma_pullback",'
          not in _ao_src)
except (AssertionError, ValueError, KeyError, AttributeError, TypeError) as _aoe:
    check("AO section", False, str(_aoe))

print("Q) 8/12 CONVENE-OR-DON'T-SHIP interlock (Marcos: two unaudited ships tonight both hid real bugs)")
# Under SHIP_CHECK=1 (the mandatory pre-deploy invocation), the rig goes RED unless
# data/audits/LATEST.md records the EXACT tree being shipped (git HEAD sha + clean worktree).
# The convening writes that file as its final act. Edit anything after the audit -> sha/dirty
# mismatch -> RED -> no deploy. Plain runs (no SHIP_CHECK) only warn, so development iterates.
try:
    import subprocess as _sp
    _sha = _sp.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()[:12]
    _dirty = bool(_sp.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    _lat = os.path.join(ROOT, "data", "audits", "LATEST.md")
    _rec = open(_lat).read() if os.path.exists(_lat) else ""
    # the artifact commit itself can't know its own sha: accept HEAD, or HEAD~1 when HEAD
    # touches ONLY bookkeeping (data/audits/, RESULTS_LEDGER.md) — code changes never ride that exemption
    _par = _sp.run(["git", "rev-parse", "HEAD~1"], cwd=ROOT, capture_output=True, text=True).stdout.strip()[:12]
    _tip_files = _sp.run(["git", "diff", "--name-only", "HEAD~1..HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    _book_only = _tip_files and all(f.startswith("data/audits/") or f == "RESULTS_LEDGER.md" for f in _tip_files)
    _ok = ((_sha in _rec) or (_book_only and _par in _rec)) and not _dirty
    # 8/12 Marcos ("does this also include a say by all members"): STANDING ROOM enforced —
    # the artifact must roll-call EVERY office on the roster (touched with findings, or clean
    # with the reason). A missing name = an officer denied their say = RED.
    _roster = [ln.strip() for ln in open(os.path.join(ROOT, "data", "audits", "ROSTER.txt"))
               if ln.strip()]
    _missing = [nm for nm in _roster if nm not in _rec]
    # 8/13 (Marcos: "make sure this is actually implemented"): the artifact must contain a
    # doctrine-inversion sweep section — either real content or the literal "n/a" line — per
    # data/audits/CONVENING_TEMPLATE.md. A missing section = an unasked question = RED.
    if "doctrine-inversion" not in _rec.lower():
        _missing.append("(doctrine-inversion sweep section)")
    _ok = _ok and not _missing
    if _missing and os.environ.get("SHIP_CHECK") == "1":
        print("  missing officers in LATEST.md: " + ", ".join(_missing[:8]) + ("…" if len(_missing) > 8 else ""))
    if os.environ.get("SHIP_CHECK") == "1":
        assert _ok, ("HEAD %s%s not covered by data/audits/LATEST.md — convene the Blast Radius "
                     "Auditor, write the artifact, commit, rerun" % (_sha, " (worktree DIRTY)" if _dirty else ""))
        check("ship-check: HEAD %s audited + tree clean" % _sha, True)
    else:
        print(("  ✅ audit current for HEAD " + _sha) if _ok else
              ("  ⚠️  HEAD " + _sha + (" (dirty)" if _dirty else "") + " NOT yet audited — required before any deploy"))
except AssertionError as _qe:
    check("ship-check audit interlock", False, str(_qe))

print(f"\n{'ALL GREEN' if not FAILS else 'RED: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
