#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CURRENT_MONTH="$(date +%Y-%m)"
STAMP_DIR=".update-stamps"
STAMP_FILE="$STAMP_DIR/monthly-github-push.txt"
mkdir -p "$STAMP_DIR"

if [[ -f "$STAMP_FILE" ]] && grep -qx "$CURRENT_MONTH" "$STAMP_FILE"; then
  echo "Monthly update already pushed for $CURRENT_MONTH. Skip."
  exit 0
fi

python3 scripts/run_monthly_update.py

git add reports data/manual data/housing_cycle.sqlite scripts README.md requirements.txt .github .gitignore GITHUB_*.md

if git diff --cached --quiet; then
  echo "No changes after monthly update. Marking $CURRENT_MONTH as checked."
  echo "$CURRENT_MONTH" > "$STAMP_FILE"
  exit 0
fi

git commit -m "monthly housing-cycle update $CURRENT_MONTH"
git push

echo "$CURRENT_MONTH" > "$STAMP_FILE"
echo "Monthly update pushed for $CURRENT_MONTH."
