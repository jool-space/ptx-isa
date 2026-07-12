#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "beautifulsoup4",
#   "html2text",
#   "requests",
# ]
# ///
"""Convert the NVIDIA PTX ISA specification to a tree of markdown files.

The spec is published as a single multi-megabyte HTML page, one per CUDA
release. This splits it by section into one file per leaf section, grouped into
a directory per chapter, and emits the result as a ready-to-use skill directory.

    ./scrape.py                        # current PTX ISA
    ./scrape.py --cuda-version 13.0.0  # PTX ISA as shipped with CUDA 13.0.0
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import html2text
import requests
from bs4 import BeautifulSoup, Tag

LATEST_URL = "https://docs.nvidia.com/cuda/parallel-thread-execution/"
ARCHIVE_URL = "https://docs.nvidia.com/cuda/archive/{version}/parallel-thread-execution/"

HEADINGS = ["h1", "h2", "h3", "h4"]


@dataclass
class Section:
    """One numbered section of the spec, e.g. "9.7.1 Integer Arithmetic"."""

    number: str  # "9.7.1", or "" for unnumbered front/back matter
    title: str
    level: int  # 0 for chapters (h1), 1 for h2, ...
    body: list[Tag] = field(default_factory=list)

    @property
    def is_chapter(self) -> bool:
        return self.level == 0


def slugify(title: str, number: str = "") -> str:
    """Turn a section title into a filename stem, prefixed with its number."""
    name = re.sub(r"^\d+(\.\d+)*\.?\s*", "", title)  # leading section number
    name = re.sub(r"[^\w\s\-_.]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.lower().strip("-.")
    name = name or "section"
    return f"{number}-{name}" if number else name


class PTXScraper:
    def __init__(self, base_url: str, out_dir: Path, skill_dir: Path, images: bool = True):
        self.base_url = base_url
        self.out_dir = out_dir
        self.skill_dir = skill_dir
        self.images = images

        self.session = requests.Session()
        self.session.headers["User-Agent"] = "ptx-isa/1.0 (+https://github.com/jool-space/ptx-isa)"

        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0
        self.h2t.unicode_snob = True
        self.h2t.decode_errors = "ignore"
        for opt in ("ignore_links", "ignore_images", "ignore_emphasis"):
            setattr(self.h2t, opt, False)

    # -- fetch ---------------------------------------------------------------

    def fetch(self) -> BeautifulSoup:
        url = urljoin(self.base_url, "index.html")
        print(f"Fetching {url}")
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        print(f"  {len(response.content):,} bytes")
        return BeautifulSoup(response.content, "html.parser")

    def main_content(self, soup: BeautifulSoup) -> Tag:
        """Locate the article body, excluding site chrome.

        NVIDIA has changed this markup before. Falling back to <body> would
        silently pull the entire navigation sidebar into every file, so a miss
        is a hard error rather than a degraded result.
        """
        for tag, attrs in [
            ("div", {"role": "main"}),
            ("section", {"role": "main"}),
            ("article", {"id": "contents"}),
            ("div", {"class": "document"}),
            ("div", {"itemprop": "articleBody"}),
        ]:
            content = soup.find(tag, attrs)
            if content:
                return content
        raise SystemExit(
            "Could not locate the main content element. NVIDIA has likely "
            "restructured the page; update PTXScraper.main_content."
        )

    # -- parse ---------------------------------------------------------------

    def sections(self, content: Tag) -> list[Section]:
        """Split the page into sections, one per heading.

        Headings live inside nested <section> elements, so a section's body runs
        from its heading up to the first sibling that *contains* a heading --
        that sibling is the start of its subsections, which are emitted as their
        own files rather than duplicated into the parent.
        """
        sections = []
        for heading in content.find_all(HEADINGS):
            for anchor in heading.find_all(class_="headerlink"):
                anchor.decompose()
            # Headings render as "9.7.1." + title in separate spans, with a
            # private-use glyph for the anchor icon.
            text = re.sub(r"[\uf000-\uf8ff]", "", heading.get_text(" ", strip=True))
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue

            match = re.match(r"^(\d+(?:\.\d+)*)\.\s*(.+)$", text)
            number, title = (match.group(1), match.group(2)) if match else ("", text)
            section = Section(
                number=number,
                title=title,
                level=int(heading.name[1]) - 1,
            )

            node = heading.next_sibling
            while node:
                if isinstance(node, Tag):
                    if node.name in HEADINGS or node.find(HEADINGS):
                        break
                    section.body.append(node)
                node = node.next_sibling

            sections.append(section)
        return sections

    def to_markdown(self, section: Section) -> str:
        heading = "#" * (section.level + 1)
        title = f"{section.number}. {section.title}" if section.number else section.title
        parts = [f"{heading} {title}\n"]

        for element in section.body:
            element = element.__copy__()
            for cls in ("headerlink", "viewcode-link", "navigation", "related"):
                for unwanted in element.find_all(class_=cls):
                    unwanted.decompose()
            for img in element.find_all("img"):
                src = img.get("src")
                if src and not src.startswith(("http://", "https://")):
                    img["src"] = urljoin(self.base_url, src)
            markdown = self.h2t.handle(str(element))
            if markdown.strip():
                parts.append(markdown)

        return re.sub(r"\n{4,}", "\n\n\n", "\n\n".join(parts)).strip() + "\n"

    def localize_images(self, files: list[Path], docs_dir: Path) -> None:
        """Download the spec's diagrams and point the markdown at local copies.

        The figures are load-bearing -- register fragment layouts, swizzling
        modes -- so a clone has to carry them. Linking to the CDN instead would
        leave the tree unreadable offline and unusable to anything that cannot
        follow a URL.
        """
        pattern = re.compile(r"https://docs\.nvidia\.com/[^)\s]*/_images/([^)\s]+)")
        urls: dict[str, str] = {}  # filename -> url
        for path in files:
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                urls[match.group(1)] = match.group(0)

        if not urls:
            return

        images_dir = docs_dir / "_images"
        images_dir.mkdir(exist_ok=True)

        print(f"Downloading {len(urls)} images")
        failed = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(self.download, url, images_dir / name): name
                for name, url in urls.items()
            }
            for future in as_completed(futures):
                if not future.result():
                    failed.append(futures[future])
        if failed:
            raise SystemExit(f"Failed to download {len(failed)} images: {failed[:5]}")

        for path in files:
            text = path.read_text(encoding="utf-8")
            relative = os.path.relpath(images_dir, path.parent)
            text = pattern.sub(lambda m: f"{relative}/{m.group(1)}", text)
            path.write_text(text, encoding="utf-8")

        total = sum(f.stat().st_size for f in images_dir.iterdir())
        print(f"  {len(urls)} images, {total / 1e6:.1f} MB")

    def download(self, url: str, path: Path) -> bool:
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            path.write_bytes(response.content)
            return True
        except Exception as error:
            print(f"  ! {url}: {error}")
            return False

    def ptx_version(self, sections: list[Section]) -> str:
        """Read the ISA version out of the spec itself (section 1.3)."""
        for section in sections:
            match = re.match(r"PTX ISA Version (\d+\.\d+)$", section.title, re.I)
            if match:
                return match.group(1)
        raise SystemExit("Could not determine the PTX ISA version from the page.")

    # -- emit ----------------------------------------------------------------

    def run(self, cuda_version: str | None) -> str:
        soup = self.fetch()
        sections = self.sections(self.main_content(soup))
        print(f"Parsed {len(sections)} sections")

        version = self.ptx_version(sections)
        print(f"PTX ISA version {version}")

        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        docs_dir = self.out_dir / "ptx"
        docs_dir.mkdir(parents=True)

        written: list[tuple[Section, Path]] = []
        chapter_dir = docs_dir
        skipping = False
        for section in sections:
            if section.is_chapter:
                # The trailing "Notices" chapter is legal boilerplate; drop it
                # and everything under it.
                skipping = "notice" in section.title.lower()
                if not skipping:
                    chapter_dir = docs_dir / slugify(section.title, section.number)
                    chapter_dir.mkdir(parents=True, exist_ok=True)
            if skipping:
                continue

            path = chapter_dir / f"{slugify(section.title, section.number)}.md"
            path.write_text(self.to_markdown(section), encoding="utf-8")
            written.append((section, path))

        if self.images:
            self.localize_images([path for _, path in written], docs_dir)

        print(f"Wrote {len(written)} files to {docs_dir}")

        self.write_index(written, version)
        self.write_manifest(version, cuda_version)
        self.write_skill(version, len(written))
        return version

    def write_index(self, written: list[tuple[Section, Path]], version: str) -> None:
        lines = [
            f"# PTX ISA {version} — Index\n",
            "Every section of the specification, in document order.\n",
        ]
        for section, path in written:
            rel = path.relative_to(self.out_dir)
            number = f"{section.number}. " if section.number else ""
            indent = "  " * section.level
            lines.append(f"{indent}- [{number}{section.title}]({rel})")
        (self.out_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_manifest(self, version: str, cuda_version: str | None) -> None:
        manifest = {
            "ptx_isa_version": version,
            "cuda_version": cuda_version or "latest",
            "source": urljoin(self.base_url, "index.html"),
        }
        (self.out_dir / "VERSION.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def write_skill(self, version: str, file_count: int) -> None:
        """Copy the skill template in, substituting the version it describes."""
        for source in sorted(self.skill_dir.rglob("*")):
            if source.is_dir():
                continue
            text = source.read_text(encoding="utf-8")
            text = text.replace("{{PTX_VERSION}}", version)
            text = text.replace("{{FILE_COUNT}}", str(file_count))
            destination = self.out_dir / source.relative_to(self.skill_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cuda-version",
        help="Build from the docs archived for this CUDA release (e.g. 13.0.0). "
        "Defaults to the current published spec.",
    )
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument("--skill", type=Path, default=Path("skill"))
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Leave figures pointing at NVIDIA's CDN instead of downloading them.",
    )
    args = parser.parse_args()

    base_url = (
        ARCHIVE_URL.format(version=args.cuda_version) if args.cuda_version else LATEST_URL
    )
    scraper = PTXScraper(base_url, args.out, args.skill, images=not args.no_images)
    version = scraper.run(args.cuda_version)
    print(f"\nBuilt PTX ISA {version} at {args.out}")


if __name__ == "__main__":
    main()
