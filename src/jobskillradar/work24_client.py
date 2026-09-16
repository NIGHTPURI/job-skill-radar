from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .models import JobPosting


ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"


def _node_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_list_response(xml_text: str) -> list[JobPosting]:
    root = ET.fromstring(xml_text)
    postings: list[JobPosting] = []
    for wanted in root.findall(".//wanted"):
        industry = _node_text(wanted, "indTpNm")
        title = _node_text(wanted, "title")
        career = _node_text(wanted, "career")
        postings.append(
            {
                "source": "work24",
                "posting_id": _node_text(wanted, "wantedAuthNo"),
                "company": _node_text(wanted, "company"),
                "title": title,
                "description": " ".join(part for part in [title, industry, career] if part),
                "region": _node_text(wanted, "region"),
                "career": career,
                "education": " ~ ".join(
                    part
                    for part in [_node_text(wanted, "minEdubg"), _node_text(wanted, "maxEdubg")]
                    if part
                ),
                "salary_type": _node_text(wanted, "salTpNm"),
                "salary": _node_text(wanted, "sal"),
                "job_code": _node_text(wanted, "jobsCd"),
                "registered_at": _node_text(wanted, "regDt"),
                "closing_at": _node_text(wanted, "closeDt"),
                "url": _node_text(wanted, "wantedInfoUrl"),
            }
        )
    return postings


def fetch_work24_postings(
    auth_key: str,
    keyword: str,
    pages: int = 1,
    display: int = 100,
    region: str | None = None,
    occupation: str | None = None,
) -> list[JobPosting]:
    if not auth_key:
        raise ValueError("WORK24_AUTH_KEY가 필요합니다.")

    display = max(1, min(display, 100))
    pages = max(1, pages)
    postings: list[JobPosting] = []

    for page in range(1, pages + 1):
        params = {
            "authKey": auth_key,
            "callTp": "L",
            "returnType": "XML",
            "startPage": page,
            "display": display,
            "sortOrderBy": "DESC",
        }
        if keyword:
            params["keyword"] = keyword
        if region:
            params["region"] = region
        if occupation:
            params["occupation"] = occupation

        url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read().decode("utf-8")
        postings.extend(_parse_list_response(body))

    return postings
