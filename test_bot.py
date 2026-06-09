"""
Marcos Trading Bot — Full Diagnostic
Tests every component and gives a clear PASS / FAIL for each.

Usage:
  python3 test_bot.py

Reads the same env vars Railway uses. You can also pass them inline:
  WEBULL_APP_KEY=xxx WEBULL_APP_SECRET=yyy ... python3 test_bot.py
"""

import os, re, json, imaplib, email, hmac, hashlib, base64, uuid, socket, requests
from datetime import datetime, timedelta
from urllib.parse import quote

# ── Load credentials (same names as Railway env vars) ──────────
WEBULL_APP_KEY      = os.environ.get("WEBULL_APP_KEY", "").strip()
WEBULL_APP_SECRET   = os.environ.get("WEBULL_APP_SECRET", "").strip()
WEBULL_ACCOUNT_ID   = os.environ.get("WEBULL_ACCOUNT_ID", "").strip()
WEBULL_ACCESS_TOKEN = os.environ.get("WEBULL_ACCESS_TOKEN", "").strip()
EMAIL_ADDRESS       = os.environ.get("EMAIL_ADDRESS", "molivera1977@icloud.com").strip()
EMAIL_APP_PASSWORD  = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "").strip()
RESEND_API_KEY      = os.environ.get("RESEND_API_KEY", "").strip()

TRADING_HOST = "api.webull.com"
MARKET_HOST  = "api.webull.com"   # same host — avoids data-api.webull.com timeout

results = {}

def ok(name, msg=""):
    results[name] = ("✅ PASS", msg)
    print(f"  ✅ PASS  {name}" + (f" — {msg}" if msg else ""))

def fail(name, msg=""):
    results[name] = ("❌ FAIL", msg)
    print(f"  ❌ FAIL  {name}" + (f" — {msg}" if msg else ""))

def warn(name, msg=""):
    results[name] = ("⚠️  WARN", msg)
    print(f"  ⚠️  WARN  {name}" + (f" — {msg}" if msg else ""))


# ── Signature helper (mirrors the bot exactly) ─────────────────
def _headers(method, path, host, query_params=None, body_dict=None):
    _SHA1_HOSTS = {"api.webull.com", "events-api.webull.com"}
    if host in _SHA1_HOSTS:
        algo_name = "HMAC-SHA1";  hmac_algo = hashlib.sha1
        body_hash = lambda s: hashlib.md5(s.encode()).hexdigest().upper()
    else:
        algo_name = "HMAC-SHA256"; hmac_algo = hashlib.sha256
        body_hash = lambda s: hashlib.sha256(s.encode()).hexdigest().upper()

    ts    = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = str(uuid.uuid5(uuid.NAMESPACE_URL, socket.gethostname() + str(uuid.uuid1())))
    hdrs  = {"Content-Type":"application/json","x-app-key":WEBULL_APP_KEY,
             "x-timestamp":ts,"x-signature-version":"1.0",
             "x-signature-algorithm":algo_name,"x-signature-nonce":nonce,"x-version":"v2"}
    if WEBULL_ACCESS_TOKEN:
        hdrs["x-access-token"] = WEBULL_ACCESS_TOKEN

    sp = {"x-app-key":WEBULL_APP_KEY,"x-timestamp":ts,"x-signature-version":"1.0",
          "x-signature-algorithm":algo_name,"x-signature-nonce":nonce,"host":host}
    if query_params:
        for k,v in query_params.items(): sp[k.lower()] = str(v)

    bs = None
    if body_dict is not None:
        bs = body_hash(json.dumps(body_dict, ensure_ascii=False, separators=(',',':')))

    kv  = "&".join(f"{k}={v}" for k,v in sorted(sp.items()))
    s2s = f"{path}&{kv}" + (f"&{bs}" if bs else "")
    s2s = quote(s2s, safe='')
    key = (WEBULL_APP_SECRET + "&").encode()
    hdrs["x-signature"] = base64.b64encode(hmac.new(key, s2s.encode(), hmac_algo).digest()).decode()
    return hdrs


def _get(path, qp=None, host=None):
    host = host or TRADING_HOST
    return requests.get(f"https://{host}{path}",
                        headers=_headers("GET", path, host, query_params=qp),
                        params=qp, timeout=12)

def _post(path, body, host=None):
    host = host or TRADING_HOST
    return requests.post(f"https://{host}{path}",
                         headers=_headers("POST", path, host, body_dict=body),
                         data=json.dumps(body, ensure_ascii=False, separators=(',',':')),
                         timeout=12)


