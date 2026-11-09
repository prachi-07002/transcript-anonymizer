"""transcript-anonymizer: redact identifiers from interview transcripts for IRB compliance."""

from .anonymizer import TranscriptAnonymizer, anonymize_text
from .audit import AuditReport, build_audit_report, check_for_leaks

__all__ = [
    "TranscriptAnonymizer",
    "anonymize_text",
    "AuditReport",
    "build_audit_report",
    "check_for_leaks",
]

__version__ = "1.0.0"
