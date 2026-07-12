# ptx-isa

The [NVIDIA PTX ISA specification](https://docs.nvidia.com/cuda/parallel-thread-execution/)
as a tree of markdown files, one per section, versioned in git.

NVIDIA publishes the spec as a single 3.5 MB HTML page. That is fine to Ctrl+F
and hopeless to grep, cite, or diff. This repository turns each ISA release into
a directory of ~485 markdown files that a person — or an agent — can search:

```bash
grep -rl 'cp.async.bulk.tensor' ptx/
find ptx -name '9.7.4.3-*'          # cite a section, open the file
git diff v9.2 v9.3                  # what changed in the ISA itself
```

Built for [PTX.jl](https://github.com/jool-space/PTX.jl), useful anywhere PTX is
written or generated.

## Using it

Every ISA version is a tag on the `docs` branch. Clone the one you need:

```bash
git clone --branch v9.3 --depth 1 https://github.com/jool-space/ptx-isa
```

The tree doubles as a [Claude Code](https://claude.com/claude-code) skill —
`SKILL.md` at the root teaches an agent how to navigate the spec, so it looks
instructions up instead of recalling them:

```bash
git clone --branch v9.3 --depth 1 https://github.com/jool-space/ptx-isa ~/.claude/skills/ptx-isa
```

Releases carry the same tree as a tarball if you would rather not clone.

## Layout

`main` holds only the generator. Generated markdown lives on `docs`, an orphan
branch whose history is one commit per published build — which is what makes
`git diff` between two ISA versions meaningful.

```
main                    docs
├── scrape.py           ├── SKILL.md        agent entry point
├── validate.py         ├── INDEX.md        every section, in order
├── skill/              ├── VERSION.json    ISA version + source URL
└── .github/            └── ptx/            1-introduction/ ... 13-release-notes/
                            └── _images/    the spec's figures, 247 of them
```

Figures are downloaded and committed, not linked to NVIDIA's CDN. They are not
decoration — the `mma`/`wgmma` register fragment layouts, the TMA swizzling
modes, and the tensor memory maps exist only as diagrams, and a reference that
loses them loses the answer to the questions people actually ask it. It costs
~19 MB per version; git stores one blob per distinct figure, so all four
versions together pack to ~17 MB. Build with `--no-images` to link the CDN
instead.

There is **one tag per ISA version** — `v9.3`, not `v9.3.0` — and a tag moves if
a rebuild produces different content, which happens because NVIDIA revises
published pages in place. The point of a tag here is "the best copy of PTX ISA
9.3", not "a particular afternoon's scrape". Superseded builds are not lost:
`docs` is append-only, so every build stays reachable by commit.

The catch, and it is the only one: **git does not update existing tags on fetch.**
If you already have `v9.3` locally and it has since moved, you need

```bash
git fetch --tags --force
```

Fresh clones and release tarballs always get the current build.

## Building

```bash
./scrape.py                        # current spec -> dist/
./scrape.py --cuda-version 13.0.1  # the spec as it shipped with a past CUDA release
./validate.py dist
scripts/publish.sh dist            # commit to docs, tag, print the tag
```

`scrape.py` is a [uv script](https://docs.astral.sh/uv/guides/scripts/) — it
declares its own dependencies and needs no environment.

In CI, use the **Run workflow** button on the
[Build workflow](../../actions/workflows/build.yml). It scrapes, validates,
publishes, and cuts a release; `dry_run` builds and validates without publishing.
The weekly schedule is present but commented out.

## Why validation is the point

NVIDIA restructures this page without warning, and the failure mode is silent:
the scraper keeps emitting plausible-looking markdown that is wrong. Two real
examples, both caught only by eye:

- The content moved into `<article id="contents">`, so a selector fallback
  quietly wrapped every file in the site's navigation sidebar.
- Headings moved inside nested `<section>` elements, so every chapter file
  duplicated the full text of all its subsections — one file reached 1.1 MB.

`validate.py` fails the build on both, plus missing chapters, unsubstituted
template placeholders, site chrome leaking into a doc, any file over 100 KB, and
a total size that drifts more than 40% from the previously published tree. A
build that cannot find its content element is an error, never a fallback.

## Coverage

PTX ISA 9.0 through 9.3, from the CUDA documentation archive. Earlier versions
are reachable the same way (`--cuda-version 12.x`) but predate the current page
theme, so expect the scraper to need work — the validator will say so loudly.

## License

The specification is © NVIDIA Corporation, reproduced here in a different format
for searchability. The generator is MIT.
