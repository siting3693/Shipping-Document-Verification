# Shipping Document Verification - Startup Guide

This document explains how to use the single-command startup script (`start.ps1`) to orchestrate the entire project.

## Usage Instructions

### First Time Setup
If you are running this for the first time, you may need to bypass the PowerShell execution policy:
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

### Normal Startup
For normal usage, just run:
```powershell
.\start.ps1
```

### Stopping the Services
To cleanly stop the background services (FastAPI and Flask) started by the launcher:
```powershell
.\start.ps1 -Stop
```

## What It Starts

The `start.ps1` script performs the following automatically:
1. **Environment Initialization:** Automatically detects/creates a Python virtual environment (`.venv`) and installs required dependencies.
2. **Environment Variables:** Loads your `.env` file containing secrets like `GEMINI_API_KEY` (without printing it).
3. **FastAPI Backend (Port 8080):** Starts the scoring API backend in the `server/` directory and polls until it's ready.
4. **Flask UI (Port 5000):** Starts the dashboard UI and polls until it's responsive.
5. **Execution Pipeline:** Triggers the main pipeline (`python main.py . --submit`) using the virtual environment, processing all emails.
6. **Results Display:** Reads `score_result.json` and prints a secure, high-level summary of the pipeline evaluation.
7. **Browser Launch:** Automatically opens the Flask dashboard in your default web browser.

## Logs and Troubleshooting

All background processes output their streams to the `logs/` directory:
- **`logs/backend.log` & `logs/backend_error.log`**: Standard output and errors for the FastAPI backend.
- **`logs/ui.log` & `logs/ui_error.log`**: Standard output and errors for the Flask web UI.
- **`logs/pipeline.log`**: Output of the `main.py` document processing pipeline.

**Troubleshooting Tips:**
- **Port Conflicts:** The script checks if ports 8080 or 5000 are already in use by this application. If they are used by an unknown service, the script will safely abort. You can check what is using the port via `netstat -ano`.
- **Backend/UI Fails to Start:** Check the respective `_error.log` in the `logs/` folder to see Python tracebacks (e.g., missing modules or syntax errors).
- **Environment:** If the virtual environment is corrupt, you can safely delete the `.venv` folder and run `.\start.ps1` again.
