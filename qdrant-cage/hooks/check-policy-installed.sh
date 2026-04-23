#!/usr/bin/env bash
# Claude Code PreToolUse hook for cage execution policy enforcement
# uses cage-core for tokenized matching (no false positives)
#
# install in settings.json:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Bash",
#         "hooks": [{ "type": "command", "command": "CAGE_CORE_PATH/check-policy.sh" }]
#       }
#     ]
#   }
# }

# CAGE_CORE_BIN is set by cage setup (absolute path to cage-core binary)
CAGE_CORE_BIN="/Users/thierrydamiba/cage/core/dist/cage-core"

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null || echo "$INPUT" | node -e "
const chunks = [];
process.stdin.on('data', c => chunks.push(c));
process.stdin.on('end', () => {
  try {
    const d = JSON.parse(chunks.join(''));
    console.log(d.tool_input?.command || '');
  } catch { console.log(''); }
});
" 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

# use cage-core for tokenized policy check
if [ -x "$CAGE_CORE_BIN" ]; then
  RESULT=$("$CAGE_CORE_BIN" policy check "$COMMAND" 2>/dev/null)
  if [ -n "$RESULT" ]; then
    echo "$RESULT"
    exit 0
  fi
else
  # fallback: walk up to find cage-core or cage.rules
  DIR="$PWD"
  while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/cage.rules" ]; then
      # try cage-core on PATH
      if command -v cage-core &>/dev/null; then
        RESULT=$(cd "$DIR" && cage-core policy check "$COMMAND" 2>/dev/null)
        if [ -n "$RESULT" ]; then
          echo "$RESULT"
          exit 0
        fi
      fi
      break
    fi
    DIR="$(dirname "$DIR")"
  done
fi

exit 0
