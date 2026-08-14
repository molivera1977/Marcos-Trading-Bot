# QUARTERMASTER REPORT — 2026-08-14 (task #50 + ferry gaps)

Officer: Quartermaster. Data-side only; no bot/reader/dashboard code touched, no deploys.

## 1. Ferry — universe cache gaps (data/universe/)
Script: `data/universe/ferry_20260814.py` (merge-only manifest update; aggregation copied verbatim from `harvester.py` phase 2; SIP feed throughout).

- **2026-08-14** (was fully absent — manifest built through 8/13): 12 manifest rows appended + 12 bars10s files built: MF, WETO, LBGJ, AKAN, BOXL, XHG, DFSC, HAO, GIPR, LEXX, TMS, BANL. (AKAN was listed twice in the flag — deduped.)
- **2026-07-27** (DFNS halt day): manifest already held 12 names, all 12 bars10s files already present (DFNS, BIYA, WLDS, LVWR incl.). Flagged stragglers STAK, MTNB, NXTC were NOT in the top-12 screen; appended to the manifest with computed gain/prev_c/dvol (prev day 7/24) and ferried: STAK 119,629 ticks → 5,345 bars; MTNB 349,562 → 5,619; NXTC 8,152 → 1,525.
- **SIP failures: ZERO.** 15/15 name-days landed. Biggest pull: WETO 8/14, 1,056,367 ticks → 4,790 bars.
- Merge-only verified: no manifest keys/rows removed; no existing bars10s file overwritten.

## 2. Backup — crown jewels
- Path: `~/Library/Mobile Documents/com~apple~CloudDocs/TradingBot/backups/backup_20260814.tar.gz`
- Size: **794 KB** · **75 files** (killtests *.md+*.json, data/history/, data/audits/, data/universe/manifest.json)
- **bars10s EXCLUDED deliberately**: 156 MB, and REBUILDABLE from SIP via `harvester.py` (resumable; that is its restore story — manifest.json in the backup is the index it rebuilds from).

## 3. Restore drill — PASS
- Extracted tarball to scratch dir: 75/75 files.
- Byte-identical spot checks (`cmp`): `data/universe/manifest.json`, `data/history/VERIFIED_BOOK.json`, `data/killtests/RESULTS_LEDGER.md` — all IDENTICAL.
- A backup without a restore drill is a rumor; this one is not a rumor.

## 4. Standing gaps (owed)
- iCloud TradingBot folder audit (first-act charter item) — still owed.
- Backup cadence not yet automated (this was a manual dated tarball).
- bars10s has no second copy anywhere; restore story is SIP re-harvest only (acceptable while SIP sub active — becomes a gap if the $99/mo SIP plan ever lapses).
- 7/27 STAK/MTNB/NXTC manifest rows are appended beyond the top-12 screen; flagged so downstream top-12 consumers know the day now has 15 rows.

Officers touched: Quartermaster (owner), Feed Engineer (SIP pulls — clean), Statistician (no ledger numbers asserted). Standing by.
