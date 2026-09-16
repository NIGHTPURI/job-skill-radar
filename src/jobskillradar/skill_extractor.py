from __future__ import annotations

import re
from collections.abc import Iterable

from .skill_taxonomy import SKILL_ALIASES


# Permit complete Korean particles, never arbitrary Hangul suffixes. Compound
# terms (e.g. natural-language processing) belong in the taxonomy as aliases.
KOREAN_PARTICLES = (
    "으로", "에서", "에게", "까지", "부터", "와의", "과의", "에는", "에도",
    "은", "는", "이", "가", "을", "를", "과", "와", "의", "도", "로", "에", "만",
)
_PARTICLES = "|".join(KOREAN_PARTICLES)


def _alias_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = r"\s+".join(re.escape(part) for part in alias.split())
    # Unicode word boundaries block Latin, Hangul and identifier substrings.
    # '+' and '#' remain attached to names; ordinary dots delimit sentences.
    return re.compile(rf"(?<![\w+#]){escaped}(?=(?:{_PARTICLES})?(?![\w+#]))")


def _compile_aliases() -> tuple[dict[str, str], list[tuple[str, str, re.Pattern[str]]]]:
    canonical_by_alias: dict[str, str] = {}
    patterns = []
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            key = _alias_key(alias)
            if not key:
                raise ValueError(f"Empty skill alias: {canonical}")
            if key in canonical_by_alias:
                if canonical_by_alias[key] != canonical:
                    raise ValueError(f"Ambiguous skill alias: {alias}")
                continue
            canonical_by_alias[key] = canonical
            patterns.append((canonical, key, _alias_pattern(key)))
    return canonical_by_alias, patterns


_CANONICAL_BY_ALIAS, _COMPILED_ALIASES = _compile_aliases()


def _short_alias_context(text: str, start: int, end: int) -> bool:
    # One/two-letter aliases need more than token boundaries: reject compound
    # abbreviations (R&D, R & D) and quantities (10 ml). This is deliberately
    # conservative; semantic disambiguation is outside this lexical extractor.
    before, after = text[:start].rstrip(), text[end:].lstrip()
    return not (before.endswith("&") or after.startswith("&")
                or (before and before[-1].isdigit()))


def extract_skills(*texts: str | None) -> list[str]:
    """Return explicitly mentioned skills once, in stable taxonomy order.

    Longest overlapping evidence wins. A separate broader mention still counts.
    Process fields separately so aliases cannot be manufactured across fields.
    """
    found = set()
    for text in texts:
        haystack = (text or "").casefold()
        candidates = []
        for order, (skill, alias, pattern) in enumerate(_COMPILED_ALIASES):
            short = alias.isascii() and alias.isalpha() and len(alias) <= 2
            for match in pattern.finditer(haystack):
                start, end = match.span()
                if short and not _short_alias_context(haystack, start, end):
                    continue
                candidates.append((start, end, order, skill))
        occupied: list[tuple[int, int]] = []
        for start, end, _, skill in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0], item[2])):
            if any(start < right and end > left for left, right in occupied):
                continue
            occupied.append((start, end))
            found.add(skill)
    return [skill for skill in SKILL_ALIASES if skill in found]


def canonicalize_skills(skills: Iterable[str]) -> list[str]:
    """Normalize whole skill names, retaining unknown spelling and input order."""
    result = []
    seen = set()
    for raw_skill in skills:
        value = raw_skill.strip()
        if not value:
            continue
        canonical = _CANONICAL_BY_ALIAS.get(_alias_key(value), value)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
