#!/usr/bin/env bash
# Build the docs branch from scratch, oldest ISA version first.
#
# Each CUDA release archives the PTX spec as it shipped, so history can be
# reconstructed. These are the CUDA releases that introduced each ISA version;
# scrape.py reads the actual version out of the page, so a wrong guess here
# surfaces as a wrong tag rather than wrong content.
set -euo pipefail

CUDA_RELEASES=(
    13.0.1  # PTX ISA 9.0
    13.1.1  # PTX ISA 9.1
    13.2.1  # PTX ISA 9.2
)

# The current ISA version comes from the live docs rather than the archive, so
# that CI rebuilding it later is a no-op instead of a tag move: archived pages
# pin their image URLs under /archive/<release>/, which would otherwise be the
# only difference between the two builds.
build_and_publish() {
    if [[ -d previous ]]; then
        ./validate.py dist --baseline previous
    else
        ./validate.py dist
    fi
    scripts/publish.sh dist
    rm -rf previous && cp -a dist previous
}

rm -rf dist previous
for release in "${CUDA_RELEASES[@]}"; do
    echo
    echo "=== CUDA $release ==="
    ./scrape.py --cuda-version "$release" --out dist
    build_and_publish
done

echo
echo "=== current ==="
./scrape.py --out dist
build_and_publish

rm -rf previous
echo
echo "Done. Review with: git log --oneline docs && git tag"
