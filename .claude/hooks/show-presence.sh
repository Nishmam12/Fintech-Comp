#!/usr/bin/env bash
# SessionStart: show the team's current claims from origin/main (falls back to local copy).
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
git fetch -q origin main 2>/dev/null
echo "=== Team presence (memory/WHO_IS_WORKING.md, origin/main) ==="
echo "git user: $(git config user.name)"
(git show origin/main:memory/WHO_IS_WORKING.md 2>/dev/null || cat memory/WHO_IS_WORKING.md) \
  | sed -n '/^## Active now/,/^## Protocol/p' | grep -E '^### |Status:|Task ID:|Branch:|Claimed areas'
exit 0
