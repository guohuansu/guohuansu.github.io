"""Reattach local PDFs to the cached Google Scholar publication list.

Use this when the Scholar list is already current and only the contents of the
local ``pdf`` directory have changed. The regular updater remains responsible
for fetching new Scholar records.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import unicodedata
import urllib.parse
from datetime import date
from difflib import SequenceMatcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLICATIONS = ROOT / "data" / "publications.json"
AUTHOR_METADATA = ROOT / "data" / "publication-author-metadata.json"
AUTHOR_OVERRIDES = ROOT / "data" / "publication-author-overrides.json"
MISSING = ROOT / "data" / "missing-pdfs.md"
PDF_DIR = ROOT / "pdf"
UPDATER = ROOT / "scripts" / "update_publications.py"


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(19|20)\d{2}\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def load_updater_literal(name: str):
    tree = ast.parse(UPDATER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"{name} not found in update_publications.py")


def is_formal_journal_article(work: dict, markers: set[str]) -> bool:
    venue = work["venue"].strip().casefold()
    return bool(venue) and not any(marker in venue for marker in markers)


def main() -> None:
    data = json.loads(PUBLICATIONS.read_text(encoding="utf-8"))
    excluded_titles = load_updater_literal("EXCLUDED_TITLES")
    non_journal_markers = load_updater_literal("NON_JOURNAL_VENUE_MARKERS")
    works = [
        work
        for work in data["works"]
        if work["title"] not in excluded_titles
        and is_formal_journal_article(work, non_journal_markers)
    ]
    data["works"] = works
    author_metadata = json.loads(AUTHOR_METADATA.read_text(encoding="utf-8"))
    author_overrides = json.loads(AUTHOR_OVERRIDES.read_text(encoding="utf-8"))
    for work in works:
        work["authors"] = author_overrides.get(work["title"], work["authors"])
        work["corresponding_authors"] = author_metadata.get(work["title"], [])

    files = sorted(PDF_DIR.glob("*.pdf"))
    overrides = load_updater_literal("PDF_OVERRIDES")
    reserved = {PDF_DIR / name for name in overrides.values() if (PDF_DIR / name).exists()}
    unused = set(files) - reserved

    for work in works:
        override = overrides.get(work["title"])
        if override and (PDF_DIR / override).exists():
            work["pdf_url"] = "/pdf/" + urllib.parse.quote(override)
            continue
        title = normalize_title(work["title"])
        ranked = sorted(
            (
                (SequenceMatcher(None, title, normalize_title(path.stem)).ratio(), path)
                for path in unused
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if ranked and ranked[0][0] >= 0.56 and (
            len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08
        ):
            path = ranked[0][1]
            work["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.remove(path)
        else:
            work["pdf_url"] = None

    data["total_works"] = len(works)
    data["pdf_count"] = sum(bool(work["pdf_url"]) for work in works)
    PUBLICATIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Publications without a local PDF",
        "",
        f"Generated {date.today().isoformat()}. Add a PDF to `pdf/` and rerun the updater.",
    ]
    lines.extend(
        f"- {work['year']} - {work['title']}" for work in works if not work["pdf_url"]
    )
    if unused:
        lines.extend(["", "## Unmatched PDF files", ""])
        lines.extend(f"- {path.name}" for path in sorted(unused))
    MISSING.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Rematched {data['pdf_count']}/{len(works)} records to "
        f"{len(files)} local PDF files; {len(unused)} files unmatched"
    )


if __name__ == "__main__":
    main()
