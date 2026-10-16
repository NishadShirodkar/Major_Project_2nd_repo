from ..domain.documents import DocumentType
from ..domain.parsed_documents import PostmortemReport
from .base_parser import BaseDocumentParser


class PostmortemParser(BaseDocumentParser[PostmortemReport]):
    document_type = DocumentType.POSTMORTEM_REPORT
    model_type = PostmortemReport
    supported_entity_fields = ("deceased_name",)

    def _document_specific_instructions(self) -> str:
        return (
            "If the document states that post-mortem examination is not applicable, not required, "
            "or the victim/injured person is alive, set is_applicable to false, status to 'Not Applicable', "
            "deceased_name to null, and explain the reason in opinion_text."
        )
