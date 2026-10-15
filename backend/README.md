# BYOMKESH Backend

This directory contains the Python implementation of the BYOMKESH investigation-to-charge-sheet pipeline.

The active backend is a **command-line workflow**, not a continuously running HTTP server. It accepts a directory of case documents, validates and stores them, sends OCR/parsing work to Gemini, builds typed investigation structures, validates evidence, creates constrained legal findings, and produces charge-sheet JSON/PDF artifacts for officer review.

> **Security:** never commit `.env`, API keys, or generated case artifacts containing sensitive case material. If an API key has been shared publicly, revoke it and create a replacement.

## 1. High-level architecture

```text
Input documents
      |
      v
Document intake and safe storage
      |
      v
OCR (Gemini for PDF/PNG/JPEG)
      |
      v
Typed document parsing (Gemini JSON extraction)
      |
      v
Investigation knowledge graph
      |
      v
Canonical investigation projection
      |
      v
Evidence/provenance validation
      |
      v
Compact CaseContext
      |
      v
Version-pinned legal reasoning
      |
      v
ChargeSheetData + validation
      |
      v
ReportLab review PDF + JSON + review state
```

The active production composition is defined in `src/workflow/production.py`. It registers these stages in this fixed order:

1. `document_intake`
2. `ocr`
3. `document_parsing`
4. `investigation_knowledge_graph`
5. `canonical_investigation`
6. `evidence_validation`
7. `case_context`
8. `legal_reasoning`
9. `chargesheet_population`

The workflow passes an immutable Pydantic-based `WorkflowContext` between stages. Stages return a new context rather than mutating the previous one. Document IDs, SHA-256 checksums, graph provenance, source references, confidence, validation status, and legal status are retained across boundaries.

Gemini is deliberately limited to:

- raw OCR;
- document-local structured extraction into typed parser schemas.

The normal production legal reasoner, graph builder, canonicalizer, validator, charge-sheet populator, formatter, renderer, and review lifecycle are deterministic Python code. An optional injected legal client is constrained by the local legal-reference dataset and an evidence allow-list.

## 2. Running the backend

Run all commands from this directory (`backend/`). No virtual environment is required if you intentionally want to use the selected global Python installation.

### Install dependencies

```powershell
py -3.13 -m pip install -r requirements.txt
```

`requirements.txt` contains:

- `pydantic` — typed immutable domain models;
- `python-dotenv` — loads `.env`;
- `google-genai` — Gemini OCR and parsing adapters;
- `reportlab` — PDF rendering;
- `groq`, `json5`, and `json-repair` — retained legacy modules;
- `pytest` — tests.

### Configure `.env`

`.env` is loaded by `src/config.py`. The file is local configuration and should not be committed or pasted into chat.

| Variable | Required by active pipeline | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | Yes | Gemini OCR and parser authentication |
| `GEMINI_MODEL` | Yes in practice | Gemini model used by OCR/parser clients |
| `LEGAL_REFERENCE_PATH` | Yes | Local legal-reference JSON path |
| `LEGAL_REFERENCE_VERSION` | Yes | Exact version pin for the legal dataset |
| `MAX_UPLOAD_FILE_SIZE_BYTES` | No | Per-file upload limit; default 100 MiB |
| `MAX_CASE_UPLOAD_SIZE_BYTES` | No | Aggregate case limit; default 500 MiB |
| `LLM_PROVIDER` | Legacy only | Provider selection for `src/llm.py` |
| `GROQ_API_KEY` | Legacy only | Groq client key |
| `GROQ_MODEL` | Legacy only | Groq model |
| `INPUT_DIR` | Legacy/default only | Default legacy input directory |
| `OUTPUT_DIR` | Legacy/default only | Default output directory |

Example non-secret settings:

```dotenv
LEGAL_REFERENCE_PATH=references/legal/bns_sections.json
LEGAL_REFERENCE_VERSION=bns-2023-2024-07-01
GEMINI_MODEL=<model-available-to-your-account>
```

### Run a case

```powershell
py -3.13 -m src.main --case-id "case-001" --input-dir .\BYOMKESH_E2E_CASE_001 --output-dir .\output
```

`--case-id` accepts a UUID or a stable external identifier. A non-UUID identifier is deterministically converted to a UUID5 value, which lets `--resume` find the same case workspace on later runs.

Useful options:

- `--gemini-api-key` — overrides `GEMINI_API_KEY` for one run;
- `--gemini-model` — overrides `GEMINI_MODEL` for one run;
- `--resume` — reuses only checksum-validated OCR artifacts and manifests.

Resume example:

```powershell
py -3.13 -m src.main --case-id "case-001" --input-dir .\BYOMKESH_E2E_CASE_001 --output-dir .\output --resume
```

### Test and quality commands

```powershell
py -3.13 -m pytest -q
py -3.13 -m compileall -q src tests
```

The normal tests use injected/fake providers and do not require external Gemini calls. `tests/test_gemini_sdk_smoke.py` is an opt-in SDK smoke test.

## 3. Complete backend structure

Generated Python bytecode under `__pycache__/` is not source code and is intentionally omitted below. `output/` is also generated runtime data; its layout is documented in section 7.

