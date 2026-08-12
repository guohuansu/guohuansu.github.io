"""Repair PDFs accidentally saved with multipart/form-data wrappers."""
from __future__ import annotations

import pathlib

from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdf"


def main() -> None:
    repaired = 0
    for path in sorted(PDF_DIR.glob("*.pdf")):
        payload = path.read_bytes()
        if payload.startswith(b"%PDF-"):
            continue
        start = payload.find(b"%PDF-")
        end = payload.rfind(b"%%EOF")
        if start < 0 or end < start:
            print(f"SKIP (no embedded PDF): {path.name}")
            continue
        candidate = path.with_suffix(".repaired.pdf")
        candidate.write_bytes(payload[start : end + len(b"%%EOF")] + b"\n")
        try:
            reader = PdfReader(str(candidate))
            if not reader.pages:
                raise ValueError("repaired PDF has no pages")
        except Exception:
            candidate.unlink(missing_ok=True)
            raise
        candidate.replace(path)
        repaired += 1
        print(f"REPAIRED ({len(reader.pages)} pages): {path.name}")
    print(f"Repaired {repaired} PDF file(s)")


if __name__ == "__main__":
    main()
