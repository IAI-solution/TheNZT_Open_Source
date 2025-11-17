
# #!/usr/bin/env bash
# set -euo pipefail

# # --- REQUIRED environment variables (no defaults) ---
# : "${MONGO_HOST:?MONGO_HOST is not set}"
# : "${MONGO_PORT:?MONGO_PORT is not set}"
# : "${ROOT_DB:?ROOT_DB is not set}"
# : "${ROOT_USER:?ROOT_USER is not set}"
# : "${ROOT_PASS:?ROOT_PASS is not set}"

# MONGOSH_BIN="${MONGOSH_BIN:-mongosh}"
# RETRIES=60
# SLEEP_SEC=1

# function die { echo "❌ $*"; exit 1; }

# # Ensure mongosh exists
# if ! command -v "$MONGOSH_BIN" >/dev/null 2>&1; then
#   die "mongosh not found. Install mongosh or set MONGOSH_BIN path."
# fi

# echo "⏳ Waiting for mongod at ${MONGO_HOST}:${MONGO_PORT}..."

# for i in $(seq 1 $RETRIES); do
#   if "$MONGOSH_BIN" --host "${MONGO_HOST}" --port "${MONGO_PORT}" --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
#     echo "✅ MongoDB is reachable"
#     break
#   fi
#   if [ "$i" -eq "$RETRIES" ]; then
#     die "MongoDB did not become ready in time."
#   fi
#   sleep "$SLEEP_SEC"
# done

# # Helper to run JS on a DB
# function run_js() {
#   local db="$1"; shift
#   local js="$*"
#   "$MONGOSH_BIN" --host "${MONGO_HOST}" --port "${MONGO_PORT}" "${db}" --eval "${js}"
# }

# echo "⚙️ Checking if root user '${ROOT_USER}' exists in ${ROOT_DB}..."

# if run_js "${ROOT_DB}" "printjson(db.getSiblingDB('${ROOT_DB}').getUser('${ROOT_USER}'))" | grep -q null; then
#   echo "ℹ️ Root user missing — creating..."
#   if run_js "${ROOT_DB}" "db.getSiblingDB('${ROOT_DB}').createUser({user:'${ROOT_USER}', pwd:'${ROOT_PASS}', roles:[{role:'root', db:'${ROOT_DB}'}]});" >/dev/null 2>&1; then
#     echo "✅ Root user created"
#   else
#     die "Failed to create root user"
#   fi
# else
#   echo "ℹ️ Root user already exists"
# fi

# echo "🔐 Testing root authentication..."
# if run_js "${ROOT_DB}" "db.auth('${ROOT_USER}','${ROOT_PASS}'); print(db.runCommand({connectionStatus:1}).ok);" | grep -q "1"; then
#   echo "✅ Root authentication successful"
# else
#   die "❌ Root authentication failed with provided credentials"
# fi

# echo "🎉 MongoDB admin initialization complete."

#!/usr/bin/env bash
set -euo pipefail

# Use the values commonly provided to the official mongo image
: "${MONGO_HOST:?MONGO_HOST is not set}"
: "${MONGO_PORT:?MONGO_PORT is not set}"
: "${MONGO_INITDB_DATABASE:?MONGO_INITDB_DATABASE is not set}"
: "${MONGO_INITDB_ROOT_USERNAME:?MONGO_INITDB_ROOT_USERNAME is not set}"
: "${MONGO_INITDB_ROOT_PASSWORD:?MONGO_INITDB_ROOT_PASSWORD is not set}"

ROOT_DB="${MONGO_INITDB_DATABASE}"
ROOT_USER="${MONGO_INITDB_ROOT_USERNAME}"
ROOT_PASS="${MONGO_INITDB_ROOT_PASSWORD}"

MONGOSH_BIN="${MONGOSH_BIN:-mongosh}"
RETRIES=60
SLEEP_SEC=1

function die { echo "❌ $*"; exit 1; }

# Ensure mongosh exists
if ! command -v "$MONGOSH_BIN" >/dev/null 2>&1; then
  die "mongosh not found. Install mongosh or set MONGOSH_BIN path."
fi

echo "⏳ Waiting for mongod at ${MONGO_HOST}:${MONGO_PORT}..."
for i in $(seq 1 $RETRIES); do
  if "$MONGOSH_BIN" --host "${MONGO_HOST}" --port "${MONGO_PORT}" --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
    echo "✅ MongoDB is reachable"
    break
  fi
  if [ "$i" -eq "$RETRIES" ]; then
    die "MongoDB did not become ready in time."
  fi
  sleep "$SLEEP_SEC"
done

# Helper to run JS on a DB
function run_js() {
  local db="$1"; shift
  local js="$*"
  "$MONGOSH_BIN" --host "${MONGO_HOST}" --port "${MONGO_PORT}" "${db}" --eval "${js}"
}

echo "⚙️ Checking if root user '${ROOT_USER}' exists in ${ROOT_DB}..."
if run_js "${ROOT_DB}" "printjson(db.getSiblingDB('${ROOT_DB}').getUser('${ROOT_USER}'))" | grep -q null; then
  echo "ℹ️ Root user missing — creating..."
  if run_js "${ROOT_DB}" "db.getSiblingDB('${ROOT_DB}').createUser({user:'${ROOT_USER}', pwd:'${ROOT_PASS}', roles:[{role:'root', db:'${ROOT_DB}'}]});" >/dev/null 2>&1; then
    echo "✅ Root user created"
  else
    die "Failed to create root user"
  fi
else
  echo "ℹ️ Root user already exists"
fi

echo "🔐 Testing root authentication..."
if run_js "${ROOT_DB}" "db.auth('${ROOT_USER}','${ROOT_PASS}'); print(db.runCommand({connectionStatus:1}).ok);" | grep -q "1"; then
  echo "✅ Root authentication successful"
else
  die "❌ Root authentication failed with provided credentials"
fi

echo "🎉 MongoDB admin initialization complete."
