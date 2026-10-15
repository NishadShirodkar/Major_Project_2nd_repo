"""Phase 1 deterministic fact tagging from typed canonical investigation fields."""

from __future__ import annotations

import re
from typing import Any

from ..normalization.canonical_models import (
    CanonicalEvidence,
    CanonicalFact,
    CanonicalInvestigation,
    CanonicalPerson,
    CanonicalTimelineEvent,
    CanonicalVehicle,
)

NEGATIVE_INJURY_PATTERNS = (
    "no injury",
    "no external injury",
    "no visible injury",
    "no significant injury",
    "no fresh injury",
    "absence of injury",
    "without any injury",
    "nil injury",
)

INJURY_KEYWORDS = (
    "injury",
    "injuries",
    "wound",
    "laceration",
    "abrasion",
    "contusion",
    "hematoma",
    "fracture",
    "bleeding",
    "swelling",
    "burn",
    "cut",
)

GRIEVOUS_KEYWORDS = (
    "fracture",
    "grievous",
    "dislocation",
    "permanent privation",
    "loss of sight",
    "loss of hearing",
    "emasculation",
    "bone fracture",
    "deep laceration",
)

DANGEROUS_WEAPON_KEYWORDS = (
    "knife",
    "dagger",
    "sword",
    "firearm",
    "gun",
    "pistol",
    "revolver",
    "acid",
    "corrosive",
    "poison",
    "heated substance",
    "iron rod",
)

WEAPON_KEYWORDS = (
    *DANGEROUS_WEAPON_KEYWORDS,
    "lathi",
    "stick",
    "bat",
    "stone",
    "brick",
    "weapon",
    "axe",
    "blade",
)


def _tag_fact(fact: CanonicalFact, new_tags: set[str], vocabulary: set[str]) -> CanonicalFact:
    if not new_tags:
        return fact
    valid_new = {t for t in new_tags if not vocabulary or t in vocabulary}
    if not valid_new:
        return fact
    combined = tuple(dict.fromkeys((*fact.tags, *valid_new)))
    return fact.model_copy(update={"tags": combined})