```text
backend/
├── .env                                  # Local secrets and runtime configuration; do not commit
├── .gitignore                            # Ignores secrets, caches, environments, and generated output
├── requirements.txt                      # Python dependencies
├── BYOMKESH_PROJECT_HANDOFF.md           # Historical engineering handoff and design notes
├── README.md                             # This document
├── BYOMKESH_E2E_CASE_001/                # PDF fixture corpus used by typed end-to-end tests/manual runs
├── CASE-002-Byomkesh/                    # Larger PDF case corpus
├── dummy_case/                            # Legacy JSON fixture corpus
├── docs/form_if5/                         # Supplied IF-5 form observations and mapping notes
├── references/legal/                      # Local version-pinned legal data
├── src/                                   # Python source
├── tests/                                 # Automated tests
├── output/                                # Generated case artifacts; not source of truth
└── tmp/                                   # Temporary/regression files
```

### 3.1 Input fixtures

#### `BYOMKESH_E2E_CASE_001/`

The active small PDF corpus contains:

- `FIR.pdf` — first-information report;
- `complaint.pdf` — complaint document;
- `fsl_report.pdf` — forensic science laboratory report;
- `medical_report.pdf` — medical report;
- `seizure_memo.pdf` — seizure documentation;
- `site_plan.pdf` — scene/site plan;
- `vehicle_inspection.pdf` — vehicle inspection report;
- `witness_statement_01.pdf` and `witness_statement_02.pdf` — witness statements.

#### `CASE-002-Byomkesh/`

The larger corpus contains:

- `accused_statement_3.pdf` — accused statement;
- `annexures_3.pdf` — annexure index/material;
- `arrest_memo_3.pdf` — arrest memo;
- `case_diary_3.pdf` — case diary;
- `cctv_report_3.pdf` — CCTV report/metadata;
- `complaint_3.pdf` — complaint;
- `evidence_list_3.pdf` — evidence list;
- `fir_3.pdf` — FIR;
- `fsl_report_3.pdf` — FSL report;
- `master_case_3.pdf` — master case document;
- `medical_report_3.pdf` — medical report;
- `postmortem_report_3.pdf` — postmortem report;
- `seizure_memo_3.pdf` — seizure memo;
- `site_plan_3.pdf` — site plan;
- `spot_panchnama_3.pdf` — spot panchnama;
- `timeline_3.pdf` — timeline;
- `vehicle_inspection_3.pdf` — vehicle inspection;
- `witness_statement_1_3.pdf` and `witness_statement_2_3.pdf` — witness statements.

#### `dummy_case/`

These JSON files belong to the retained legacy pipeline rather than the active typed PDF workflow:

`accused_statement.json`, `annexures.json`, `arrest_memo.json`, `case_diary.json`, `cctv_report.json`, `complaint.json`, `evidence_list.json`, `fir.json`, `fsl_report.json`, `master_case.json`, `medical_report.json`, `postmortem_report.json`, `seizure_memo.json`, `site_plan.json`, `spot_panchnama.json`, `timeline.json`, `vehicle_inspection.json`, `witness_statement_1.json`, and `witness_statement_2.json`.

### 3.2 Documentation and legal data

#### `docs/form_if5/`

- `field_inventory.md` — inventory of fields observed in the supplied IF-5 charge-sheet form;
- `layout_reference.md` — observations about form layout and pagination;
- `mapping_reference.md` — mapping rules from `CaseContext` and legal findings to charge-sheet fields. It also documents how unavailable, review-required, and final-blocked information should be presented.

#### `references/legal/bns_sections.json`

Local legal-reference dataset. `LocalLegalReferenceProvider` validates this file and pins every record to `LEGAL_REFERENCE_VERSION`. The current repository dataset is intentionally small and must not be treated as a complete legal corpus.

## 4. Source file reference

This section lists every source file currently present under `src/` and its responsibility.

### 4.1 Root `src/` files

| File | Responsibility |
|---|---|
| `src/__init__.py` | Marks `src` as a Python package. |
| `src/config.py` | Loads `.env` and exposes environment-backed configuration through `Config`. |
| `src/main.py` | Active CLI entry point; parses arguments, discovers uploads, runs production workflow, prints stage/artifact summaries, and returns process status. |
| `src/utils.py` | Retained legacy JSON/file helper functions. |
| `src/case_summary.json` | Legacy scene-projector fact-ledger input. |
| `src/llm.py` | Retained Groq/Gemini text-generation helper; not used by the active typed production composition. |
| `src/loader.py` | Retained JSON-directory loader for the legacy path. |
| `src/models.py` | Retained mutable legacy `CaseContext` dataclass/models. |
| `src/prompt_builder.py` | Retained broad legacy prompt builder for direct LLM charge-sheet generation. |
| `src/pdf_generator.py` | Retained legacy LLM-response-to-PDF generator. |
| `src/test_scene.py` | Standalone scene projection/demo script, separate from the pytest suite. |
| `src/test_trellis.py` | Standalone TRELLIS/3D generation smoke script. |

### 4.2 `src/workflow/`

The workflow package provides the generic orchestration mechanism. It should not contain document-specific business rules.

