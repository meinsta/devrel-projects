#!/usr/bin/env bash
# CAGE test v2: enforcement loop active
#
# the key difference from v1: the caged agent is told to COMMIT its work.
# pre-commit hooks catch violations and force the agent to fix them.
# the uncaged agent just edits files with no enforcement.
#
# usage: ./run-test-v2.sh <task-number|all>

set -uo pipefail

CAGE_DIR="/Users/thierrydamiba/cage"
AUDIT="$CAGE_DIR/test/cage-test/audit.sh"
BASELINE="/tmp/cage-test-project"
RESULTS_DIR="$CAGE_DIR/test/cage-test/results-v2"
CAGE_CORE="$CAGE_DIR/core/dist/cage-core"

mkdir -p "$RESULTS_DIR"

TASK_PROMPTS=(
  ""
  "Add a 'hackathon' event type to the system. It should be selectable when creating events and displayed in the event list."
  "Create a GET /api/events/:id/attendees endpoint that returns the list of confirmed attendees for an event. Consume it in the frontend with a new useAttendees hook."
  "Add email validation for RSVPs. Validate email format before creating the RSVP. Add validation on both backend and frontend."
  "Rename the 'status' field in RSVPs to 'rsvpStatus' for clarity across the API response."
  "Before accepting an RSVP, check if the event has reached its maxAttendees limit. Reject with a 400 error if full."
  "Add a utility function that formats event dates as 'March 21, 2026' format. Use it in the EventList component."
  "Allow users to cancel their RSVP. Add a DELETE /api/events/:id/rsvps/:rsvpId endpoint. Add a 'cancelled' status to the RSVP status values."
  "Add a search endpoint GET /api/events/search?q=query that searches events by title. Add a SearchBar component in the frontend that uses this endpoint."
  "Only organizers and admins should be able to create events. Add middleware that checks the user role before allowing event creation."
  "Add a GET /api/events/:id/analytics endpoint that returns attendee count, RSVP conversion rate, and most common RSVP status. Display it in a new EventAnalytics component."
)

