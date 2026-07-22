# Alpaca capture — requirements note (Phase 0, 2026-07-22)

`websocket-client` is NOT in `requirements.txt` (checked 7/22 — the repo only carries
`paho-mqtt` for the Webull stream). Phase 0 deliberately does NOT edit the shared
`requirements.txt`: it is market hours, and a shared-file change rebuilds every service
at the next push (the 7/21 lesson).

Interim (already wired): `railway.alpacacap.toml` startCommand pip-installs
`websocket-client==1.8.0` at boot, so the new service is self-contained.

At the next EVENING push ritual (after 16:00, flat, per the deploy rules):
1. Add to `requirements.txt`:  `websocket-client==1.8.0   # alpaca_capture websocket feed`
2. Simplify `railway.alpacacap.toml` startCommand to `python alpaca_capture.py`.

We use `websocket-client` directly — NOT the `alpaca-py` SDK — one tiny proven dependency,
raw frames we can log, nothing that could drag extra deps into the shared build.