| File | Responsibility |
|---|---|
| `__init__.py` | Package exports. |
| `context.py` | Immutable `WorkflowContext`, `ContextItem`, `GeneratedArtifact`, and workflow result structures passed between stages. |
| `contracts.py` | Backward-compatible workflow contract exports. |
| `engine.py` | Runs registered stages in order, skips completed/non-runnable stages, captures failures, and produces an execution report. |
| `exceptions.py` | Workflow/stage exception types. |
| `production.py` | Composition root: creates all active clients, providers, stages, and fixed `STAGE_ORDER`. |
| `registry.py` | Ordered stage registry with duplicate/order safety. |
| `stage.py` | Base `WorkflowStage` contract, including stage name, criticality, `can_run`, and `execute`. |
| `state.py` | Immutable stage statuses, execution records, timestamps, and workflow execution reports. |

`WorkflowEngine` enforces that a stage returns a `WorkflowContext` for the same case ID. A failed critical stage stops the pipeline. In production, intake/OCR/parser and downstream stages are effectively critical because later stages cannot produce meaningful results without their inputs.

### 4.3 `src/domain/`

| File | Responsibility |
|---|---|
| `__init__.py` | Domain exports. |
| `common.py` | Frozen Pydantic base models, confidence/status enums, source locations, provenance, and common value types. |
| `documents.py` | `SourceDocument`, document types, validation status, extraction state, storage metadata, and upload-related document contracts. |
| `parsed_documents.py` | Typed parser outputs for FIR, complaints, witness statements, medical/postmortem/FSL reports, memos, site/vehicle/CCTV documents, and unknown documents. |
| `investigation.py` | Older canonical investigation model family retained for compatibility; the active normalization package contains the current production projections. |

These models are the typed boundaries that prevent arbitrary dictionaries from silently losing provenance or status.

### 4.4 `src/intake/`

| File | Responsibility |
|---|---|
| `__init__.py` | Intake exports. |
| `checksum.py` | Streaming SHA-256 calculation for uploaded/stored files. |
| `document_classifier.py` | Deterministic document-type classification from filename and MIME type. |
| `document_intake_stage.py` | Adapts `UploadManager` to the workflow and records intake metrics/artifacts. |
| `exceptions.py` | Intake, path, validation, and storage exception types. |
| `file_validator.py` | Validates extension, size, emptiness, file signatures, and DOCX ZIP structure. |
| `storage_layout.py` | Defines `CASE_<uuid>/originals`, `processed`, and related case directories. |
| `upload_manager.py` | Validates uploads, calculates checksums, detects duplicates, copies originals, creates `SourceDocument` values, and writes manifests. |
| `upload_manifest.py` | Manifest schemas and accepted/rejected/duplicate entry statuses. |

The intake layer rejects unsafe filenames/path traversal, applies file and case-size limits, and treats duplicate bytes as duplicates using SHA-256 rather than filename alone. The validator can accept PDF/JPEG/PNG/DOCX/MP4/MOV/WAV, but the active Gemini OCR client supports PDF/JPEG/PNG.

### 4.5 `src/extraction/`

| File | Responsibility |
|---|---|
| `__init__.py` | Extraction exports. |
| `base.py` | Compatibility OCR/parser ports retained from earlier architecture. |
| `gemini_ocr.py` | `GeminiOCRClient`: raw OCR adapter using the `google-genai` SDK. |
| `ocr_artifacts.py` | Writes, loads, and validates raw text, metadata, and typed OCR-result artifacts. |
| `ocr_client.py` | Provider-neutral OCR client interface. |
| `ocr_exceptions.py` | Unsupported-document, provider, and malformed-response error types. |
| `ocr_result.py` | OCR page, metadata, and result Pydantic models. |
| `ocr_stage.py` | Runs OCR over eligible documents, updates extraction state, records metrics, and performs checksum-safe resume. |

`GeminiOCRClient` uses the Files API for PDFs and inline byte parts for images. It requests structured JSON containing ordered pages, text, confidence, language, and warnings. It does not infer document fields. A transient provider failure currently fails the OCR stage; there is no built-in 429/503 exponential backoff.

### 4.6 `src/parsers/`

| File | Responsibility |
|---|---|
| `__init__.py` | Parser exports. |
| `base_parser.py` | Parser contract, Gemini structured-output client, schema prompts, validation/retry behavior, OCR-text hash, and supported-entity checks. |
| `parser_registry.py` | Maps detected `DocumentType` values to parser instances. |
| `parser_stage.py` | Selects parsers, converts OCR results into typed documents, persists outputs, and updates document state. |
| `parser_artifacts.py` | Persists typed parsed-document JSON. |
| `unknown_document_parser.py` | Preserves OCR as `UnknownDocument` without inventing document-specific fields. |
| `fir_parser.py` | FIR parser schema/configuration and parser-specific instructions. |
| `complaint_parser.py` | Complaint parser schema/configuration. |
| `medical_report_parser.py` | Medical-report parser schema/configuration. |
| `postmortem_parser.py` | Postmortem parser schema/configuration. |
| `fsl_parser.py` | Forensic Science Laboratory parser schema/configuration. |
| `witness_parser.py` | Witness-statement parser schema/configuration. |
| `case_diary_parser.py` | Case-diary parser schema/configuration. |
| `arrest_memo_parser.py` | Arrest-memo parser schema/configuration. |
| `seizure_memo_parser.py` | Seizure-memo parser schema/configuration. |
| `spot_panchnama_parser.py` | Spot-panchnama parser schema/configuration. |
| `vehicle_inspection_parser.py` | Vehicle-inspection parser schema/configuration. |
| `site_plan_parser.py` | Site-plan parser schema/configuration. |
| `cctv_metadata_parser.py` | CCTV metadata parser schema/configuration. |

