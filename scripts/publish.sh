#!/usr/bin/env bash
# Commit a built tree onto the docs branch and tag it.
#
# The docs branch is an orphan and append-only: one commit per published build,
# so `git diff v9.2 v9.3` is a changelog of the specification itself.
#
#   scripts/publish.sh [dist-dir]
#
# There is one tag per ISA version. NVIDIA revises pages in place, so a rebuild
# of an already-published version moves its tag onto the new build; the previous
# build stays on the branch, reachable by commit. Prints the tag; push with
#
#   git push origin docs && git push --force origin <tag>
#
set -euo pipefail

DIST="${1:-dist}"
BRANCH="docs"
ROOT="$(git rev-parse --show-toplevel)"
WORKTREE="$(mktemp -d)"

read -r version source_url < <(
    python3 -c "import json; m=json.load(open('$DIST/VERSION.json')); print(m['ptx_isa_version'], m['source'])"
)
tag="v${version}"
existing="$(git rev-parse -q --verify "refs/tags/${tag}" || true)"

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

if [[ -n "$existing" ]]; then
    summary="Rebuild of PTX ISA ${version}"
else
    summary="PTX ISA ${version}"
fi

git -C "$WORKTREE" commit --quiet -m "$summary" -m "Source: ${source_url}"
git -C "$WORKTREE" tag --force --annotate "$tag" -m "PTX ISA ${version}" >/dev/null

echo "$tag"