# ═══════════════════════════════════════════════════════════════
print("\n" + "═"*60)
print("  MARCOS TRADING BOT — FULL DIAGNOSTIC")
print(f"  {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
print("═"*60)


# ── 1. Credentials present ─────────────────────────────────────
print("\n[1] Credentials")
for name, val in [("WEBULL_APP_KEY",    WEBULL_APP_KEY),
                  ("WEBULL_APP_SECRET", WEBULL_APP_SECRET),
                  ("WEBULL_ACCOUNT_ID", WEBULL_ACCOUNT_ID),
                  ("WEBULL_ACCESS_TOKEN", WEBULL_ACCESS_TOKEN),
                  ("EMAIL_APP_PASSWORD", EMAIL_APP_PASSWORD),
                  ("ANTHROPIC_API_KEY",  ANTHROPIC_API_KEY),
                  ("RESEND_API_KEY",     RESEND_API_KEY)]:
    if val:
        ok(name, f"{val[:4]}{'*'*(len(val)-4) if len(val)>4 else ''}")
    else:
        fail(name, "NOT SET")


# ── 2. Webull token validity ────────────────────────────────────
print("\n[2] Webull Token")
try:
    path  = "/openapi/auth/token/check"
    body  = {"token": WEBULL_ACCESS_TOKEN}
    resp  = _post(path, body)
    data  = resp.json()
    status = data.get("status") or (data.get("data") or {}).get("status")
    if status == "NORMAL":
        ok("token_valid", f"status=NORMAL")
    elif status == "PENDING":
        fail("token_valid", "PENDING — approve in Webull app, then re-run webull_setup.py")
    elif status in ("INVALID", "EXPIRED"):
        fail("token_valid", f"{status} — run webull_setup.py to get a new token")
    else:
        warn("token_valid", f"Unknown status={status!r}  raw={json.dumps(data)[:200]}")
except Exception as e:
    fail("token_valid", str(e))


# ── 3. Account ID discovery ────────────────────────────────────
print("\n[3] Webull Account ID")
discovered_id = None
for ep in ("/openapi/account/list",
           "/openapi/trade/account/list",
           "/openapi/assets/account/list"):
    try:
        r = _get(ep)
        if r.status_code == 200:
            raw = r.json()
            data = raw.get("data", raw)
            items = data if isinstance(data, list) else data.get("items", [])
            if items:
                a = items[0]
                aid = a.get("account_id") or a.get("accountId") or a.get("id")
                if aid:
                    discovered_id = str(aid)
                    ok("account_id_discovery", f"Found account_id={aid} at {ep}")
                    break
                else:
                    warn("account_id_discovery", f"{ep} returned items but no id field: {json.dumps(items[0])[:150]}")
            else:
                warn("account_id_discovery", f"{ep} returned empty list — HTTP 200 but no accounts")
        else:
            print(f"     {ep} → HTTP {r.status_code}: {r.text[:120]}")
    except Exception as ex:
        print(f"     {ep} → error: {ex}")

if not discovered_id:
    if WEBULL_ACCOUNT_ID:
        warn("account_id_discovery", f"Could not discover via API — will use env var: {WEBULL_ACCOUNT_ID}")
        discovered_id = WEBULL_ACCOUNT_ID
    else:
        fail("account_id_discovery", "No account ID found anywhere")


# ── 4. Balance endpoint ────────────────────────────────────────
print("\n[4] Webull Balance")
for acct_id in ([discovered_id] if discovered_id else []):
    try:
        r = _get("/openapi/assets/balance", qp={"account_id": acct_id})
        print(f"     HTTP {r.status_code}  body: {r.text[:400]}")
        if r.status_code == 200:
            data = r.json().get("data", {})
            cash = (data.get("cash_balance") or data.get("cashBalance") or
                    data.get("available_cash") or data.get("availableFunds") or
                    data.get("net_liquidation"))
            ok("balance", f"cash=${cash}  account_id={acct_id}")
        elif r.status_code == 401:
            fail("balance", f"401 Unauthorized — full response: {r.text[:300]}")
        else:
            fail("balance", f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        fail("balance", str(e))


# ── 5. Market data (quotes) ────────────────────────────────────
print("\n[5] Webull Market Data")
try:
    r = _get("/openapi/market-data/stock/quotes",
             qp={"symbol":"AAPL","category":"US_STOCK"},
             host=MARKET_HOST)
    print(f"     HTTP {r.status_code}  body: {r.text[:300]}")
    if r.status_code == 200:
        ok("market_data_quotes", "AAPL quote fetched")
    else:
        fail("market_data_quotes", f"HTTP {r.status_code}: {r.text[:200]}")
except Exception as e:
    fail("market_data_quotes", str(e))

try:
    r = _get("/openapi/market-data/stock/bars",
             qp={"symbol":"AAPL","category":"US_STOCK","timespan":"m1","count":"5"},
             host=MARKET_HOST)
    print(f"     HTTP {r.status_code}  body: {r.text[:200]}")
    if r.status_code == 200:
        ok("market_data_bars", "AAPL bars fetched")
    else:
        warn("market_data_bars", f"HTTP {r.status_code}: {r.text[:150]}")
except Exception as e:
    fail("market_data_bars", str(e))


# ── 6. iCloud email ────────────────────────────────────────────
print("\n[6] iCloud Email")
try:
    mail = imaplib.IMAP4_SSL("imap.mail.me.com", 993)
    mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    ok("icloud_login", f"Logged in as {EMAIL_ADDRESS}")

    mail.select("inbox")
    since = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
    _, msgs = mail.search(None, f'(SINCE "{since}")')
    ids = msgs[0].split() if msgs[0] else []
    print(f"     Found {len(ids)} email(s) in last 48h")

    if ids:
        # Show subjects + senders of last 5
        skip = {"THE","FOR","AND","NOT","ALL","DAY","TOP","NEW","BIG","HOT",
                "PDT","RE","AI","ET","FW","FWD","TO","IN","UP","AM","PM","IS","IT"}
        best_subj, best_score = "", -1
        for mid in ids[-5:][::-1]:
            _, mdata = mail.fetch(mid, "(BODY[HEADER.FIELDS (FROM SUBJECT)])")
            raw = b""
            for part in mdata:
                if isinstance(part, tuple): raw = part[1]; break
            if not raw:
                raw = max((p for p in mdata if isinstance(p, bytes)), key=len, default=b"")
            parsed = email.message_from_bytes(raw)
            subj = parsed.get("subject","") or ""
            frm  = parsed.get("from","") or ""
            # Score for tickers
            combined = (subj).upper()
            dollar_hits = len(re.findall(r'\$[A-Z]{2,5}\b', combined))
            caps_hits   = len([t for t in re.findall(r'\b[A-Z]{2,5}\b', combined) if t not in skip])
            score = dollar_hits*5 + caps_hits
            flag = " ← best pick" if score > best_score else ""
            print(f"     Email {mid.decode() if isinstance(mid,bytes) else mid}: "
                  f"from={frm[:35]!r}  subj={subj[:55]!r}  score={score}{flag}")
            if score > best_score:
                best_score = score; best_subj = subj

        if best_score > 0:
            ok("email_tickers", f"Best email subject: {best_subj[:60]!r}  score={best_score}")
        else:
            warn("email_tickers", "No emails with obvious tickers found — "
                                  "make sure Kev's email has stock symbols in subject/body")
    else:
        warn("email_tickers", "No emails in last 48h — inbox is empty for that window")

    mail.logout()
except Exception as e:
    fail("icloud_login", str(e))


# ── 7. Anthropic API ───────────────────────────────────────────
print("\n[7] Anthropic / Claude")
try:
    import anthropic as _ant
    client = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=20,
        messages=[{"role":"user","content":"Reply with just the word READY"}]
    )
    reply = msg.content[0].text.strip() if msg.content else ""
    if "READY" in reply.upper():
        ok("anthropic_api", f"Claude replied: {reply!r}")
    else:
        warn("anthropic_api", f"Unexpected reply: {reply!r}")
except Exception as e:
    fail("anthropic_api", str(e))


# ── 8. Resend email ────────────────────────────────────────────
print("\n[8] Resend Email")
try:
    import resend as _resend
    _resend.api_key = RESEND_API_KEY
    r = _resend.Emails.send({
        "from":    "Marcos Bot <bot@resend.dev>",
        "to":      ["molivera1977@gmail.com"],
        "subject": "🤖 Bot Diagnostic — All Systems Check",
        "text":    "This is a test from the trading bot diagnostic script. If you got this, email sending works!"
    })
    ok("resend_email", f"Test email sent! id={getattr(r,'id',r)}")
except Exception as e:
    fail("resend_email", str(e))


# ── Summary ────────────────────────────────────────────────────
print("\n" + "═"*60)
print("  SUMMARY")
print("═"*60)
passes = sum(1 for v,_ in results.values() if "PASS" in v)
fails  = sum(1 for v,_ in results.values() if "FAIL" in v)
warns  = sum(1 for v,_ in results.values() if "WARN" in v)
for name,(status,msg) in results.items():
    print(f"  {status}  {name}" + (f" — {msg}" if msg else ""))
print(f"\n  {passes} passed · {warns} warnings · {fails} failed")
if fails == 0:
    print("\n  🟢 BOT IS READY TO TRADE")
elif fails <= 2:
    print("\n  🟡 ALMOST READY — fix the FAILs above")
else:
    print("\n  🔴 NOT READY — multiple issues need fixing")
print("═"*60 + "\n")
