#!/usr/bin/env bash
# cage test audit: scores a codebase on 8 metrics
# usage: ./audit.sh <project-dir>

set -uo pipefail

PROJECT="${1:-.}"
CAGE_CORE="/Users/thierrydamiba/cage/core/dist/cage-core"

cd "$PROJECT"

echo "========================================="
echo "  CAGE TEST AUDIT"
echo "  project: $(pwd)"
echo "========================================="
echo ""

TOTAL_VIOLATIONS=0

# --- 1. contract integrity ---
echo "## 1. CONTRACT INTEGRITY"
echo "   are domain values used from shared/, not hardcoded?"

# count hardcoded event types
HC_EVENTS=$(grep -rn '"hackathon"\|"conference"\|"workshop"\|"meetup"\|"webinar"' \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "shared/" | grep -v "domain-values" | grep -v "node_modules" | \
  grep -v "import" | wc -l | tr -d ' ')

# count hardcoded RSVP statuses
HC_STATUS=$(grep -rn '"confirmed"\|"pending"\|"declined"\|"waitlisted"\|"cancelled"' \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "shared/" | grep -v "domain-values" | grep -v "node_modules" | \
  grep -v "import" | wc -l | tr -d ' ')

# count hardcoded roles
HC_ROLES=$(grep -rn '"admin"\|"organizer"\|"attendee"' \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "shared/" | grep -v "domain-values" | grep -v "node_modules" | \
  grep -v "import" | wc -l | tr -d ' ')

HC_TOTAL=$((HC_EVENTS + HC_STATUS + HC_ROLES))
echo "   hardcoded values: $HC_TOTAL ($HC_EVENTS event types, $HC_STATUS statuses, $HC_ROLES roles)"
TOTAL_VIOLATIONS=$((TOTAL_VIOLATIONS + HC_TOTAL))

# --- 2. boundary integrity ---
echo ""
echo "## 2. BOUNDARY INTEGRITY"
echo "   any cross-service imports?"

BOUNDARY=$(grep -rn "from.*\.\./frontend\|from.*\.\./backend\|require.*\.\./frontend\|require.*\.\./backend" \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "shared/" | grep -v "node_modules" | wc -l | tr -d ' ')
echo "   cross-service imports: $BOUNDARY"
TOTAL_VIOLATIONS=$((TOTAL_VIOLATIONS + BOUNDARY))

# --- 3. API consistency ---
echo ""
echo "## 3. API CONSISTENCY"
echo "   are new endpoints in api-field-snapshots.json?"

# count endpoints in code vs snapshots
CODE_ENDPOINTS=$(grep -rn "router\.\(get\|post\|put\|delete\|patch\)" \
  backend/ --include="*.ts" 2>/dev/null | wc -l | tr -d ' ')
