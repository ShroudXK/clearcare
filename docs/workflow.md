# Workflow and troubleshooting

## 1. Set up an isolated environment

Run commands from the repository root, where `clearcare/`, `sql/`, and `requirements.txt` are visible. Python 3.12 is the tested version. Install only the two pinned dependencies into a project virtual environment; no global settings, database server, or API credentials are required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The first dependency installation needs internet access. After that, the snapshot workflow can run offline.

## 2. Understand the reviewed inputs

`data/curated/` contains 11 CSV tables, `dataset.json`, input checksums, and initial retrieval metadata. Empty insurance CSVs contain headers but no invented production rows. `data/fixtures/network_demo.json` contains explicitly fictional observations used only inside an evaluation transaction that is rolled back.

Source pages were read before summaries were written. The retrieval log records what was downloaded, not a promise that every page remains unchanged. Full pages and PDF bytes are excluded from Git and the public download.

## 3. Build and inspect the database

```bash
python -m clearcare build --database build/clearcare.duckdb
```

The builder:

1. Verifies reviewed input hashes.
2. Creates a temporary database next to the destination.
3. Starts a transaction and creates parent tables before dependent tables.
4. Loads each CSV through DuckDB `read_csv` using typed destination tables.
5. Runs content and relationship checks, including the dependency graph.
6. Commits and replaces the destination after checks pass.

This is a rebuild of a derived database, not a migration tool for patient data. The source CSVs remain the authoritative project inputs.

For an example SQL query from Python:

```python
import duckdb
from clearcare.core import rows, sql

with duckdb.connect("build/clearcare.duckdb", read_only=True) as con:
    result = rows(con, sql("facility_services.sql"), {
        "service_id": "radiology", "as_of": "2026-10-07"
    })
    for item in result:
        print(item["name"], item["evidence_state"], item["scope_note"])
```

This joins locations, service relationships, services, and sources. A listed imaging service is not a guarantee of availability or coverage. The notebook walks through the same pattern without requiring a separate database server.

## 4. Generate a guide

```bash
python -m clearcare guide --scenario campus_visit --needs-interpreter --as-of 2026-10-07
python -m clearcare guide --scenario fracture_followup --needs-interpreter \
  --no-prior-records --mckinley-referral --as-of 2026-10-07
python -m clearcare guide --emergency --as-of 2026-10-07
```

The guide command reads an existing database and writes JSON, Markdown, and HTML. It uses the actual local date when `--as-of` is omitted. The pipeline uses the fixed snapshot date by default for reproducibility. Conditions reflect preparation needs rather than clinical judgments.

SQL chooses applicable steps and checks all linked sources. Python orders the chosen steps so prerequisites come first, while preserving the editorial order where possible. The dependency graph organizes the checklist; it does not enforce a clinical workflow or require completing insurance checks before emergency care.

An item is within its review interval when the selected date is on or after its review date and no more than its configured interval later. Older or not-yet-reviewed items keep their title and sources but replace the instructions with a review prompt. Local source intervals are 30 days; general pages use 180 days; the older CMS preparation PDF uses 365 days. These are explicit project assumptions, not published standards.

## 5. Evaluate and replay

```bash
python -m unittest discover -s tests -v
python -m clearcare pipeline --as-of 2026-10-07 --output build
python scripts/verify_examples.py
```

The scenario evaluator defines 30 expectations. The regression suite contains 24 test methods, one of which reruns those scenarios, so the counts overlap. It also tests database constraints, preserved previous builds, deterministic guide text, and safe source parsing. CI runs the same commands on Linux and uploads generated results.

Published examples are produced with the fixed snapshot date. `verify_examples.py` compares generated guide text and reports against committed examples; it ignores database bytes and environment-specific run metadata.

## 6. Check and update sources deliberately

```bash
python -m clearcare check-sources --output build/source_check
```

This is opt-in because external websites can change. Each approved URL is retrieved with certificate validation, a timeout, a size limit, and an approved-domain redirect check. HTML text and PDF text are extracted; raw hashes and short anchors are compared with the original retrieval metadata. No credentials are sent.

A changed hash is a reason to inspect the page, not proof that a policy changed. Repeated dynamic navigation or layout changes may alter the bytes. HTTP failures, non-PDF responses, missing anchors, and redirected domains are reported without silently approving new guidance.

After personally inspecting a source update:

1. Edit the relevant CSV summaries and links, keeping uncertain requirements as questions.
2. Update the source's `reviewed_on`, locator, and publication note when justified.
3. Check both language versions and scope.
4. Recompute the input manifest using `python scripts/update_manifest.py --review-confirmed`.
5. Run tests and the pipeline. If the dataset has deliberately changed, update the expected evaluation and published examples after inspecting the new outputs; document the change in `docs/decision_log.md`.

The manifest command records accepted input bytes. It cannot perform the source review for you. The initial retrieval baseline should remain historical evidence; later retrieval reports can be saved as separately dated records.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `No module named duckdb` or `pypdf` | Activate the project environment, then run `python -m pip install -r requirements.txt` with that same interpreter. |
| `No module named clearcare` | Move to the repository root before running `python -m clearcare`. |
| `Database not found` | Run the `build` or `pipeline` command first, or pass the correct `--database` path. |
| File lock or replacement failure | Close notebooks and other processes using that database, then rebuild. Do not delete unrelated database files. |
| Curated input checksum mismatch | Inspect whether a CSV was intentionally edited. Review the change before using the manifest update command; do not bypass the check just to make it pass. |
| HTTP 403, timeout, or certificate failure during source checks | Keep the reviewed snapshot for reproduction and inspect the official page manually. Do not disable TLS verification or bypass an access restriction. |
| Source check exits with code `2` | Review the JSON report. A retrieval failure, missing anchor, or changed hash needs review; the source snapshot was not edited. |
| A PDF response is HTML | The source may have returned an error page. The parser rejects it and records the failure. |
| Guide says `needs review` | Use the official linked page and confirm current instructions. A fixed historical `--as-of` is only for demonstration, not a way to establish current information. |
| HTML is visible as code on GitHub | Download the file and open it in a browser, or read its Markdown counterpart. No hosting service is required. |

## Publication

The public repository includes source code, reviewed CSVs, attribution, tests, documentation, and examples. It excludes virtual environments, raw third-party pages, generated databases, medical records, API keys, and local settings. A GitHub Actions workflow reproduces the project; no application deployment is needed.
