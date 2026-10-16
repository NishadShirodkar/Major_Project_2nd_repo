"""HTTP and domain-level exceptions for the Byomkesh AI service layer."""

from __future__ import annotations


class APIError(Exception):
    """Base error for API-level failures."""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class InvalidCaseIdError(APIError):
    def __init__(self, message: str = "Invalid case ID format or characters.") -> None:
        super().__init__(message, status_code=400, error_code="INVALID_CASE_ID")


class CaseNotFoundError(APIError):
    def __init__(self, case_id: str) -> None:
        super().__init__(f"Case '{case_id}' was not found.", status_code=404, error_code="CASE_NOT_FOUND")


class EmptyUploadError(APIError):
    def __init__(self, message: str = "No files were provided in the upload request.") -> None:
        super().__init__(message, status_code=400, error_code="EMPTY_UPLOAD")


class InvalidFilenameError(APIError):
    def __init__(self, filename: str, reason: str = "Filename contains invalid or dangerous path characters.") -> None:
        super().__init__(f"Invalid filename '{filename}': {reason}", status_code=400, error_code="INVALID_FILENAME")


class FileSizeLimitExceededError(APIError):
    def __init__(self, filename: str, size_bytes: int, limit_bytes: int) -> None:
        super().__init__(
            f"File '{filename}' ({size_bytes} bytes) exceeds the limit of {limit_bytes} bytes.",
            status_code=413,
            error_code="FILE_SIZE_LIMIT_EXCEEDED",
        )


class CaseSizeLimitExceededError(APIError):
    def __init__(self, total_bytes: int, limit_bytes: int) -> None:
        super().__init__(
            f"Total case uploads ({total_bytes} bytes) exceed the case limit of {limit_bytes} bytes.",
            status_code=413,
            error_code="CASE_SIZE_LIMIT_EXCEEDED",
        )


class UnsupportedMediaTypeError(APIError):
    def __init__(self, filename: str, extension: str) -> None:
        super().__init__(
            f"File '{filename}' has unsupported extension '{extension}'.",
            status_code=415,
            error_code="UNSUPPORTED_MEDIA_TYPE",
        )


class CaseAlreadyProcessingError(APIError):
    def __init__(self, case_id: str, job_id: str | None = None) -> None:
        msg = f"Case '{case_id}' is already actively being processed" + (f" by job '{job_id}'." if job_id else ".")
        super().__init__(msg, status_code=409, error_code="CASE_ALREADY_PROCESSING")
        self.case_id = case_id
        self.job_id = job_id


class NoDocumentsUploadedError(APIError):
    def __init__(self, case_id: str) -> None:
        super().__init__(
            f"Case '{case_id}' has no uploaded documents. Please upload documents before processing.",
            status_code=400,
            error_code="NO_DOCUMENTS_UPLOADED",
        )


class JobNotFoundError(APIError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' was not found.", status_code=404, error_code="JOB_NOT_FOUND")


class ArtifactNotFoundError(APIError):
    def __init__(self, message: str = "Requested artifact was not found.") -> None:
        super().__init__(message, status_code=404, error_code="ARTIFACT_NOT_FOUND")


class ArtifactSecurityError(APIError):
    def __init__(self, message: str = "Artifact access outside managed storage root is forbidden.") -> None:
        super().__init__(message, status_code=403, error_code="ARTIFACT_ACCESS_FORBIDDEN")


class DependencyUnavailableError(APIError):
    def __init__(self, service: str, reason: str) -> None:
        super().__init__(f"Required dependency '{service}' is unavailable: {reason}", status_code=503, error_code="SERVICE_UNAVAILABLE")