`BaseDocumentParser` gives Gemini the target Pydantic schema and OCR transcription. It tells the model to use only explicitly supported information, use null/empty values when unavailable, and not invent legal sections or facts. It retries parser failures up to the configured attempt count and verifies configured entities against normalized OCR text.

### 4.7 `src/knowledge_graph/`

| File | Responsibility |
|---|---|
| `__init__.py` | Graph exports. |
| `entity_resolver.py` | Normalizes identity keys and conservatively resolves repeated people/entities. |
| `graph_artifacts.py` | Persists graph, node, and edge JSON. |
| `graph_builder.py` | Deterministically maps typed parsed documents into graph nodes, edges, and provenance. |
| `graph_models.py` | Graph node/edge/provenance models, person roles, and relationship types. |
| `graph_registry.py` | Registry of document-type graph mappers. |
| `graph_stage.py` | Workflow adapter that builds and stores the investigation graph. |

A document node is created for every parsed document. Non-empty parser fields are retained as document attributes. Mappers create people, vehicles, locations, evidence, events, property, medical findings, and forensic findings, then connect them with relationships such as `MENTIONS`, `ASSERTED_BY`, `SUPPORTED_BY`, `PART_OF`, `RECOVERED_FROM`, `COLLECTED_BY`, and `EXAMINED_BY`. Every node and edge receives provenance.

### 4.8 `src/normalization/`

| File | Responsibility |
|---|---|
| `__init__.py` | Normalization exports. |
| `canonical_models.py` | Canonical facts, persons, vehicles, locations, evidence, documents, timeline events, conflicts, missing information, and confidence models. |
| `canonical_builder.py` | Assembles the `CanonicalInvestigation` from graph projections. |
| `canonical_artifacts.py` | Persists canonical investigation, conflict, timeline, and evidence JSON. |
| `canonical_stage.py` | Workflow stage that invokes the builder and artifact writer. |
| `conflict_registry.py` | Detects and records competing/conflicting canonical facts. |
| `fact_projection.py` | Converts graph facts and graph provenance into `CanonicalFact` values. |
| `entity_projection.py` | Projects graph people, vehicles, locations, and documents. |
| `evidence_projection.py` | Projects evidence/property nodes and custody/collection details. |
| `timeline_projection.py` | Projects event nodes into ordered timeline data. |

Normalization is deterministic. It does not fill missing values with guesses. A canonical value should retain source document IDs and source references so later validation and presentation can explain where it came from.

### 4.9 `src/validation/`

| File | Responsibility |
|---|---|
| `__init__.py` | Validation exports. |
| `validation_models.py` | Validation issues, rules, dispositions, reports, and severity/status models. |
| `completeness_checker.py` | Checks required case/document fields and expected completeness. |
| `support_checker.py` | Checks whether required facts are supported by expected documents. |
| `conflict_detector.py` | Detects unresolved canonical conflicts. |
| `timeline_validator.py` | Checks suspicious chronology and timeline consistency. |
| `evidence_validator.py` | Coordinates checks and assigns `draft_allowed`, `review_required`, or `final_blocked`. |
| `exceptions.py` | Validation-specific errors. |
| `validation_artifacts.py` | Writes validation report, conflicts, and missing-information files. |
| `validation_stage.py` | Non-mutating workflow adapter for evidence validation. |

A fact with no valid source document ID/reference is treated as unsupported. Critical unsupported facts produce `final_blocked`. Other errors, conflicts, chronology issues, unresolved entities, or low-confidence conditions generally produce `review_required`. Clean supported data can produce `draft_allowed`.

### 4.10 `src/context/`

| File | Responsibility |
|---|---|
| `__init__.py` | Context exports. |
| `case_context.py` | Compact provenance-preserving context model used by legal and presentation layers. |
| `case_context_builder.py` | Selects canonical facts, evidence, documents, timeline, issues, and references. |
| `context_artifacts.py` | Persists `case_context.json`. |
| `context_stage.py` | Workflow adapter that builds context after canonical validation. |

`CaseContext` is a derived working view, not the source of truth. It includes metadata, FIR/occurrence facts, complainants, victims, accused, witnesses, officers, doctors, locations, vehicles, evidence, recovered property, medical/forensic findings, investigation actions, documents, legal references, validation findings, conflicts, missing information, and provenance.

### 4.11 `src/legal/`

| File | Responsibility |
|---|---|
| `__init__.py` | Legal package exports. |
| `legal_rules.py` | Legal-reference models, local version-pinned provider, and fixture provider. |
| `evidence_mapper.py` | Builds the finite allow-list of evidence that can support legal findings. |
| `legal_findings.py` | Legal finding, status, confidence, evidence strength, and evidence-mapping models. |
| `legal_reasoner.py` | Deterministic legal reasoning plus constrained optional-client handling. |
| `legal_artifacts.py` | Writes legal findings and evidence mappings. |
| `legal_stage.py` | Workflow adapter for legal reasoning. |

