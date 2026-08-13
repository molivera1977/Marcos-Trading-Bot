#!/bin/zsh
# THE ONLY SANCTIONED DEPLOY PATH (8/13, Marcos: "do we have the protocol to prevent this
# mistake from happening again?"). Refuses to deploy unless the full gate passes IN THIS RUN:
#   1. SHIP_CHECK=1 rig (includes section Q: audited sha + clean tree + full-room roll call)
#   2. flat book verified THIS invocation
#   3. RTH guard: refuses Mon-Fri 09:30-16:00 ET unless SHIP_RTH_OVERRIDE=1 (Marcos-only call)
# Usage: ./ship.sh "<railway service name>"
set -e
SVC="$1"
[ -z "$SVC" ] && { echo "usage: ./ship.sh \"<service>\""; exit 2; }
ET_DOW=$(TZ=America/New_York date +%u); ET_HM=$(TZ=America/New_York date +%H:%M)
if [ "$ET_DOW" -le 5 ] && [[ "$ET_HM" > "09:29" ]] && [[ "$ET_HM" < "16:00" ]] && [ "$SHIP_RTH_OVERRIDE" != "1" ]; then
  echo "🛑 RTH ($ET_HM ET) — no deploys during market hours (law). SHIP_RTH_OVERRIDE=1 only on Marcos's word."; exit 1
fi
echo "— gate 1/3: SHIP_CHECK rig —"
SHIP_CHECK=1 python3 rig/test_shipset_20260804.py || { echo "🛑 rig RED — convene, write the artifact, commit, retry"; exit 1; }
echo "— gate 2/3: flat book —"
OT=$(curl -s --max-time 20 https://zestful-intuition-production-b16a.up.railway.app/api/open_trades)
echo "   $OT"
echo "$OT" | grep -q '"open_trades":\s*\[\]' || { echo "🛑 book NOT flat — STOP; Marcos decides per position"; exit 1; }
echo "— gate 3/3: deploy $SVC —"
railway up --service "$SVC" --detach
echo "✅ shipped $SVC at $(TZ=America/New_York date '+%H:%M:%S ET') — verify the new deployment goes SUCCESS + boot logs clean"
