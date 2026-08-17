# RUNNER MODEL TEST — 8/17: is the negativity the MODEL or the TAPE?

**Analysis only. No bot edits, no deploy, no env change.**

Marcos's challenge: *"We KNOW the runners. IPST went +228% today. Every study you run comes
back wildly negative. If you can't make money on a stock that goes up 228%, the model is
wrong, not the market."*

Script: `data/killtests/runner_model_test_20260817.py` · rows: `runner_model_test_20260817_out.json`
Tape: SIP 10s bars rebuilt from `/v2/stocks/trades` (feed=sip), 13:25–19:55Z, 11 names.
E3 live-parity: $500 clip, +1% entry slip, −0.5% exit slip, intrabar stop FIRST, bank ½ at
+10%, 10% trail off run-high on 10s CLOSES after scale, 15:45 flatten. Stop = prior-60s tape
low, widened to a 4% floor (the live behaviour), except arm (e) which uses a hard 10%.

---

## 1. THE NAIVE BENCHMARK — arms (a)–(e), $ on a $500 clip

| TKR | arm | entry | exit | reason | time | $ |
|---|---|---|---|---|---|---|
| IPST | a 09:30 E3 | 8.0093 | 7.6505 | stop | 09:30:10 | −22.40 |
| IPST | b 10:00 E3 | 7.2922 | 6.9655 | stop | 10:06:10 | −22.40 |
| IPST | c VWAP E3 | 7.7332 | 7.2138 | stop | 10:32:40 | −33.58 |
| IPST | **d hold** | 8.0093 | 7.3614 | flatten | 15:45 | **−40.45** |
| IPST | **e 10% stop** | 8.0093 | 7.1723 | stop | 09:43:00 | **−52.25** |
| WETO | a | 10.3020 | 9.8405 | stop | 09:32:00 | −22.40 |
| WETO | b | 16.2038 | 15.4779 | stop | 10:00:20 | −22.40 |
| WETO | c | 14.5260 | 20.7059 | trail | 10:29:30 | +131.36 |
| WETO | **d hold** | 10.3020 | 23.3129 | flatten | 15:45 | **+631.47** |
| WETO | **e 10% stop** | 10.3020 | 23.3129 | flatten | 15:45 | **+631.47** |
| IVF | a | 2.2826 | 2.1803 | stop | 09:30:10 | −22.40 |
| IVF | b | 2.5552 | 2.4407 | stop | 10:00:30 | −22.40 |
| IVF | c | 2.5667 | 2.4477 | stop | 10:00:30 | −23.18 |
| IVF | **d hold** | 2.2826 | 1.4378 | flatten | 15:45 | **−185.06** |
| IVF | **e 10% stop** | 2.2826 | 2.0441 | stop | 11:02:00 | **−52.25** |
| TRUG | a | 1.6059 | 1.5340 | stop | 09:32:00 | −22.40 |
| TRUG | b | 1.5642 | 1.5933 | trail | 11:01:30 | +29.65 |
| TRUG | c | 1.6184 | 1.5459 | stop | 09:48:40 | −22.40 |
| TRUG | **d hold** | 1.6059 | 1.5734 | flatten | 15:45 | **−10.12** |
| TRUG | **e** | 1.6059 | 1.5734 | flatten | 15:45 | **−10.12** |
| WFF | a | 1.5150 | 2.7273 | trail | 10:53:50 | +225.05 |
| WFF | b | 1.5463 | 2.7273 | trail | 10:53:50 | +215.94 |
| WFF | c | 1.5204 | 2.7273 | trail | 10:53:50 | +223.45 |
| WFF | **d hold** | 1.5150 | 1.9900 | flatten | 15:45 | **+156.77** |
| WFF | **e** | 1.5150 | 1.9900 | flatten | 15:45 | **+156.77** |
| CDTG | a | 2.1917 | 2.0397 | stop | 09:32:20 | −34.66 |
| CDTG | b | 3.1612 | 2.8358 | stop | 10:00:10 | −51.46 |
| CDTG | c | 2.8059 | 2.6802 | stop | 09:55:40 | −22.40 |
| CDTG | **d hold** | 2.1917 | 2.7263 | flatten | 15:45 | **+121.96** |
| CDTG | **e** | 2.1917 | 2.7263 | flatten | 15:45 | **+121.96** |
| SLE | a | 3.0906 | 3.0945 | trail | 09:39:30 | +25.32 |
| SLE | b | 3.0907 | 2.9522 | stop | 12:03:00 | +13.80 |
| SLE | c | 3.2563 | 3.1105 | stop | 10:38:50 | −22.40 |
| SLE | **d hold** | 3.0906 | 3.0646 | flatten | 15:45 | **−4.21** |
| SLE | **e** | 3.0906 | 2.7676 | stop | 12:03:00 | **−52.25** |
| XPON | a | 4.5551 | 4.3510 | stop | 09:30:30 | −22.40 |
| XPON | b | 4.5046 | 4.5670 | flatten | 15:45 | +6.92 |
| XPON | c | 4.5301 | 4.3271 | stop | 09:53:30 | −22.40 |
| XPON | **d hold** | 4.5551 | 4.5670 | flatten | 15:45 | **+1.30** |
| XPON | **e** | 4.5551 | 4.5670 | flatten | 15:45 | **+1.30** |
| RETO | a | 1.2524 | 1.1963 | stop | 09:50:00 | −22.40 |
| RETO | b | 1.2019 | 1.4527 | trail | 12:40:00 | +77.17 |
| RETO | c | 1.2283 | 1.1733 | stop | 11:16:40 | −22.40 |
| RETO | **d hold** | 1.2524 | 1.6417 | flatten | 15:45 | **+155.44** |
| RETO | **e** | 1.2524 | 1.6417 | flatten | 15:45 | **+155.44** |
| NIVF | a | 0.6009 | 0.6244 | trail | 15:33:40 | +34.74 |
| NIVF | b | 0.6416 | 0.6367 | flatten | 15:45 | −3.78 |
| NIVF | c | 0.6404 | 0.6367 | flatten | 15:45 | −2.90 |
| NIVF | **d hold** | 0.6009 | 0.6367 | flatten | 15:45 | **+29.74** |
| NIVF | **e** | 0.6009 | 0.6367 | flatten | 15:45 | **+29.74** |
| DFSC | a | 2.7068 | 2.7609 | trail | 10:22:30 | +30.00 |
| DFSC | b | 2.8028 | 2.7609 | trail | 10:22:30 | +21.27 |
| DFSC | c | 2.8144 | 2.6883 | stop | 10:22:40 | −22.40 |
| DFSC | **d hold** | 2.7068 | 2.3118 | flatten | 15:45 | **−72.97** |
| DFSC | **e** | 2.7068 | 2.4239 | stop | 14:11:10 | **−52.25** |

