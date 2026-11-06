"""Resolve verified author roles without treating missing evidence as negative."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import unicodedata
import urllib.parse
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDENTITIES = ROOT / "data/publication-author-identities.json"
PENDING_JSON = ROOT / "data/pending-author-review.json"
PENDING_MD = ROOT / "data/pending-author-review.md"


def title_key(title: str) -> str:
    title = unicodedata.normalize("NFKC", title).casefold()
    return re.sub(r"[^\w]+", " ", title).strip()


def citation_id(url: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("citation_for_view", [""])[0]


def unique_title_entry(mapping: dict, title: str):
    if title in mapping:
        return title, mapping[title]
    matches = [(key, value) for key, value in mapping.items() if title_key(key) == title_key(title)]
    return matches[0] if len(matches) == 1 else None


def resolve_author_roles(works: list[dict], curated: dict, overrides: dict, identities: dict) -> dict:
    identities = dict(identities)
    for work in works:
        stable_id = citation_id(work.get("url", ""))
        record = identities.get(stable_id)
        curated_entry = unique_title_entry(curated, work["title"])
        author_entry = unique_title_entry(overrides, work["title"])
        if author_entry:
            work["authors"] = author_entry[1]
        elif record and record.get("authors_override"):
            work["authors"] = record["authors_override"]
        # Stable-ID evidence survives changes to the displayed title. An
        # explicitly curated current title may deliberately update an existing ID.
        if record and record.get("status") == "confirmed":
            roles = record["corresponding_authors"]
            if curated_entry:
                roles = curated_entry[1]
        elif curated_entry:
            roles = curated_entry[1]
        else:
            work["corresponding_authors"] = []
            work["corresponding_authors_status"] = "pending"
            continue
        work["corresponding_authors"] = list(roles)
        work["corresponding_authors_status"] = "confirmed"
        if stable_id:
            entry = dict(record or {})
            entry.update(title=work["title"], corresponding_authors=list(roles), status="confirmed")
            entry.setdefault("source", "Manually curated author metadata")
            entry.setdefault("recorded_at", date.today().isoformat())
            if author_entry:
                entry["authors_override"] = author_entry[1]
            identities[stable_id] = entry
    return identities


def apply_author_metadata(works: list[dict]) -> None:
    curated = json.loads((ROOT / "data/publication-author-metadata.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "data/publication-author-overrides.json").read_text(encoding="utf-8"))
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8")) if IDENTITIES.exists() else {}
    identities = resolve_author_roles(works, curated, overrides, identities)
    IDENTITIES.write_text(json.dumps(identities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_report(works)


def write_review_report(works: list[dict], notify: bool = False) -> list[dict]:
    pending = [{"title": work["title"], "year": work.get("year"), "scholar_id": citation_id(work.get("url", "")), "url": work.get("url"), "reason": "No verified corresponding-author record; do not infer roles from author order or the original article."} for work in works if work.get("corresponding_authors_status") == "pending"]
    PENDING_JSON.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Author roles awaiting verification", "", "Missing records mean unreviewed, not confirmed non-corresponding authorship.", ""]
    lines += [f"- {item['year']} — [{item['title']}]({item['url']})" for item in pending] or ["No pending records."]
    PENDING_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if notify:
        summary = f"## Corresponding-author verification\n\n{len(pending)} publication(s) await verification.\n\n"
        summary += "\n".join(f"- {item['title']}" for item in pending)
        if pending:
            print(f"::warning title=Author roles require verification::{len(pending)} publication(s) are pending. Review data/pending-author-review.md; these are not classified as Other publications.")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
                handle.write(summary + "\n")
        print(f"Author-role review: {len(pending)} pending")
    return pending


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", required=True)
    parser.parse_args()
    data = json.loads((ROOT / "data/publications.json").read_text(encoding="utf-8"))
    write_review_report(data["works"], notify=True)
