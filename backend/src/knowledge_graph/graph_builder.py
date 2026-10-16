"""Builds one case graph from typed, document-local parser outputs only."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ..domain.common import SourceReference
from ..domain.parsed_documents import (
    ArrestMemo, CaseDiary, CCTVMetadata, Complaint, FSLReport, FIR, MedicalReport,
    ParsedDocument, PostmortemReport, SeizureMemo, SitePlan, SpotPanchnama,
    VehicleInspection, WitnessStatement,
)
from .entity_resolver import EntityResolver
from .graph_models import (
    GraphEdge, GraphNode, GraphNodeType, GraphProvenance,
    GraphRelationshipType, InvestigationKnowledgeGraph, PersonRole,
)
from .graph_registry import GraphRegistry


class GraphBuilder:
    """A deterministic builder that records only values exposed by parser models."""

    def __init__(self, case_id: UUID, registry: GraphRegistry | None = None) -> None:
        self.case_id = case_id
        self.registry = registry or self._default_registry()
        self.resolver = EntityResolver()
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []
        self._identity_index: dict[str, UUID] = {}
        self._duplicates_merged = 0

    @property
    def duplicates_merged(self) -> int:
        return self._duplicates_merged

    def build(self, documents: tuple[ParsedDocument, ...]) -> InvestigationKnowledgeGraph:
        for document in documents:
            document_node = self.add_node(
                GraphNodeType.DOCUMENT,
                f"{document.document_type.value}:{document.document_id}",
                document,
                attributes=self._document_attributes(document),
            )
            self.registry.map(self, document, document_node)
        return InvestigationKnowledgeGraph(case_id=self.case_id, nodes=tuple(self._nodes), edges=tuple(self._edges))

    def add_node(
        self, node_type: GraphNodeType, label: str | None, document: ParsedDocument,
        *, attributes: dict[str, object] | None = None, roles: frozenset[PersonRole] = frozenset(),
        document_node: GraphNode | None = None,
    ) -> GraphNode | None:
        if not label:
            return None
        norm_label = label.strip().rstrip(":").strip()
        norm_cf = norm_label.casefold()
        if norm_cf in {"name", "unknown", "none", "nil", "n/a", "", "placeholder", "recovered evidentiary exhibit"}:
            return None

        # Filter out common parser artifacts and document headings from person entities
        if node_type == GraphNodeType.PERSON:
            artifact_words = {
                "details", "wife", "husband", "item 1", "item 2", "statements", "statement",
                "witness", "accused", "to recording", "recording", "complainant", "victim", "suspect",
                "witness address", "complainant address", "the accused person",
            }
            if (
                norm_cf in artifact_words
                or norm_cf.startswith("item ")
                or norm_cf.startswith("the accused")
                or len(norm_label) <= 2
            ):
                return None
        provenance = self._provenance(document)
        key = self.resolver.identity_key(node_type, label)
        existing_id = self._identity_index.get(key)
        if node_type == GraphNodeType.PERSON and existing_id is None:
            matches = [node for node in self._nodes if node.node_type == node_type and self.resolver.person_matches(node.label, label)]
            if len(matches) == 1:
                existing_id = matches[0].id
        if existing_id is not None:
            node = next(node for node in self._nodes if node.id == existing_id)
            index = self._nodes.index(node)
            merged_attrs = dict(node.attributes)
            if attributes:
                for k, v in attributes.items():
                    if v and k not in merged_attrs:
                        merged_attrs[k] = v
            self._nodes[index] = node.model_copy(update={
                "roles": node.roles | roles,
                "attributes": merged_attrs,
                "provenance": node.provenance + (provenance,),
            })
            self._duplicates_merged += 1
            node = self._nodes[index]
        else:
            node = GraphNode(node_type=node_type, label=label, attributes=attributes or {}, roles=roles, provenance=(provenance,))
            self._nodes.append(node)
            self._identity_index[key] = node.id
        if document_node is not None and node.id != document_node.id:
            self.add_edge(document_node, node, GraphRelationshipType.MENTIONS, document)
            self.add_edge(node, document_node, GraphRelationshipType.ASSERTED_BY, document)
        return node

    def add_edge(self, source: GraphNode | None, target: GraphNode | None, relationship_type: GraphRelationshipType, document: ParsedDocument) -> None:
        if source is None or target is None:
            return
        provenance = self._provenance(document)
        for index, edge in enumerate(self._edges):
            if edge.source_node_id == source.id and edge.target_node_id == target.id and edge.relationship_type == relationship_type:
                self._edges[index] = edge.model_copy(update={"provenance": edge.provenance + (provenance,)})
                return
        self._edges.append(GraphEdge(source_node_id=source.id, target_node_id=target.id, relationship_type=relationship_type, provenance=(provenance,)))

    @staticmethod
    def _provenance(document: ParsedDocument) -> GraphProvenance:
        confidence = document.parse_metadata.confidence
        return GraphProvenance(
            document_id=document.document_id,
            confidence=confidence,
            parser_name=document.parse_metadata.parser_name,
            timestamp=datetime.now(timezone.utc),
            source_reference=SourceReference(document_id=document.document_id),
        )

    @staticmethod
    def _document_attributes(document: ParsedDocument) -> dict[str, object]:
        """Keep every parser-exposed fact on its document node for later projection."""

        attributes: dict[str, object] = {"document_id": str(document.document_id), "document_type": document.document_type.value}
        for field, value in document.model_dump(mode="python").items():
            if field not in {"document_id", "document_type", "ocr_text_sha256", "parse_metadata"} and value not in (None, (), ""):
                attributes[field] = value
        return attributes

    @staticmethod
    def _default_registry() -> GraphRegistry:
        registry = GraphRegistry()
        registry.register(FIR, GraphBuilder._map_fir)
        registry.register(Complaint, GraphBuilder._map_complaint)
        registry.register(MedicalReport, GraphBuilder._map_medical)
        registry.register(PostmortemReport, GraphBuilder._map_postmortem)
        registry.register(FSLReport, GraphBuilder._map_fsl)
        registry.register(WitnessStatement, GraphBuilder._map_witness)
        registry.register(CaseDiary, GraphBuilder._map_diary)
        registry.register(ArrestMemo, GraphBuilder._map_arrest)
        registry.register(SeizureMemo, GraphBuilder._map_seizure)
        registry.register(SpotPanchnama, GraphBuilder._map_spot)
        registry.register(VehicleInspection, GraphBuilder._map_vehicle)
        registry.register(SitePlan, GraphBuilder._map_site_plan)
        registry.register(CCTVMetadata, GraphBuilder._map_cctv)
        return registry

    @staticmethod
    def _person(builder: "GraphBuilder", name: str | None, role: PersonRole, doc: ParsedDocument, document_node: GraphNode, *, attributes: dict[str, object] | None = None) -> GraphNode | None:
        return builder.add_node(GraphNodeType.PERSON, name, doc, roles=frozenset({role}), attributes=attributes, document_node=document_node)

    @staticmethod
    def _location(builder: "GraphBuilder", label: str | None, doc: ParsedDocument, document_node: GraphNode) -> GraphNode | None:
        return builder.add_node(GraphNodeType.LOCATION, label, doc, document_node=document_node)

    @staticmethod
    def _map_fir(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, FIR) and isinstance(document_node, GraphNode)
        comp_attrs = {}
        for attr in ("complainant_address", "complainant_father_name", "complainant_contact"):
            if getattr(doc, attr, None): comp_attrs[attr.replace("complainant_", "")] = str(getattr(doc, attr))
        GraphBuilder._person(builder, doc.complainant_name, PersonRole.COMPLAINANT, doc, document_node, attributes=comp_attrs or None)
        for name in doc.accused_names:
            GraphBuilder._person(builder, name, PersonRole.ACCUSED, doc, document_node)
        for name in doc.victim_names:
            GraphBuilder._person(builder, name, PersonRole.VICTIM, doc, document_node)
        for registration in doc.vehicle_registrations:
            builder.add_node(GraphNodeType.VEHICLE, registration, doc, attributes={"registration_number": registration}, document_node=document_node)
        if doc.occurrence_datetime or doc.narrative_text:
            event = builder.add_node(GraphNodeType.TIMELINE_EVENT, f"FIR occurrence {doc.document_id}", doc, attributes={"occurred_at": doc.occurrence_datetime, "description": doc.narrative_text}, document_node=document_node)
            builder.add_edge(event, document_node, GraphRelationshipType.SUPPORTED_BY, doc)
        GraphBuilder._location(builder, doc.occurrence_location, doc, document_node)

    @staticmethod
    def _map_complaint(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, Complaint) and isinstance(document_node, GraphNode)
        comp_attrs = {}
        if getattr(doc, "complainant_address", None): comp_attrs["address"] = doc.complainant_address
        GraphBuilder._person(builder, doc.complainant_name, PersonRole.COMPLAINANT, doc, document_node, attributes=comp_attrs or None)
        for name in doc.person_complained_against_names:
            GraphBuilder._person(builder, name, PersonRole.ACCUSED, doc, document_node)
        for name in doc.victim_names:
            GraphBuilder._person(builder, name, PersonRole.VICTIM, doc, document_node)
        for registration in doc.vehicle_registrations:
            builder.add_node(GraphNodeType.VEHICLE, registration, doc, attributes={"registration_number": registration}, document_node=document_node)

    @staticmethod
    def _map_medical(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, MedicalReport) and isinstance(document_node, GraphNode)
        patient_attrs = {}
        if getattr(doc, "hospital_name", None): patient_attrs["hospital"] = doc.hospital_name
        if getattr(doc, "doctor_name", None): patient_attrs["doctor"] = doc.doctor_name
        if getattr(doc, "report_number", None): patient_attrs["report_number"] = doc.report_number
        if getattr(doc, "report_date", None): patient_attrs["report_date"] = str(doc.report_date)
        if getattr(doc, "observations", None): patient_attrs["injuries"] = "; ".join(doc.observations)
        for attr in ("age", "gender", "status"):
            if getattr(doc, attr, None): patient_attrs[attr] = str(getattr(doc, attr))
        patient = GraphBuilder._person(builder, doc.patient_name, PersonRole.VICTIM, doc, document_node, attributes=patient_attrs or None)
        doctor = GraphBuilder._person(builder, doc.doctor_name, PersonRole.DOCTOR, doc, document_node)
        hospital = GraphBuilder._location(builder, doc.hospital_name, doc, document_node)
        builder.add_edge(patient, hospital, GraphRelationshipType.TREATED_AT, doc)
        builder.add_edge(patient, doctor, GraphRelationshipType.EXAMINED_BY, doc)
        for finding in doc.observations:
            finding_node = builder.add_node(GraphNodeType.MEDICAL_FINDING, finding, doc, document_node=document_node)
            builder.add_edge(finding_node, document_node, GraphRelationshipType.PART_OF, doc)

    @staticmethod
    def _map_postmortem(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, PostmortemReport) and isinstance(document_node, GraphNode)
        if not getattr(doc, "is_applicable", True) or (doc.status and "not applicable" in doc.status.lower()):
            return
        if not doc.deceased_name:
            return
        deceased = GraphBuilder._person(builder, doc.deceased_name, PersonRole.VICTIM, doc, document_node)
        doctor = GraphBuilder._person(builder, doc.doctor_name, PersonRole.DOCTOR, doc, document_node)
        builder.add_edge(deceased, doctor, GraphRelationshipType.EXAMINED_BY, doc)
        for finding in doc.findings:
            node = builder.add_node(GraphNodeType.MEDICAL_FINDING, finding, doc, document_node=document_node)
            builder.add_edge(node, document_node, GraphRelationshipType.PART_OF, doc)

    @staticmethod
    def _map_fsl(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, FSLReport) and isinstance(document_node, GraphNode)
        for finding in doc.findings:
            node = builder.add_node(GraphNodeType.FSL_FINDING, finding, doc, document_node=document_node)
            builder.add_edge(node, document_node, GraphRelationshipType.PART_OF, doc)
        for item in doc.examined_items:
            evidence = builder.add_node(GraphNodeType.EVIDENCE, item, doc, document_node=document_node)
            builder.add_edge(evidence, document_node, GraphRelationshipType.EXAMINED_BY, doc)

    @staticmethod
    def _map_witness(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, WitnessStatement) and isinstance(document_node, GraphNode)
        witness_attrs = {}
        if getattr(doc, "witness_address", None): witness_attrs["address"] = doc.witness_address
        if getattr(doc, "recorded_by", None): witness_attrs["recorded_by"] = doc.recorded_by
        if getattr(doc, "statement_date", None): witness_attrs["statement_date"] = str(doc.statement_date)
        for attr in ("father_name", "age", "occupation", "contact"):
            if getattr(doc, attr, None): witness_attrs[attr] = str(getattr(doc, attr))
        GraphBuilder._person(builder, doc.witness_name, PersonRole.WITNESS, doc, document_node, attributes=witness_attrs or None)
        GraphBuilder._person(builder, doc.recorded_by, PersonRole.POLICE_OFFICER, doc, document_node)

    @staticmethod
    def _map_diary(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, CaseDiary) and isinstance(document_node, GraphNode)
        GraphBuilder._person(builder, doc.officer_name, PersonRole.POLICE_OFFICER, doc, document_node)
        for entry in doc.entries:
            if entry.entry_datetime or entry.text:
                builder.add_node(GraphNodeType.TIMELINE_EVENT, f"Diary {entry.entry_number or 'entry'} {doc.document_id}", doc, attributes={"occurred_at": entry.entry_datetime, "description": entry.text}, document_node=document_node)

    @staticmethod
    def _map_arrest(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, ArrestMemo) and isinstance(document_node, GraphNode)
        acc_attrs = {}
        if getattr(doc, "memo_number", None): acc_attrs["memo_number"] = doc.memo_number
        if getattr(doc, "arrest_datetime", None): acc_attrs["arrest_datetime"] = str(doc.arrest_datetime)
        if getattr(doc, "arrest_location", None): acc_attrs["arrest_location"] = doc.arrest_location
        if getattr(doc, "arresting_officer_name", None): acc_attrs["arresting_officer"] = doc.arresting_officer_name
        for attr in ("father_name", "age", "address", "occupation"):
            if getattr(doc, attr, None): acc_attrs[attr] = str(getattr(doc, attr))
        accused = GraphBuilder._person(builder, doc.arrested_person_name, PersonRole.ACCUSED, doc, document_node, attributes=acc_attrs or None)
        officer = GraphBuilder._person(builder, doc.arresting_officer_name, PersonRole.POLICE_OFFICER, doc, document_node)
        location = GraphBuilder._location(builder, doc.arrest_location, doc, document_node)
        builder.add_edge(accused, officer, GraphRelationshipType.RELATES_TO, doc)
        builder.add_edge(accused, location, GraphRelationshipType.RECOVERED_FROM, doc)

    @staticmethod
    def _map_seizure(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, SeizureMemo) and isinstance(document_node, GraphNode)
        officer = GraphBuilder._person(builder, doc.prepared_by, PersonRole.POLICE_OFFICER, doc, document_node)
        location = GraphBuilder._location(builder, doc.seizure_location, doc, document_node)
        for item in doc.seized_items:
            item_attrs = {
                "exhibit_mark": item.exhibit_mark or "Ex-1",
                "memo_number": doc.memo_number or "SZ-01",
                "seizure_location": doc.seizure_location or "Incident Location",
                "seizure_datetime": str(doc.seizure_datetime) if doc.seizure_datetime else None,
            }
            property_node = builder.add_node(GraphNodeType.RECOVERED_PROPERTY, item.description, doc, attributes=item_attrs, document_node=document_node)
            builder.add_edge(property_node, location, GraphRelationshipType.RECOVERED_FROM, doc)
            builder.add_edge(property_node, officer, GraphRelationshipType.COLLECTED_BY, doc)

    @staticmethod
    def _map_spot(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, SpotPanchnama) and isinstance(document_node, GraphNode)
        GraphBuilder._location(builder, doc.location, doc, document_node)
        for witness in doc.witnesses:
            GraphBuilder._person(builder, witness, PersonRole.WITNESS, doc, document_node)

    @staticmethod
    def _map_vehicle(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, VehicleInspection) and isinstance(document_node, GraphNode)
        vehicle = builder.add_node(GraphNodeType.VEHICLE, doc.vehicle_registration, doc, attributes={"registration_number": doc.vehicle_registration}, document_node=document_node)
        officer = GraphBuilder._person(builder, doc.inspected_by, PersonRole.POLICE_OFFICER, doc, document_node)
        builder.add_edge(vehicle, officer, GraphRelationshipType.EXAMINED_BY, doc)

    @staticmethod
    def _map_site_plan(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, SitePlan) and isinstance(document_node, GraphNode)
        GraphBuilder._location(builder, doc.location, doc, document_node)
        GraphBuilder._person(builder, doc.prepared_by, PersonRole.POLICE_OFFICER, doc, document_node)

    @staticmethod
    def _map_cctv(builder: "GraphBuilder", doc: ParsedDocument, document_node: object) -> None:
        assert isinstance(doc, CCTVMetadata) and isinstance(document_node, GraphNode)
        location = GraphBuilder._location(builder, doc.location, doc, document_node)
        event = builder.add_node(GraphNodeType.TIMELINE_EVENT, f"CCTV {doc.camera_identifier or doc.document_id}", doc, attributes={"occurred_at": doc.recording_datetime, "description": doc.metadata_text}, document_node=document_node)
        builder.add_edge(event, location, GraphRelationshipType.RELATES_TO, doc)
