# Byomkesh AI — FastAPI Service Layer Guide (Phase 2)

## Overview

The Byomkesh AI backend exposes the typed 9-stage investigation and charge-sheet drafting pipeline as a production-ready asynchronous REST API.

```
React Frontend (Future Phase)
       │
       ▼  HTTP / JSON & Multipart
FastAPI Service Layer (`backend/src/api/`)
       │
       ├── Case Management & Document Intake (`CaseService`)
       │     └─ Local filesystem isolation under `CASE_<hex>/`
       ├── Asynchronous Pipeline Execution (`JobService`)
       │     └─ In-process worker thread executing `run_production_workflow()`
       └── Artifact & PDF Delivery (`ArtifactService`)
             └─ Sandboxed draft PDF delivery (`ChargeSheet_v1_review.pdf`)
```

---

## 1. Installation & Startup

### Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- Virtual environment at `backend/.venv`

### Dependency Installation
From the `backend/` directory:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Running the API Server
Start the Uvicorn server on `127.0.0.1:8000`:
```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI documentation is available at:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 2. Configuration & Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `API_HOST` | `127.0.0.1` | Network binding interface. |
| `API_PORT` | `8000` | Port for the Uvicorn HTTP server. |
| `OUTPUT_DIR` | `output` | Managed root directory for all case storage and outputs. |
| `MAX_UPLOAD_FILE_SIZE_BYTES` | `104857600` (100 MB) | Maximum permitted size for any single uploaded document. |
| `MAX_CASE_UPLOAD_SIZE_BYTES` | `524288000` (500 MB) | Maximum cumulative size of all uploaded files in one case. |
| `GEMINI_API_KEY` | *(None)* | Google Gemini API key required for live OCR and parsing. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Model identifier used for OCR and structured extraction. |
| `BYOMKESH_MOCK_LLM` | `0` | When set to `1`, forces deterministic offline mock execution. |
| `LEGAL_REFERENCE_PATH` | `references/legal/bns_sections.json` | Path to the versioned BNS legal reference dataset. |
| `LEGAL_REFERENCE_VERSION` | `bns-2023-2024-07-01` | Expected version tag of the legal reference dataset. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed frontend origins. |

---

## 3. API Endpoints

### A. Health & Readiness

#### `GET /health`
Liveness probe indicating whether the server process is alive.
- **Status**: `200 OK`
- **Response**:
  ```json
  {
    "status": "ok",
    "service": "byomkesh-ai",
    "version": "1.0.0"
  }
  ```

#### `GET /ready`
Readiness probe verifying storage accessibility and legal reference dataset availability without making external LLM calls.
- **Status**: `200 OK` (or `503 Service Unavailable` if checks fail)
- **Response**:
  ```json
  {
    "status": "ready",
    "ready": true,
    "checks": {
      "storage_root": true,
      "legal_reference": true,
      "gemini_configured": false
    },
    "details": {
      "storage_root": "Accessible at C:\\Github\\Major_Project_2nd_repo\\backend\\output",
      "legal_reference": "Valid version 'bns-2023-2024-07-01' at bns_sections.json",
      "gemini_configured": "API key not set (mock mode required for processing)"
    }
  }
  ```

---

### B. Case Management

#### `POST /api/v1/cases`
Creates a new case workspace.
- **Status**: `201 Created`
- **Request Body (Optional)**:
  ```json
  {
    "case_id": "case-central-2026-42",
    "title": "Central PS Assault Case",
    "description": "Assault at Market Road involving FIR 42/2026."
  }
  ```
- **Response**:
  ```json
  {
    "case_id": "case-central-2026-42",
    "status": "created",
    "created_at": "2026-10-15T17:10:00.000000Z",
    "storage_key": "CASE_8a3461983b2e597bb43fad0a401c11d4"
  }
  ```

#### `GET /api/v1/cases`
Lists all known case workspaces.
- **Status**: `200 OK`
- **Response**:
  ```json
  {
    "cases": [
      {
        "case_id": "case-central-2026-42",
        "created_at": "2026-10-15T17:10:00.000000Z",
        "document_count": 5,
        "status": "processed",
        "validation_disposition": "draft_allowed",
        "review_status": "review_required"
      }
    ],
    "total": 1
  }
  ```

#### `GET /api/v1/cases/{case_id}`
Retrieves detailed metadata, uploaded document list, and processing dispositions for a specific case.
- **Status**: `200 OK` (or `404 Not Found`)
- **Response**:
  ```json
  {
    "case_id": "case-central-2026-42",
    "created_at": "2026-10-15T17:10:00.000000Z",
    "title": "Central PS Assault Case",
    "description": "Assault at Market Road involving FIR 42/2026.",
    "status": "processed",
    "document_count": 2,
    "documents": [
      {
        "document_id": "e9d48276-1234-5678-90ab-cdef12345678",
        "original_filename": "FIR.pdf",
        "stored_filename": "e9d48276-1234-5678-90ab-cdef12345678_FIR.pdf",
        "size_bytes": 2531,
        "media_type": "application/pdf",
        "uploaded_at": "2026-10-15T17:11:00.000000Z"
      }
    ],
    "validation_disposition": "draft_allowed",
    "review_status": "review_required",
    "artifacts_available": [
      "chargesheet/draft/ChargeSheet_v1_review.pdf",
      "chargesheet/draft/ChargeSheet_v1_data.json"
    ]
  }
  ```

---

### C. Document Upload

#### `POST /api/v1/cases/{case_id}/documents`
Uploads one or more case documents via `multipart/form-data`.
- **Supported Formats**: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.docx`, `.mp4`, `.mov`, `.wav`
- **Status**: `201 Created` (or `400 Bad Request`, `413 Payload Too Large`, `415 Unsupported Media Type`)
- **Example cURL**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/cases/case-central-2026-42/documents" \
    -F "files=@FIR.pdf" \
    -F "files=@medical_report.pdf"
  ```
- **Response**:
  ```json
  {
    "case_id": "case-central-2026-42",
    "uploaded_count": 2,
    "failed_count": 0,
    "documents": [
      {
        "document_id": "e9d48276-1234-5678-90ab-cdef12345678",
        "original_filename": "FIR.pdf",
        "size_bytes": 2531,
        "media_type": "application/pdf",
        "status": "uploaded",
        "errors": []
      },
      {
        "document_id": "84e3c5fe-2345-6789-01bc-def234567890",
        "original_filename": "medical_report.pdf",
        "size_bytes": 2230,
        "media_type": "application/pdf",
        "status": "uploaded",
        "errors": []
      }
    ]
  }
  ```

---

### D. Workflow Processing

#### `POST /api/v1/cases/{case_id}/process`
Initiates the 9-stage investigation workflow in a background worker thread.
- **Status**: `202 Accepted` (or `400 Bad Request` if no documents, `409 Conflict` if already running)
- **Request Body (Optional)**:
  ```json
  {
    "resume": false,
    "mock_llm": true
  }
  ```
- **Response**:
  ```json
  {
    "job_id": "67b93c8d-3456-7890-12cd-ef3456789012",
    "case_id": "case-central-2026-42",
    "status": "queued",
    "message": "Case processing workflow queued successfully."
  }
  ```

---

### E. Job Status

#### `GET /api/v1/jobs/{job_id}`
Returns the truthful execution status of the background workflow.
- **Status**: `200 OK` (or `404 Not Found`)
- **Response**:
  ```json
  {
    "job_id": "67b93c8d-3456-7890-12cd-ef3456789012",
    "case_id": "case-central-2026-42",
    "status": "completed",
    "created_at": "2026-10-15T17:12:00.000000Z",
    "started_at": "2026-10-15T17:12:00.050000Z",
    "completed_at": "2026-10-15T17:12:08.500000Z",
    "current_stage": null,
    "completed_stages": [
      "document_intake",
      "ocr",
      "document_parsing",
      "investigation_knowledge_graph",
      "canonical_investigation",
      "evidence_validation",
      "case_context",
      "legal_reasoning",
      "chargesheet_population"
    ],
    "stage_records": [
      {"stage_name": "document_intake", "status": "completed", "error_message": null},
      {"stage_name": "ocr", "status": "completed", "error_message": null},
      {"stage_name": "document_parsing", "status": "completed", "error_message": null},
      {"stage_name": "investigation_knowledge_graph", "status": "completed", "error_message": null},
      {"stage_name": "canonical_investigation", "status": "completed", "error_message": null},
      {"stage_name": "evidence_validation", "status": "completed", "error_message": null},
      {"stage_name": "case_context", "status": "completed", "error_message": null},
      {"stage_name": "legal_reasoning", "status": "completed", "error_message": null},
      {"stage_name": "chargesheet_population", "status": "completed", "error_message": null}
    ],
    "error": null,
    "validation_disposition": "draft_allowed",
    "artifacts_available": [
      "CASE_8a3461983b2e597bb43fad0a401c11d4/processed/upload_manifest.json",
      "CASE_8a3461983b2e597bb43fad0a401c11d4/processed/chargesheet/draft/ChargeSheet_v1_review.pdf"
    ]
  }
  ```

---

### F. Artifacts & PDF Retrieval

#### `GET /api/v1/cases/{case_id}/artifacts`
Lists metadata for all artifacts generated by the workflow.
- **Status**: `200 OK` (or `404 Not Found`)
- **Response**:
  ```json
  {
    "case_id": "case-central-2026-42",
    "artifacts": [
      {"name": "upload_manifest", "relative_path": "processed/upload_manifest.json", "size_bytes": 1045, "exists": true},
      {"name": "investigation_graph", "relative_path": "processed/graph/investigation_graph.json", "size_bytes": 5420, "exists": true},
      {"name": "canonical_investigation", "relative_path": "processed/canonical/canonical_investigation.json", "size_bytes": 7820, "exists": true},
      {"name": "validation_report", "relative_path": "processed/validation/validation_report.json", "size_bytes": 356, "exists": true},
      {"name": "case_context", "relative_path": "processed/context/case_context.json", "size_bytes": 6240, "exists": true},
      {"name": "legal_findings", "relative_path": "processed/legal/legal_findings.json", "size_bytes": 1820, "exists": true},
      {"name": "chargesheet_data", "relative_path": "processed/chargesheet/draft/ChargeSheet_v1_data.json", "size_bytes": 49379, "exists": true},
      {"name": "chargesheet_draft", "relative_path": "processed/chargesheet/draft/ChargeSheet_v1_review.pdf", "size_bytes": 12645, "exists": true},
      {"name": "review_state", "relative_path": "processed/chargesheet/review_state.json", "size_bytes": 1167, "exists": true}
    ],
    "draft_pdf_available": true
  }
  ```

#### `GET /api/v1/cases/{case_id}/artifacts/chargesheet.pdf`
Streams the generated draft charge-sheet PDF file.
- **Status**: `200 OK` (or `404 Not Found` if not ready)
- **Headers**:
  - `Content-Type`: `application/pdf`
  - `Content-Disposition`: `inline; filename="draft_chargesheet_case-central-2026-42.pdf"`

---

## 4. End-to-End PowerShell Workflow Example

```powershell
# 1. Check Service Health
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get

