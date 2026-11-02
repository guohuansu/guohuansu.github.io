"""Rename the existing PDF library and update all tracked source references.

Dry-run by default. --apply checks every path/collision before renaming, records
SHA-256 hashes and old names in data/pdf-library.json, and never deletes a PDF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import urllib.parse

from pdf_library import CATALOG, ROOT, standard_filename, identity

PDF_DIR = ROOT / "pdf"
EXTRAS = {
    "2020-mapping-global-biodiversity-doctoral-thesis.pdf": {
        "year": 2020, "authors": "G Su", "venue": "University of Toulouse",
        "title": "Mapping global biodiversity, profiling invasive species and developing a global index of biodiversity change based on taxonomic, functional and phylogenetic facets of freshwater fish biodiversity",
        "note": "Doctoral thesis; single author",
    },
    "2022-biogeographic-regionalization-freshwater.pdf": {
        "year": 2022, "authors": "MS Dias, A Oikonomou, G Su", "venue": "Encyclopedia of Biodiversity",
        "title": "Biogeographic Regionalization: Freshwater",
        "note": "Year follows this PDF's 2022 edition, not the later Crossref edition",
    },
    "2023-data-and-code-from-species-invasiveness-and-community-invasibility-of-north-american-freshwater-fish-fauna-revealed-via-trait-based-ana.pdf": {
        "year": 2023, "authors": "G Su, A Mertel, S Brosse, JM Calabrese", "venue": "Nature Communications",
        "title": "Species invasiveness and community invasibility of North American freshwater fish fauna revealed via trait-based analysis",
        "note": "Byte-identical duplicate of the journal paper; original filename incorrectly described a dataset",
    },
    "2025-terrestrial-protected-areas-stabilize-the-inland-habitats-of-diadromous-fishes-under-climate-change.pdf": {
        "year": 2025, "authors": "X Bai, P Zhang, Z Yang, G Grenouillet, J Gessner, X Dong, BR Shipley", "venue": "SSRN",
        "title": "Terrestrial protected areas stabilize the inland habitats of diadromous fishes under climate change",
    },
    "2026-temperature-regimes-shape-similarity-of-life-history-strategies-between-native-and-non-native-freshwater-fishes.pdf": {
        "year": 2026, "authors": "K Zhao, JD Olden, JG Molinos, G Su, C Liu, M Zhang, J Xu, O Ovaskainen", "venue": "Research Square",
        "title": "Temperature regimes shape similarity of life-history strategies between native and non-native freshwater fishes",
        "note": "First author follows manuscript page 2 and PDF metadata; generated cover lists G Su first",
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    works = json.loads((ROOT / "data/publications.json").read_text(encoding="utf-8"))["works"]
    sources = json.loads((ROOT / "data/manual-open-pdf-sources.json").read_text(encoding="utf-8"))
    known = {}
    # Prefer manually verified originals over an accidentally fuzzy-matched
    # correction in the cached publication data.
    for source in sources:
        work = next((w for w in works if w["title"] == source["title"]), None)
        if work and source.get("filename") and (PDF_DIR / source["filename"]).exists():
            known[source["filename"]] = work
    for work in works:
        if work.get("pdf_url"):
            old = urllib.parse.unquote(work["pdf_url"].rsplit("/", 1)[-1])
            known.setdefault(old, work)
    previous = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    for item in previous:
        current = next((work for work in works if identity(work) == identity(item)), {})
        known[item["filename"]] = {**current, **item}
    plan, used = [], set()
    for path in sorted(PDF_DIR.glob("*.pdf")):
        work = EXTRAS.get(path.name) or known.get(path.name)
        if path.name == "2026-yzfishdb-a-curated-dna-reference-database-for-the-fishes-of-the-yangtze-river-basin.pdf":
            work = next(w for w in works if w["title"] == "YZFishDB: A curated DNA reference database for the fishes of the Yangtze River Basin")
        if not work:
            raise RuntimeError(f"Missing metadata: {path.name}")
        suffix = " (duplicate)" if "Byte-identical duplicate" in work.get("note", "") else ""
        name = standard_filename(work, suffix)
        key = name.casefold()
        if key in used:
            raise RuntimeError(f"Filename collision: {name}")
        used.add(key)
        target = PDF_DIR / name
        if path.resolve().parent != PDF_DIR.resolve() or target.resolve().parent != PDF_DIR.resolve():
            raise RuntimeError("Rename target escaped the PDF directory")
        if target.exists() and target != path:
            raise RuntimeError(f"Refusing to overwrite: {name}")
        entry = {key: work[key] for key in ("year", "authors", "title", "venue")}
        if work.get("url") or work.get("scholar_url"):
            entry["scholar_url"] = work.get("url") or work["scholar_url"]
        entry.update(filename=name, former_filenames=list(dict.fromkeys(work.get("former_filenames", []) + ([path.name] if path.name != name else []))), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if work.get("note"):
            entry["note"] = work["note"]
        plan.append((path, target, entry))
    changed = [(src, dst, entry) for src, dst, entry in plan if src != dst]
    print(f"Validated {len(plan)} files; {len(changed)} renames; no PDF will be deleted")
    for src, dst, _ in changed:
        print(f"{src.name} -> {dst.name}".encode("ascii", "backslashreplace").decode())
    if not args.apply:
        return
    mapping = {src.name: dst.name for src, dst, _ in changed}
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    edits = []
    for relative in tracked:
        path = ROOT / relative
        if path.suffix not in {".json", ".py", ".html", ".md", ".yml"} or path == CATALOG or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace("/pdf/" + urllib.parse.quote(old), "/pdf/" + urllib.parse.quote(new))
            updated = updated.replace('href="pdf/' + old, 'href="pdf/' + urllib.parse.quote(new))
            updated = updated.replace(old, new)
            if urllib.parse.quote(old) != old:
                updated = updated.replace(urllib.parse.quote(old), urllib.parse.quote(new))
        if updated != text:
            edits.append((path, updated))
    for src, dst, _ in changed:
        src.rename(dst)
    for path, updated in edits:
        path.write_text(updated, encoding="utf-8")
    CATALOG.write_text(json.dumps([entry for _, _, entry in plan], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for _, dst, entry in plan:
        if hashlib.sha256(dst.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Content checksum changed: {dst.name}")
    print(f"Applied {len(changed)} renames; updated {len(edits)} reference files; all SHA-256 hashes unchanged")


if __name__ == "__main__":
    main()
