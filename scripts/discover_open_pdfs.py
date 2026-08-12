"""Find and download legally reusable open full texts for missing publications.

Sources are discovered through OpenAlex. A file is downloaded only when the
location has an explicit Creative Commons/public-domain licence, or is an
accepted/submitted manuscript hosted by a scholarly repository. Every accepted
file is checked as a readable PDF and matched against the publication title.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import time
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "publications.json"
PDF_DIR = ROOT / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
AUDIT = ROOT / "data" / "open-pdf-sources.json"
UA = "guohuansu.github.io open-access full-text updater"


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def reusable(location: dict) -> bool:
    licence = (location.get("license") or "").lower()
    source = location.get("source") or {}
    version = location.get("version") or ""
    if licence.startswith("cc-") or licence in {"public-domain", "pd"}:
        return True
    return source.get("host_organization_lineage") and source.get("type") in {"repository", "preprint"} and version in {"acceptedVersion", "submittedVersion"}


def unpaywall_locations(doi_url: str | None) -> list[dict]:
    if not doi_url:
        return []
    doi = re.sub(r"^https?://doi.org/", "", doi_url, flags=re.I)
    try:
        record = request_json(
            "https://api.unpaywall.org/v2/"
            + urllib.parse.quote(doi, safe="/")
            + "?email=webmaster%40guohuansu.github.io"
        )
    except Exception:
        return []
    locations = []
    for item in record.get("oa_locations", []):
        if not item.get("url_for_pdf"):
            continue
        locations.append(
            {
                "pdf_url": item["url_for_pdf"],
                "license": item.get("license"),
                "version": item.get("version"),
                "source": {
                    "display_name": (item.get("repository_institution") or item.get("host_type") or "Unpaywall"),
                    "type": item.get("host_type"),
                    "host_organization_lineage": ["repository"] if item.get("host_type") == "repository" else [],
                },
            }
        )
    return locations


def crossref_locations(doi_url: str | None) -> list[dict]:
    if not doi_url:
        return []
    doi = re.sub(r"^https?://doi.org/", "", doi_url, flags=re.I)
    try:
        message = request_json(
            "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
        )["message"]
    except Exception:
        return []
    licences = [item.get("URL", "").lower() for item in message.get("license", [])]
    licence = next((url for url in licences if "creativecommons.org/licenses/" in url), "")
    if not licence:
        return []
    licence_name = "cc-" + licence.split("creativecommons.org/licenses/", 1)[1].strip("/").split("/", 1)[0]
    return [
        {
            "pdf_url": item["URL"],
            "license": licence_name,
            "version": "publishedVersion",
            "source": {"display_name": "Crossref publisher link", "type": "journal"},
        }
        for item in message.get("link", [])
        if item.get("content-type") == "application/pdf" and item.get("URL")
    ]


def safe_filename(year: int, title: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", normalise(title)).strip("-")[:135]
    return f"{year}-{stem}.pdf"


def title_matches_pdf(path: pathlib.Path, title: str) -> tuple[bool, str]:
    try:
        reader = PdfReader(str(path))
        if not reader.pages:
            return False, "no pages"
        text = " ".join((page.extract_text() or "") for page in reader.pages[:3])
        wanted = set(normalise(title).split())
        found = set(normalise(text).split())
        distinctive = {word for word in wanted if len(word) >= 5}
        overlap = len(distinctive & found) / max(1, len(distinctive))
        return overlap >= 0.62, f"title-word overlap {overlap:.2f}"
    except Exception as exc:
        return False, f"unreadable PDF: {exc}"


def download(url: str, target: pathlib.Path) -> tuple[bool, str]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf"})
        with urllib.request.urlopen(request, timeout=75) as response, target.open("wb") as output:
            content_type = response.headers.get("Content-Type", "")
            shutil.copyfileobj(response, output)
        if target.stat().st_size < 20_000:
            return False, "file too small"
        with target.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return False, f"not a PDF ({content_type})"
        return True, content_type
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    publications = json.loads(DATA.read_text(encoding="utf-8"))["works"]
    missing = [work for work in publications if not work.get("pdf_url")]
    PDF_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    audit = []
    for index, work in enumerate(missing, 1):
        query = urllib.parse.urlencode({"search": work["title"], "per-page": 8})
        try:
            results = request_json(f"https://api.openalex.org/works?{query}").get("results", [])
        except Exception as exc:
            audit.append({"title": work["title"], "status": "lookup_failed", "detail": str(exc)})
            continue
        ranked = sorted(
            ((SequenceMatcher(None, normalise(work["title"]), normalise(item.get("title") or "")).ratio(), item) for item in results),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if not ranked or ranked[0][0] < 0.88:
            audit.append({"title": work["title"], "status": "no_metadata_match"})
            continue
        score, record = ranked[0]
        all_locations = record.get("locations", []) + unpaywall_locations(record.get("doi")) + crossref_locations(record.get("doi"))
        seen_urls = set()
        locations = []
        for location in all_locations:
            url = location.get("pdf_url")
            if url and url not in seen_urls and reusable(location):
                seen_urls.add(url)
                locations.append(location)
        entry = {"title": work["title"], "openalex_title": record.get("title"), "title_score": round(score, 3), "doi": record.get("doi"), "openalex_id": record.get("id"), "candidates": []}
        accepted = False
        for candidate_index, location in enumerate(locations, 1):
            candidate = {"url": location["pdf_url"], "license": location.get("license"), "version": location.get("version"), "source": (location.get("source") or {}).get("display_name")}
            entry["candidates"].append(candidate)
            if not args.download or accepted:
                continue
            temporary = TMP_DIR / f"candidate-{index}-{candidate_index}.pdf"
            ok, detail = download(location["pdf_url"], temporary)
            candidate["download"] = detail
            if ok:
                ok, detail = title_matches_pdf(temporary, work["title"])
                candidate["validation"] = detail
            if ok:
                final = PDF_DIR / safe_filename(work["year"], work["title"])
                temporary.replace(final)
                candidate["saved_as"] = final.name
                accepted = True
            elif temporary.exists():
                temporary.unlink()
        entry["status"] = "downloaded" if accepted else ("candidate_found" if locations else "no_reusable_pdf")
        audit.append(entry)
        print(f"[{index}/{len(missing)}] {entry['status']}: {work['title']}")
        time.sleep(0.12)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Audit written to {AUDIT}")


if __name__ == "__main__":
    main()
