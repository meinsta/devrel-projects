#!/usr/bin/env bash
# the CAGE test: caged vs uncaged agent on the same tasks
#
# usage: ./run-test.sh <task-number>
#   runs one task against both uncaged and caged copies
#   audits both after completion
#
# usage: ./run-test.sh all
#   runs all 10 tasks sequentially

set -uo pipefail

CAGE_DIR="/Users/thierrydamiba/cage"
AUDIT="$CAGE_DIR/test/cage-test/audit.sh"
TASKS="$CAGE_DIR/test/cage-test/tasks.md"
BASELINE="/tmp/cage-test-project"
RESULTS_DIR="$CAGE_DIR/test/cage-test/results"

mkdir -p "$RESULTS_DIR"

TASK_PROMPTS=(
  ""  # index 0 unused
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

run_task() {
  local TASK_NUM="$1"
  local PROMPT="${TASK_PROMPTS[$TASK_NUM]}"

  echo "============================================"
  echo "  TASK $TASK_NUM"
  echo "  $PROMPT"
  echo "============================================"
  echo ""

  # create two copies of the baseline
  local UNCAGED="/tmp/cage-test-uncaged-$TASK_NUM"
  local CAGED="/tmp/cage-test-caged-$TASK_NUM"

  rm -rf "$UNCAGED" "$CAGED"
  cp -r "$BASELINE" "$UNCAGED"
  cp -r "$BASELINE" "$CAGED"

  # remove CAGE artifacts from uncaged copy
  rm -rf "$UNCAGED/CLAUDE.md" "$UNCAGED/AGENTS.md" "$UNCAGED/cage.rules" \
    "$UNCAGED/.pre-commit-config.yaml" "$UNCAGED/cage-infra.yaml" "$UNCAGED/.cage"

  echo "--- UNCAGED AGENT (task $TASK_NUM) ---"
  echo ""

  # run uncaged agent
  claude -p "$PROMPT

Work in the project at $UNCAGED. Make all necessary changes to implement this feature.
Do not ask questions, just implement it. Do not run any commands, just edit files." \
    --max-turns 15 --output-format text \
    --add-dir "$UNCAGED" \
    --dangerously-skip-permissions \
    2>/dev/null || echo "(agent finished)"

  echo ""
  echo "--- CAGED AGENT (task $TASK_NUM) ---"
  echo ""

  # run caged agent
  claude -p "$PROMPT

Work in the project at $CAGED. Make all necessary changes to implement this feature.
Do not ask questions, just implement it. Do not run any commands, just edit files.

IMPORTANT: Read CLAUDE.md first. This project uses CAGE. Follow the rules:
- All domain values must be in shared/domain-values.json, never hardcoded
- All API response shapes must be in shared/api-field-snapshots.json
- All HTTP calls must go through lib/api-client.ts, never raw fetch/axios
- No cross-service imports (backend cannot import from frontend or vice versa)
- Shared logic goes in shared/ or lib/, not duplicated across services
- Read cage.rules for blocked commands" \
    --max-turns 15 --output-format text \
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
  UNCAGED_JSON=$(tail -1 "$RESULTS_DIR/uncaged-task-$TASK_NUM.txt")

  echo ""
  echo "--- CAGED AUDIT ---"
  bash "$AUDIT" "$CAGED" 2>/dev/null | tee "$RESULTS_DIR/caged-task-$TASK_NUM.txt"
  CAGED_JSON=$(tail -1 "$RESULTS_DIR/caged-task-$TASK_NUM.txt")

  echo ""
  echo "============================================"
  echo "  TASK $TASK_NUM COMPARISON"
  echo "============================================"

  UNCAGED_V=$(echo "$UNCAGED_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "?")
  CAGED_V=$(echo "$CAGED_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "?")

  echo "  uncaged violations: $UNCAGED_V"
  echo "  caged violations:   $CAGED_V"

  if [ "$CAGED_V" -lt "$UNCAGED_V" ] 2>/dev/null; then
    echo "  CAGE WINS (fewer violations)"
  elif [ "$CAGED_V" -eq "$UNCAGED_V" ] 2>/dev/null; then
    echo "  TIE"
  else
    echo "  CAGE LOST (more violations than uncaged)"
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
  echo "  FINAL RESULTS"
  echo "============================================"
  echo ""

  TOTAL_UNCAGED=0
  TOTAL_CAGED=0
  CAGE_WINS=0

  for i in $(seq 1 10); do
    U=$(tail -1 "$RESULTS_DIR/uncaged-task-$i.txt" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "0")
    C=$(tail -1 "$RESULTS_DIR/caged-task-$i.txt" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['total_violations'])" 2>/dev/null || echo "0")
    TOTAL_UNCAGED=$((TOTAL_UNCAGED + U))
    TOTAL_CAGED=$((TOTAL_CAGED + C))
    if [ "$C" -lt "$U" ] 2>/dev/null; then
      CAGE_WINS=$((CAGE_WINS + 1))
    fi
    echo "  task $i: uncaged=$U caged=$C"
  done

  echo ""
  echo "  total uncaged violations: $TOTAL_UNCAGED"
  echo "  total caged violations:   $TOTAL_CAGED"
  echo "  cage won $CAGE_WINS / 10 tasks"
  echo ""

  if [ "$TOTAL_CAGED" -lt "$TOTAL_UNCAGED" ]; then
    echo "  CAGE PASSES: fewer total violations"
  else
    echo "  CAGE FAILS: did not reduce violations"
  fi
else
  run_task "$TASK"
fi