The provider refuses missing/unversioned legal data. The deterministic reasoner preserves uncertainty:

- `supported` means required evidence text/elements were found;
- `insufficient_evidence` means required support is missing;
- `conflicted` means context conflicts affect the finding;
- `review_required` flags findings needing officer review.

Legal reasoning must not upgrade unsupported data into a conclusive charge. The local legal file is an allow-list/reference dataset, not legal advice and not a complete statutory corpus.

### 4.12 `src/chargesheet/`

| File | Responsibility |
|---|---|
| `__init__.py` | Charge-sheet exports. |
| `form_if5_schema.py` | Typed IF-5 charge-sheet data contract, field status/provenance rules, rows, findings, annexures, and stable content hash. |
| `chargesheet_populator.py` | Deterministically projects `CaseContext` and `LegalFindings` into `ChargeSheetData`. |
| `chargesheet_validator.py` | Performs the final provenance/status/field consistency checks. |
| `chargesheet_artifacts.py` | Writes charge-sheet data artifacts. |
| `chargesheet_stage.py` | Coordinates population, validation, JSON writing, PDF rendering, and review-state creation. |
| `presentation.py` | Recursively formats values for human display and maps document types to factual investigation-action text. |

This package is the direct bridge between validated investigation data and the rendered charge sheet. It must remain presentation-only: it may decide how to display a value, but it must not invent or upgrade evidence, confidence, legal status, or provenance.

### 4.13 `src/rendering/`

| File | Responsibility |
|---|---|
| `__init__.py` | Rendering package marker/exports. |
| `if5_renderer.py` | Active ReportLab renderer for the IF-5 draft/final PDF. |
| `if5_layout.py` | Retained legacy/stub layout helpers; not the active renderer contract. |
| `pagination.py` | Retained legacy/stub pagination helpers. |
| `styles.py` | Retained legacy/stub style helpers. |
| `template_mapping.py` | Retained legacy/stub template mapping helpers. |

The active renderer builds an A4 PDF with escaped text, section headings, case information, evidence/legal tables, annexures, repeated table headers, and page header/footer chrome. The renderer receives charge-sheet data, not raw LLM responses, so it cannot alter upstream facts.

### 4.14 `src/review/`

| File | Responsibility |
|---|---|
| `__init__.py` | Review exports. |
| `review_models.py` | Review statuses, events, reviewer metadata, version, and content-hash models. |
| `review_service.py` | Draft, submit, approve, reject, revise, and finalize lifecycle with hash/version checks. |

The intended lifecycle is `DRAFT -> REVIEW_REQUIRED -> APPROVED/REJECTED -> FINALIZED`. Approval and finalization must use the same case/version/content hash. Finalized artifacts cannot be silently overwritten.

### 4.15 `src/scene/`

This is an adjacent visualization/3D reconstruction subsystem, not a stage in the active charge-sheet workflow.

| File | Responsibility |
|---|---|
| `scene_models.py` | Domain-neutral scene intermediate representation models. |
| `scene_projector.py` | Projects legacy fact ledgers or canonical investigations into scene data. |
| `asset_registry.py` | Selects semantic GLB assets and fallback assets. |
| `trellis_generator.py` | Optional Hugging Face/Gradio TRELLIS asset generation. |

### 4.16 `src/evidence_graph/`, `src/infrastructure/`, and `src/repositories/`

| File | Responsibility |
|---|---|
| `evidence_graph/__init__.py` | Legacy evidence-graph exports. |
| `evidence_graph/models.py` | Legacy graph model family. |
| `infrastructure/__init__.py` | Infrastructure package marker; no concrete production service wiring. |
| `repositories/__init__.py` | Repository exports. |
| `repositories/base.py` | Abstract persistence ports for documents/cases; no concrete database implementation. |

## 5. Detailed charge-sheet creation lifecycle

This is the complete active path used by `python -m src.main`.

### Step 1: CLI creates the input snapshot

`src/main.py` is the entry point.

1. `argparse` requires `--case-id`, `--input-dir`, and `--output-dir`.
2. `_discover_uploads()` verifies the input directory exists and creates an `IncomingUpload` for every direct file.
3. `_case_id()` accepts a UUID directly. Otherwise it derives a stable UUID5 from the external identifier, so `case-001` maps to the same case ID every time.
4. The CLI requires a Gemini API key because both OCR and parser clients are constructed from it.
5. `create_workflow_context()` creates the initial immutable context with pending uploads and an empty workflow state.
6. `run_production_workflow()` builds the production registry and invokes `WorkflowEngine`.

The CLI prints each stage status and generated artifact. It returns:

- `0` for successful completion;
- `1` if the workflow failed or the final disposition is `final_blocked`;
- `2` for input/configuration errors.

### Step 2: Intake validates and stores originals

`DocumentIntakeStage` delegates to `UploadManager`.

For each file:

1. `FileValidator` checks existence, supported extension, non-empty content, size, and basic file signature.
2. The safe filename check rejects path traversal and unsafe names.
3. `DeterministicDocumentClassifier` uses filename/MIME signals to select a document type.
4. `calculate_sha256()` hashes the bytes.
5. Matching hashes are recorded as duplicates.
6. Accepted files are copied into `output/CASE_<uuid>/originals/` using UUID-based names.
7. A `SourceDocument` records case ID, document ID, original/stored filename, MIME type, size, SHA-256, detected type, validation state, and extraction state.
8. `UploadManifest` records every accepted, rejected, or duplicate result.
9. `processed/upload_manifest.json` is written.

