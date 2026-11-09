"""Demo: anonymize every fictional sample transcript in data/.

Writes anonymized versions to output/, prints the audit log to stdout,
and saves it to output/audit_log.txt.

Run:
    python main.py
    python run_demo.py        # same demo, alternate entry point
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from transcript_anonymizer import TranscriptAnonymizer  # noqa: E402
from transcript_anonymizer.audit import build_audit_report, check_for_leaks  # noqa: E402


def run_demo(data_dir: Path | None = None,
             output_dir: Path | None = None) -> str:
    data_dir = data_dir or ROOT / "data"
    output_dir = output_dir or ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    per_file_audits: dict[str, dict] = {}
    per_file_leaks: dict[str, dict] = {}

    for sample in sorted(data_dir.glob("*.txt")):
        original = sample.read_text(encoding="utf-8")
        anonymizer = TranscriptAnonymizer()
        anonymized, audit = anonymizer.anonymize(original)
        leak = check_for_leaks(anonymized)

        out_path = output_dir / sample.name.replace(".txt", "_anonymized.txt")
        out_path.write_text(anonymized, encoding="utf-8")

        per_file_audits[sample.name] = audit
        per_file_leaks[sample.name] = leak
        print(f"{sample.name}: redacted {audit['total']} identifiers "
              f"-> {out_path.name} "
              f"(identifiers remaining: {leak['remaining']})")

    report = build_audit_report(per_file_audits, per_file_leaks)
    report_text = report.as_text()
    (output_dir / "audit_log.txt").write_text(report_text, encoding="utf-8")

    print()
    print(report_text)
    print(f"Anonymized transcripts + audit log saved to {output_dir}/")
    return report_text


if __name__ == "__main__":
    run_demo()
