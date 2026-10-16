# Byomkesh AI — Phase 3 Manual Verification & Integration Guide

This guide provides copy-and-paste PowerShell commands to run and verify the complete end-to-end Byomkesh AI system: FastAPI Backend, React Investigation Dashboard, 9-Stage Processing Pipeline, Artifact Discovery, Draft PDF Download, and the Preserved 3D Crime Scene Reconstruction Viewer.

---

## 1. Prerequisites

- **OS**: Windows (PowerShell 5.1 or PowerShell 7+)
- **Python**: 3.11+ (virtual environment located at `backend/.venv`)
- **Node.js**: v20+ or v22+
- **Repository Root**: `c:\Github\Major_Project_2nd_repo`

---

## 2. Step-by-Step Workflow Instructions

### Step 1: Start the FastAPI Backend
Open a PowerShell terminal:

```powershell
cd c:\Github\Major_Project_2nd_repo\backend
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
*Expected Output:*
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Step 2: Start the React Development Server
Open a second PowerShell terminal:

```powershell
cd c:\Github\Major_Project_2nd_repo\frontend
npm run dev
```
*Expected Output:*
```
  VITE v8.2.1  ready in ~200 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 3: Open the Frontend Application
Navigate to [http://localhost:5173](http://localhost:5173) in your browser (Google Chrome or Microsoft Edge recommended).

### Step 4: Verify the API Connection
- Observe the top right header badge: it will display `FASTAPI ONLINE` with a green indicator dot.
- If the backend is stopped or unreachable, it will display `BACKEND OFFLINE` with a red indicator dot and an inline retry option.

### Step 5: Create an Investigation Case
1. On the Dashboard, click **Create New Case** (top right).
2. Enter:
   - **Case Identifier**: `CASE-CR-2026-089` (or leave blank to auto-generate)
   - **Title**: `Demonstration Hit & Run Incident — Outer Ring Road`
   - **Investigation Summary**: `Collision between heavy transport vehicle and two-wheeler near T-point.`
3. Click **Create Case**. The case workspace will open automatically.

### Step 6: Upload Synthetic Evidence Documents
1. In the **Evidence Documents** tab, drag and drop or browse files to stage documents.
2. Example synthetic documents are available in the repository at `BYOMKESH_E2E_CASE_001/`:
   - `BYOMKESH_E2E_CASE_001\FIR.pdf`
   - `BYOMKESH_E2E_CASE_001\complaint.pdf`
   - `BYOMKESH_E2E_CASE_001\witness_statement_01.pdf`
   - `BYOMKESH_E2E_CASE_001\medical_report.pdf`
   - `BYOMKESH_E2E_CASE_001\seizure_memo.pdf`
3. Click **Upload Files to Case Workspace**.
4. Verify that each file shows `uploaded` status and appears in the **Current Case Evidence Inventory** table.

### Step 7: Start Investigation Processing
1. Navigate to the **Pipeline & Processing** tab.
2. Select options:
   - Check **Deterministic Mock LLM** (default: enabled for offline demonstration without requiring Google Gemini API quotas).
   - Leave **Reuse Cached OCR** unchecked for a fresh processing run.
3. Click the explicit button: **Start Investigation Processing**.

### Step 8: Monitor the 9-Stage Job
- The job status badge transitions to `RUNNING PIPELINE`.
- The system polls `GET /api/v1/jobs/{job_id}` every 1.5 seconds.
- Watch each stage update from `PENDING` to `✓ COMPLETED`:
  1. `Document Intake`
  2. `OCR & Vision Extraction`
  3. `Document Parsing & Classification`
  4. `Investigation Knowledge Graph`
  5. `Canonical Investigation`
  6. `Evidence Validation`
  7. `Case Context Assembly`
  8. `Legal Reasoning & Penal Code Mapping`
  9. `Charge-Sheet Draft Population`
- Once stage 9 completes, polling automatically stops and status displays `✓ COMPLETED`.

### Step 9: View Validation Findings & Legal Analysis
1. Navigate to the **Validation & Legal Findings** tab.
2. Inspect:
   - **Validation Disposition**: displays `⚖ DRAFT ALLOWED (REVIEW REQUIRED)` (or `REVIEW REQUIRED` / `FINAL BLOCKED`).
   - **Legal Notice**: highlights that `DRAFT_ALLOWED` is an automated validation milestone, not judicial approval.
   - **Completeness Score**: calculated percentage of verified legal and evidential elements.
   - **Legal Reasoning**: recommended BNS sections (e.g. BNS 106, 281), substantiated ingredients, and investigative facts.

### Step 10: View Charge-Sheet Draft & Download PDF
1. Navigate to the **Charge-Sheet Draft & PDF** tab.
2. Inspect the populated draft form fields: Police Station, FIR Number, Incident Date/Time, Complainant, Accused, and Brief Facts.
3. Verify that the document is clearly labeled: `CONFIDENTIAL DRAFT — NOT JUDICIALLY SUBMITTED`.
4. Click **Download Draft PDF**. The browser downloads `draft_chargesheet_CASE-CR-2026-089.pdf`.
5. View the embedded PDF preview directly inside the browser viewport.

### Step 11: Launch the 3D Crime Scene Reconstruction Viewer
1. In the header bar, click **3D Scene Simulation** (or click **Launch 3D Crime Scene** inside any case).
2. The interactive Three.js / React Three Fiber viewport loads with Arkham Detective Mode HUD:
   - Orbit controls: rotate, pan, and zoom around the collision site.
   - Kinematics timeline: play, scrub, and pause keyframe trajectory events.
   - Tactical camera presets: tactical overhead, driver perspective, witness perspective.
   - Evidence markers and vehicle telemetry HUD.
3. Click the top-right button: **← RETURN TO INVESTIGATION WORKSPACE** to switch seamlessly back to the case dashboard.

---

## 3. Automated Test Verification Commands

### Run Frontend Automated Test Suite
From `c:\Github\Major_Project_2nd_repo\frontend`:
```powershell
npm test
```
*Expected Output:*
```
# tests 16
# pass 16
# fail 0
```

### Run Frontend Production Build
```powershell
npm run build
```
*Expected Output:*
```
✓ built in ~1.1s
```

### Run Backend Pytest Suite
From `c:\Github\Major_Project_2nd_repo\backend`:
```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```
*Expected Output:*
```
156 passed, 1 skipped, 1 warning, 10 subtests passed
```
