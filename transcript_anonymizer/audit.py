"""Audit report + leak check for anonymized transcripts.

``build_audit_report`` turns per-file audits into a human-readable
before/after log.  ``check_for_leaks`` re-scans anonymized text for any
identifier pattern (or known name) that survived, so a transcript is
only declared clean when the scan finds nothing.
"""

from __future__ import annotations

import re

from .anonymizer import (
    CATEGORIES,
    COURSE_RE,
    DATE_RE,
    EMAIL_RE,
    ID_RE,
    KNOWN_NAMES,
    PHONE_RE,
)

# Patterns that must NOT appear in anonymized output.
LEAK_PATTERNS = {
    "email": EMAIL_RE,
    "phone": PHONE_RE,
    "student_id": ID_RE,
    "course": COURSE_RE,
    # Dates are redacted too, but a bare year (2026) is not an identifier
    # on its own, so the leak scan uses the full-date pattern only.
    "date": DATE_RE,
}

CATEGORY_LABELS = {
    "name": "Names",
    "email": "Emails",
    "phone": "Phone numbers",
    "student_id": "Student IDs",
    "course": "Course codes",
    "date": "Dates",
}


class AuditReport:
    """Aggregated audit across one demo run (several transcripts)."""

    def __init__(self):
        self.per_file: dict[str, dict] = {}
        self.total_counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}
        self.leak_results: dict[str, dict] = {}

    def add_file(self, filename: str, audit: dict, leak: dict) -> None:
        self.per_file[filename] = audit
        self.leak_results[filename] = leak
        for cat in CATEGORIES:
            self.total_counts[cat] += audit["counts"].get(cat, 0)

    @property
    def total(self) -> int:
        return sum(self.total_counts.values())

    @property
    def total_leaks(self) -> int:
        return sum(r["remaining"] for r in self.leak_results.values())

    def as_text(self) -> str:
        lines = [
            "TRANSCRIPT ANONYMIZER -- AUDIT LOG",
            "=" * 60,
            "",
            "Per-file redaction counts (occurrences):",
        ]
        for filename, audit in self.per_file.items():
            counts = ", ".join(
                f"{cat}={audit['counts'].get(cat, 0)}" for cat in CATEGORIES
            )
            leak = self.leak_results[filename]["remaining"]
            lines.append(f"  {filename}: total={audit['total']} ({counts}) "
                         f"| identifiers remaining after redaction: {leak}")
        lines += [
            "",
            "TOTAL identifiers redacted (all files): "
            f"{self.total}",
        ]
        for cat in CATEGORIES:
            lines.append(f"  {CATEGORY_LABELS[cat]}: {self.total_counts[cat]}")
        lines += [
            "",
            "Leak check (re-scan of anonymized output):",
            f"  Identifiers remaining: {self.total_leaks} "
            f"({'PASS -- 0 remaining' if self.total_leaks == 0 else 'FAIL'})",
            "",
            "Replacements (original -> placeholder, first-seen order):",
        ]
        for filename, audit in self.per_file.items():
            lines.append(f"  [{filename}]")
            for rep in audit["replacements"]:
                lines.append(
                    f"    {rep['category']:>10}: {rep['original']!r} "
                    f"-> {rep['placeholder']}"
                )
        lines.append("")
        return "\n".join(lines)


def check_for_leaks(anonymized_text: str,
                    extra_names: list[str] | None = None) -> dict:
    """Scan anonymized text for leftover identifiers.

    Returns ``{"remaining": int, "found": {category: [matches]}}``.
    A name counts as a leak only if a full known name still appears
    verbatim -- standalone first names are not checked, because common
    first names (e.g. Alex) can also be ordinary words.
    """
    found: dict[str, list[str]] = {}
    for category, pattern in LEAK_PATTERNS.items():
        matches = pattern.findall(anonymized_text)
        # findall returns tuples for patterns with groups; normalise.
        flat = [m[0] if isinstance(m, tuple) else m for m in matches]
        if flat:
            found[category] = sorted(set(flat))

    names = set(KNOWN_NAMES) | set(extra_names or [])
    leaked_names = sorted(
        name for name in names
        if re.search(r"\b" + re.escape(name) + r"\b", anonymized_text)
    )
    if leaked_names:
        found["name"] = leaked_names

    return {"remaining": sum(len(v) for v in found.values()), "found": found}


def build_audit_report(per_file_audits: dict[str, dict],
                       per_file_leaks: dict[str, dict]) -> AuditReport:
    """Assemble an :class:`AuditReport` from per-file audits and leak checks."""
    report = AuditReport()
    for filename, audit in per_file_audits.items():
        report.add_file(filename, audit, per_file_leaks[filename])
    return report