The stage clears `pending_uploads`, populates `uploaded_documents`, and adds an `upload_manifest` generated artifact.

When `--resume` is used, the current valid-upload checksum multiset must exactly match the persisted accepted checksums. Otherwise intake creates a fresh manifest rather than trusting stale state.

### Step 3: OCR extracts source text

`OCRStage` selects documents that are valid, pending extraction, and supported by `GeminiOCRClient`.

For a PDF:

1. `GeminiOCRClient` uploads the stored original through the Google GenAI Files API.
2. It waits for asynchronous file processing when necessary.
3. It asks the configured model to transcribe exactly, without summarizing or extracting fields.
4. It requests structured JSON containing ordered page entries, language, and warnings.
5. It deletes the remote uploaded file in a `finally` block.

For PNG/JPEG:

1. The file bytes become a `google.genai.types.Part`.
2. The same structured OCR request is sent inline.

The response becomes an `OCRResult` containing:

- `document_id`;
- ordered `OCRPage` values;
- page text and optional confidence;
- `raw_text` joined from page text;
- language and warnings;
- provider/model/input MIME metadata;
- timing/token usage when available.

`OCRArtifactWriter` stores three pieces of evidence under `processed/ocr/`:

- raw text;
- metadata JSON;
- serialized `OCRResult` JSON.

A document is moved from pending to complete extraction. If the provider returns 503/404/429 or malformed data, the critical OCR stage fails and parsing remains pending. The current adapter has no automatic transient-error backoff.

Resume is deliberately strict. It reuses OCR only if the original checksum and all persisted OCR artifacts validate. If a document ID changed, it may locate a byte-identical UUID-named original, validate that candidate's checksum/artifacts, and rebind the result to the current ID.

### Step 4: Typed parsers extract document-local fields

`ParserStage` takes completed OCR results and consults `ParserRegistry`.

The registry chooses a specialized parser for FIR, complaint, medical, postmortem, FSL, witness, case diary, arrest memo, seizure memo, spot panchnama, vehicle inspection, site plan, and CCTV metadata. Unknown types use `UnknownDocumentParser` and retain raw text without guessing a schema.

`BaseDocumentParser`:

1. Builds a prompt from the target Pydantic JSON schema.
2. Includes the OCR transcription.
3. Tells Gemini to use only explicit information.
4. Requires null/empty values for unavailable fields.
5. Forbids inferred facts and invented legal sections.
6. Requests structured JSON.
7. Validates the result with Pydantic.
8. Retries parse/validation failures up to the parser attempt limit.
9. Stores the OCR text SHA-256 and parse metadata.
10. Checks configured entity fields against normalized OCR text to catch invented names/identifiers.

`parser_artifacts.py` writes typed document JSON under `processed/parsed/`. The resulting parsed documents retain their source document ID and feed the graph stage.

### Step 5: GraphBuilder creates a provenance graph

`GraphStage` invokes `GraphBuilder`.

The builder always creates a document node for every parsed document. It then uses registered document mappers to create nodes for:

- persons and explicit roles;
- vehicles;
- locations;
- evidence and recovered property;
- events/timeline entries;
- medical/FSL findings;
- investigation actions;
- documents and assertions.

It creates typed edges such as:

- `MENTIONS`;
- `ASSERTED_BY`;
- `SUPPORTED_BY`;
- `PART_OF`;
- `RECOVERED_FROM`;
- `COLLECTED_BY`;
- `EXAMINED_BY`;
- `RELATES_TO`.

`EntityResolver` normalizes identity keys. It only merges people when identity matching is sufficiently safe; separate names are not silently collapsed. If one identity is explicitly assigned multiple roles across source documents, the roles are unioned while provenance is retained.

`GraphArtifactWriter` persists:

- `processed/graph/investigation_graph.json`;
- `processed/graph/nodes.json`;
- `processed/graph/edges.json`.

### Step 6: CanonicalBuilder creates one investigation projection

`CanonicalInvestigationStage` converts the graph to typed canonical data.

The projection modules divide responsibility:

- `fact_projection.py` creates source-backed canonical facts;
- `entity_projection.py` creates role-specific people, vehicles, locations, and document projections;
- `evidence_projection.py` creates evidence/property/custody structures;
- `timeline_projection.py` orders event projections;
- `conflict_registry.py` records competing values;
- `canonical_builder.py` assembles the complete model.

The canonical model contains case metadata, complainants, victims, accused, witnesses, police, doctors, locations, vehicles, evidence, recovered property, timeline, medical/FSL findings, documents, investigation actions, conflicts, missing information, and confidence summaries.

Every supported fact should carry source document IDs/references. Missing data stays missing. The stage writes canonical artifacts under `processed/canonical/`.

### Step 7: EvidenceValidator determines whether a draft is allowed

`EvidenceValidationStage` calls `EvidenceValidator` without mutating the canonical investigation.

It runs:

- completeness checks;
- expected-document support checks;
- unresolved conflict detection;
- chronology/timeline checks;
- provenance/unsupported-fact checks;
- low-confidence checks;
- unresolved-entity checks.

