# ptx-isa

The [NVIDIA PTX ISA specification](https://docs.nvidia.com/cuda/parallel-thread-execution/)
as a tree of markdown files, one per section, versioned in git.

NVIDIA publishes the spec as a single 3.5 MB HTML page. That is fine to Ctrl+F
and hopeless to grep, cite, or diff. This repository turns each ISA release into
a directory of ~485 markdown files that a person — or an agent — can search:

```bash
grep -rl 'cp.async.bulk.tensor' ptx/
find ptx -name '9.7.4.3-*'          # cite a section, open the file
git diff v9.2.0 v9.3.0              # what changed in the ISA itself
```

Built for [PTX.jl](https://github.com/jool-space/PTX.jl), useful anywhere PTX is
written or generated.

## Using it

Every ISA version is a tag on the `docs` branch. Clone the one you need:

```bash
git clone --branch v9.3.0 --depth 1 https://github.com/jool-space/ptx-isa
```

The tree doubles as a [Claude Code](https://claude.com/claude-code) skill —
`SKILL.md` at the root teaches an agent how to navigate the spec, so it looks
instructions up instead of recalling them:

```bash
git clone --branch v9.3.0 --depth 1 https://github.com/jool-space/ptx-isa ~/.claude/skills/ptx-isa
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
```

Tags are `v<major>.<minor>.<build>`: `v9.3.0` is the first build of PTX ISA 9.3,
`v9.3.1` a rebuild of the same ISA version (NVIDIA revises pages in place). The
ISA has never used a third version component, so this cannot collide with an
upstream version.

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
