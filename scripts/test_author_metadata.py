"""Regression coverage for silent corresponding-author omissions."""
import copy
import unittest

from author_metadata import resolve_author_roles


def work(title, key="paper"):
    return {"title": title, "authors": "A Author, G Su", "year": 2026,
            "url": "https://scholar.google.com/citations?citation_for_view=profile:" + key}


class AuthorRoleTests(unittest.TestCase):
    def test_missing_evidence_is_pending_not_a_negative(self):
        papers = [work("Confirmed negative", "negative"), work("Unknown paper", "unknown")]
        resolve_author_roles(papers, {"Confirmed negative": []}, {}, {})
        self.assertEqual(papers[0]["corresponding_authors_status"], "confirmed")
        self.assertEqual(papers[1]["corresponding_authors_status"], "pending")

    def test_correction_does_not_inherit_the_original_roles(self):
        papers = [work("Original paper", "original"), work("Corrigendum to Original paper", "correction")]
        identities = resolve_author_roles(papers, {"Original paper": ["G Su"]}, {}, {})
        self.assertEqual(papers[1]["corresponding_authors_status"], "pending")
        self.assertNotIn("profile:correction", identities)

    def test_stable_id_preserves_confirmation_and_full_author_override(self):
        papers = [work("Original title")]
        identities = resolve_author_roles(papers, {"Original title": ["G Su"]}, {"Original title": "A Author, B Author, Guohuan Su"}, {})
        changed = [work("Completely revised display title")]
        resolve_author_roles(changed, {}, {}, copy.deepcopy(identities))
        self.assertEqual(changed[0]["corresponding_authors"], ["G Su"])
        self.assertEqual(changed[0]["corresponding_authors_status"], "confirmed")
        self.assertEqual(changed[0]["authors"], "A Author, B Author, Guohuan Su")
        amended = [work("Completely revised display title")]
        resolve_author_roles(amended, {"Completely revised display title": ["G Su", "B Author"]}, {}, identities)
        self.assertEqual(amended[0]["corresponding_authors"], ["G Su", "B Author"])

    def test_unicode_title_fallback_is_unique_and_conservative(self):
        papers = [work("鱼类 α-diversity—patterns")]
        resolve_author_roles(papers, {"鱼类 α-diversity: patterns": ["G Su"]}, {}, {})
        self.assertEqual(papers[0]["corresponding_authors_status"], "confirmed")
        ambiguous = [work("A—B")]
        resolve_author_roles(ambiguous, {"A: B": ["G Su"], "A B": []}, {}, {})
        self.assertEqual(ambiguous[0]["corresponding_authors_status"], "pending")


if __name__ == "__main__":
    unittest.main()
