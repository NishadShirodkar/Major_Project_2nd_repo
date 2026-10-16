"""Service coordinating case creation, listing, metadata, and document staging."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import UploadFile

from ...domain.documents import DocumentType
from ...intake.file_validator import SUPPORTED_MEDIA_TYPES, FileValidator
from ...intake.storage_layout import CaseStorageLayout
from ..config import api_config
from ..exceptions import (
    CaseNotFoundError,
    CaseSizeLimitExceededError,
    EmptyUploadError,
    FileSizeLimitExceededError,
    InvalidCaseIdError,
    InvalidFilenameError,
    UnsupportedMediaTypeError,
)
from ..schemas.case import (
    CaseCreateResponse,
    CaseDeleteResponse,
    CaseDetailResponse,
    CaseDocumentItem,
    CaseListResponse,
    CaseSummary,
    DocumentUploadItem,
    DocumentUploadResponse,
)

_SAFE_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_CHUNK_SIZE = 64 * 1024


def parse_safe_case_id(value: str | None) -> tuple[UUID, str]:
    """Validate and convert an external case identifier into an isolated UUID and safe display key."""
    if value is None:
        generated = uuid4()
        return generated, str(generated)

    stripped = value.strip()
    if not stripped or not _SAFE_CASE_ID_RE.match(stripped) or ".." in stripped:
        raise InvalidCaseIdError(
            f"Case ID '{value}' is invalid. Allowed format: 1-64 alphanumeric, dash, or underscore characters."
        )

    try:
        parsed_uuid = UUID(stripped)
        return parsed_uuid, stripped
    except ValueError:
        derived_uuid = uuid5(NAMESPACE_URL, f"byomkesh-ai-case:{stripped}")
        return derived_uuid, stripped


class CaseService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or api_config.storage_root).resolve()
        self.validator = FileValidator(max_size_bytes=api_config.max_upload_file_size_bytes)

    def create_case(
        self,
        case_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> CaseCreateResponse:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid).ensure_exists()
        uploads_dir = layout.case_directory / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        meta_path = layout.case_directory / "case_meta.json"
        now_str = datetime.now(timezone.utc).isoformat()
        if not meta_path.is_file():
            meta = {
                "case_id": str(case_uuid),
                "client_id": client_id,
                "title": title or f"Case {client_id}",
                "description": description or "",
                "created_at": now_str,
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        else:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        return CaseCreateResponse(
            case_id=client_id,
            status="created",
            created_at=meta.get("created_at", now_str),
            storage_key=f"CASE_{case_uuid.hex}",
        )

    def list_cases(self) -> CaseListResponse:
        cases: list[CaseSummary] = []
        if not self.storage_root.is_dir():
            return CaseListResponse(cases=[], total=0)

        for case_dir in sorted(self.storage_root.iterdir()):
            if not case_dir.is_dir() or not case_dir.name.startswith("CASE_"):
                continue

            case_meta_path = case_dir / "case_meta.json"
            meta: dict[str, str] = {}
            if case_meta_path.is_file():
                try:
                    meta = json.loads(case_meta_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            case_id_display = meta.get("client_id") or case_dir.name.removeprefix("CASE_")
            created_at = meta.get("created_at") or datetime.fromtimestamp(case_dir.stat().st_ctime, timezone.utc).isoformat()

            # Count documents
            doc_count = 0
            index_path = case_dir / "uploads" / "upload_index.json"
            if index_path.is_file():
                try:
                    docs = json.loads(index_path.read_text(encoding="utf-8"))
                    doc_count = len(docs)
                except (json.JSONDecodeError, OSError):
                    pass
            elif (case_dir / "originals").is_dir():
                doc_count = len([f for f in (case_dir / "originals").iterdir() if f.is_file()])

            # Read validation disposition if available
            val_path = case_dir / "processed" / "validation" / "validation_report.json"
            disposition: str | None = None
            if val_path.is_file():
                try:
                    val_data = json.loads(val_path.read_text(encoding="utf-8"))
                    disposition = val_data.get("disposition")
                except (json.JSONDecodeError, OSError):
                    pass

            # Read review status if available
            rev_path = case_dir / "processed" / "chargesheet" / "review_state.json"
            review_status: str | None = None
            if rev_path.is_file():
                try:
                    rev_data = json.loads(rev_path.read_text(encoding="utf-8"))
                    review_status = rev_data.get("status")
                except (json.JSONDecodeError, OSError):
                    pass

            status = "processed" if val_path.is_file() else ("documents_uploaded" if doc_count > 0 else "created")

            cases.append(
                CaseSummary(
                    case_id=case_id_display,
                    created_at=created_at,
                    document_count=doc_count,
                    status=status,
                    validation_disposition=disposition,
                    review_status=review_status,
                )
            )

        return CaseListResponse(cases=cases, total=len(cases))

    def get_case(self, case_id: str) -> CaseDetailResponse:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        meta_path = layout.case_directory / "case_meta.json"
        meta: dict[str, str] = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        created_at = meta.get("created_at") or datetime.fromtimestamp(layout.case_directory.stat().st_ctime, timezone.utc).isoformat()

        # Read uploaded documents from upload_index.json
        documents: list[CaseDocumentItem] = []
        index_path = layout.case_directory / "uploads" / "upload_index.json"
        if index_path.is_file():
            try:
                docs = json.loads(index_path.read_text(encoding="utf-8"))
                for doc in docs:
                    documents.append(
                        CaseDocumentItem(
                            document_id=doc["document_id"],
                            original_filename=doc["original_filename"],
                            stored_filename=doc["stored_filename"],
                            size_bytes=doc["size_bytes"],
                            media_type=doc["media_type"],
                            uploaded_at=doc["uploaded_at"],
                        )
                    )
            except (json.JSONDecodeError, OSError):
                pass

        # Validation report
        val_path = layout.processed_directory / "validation" / "validation_report.json"
        disposition: str | None = None
        if val_path.is_file():
            try:
                val_data = json.loads(val_path.read_text(encoding="utf-8"))
                disposition = val_data.get("disposition")
            except (json.JSONDecodeError, OSError):
                pass

        # Review status
        rev_path = layout.processed_directory / "chargesheet" / "review_state.json"
        review_status: str | None = None
        if rev_path.is_file():
            try:
                rev_data = json.loads(rev_path.read_text(encoding="utf-8"))
                review_status = rev_data.get("status")
            except (json.JSONDecodeError, OSError):
                pass

        # List existing artifacts
        artifacts_available: list[str] = []
        if layout.processed_directory.is_dir():
            for p in layout.processed_directory.rglob("*"):
                if p.is_file():
                    artifacts_available.append(str(p.relative_to(layout.processed_directory)).replace("\\", "/"))

        status = "processed" if val_path.is_file() else ("documents_uploaded" if len(documents) > 0 else "created")

        return CaseDetailResponse(
            case_id=client_id,
            created_at=created_at,
            title=meta.get("title"),
            description=meta.get("description"),
            status=status,
            document_count=len(documents),
            documents=documents,
            validation_disposition=disposition,
            review_status=review_status,
            artifacts_available=artifacts_available,
        )

    def upload_documents(self, case_id: str, files: list[UploadFile]) -> DocumentUploadResponse:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        if not files:
            raise EmptyUploadError("No files provided in upload request.")

        uploads_dir = layout.case_directory / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        index_path = uploads_dir / "upload_index.json"

        existing_docs: list[dict[str, Any]] = []
        if index_path.is_file():
            try:
                existing_docs = json.loads(index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing_docs = []

        current_case_size = sum(d.get("size_bytes", 0) for d in existing_docs)
        uploaded_items: list[DocumentUploadItem] = []
        failed_count = 0

        for file in files:
            raw_filename = file.filename or ""
            # Validate filename safety
            if not raw_filename or not raw_filename.strip():
                uploaded_items.append(
                    DocumentUploadItem(
                        document_id=str(uuid4()),
                        original_filename="[unnamed]",
                        size_bytes=0,
                        media_type="application/octet-stream",
                        status="rejected",
                        errors=["Filename cannot be empty."],
                    )
                )
                failed_count += 1
                continue

            cleaned_filename = Path(raw_filename).name
            if "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename:
                raise InvalidFilenameError(raw_filename, "Path traversal characters are forbidden.")

            extension = Path(cleaned_filename).suffix.lower()
            if extension not in SUPPORTED_MEDIA_TYPES:
                raise UnsupportedMediaTypeError(cleaned_filename, extension or "[none]")

            doc_id = uuid4()
            stored_filename = f"{doc_id}_{cleaned_filename}"
            target_path = uploads_dir / stored_filename

            # Stream chunks to prevent OOM
            file_bytes = 0
            try:
                with target_path.open("wb") as out:
                    while True:
                        chunk = file.file.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        file_bytes += len(chunk)
                        if file_bytes > api_config.max_upload_file_size_bytes:
                            out.close()
                            if target_path.is_file():
                                target_path.unlink()
                            raise FileSizeLimitExceededError(
                                cleaned_filename,
                                file_bytes,
                                api_config.max_upload_file_size_bytes,
                            )
                        if current_case_size + file_bytes > api_config.max_case_upload_size_bytes:
                            out.close()
                            if target_path.is_file():
                                target_path.unlink()
                            raise CaseSizeLimitExceededError(
                                current_case_size + file_bytes,
                                api_config.max_case_upload_size_bytes,
                            )
                        out.write(chunk)
            except (FileSizeLimitExceededError, CaseSizeLimitExceededError):
                raise
            except Exception as exc:
                if target_path.is_file():
                    target_path.unlink()
                uploaded_items.append(
                    DocumentUploadItem(
                        document_id=str(doc_id),
                        original_filename=cleaned_filename,
                        size_bytes=file_bytes,
                        media_type=file.content_type or "application/octet-stream",
                        status="rejected",
                        errors=[f"Streaming failed: {exc}"],
                    )
                )
                failed_count += 1
                continue

            # Run validation check on saved file
            val_res = self.validator.validate(target_path)
            if not val_res.is_valid:
                if target_path.is_file():
                    target_path.unlink()
                uploaded_items.append(
                    DocumentUploadItem(
                        document_id=str(doc_id),
                        original_filename=cleaned_filename,
                        size_bytes=val_res.size_bytes,
                        media_type=val_res.detected_mime_type or "application/octet-stream",
                        status="rejected",
                        errors=list(val_res.errors),
                    )
                )
                failed_count += 1
                continue

            # Validated successfully
            now_iso = datetime.now(timezone.utc).isoformat()
            detected_media = val_res.detected_mime_type or SUPPORTED_MEDIA_TYPES.get(extension, "application/octet-stream")
            record = {
                "document_id": str(doc_id),
                "original_filename": cleaned_filename,
                "stored_filename": stored_filename,
                "size_bytes": val_res.size_bytes,
                "media_type": detected_media,
                "uploaded_at": now_iso,
            }
            existing_docs.append(record)
            current_case_size += val_res.size_bytes

            uploaded_items.append(
                DocumentUploadItem(
                    document_id=str(doc_id),
                    original_filename=cleaned_filename,
                    size_bytes=val_res.size_bytes,
                    media_type=detected_media,
                    status="uploaded",
                )
            )

        # Write updated upload_index.json
        index_path.write_text(json.dumps(existing_docs, indent=2), encoding="utf-8")

        return DocumentUploadResponse(
            case_id=client_id,
            uploaded_count=len(uploaded_items) - failed_count,
            failed_count=failed_count,
            documents=uploaded_items,
        )

    def delete_case(self, case_id: str) -> CaseDeleteResponse:
        """Permanently delete a case workspace, all uploaded files, and generated artifacts."""
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        target_dir = layout.case_directory
        if not target_dir.is_dir():
            alt_dir = self.storage_root / f"CASE_{client_id}"
            if alt_dir.is_dir():
                target_dir = alt_dir
            else:
                raise CaseNotFoundError(case_id)

        import os
        import shutil
        import stat

        def _on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        shutil.rmtree(target_dir, onerror=_on_rm_error)

        return CaseDeleteResponse(
            case_id=client_id,
            status="deleted",
            message=f"Case '{client_id}' and all associated evidence were permanently deleted.",
        )
