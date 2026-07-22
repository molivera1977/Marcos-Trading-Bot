#!/usr/bin/env python3
"""TICKER CHARACTER BOOK (Handicapper #69, Marcos 7/22: "each day adds to each ticker's
character and we add to it each day... if Kev speaks on an individual ticker, we add that").

A living per-ticker ledger, appended daily from three sources — data only, no verdict labels:
  1. TAPE  — per day, for every watched name that moved >=10% (or was traded): open→high %,
             giveback % (high→close of the o→h range), peak 5-min velocity, missing RTH
             minutes (halt OR thin tape OR recorder coverage hole — confounded, labeled as such),
             first-bar time (late first bar = late subscribe = coverage hole).
  2. TRADES — every live trade on the name that day: machine, entry/exit, P&L, R, exit reason.
  3. KEV   — dated spoken verdicts/levels, quoted with a source (video id / sheet), never vibes.

Store: data/character_book.json (committed). Render: data/character_book.md.
Doctrine (persona_handicapper): character stays DATA until kill-tested — nothing gates on it.

Usage:
  python3 character_book.py append [YYYY-MM-DD]     # add the day's tape+trade rows (default: today ET)
  python3 character_book.py note TICKER "text" [--src SOURCE] [--date YYYY-MM-DD]
  python3 character_book.py render                  # regenerate the markdown view
  python3 character_book.py show TICKER
"""
import json, sys, os, urllib.request, urllib.parse, datetime, pathlib

U = os.environ.get("SCREENER_URL", "https://zestful-intuition-production-b16a.up.railway.app").rstrip("/")
HERE = pathlib.Path(__file__).resolve().parent
STORE = HERE / "data" / "character_book.json"
MD = HERE / "data" / "character_book.md"

def api(path):
    try:
        with urllib.request.urlopen(f"{U}{path}", timeout=30) as r:
            return json.load(r)
    except Exception as e:
        print(f"  api error {path}: {e}")
        return {}

def load():
    return json.load(open(STORE)) if STORE.exists() else {}

def save(book):
    STORE.parent.mkdir(exist_ok=True)
    json.dump(book, open(STORE, "w"), indent=1, sort_keys=True)

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

def tape_row(tk, d):
    bars = [x for x in (api(f"/api/minute_ext?ticker={urllib.parse.quote(tk)}&count=1200").get("bars") or [])
            if str(x.get("time", "")).startswith(d) and x.get("session") == "RTH"]
    bars.sort(key=lambda x: str(x["time"]))
    if len(bars) < 30:
        return None
    c = [f(x.get("close")) for x in bars]; h = [f(x.get("high")) for x in bars]
    o, hi = c[0], max(h)
    if o <= 0:
        return None
    move = (hi - o) / o * 100
    gb = (hi - c[-1]) / (hi - o) * 100 if hi > o else 0.0
    mins = [str(x["time"])[11:16] for x in bars]
    span = (int(mins[-1][:2]) * 60 + int(mins[-1][3:])) - (int(mins[0][:2]) * 60 + int(mins[0][3:])) + 1
    vel5 = max(((c[i] - c[i - 5]) / c[i - 5] * 100 for i in range(5, len(c)) if c[i - 5] > 0), default=0.0)
    vol = sum(f(x.get("volume")) for x in bars)
    return {"o2h_pct": round(move, 1), "giveback_pct": round(gb, 1), "maxvel5_pct": round(vel5, 1),
            "missing_min": span - len(bars), "first_bar_utc": mins[0], "close": c[-1], "day_vol": int(vol)}

def append_day(d):
    book = load()
    trades = [t for t in (api("/api/trades").get("trades") or []) if t.get("date") == d]
    roster = set(api(f"/api/watching?date={d}").get("tickers") or []) | {t.get("ticker") for t in trades}
    for r in (api(f"/api/decisions_archive?date={d}&limit=12000").get("rows") or []):
        roster.add((r.get("ticker") or "").upper())
    roster.discard("N/A"); roster.discard("")
    n_tape = n_tr = 0
    for tk in sorted(x for x in roster if x):
        traded = [t for t in trades if t.get("ticker") == tk]
        row = tape_row(tk, d)
        if row is None and not traded:
            continue
        if row and row["o2h_pct"] < 10 and not traded:
            continue
        e = book.setdefault(tk, {"days": {}, "notes": []})
        day = e["days"].setdefault(d, {})
        if row:
            day["tape"] = row; n_tape += 1
        if traded:
            day["trades"] = [{"machine": t.get("entry_type"), "entry": t.get("entry"), "exit": t.get("exit"),
                              "pnl": round(f(t.get("pnl")), 2),
                              "R": round(f(t.get("pnl")) / f(t.get("planned_risk")), 2) if f(t.get("planned_risk")) > 0 else None,
                              "exit_reason": str(t.get("exit_reason", ""))[:40]} for t in traded]
            n_tr += len(traded)
    save(book)
    print(f"{d}: appended tape rows for {n_tape} names, {n_tr} trades. Book now {len(book)} tickers.")

def note(tk, text, src, d):
    book = load()
    e = book.setdefault(tk.upper(), {"days": {}, "notes": []})
    if any(n["text"] == text for n in e["notes"]):
        print("duplicate note — skipped"); return
    e["notes"].append({"date": d, "text": text, "source": src})
    save(book)
    print(f"note added to {tk.upper()} ({d}, src={src})")

def render():
    book = load()
    out = ["# Ticker Character Book (living ledger — data speaks, no labels)",
           f"_{len(book)} tickers; rendered {datetime.date.today()}. missing_min = halt OR thin tape OR recorder",
           "coverage hole (confounded); late first_bar = late subscribe. Character is DATA until kill-tested._", ""]
    for tk in sorted(book):
        e = book[tk]
        out.append(f"### {tk}")
        for d in sorted(e["days"]):
            day = e["days"][d]
            if "tape" in day:
                t = day["tape"]
                out.append(f"- {d} tape: o→h +{t['o2h_pct']}%, giveback {t['giveback_pct']}%, "
                           f"vel5 {t['maxvel5_pct']}%, missing {t['missing_min']}m, first bar {t['first_bar_utc']}Z, "
                           f"close {t['close']}, vol {t['day_vol']:,}")
            for tr in day.get("trades", []):
                out.append(f"- {d} TRADE {tr['machine']}: {tr['entry']}→{tr['exit']} {tr['pnl']:+.2f}"
                           + (f" ({tr['R']:+.2f}R)" if tr.get("R") is not None else "") + f" [{tr['exit_reason']}]")
        for n in e["notes"]:
            out.append(f"- {n['date']} KEV/NOTE [{n['source']}]: {n['text']}")
        out.append("")
    MD.write_text("\n".join(out))
    print(f"rendered {MD} ({len(book)} tickers)")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "append":
        et = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
        append_day(a[1] if len(a) > 1 else et.strftime("%Y-%m-%d")); render()
    elif a[0] == "note":
        src = a[a.index("--src") + 1] if "--src" in a else "manual"
        d = a[a.index("--date") + 1] if "--date" in a else str(datetime.date.today())
        note(a[1], a[2], src, d); render()
    elif a[0] == "render":
        render()
    elif a[0] == "show":
        print(json.dumps(load().get(a[1].upper(), {}), indent=1))
    else:
        print(__doc__)
