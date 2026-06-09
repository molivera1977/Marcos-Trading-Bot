"""
Webull Access Token Setup — Run this ONCE locally to get your access token.

Usage:
  python webull_setup.py

Steps:
  1. Enter your Webull App Key and App Secret when prompted
  2. The script calls Webull to create a pending token
  3. Webull sends an SMS/notification to your Webull app — approve it
  4. Press Enter, and the script verifies the token is active
  5. Copy the token and add it to Railway as WEBULL_ACCESS_TOKEN

Tokens expire in 15 days. Run this script again when it expires.
"""

import json
import time
import requests
import hashlib
import hmac
import base64
import uuid
import socket
from datetime import datetime
from urllib.parse import quote

print("=" * 60)
print("  WEBULL ACCESS TOKEN SETUP")
print("=" * 60)
print()

WEBULL_APP_KEY    = input("Enter your Webull App Key:    ").strip()
WEBULL_APP_SECRET = input("Enter your Webull App Secret: ").strip()
print()

WEBULL_HOST = "us-openapi-alb.uat.webullbroker.com"
BASE_URL    = f"https://{WEBULL_HOST}"


def _headers(path, body_dict=None, query_params=None, access_token=None):
    """Build Webull OpenAPI v2 headers with HMAC-SHA1 signature."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = str(uuid.uuid5(uuid.NAMESPACE_URL,
                           socket.gethostname() + str(uuid.uuid1())))

    headers = {
        "Content-Type":          "application/json",
        "x-app-key":             WEBULL_APP_KEY,
        "x-timestamp":           timestamp,
        "x-signature-version":   "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce":     nonce,
        "x-version":             "v2",
    }
    if access_token:
        headers["x-access-token"] = access_token

    sign_params = {
        "x-app-key":             WEBULL_APP_KEY,
        "x-timestamp":           timestamp,
        "x-signature-version":   "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce":     nonce,
        "host":                  WEBULL_HOST,
    }
    if query_params:
        for k, v in query_params.items():
            sign_params[k.lower()] = str(v)

    body_string = None
    if body_dict is not None:
        body_str    = json.dumps(body_dict, ensure_ascii=False, separators=(',', ':'))
        body_string = hashlib.md5(body_str.encode()).hexdigest().upper()

    sorted_kv = "&".join(f"{k}={v}" for k, v in sorted(sign_params.items()))
    s2s = f"{path}&{sorted_kv}"
    if body_string:
        s2s += f"&{body_string}"

    s2s = quote(s2s, safe='')
    key = (WEBULL_APP_SECRET + "&").encode()
    h   = hmac.new(key, s2s.encode(), hashlib.sha1)
    headers["x-signature"] = base64.b64encode(h.digest()).decode()
    return headers


# ── Step 1: Create token ──────────────────────────────────────
print("📱 Step 1: Creating Webull access token...")
path = "/openapi/auth/token/create"
body = {}
hdrs = _headers(path, body_dict=body)
body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))

try:
    resp = requests.post(f"{BASE_URL}{path}", headers=hdrs,
                         data=body_str, timeout=15)
    print(f"   HTTP {resp.status_code}")
    data = resp.json()
    print(f"   Response: {json.dumps(data, indent=4)}")
except Exception as e:
    print(f"❌ Request failed: {e}")
    print("\nCheck your App Key and App Secret are correct.")
    exit(1)

# Extract token from response (try common field paths)
token = None
if isinstance(data.get("data"), dict):
    token = data["data"].get("token")
elif isinstance(data.get("data"), str):
    token = data["data"]
elif data.get("token"):
    token = data["token"]

if not token:
    print(f"\n❌ Could not extract token from response: {data}")
    print("Check your credentials and try again.")
    exit(1)

print(f"\n✅ Pending token received: {token}")
print()
print("━" * 60)
print("  ACTION REQUIRED:")
print("  Open your Webull app → you should see a login notification.")
print("  Approve it (or enter the SMS code if prompted).")
print("━" * 60)
input("\nPress Enter after approving in your Webull app...")

# ── Step 2: Poll until token is NORMAL ───────────────────────
print("\n🔍 Step 2: Checking token status...")
path_check   = "/openapi/auth/token/check"
query_params = {"token": token}

for attempt in range(1, 31):
    try:
        hdrs = _headers(path_check, query_params=query_params)
        resp = requests.get(f"{BASE_URL}{path_check}", headers=hdrs,
                            params=query_params, timeout=15)
        data = resp.json()

        # Status can be nested in data or at top level
        status = None
        if isinstance(data.get("data"), dict):
            status = data["data"].get("status")
        elif data.get("status"):
            status = data["status"]

        print(f"   Attempt {attempt}/30 — status: {status or 'unknown'}")

        if status == "NORMAL":
            print()
            print("=" * 60)
            print("  🎉  SUCCESS! Your Webull access token:")
            print()
            print(f"  {token}")
            print()
            print("  Add this to Railway.app environment variables as:")
            print("  WEBULL_ACCESS_TOKEN = <the token above>")
            print()
            print("  ⚠️  Token expires in ~15 days.")
            print("  Run this script again when it expires.")
            print("=" * 60)
            exit(0)

        elif status in ("INVALID", "EXPIRED"):
            print(f"\n❌ Token is {status}. Run setup again.")
            exit(1)

        elif status == "PENDING":
            print(f"   Still pending — make sure you approved in the Webull app.")

    except Exception as e:
        print(f"   Error checking token: {e}")

    time.sleep(5)

print("\n❌ Timed out after 30 attempts.")
print("Make sure you approved the login in your Webull app and run setup again.")
