"""Download and verify manually vetted public full-text sources.

The source list records where each file came from and its public-sharing basis.
Downloaded files are accepted only when they are readable PDFs whose opening
pages match the target publication title.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import tarfile
import tempfile
import unicodedata
import urllib.request

from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLICATIONS = ROOT / "data" / "publications.json"
SOURCES = ROOT / "data" / "manual-open-pdf-sources.json"
AUDIT = ROOT / "data" / "manual-open-pdf-audit.json"
PDF_DIR = ROOT / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) guohuansu.github.io"


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def filename(year: int, title: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", normalise(title)).strip("-")[:135]
    if not stem:
        stem = "publication"
    return f"{year}-{stem}.pdf"


def download(url: str, target: pathlib.Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/pdf,application/gzip,application/octet-stream;q=0.9,*/*;q=0.2",
            "Referer": urllib.request.Request(url).full_url,
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)


def acquire(source: dict, target: pathlib.Path) -> None:
    if source.get("local_path"):
        local = pathlib.Path(source["local_path"]).expanduser()
        if not local.is_absolute():
            local = (ROOT / local).resolve()
        if not local.exists():
            raise FileNotFoundError(f"local source not found: {source['local_path']}")
        shutil.copyfile(local, target)
        return
    if source.get("local_filename"):
        local = pathlib.Path.home() / "Downloads" / source["local_filename"]
        if not local.exists():
            raise FileNotFoundError(f"local source not found: {source['local_filename']}")
        shutil.copyfile(local, target)
        return
    download(source["url"], target)


def extract_pdf(archive: pathlib.Path, output: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = pathlib.Path(directory)
        with tarfile.open(archive, "r:gz") as bundle:
            safe_members = []
            for member in bundle.getmembers():
                destination = (base / member.name).resolve()
                if destination.is_relative_to(base.resolve()):
                    safe_members.append(member)
            bundle.extractall(base, members=safe_members, filter="data")
        candidates = sorted(base.rglob("*.pdf"), key=lambda path: path.stat().st_size, reverse=True)
        if not candidates:
            raise ValueError("PMC package contained no PDF")
        shutil.copyfile(candidates[0], output)


def title_check(path: pathlib.Path, title: str) -> str:
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError("PDF has no pages")
    text = " ".join((page.extract_text() or "") for page in reader.pages[:3])
    wanted = {word for word in normalise(title).split() if len(word) >= 5}
    if wanted:
        found = set(normalise(text).split())
        overlap = len(wanted & found) / len(wanted)
        if overlap < 0.58:
            raise ValueError(f"title-word overlap too low ({overlap:.2f})")
        return f"title-word overlap {overlap:.2f}"
    # Chinese titles do not survive ASCII normalisation. Matching several long
    # character runs still catches wrong files while tolerating PDF text spacing.
    compact_title = re.sub(r"[^\u3400-\u9fff]", "", title)
    compact_text = re.sub(r"[^\u3400-\u9fff]", "", text)
    chunks = {compact_title[index:index + 4] for index in range(max(0, len(compact_title) - 3))}
    overlap = sum(chunk in compact_text for chunk in chunks) / max(1, len(chunks))
    if overlap < 0.35:
        raise ValueError(f"Chinese-title overlap too low ({overlap:.2f})")
    return f"Chinese-title overlap {overlap:.2f}"


def validate_source(path: pathlib.Path, source: dict, title: str) -> str:
    """Validate automatically, or retain a documented visual check for legacy PDFs."""
    manual = source.get("manual_validation")
    if manual:
        reader = PdfReader(str(path))
        if not reader.pages:
            raise ValueError("PDF has no pages")
        return manual
    return title_check(path, title)


def main() -> None:
    works = json.loads(PUBLICATIONS.read_text(encoding="utf-8"))["works"]
    by_title = {work["title"]: work for work in works}
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    PDF_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    audit = []
    for index, source in enumerate(sources, 1):
        entry = dict(source)
        work = by_title.get(source["title"])
        if not work:
            entry.update(status="skipped", detail="publication title not found")
            audit.append(entry)
            continue
        final = PDF_DIR / source.get("filename", filename(work["year"], work["title"]))
        if final.exists():
            try:
                entry.update(
                    status="verified_present",
                    saved_as=final.name,
                    bytes=final.stat().st_size,
                    validation=validate_source(final, source, work["title"]),
                )
            except Exception as exc:
                entry.update(status="failed_existing_validation", detail=str(exc))
            audit.append(entry)
            continue
        raw = TMP_DIR / f"manual-{index}.download"
        candidate = TMP_DIR / f"manual-{index}.pdf"
        try:
            acquire(source, raw)
            if raw.stat().st_size < 20_000:
                raise ValueError(f"download too small ({raw.stat().st_size} bytes)")
            if source.get("format") == "pmc-tar":
                extract_pdf(raw, candidate)
            else:
                shutil.copyfile(raw, candidate)
            if candidate.read_bytes()[:5] != b"%PDF-":
                raise ValueError("downloaded content is not a PDF")
            entry["validation"] = validate_source(candidate, source, work["title"])
            candidate.replace(final)
            entry.update(status="downloaded", saved_as=final.name, bytes=final.stat().st_size)
        except Exception as exc:
            entry.update(status="failed", detail=str(exc))
        finally:
            raw.unlink(missing_ok=True)
            candidate.unlink(missing_ok=True)
        audit.append(entry)
        print(f"[{index}/{len(sources)}] {entry['status']}: {source['title']}")
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
