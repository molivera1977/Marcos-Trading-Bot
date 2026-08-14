# FICTIONAL-FILL CENSUS + FIX (Marcos: "This needs to be worked on right now... Get to the bottom of it. Now.")
## Mechanism (code-confirmed)
Monitor accumulates _tape_hi over EVERY fetched bar (marcos_trading_bot.py ~:8896) and the fetch
window reaches ~45min pre-entry; RESTING_BANK tier fills trigger on _tape_hi > tier (:8809) and
BOOK AT TIER PRICE. The ":8803 'cumulative since entry'" comment was FALSE — no time check existed.
A resting order cannot fill on tape that predates its placement.
## Damage (era 7/24-8/13, 181 trades w/ fills, 226 fills audited vs post-entry 10s tape)
41 FICTIONAL fills, +$284.78 fake profit. 82% of fills verify clean. Top: HUIZ 8/7 six fills
$105.20 (tape topped 2.45, fills booked 2.64-2.91 -> the era-record day is really ~+$425 not
+$531); BQ 8/12 $31.12; FVN 8/6 $10.92; CYCU, FGL, WYHG, PCLA, MGRX, CELZ, THH single-digits.
## Fix (shipped tonight)
_tape_birth = monitor start - 15s grace; bars older than birth EXCLUDED from tape_lo/hi
(unparseable bar time = excluded, fail-closed). Kill: TAPE_SINCE_ENTRY=0.
Blast radius: second consumer _verify_exit_px gets NARROWER (stricter) bounds — clamping only to
proven post-entry tape; empty-tape path unchanged (raw + unverified label). 7/27 blind-stop class
still caught (stricter = safer). Resumed monitors: tape since RESUME counts (conservative).
## Book corrections
Store is append-only by ruling — corrections applied AT ANALYSIS like the runner-leg ledger:
this census file = the correction ledger for the 41 fills. OFFICIAL_BOOK gets an inflation
footnote (Historian). Sim-vs-live delta shrinks accordingly for the go/no-go read.