# 2. Check Service Readiness
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ready" -Method Get

# 3. Create a Case
$createRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases" -Method Post `
  -ContentType "application/json" `
  -Body '{"case_id": "demo-case-001", "title": "Demonstration Case"}'

# 4. Upload Documents
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"
$pdfBytes = [System.IO.File]::ReadAllBytes("BYOMKESH_E2E_CASE_001\FIR.pdf")
$pdfText = [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($pdfBytes)

$bodyLines = (
    "--$boundary",
    'Content-Disposition: form-data; name="files"; filename="FIR.pdf"',
    'Content-Type: application/pdf',
    '',
    $pdfText,
    "--$boundary--"
) -join $LF

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases/demo-case-001/documents" `
  -Method Post `
  -ContentType "multipart/form-data; boundary=$boundary" `
  -Body ([System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes($bodyLines))

# 5. Start Processing with Mock LLM
$jobRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases/demo-case-001/process" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"mock_llm": true}'
$jobId = $jobRes.job_id

# 6. Poll Job Status
do {
  Start-Sleep -Seconds 1
  $status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/jobs/$jobId" -Method Get
} while ($status.status -in @("queued", "running"))

$status

# 7. List Artifacts
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases/demo-case-001/artifacts" -Method Get

# 8. Download Draft PDF
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/cases/demo-case-001/artifacts/chargesheet.pdf" `
  -OutFile "downloaded_draft.pdf"
```

---

## 5. Security & Deployment Limitations

> [!WARNING]
> **No Authentication Built-In**: This service layer does not provide user authentication, API token validation, or role-based access control. It is designed for private local network communication with a companion frontend. It **must not** be exposed directly to the public internet without an API gateway, reverse proxy with TLS/auth, or VPN perimeter.

> [!IMPORTANT]
> **Local In-Process Job Durability**: Background workflow tasks run in local Python daemon threads managed by `JobService`. If the server process stops or restarts while a job is running, the in-process job state will be interrupted. A production distributed cluster will require durable external queues (e.g. Celery/RabbitMQ) in future phases.

> [!NOTE]
> **Filesystem Sandboxing**: All case directories and downloads are strictly validated using `is_relative_to(storage_root)`. Path traversal attempts (such as `../` or absolute drive roots) are rejected with HTTP 400 or 403.
