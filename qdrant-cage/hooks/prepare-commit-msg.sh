#!/usr/bin/env bash
# prepare-commit-msg hook: blocks merge commits on protected branches
# installed by cage setup into .git/hooks/prepare-commit-msg

COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

# only block merge commits
if [ "$COMMIT_SOURCE" = "merge" ]; then
  BRANCH=$(git branch --show-current 2>/dev/null)
  PROTECTED="main develop"

  for b in $PROTECTED; do
    if [ "$BRANCH" = "$b" ]; then
      echo "error: merge commits blocked on '$BRANCH' by CAGE" >&2
      echo "use 'cage merge <branch>' for safe squash merges" >&2
      exit 1
    fi
  done
fi

exit 0
