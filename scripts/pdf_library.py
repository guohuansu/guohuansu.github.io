"""Shared PDF naming and exact matching for the local publication library."""
from __future__ import annotations

import json
import hashlib
import pathlib
import re
import unicodedata
import urllib.parse
from difflib import SequenceMatcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "pdf-library.json"


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", " ", value).strip()


def journal_name(venue: str) -> str:
    name = re.split(r",\s*(?:\d|e\d)|\s+\d+(?:\s*\(|\s*[,，]|$)", venue, maxsplit=1)[0].strip(" ,")
    return {"Plos one": "PLOS ONE", "Frontiers in plant science": "Frontiers in Plant Science", "Journal of ichthyology": "Journal of Ichthyology"}.get(name, name)


def safe_component(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " - ", value)
    value = value.replace("_", " ")
    return re.sub(r"\s+", " ", value).strip(" .")


def first_author_label(authors: str) -> str:
    names = [name.strip() for name in re.split(r"[,，]", authors) if name.strip()]
    first = names[0] if names else "Unknown"
    surname = {"沙永翠": "Sha", "沙泳翠": "Sha", "熊鹰": "Xiong", "苏国欢": "Su"}.get(first, first.split()[-1])
    return safe_component(surname) + (" et al" if len(names) > 1 else "")


def standard_filename(work: dict, suffix: str = "") -> str:
    prefix = f"{work['year']}_{first_author_label(work['authors'])}_"
    ending = "_" + safe_component(journal_name(work.get("venue", "")) or "Unknown source") + suffix + ".pdf"
    title = safe_component(work["title"])
    # Linux/GitHub limits each filename to 255 bytes; keep a small safety margin.
    budget = 240 - len((prefix + ending).encode("utf-8"))
    if budget < 16:
        raise ValueError("Author/source fields leave no room for the title")
    if len(title.encode("utf-8")) > budget:
        title = title.encode("utf-8")[:budget - 3].decode("utf-8", "ignore").rstrip(" .") + "..."
    return prefix + title + ending


def identity(work: dict) -> tuple:
    return normalise(work["title"]), work.get("year"), normalise(journal_name(work.get("venue", "")))


def is_correction(title: str) -> bool:
    return bool(re.match(r"\s*(corrigendum|erratum|correction)\b", title, re.I))


def scholar_id(url: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("citation_for_view", [""])[0]


def match_publication_pdfs(works: list[dict], pdf_dir: pathlib.Path, legacy: dict) -> tuple:
    files = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    indexed = {}
    by_scholar = {}
    for item in catalog:
        key = identity(item)
        if key not in indexed or item["filename"] == standard_filename(item):
            indexed[key] = item["filename"]
        citation = scholar_id(item.get("scholar_url", ""))
        if citation:
            by_scholar[citation] = item["filename"]
    reserved = {pdf_dir / item["filename"] for item in catalog}
    reserved.update(pdf_dir / name for name in legacy.values())
    unused = set(files) - reserved
    unmatched = []
    # Resolve ALL exact/catalog mappings before trying any fuzzy match. A
    # corrigendum must never consume the original paper's PDF.
    for work in works:
        candidates = [by_scholar.get(scholar_id(work.get("url", ""))), indexed.get(identity(work)), standard_filename(work), legacy.get(work["title"])]
        path = next((pdf_dir / name for name in candidates if name and (pdf_dir / name).is_file()), None)
        if path:
            work["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.discard(path)
        else:
            work["pdf_url"] = None
            unmatched.append(work)
    for work in unmatched:
        title = normalise(work["title"])
        candidates = [path for path in unused if is_correction(work["title"]) == bool(re.search(r"\b(corrigendum|erratum|correction)\b", path.stem, re.I))]
        ranked = sorted(((SequenceMatcher(None, title, normalise(path.stem)).ratio(), path) for path in candidates), reverse=True)
        if ranked and ranked[0][0] >= 0.56 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
            path = ranked[0][1]
            work["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.remove(path)
    return files, unused


def register_pdf(work: dict, path: pathlib.Path) -> None:
    """Keep the inventory current when a weekly search downloads a new PDF."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    catalog = [item for item in catalog if item["filename"] != path.name]
    entry = {key: work[key] for key in ("year", "authors", "title", "venue")}
    if work.get("url"):
        entry["scholar_url"] = work["url"]
    entry.update(filename=path.name, former_filenames=[], sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    catalog.append(entry)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
