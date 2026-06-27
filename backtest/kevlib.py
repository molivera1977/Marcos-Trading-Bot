# VERBATIM-extracted from marcos_trading_bot.py — the bot's exact supply/room detection code.
STOP_LOSS_PCT=0.07; FLAT_TOP_WINDOW=4; FLAT_TOP_MAX_RANGE=0.080; TOPPING_TAIL_RATIO=0.55
PIVOT_WINDOW=3; SUPPLY_CLUSTER_PCT=0.01; SUPPLY_MIN_DIST_PCT=0.003; MIN_ROOM_RR=2.0

def is_topping_tail(bar) -> bool:
    """Kev's 'topping tail / tail off the high' — a candle whose upper wick is ≥
    TOPPING_TAIL_RATIO of its full range = price spiked up and got rejected at the high.
    Used as an entry-skip (don't buy into rejection) and as an exit (momentum is done)."""
    try:
        o = float(bar.get("open")  or bar.get("o") or 0)
        c = float(bar.get("close") or bar.get("c") or 0)
        h = float(bar.get("high")  or bar.get("h") or 0)
        l = float(bar.get("low")   or bar.get("l") or 0)
    except (TypeError, ValueError):
        return False
    rng = h - l
    if rng <= 0:
        return False
    upper_wick = h - max(o, c)

def _bar_high(b):  return float(b.get("high")  or b.get("h") or b.get("close") or b.get("c") or 0)
def _bar_low(b):   return float(b.get("low")   or b.get("l") or b.get("close") or b.get("c") or 0)
def _bar_open(b):  return float(b.get("open")  or b.get("o") or b.get("close") or b.get("c") or 0)
def _bar_close(b): return float(b.get("close") or b.get("c") or 0)

def _pivot_highs(bars, window=PIVOT_WINDOW):
    """Swing highs = a bar whose high tops the `window` bars on each side (a real local peak =
    a level where price topped and reversed = supply). What Kev marks by eye."""
    highs = [_bar_high(b) for b in bars]
    peaks = []
    for i in range(window, len(highs) - window):
        h = highs[i]
        if h <= 0:
            continue
        if h == max(highs[i - window:i + window + 1]) and h > highs[i - 1] and h > highs[i + 1]:
            peaks.append(h)
    return peaks

def _topping_tail_highs(bars):
    """Highs of topping-tail candles — where a big upper wick shows sellers rejected the high (supply).
    Uses the canonical is_topping_tail() (defined below; resolved at call time)."""
    out = []
    for b in bars:
        if is_topping_tail(b):
            out.append(_bar_high(b))
    return out

def find_next_supply(bars, current_price, premarket_high=None, prior_day_high=None):
    """Nearest OVERHEAD supply above current_price, from the intraday bars + key reference levels.
    Returns (level, source) — or (None, 'open') when nothing is overhead = NEW HIGH OF DAY = open room.
    Sources, strongest first: premarket high, prior-day high, swing-high pivots, topping-tail highs."""
    if not bars or current_price <= 0:
        return None, "unknown"
    floor = current_price * (1 + SUPPLY_MIN_DIST_PCT)   # ignore levels basically AT price
    levels = []
    if premarket_high and premarket_high >= floor: levels.append((float(premarket_high), "pm_high"))
    if prior_day_high and prior_day_high >= floor: levels.append((float(prior_day_high), "pd_high"))
    hod = max((_bar_high(b) for b in bars), default=0)   # day's high = the ceiling (pivot windows miss edges)
    if hod >= floor: levels.append((hod, "hod"))
    levels += [(h, "pivot") for h in _pivot_highs(bars) if h >= floor]
    levels += [(h, "tail")  for h in _topping_tail_highs(bars) if h >= floor]
    if not levels:
        return None, "open"
    levels.sort(key=lambda x: x[0])
    return round(levels[0][0], 4), levels[0][1]   # nearest overhead = the cap on the trade

def compute_room(entry_price, stop_loss, bars, premarket_high=None, prior_day_high=None):
    """Kev's gate: room to the next supply ÷ risk to support. Open room (new HOD) = pass (rr=999).
    ANY failure (bad bars, etc.) returns rr=None so the caller FAILS OPEN — a code glitch in the
    detector must never halt trading (per feedback_kev_is_the_bible: verify our code, never block on a bug)."""
    try:
        risk = entry_price - stop_loss
        supply, src = find_next_supply(bars, entry_price, premarket_high, prior_day_high)
        if src == "unknown":
            return {"next_supply": None, "supply_src": "unknown", "room_pct": None, "rr_to_supply": None, "risk": round(risk, 4)}
        if supply is None:                              # new high of day → open room (JSON-safe sentinel)
            return {"next_supply": None, "supply_src": "open", "room_pct": None, "rr_to_supply": 999.0, "risk": round(risk, 4)}
        room = supply - entry_price
        rr = (room / risk) if risk > 0 else 0.0
        return {"next_supply": supply, "supply_src": src,
                "room_pct": round(room / entry_price * 100, 2),
                "rr_to_supply": round(rr, 2), "risk": round(risk, 4)}
    except Exception as e:
        print(f"⚠️  compute_room error ({e}) — failing OPEN (room unknown)")
        return {"next_supply": None, "supply_src": "unknown", "room_pct": None, "rr_to_supply": None, "risk": 0}


