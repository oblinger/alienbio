#!/usr/bin/env bash
# Deploy Alien Biology project page to oblinger.github.io
set -euo pipefail

WEBSITE_REPO="/Users/oblinger/ob/proj/oblinger.github.io"
SLUG="AlienBiology"
TARGET="$WEBSITE_REPO/gitproj/$SLUG"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying Alien Biology project page..."

# Copy index.md (splash page) to website repo
cp "$SCRIPT_DIR/index.md" "$TARGET/index.md"

echo "  Copied index.md to $TARGET/"

# Commit and push
cd "$WEBSITE_REPO"
git add "gitproj/$SLUG/index.md"

if git diff --cached --quiet; then
    echo "  No changes to deploy."
else
    git commit -m "Update Alien Biology project page"
    git push
    echo "  Pushed to GitHub."
fi

echo "Done: https://oblinger.github.io/gitproj/$SLUG/"
