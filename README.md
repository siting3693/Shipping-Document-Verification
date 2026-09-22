# SheepMeal

SheepMeal is an AI-powered shipping-document verification application. It processes a mixed shipping inbox, identifies document-comparison requests, and verifies draft Bills of Lading (BLs) against their corresponding Shipping Instructions (SIs).

The system combines deterministic processing with targeted AI assistance: it classifies emails, resolves SI/BL attachments, extracts seven shipment fields, normalizes values, compares documents, and returns one of three outcomes:

- `OK`
- `MISMATCH`
- `NEEDS_REVIEW`

The FastAPI dashboard supports transparent inspection of classifications, discrepancies, and human-review cases.

## What it does

Each email in `inbox/` is assigned one of these categories:

- `BL_COMPARISON`
- `SI_REQUEST`
- `INVOICE_QUERY`
- `GENERAL`
- `SPAM`

Only `BL_COMPARISON` emails proceed to document verification. For those emails, SheepMeal:

1. Identifies the relevant SI and BL attachments.
2. Parses TXT, PDF, DOCX, and XLSX documents.
3. Extracts and normalizes seven canonical shipment fields.
4. Compares the SI and BL deterministically.
5. Returns `OK`, `MISMATCH`, or `NEEDS_REVIEW` with supporting details for review.

### Fields compared

- shipper
- consignee
- notify party
- port of loading
- port of discharge
- container count
- gross weight (kg)

`MISMATCH` results identify the defective fields. `NEEDS_REVIEW` is used when a dependable decision cannot be made, for example because of `missing_attachment`, `wrong_doc_type`, `unreadable`, or `missing_value`.

## Architecture

SheepMeal uses a hybrid approach:

- Deterministic code handles normalization, comparison, decision logic, and submission generation.
- The Gemini API is an optional fallback for difficult or garbled document extraction.
- FastAPI provides the dashboard and application API.
- Google Cloud Run hosts the deployed application; Google Secret Manager supplies the Gemini API key.

Gemini is a targeted extraction fallback, not the final authority for document comparison.

```text
Inbox -> Email classification -> BL comparison -> Seven-field comparison
                                              -> OK / MISMATCH / NEEDS_REVIEW
```

## Quick start (Windows)

Prerequisite: Python 3.11+ installed and available on `PATH`.

Start the complete local application:

```powershell
.\start.ps1
```

If PowerShell blocks script execution:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

The launcher prepares the virtual environment, installs dependencies, starts the FastAPI scorer on port `8080`, starts the legacy local dashboard on port `5000`, runs the pipeline, and opens the dashboard.

Stop services started by the launcher:

```powershell
.\start.ps1 -Stop
```

## Manual local run

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the FastAPI application:

```powershell
python -m uvicorn server.app:app --host 0.0.0.0 --port 8080
```

Open the primary dashboard at `http://localhost:8080/`. Check service health at `http://localhost:8080/health`.

When processing has not been initialized, the dashboard can trigger it automatically through `POST /api/initialize`. You can also run the pipeline directly:

```powershell
python main.py .
```

This generates `submission.json`.

## Local self-evaluation

Self-evaluation is intended for local development only. The reference data must never be exposed by a public deployment.

Start the FastAPI application with local evaluation data configured:

```powershell
$env:DATA_DIR = "data_v2"
$env:GROUND_TRUTH = "data_v2\ground_truth.json"
python -m uvicorn server.app:app --host 0.0.0.0 --port 8080
```

Then submit the pipeline output:

```powershell
python main.py . --submit
```

This creates `submission.json` and `score_result.json`. The local scorer compares the result with the private reference set without returning the reference answers.

## Useful API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health and email count |
| `GET` | `/api` | API endpoint information |
| `GET` | `/emails` | Inbox email records |
| `GET` | `/emails/{email_id}` | A single email record |
| `GET` | `/api/case/{email_id}` | Detailed case inspection |
| `GET` | `/sample_submission` | Required submission schema |
| `POST` | `/api/initialize` | Initialize the verification pipeline |
| `POST` | `/submit` | Local self-evaluation submission |

## Gemini fallback

SheepMeal performs deterministic document processing first. Gemini is only used as a fallback for genuinely difficult or garbled extractions.

For local development, create `.env` in the project root:

```dotenv
GEMINI_API_KEY=your_key_here
```

Do not commit `.env` or a real API key. The application continues using its local fallback when Gemini is unavailable.

## Docker

Build and run the application image:

```powershell
docker build -t sheepmeal .
docker run --rm -p 8080:8080 -e GEMINI_API_KEY=your_key_here sheepmeal
```

For deployed environments, use Secret Manager rather than passing a key in source code or deployment commands. See [dockerREADME.md](dockerREADME.md) for the separate dataset/scoring-server Docker setup.

## Google Cloud Run deployment

The application is deployed as the `sheepmeal` Cloud Run service in `asia-southeast1`. It serves both the dashboard and API.

Deploy from the project root:

```powershell
gcloud run deploy sheepmeal `
  --source . `
  --region asia-southeast1 `
  --port 8080 `
  --allow-unauthenticated `
  --max-instances 1 `
  --update-secrets=GEMINI_API_KEY=GEMINI_API_KEY:1
```

The public deployment must not include `ground_truth.json` or any other private local-evaluation data.

Public prototype: <https://sheepmeal-439256477142.asia-southeast1.run.app>

## Project layout

```text
main.py                   End-to-end classification and verification pipeline
classify_emails.py        Email classification
attachment_resolver.py    SI/BL attachment identification
document_parser.py        TXT, PDF, DOCX, and XLSX parsing
field_extraction.py       Canonical field extraction
comparison_engine.py      Deterministic normalization and SI/BL comparison
gemini_fallback.py        Targeted Gemini extraction fallback
server/                   FastAPI application and local self-evaluation support
app_ui.py                 Legacy local Flask dashboard
inbox/                    Email records
attachments/              Shipping-document attachments
data_v2/                  Evaluation dataset and private local scoring data
```

## Output format

`submission.json` contains an entry for every email. Example:

```json
{
  "email_001": {
    "category": "BL_COMPARISON",
    "status": "MISMATCH",
    "review_reason": null,
    "has_defect": true,
    "defect_fields": ["consignee"]
  }
}
```

Use `sample_submission.json` as the authoritative submission schema.

## Additional documentation

- [STARTUP.md](STARTUP.md) — launcher behavior and logs
- [RUN_MANUAL.md](RUN_MANUAL.md) — local setup, Docker, and troubleshooting
- [server/README.md](server/README.md) — FastAPI and self-evaluation details
- [data_v2/README.md](data_v2/README.md) — dataset and submission details