setup_pre_commit_checks() {
  local PROJECT_DIR="$1"

  # create a pre-commit hook that runs cage checks
  mkdir -p "$PROJECT_DIR/.git/hooks"
  cat > "$PROJECT_DIR/.git/hooks/pre-commit" << 'HOOKEOF'
#!/usr/bin/env bash
set -e

CAGE_CORE="/Users/thierrydamiba/cage/core/dist/cage-core"
ERRORS=0

echo "=== cage pre-commit checks ==="

# 1. contract sync: validate JSON
echo "checking contracts..."
$CAGE_CORE contract validate shared 2>&1 | grep -E "FAIL|ok" || true

# 2. hardcoded value detection
echo "checking for hardcoded domain values..."
if [ -f shared/domain-values.json ]; then
  # extract all string values from domain-values
  VALUES=$(python3 -c "
import json
def extract(obj):
    if isinstance(obj, str) and len(obj) > 2: print(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): extract(v)
with open('shared/domain-values.json') as f:
    d = json.load(f)
extract(d.get('values', d))
" 2>/dev/null)

  while IFS= read -r val; do
    [ -z "$val" ] && continue
    # check staged files for hardcoded values
    MATCHES=$(git diff --cached --name-only | xargs grep -l "\"$val\"\|'$val'" 2>/dev/null | grep -v shared/ | grep -v node_modules || true)
    if [ -n "$MATCHES" ]; then
      echo "FAIL: hardcoded value \"$val\" found in: $MATCHES"
      echo "  fix: import from shared/domain-values.json"
      ERRORS=$((ERRORS + 1))
    fi
  done <<< "$VALUES"
fi

# 3. API snapshot coverage
echo "checking API snapshot coverage..."
if [ -f shared/api-field-snapshots.json ]; then
  # count router endpoints in staged files
  STAGED_FILES=$(git diff --cached --name-only | grep -E "\.ts$|\.tsx$" || true)
  if [ -n "$STAGED_FILES" ]; then
    NEW_ENDPOINTS=$(echo "$STAGED_FILES" | xargs grep -c "router\.\(get\|post\|put\|delete\|patch\)" 2>/dev/null | grep -v ":0$" || true)
    SNAPSHOT_COUNT=$(python3 -c "import json; print(len(json.load(open('shared/api-field-snapshots.json')).get('endpoints',{})))" 2>/dev/null || echo 0)

    if [ -n "$NEW_ENDPOINTS" ]; then
      # check if api-field-snapshots.json is also staged
      if ! git diff --cached --name-only | grep -q "api-field-snapshots.json"; then
        echo "FAIL: new endpoints detected but shared/api-field-snapshots.json not updated"
        echo "  files with endpoints: $NEW_ENDPOINTS"
        echo "  fix: add endpoint shapes to shared/api-field-snapshots.json"
        ERRORS=$((ERRORS + 1))
      fi
    fi
  fi
fi

# 4. boundary enforcement
echo "checking service boundaries..."
STAGED_TS=$(git diff --cached --name-only | grep -E "\.ts$|\.tsx$" || true)
if [ -n "$STAGED_TS" ]; then
  for f in $STAGED_TS; do
    if echo "$f" | grep -q "^backend/"; then
      if git diff --cached -- "$f" | grep -q "from.*\.\./frontend\|from.*\.\./frontend"; then
        echo "FAIL: $f imports from frontend (cross-service boundary violation)"
        ERRORS=$((ERRORS + 1))
      fi
    fi
    if echo "$f" | grep -q "^frontend/"; then
      if git diff --cached -- "$f" | grep -q "from.*\.\./backend\|from.*\.\./backend"; then
        echo "FAIL: $f imports from backend (cross-service boundary violation)"
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done
fi

# 5. import centralization
echo "checking import centralization..."
if [ -d lib ] && [ -n "$STAGED_TS" ]; then
  for f in $STAGED_TS; do
    [ "$f" = "lib/api-client.ts" ] && continue
    if git diff --cached -- "$f" | grep -qE "from ['\"]axios['\"]|require\(['\"]axios['\"]|from ['\"]node-fetch['\"]"; then
      echo "FAIL: $f imports HTTP client directly. use lib/api-client.ts"
      ERRORS=$((ERRORS + 1))
    fi
  done
fi

echo ""
if [ $ERRORS -gt 0 ]; then
  echo "=== $ERRORS violation(s) found. commit rejected. ==="
  echo "fix the violations and try again."
  exit 1
else
  echo "=== all checks passed ==="
fi
HOOKEOF
  chmod +x "$PROJECT_DIR/.git/hooks/pre-commit"
}

run_task() {
  local TASK_NUM="$1"
  local PROMPT="${TASK_PROMPTS[$TASK_NUM]}"

  echo "============================================"
  echo "  TASK $TASK_NUM (v2: enforcement loop)"
  echo "  $PROMPT"
  echo "============================================"
  echo ""

  local UNCAGED="/tmp/cage-test-v2-uncaged-$TASK_NUM"
  local CAGED="/tmp/cage-test-v2-caged-$TASK_NUM"

  rm -rf "$UNCAGED" "$CAGED"
  cp -r "$BASELINE" "$UNCAGED"
  cp -r "$BASELINE" "$CAGED"

  # uncaged: remove CAGE artifacts, no hooks
  rm -rf "$UNCAGED/CLAUDE.md" "$UNCAGED/AGENTS.md" "$UNCAGED/cage.rules" \
    "$UNCAGED/.pre-commit-config.yaml" "$UNCAGED/cage-infra.yaml" "$UNCAGED/.cage"

  # caged: install enforcement hooks
  setup_pre_commit_checks "$CAGED"

  echo "--- UNCAGED AGENT (task $TASK_NUM) ---"
  echo ""

  # uncaged: just edit files, no enforcement
  claude -p "$PROMPT

Work in the project at $UNCAGED. Make all necessary changes to implement this feature.
Do not ask questions, just implement it." \
    --max-turns 15 --output-format text \
    --add-dir "$UNCAGED" \
    --dangerously-skip-permissions \
    2>/dev/null || echo "(agent finished)"

  echo ""
  echo "--- CAGED AGENT (task $TASK_NUM) ---"
  echo ""

  # caged: the agent must commit its work. pre-commit hooks enforce the cage.
  # if the commit is rejected, the agent must fix the violations and retry.
  claude -p "$PROMPT

Work in the project at $CAGED. This project uses CAGE. Read CLAUDE.md first.

After implementing the feature, you MUST commit your changes:
  cd $CAGED
  git add -A
  git commit -m 'implement feature'

The project has pre-commit hooks that enforce architectural rules:
- Domain values must be in shared/domain-values.json (not hardcoded)
- New API endpoints must be documented in shared/api-field-snapshots.json
- No cross-service imports (backend cannot import from frontend)
- HTTP calls must go through lib/api-client.ts

If the commit is rejected, read the error message, fix the violations, and commit again.
Keep trying until the commit succeeds. This is the most important part.

Rules from CLAUDE.md:
- All domain values must be in shared/domain-values.json, never hardcoded
- All API response shapes must be in shared/api-field-snapshots.json
- All HTTP calls must go through lib/api-client.ts, never raw fetch/axios
- No cross-service imports
- Shared logic goes in shared/ or lib/, not duplicated" \
    --max-turns 25 --output-format text \
    --add-dir "$CAGED" \
    --dangerously-skip-permissions \
    2>/dev/null || echo "(agent finished)"

  echo ""
  echo "============================================"
  echo "  AUDITING TASK $TASK_NUM"
  echo "============================================"
  echo ""

  echo "--- UNCAGED AUDIT ---"
  bash "$AUDIT" "$UNCAGED" 2>/dev/null | tee "$RESULTS_DIR/uncaged-task-$TASK_NUM.txt"

  echo ""
  echo "--- CAGED AUDIT ---"
  bash "$AUDIT" "$CAGED" 2>/dev/null | tee "$RESULTS_DIR/caged-task-$TASK_NUM.txt"

  # comparison
  UNCAGED_JSON=$(tail -1 "$RESULTS_DIR/uncaged-task-$TASK_NUM.txt")
  CAGED_JSON=$(tail -1 "$RESULTS_DIR/caged-task-$TASK_NUM.txt")

  UNCAGED_V=$(echo "$UNCAGED_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "?")
  CAGED_V=$(echo "$CAGED_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "?")

  echo ""
  echo "============================================"
  echo "  TASK $TASK_NUM COMPARISON"
  echo "============================================"
  echo "  uncaged violations: $UNCAGED_V"
  echo "  caged violations:   $CAGED_V"

  if [ "$CAGED_V" -lt "$UNCAGED_V" ] 2>/dev/null; then
    echo "  CAGE WINS"
  elif [ "$CAGED_V" -eq "$UNCAGED_V" ] 2>/dev/null; then
    echo "  TIE"
  else
    echo "  CAGE LOST"
  fi
  echo ""
}

# main
TASK="${1:-1}"

if [ "$TASK" = "all" ]; then
  for i in $(seq 1 10); do
    run_task "$i"
  done

  echo ""
  echo "============================================"
  echo "  FINAL RESULTS (v2: enforcement loop)"
  echo "============================================"
  echo ""

  TOTAL_UNCAGED=0
  TOTAL_CAGED=0
  CAGE_WINS=0
  CAGE_LOSSES=0

  for i in $(seq 1 10); do
    U=$(tail -1 "$RESULTS_DIR/uncaged-task-$i.txt" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "0")
    C=$(tail -1 "$RESULTS_DIR/caged-task-$i.txt" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "0")
    TOTAL_UNCAGED=$((TOTAL_UNCAGED + U))
    TOTAL_CAGED=$((TOTAL_CAGED + C))
    RESULT="TIE"
    if [ "$C" -lt "$U" ] 2>/dev/null; then
      CAGE_WINS=$((CAGE_WINS + 1))
      RESULT="CAGE"
    elif [ "$C" -gt "$U" ] 2>/dev/null; then
      CAGE_LOSSES=$((CAGE_LOSSES + 1))
      RESULT="LOST"
    fi
    printf "  task %2d: uncaged=%d caged=%d %s\n" "$i" "$U" "$C" "$RESULT"
  done

  REDUCTION=0
  if [ $TOTAL_UNCAGED -gt 0 ]; then
    REDUCTION=$(( (TOTAL_UNCAGED - TOTAL_CAGED) * 100 / TOTAL_UNCAGED ))
  fi

  echo ""
  echo "  total uncaged: $TOTAL_UNCAGED"
  echo "  total caged:   $TOTAL_CAGED"
  echo "  reduction:     ${REDUCTION}%"
  echo "  wins/ties/losses: $CAGE_WINS / $((10 - CAGE_WINS - CAGE_LOSSES)) / $CAGE_LOSSES"
  echo ""

  if [ "$TOTAL_CAGED" -lt "$TOTAL_UNCAGED" ] && [ "$CAGE_LOSSES" -eq 0 ]; then
    echo "  CAGE PASSES: fewer violations, zero losses"
  elif [ "$TOTAL_CAGED" -lt "$TOTAL_UNCAGED" ]; then
    echo "  CAGE PASSES (with concerns): fewer total but lost $CAGE_LOSSES tasks"
  else
    echo "  CAGE FAILS"
  fi
else
  run_task "$TASK"
fi
