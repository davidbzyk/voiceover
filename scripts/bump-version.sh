#!/usr/bin/env bash
# Bump version across all three config files simultaneously.
# Usage: ./scripts/bump-version.sh 0.2.0

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

VERSION="$1"

# Validate semver format
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
    echo "Error: '$VERSION' is not a valid semver (expected X.Y.Z or X.Y.Z-pre.N)"
    exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 1. package.json
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/package.json"

# 2. Cargo.toml (only the package version, line 3)
sed -i '' "3s/version = \"[^\"]*\"/version = \"$VERSION\"/" "$ROOT/src-tauri/Cargo.toml"

# 3. tauri.conf.json
sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$ROOT/src-tauri/tauri.conf.json"

echo "Bumped to $VERSION in:"
echo "  package.json"
echo "  src-tauri/Cargo.toml"
echo "  src-tauri/tauri.conf.json"

# Show the changes
grep -n "\"version\"" "$ROOT/package.json" | head -1
grep -n "^version" "$ROOT/src-tauri/Cargo.toml" | head -1
grep -n "\"version\"" "$ROOT/src-tauri/tauri.conf.json" | head -1
