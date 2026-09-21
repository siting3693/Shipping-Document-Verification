# SDOC Verification - Local Startup Manual

This is the verified guide to starting the entire Shipping Document Verification project from a clean state. It covers the backend scoring server, the processing pipeline, and the judge dashboard UI.

## 1. Prerequisites
- **Python Version**: 3.12 (or recent 3.x)
- **Required Packages**: 
  - `fastapi`, `uvicorn`, `flask`
  - `pdfplumber`, `pypdfium2`, `python-docx`, `openpyxl`
  - `google-generativeai` (for AI fallback)
- **Environment Variables**:
  - `GEMINI_API_KEY`: Required if you want the pipeline to invoke the real Gemini API for garbled PDFs. (If missing, the pipeline gracefully falls back to a deterministic `pypdfium2` reader).
- **Docker**: Optional (see Section 5), but we recommend the native Python startup (Section 4).

## 2. Project Directory
**All commands in this manual must be run from the root of the repository:**
`D:\Project\Shipping-Document-Verification`

Ensure you see folders like `server/`, `data_v2/`, `inbox/`, and `attachments/`.

## 3. First-Time Setup
If you haven't installed dependencies yet, open PowerShell and run:
```powershell
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate

# Install all backend, pipeline, and UI dependencies
pip install fastapi uvicorn flask httpx pdfplumber pypdfium2 python-docx openpyxl google-generativeai
```

## 4. Normal Startup — Preferred Method (No Docker)

You will need **three separate PowerShell windows**. 
Always ensure you are in `D:\Project\Shipping-Document-Verification` and your virtual environment is activated (`.\venv\Scripts\Activate`).

### Window 1: Start the Backend Scoring Server
The FastAPI backend serves the `/health`, `/emails`, and `/submit` endpoints.
```powershell
$env:DATA_DIR="data_v2"
$env:GROUND_TRUTH="data_v2\ground_truth.json"
uvicorn server.app:app --host 0.0.0.0 --port 8080
```
**Expected Output:** `INFO: Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)`
**How to know it's ready:** Navigate to `http://localhost:8080/health` in your browser. It should say `{"status": "ok", "emails": 520, "scoring_available": true}`.

### Window 2: Start the Web UI
The Flask dashboard visualizes the `submission.json` output.
```powershell
python app_ui.py
```
**Expected Output:** `* Running on http://127.0.0.1:5000`
**How to know it's ready:** You can visit `http://localhost:5000`, but you won't see results until you run the pipeline in Window 3.

### Window 3: Run the Pipeline (See Section 7)
*Keep Window 1 and Window 2 open and running while you execute Window 3.*

## 5. Docker Startup
If you prefer Docker, you can run the backend server inside a container instead of Window 1.
**Command:**
```powershell
docker compose up --build
```
**Expected Services & Ports:** It spins up the `inbox` service mapped to host port `8080`.
**Health Check:** Visit `http://localhost:8080/health`.
**How to Stop:** Press `CTRL+C` or run `docker compose down`.
*(Note: You still need to run the pipeline and UI natively via Python as shown in Sections 7 and 9).*

## 6. Non-Docker Fallback
Section 4 exactly describes the verified Non-Docker fallback. We inject the environment variables (`DATA_DIR` and `GROUND_TRUTH`) directly in PowerShell and launch Uvicorn. This bypasses the need for the Docker volume mounts.

## 7. Run the Pipeline
To evaluate all 520 emails, classify them, extract fields, compare them, and score them against the backend:

In **Window 3**, run:
```powershell
python main.py . --submit
```
- **`main.py .`**: Scans the current directory for `inbox/` and `attachments/`.
- **`--submit`**: Posts the final `submission.json` to the Uvicorn server at `http://localhost:8080/submit` to generate the Self-Evaluation Result.

**Expected Output:** You will see a stream of INFO logs followed by the `SDOC VERIFICATION REPORT` and the `SELF-EVALUATION RESULT` JSON. The final score will be `1.0`.

## 8. Generate / Refresh `submission.json`
`submission.json` is automatically generated every time you run `python main.py .`.
**UI Dependency:** The Flask Web UI (Window 2) directly reads `submission.json` from the disk. If you make code changes, you must re-run `python main.py .` to overwrite `submission.json`, and then refresh the browser page (F5) to see the updated dashboard.

## 9. Open the Web UI
- **Exact URL:** http://localhost:5000
- **Provided By:** The `python app_ui.py` process.
- **Expected View:** A dashboard showing "Total Processed: 520", grouped into Clean Matches (OK), Discrepancies Found (MISMATCH), and Human Review Queue (NEEDS_REVIEW).

## 10. Verify Everything (Checklist)
- [x] Backend health works (`http://localhost:8080/health` returns JSON)
- [x] Emails endpoint works (`http://localhost:8080/emails` returns list)
- [x] Sample submission endpoint works (`http://localhost:8080/sample_submission` returns JSON)
- [x] Pipeline completed (`python main.py . --submit` reaches 100%)
- [x] `submission.json` exists in the root directory
- [x] UI returns HTTP 200 (`http://localhost:5000` loads)
- [x] Dashboard displays current results (520 total items)

## 11. Test a Demo
Once the UI is loaded at http://localhost:5000, verify these specific cases visually in the tables:
- **One OK case:** Scroll to the "Clean Matches" section and find `email_001`. It will have a green `OK` badge.
- **One MISMATCH case:** Scroll to the "Discrepancies Found" section and find `email_313`. It will have a red `MISMATCH` badge listing `container_count` and `gross_weight_kg` as defect fields.
- **One NEEDS_REVIEW case:** Scroll to the "Human Review Queue" section and find `email_501`. It will have an orange `NEEDS_REVIEW` badge with the reason `wrong_doc_type`.

## 12. Stop Everything
- **FastAPI/Uvicorn (Window 1):** Click into the terminal and press `CTRL+C`.
- **Flask (Window 2):** Click into the terminal and press `CTRL+C`.
- **Docker:** If you used Docker, run `docker compose down`.

## 13. Troubleshooting
- **Port 8080 already in use:** Edit `uvicorn server.app:app --port 8080` to a different port (e.g., `8081`). If you do this, you must edit `main.py` line 25 to point to `http://localhost:8081/submit`.
- **Port 5000 already in use:** In `app_ui.py`, change `app.run(port=5000)` to `app.run(port=5001)`.
- **Docker Desktop unavailable:** Skip Docker entirely and use the Native Python instructions in Section 4.
- **Missing Python dependency:** Ensure your virtual environment is activated, then run `pip install -r requirements.txt` (or install manually as shown in Setup).
- **Missing `GEMINI_API_KEY`:** A warning log will appear during pipeline execution, but the system will gracefully mock the response using `pypdfium2`, avoiding a crash.
- **UI shows stale results:** You must re-run `python main.py .` to write fresh data to `submission.json`, then refresh the page.
- **Backend starts but UI cannot connect:** The UI reads from disk, not the backend. The backend is only queried by `main.py --submit`.

## 14. Start From Zero (Clean Restart Sequence)
1. Open PowerShell to `D:\Project\Shipping-Document-Verification`.
2. `.\venv\Scripts\Activate` (if using venv)
3. `Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd D:\Project\Shipping-Document-Verification; `$env:DATA_DIR='data_v2'; `$env:GROUND_TRUTH='data_v2\ground_truth.json'; uvicorn server.app:app --host 0.0.0.0 --port 8080"`
4. `Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd D:\Project\Shipping-Document-Verification; python app_ui.py"`
5. `python main.py . --submit`
6. Open `http://localhost:5000` in your browser.
