"""Core anonymizer: regex + name-list redaction with consistent per-transcript mapping.

Design notes
------------
* One ``TranscriptAnonymizer`` instance = one transcript.  Mappings are
  reset between transcripts so ``[NAME-1]`` always means the same person
  *within* a transcript, and numbering restarts for the next one.
* Replacement order matters: emails first (so a name inside an email
  address is not redacted separately), then phones, student IDs,
  course codes, dates, then names.
* Structure is preserved: line breaks, blank lines, ``[HH:MM:SS]``
  timestamps and speaker-label colons are never touched.  Only the
  identifier inside a speaker label (``Maya Thompson:``) is replaced.
* Only the Python standard library is used (``re`` and ``collections``).
"""

from __future__ import annotations

import re
from collections import Counter, OrderedDict

# ---------------------------------------------------------------------------
# Regex patterns (compiled once, reused for every transcript)
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
# (765) 555-0142 | 765-555-0142 | 765.555.0142 | 765 555 0142 | +1 765-555-0142
PHONE_RE = re.compile(
    r"(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}"
)
# Purdue student ID: exactly 10 digits (also catches 002-34-5678 style).
ID_RE = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b|\b\d{10}\b"
)
# ECE 36800 | MA16500 | CS 18000 | FIN 30400 -- 2-4 letters + 5 digits.
COURSE_RE = re.compile(
    r"\b[A-Z]{2,4}\s?\d{5}\b"
)
# January 15, 2026 | Jan 15, 2026 | 03/14/2026 | 2026-03-14
DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
    r"Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)
# Timestamp that must be PRESERVED, e.g. [00:01:12] or 10:30 AM.
TIMESTAMP_RE = re.compile(r"\[\d{2}:\d{2}:\d{2}\]|\b\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)\b")

# Speaker label at the start of a line: "Maya Thompson:" / "Jordan Lee:"
SPEAKER_RE = re.compile(
    r"(?m)^([A-Z][a-z]+(?: [A-Z][a-z]+)+):"
)

# Role labels that are NOT names and must be kept verbatim.
ROLE_LABELS = {
    "Interviewer", "Participant", "Student", "Professor", "Researcher",
    "Facilitator", "Moderator", "Speaker", "Instructor", "Teaching Assistant",
    "Note Taker", "Observer",
}

# First names that are also common English words -- never redact standalone.
AMBIGUOUS_FIRST_NAMES = {"May", "Grace", "Hope", "Faith", "Joy", "Summer",
                          "April", "June", "Rose", "Bill", "Chase", "Mark"}

# ---------------------------------------------------------------------------
# Name list: fictional names used in the samples, plus common names so the
# anonymizer also works on unseen transcripts that reuse them.  Full names
# are matched first; a standalone first/last name then maps to the same
# placeholder as the full name it came from.
# ---------------------------------------------------------------------------

KNOWN_NAMES = [
    # Names planted in the sample transcripts.
    "Maya Thompson", "Jordan Lee", "Priya Sharma", "Alex Morgan",
    "Sam Rivera", "Taylor Nguyen", "Chris Patel", "Emma Wilson",
    "Liam Chen", "Sofia Garcia", "Noah Kim", "Ava Johnson",
    "Ethan Brown", "Mia Davis", "Lucas Miller", "Zoe Anderson",
    "Owen Clark", "Ruby Patel", "Caleb Brooks", "Nina Rossi",
    "Daniel Okafor", "Hannah Kim", "Ben Carter", "Lena Fischer",
    # Extra common names, for transcripts beyond the samples.
    "James Smith", "Mary Johnson", "John Davis", "Sarah Miller",
    "Michael Brown", "Emily Wilson", "David Moore", "Jessica Taylor",
    "Daniel Anderson", "Laura Thomas", "Kevin White", "Rachel Harris",
    "Ryan Martin", "Olivia Thompson", "Jacob Garcia", "Sophia Martinez",
    "William Robinson", "Isabella Clark", "Ethan Rodriguez", "Mia Lewis",
]

CATEGORIES = ("name", "email", "phone", "student_id", "course", "date")

# Placeholder prefix per category.
PREFIX = {
    "name": "NAME",
    "email": "EMAIL",
    "phone": "PHONE",
    "student_id": "ID",
    "course": "COURSE",
    "date": "DATE",
}


