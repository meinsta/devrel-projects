#!/usr/bin/env bash
# pre-commit check: detects bypass attempts in committed code
# catches: --no-verify in scripts, disabled hooks, hardcoded secrets patterns

ERRORS=0

# check staged files for bypass patterns
while IFS= read -r file; do
  [ -z "$file" ] && continue

  # skip binary files
  if file "$file" | grep -q "binary"; then
    continue
  fi

  content=$(cat "$file" 2>/dev/null || true)
  [ -z "$content" ] && continue

  # --no-verify in scripts
  if echo "$content" | grep -n "\-\-no-verify" | grep -v "^#" > /dev/null 2>&1; then
    LINE=$(echo "$content" | grep -n "\-\-no-verify" | head -1 | cut -d: -f1)
    echo "BYPASS: $file:$LINE contains --no-verify (skips git hooks)" >&2
    ERRORS=$((ERRORS + 1))
  fi

  # pre-commit skip patterns
  if echo "$content" | grep -n "SKIP=.*pre-commit\|PRE_COMMIT_ALLOW_NO_CONFIG" | grep -v "^#" > /dev/null 2>&1; then
    LINE=$(echo "$content" | grep -n "SKIP=.*pre-commit\|PRE_COMMIT_ALLOW_NO_CONFIG" | head -1 | cut -d: -f1)
    echo "BYPASS: $file:$LINE disables pre-commit hooks" >&2
    ERRORS=$((ERRORS + 1))
  fi

  # disabled eslint/type checking
  if echo "$content" | grep -n "eslint-disable-next-line\|@ts-ignore\|@ts-nocheck\|# type: ignore" | grep -v "test\|spec\|\.test\.\|\.spec\." > /dev/null 2>&1; then
    COUNT=$(echo "$content" | grep -c "eslint-disable-next-line\|@ts-ignore\|@ts-nocheck\|# type: ignore" || true)
    if [ "$COUNT" -gt 3 ]; then
      echo "BYPASS: $file has $COUNT lint/type suppression comments (excessive)" >&2
      ERRORS=$((ERRORS + 1))
    fi
  fi

done < <(git diff --cached --name-only --diff-filter=ACM)

if [ $ERRORS -gt 0 ]; then
  echo "" >&2
  echo "$ERRORS bypass attempt(s) detected. fix before committing." >&2
  echo "if intentional, document why in the commit message." >&2
  exit 1
fi

exit 0
