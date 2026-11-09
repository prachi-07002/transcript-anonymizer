"""Unit tests for transcript-anonymizer (stdlib unittest only)."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from transcript_anonymizer import TranscriptAnonymizer, anonymize_text  # noqa: E402
from transcript_anonymizer.audit import check_for_leaks  # noqa: E402


class TestEmailRedaction(unittest.TestCase):
    def test_single_email_replaced_with_placeholder(self):
        text, audit = anonymize_text(
            "Contact Maya at maya.thompson@purdue.edu for details.")
        self.assertNotIn("maya.thompson@purdue.edu", text)
        self.assertIn("[EMAIL-1]", text)
        self.assertEqual(audit["counts"]["email"], 1)

    def test_multiple_emails_get_distinct_placeholders(self):
        text, audit = anonymize_text(
            "Email maya.thompson@purdue.edu or jordan.lee@purdue.edu.")
        self.assertIn("[EMAIL-1]", text)
        self.assertIn("[EMAIL-2]", text)
        self.assertEqual(audit["counts"]["email"], 2)

    def test_same_email_twice_gets_same_placeholder(self):
        text, _ = anonymize_text(
            "Write to emma.wilson@purdue.edu. Again: emma.wilson@purdue.edu.")
        self.assertEqual(text.count("[EMAIL-1]"), 2)
        self.assertNotIn("[EMAIL-2]", text)


class TestPhoneRedaction(unittest.TestCase):
    def test_phone_formats(self):
        for phone in ["(765) 555-0142", "765-555-0142", "765.555.0142",
                      "+1 765-555-0142"]:
            text, audit = anonymize_text(f"Call me at {phone}.")
            self.assertNotIn(phone, text, msg=phone)
            self.assertIn("[PHONE-1]", text, msg=phone)
            self.assertEqual(audit["counts"]["phone"], 1, msg=phone)


class TestStudentIdRedaction(unittest.TestCase):
    def test_ten_digit_id_replaced(self):
        text, audit = anonymize_text("My student ID is 0034567891.")
        self.assertNotIn("0034567891", text)
        self.assertIn("[ID-1]", text)
        self.assertEqual(audit["counts"]["student_id"], 1)

    def test_short_numbers_are_not_ids(self):
        # A 5-digit course-adjacent number / year must survive.
        text, _ = anonymize_text("In 2026 we had 42 students.")
        self.assertIn("2026", text)
        self.assertIn("42", text)


class TestCourseAndDateRedaction(unittest.TestCase):
    def test_course_code_replaced(self):
        text, audit = anonymize_text("I am taking ECE 36800 and MA 16500.")
        self.assertNotIn("ECE 36800", text)
        self.assertNotIn("MA 16500", text)
        self.assertIn("[COURSE-1]", text)
        self.assertIn("[COURSE-2]", text)
        self.assertEqual(audit["counts"]["course"], 2)

    def test_date_replaced(self):
        text, audit = anonymize_text("We met on March 14, 2026.")
        self.assertNotIn("March 14, 2026", text)
        self.assertIn("[DATE-1]", text)
        self.assertEqual(audit["counts"]["date"], 1)


class TestNameRedaction(unittest.TestCase):
    def test_full_name_replaced(self):
        text, audit = anonymize_text("Maya Thompson joined the study.")
        self.assertNotIn("Maya Thompson", text)
        self.assertIn("[NAME-1]", text)
        self.assertEqual(audit["counts"]["name"], 1)

    def test_consistent_mapping_same_name_same_placeholder(self):
        text, _ = anonymize_text(
            "Maya Thompson said hello. Maya Thompson agreed. Maya nodded.")
        self.assertEqual(text.count("[NAME-1]"), 3)
        self.assertNotIn("[NAME-2]", text)
        self.assertNotIn("Maya", text)

    def test_different_names_get_different_placeholders(self):
        text, _ = anonymize_text(
            "Maya Thompson met Jordan Lee after class.")
        self.assertIn("[NAME-1]", text)
        self.assertIn("[NAME-2]", text)

    def test_unknown_name_in_speaker_label_is_redacted(self):
        text, _ = anonymize_text(
            "Zara Ahmed: I used the tool every week.\nInterviewer: Thanks.")
        self.assertNotIn("Zara Ahmed", text)
        self.assertIn("[NAME-1]:", text)
        # Role labels are preserved, not redacted.
        self.assertIn("Interviewer:", text)

    def test_mapping_resets_for_each_transcript(self):
        anon = TranscriptAnonymizer()
        text1, _ = anon.anonymize("Maya Thompson spoke first.")
        text2, _ = anon.anonymize("Jordan Lee spoke first.")
        self.assertIn("[NAME-1]", text1)
        self.assertIn("[NAME-1]", text2)  # numbering restarts per transcript


class TestStructurePreservation(unittest.TestCase):
    def test_line_breaks_and_timestamps_preserved(self):
        original = (
            "[00:00:05] Interviewer: Hello, Maya Thompson.\n"
            "[00:00:12] Maya Thompson: Hi, my email is maya.thompson@purdue.edu.\n"
            "\n"
            "[00:01:00] Interviewer: Thanks.\n"
        )
        text, _ = anonymize_text(original)
        self.assertEqual(text.count("\n"), original.count("\n"))
        self.assertIn("[00:00:05]", text)
        self.assertIn("[00:00:12]", text)
        self.assertIn("[00:01:00]", text)
        self.assertIn("Interviewer:", text)
        # Speaker label keeps its colon, only the name is replaced.
        self.assertIn("[NAME-1]: Hi,", text)

    def test_non_identifier_text_is_unchanged(self):
        text, _ = anonymize_text("The project charter was due on Friday.")
        self.assertEqual(text, "The project charter was due on Friday.")


class TestNoLeak(unittest.TestCase):
    def test_no_identifiers_remain_in_output(self):
        original = (
            "Maya Thompson, ID 0034567891, maya.thompson@purdue.edu, "
            "(765) 555-0142, ECE 36800, March 14, 2026."
        )
        text, audit = anonymize_text(original)
        self.assertEqual(audit["total"], 6)
        for secret in ["Maya Thompson", "0034567891",
                       "maya.thompson@purdue.edu", "(765) 555-0142",
                       "ECE 36800", "March 14, 2026"]:
            self.assertNotIn(secret, text)
        leak = check_for_leaks(text)
        self.assertEqual(leak["remaining"], 0, msg=str(leak["found"]))

    def test_sample_files_have_zero_leaks(self):
        data_dir = ROOT / "data"
        self.assertTrue(list(data_dir.glob("*.txt")),
                        "expected sample transcripts in data/")
        for sample in sorted(data_dir.glob("*.txt")):
            with self.subTest(sample=sample.name):
                text, audit = anonymize_text(
                    sample.read_text(encoding="utf-8"))
                self.assertGreater(audit["total"], 0,
                                   msg=f"{sample.name} should plant identifiers")
                leak = check_for_leaks(text)
                self.assertEqual(leak["remaining"], 0,
                                 msg=f"{sample.name}: {leak['found']}")
                # No planted email / phone / ID survives in any sample.
                self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
                self.assertNotRegex(text, r"\b\d{10}\b")


if __name__ == "__main__":
    unittest.main()