### ARM TOTALS (11 names, $500 clip each)

| arm | n | total | avg/trade |
|---|---|---|---|
| (a) 09:30 open, E3 | 11 | **+$146.04** | +$13.28 |
| (b) 10:00, E3 | 11 | **+$242.30** | +$22.03 |
| (c) VWAP touch after 09:45, E3 | 11 | **+$160.75** | +$14.61 |
| (d) 09:30 buy & HOLD to 15:45 | 11 | **+$783.89** | +$71.26 |
| (e) 09:30, hard 10% stop only, hold to flatten | 11 | **+$877.56** | +$79.78 |

**The dumbest arm wins by 6×.** Arm (e) — buy the open, one hard 10% stop, no scale, no
trail, flatten at 15:45 — returns **+$877.56** against E3's **+$146.04** on identical entries.
The gap between (a) and (e) on the same entry price and the same tape is **$731.52**.

---

## 2. WHERE E3 GIVES IT BACK — MFE capture

MFE measured over the full entry→15:45 window (independent of when the arm exited).

| TKR | entry | true MFE | MFE% | MFE$ | E3 (a) $ | **capture** | hold (d) $ | hold capture |
|---|---|---|---|---|---|---|---|---|
| IPST | 8.0093 | 9.6600 | +20.6% | 103.05 | −22.40 | **−21.7%** | −40.45 | −39.2% |
| WETO | 10.3020 | 29.5000 | +186.4% | 931.76 | −22.40 | **−2.4%** | +631.47 | +67.8% |
| IVF | 2.2826 | 2.8000 | +22.7% | 113.34 | −22.40 | −19.8% | −185.06 | −163.3% |
| TRUG | 1.6059 | 1.8199 | +13.3% | 66.63 | −22.40 | −33.6% | −10.12 | −15.2% |
| WFF | 1.5150 | 10.7100 | +606.9% | 3034.65 | +225.05 | **+7.4%** | +156.77 | +5.2% |
| CDTG | 2.1917 | 3.3000 | +50.6% | 252.84 | −34.66 | −13.7% | +121.96 | +48.2% |
| SLE | 3.0906 | 3.4700 | +12.3% | 61.38 | +25.32 | +41.3% | −4.21 | −6.9% |
| XPON | 4.5551 | 4.9000 | +7.6% | 37.86 | −22.40 | −59.2% | +1.30 | +3.4% |
| RETO | 1.2524 | 2.1600 | +72.5% | 362.34 | −22.40 | −6.2% | +155.44 | +42.9% |
| NIVF | 0.6009 | 0.7000 | +16.5% | 82.41 | +34.74 | +42.2% | +29.74 | +36.1% |
| DFSC | 2.7068 | 3.0946 | +14.3% | 71.63 | +30.00 | +41.9% | −72.97 | −101.9% |

