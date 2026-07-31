"""IGNITION-10S rig (7/26, Marcos: "Move it to 10 second bars. The idea of knowingly being blind
is dumb."). Detector ported condition-for-condition from detect_ignition to the 10s stream after
the two-arm kill-test (n=26 paired 7/23-24: 10s entry beats 1-min fill 17/26, medMFE 0.90->1.06R,
>=2R 5->9, same price). FUNCTIONAL tests on the real machine + POSITIONAL pins on every wiring
touchpoint. Downstream gates must be UNTOUCHED — this change is eyes-only."""
import sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loader import load_bot
bot = load_bot()
SRC = (pathlib.Path(__file__).resolve().parent.parent / "marcos_trading_bot.py").read_text()
PASS, FAIL = [], []
def check(n, cond, d=""):
    (PASS if cond else FAIL).append(n)
    print(("  ok  " if cond else "  XX  ") + n + ((" — " + d) if d and not cond else ""))

# epochs at fixed ET wall-times TODAY (machine day-keys on today's ET date)
def ep(hh, mm, ss=0):
    now = dt.datetime.now(bot.EASTERN)
    return int(now.replace(hour=hh, minute=mm, second=ss, microsecond=0).timestamp())

def B(k, o, h, l, c, v): return (k, o, h, l, c, v)

# 7/28: the stale-fire guard (own suite: test_stale_fire_guard.py, real epochs) would suppress
# these wall-time fixtures whenever the rig runs after 09:31 ET. Neutralize it HERE ONLY so this
# suite tests detector logic at fixed wall-times regardless of run time-of-day.
bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9

def quiet_base(start_hh, start_mm, n=30, px=2.00, vol=200):
    """n flat low-vol 10s bars from the given ET time."""
    t0 = ep(start_hh, start_mm)
    return [B(t0 + i * 10, px, px * 1.004, px * 0.996, px, vol) for i in range(n)]

# ── M: machine functional ──
bot._ig10_st.clear()
base = quiet_base(9, 30)                                    # 9:30:00..9:34:50, open 2.00
surge = B(base[-1][0] + 10, 2.00, 2.10, 2.00, 2.09, 40000)  # green, strong close, +4.5% ext, 200x vol
r = bot.ignition_10s_step("AAA", base + [surge])
check("M1 fires on quiet base + 10s volume-accel break", r is not None)
check("M2 stop = base_lo*(1-buffer)", r and abs(r["stop"] - round(2.00 * 0.996 * (1 - bot.ZONE_STOP_BUFFER), 4)) < 1e-3)
check("M3 px stamp = fire-bar close (stale-guard contract)", r and abs(r["px"] - 2.09) < 1e-9)
check("M4 openp = first RTH bar open", r and abs(r["openp"] - 2.00) < 1e-9)
check("M5 volx/ext stamped", r and r["volx"] > 100 and 4.0 < r["ext_pct"] < 5.0)

bot._ig10_st.clear()
weak = B(base[-1][0] + 10, 2.00, 2.12, 2.00, 2.03, 40000)   # closes bottom-quarter of range
check("M6 refuses weak close (strong<0.5)", bot.ignition_10s_step("BBB", base + [weak]) is None)

bot._ig10_st.clear()
lowv = B(base[-1][0] + 10, 2.00, 2.10, 2.00, 2.09, 250)     # no volume acceleration
check("M7 refuses low-volume break", bot.ignition_10s_step("CCC", base + [lowv]) is None)

bot._ig10_st.clear()
ext = B(base[-1][0] + 10, 2.30, 2.40, 2.30, 2.39, 40000)    # +19.5% from open > MAX_EXT
check("M8 refuses extended break (+15% cap)", bot.ignition_10s_step("DDD", base + [ext]) is None)

bot._ig10_st.clear()
late_base = quiet_base(11, 30)                              # window (90 min) closed at 11:00
late_surge = B(late_base[-1][0] + 10, 2.00, 2.10, 2.00, 2.09, 40000)
check("M9 refuses fire outside the 90-min window", bot.ignition_10s_step("EEE", late_base + [late_surge]) is None)