The report contains errors, warnings, critical issues, missing documents, conflicts, unsupported facts, low-confidence facts, and a completeness score.

The disposition gates later presentation:

- `draft_allowed` — no blocking problems found;
- `review_required` — a draft may be produced but an officer must review issues;
- `final_blocked` — a final/conclusive charge-sheet is not permitted.

Validation artifacts are written under `processed/validation/`.

### Step 8: CaseContextBuilder prepares downstream data

`CaseContextStage` creates a compact context from canonical data and the validation report.

It carries forward:

- case/FIR/station/court metadata;
- occurrence and full timeline;
- all explicit person roles;
- vehicles and locations;
- evidence, recovered property, medical and forensic findings;
- source documents and document attributes;
- investigation actions;
- legal references;
- validation issues, conflicts, missing information, disposition, and provenance.

This context is intentionally compact for legal and presentation use, but it is not the source of truth. The canonical investigation and source artifacts remain authoritative.

`processed/context/case_context.json` is written.

### Step 9: LegalReasoner creates status-preserving findings

`LegalReasoningStage` loads the local dataset through `LocalLegalReferenceProvider`.

The provider checks:

1. the legal-reference path exists;
2. the JSON shape is valid;
3. the requested dataset version is present;
4. every record is pinned to the same version.

`EvidenceMapper` derives a finite allow-list from current context facts, evidence, and timeline. Legal findings may only refer to evidence in this allow-list.

Normal deterministic reasoning:

- `final_blocked` context produces no conclusive findings;
- conflicting context produces `conflicted` findings;
- required evidence elements found in supported context can produce `supported`;
- missing required elements produce `insufficient_evidence`;
- non-supported statuses retain review flags.

The reasoner does not turn absence of evidence into a factual allegation. `processed/legal/legal_findings.json` and `processed/legal/evidence_mapping.json` are written.

### Step 10: ChargeSheetPopulator builds typed IF-5 data

`ChargeSheetStage` requires both `CaseContext` and `LegalFindings`. It calls `ChargeSheetPopulator.populate()`.

The populator fills the charge-sheet schema with source-backed sections:

1. case summary;
2. detailed occurrence facts;
3. investigation conducted;
4. complainant, victim, accused, witness, officer, and doctor rows;
5. timeline/events;
6. documentary/material/medical/forensic/vehicle/witness evidence;
7. collection and custody details;
8. legal findings and statuses;
9. conflicts and missing information;
10. annexure index;
11. explicitly unavailable final opinion/signature fields.

The populator does not write directly to a PDF. It creates typed `ChargeSheetData` containing `ChargeSheetField` values, rows, findings, review items, version, disposition, and provenance.

The schema rejects:

- populated values without source references;
- review-required values without provenance;
- values placed into unavailable/not-applicable fields;
- invalid legal/evidence mappings.

### Step 11: Final charge-sheet validation

`ChargeSheetValidator` performs a second validation pass after population. This protects the final presentation boundary even if an upstream context object was incomplete or a mapping was wrong.

If validation returns errors, `ChargeSheetStage` raises an exception and does not proceed to PDF generation. If `final_blocked`, charge-sheet data can still be stored for review/audit, but a review PDF is intentionally not rendered.

`ChargeSheetData.content_hash` is calculated from stable serialized data and version. The hash is later used by review/approval operations to prevent approval of changed content.

### Step 12: JSON artifact and PDF rendering

For data that is not `final_blocked`:

1. `ChargeSheetArtifactWriter` writes the versioned charge-sheet JSON under `processed/chargesheet/draft/`.
2. `CaseStorageLayout` ensures the chargesheet directories exist.
3. `IF5Renderer` converts typed data into a ReportLab PDF.
4. `presentation.py` recursively formats mappings, sequences, dates, booleans, `None`, and nested document attributes into human-readable text.
5. The renderer escapes text and lays out tables, sections, evidence, legal findings, and annexures.
6. The review PDF is stored as `processed/chargesheet/draft/ChargeSheet_v<version>_review.pdf`.
7. `ReviewService` creates a draft review record and submits it for review.
8. `review_state.json` stores the review state, events, version, and content hash.

The PDF is marked as a draft/review copy. Rendering is not allowed to upgrade `insufficient_evidence`, `conflicted`, or `review_required` findings into conclusive claims.

### Step 13: Officer review and finalization

The production stage creates the draft and review state. A later caller must use `ReviewService` to transition it:

```text
DRAFT
  -> REVIEW_REQUIRED
  -> APPROVED
  -> FINALIZED
```

Rejection or revision can return the item to a draft/review state. Every transition checks case ID, version, content hash, status, and required reviewer metadata. Final-blocked data cannot be approved/finalized. Finalized files cannot be overwritten.

## 6. Generated artifact layout

For a case ID such as `case-001`, the stable UUID-derived workspace is:

```text
output/
└── CASE_<case-uuid-hex>/
    ├── originals/
    │   └── <document-uuid>.<extension>
    └── processed/
        ├── upload_manifest.json
        ├── ocr/
        │   ├── <document>_<id>_raw.txt
        │   ├── <document>_<id>_metadata.json
        │   └── <document>_<id>_OCRResult.json
        ├── parsed/
        │   └── <document>_<id>.json
        ├── graph/
        │   ├── investigation_graph.json
        │   ├── nodes.json
        │   └── edges.json
        ├── canonical/
        │   ├── canonical_investigation.json
        │   ├── timeline.json
        │   ├── evidence.json
        │   └── conflicts.json
        ├── validation/
        │   ├── validation_report.json
        │   ├── conflicts.json
        │   └── missing_information.json
        ├── context/
        │   └── case_context.json
        ├── legal/
        │   ├── legal_findings.json
        │   └── evidence_mapping.json
        └── chargesheet/
            ├── draft/
            │   ├── ChargeSheet_v<version>_data.json
            │   └── ChargeSheet_v<version>_review.pdf
            ├── review_state.json
            └── final/
                └── ChargeSheet_v<version>_final.pdf
```

The exact artifact names can vary slightly with the writer implementation, but the stage ownership and directory boundaries follow this structure.

The repository may also contain historical/generated files such as:

- `output/ChargeSheet.pdf` — legacy PDF output;
- `output/llm_response_raw.txt` — legacy raw LLM output;
- `output/pdf/phase10_charge_sheet_review.pdf` — older phase output;
- old `CASE_*` directories — previous workflow runs.

These files are generated evidence, not source code. Do not edit them to fix application behavior.

## 7. Tests and what they protect

| Test file | Main coverage |
|---|---|
| `test_domain_models.py` | Model immutability, hashes, filenames, provenance, confidence. |
| `test_document_intake.py` | File signatures, limits, classification, duplicates, storage, manifests. |
| `test_production_hardening.py` | Production composition, provider/configuration safeguards, isolation. |
| `test_ocr_layer.py` | Gemini SDK shape, OCR responses, artifacts, PDF/image paths, failures. |
| `test_ocr_resume.py` | Checksum validation, stale-artifact rejection, OCR reuse, ID rebinding. |
| `test_gemini_sdk_smoke.py` | Optional live SDK availability/smoke behavior. |
| `test_document_parsers.py` | Parser registry, schema validation, retry behavior, entity support, artifacts. |
| `test_knowledge_graph.py` | Identity merging, roles, graph relationships, provenance. |
| `test_canonical_investigation.py` | Canonical projection, conflicts, evidence, timeline. |
| `test_evidence_validation.py` | Completeness, support, provenance, conflict, chronology, confidence. |
| `test_case_context_and_legal.py` | Context selection, evidence allow-list, legal status constraints. |
| `test_legal_reference_provider.py` | Legal dataset structure and strict version pinning. |
| `test_chargesheet.py` | Population, formatting, field provenance, renderer, blocked output. |
| `test_information_preservation.py` | Role/fact preservation across parser, graph, canonical, context, and presentation. |
| `test_officer_review.py` | Review transitions, content hashes, versions, final artifact safety. |
| `test_workflow_engine.py` | Stage order, skipping, critical/non-critical failure semantics. |
| `test_end_to_end_pipeline.py` | Full typed fixture workflow and failure gates. |
| `test_final_end_to_end.py` | Production composition through approved/final PDF behavior. |

## 8. Legacy versus active code

The active typed workflow should be preferred for new work. The following are retained but are not part of the normal production composition:

- `src/llm.py`;
- `src/loader.py`;
- `src/prompt_builder.py`;
- `src/pdf_generator.py`;
- `src/models.py`;
- `src/evidence_graph/`;
- `src/domain/investigation.py`;
- most of `src/rendering/if5_layout.py`, `pagination.py`, `styles.py`, and `template_mapping.py`;
- `dummy_case/` JSON fixtures;
- legacy files under `output/`;
- standalone scene/TRELLIS scripts.

The legacy path uses broad direct-LLM prompting and a different JSON/PDF flow. Do not accidentally import it into `src/workflow/production.py`; doing so would bypass the active typed, provenance-preserving controls.

## 9. Current limitations and operational notes

1. Gemini OCR/parser calls require network access, a valid API key, an account-enabled model, and available quota.
2. The OCR client currently does not retry transient 429/503 provider failures automatically.
3. `--resume` safely reuses OCR only; parsing and later stages are recomputed.
4. The legal dataset is local and version-pinned, but it is not a complete legal corpus.
5. Legal element checking is deterministic string/requirement matching, not a complete legal reasoning engine.
6. Filename/MIME classification is deterministic and can be affected by inaccurate filenames.
7. DOCX, video, and audio may pass intake validation but are not supported by the active OCR adapter.
8. The repository does not implement an HTTP API, authentication, database, deployment configuration, or institutional approval system.
9. A `final_blocked` disposition intentionally prevents draft PDF generation; inspect validation artifacts to understand why.
10. Generated output, secrets, and Python caches should not be treated as source-of-truth project files.

## 10. Safe change workflow

When changing the backend:

1. Find the owning typed boundary and read its tests first.
2. Preserve Pydantic models, source references, document IDs, checksums, role semantics, validation dispositions, and review hashes.
3. Keep LLM use narrow and schema-constrained.
4. Add a focused regression test before changing behavior where practical.
5. Run focused tests, then `py -3.13 -m pytest -q`.
6. Run `py -3.13 -m compileall -q src tests`.
7. Do not modify generated PDFs/JSON to solve source defects.
8. Never commit `.env` or expose API keys.