SNAPSHOT_ENDPOINTS=$(python3 -c "
import json
with open('shared/api-field-snapshots.json') as f:
    d = json.load(f)
print(len(d.get('endpoints', {})))
" 2>/dev/null || echo "0")

MISSING_SNAPSHOTS=$((CODE_ENDPOINTS - SNAPSHOT_ENDPOINTS))
if [ $MISSING_SNAPSHOTS -lt 0 ]; then MISSING_SNAPSHOTS=0; fi
echo "   code endpoints: $CODE_ENDPOINTS, snapshots: $SNAPSHOT_ENDPOINTS, undocumented: $MISSING_SNAPSHOTS"
TOTAL_VIOLATIONS=$((TOTAL_VIOLATIONS + MISSING_SNAPSHOTS))

# --- 4. code duplication ---
echo ""
echo "## 4. CODE DUPLICATION"
echo "   similar functions across services?"

# check if formatDate exists in both backend and frontend
DUP_FORMAT=$(grep -rln "function formatDate\|formatDate.*=.*(" \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l | tr -d ' ')
DUP_VALIDATE=$(grep -rln "function validateEmail\|validateEmail.*=.*(" \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l | tr -d ' ')

DUP_TOTAL=0
if [ "$DUP_FORMAT" -gt 1 ]; then
  echo "   formatDate duplicated across $DUP_FORMAT files"
  DUP_TOTAL=$((DUP_TOTAL + DUP_FORMAT - 1))
fi
if [ "$DUP_VALIDATE" -gt 1 ]; then
  echo "   validateEmail duplicated across $DUP_VALIDATE files"
  DUP_TOTAL=$((DUP_TOTAL + DUP_VALIDATE - 1))
fi
if [ "$DUP_TOTAL" -eq 0 ]; then
  echo "   no duplicated logic detected"
fi
TOTAL_VIOLATIONS=$((TOTAL_VIOLATIONS + DUP_TOTAL))

# --- 5. import hygiene ---
echo ""
echo "## 5. IMPORT HYGIENE"
echo "   are HTTP calls centralized through lib/api-client?"

DIRECT_HTTP=$(grep -rn "from .axios.\|require.*axios\|from .node-fetch." \
  frontend/ backend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "lib/api-client" | grep -v "node_modules" | wc -l | tr -d ' ')
DIRECT_FETCH=$(grep -rn "fetch(" \
  frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | \
  grep -v "lib/api-client" | grep -v "node_modules" | grep -v "useEffect" | wc -l | tr -d ' ')

IMPORT_TOTAL=$((DIRECT_HTTP + DIRECT_FETCH))
echo "   direct HTTP imports: $DIRECT_HTTP, raw fetch calls: $DIRECT_FETCH"
TOTAL_VIOLATIONS=$((TOTAL_VIOLATIONS + IMPORT_TOTAL))

# --- 6. domain values coverage ---
echo ""
echo "## 6. DOMAIN VALUES COVERAGE"
echo "   are new values in shared/domain-values.json?"

DOMAIN_EVENT_TYPES=$(python3 -c "
import json
with open('shared/domain-values.json') as f:
    d = json.load(f)
print(len(d.get('values', {}).get('eventTypes', {})))
" 2>/dev/null || echo "0")
DOMAIN_RSVP_STATUS=$(python3 -c "
import json
with open('shared/domain-values.json') as f:
    d = json.load(f)
print(len(d.get('values', {}).get('rsvpStatus', {})))
" 2>/dev/null || echo "0")

echo "   event types in contract: $DOMAIN_EVENT_TYPES"
echo "   rsvp statuses in contract: $DOMAIN_RSVP_STATUS"

# --- 7. doc freshness ---
echo ""
echo "## 7. DOC FRESHNESS"
echo "   were docs updated?"

DOC_FILES=$(find docs/ -name "*.md" -newer .git/index 2>/dev/null | wc -l | tr -d ' ')
echo "   recently modified doc files: $DOC_FILES"

# --- 8. regression check ---
echo ""
echo "## 8. REGRESSION CHECK"
echo "   do existing patterns still work?"

# check that existing imports from shared/ still work
SHARED_IMPORTS=$(grep -rn "from.*shared/domain-values\|from.*shared/api-field" \
  backend/ frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l | tr -d ' ')
echo "   shared/ imports still in place: $SHARED_IMPORTS"

# check that lib/api-client is still used
CLIENT_IMPORTS=$(grep -rn "from.*lib/api-client\|from.*api-client" \
  frontend/ --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l | tr -d ' ')
echo "   api-client imports: $CLIENT_IMPORTS"

# --- summary ---
echo ""
echo "========================================="
echo "  TOTAL VIOLATIONS: $TOTAL_VIOLATIONS"
echo "========================================="
echo ""

if [ $TOTAL_VIOLATIONS -eq 0 ]; then
  echo "  RESULT: CLEAN"
else
  echo "  RESULT: $TOTAL_VIOLATIONS violation(s) detected"
fi

# output JSON for comparison
echo ""
echo "--- JSON ---"
echo "{\"hardcoded_values\":$HC_TOTAL,\"boundary_crossings\":$BOUNDARY,\"missing_snapshots\":$MISSING_SNAPSHOTS,\"code_duplication\":$DUP_TOTAL,\"import_bypasses\":$IMPORT_TOTAL,\"domain_event_types\":$DOMAIN_EVENT_TYPES,\"domain_rsvp_statuses\":$DOMAIN_RSVP_STATUS,\"doc_changes\":$DOC_FILES,\"shared_imports\":$SHARED_IMPORTS,\"client_imports\":$CLIENT_IMPORTS,\"total_violations\":$TOTAL_VIOLATIONS}"
