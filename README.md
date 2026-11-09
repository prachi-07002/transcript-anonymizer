# transcript-anonymizer

Redact names, emails, courses, student IDs, phone numbers, and dates from
interview transcripts for IRB compliance — with a before/after audit log
showing exactly what was replaced.

Built for Prachi Payasi's Spring 2027 Honors College research project with
Prof. Lisa B Bosman, **"Analyzing STEM Education Interventions via
Qualitative Data Analysis"** (GenAI in Project Management, Social Justice
in Calculus, Autoethnography with PMaster Game). Interview transcripts in
qualitative research are full of identifiers; this tool makes them safe to
share, code, and analyse without leaking who said what.

**All sample transcripts are fictional.** Every name, email, Purdue ID,
and phone number in `data/` was invented for testing — no real personal
data is included anywhere in this repo.

## How it works

- **Regex redaction** (`transcript_anonymizer/anonymizer.py`): email,
  phone (`(765) 555-0142`, `765-555-0142`, `765.555.0142`, `+1 …`),
  10-digit Purdue student IDs, course codes (`ECE 36800`, `MA 16500`),
  and full dates (`March 14, 2026`, `05/08/2026`).
- **Name-list replacement**: full names — plus standalone first/last
  names of people already seen — map to consistent placeholders
  (`[NAME-1]`, `[EMAIL-1]`, `[ID-1]`, …). The same person always gets
  the same placeholder *within* a transcript, and numbering restarts for
  the next transcript. Unknown two-word names in speaker labels
  (`Zara Ahmed:`) are also caught; role labels (`Interviewer:`,
  `Facilitator:`) are preserved.
- **Structure preserved**: line breaks, blank lines, `[HH:MM:SS]`
  timestamps, and speaker-label colons are never touched.
- **Audit report** (`transcript_anonymizer/audit.py`): counts per
  category, the full original → placeholder replacement list, and a
  leak check that re-scans the anonymized output for any surviving
  identifier pattern or known name.

Python standard library only — no dependencies to install.

## How to run

```bash
# Demo: anonymize the 4 fictional samples, write output/ + audit log
python main.py
# (same demo, alternate entry point)
python run_demo.py

# Tests
python -m unittest discover -s tests -v
```

Demo output:

- `output/sample_*_anonymized.txt` — one anonymized transcript per sample
- `output/audit_log.txt` — per-file counts, totals, replacements, leak check

## Headline results (sample run)

Verified by running the demo and the test suite on 2026-11-08:

| Metric | Result |
|---|---|
| Unit tests | **17 passed, 0 failed** (`python -m unittest discover -s tests -v`) |
| Total identifiers redacted (4 transcripts) | **113** |
| Names | 64 |
| Emails | 11 |
| Phone numbers | 6 |
| Student IDs | 7 |
| Course codes | 14 |
| Dates | 11 |
| Per-file totals | sample_01: 25 · sample_02: 28 · sample_03: 26 · sample_04: 34 |
| Leak check (identifiers remaining in anonymized output) | **0 — PASS** |

## Project structure

```
transcript-anonymizer/
├── main.py                     # demo runner (also: run_demo.py)
├── transcript_anonymizer/
│   ├── __init__.py
│   ├── anonymizer.py           # regex patterns + name mapping
│   └── audit.py                # audit report + leak check
├── data/                       # 4 fictional sample transcripts
│   ├── sample_01_genai_project_management.txt
│   ├── sample_02_social_justice_calculus.txt
│   ├── sample_03_pmaster_autoethnography.txt
│   └── sample_04_followup_interview.txt
├── output/                     # anonymized transcripts + audit_log.txt
└── tests/
    └── test_anonymizer.py      # 17 unittest tests
```

## Limitations (honest notes)

- Name redaction relies on a name list plus speaker-label detection, so
  a name never seen before and not in a speaker label can slip through —
  that is exactly what the leak check + audit log are for: review them
  before sharing any transcript, and add new names via
  `TranscriptAnonymizer(extra_names=[...])`.
- Dates are redacted as identifiers; if a study needs relative timing
  (e.g. "week 3"), replace dates with relative labels instead.
- This is a de-identification aid, not a legal guarantee of anonymity:
  distinctive stories can still identify someone, so always follow your
  IRB protocol and human-subjects training.

## Application talking point

> Built a Python transcript anonymizer that redacted 113 identifiers across 4 interview transcripts (names, emails, IDs, phones, courses, dates) with a before/after audit log and a 0-identifier leak check, to prepare qualitative data for IRB-compliant analysis.