**Mean MFE capture: E3 −2.2%, buy-and-hold −11.2%** — but the mean is not the story; the
distribution is. E3 captures a decent 40%-ish on the small movers (SLE, NIVF, DFSC) and
captures **essentially nothing on the two genuine runners**, which is exactly backwards.

### The two decompositions that matter

**WETO — killed by the STOP.** Entry 10.3020 at 09:30. Stop 9.8899 (a 4% floor). Stopped at
**09:32:00**, two minutes in, for −$22.40. The name then ran to **$29.50 at 14:50** and closed
the session at 23.43. E3 captured **−2.4% of a $931.76 MFE**. Buy-and-hold on the identical
entry: **+$631.47**. Single-name model cost: **$653.87**.

**WFF — killed by the TRAIL.** Entry 1.5150. Banked ½ at +10%, then the 10%-off-run-high trail
on 10s closes exited the runner leg at **2.7273 at 10:53:50** (run-high to that point: 3.30).
WFF then went to **$10.71 at 12:08:10** — the trail cut a +607% move at +80%. Captured
**7.4% of a $3,034.65 MFE**. This is not a stop problem; the trade was *working* and the trail
took it off mid-run.

Those two names are the entire case. The stop kills the runner before it runs; if the runner
survives the stop, the trail takes it off before the run finishes.

---

## 3. THE FILL ASSUMPTIONS — how much is slippage?

Arm (a) re-run with progressively kinder fills:

| TKR | (i) current | (ii) no entry slip | (iii) no slip either | (iv) mid fills |
|---|---|---|---|---|
| IPST | −22.40 | +23.75 | +25.00 | −20.00 |
| WETO | −22.40 | −22.40 | −20.00 | −20.00 |
| IVF | −22.40 | +39.16 | +40.49 | +44.06 |
| TRUG | −22.40 | −22.40 | −20.00 | −20.00 |
| WFF | +225.05 | +229.55 | +231.83 | +231.83 |
| CDTG | −34.66 | −30.01 | −27.65 | −20.00 |
| SLE | +25.32 | +27.82 | +29.09 | +26.22 |
| XPON | −22.40 | −22.40 | −20.00 | −20.00 |
| RETO | −22.40 | +67.88 | +69.35 | +69.35 |
| NIVF | +34.74 | +37.34 | +38.66 | +35.40 |
| DFSC | +30.00 | +32.55 | +33.84 | +35.30 |
| **TOTAL** | **+146.04** | **+360.84** | **+380.62** | **+342.16** |

- **entry slip (i→ii): +$214.80** — the single largest fill effect, and it is *non-linear*:
  the +1% entry slip does not merely cost 1%, it pushes the entry up far enough that the
  4%-floor stop sits inside normal open noise and converts winners into stop-outs (IPST, IVF,
  RETO all flip from red to green with the slip removed).
- **exit slip (ii→iii): +$19.78** — negligible. Exit slip is not the problem.
- **mid fills (iii→iv): −$38.46** — *worse*, because on names that opened and immediately
  faded, the bar midpoint is a higher entry than the open. Mid-fill is not a kinder assumption.

So slippage assumptions explain **~$215 of the $731.52 gap (29%)**. The remaining **~$517
(71%) is the stop and trail logic itself.**

---

## 4. THE STOP — stopped out then recovered

**7 of 7 stopped trades traded back above their entry before 15:45. 100%.**

| TKR | stopped at | stop px | entry | $ | high after stop | recovered | 2× wider stop |
|---|---|---|---|---|---|---|---|
| IPST | 09:30:10 | 7.6889 | 8.0093 | −22.40 | 9.6600 | yes | 7.3686 → trail **+$21.29** |
| WETO | 09:32:00 | 9.8899 | 10.3020 | −22.40 | 29.5000 | yes | 9.4778 → trail **+$131.39** |
| IVF | 09:30:10 | 2.1913 | 2.2826 | −22.40 | 2.8000 | yes | 2.1000 → trail **+$36.54** |
| TRUG | 09:32:00 | 1.5417 | 1.6059 | −22.40 | 1.8199 | yes | 1.4774 → trail **+$14.32** |
| CDTG | 09:32:20 | 2.0500 | 2.1917 | −34.66 | 3.3000 | yes | 1.9083 → trail **+$42.85** |
| XPON | 09:30:30 | 4.3729 | 4.5551 | −22.40 | 4.9000 | yes | 4.1907 → flatten **+$1.30** |
| RETO | 09:50:00 | 1.2023 | 1.2524 | −22.40 | 2.1600 | yes | 1.1522 → trail **+$64.98** |