class TranscriptAnonymizer:
    """Redact identifiers from one transcript, with a consistent mapping."""

    def __init__(self, extra_names: list[str] | None = None):
        self.extra_names = list(extra_names or [])
        self.reset()

    def reset(self) -> None:
        """Clear per-transcript mappings and counts (call before each file)."""
        # category -> OrderedDict[original, placeholder]
        self.mapping: dict[str, OrderedDict[str, str]] = {
            cat: OrderedDict() for cat in CATEGORIES
        }
        self.counts: Counter = Counter()
        # Unique replacements, in first-seen order, for the audit log.
        self.replacements: list[dict[str, str]] = []

    # -- internal helpers ---------------------------------------------------

    def _placeholder(self, category: str, original: str) -> str:
        """Return the (stable) placeholder for ``original`` in ``category``."""
        mapping = self.mapping[category]
        if original not in mapping:
            number = len(mapping) + 1
            placeholder = f"[{PREFIX[category]}-{number}]"
            mapping[original] = placeholder
            self.replacements.append(
                {"category": category, "original": original,
                 "placeholder": placeholder}
            )
        return mapping[original]

    def _sub(self, pattern: re.Pattern, category: str, text: str) -> str:
        def repl(match: re.Match) -> str:
            original = match.group(0)
            self.counts[category] += 1
            return self._placeholder(category, original)

        return pattern.sub(repl, text)

    def _redact_names(self, text: str) -> str:
        # 1. Speaker labels first: an unknown two-word name in "Name:" position
        #    is a name even if it is not in KNOWN_NAMES.
        def speaker_repl(match: re.Match) -> str:
            label = match.group(1)
            if label in ROLE_LABELS:
                return match.group(0)
            self.counts["name"] += 1
            return f"{self._placeholder('name', label)}:"

        text = SPEAKER_RE.sub(speaker_repl, text)

        # 2. Known full names, longest first so "Maya Thompson" wins over "Maya".
        names = sorted(
            set(KNOWN_NAMES) | set(self.extra_names),
            key=len, reverse=True,
        )
        for full_name in names:
            pattern = re.compile(r"\b" + re.escape(full_name) + r"\b")
            if pattern.search(text):
                placeholder = self._placeholder("name", full_name)
                text, n = pattern.subn(placeholder, text)
                self.counts["name"] += n

        # 3. Standalone first/last names of people already seen in this
        #    transcript map to the SAME placeholder as their full name.
        #    (Only for names already in the mapping, so no guessing.)
        seen_full = list(self.mapping["name"].keys())
        for full_name in seen_full:
            parts = full_name.split()
            if len(parts) < 2:
                continue
            placeholder = self.mapping["name"][full_name]
            for part in parts:
                if part in AMBIGUOUS_FIRST_NAMES:
                    continue
                # Skip parts that are already inside a placeholder (they aren't
                # plain text any more) -- plain word-boundary search is enough.
                pattern = re.compile(r"\b" + re.escape(part) + r"\b")
                if pattern.search(text):
                    text, n = pattern.subn(placeholder, text)
                    self.counts["name"] += n
        return text

    # -- public API ---------------------------------------------------------

    def anonymize(self, text: str) -> tuple[str, dict]:
        """Return ``(anonymized_text, audit)`` for one transcript.

        ``audit`` is ``{"counts": {...}, "replacements": [...],
        "total": int}`` -- counts are occurrences, replacements are the
        unique original -> placeholder pairs in first-seen order.
        """
        self.reset()
        result = text

        # Order matters: email before names, ID/phone before dates.
        result = self._sub(EMAIL_RE, "email", result)
        result = self._sub(PHONE_RE, "phone", result)
        result = self._sub(ID_RE, "student_id", result)
        result = self._sub(COURSE_RE, "course", result)
        result = self._sub(DATE_RE, "date", result)
        result = self._redact_names(result)

        audit = {
            "counts": {cat: self.counts.get(cat, 0) for cat in CATEGORIES},
            "replacements": list(self.replacements),
            "total": sum(self.counts.values()),
        }
        return result, audit


def anonymize_text(text: str, extra_names: list[str] | None = None) -> tuple[str, dict]:
    """One-shot helper: anonymize ``text`` with a fresh anonymizer."""
    return TranscriptAnonymizer(extra_names=extra_names).anonymize(text)
