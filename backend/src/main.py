"""CLI entry point for the typed investigation-to-draft-charge-sheet workflow."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from .config import Config
from .intake.upload_manager import IncomingUpload
from .validation.validation_models import ValidationDisposition
from .workflow.production import create_workflow_context, run_production_workflow
from .api.app import app


def _case_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"byomkesh-ai-case:{value}")


def _discover_uploads(input_directory: Path) -> tuple[IncomingUpload, ...]:
    if not input_directory.is_dir():
        raise ValueError(f"Input directory does not exist: {input_directory}")
    return tuple(
        IncomingUpload(source_path=path, original_filename=path.name)
        for path in sorted(input_directory.iterdir())
        if path.is_file()
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the typed Byomkesh AI charge-sheet workflow.")
    parser.add_argument("--case-id", required=True, help="UUID or stable external case identifier")
    parser.add_argument("--input-dir", required=True, type=Path, help="Directory containing case source documents")
    parser.add_argument("--output-dir", required=True, type=Path, help="Root directory for typed case artifacts")
    parser.add_argument("--gemini-api-key", default=Config.GEMINI_API_KEY, help="Gemini key; defaults to GEMINI_API_KEY")
    parser.add_argument("--gemini-model", default=Config.GEMINI_MODEL, help="Gemini model; defaults to GEMINI_MODEL")
    parser.add_argument("--resume", action="store_true", help="Reuse only OCR artifacts validated against this case's persisted manifest.")
    parser.add_argument("--mock-llm", action="store_true", help="Run with deterministic synthetic mock OCR and Parser clients for offline testing and verification without calling Gemini.")
    parser.add_argument("--legal-reference-path", type=Path, default=None, help="Path to BNS legal references JSON (defaults to bundled references/legal/bns_sections.json).")
    parser.add_argument("--legal-reference-version", default=Config.LEGAL_REFERENCE_VERSION or "bns-2023-2024-07-01", help="Legal reference version tag.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        uploads = _discover_uploads(args.input_dir)
        if not uploads:
            raise ValueError(f"No files found in input directory: {args.input_dir}")

        mock_mode = args.mock_llm or bool(os.getenv("BYOMKESH_MOCK_LLM"))
        if not mock_mode and not args.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for OCR and document parsing (or specify --mock-llm for offline execution)")

        # Resolve legal reference path: explicit CLI arg -> environment config -> bundled reference
        legal_ref_path = args.legal_reference_path
        if legal_ref_path is None:
            if Config.LEGAL_REFERENCE_PATH:
                legal_ref_path = Path(Config.LEGAL_REFERENCE_PATH)
            else:
                bundled_path = Path(__file__).resolve().parent.parent / "references" / "legal" / "bns_sections.json"
                if bundled_path.is_file():
                    legal_ref_path = bundled_path

        case_id = _case_id(args.case_id)
        context = create_workflow_context(case_id, uploads, resume=args.resume, storage_root=args.output_dir)

        dependencies: dict[str, object] = {
            "legal_reference_path": legal_ref_path,
            "legal_reference_version": args.legal_reference_version,
            "resume": args.resume,
        }

        if mock_mode:
            from .extraction.mock_client import MockOCRClient, MockParserClient
            dependencies["ocr_client"] = MockOCRClient()
            dependencies["parser_client"] = MockParserClient()
        else:
            dependencies["gemini_api_key"] = args.gemini_api_key
            dependencies["gemini_model"] = args.gemini_model

        result = run_production_workflow(
            args.output_dir,
            context,
            **dependencies,
        )
    except (ValueError, OSError) as exc:
        print(f"Configuration error: {exc}")
        return 2

    print("Stage summary:")
    for record in result.report.stage_records:
        detail = f" ({record.exception.message})" if record.exception else ""
        print(f"- {record.stage_name}: {record.status.value}{detail}")
    print("Generated artifacts:")
    for artifact in result.context.generated_artifacts:
        print(f"- {artifact.name}: {artifact.storage_key}")

    blocked = result.context.validation_report is not None and result.context.validation_report.disposition == ValidationDisposition.FINAL_BLOCKED
    if not result.report.successful or blocked:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
