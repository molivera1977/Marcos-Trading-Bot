"""One-night watcher (8/11 00:20+): Kev posted that the Tuesday TOP-3 would be LATE tonight
(new-car pickup). run_once('night') mis-targets 8/12 after midnight, so this drives the
internals with the explicit 8/11 date. Exits 0 with POSTED on success; exits 3 on no-sheet."""
import datetime, sys
import kev_sweep_server as k

target = datetime.date(2026, 8, 11)
k.fetch_pass("shorts", k.DATA / "shorts")
f = k.find_top3(target, update=False)
if not f:
    f = k.find_top3(target, update=True)   # in case he titles the late post an UPDATE
if not f:
    print("no sheet yet"); sys.exit(3)
levels = k._vision_check(f.name.split("_", 1)[0], k.parse_top3(f))
posted = k.post_sheet(target.strftime("%Y-%m-%d"), levels, f.name,
                      src_text=f.read_text(errors="ignore"))
print(f"POSTED {posted} names from {f.name}: {sorted(levels.keys()) if isinstance(levels, dict) else levels}")
sys.exit(0 if posted else 4)
