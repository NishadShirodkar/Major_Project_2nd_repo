"""Background job execution and status tracking for the Byomkesh AI workflow."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ...config import Config
from ...extraction.mock_client import MockOCRClient, MockParserClient
from ...intake.storage_layout import CaseStorageLayout
from ...intake.upload_manager import IncomingUpload
from ...workflow.production import create_workflow_context, run_production_workflow
from ...workflow.state import StageStatus
from ..config import api_config
from ..exceptions import (
    CaseAlreadyProcessingError,
    CaseNotFoundError,
    JobNotFoundError,
    NoDocumentsUploadedError,
)
from ..schemas.job import JobStartResponse, JobStatusResponse, StageRecordItem
from .case_service import parse_safe_case_id

logger = logging.getLogger("byomkesh.api.jobs")


class JobRecord:
    def __init__(self, job_id: str, case_id: str, case_uuid: UUID) -> None:
        self.job_id = job_id
        self.case_id = case_id
        self.case_uuid = case_uuid
        self.status = "queued"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: str | None = None
        self.completed_at: str | None = None
        self.current_stage: str | None = None
        self.completed_stages: list[str] = []
        self.stage_records: list[StageRecordItem] = []
        self.error: str | None = None
        self.validation_disposition: str | None = None
        self.artifacts_available: list[str] = []


class JobService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or api_config.storage_root).resolve()
        self._jobs: dict[str, JobRecord] = {}
        self._active_cases: set[UUID] = set()
        self._lock = threading.Lock()

    def start_job(
        self,
        case_id: str,
        resume: bool = False,
        mock_llm: bool = False,
    ) -> JobStartResponse:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        # Check uploaded files exist
        index_path = layout.case_directory / "uploads" / "upload_index.json"
        if not index_path.is_file():
            raise NoDocumentsUploadedError(case_id)

        try:
            docs = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            docs = []

        if not docs:
            raise NoDocumentsUploadedError(case_id)

        # Concurrency guard: prevent two jobs from running on the same case
        with self._lock:
            if case_uuid in self._active_cases:
                # Find the running job ID if available
                running_job = next(
                    (j.job_id for j in self._jobs.values() if j.case_uuid == case_uuid and j.status in ("queued", "running")),
                    None,
                )
                raise CaseAlreadyProcessingError(client_id, running_job)

            job_id = str(uuid4())
            record = JobRecord(job_id=job_id, case_id=client_id, case_uuid=case_uuid)
            self._jobs[job_id] = record
            self._active_cases.add(case_uuid)

        # Launch worker thread
        thread = threading.Thread(
            target=self._run_job_worker,
            args=(record, resume, mock_llm),
            name=f"byomkesh-job-{job_id}",
            daemon=True,
        )
        thread.start()

        return JobStartResponse(
            job_id=job_id,
            case_id=client_id,
            status="queued",
            message="Case processing workflow queued successfully.",
        )

    def _run_job_worker(self, record: JobRecord, resume: bool, mock_llm: bool) -> None:
        record.status = "running"
        record.started_at = datetime.now(timezone.utc).isoformat()
        case_uuid = record.case_uuid
        layout = CaseStorageLayout(self.storage_root, case_uuid)

        try:
            index_path = layout.case_directory / "uploads" / "upload_index.json"
            raw_docs = json.loads(index_path.read_text(encoding="utf-8"))

            uploads: list[IncomingUpload] = []
            for doc in raw_docs:
                source_path = layout.case_directory / "uploads" / doc["stored_filename"]
                if source_path.is_file():
                    uploads.append(
                        IncomingUpload(
                            source_path=source_path,
                            original_filename=doc["original_filename"],
                        )
                    )

            if not uploads:
                raise ValueError("No valid uploaded source files found on disk.")

            context = create_workflow_context(
                case_uuid,
                tuple(uploads),
                resume=resume,
                storage_root=self.storage_root,
            )

            # Resolve execution dependencies
            dependencies: dict[str, Any] = {
                "legal_reference_path": api_config.legal_reference_path,
                "legal_reference_version": api_config.legal_reference_version,
                "resume": resume,
            }

            api_key = os.getenv("GEMINI_API_KEY") or Config.GEMINI_API_KEY
            model = os.getenv("GEMINI_MODEL") or Config.GEMINI_MODEL or "gemini-flash-latest"

            is_mock = mock_llm or bool(os.getenv("BYOMKESH_MOCK_LLM"))
            if is_mock:
                from ...rag.embedding_provider import NoOpEmbeddingProvider

                dependencies["ocr_client"] = MockOCRClient()
                dependencies["parser_client"] = MockParserClient()
                dependencies["embedding_provider"] = NoOpEmbeddingProvider()
            else:
                dependencies["gemini_api_key"] = api_key
                dependencies["gemini_model"] = model

            def on_stage_update(stage_name: str, stage_status: StageStatus, _ctx: Any = None) -> None:
                with self._lock:
                    record.current_stage = stage_name
                    if stage_status == StageStatus.COMPLETED:
                        if stage_name not in record.completed_stages:
                            record.completed_stages.append(stage_name)
                    existing = [r for r in record.stage_records if r.stage_name != stage_name]
                    existing.append(
                        StageRecordItem(
                            stage_name=stage_name,
                            status=stage_status.value,
                            error_message=None,
                        )
                    )
                    record.stage_records = existing

            # Execute pipeline
            result = run_production_workflow(
                self.storage_root,
                context,
                on_stage_update=on_stage_update,
                **dependencies,
            )

            # Record stage outcomes
            completed: list[str] = []
            stage_records: list[StageRecordItem] = []
            for rec in result.report.stage_records:
                err_msg = rec.exception.message if rec.exception else None
                stage_records.append(
                    StageRecordItem(
                        stage_name=rec.stage_name,
                        status=rec.status.value,
                        error_message=err_msg,
                    )
                )
                if rec.status == StageStatus.COMPLETED:
                    completed.append(rec.stage_name)

            record.stage_records = stage_records
            record.completed_stages = completed

            # Check for validation disposition
            if result.context.validation_report is not None:
                record.validation_disposition = result.context.validation_report.disposition.value

            # Record artifact references
            artifacts: list[str] = []
            for art in result.context.generated_artifacts:
                artifacts.append(art.storage_key)
            record.artifacts_available = artifacts

            if result.report.successful:
                record.status = "completed"
            else:
                record.status = "failed"
                failed_rec = next((r for r in result.report.stage_records if r.status == StageStatus.FAILED), None)
                record.error = (
                    f"Workflow halted at stage '{failed_rec.stage_name}': {failed_rec.exception.message}"
                    if failed_rec and failed_rec.exception
                    else "Workflow failed with incomplete stage execution."
                )

        except Exception as exc:
            logger.exception("Unexpected error in background job %s", record.job_id)
            record.status = "failed"
            # Sanitize error to avoid leaking secrets
            record.error = f"Workflow execution error: {type(exc).__name__}: {str(exc)}"
        finally:
            record.completed_at = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._active_cases.discard(case_uuid)

    def reset_case_processing(self, case_id: str) -> None:
        case_uuid, _ = parse_safe_case_id(case_id)
        with self._lock:
            self._active_cases.discard(case_uuid)
            for j in self._jobs.values():
                if j.case_uuid == case_uuid and j.status in ("queued", "running"):
                    j.status = "failed"
                    j.error = "Cancelled by user reset request."

    def get_active_job_for_case(self, case_uuid: UUID) -> str | None:
        with self._lock:
            if case_uuid in self._active_cases:
                return next(
                    (j.job_id for j in self._jobs.values() if j.case_uuid == case_uuid and j.status in ("queued", "running")),
                    None,
                )
            return None

    def get_job(self, job_id: str) -> JobStatusResponse:
        record = self._jobs.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)

        return JobStatusResponse(
            job_id=record.job_id,
            case_id=record.case_id,
            status=record.status,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            current_stage=record.current_stage,
            completed_stages=record.completed_stages,
            stage_records=record.stage_records,
            error=record.error,
            validation_disposition=record.validation_disposition,
            artifacts_available=record.artifacts_available,
        )

    def wait_for_job(self, job_id: str, timeout: float = 15.0) -> JobStatusResponse:
        """Helper for test suites and synchronous callers to await job completion."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job.status in ("completed", "failed"):
                return job
            time.sleep(0.05)
        return self.get_job(job_id)
