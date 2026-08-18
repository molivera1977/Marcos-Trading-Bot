#!/usr/bin/env python3
"""CONFIG EPOCHS — 8/17 C2.  Which machine actually produced each stretch of a day's book?

WHY THIS EXISTS
---------------
2026-08-17 carried FIVE boot_config rows.  "8/17 did X" is therefore a statement about a BAG OF
FIVE MACHINES, and "8/17 vs 8/14" compares two bags whose composition nobody recorded.  Every
multi-day aggregate this system has produced is a mixture.  This tool makes the mixture visible:
it groups a date range's fire/fill rows into CONFIG EPOCHS and reports the counts per epoch.

TWO MODES, and the report always says which one it used
-------------------------------------------------------
  STAMPED   rows carry `config_hash` (shipped 2026-08-17 night).  Epochs are exact: a boundary is
            a genuine change of code-or-env, and a plain restart of the same image does NOT open
            a new epoch.
  INFERRED  rows predate the stamp.  Epochs are segmented by boot_config-row boundaries instead,
            which is the best that history supports.  This OVERCOUNTS: two restarts of the same
            image look like two epochs, because nothing recorded that they were the same machine.
            Inferred epoch ids are `boot#N`, never a hash, so the two can never be confused.

LIMITS
------
  * The hash covers code + the behaviour-governing env list.  It cannot see broker state, the
    day's Kev sheet, vendor behaviour, or the market.  Same hash does NOT mean same world.
  * Counts here are ROW counts from the decisions archive, and rows are not necessarily distinct
    setups (see data/killtests/ma_pullback_dup_20260817.md — ma_pullback logged 210 rows for
    ~123 distinct setups on 8/17).  Treat per-epoch fire counts as row counts, labelled as such.
  * A day with no boot_config row at all (bot ran across midnight) reports one epoch `boot#0`
    covering everything, flagged UNSEGMENTED.

USAGE
-----
    python3 data/audits/config_epochs.py 2026-08-17
    python3 data/audits/config_epochs.py 2026-08-11 2026-08-17        # inclusive range
    python3 data/audits/config_epochs.py 2026-08-17 --json
    SCREENER_URL=... DASHBOARD_SECRET=... python3 data/audits/config_epochs.py 2026-08-17

Exit 0 = report produced.  Exit 2 = could not reach the archive.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://zestful-intuition-production-b16a.up.railway.app"
FILL_STATUSES = ("filled", "retest_fill", "tier_fill")
BOOT = "boot_config"


# ── archive access ────────────────────────────────────────────────────────────────────────
def _get(url, secret, path):
    req = urllib.request.Request(url.rstrip("/") + path,
                                 headers={"X-Dashboard-Secret": secret})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def fetch_day(url, secret, date):
    """(rows, by_status) for one date — boot markers, fires and fills only.

    Pulled per-status rather than as one bulk page: `watching`/`consolidating` alone are
    thousands of rows a day and would push the interesting rows past any limit."""
    head = _get(url, secret, "/api/decisions_archive?date=%s&limit=1" % date)
    by_status = head.get("by_status") or {}
    wanted = [s for s in by_status
              if s == BOOT or s in FILL_STATUSES or s.startswith("triggered_")]
    rows = []
    for st in sorted(wanted):
        d = _get(url, secret,
                 "/api/decisions_archive?date=%s&status=%s&limit=5000" % (date, st))
        rows.extend(d.get("rows") or [])
    rows.sort(key=lambda r: str(r.get("recorded_at") or ""))
    return rows, by_status


# ── epoch assignment ──────────────────────────────────────────────────────────────────────
def assign_epochs(rows):
    """Tag every row with an epoch id.  Returns (rows, mode) where mode is 'stamped',
    'inferred', or 'mixed' — a day that straddles the ship carries both kinds."""
    boot_n, cur_boot = 0, "boot#0"
    n_stamped = 0
    for r in rows:
        if r.get("status") == BOOT:
            boot_n += 1
            cur_boot = "boot#%d" % boot_n
        h = r.get("config_hash")
        if h:
            r["_epoch"], r["_kind"] = h, "stamped"
            n_stamped += 1
        else:
            r["_epoch"], r["_kind"] = cur_boot, "inferred"
    if not rows:
        return rows, "empty"
    if n_stamped == len(rows):
        return rows, "stamped"
    return rows, ("mixed" if n_stamped else "inferred")


def summarise(rows):
    """epoch id -> {first, last, fires, fills, kind, code_sha, lanes{lane: rows}, boots}"""
    out = {}
    for r in rows:
        e = out.setdefault(r["_epoch"], {"first": None, "last": None, "fires": 0, "fills": 0,
                                         "boots": 0, "kind": r["_kind"], "code_sha": None,
                                         "lanes": {}})
        t = str(r.get("recorded_at") or "")
        if e["first"] is None or t < e["first"]:
            e["first"] = t
        if e["last"] is None or t > e["last"]:
            e["last"] = t
        e["code_sha"] = e["code_sha"] or r.get("code_sha")
        st = str(r.get("status") or "")
        if st == BOOT:
            e["boots"] += 1
        elif st in FILL_STATUSES:
            e["fills"] += 1
        elif st.startswith("triggered_"):
            e["fires"] += 1
            lane = st[len("triggered_"):]
            e["lanes"][lane] = e["lanes"].get(lane, 0) + 1
    return out


def _hhmm(iso):
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%H:%M")
    except Exception:
        return "??:??"


def report_day(date, rows, mode, by_status):
    ep = summarise(rows)
    order = sorted(ep, key=lambda k: ep[k]["first"] or "")
    lines = []
    if not order:
        lines.append("%s: no boot/fire/fill rows in the archive." % date)
        return lines, ep
    lines.append("%s — %d epoch%s  [%s]" % (date, len(order), "" if len(order) == 1 else "s",
                                            mode.upper()))
    if mode in ("inferred", "mixed"):
        lines.append("   ⚠️  INFERRED epochs are boot-row segments, not config identity — a "
                     "restart of the SAME machine counts as a new epoch (overcount).")
    if not any(r.get("status") == BOOT for r in rows):
        lines.append("   ⚠️  UNSEGMENTED: no boot_config row on this date.")
    for e in order:
        v = ep[e]
        top = sorted(v["lanes"].items(), key=lambda kv: -kv[1])[:4]
        lines.append("   %-14s %s–%s   fire_rows=%-4d fills=%-3d boots=%-2d %s%s"
                     % (e, _hhmm(v["first"]), _hhmm(v["last"]), v["fires"], v["fills"],
                        v["boots"],
                        ("code=%s " % v["code_sha"]) if v["code_sha"] else "",
                        ("| " + ", ".join("%s×%d" % (k, n) for k, n in top)) if top else ""))
    tot_f = sum(v["fires"] for v in ep.values())
    tot_x = sum(v["fills"] for v in ep.values())
    lines.append("   TOTAL fire_rows=%d fills=%d  (fire_rows are ROW counts, not distinct "
                 "setups — see ma_pullback_dup_20260817.md)" % (tot_f, tot_x))
    return lines, ep


def main(argv=None):
    ap = argparse.ArgumentParser(description="Config epochs for a date range.")
    ap.add_argument("start")
    ap.add_argument("end", nargs="?")
    ap.add_argument("--url", default=os.environ.get("SCREENER_URL") or DEFAULT_URL)
    ap.add_argument("--secret", default=os.environ.get("DASHBOARD_SECRET") or "marcos2026")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    d0 = datetime.date.fromisoformat(a.start)
    d1 = datetime.date.fromisoformat(a.end) if a.end else d0
    if d1 < d0:
        d0, d1 = d1, d0

    blob, all_lines = {}, []
    d = d0
    while d <= d1:
        ds = d.isoformat()
        try:
            rows, by_status = fetch_day(a.url, a.secret, ds)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as e:
            print("archive unreachable for %s: %s" % (ds, e), file=sys.stderr)
            return 2
        rows, mode = assign_epochs(rows)
        lines, ep = report_day(ds, rows, mode, by_status)
        all_lines.extend(lines)
        blob[ds] = {"mode": mode, "epochs": ep}
        d += datetime.timedelta(days=1)

    if (d1 - d0).days > 0:
        hashes = sorted({e for v in blob.values() for e, x in v["epochs"].items()
                         if x["kind"] == "stamped"})
        modes = {v["mode"] for v in blob.values()}
        all_lines.append("")
        all_lines.append("RANGE %s..%s — %d day(s), config hashes covered: %s"
                         % (d0, d1, (d1 - d0).days + 1, ", ".join(hashes) if hashes else "NONE"))
        if modes - {"stamped"} or len(hashes) > 1:
            all_lines.append("MIXED-EPOCH: this range does not describe one machine. Any "
                             "aggregate over it must say so in its LIMITS.")

    if a.json:
        print(json.dumps(blob, indent=1, default=str))
    else:
        print("\n".join(all_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