bot._ig10_st.clear()
pre = quiet_base(9, 0, n=12)                                # premarket bars: ignored entirely
r10 = bot.ignition_10s_step("FFF", pre)
check("M10 premarket bars ignored (no state, no fire)", r10 is None and not bot._ig10_st.get("FFF", {}).get("bars"))

bot._ig10_st.clear()
dump = quiet_base(9, 30, px=2.00)
dump_surge = B(dump[-1][0] + 10, 1.85, 1.94, 1.85, 1.88, 40000)   # −6% from open < MIN_EXT... green+strong but dumped
check("M11 refuses dump-bounce (ext < -5%)", bot.ignition_10s_step("GGG", dump + [dump_surge]) is None)

bot._ig10_st.clear()
thin = quiet_base(9, 30, n=3)                               # < IGNITION_BASE_MIN*6 base bars
thin_surge = B(thin[-1][0] + 10, 2.00, 2.10, 2.00, 2.09, 40000)
check("M12 refuses with too-thin base", bot.ignition_10s_step("HHH", thin + [thin_surge]) is None)

# ── W: wiring pins ──
check("W1 IGNITION_10S default ON, env kill-switch",
      bot.IGNITION_10S is True and 'os.environ.get("IGNITION_10S", "1")' in SRC)
check("W2 base window = same 4 minutes (LOOKBACK*6) + abs-vol scaled /6",
      bot._IG10_BASE_BARS == bot.IGNITION_BASE_LOOKBACK * 6
      and abs(bot._IG10_MIN_ABS_VOL - bot.IGNITION_MIN_ABS_VOL / 6.0) < 1e-9)
check("W3 feed loop: own cursor + choke-point + still-forming bucket excluded",
      "_ig_cursor.get(_cur_i, 0)" in SRC and "_d10i, _ig_src = _curl_feed(t)" in SRC
      and SRC.count("int(time.time()) // 10 * 10") >= 3)
check("W4 feed is VWAP-INDEPENDENT (outside the _vr_sv gate)",
      "VWAP-INDEPENDENT" in SRC and SRC.index("_ig_fire = None") > SRC.index('"hidden_shadow_fire"'))
check("W5 consume branch swaps eyes only: ign = _ig_fire, legacy detector retained as fallback",
      "ign = _ig_fire" in SRC and "detect_ignition(_sess1, price)" in SRC)
check("W6 live no-chase cap re-applied at consume (ext_live clause)",
      "ignition_ext_live_skip" in SRC and '(price - ign["openp"]) / ign["openp"] > IGNITION_MAX_EXT' in SRC)
check("W7 stale-price fix on the 10s fire (a4fe777 pattern)",
      '_swap_price_ok(t, price, ign["px"]' in SRC and "stale_swap_refused" in SRC)
check("W8 triggered_ignition stamps src=10s/1min",
      'src=("10s" if IGNITION_10S else "1min")' in SRC)
check("W9 downstream gates UNTOUCHED: ignition still day-gain-floored + vel5-floored legacy",
      "ignition" in bot.DAYGAIN_LEGACY
      and '"ignition", "flat_top", "ma_pullback", "orb", "ema_bounce"' in SRC)
# W10 RE-PINNED 7/30 (Fable E3/E4 ruling + Marcos "ship it and shadow the alternative"): ignition
# now JOINS the live-structure bypass behind IGNITION_CHART_BYPASS (default on) — the old pin
# ("ignition NOT in the bypass") tested the pre-7/30 doctrine. The kill switch must restore the
# old gated behavior exactly, and the bypass must be conditional, not hardcoded.
check("W10 chart-gate bypass: conditional on IGNITION_CHART_BYPASS, kill switch restores legacy",
      '(("ignition",) if IGNITION_CHART_BYPASS else ())' in SRC
      and 'in ("hidden_entry", "vwap_reclaim", "zone_flip", "ignition")' not in SRC)
check("W11 once-per-ticker cap preserved (cache flag both feed + consume)",
      SRC.count('cache[t].get("ignition_fired")') >= 2 and 'cache[t]["ignition_fired"] = True' in SRC)

print(f"\n{'GREEN' if not FAIL else 'RED'} — {len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