**Same set: current stop −$169.06 → 2× wider stop +$312.68. Delta +$481.74.**

Note the times: five of seven stops fire **within 150 seconds of the open**. This is not risk
management, it is the model paying the opening spread and calling it a loss.

---

## 5. WHERE THE MOVE HAPPENED — the IPST correction

| TKR | pre LO | pre HI | 09:30 open | RTH high | 15:45 | RTH open→high | RTH open→close |
|---|---|---|---|---|---|---|---|
| IPST | 7.7600 | 8.1399 | 7.9300 | 9.6600 | 7.3984 | +21.8% | **−6.7%** |
| WETO | 9.9220 | 10.3900 | 10.2000 | 29.5000 | 23.4300 | **+189.2%** | +129.7% |
| IVF | 2.2498 | 2.3200 | 2.2600 | 2.8000 | 1.4450 | +23.9% | −36.1% |
| TRUG | 1.5700 | 1.6100 | 1.5900 | 1.8199 | 1.5813 | +14.5% | −0.5% |
| WFF | — | — | 1.5000 | 10.7100 | 2.0000 | **+614.0%** | +33.3% |
| CDTG | 2.0500 | 2.0500 | 2.1700 | 3.3000 | 2.7400 | +52.1% | +26.3% |
| SLE | 2.9100 | 3.0700 | 3.0600 | 3.4700 | 3.0800 | +13.4% | +0.7% |
| XPON | 4.4400 | 4.5800 | 4.5100 | 4.9000 | 4.5899 | +8.6% | +1.8% |
| RETO | — | — | 1.2400 | 2.1600 | 1.6500 | +74.2% | +33.1% |
| NIVF | 0.6000 | 0.6300 | 0.5950 | 0.7000 | 0.6399 | +17.6% | +7.5% |
| DFSC | 2.6700 | 2.8244 | 2.6800 | 3.0946 | 2.3234 | +15.5% | −13.3% |

**Marcos's headline example does not support his case — but his thesis survives without it.**
IPST's +228% was a **gap**, banked before the bell. From the 09:30 open it offered only +21.8%
to its high and closed the RTH session **−6.7%**. Buy-and-hold IPST loses **−$40.45**. There
was no 228% intraday move to catch. The names that *did* run intraday were **WETO (+189%)** and
**WFF (+614%)** — and those are precisely the two the exit model destroyed.

---

## VERDICT: **MIXED — and the majority is MODEL.**

Total gap between E3 (arm a, +$146.04) and the dumbest viable arm (e, +$877.56) on identical
entries and identical tape: **$731.52.**

| component | $ | share |
|---|---|---|
| **STOP too tight** (4% floor + 1% entry slip → stopped in the first 2 min; 7/7 recovered) | ~$482 | **66%** |
| **ENTRY SLIP assumption** (+1%, non-linear because it arms the tight stop) | ~$215 | **29%** |
| **TRAIL too tight** (10% off run-high on 10s closes; WFF cut at +80% of a +607% move) | large but overlapping the above | — |
| exit slip assumption (−0.5%) | ~$20 | 3% |
| mid-price fills | −$38 (worse) | — |

**Marcos is substantially right.** The negativity on genuine runners is an artifact of the exit
model, not the tape. On the day's two real intraday runners the model returned **−$22.40
(WETO)** and **+$225.05 on a $3,035 MFE (WFF)** while doing nothing more sophisticated than
buying the open and sitting there returned **+$631** and **+$157**. A 100% stopped-then-
recovered rate on 7 of 7 stops is not a sampling artifact; it is a mis-specified stop.

**Where he is wrong:** the specific example. IPST was a premarket gap that faded all day — even
perfect buy-and-hold loses money on it. And buy-and-hold is *not* the answer either: it
loses **−$185 on IVF** and **−$73 on DFSC** when the runner round-trips. That is why arm (e)
(hold + one hard 10% stop) beats pure hold by $94 — the stop has to exist, it just has to be
**wide enough to survive the first two minutes.**

### The specific components and numbers to take forward
1. **Stop width is the primary defect.** 4% floor after a +1% entry slip = ~3% of real room,
   which the open eats. Doubling it turns −$169 into +$313 on the same seven trades.
2. **The trail is the secondary defect on the biggest winners.** 10% off run-high on 10s
   *closes* exits a parabolic name mid-move (WFF: out at 2.73, high 10.71 seventy-five minutes
   later). Capture on the largest MFE of the day was 7.4%.
3. **Entry slip at +1% is not a neutral cost** — it is load-bearing, because it interacts with
   the stop floor. Whether +1% is real needs its own measurement against actual fills.

*Caveat: n=11 names, one session, entries chosen by clock rather than by signal. This tests
the exit model, not the entry lanes. It does not license a ship — it names where to look.*
