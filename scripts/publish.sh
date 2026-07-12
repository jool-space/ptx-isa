#!/usr/bin/env bash
# Commit a built tree onto the docs branch and tag it.
#
# The docs branch is an orphan: its history is one commit per published ISA
# build, so `git diff v9.2.0 v9.3.0` is a changelog of the specification itself.
#
#   scripts/publish.sh [dist-dir]
#
# Tags are v<major>.<minor>.<build>, where build counts rebuilds of an unchanged
# ISA version (NVIDIA revises pages in place). Prints the tag it created; push
# with `git push origin docs --tags`.
set -euo pipefail

DIST="${1:-dist}"
BRANCH="docs"
ROOT="$(git rev-parse --show-toplevel)"
WORKTREE="$(mktemp -d)"

version="$(python3 -c "import json,sys; print(json.load(open('$DIST/VERSION.json'))['ptx_isa_version'])")"

build=0
while git rev-parse -q --verify "refs/tags/v${version}.${build}" >/dev/null; do
    build=$((build + 1))
done
tag="v${version}.${build}"

cleanup() { git worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"; }
trap cleanup EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add --quiet "$WORKTREE" "$BRANCH"
else
    git worktree add --quiet --detach "$WORKTREE"
    git -C "$WORKTREE" checkout --quiet --orphan "$BRANCH"
    git -C "$WORKTREE" rm -rqf . 2>/dev/null || true
fi

find "$WORKTREE" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -a "$ROOT/$DIST/." "$WORKTREE/"

git -C "$WORKTREE" add -A
if git -C "$WORKTREE" diff --cached --quiet; then
    echo "No change from the published tree; nothing to do."
    exit 0
fi

source_url="$(python3 -c "import json; print(json.load(open('$DIST/VERSION.json'))['source'])")"
git -C "$WORKTREE" commit --quiet -m "PTX ISA ${version} (build ${build})" -m "Source: ${source_url}"
git -C "$WORKTREE" tag -a "$tag" -m "PTX ISA ${version}"

echo "$tag"
