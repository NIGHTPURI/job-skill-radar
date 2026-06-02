from __future__ import annotations


REQUIRED_FIELDS = [
    "source",
    "posting_id",
    "company",
    "title",
    "description",
    "region",
    "career",
    "education",
    "salary_type",
    "salary",
    "job_code",
    "registered_at",
    "closing_at",
    "url",
]


REGION_ALIASES = {
    "서울": ["서울", "서울특별시"],
    "경기": ["경기", "경기도", "성남", "판교", "수원", "용인", "고양"],
    "인천": ["인천", "인천광역시"],
    "부산": ["부산", "부산광역시"],
    "대전": ["대전", "대전광역시"],
    "대구": ["대구", "대구광역시"],
    "광주": ["광주", "광주광역시"],
    "울산": ["울산", "울산광역시"],
    "세종": ["세종", "세종특별자치시"],
    "강원": ["강원", "강원도", "강원특별자치도"],
    "충북": ["충북", "충청북도"],
    "충남": ["충남", "충청남도"],
    "전북": ["전북", "전라북도", "전북특별자치도"],
    "전남": ["전남", "전라남도"],
    "경북": ["경북", "경상북도"],
    "경남": ["경남", "경상남도", "창원"],
    "제주": ["제주", "제주특별자치도"],
}


def normalize_region(region: str | None) -> str:
    value = (region or "").strip()
    if not value:
        return "미상"
    for canonical, aliases in REGION_ALIASES.items():
        if any(alias in value for alias in aliases):
            return canonical
    return value.split()[0]


def normalize_career(career: str | None) -> str:
    value = (career or "").strip()
    if not value:
        return "미상"
    if "신입" in value:
        return "신입"
    if "경력" in value:
        return "경력"
    if "무관" in value or "관계없음" in value:
        return "무관"
    return "기타"


def clean_posting(posting: dict) -> dict:
    cleaned = {field: str(posting.get(field, "") or "").strip() for field in REQUIRED_FIELDS}
    cleaned["region"] = normalize_region(cleaned["region"])
    cleaned["career"] = normalize_career(cleaned["career"])
    return cleaned


def clean_postings(postings: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for posting in postings:
        cleaned = clean_posting(posting)
        posting_id = cleaned["posting_id"]
        if posting_id and posting_id not in seen:
            seen.add(posting_id)
            result.append(cleaned)
    return result
