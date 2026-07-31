"""VELOCITY_RIDE ON IGNITION (7/30, Marcos: "test it on ignition for fun").
The harness has never modeled VELOCITY_RIDE — so every ignition number so far is the WITHOUT case.
Here the live rule is implemented exactly: at a scale target, if price gained >= VELO_RIDE_PCT (12%)
over the trailing VELO_BARS (3) 1-min bars, SKIP the scale and hold. Compare with/without, at the
live 2.0x and at the proposed 4.5x."""
import sys, pathlib, json, urllib.request, collections
import harness
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "rig"))
from loader import load_bot
bot = load_bot(); bot.CURL_FIRE_MAX_AGE_SECS = 10 ** 9
DAYS = ("2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30")
VELO_BARS, VELO_PCT = bot.VELO_BARS, bot.VELO_RIDE_PCT
print(f"live rule: skip the scale if price gained >= {VELO_PCT:.0%} over the last {VELO_BARS} 1-min bars\n")

uni = collections.defaultdict(set)
for d in DAYS:
    rows = (json.load(urllib.request.urlopen(
        f"{harness.U}/api/decisions_archive?date={d}&limit=50000", timeout=30)).get("rows") or [])
    for r in rows:
        if r.get("status") in ("triggered_ignition", "ignition_low_room_soft", "daygain_reject") and r.get("ticker"):
            uni[d].add(r["ticker"])

def walk(b, i0, e, s, vride):
    """kev25 ladder with intrabar tiers; vride=True applies the live deferral. Returns (pnl_ps, defers)."""
    R = e - s
    tiers = [(e + R, 0.50), (e + 2 * R, 0.25)]
    rem, real, cur, cum, defers = 1.0, 0.0, s, 0.0, 0
    m1 = {}
    for j in range(i0, len(b)):
        k, o, h, l, c, v, hm = b[j]
        key = k // 60
        d = m1.setdefault(key, [c, c]); d[1] = c
        if hm >= "15:45:00":
            return real + rem * (c - e), defers
        if l <= cur:
            fill = cur - (harness.SLIP_PCT * e if cur <= s + 1e-9 else 0.0)
            return real + rem * (fill - e), defers
        for tp, tc in tiers:
            if h >= tp and tc > cum:
                if vride:
                    keys = sorted(m1)
                    if len(keys) > VELO_BARS:
                        c_now = m1[keys[-1]][1]; c_ago = m1[keys[-1 - VELO_BARS]][1]
                        if c_ago > 0 and (c_now - c_ago) / c_ago >= VELO_PCT:
                            defers += 1
                            continue                       # DEFER — ride the vertical
                q = tc - cum; real += q * (tp - e); rem -= q; cum = tc
                if cum >= 0.75: cur = max(cur, e)           # BE floor after scale 2 (live)
        if rem <= 1e-9:
            return real, defers
    return real + rem * (b[-1][4] - e), defers

def run(vol, vride, label):
    bot.IGNITION_VOL_MULT = vol
    bot.IGNITION_MAX_EXT = 0.15; bot.IGNITION_MIN_ABS_VOL = 5000; bot._IG10_MIN_ABS_VOL = 5000/6.0
    tot = n = w = D = 0
    for d in DAYS:
        for tk in uni[d]:
            b = harness.bars(tk, d)
            if not b: continue
            bot._ig10_st.pop(tk, None); taken = False
            for i, bar in enumerate(b):
                f = bot.ignition_10s_step(tk, [bar[:6]])
                if not f or taken: continue
                e, s = f["px"], f["stop"]
                if not (e and s and e > s): continue
                sh, clamp, det = harness.size(e, s, b, i)
                if sh == 0: continue
                taken = True
                pps, defers = walk(b, i, e, s, vride)
                tot += pps * sh; n += 1; w += (pps > 0); D += defers
    print(f"  {label:38}{n:5}{tot:11.2f}{(tot/n if n else 0):9.2f}{w:6}{D:9}")
    return tot

print(f"  {'setting':38}{'n':>5}{'total':>11}{'$/fire':>9}{'wins':>6}{'defers':>9}")
a = run(2.0, False, "2.0x  VELOCITY_RIDE OFF")
b_ = run(2.0, True,  "2.0x  VELOCITY_RIDE ON (live)")
print(f"  {'-> cost of the rule at 2.0x':38}{'':5}{b_-a:11.2f}")
c = run(4.5, False, "4.5x  VELOCITY_RIDE OFF")
d_ = run(4.5, True,  "4.5x  VELOCITY_RIDE ON (live)")
print(f"  {'-> cost of the rule at 4.5x':38}{'':5}{d_-c:11.2f}")
