"""Conservative, deterministic requirements derived from unchanged source text.

This is a small line/section rule set, not a language parser. Offsets refer to
the supplied field (or keyword item), never to casefolded text. No I/O or cache.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

from .models import (
    DetailEvidence, RequirementEvidence, RequirementExtraction, RequirementType,
    SkillRequirement, SourceCondition,
)
from .normalizer import normalize_career
from .skill_extractor import extract_skills
from .skill_taxonomy import SKILL_ALIASES


REQUIREMENT_EXTRACTOR_VERSION = 2
REQUIREMENT_PRECEDENCE = {"required": 0, "preferred": 1, "responsibility": 2, "unspecified": 3}
TEXT_FIELDS = (
    "job_content", "preferred_conditions", "other_preferred_conditions",
    "certificate", "computer_skill", "other_information",
)
PREFERRED_FIELDS = {"preferred_conditions", "other_preferred_conditions"}
CONDITION_FIELDS = ("raw_career_condition", "education", "employment_type", "work_region")

_HEADINGS: dict[str, RequirementType] = {
    **dict.fromkeys(("자격요건", "지원자격", "필수요건", "필수사항", "필수", "requirements",
                     "required", "required skills", "must have", "qualifications"), "required"),
    **dict.fromkeys(("우대사항", "우대조건", "우대", "preferred", "preferred skills",
                     "nice to have", "nice-to-have"), "preferred"),
    **dict.fromkeys(("주요업무", "담당업무", "업무내용", "responsibilities", "duties"), "responsibility"),
    **dict.fromkeys(("기술스택", "사용 기술", "tech stack", "technologies", "복리후생", "혜택",
                     "전형절차", "회사소개", "benefits", "about us", "not required", "not necessary",
                     "필수가 아님", "필수가 아닙니다", "요구하지 않음", "요구하지 않습니다"), "unspecified"),
}
# Wrappers must surround the entire label; prose mentioning a heading is not one.
_DECORATION = re.compile(r"^\s*(?:#{1,6}\s+|[-*•●]\s+|\d+[.)]\s+)?")
_REQUIRED = re.compile(
    r"(?<!\w)필수(?:입니다|사항|요건)?(?!\w)|"
    r"반드시[^,;.!?\n]{0,60}(?:경험|역량|지식|능력|보유|숙지)|"
    r"(?:경험|역량|지식|이해|능력)(?:이|가|은|는)?\s*필요합니다|"
    r"(?<!\w)사용\s+가능자(?!\w)|"
    r"(?<!\w)(?:required|mandatory|must[ -]+have)(?!\w)", re.I,
)
_PREFERRED = re.compile(
    r"(?<!\w)우대(?:합니다|사항|조건)?(?!\w)|"
    r"(?<!\w)(?:preferred|nice[ -]+to[ -]+have)(?!\w)|"
    r"(?:경험|\bexperience\b)[^,;.!?\n]{0,12}\bplus\b|\bis\s+(?:a\s+)?plus\b", re.I,
)
_NEGATED = re.compile(
    r"(?:필수|필요|요구|우대)[^,;.!?\n]{0,24}(?:아니|아닙|아님|아닌|아닐|않|없)|없어도|불필요|"
    r"경험[^,;.!?\n]{0,8}무관|"
    r"\b(?:not|never)\b[^,;.!?\n]{0,30}\b(?:required|mandatory|necessary|preferred|needed|requirement)\b|"
    r"\bno\b[^,;.!?\n]{0,30}\b(?:required|necessary|needed)\b|"
    r"\b(?:do|does)\s+not\s+require\b|\bwithout\b[^,;.!?\n]{0,30}\bexperience\b|"
    r"선택\s*사항|\boptional\b", re.I,
)
_UNCERTAIN = re.compile(r'[?？"“”<>|\[\]【】]|여부|미정|검토|협의|예시|가정|\b(?:if|whether|example|maybe)\b', re.I)
_DUTY = re.compile(
    r"(?<!\w)(?:개발|운영|관리|배포|구축|유지보수)(?:합니다)?(?!\w)|사용\s+업무|"
    r"\b(?:build|develop|maintain|operate|deploy|manage)\b", re.I,
)
_EXPERIENCE = re.compile(r"경험|역량|지식|\b(?:experience|knowledge|proficiency)\b", re.I)
_ALTERNATIVE = re.compile(r"또는|혹은|중\s*하나|\b(?:or|either|one of)\b", re.I)
_CONJUNCTION = re.compile(r"이며|이고|하지만|그러나|및|\b(?:and|but)\b", re.I)
_NON_SKILL_OBLIGATION = re.compile(
    r"지원서|서류|이력서|회의|참석|제출|출근|면접|"
    r"\b(?:resume|application|meeting|attendance|interview)\b", re.I,
)
# Commas deliberately end cue scope: do not carry 'Java required' onto 'Python'.
_SPLIT = re.compile(r"[,;]|(?<=[.!?])\s+")

# This grammar recognizes names from the owned taxonomy, separators and one
# bounded suffix/prefix only. It cannot swallow arbitrary prose or unknown
# alternative members. Longer names win without creating a second taxonomy.
_NAME = "(?:" + "|".join(
    r"\s+".join(re.escape(part) for part in alias.split())
    for alias in sorted({a for aliases in SKILL_ALIASES.values() for a in aliases},
                        key=lambda value: (-len(value), value))
) + ")"
_SEPARATOR = r"(?:\s*,\s*|\s+(?:and|or|및|또는|혹은)\s+|\s*[와과/]\s*)"
_SHARED_LIST = re.compile(
    rf"(?:must[ -]+have\s+)?(?P<names>{_NAME}(?:{_SEPARATOR}{_NAME})+)"
    r"\s*(?:중\s*하나(?:\s*이상)?)?\s*"
    r"(?:(?:사용\s+)?경험(?:자|이|은)?|역량|experience|proficiency)?\s*"
    r"(?:필수(?:입니다)?|필요합니다|우대(?:합니다)?|required|mandatory|preferred|"
    r"nice[ -]+to[ -]+have|is\s+(?:a\s+)?plus|"
    r"(?:is\s+)?not\s+(?:required|necessary|mandatory|preferred|needed)|"
    r"필수(?:가|는)?\s*(?:아님|아닙니다)|요구하지\s*(?:않음|않습니다)|"
    r"없어도\s*지원\s*가능(?:합니다)?)?[.!]?",
    re.I,
)


def _shared_context(text: str, section: RequirementType | None, field: str):
    """Return (relation, class, rule) only for a complete bounded skill list."""
    body = text[_DECORATION.match(text).end():]
    match = _SHARED_LIST.fullmatch(body)
    if match is None or len(extract_skills(body)) < 2:
        return None
    names = match["names"]
    any_of = bool(_ALTERNATIVE.search(body))
    # Mixed boolean operators and unqualified slash lists remain ambiguous.
    # Check connectors between names, not substrings inside canonical names.
    connectors = re.sub(_NAME, "", names, flags=re.I)
    has_and = bool(re.search(r"and|및|와|과", connectors, re.I))
    if (any_of and has_and) or ("/" in connectors and not any_of):
        return "independent", "unspecified", "unsupported_relation"
    kind, rule = _classify(body, section, field, shared=True)
    if rule in {"negated", "ambiguous_context", "conflicting_cues"}:
        return "independent", "unspecified", rule
    if any_of:
        return "any_of", kind, rule
    # A new all-of group needs an explicit shared cue. Heading/field defaults
    # keep their existing independent classification contract.
    if _REQUIRED.search(body) or _PREFERRED.search(body):
        return "all_of", kind, rule
    return None


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _heading(line: str) -> tuple[RequirementType, int] | None:
    """Return section type and content offset for an exact heading/colon label."""
    prefix = _DECORATION.match(line).end()
    body = line[prefix:]
    # Accept punctuation inside a complete heading wrapper, without changing
    # the original string used for provenance or accepting decorated prose.
    wrapped = re.fullmatch(r"(?:\*\*(.+)\*\*|\[(.+)\]|【(.+)】)[:：]?", body)
    if wrapped:
        label = next(value for value in wrapped.groups() if value is not None)
        key = " ".join(label.rstrip(":： ").casefold().split())
        if key in _HEADINGS:
            return _HEADINGS[key], len(line)
    parts = re.split(r"([:：])", body, maxsplit=1)
    label, separator = (parts[0], parts[1]) if len(parts) > 1 else (body, "")
    key = label.strip()
    for left, right in (("[", "]"), ("【", "】"), ("**", "**")):
        if key.startswith(left) and key.endswith(right):
            key = key[len(left):-len(right)].strip()
            break
    key = " ".join(key.casefold().split())
    if key in _HEADINGS:
        return _HEADINGS[key], prefix + len(label) + len(separator)
    # An unknown decorated/colon heading is a boundary, never positive evidence.
    formatted = (body.strip().startswith(("[", "【", "**", "<"))
                 or line.lstrip().startswith("#") or "|" in line)
    if formatted or (separator and not extract_skills(label)):
        return "unspecified", 0 if extract_skills(label) else prefix + len(label) + len(separator)
    return None


def _classify(text: str, section: RequirementType | None, field: str, *, shared: bool = False) -> tuple[RequirementType, str]:
    if _NEGATED.search(text):
        return "unspecified", "negated"
    if _UNCERTAIN.search(text):
        return "unspecified", "ambiguous_context"
    required, preferred = bool(_REQUIRED.search(text)), bool(_PREFERRED.search(text))
    if required and preferred:
        return "unspecified", "conflicting_cues"
    if (required or section == "required") and _NON_SKILL_OBLIGATION.search(text):
        return "unspecified", "ambiguous_context"
    if not shared and (_ALTERNATIVE.search(text) or ((required or preferred) and _CONJUNCTION.search(text)
                                                   and len(extract_skills(text)) > 1)):
        return "unspecified", "ambiguous_context"
    if required:
        return "required", "explicit_required"
    if preferred:
        return "preferred", "explicit_preferred"
    if section is not None:
        return section, "section_heading"
    if field in PREFERRED_FIELDS:
        return "preferred", "preferred_field"
    if _DUTY.search(text) and not _EXPERIENCE.search(text):
        return "responsibility", "explicit_duty"
    return "unspecified", "mention_only"


def _field_evidence(text: str, field: str) -> Iterator[RequirementEvidence]:
    section = None
    heading = None
    heading_start = None
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        start, end = _trim_span(text, offset, offset + len(raw_line))
        offset += len(raw_line)
        if start == end:
            continue
        line = text[start:end]
        matched = _heading(line)
        if matched is not None:
            section, content_offset = matched
            heading, heading_start = line[:content_offset] if content_offset else line, start
            start += content_offset
        # A leading list marker belongs to the source slice; no text rewriting.
        shared = _shared_context(text[start:end], section, field)
        # Keep unresolved alternatives intact. Splitting a comma prefix could
        # otherwise manufacture an independent required/preferred member.
        unresolved = shared is None and bool(_ALTERNATIVE.search(text[start:end]))
        clause_start = start
        boundaries = [] if shared or unresolved else list(_SPLIT.finditer(text, start, end))
        for boundary in [*boundaries, None]:
            clause_end = boundary.start() if boundary else end
            left, right = _trim_span(text, clause_start, clause_end)
            clause_start = boundary.end() if boundary else end
            if left == right:
                continue
            evidence_text = text[left:right]
            relation = "independent"
            if shared:
                relation, kind, rule = shared
            else:
                kind, rule = _classify(evidence_text, section, field)
            yield {"source_field": field, "source_index": None, "evidence_text": evidence_text,
                   "evidence_start": left, "evidence_end": right,
                   "section_heading": heading, "section_start": heading_start,
                   "requirement_type": kind, "rule": rule, "relation": relation}


def _conditions(detail: DetailEvidence) -> list[SourceCondition]:
    result = []
    # Only complete, unambiguous categories enter the existing normalizer.
    # Complex years/alternatives stay raw; substring normalization is unsafe here.
    career_categories = {"신입", "경력", "무관", "경력무관", "경력 무관", "관계없음",
                         "경력 관계없음", "신입/경력", "경력/신입", "신입 / 경력", "경력 / 신입"}
    for field in CONDITION_FIELDS:
        raw = detail.get(field)
        normalized = None
        if field == "raw_career_condition" and raw and raw.strip() in career_categories:
            normalized = normalize_career(raw)
        status = "missing"
        if raw and raw.strip():
            status = "normalized" if normalized is not None else "not_interpreted"
        result.append({"source_field": field, "raw_text": raw, "status": status, "normalized_value": normalized})
    return result


def extract_requirements(detail: DetailEvidence | None) -> RequirementExtraction:
    """Recompute from source evidence, retaining all distinct source occurrences.

    Quality describes observable extraction coverage, never employer completeness.
    Classified skills can coexist with unspecified/unmapped evidence. Invalid
    inputs and unexpected errors propagate; they are not empty successful results.
    """
    result: RequirementExtraction = {
        "extractor_version": REQUIREMENT_EXTRACTOR_VERSION,
        "source": detail.get("source") if detail is not None else None,
        "posting_id": detail.get("posting_id") if detail is not None else None,
        "detail_fetched_at": detail.get("fetched_at") if detail is not None else None,
        "quality_status": "detail_not_fetched", "skills": [], "groups": [], "unclassified_evidence": [], "conditions": [],
    }
    if detail is None:
        return result
    evidence = []
    for field in TEXT_FIELDS:
        value = detail.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text or None")
        evidence.extend(_field_evidence(value or "", field))
    keywords = detail.get("keywords", [])
    if not isinstance(keywords, list) or any(not isinstance(word, str) for word in keywords):
        raise ValueError("keywords must be a list of strings")
    for index, keyword in enumerate(keywords):
        if keyword.strip():
            evidence.append({"source_field": "keywords", "source_index": index, "evidence_text": keyword,
                             "evidence_start": 0, "evidence_end": len(keyword), "section_heading": None,
                             "section_start": None, "requirement_type": "unspecified", "rule": "discovery_metadata",
                             "relation": "independent"})
    by_skill: dict[str, SkillRequirement] = {}
    for item in evidence:
        skills = extract_skills(item["evidence_text"])
        if item["relation"] in {"all_of", "any_of"}:
            result["groups"].append({"relation": item["relation"], "skills": skills,
                                     "requirement_type": item["requirement_type"], "evidence": item.copy()})
        if item["relation"] == "any_of":
            item = {**item, "requirement_type": "unspecified", "rule": "alternative_member"}
        for skill in skills:
            if skill not in by_skill:
                by_skill[skill] = {"skill": skill, "requirement_type": "unspecified", "evidence": []}
            requirement = by_skill[skill]
            requirement["evidence"].append(item.copy())
            if REQUIREMENT_PRECEDENCE[item["requirement_type"]] < REQUIREMENT_PRECEDENCE[requirement["requirement_type"]]:
                requirement["requirement_type"] = item["requirement_type"]
        if not skills and (item["requirement_type"] != "unspecified"
                           or item["rule"] in {"negated", "conflicting_cues", "ambiguous_context", "discovery_metadata"}
                           or item["source_field"] in {"certificate", "computer_skill"}):
            result["unclassified_evidence"].append(item)
    for field in CONDITION_FIELDS:
        if detail.get(field) is not None and not isinstance(detail[field], str):
            raise ValueError(f"{field} must be text or None")
    result["conditions"] = _conditions(detail)
    result["skills"] = [by_skill[skill] for skill in SKILL_ALIASES if skill in by_skill]
    if any(item["requirement_type"] != "unspecified" for item in [*result["skills"], *result["groups"]]):
        result["quality_status"] = "requirements_extracted"
    elif (result["skills"] or result["unclassified_evidence"]
          or any(c["status"] != "missing" for c in result["conditions"])):
        result["quality_status"] = "requirement_evidence_present_but_unclassified"
    else:
        result["quality_status"] = "detail_fetched_but_no_requirement_evidence"
    return result
