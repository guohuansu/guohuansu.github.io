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
from pdf_library import match_publication_pdfs
from author_metadata import apply_author_metadata

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
    apply_author_metadata(works)

    overrides = load_updater_literal("PDF_OVERRIDES")
    files, unused = match_publication_pdfs(works, PDF_DIR, overrides)

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