class DeterministicTagger:
    """Assigns controlled fact tags to CanonicalFacts using deterministic rule matching."""

    def __init__(self, vocabulary: set[str] | None = None) -> None:
        self.vocabulary = vocabulary or set()

    def tag_investigation(self, canonical: CanonicalInvestigation) -> CanonicalInvestigation:
        # 1. Accused tags
        accused_count = len(canonical.accused)
        tagged_accused: list[CanonicalPerson] = []
        for person in canonical.accused:
            tags: set[str] = {"accused.identified"}
            if accused_count >= 2:
                tags.add("accused.multiple")
            if accused_count >= 5:
                tags.add("group.five_or_more")
            tagged_name = _tag_fact(person.name, tags, self.vocabulary)
            tagged_accused.append(person.model_copy(update={"name": tagged_name}))

        # 2. Medical findings
        tagged_medical: list[CanonicalFact] = []
        for fact in canonical.medical_findings:
            text = str(fact.value or "").casefold()
            tags: set[str] = set()
            is_negative = any(neg in text for neg in NEGATIVE_INJURY_PATTERNS)
            if not is_negative and any(kw in text for kw in INJURY_KEYWORDS):
                tags.add("injury.documented")
                if "pain" in text:
                    tags.add("injury.bodily_pain")
                if any(kw in text for kw in GRIEVOUS_KEYWORDS):
                    tags.add("injury.grievous")
                if "survived" in text or "discharge" in text:
                    tags.add("injury.survived_victim")
            tagged_medical.append(_tag_fact(fact, tags, self.vocabulary))

        # 3. Forensic findings
        tagged_forensic: list[CanonicalFact] = []
        for fact in canonical.forensic_findings:
            text = str(fact.value or "").casefold()
            tags: set[str] = set()
            if any(kw in text for kw in ("blood", "stain", "tissue")):
                tags.add("injury.documented")
            if any(kw in text for kw in ("poison", "chemical", "toxic")):
                tags.add("weapon.dangerous")
            tagged_forensic.append(_tag_fact(fact, tags, self.vocabulary))

        # 4. Evidence & Recovered Property
        def tag_evidence_item(item: CanonicalEvidence) -> CanonicalEvidence:
            text = str(item.description.value or "").casefold()
            tags: set[str] = set()
            if any(kw in text for kw in WEAPON_KEYWORDS):
                tags.add("weapon.recovered")
                tags.add("accused.act.weapon_use")
            if any(kw in text for kw in DANGEROUS_WEAPON_KEYWORDS):
                tags.add("weapon.dangerous")
            if any(kw in text for kw in ("cash", "gold", "jewel", "vehicle", "phone", "wallet", "property")):
                tags.add("property.movable")
            tagged_desc = _tag_fact(item.description, tags, self.vocabulary)
            return item.model_copy(update={"description": tagged_desc})

        tagged_evidence = tuple(tag_evidence_item(e) for e in canonical.evidence)
        tagged_recovered = tuple(tag_evidence_item(e) for e in canonical.recovered_property)

        # 5. Vehicles
        tagged_vehicles: list[CanonicalVehicle] = []
        for veh in canonical.vehicles:
            tags: set[str] = {"vehicle.involved"}
            tagged_reg = _tag_fact(veh.registration_number, tags, self.vocabulary)
            tagged_vehicles.append(veh.model_copy(update={"registration_number": tagged_reg}))

        # 6. Timeline events
        tagged_timeline: list[CanonicalTimelineEvent] = []
        for event in canonical.timeline:
            text = str(event.description.value or "").casefold()
            tags: set[str] = set()
            if any(kw in text for kw in ("accident", "collision", "hit", "crash")):
                tags.add("accident.occurred")
                tags.add("vehicle.involved")
            if any(kw in text for kw in ("road", "highway", "street", "public way", "junction")):
                tags.add("driving.on_public_way")
            if any(kw in text for kw in ("rush", "rash", "negligent", "speed", "overspeed")):
                tags.add("vehicle.rash_or_negligent_indicators")
                tags.add("negligence.indicators")
            if any(kw in text for kw in ("threat", "threaten", "warned")):
                tags.add("threat.communicated")
                tags.add("accused.act.threat")
            if any(kw in text for kw in ("strike", "push", "beat", "assault", "stab", "punch")):
                tags.add("accused.act.physical")
            tagged_desc = _tag_fact(event.description, tags, self.vocabulary)
            tagged_timeline.append(event.model_copy(update={"description": tagged_desc}))

        # 7. Document attributes (postmortem, seizure, inspection)
        tagged_docs = []
        for doc in canonical.documents:
            doc_type = str(doc.document_type.value if doc.document_type else "").casefold()
            updated_attrs = dict(doc.attributes)
            for attr_name, attr_fact in doc.attributes.items():
                val_text = str(attr_fact.value or "").casefold()
                tags: set[str] = set()
                if "postmortem" in doc_type or "autopsy" in doc_type:
                    if "cause" in attr_name.casefold() or "cause_of_death" in attr_name.casefold():
                        tags.add("death.cause_documented")
                        tags.add("death.confirmed")
                        if any(kw in val_text for kw in ("asphyxia", "homicide", "burn", "poison", "stab", "hanging")):
                            tags.add("death.unnatural_circumstances")
                elif "vehicle" in doc_type:
                    tags.add("vehicle.involved")
                    if any(kw in val_text for kw in ("damage", "impact", "rash", "speed")):
                        tags.add("vehicle.rash_or_negligent_indicators")
                elif "seizure" in doc_type:
                    if any(kw in val_text for kw in WEAPON_KEYWORDS):
                        tags.add("weapon.recovered")
                if tags:
                    updated_attrs[attr_name] = _tag_fact(attr_fact, tags, self.vocabulary)
            tagged_docs.append(doc.model_copy(update={"attributes": updated_attrs}))

        return canonical.model_copy(update={
            "accused": tuple(tagged_accused),
            "medical_findings": tuple(tagged_medical),
            "forensic_findings": tuple(tagged_forensic),
            "evidence": tagged_evidence,
            "recovered_property": tagged_recovered,
            "vehicles": tuple(tagged_vehicles),
            "timeline": tuple(tagged_timeline),
            "documents": tuple(tagged_docs),
        })

