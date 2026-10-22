#!/usr/bin/env bash
set -euo pipefail
# No Atlrium Git token or repository write permission. Everything submitted is a hint.
CONFIG_URL="${ATRIUM_REGISTRATION_CONFIG_URL:-https://thebigtreeinc.github.io/atrium/registration-config.json}"
CONFIG_PATH="$(mktemp)"; PAYLOAD_PATH="$(mktemp)"; trap 'rm -f "$CONFIG_PATH" "$PAYLOAD_PATH"' EXIT
curl --silent --show-error --fail --location --max-time 15 "$CONFIG_URL" -o "$CONFIG_PATH"
ENDPOINT="$(python - "$CONFIG_PATH" <<'PY'
import json,sys
from urllib.parse import urlsplit
config=json.load(open(sys.argv[1],encoding='utf8'))
if set(config)!={'schema','endpointUrl'} or config['schema']!='atrium.registration-source/v1':raise SystemExit('Invalid Atrium registration discovery file')
u=config['endpointUrl']
if not u:raise SystemExit('Atrium registration endpoint not configured; publisher source check succeeded but registration was not sent')
if not isinstance(u,str) or len(u)>1024:raise SystemExit('Invalid endpoint length')
p=urlsplit(u)
if p.scheme!='https' or not p.hostname or '.' not in p.hostname or p.port or p.hostname.endswith(('.local','.localhost','.internal')) or p.hostname.replace('.','').isdigit() or p.query or p.fragment or p.username or p.password or p.path!='/looprd/atrium-registration/v1/registrations':raise SystemExit('Unsafe Atrium registration URL')
print(u)
PY
)"
python - "$PAYLOAD_PATH" <<'PY'
import json,os,sys
with open(sys.argv[1],'w',encoding='utf8') as out:
 json.dump({'schema':'atrium.registration-notice/v1','repository':os.environ['REGISTRATION_REPO'],'sha':os.environ['REGISTRATION_SHA'],'runId':int(os.environ['REGISTRATION_RUN_ID'])},out)
PY
# The server returns queued, not published. Atrium independently checks GitHub.
curl --silent --show-error --fail-with-body --retry 2 --max-time 15 \
  --header 'Content-Type: application/json' \
  --data-binary "@$PAYLOAD_PATH" "$ENDPOINT"
echo
