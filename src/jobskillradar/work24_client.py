from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.client import HTTPException
from typing import cast

from .models import DetailEvidence, JobPosting, PostingDetail


ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"
DETAIL_ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210D01.do"
REQUEST_TIMEOUT = 30


class Work24Error(Exception):
    """A safe failure category; never include response text or authenticated URLs."""

    def __init__(self, kind: str):
        self.kind = kind if kind in {
            "api_error", "malformed_xml", "unexpected_structure", "missing_detail",
            "missing_identity", "identity_mismatch", "invalid_encoding",
            "transport_error", "unsupported_source",
        } else "request_error"
        super().__init__(f"Work24 request failed: {self.kind}")


def _read_response(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Work24Error("invalid_encoding") from None
    except (OSError, HTTPException):
        raise Work24Error("transport_error") from None


def _parse_xml(xml_text: str) -> ET.Element:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise Work24Error("malformed_xml") from None
    _raise_api_error(root)
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    return root


def _raise_api_error(root: ET.Element) -> None:
    # Defensive recognition, not an assertion of an official error-code schema.
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag == "error" or (tag in {"errorcode", "errorcd"} and (node.text or "").strip()):
            raise Work24Error("api_error")


# Only fields documented under wantedDtl/wantedInfo are mapped here.
DETAIL_XML_FIELDS = {
    "job_content": "jobCont",
    "employment_type": "empTpNm",
    "raw_career_condition": "enterTpNm",
    "education": "eduNm",
    "foreign_language": "forLang",
    "major": "major",
    "certificate": "certificate",
    "computer_skill": "compAbl",
    "preferred_conditions": "pfCond",
    "other_preferred_conditions": "etcPfCond",
    "selection_method": "selMthd",
    "receipt_method": "rcptMthd",
    "submit_documents": "submitDoc",
    "other_information": "etcHopeCont",
    "work_region": "workRegion",
    "work_hours": "workdayWorkhrCont",
    "welfare": "etcWelfare",
    "salary_condition": "salTpNm",
    "closing_at": "receiptCloseDt",
    "detail_url": "dtlRecrContUrl",
}
DETAIL_OTHER_TAGS = {
    "jobsNm", "wantedTitle", "relJobsNm", "collectPsncnt", "mltsvcExcHope", "nearLine",
    "fourIns", "retirepay", "disableCvntl", "attachFileInfo", "corpAttachList", "jobsCd",
    "minEdubgIcd", "maxEdubgIcd", "regionCd", "empTpCd", "enterTpCd", "salTpCd",
    "staAreaRegionCd", "lineCd", "staNmCd", "exitNoCd", "walkDistCd", "keywordList",
}


def _detail_text(node: ET.Element, tag: str) -> str | None:
    children = node.findall(tag)
    if not children:
        return None
    if len(children) != 1 or len(children[0]):
        raise Work24Error("unexpected_structure")
    # Strip outer padding only: preserve newlines, spacing, escaped text and CDATA.
    return (children[0].text or "").strip() or None


def parse_posting_detail(xml_text: str) -> DetailEvidence:
    """Parse documented nested XML without I/O, timestamps or interpretation."""
    root = _parse_xml(xml_text)
    if root.tag != "wantedDtl":
        if root.tag in {"wantedRoot", "root"} and not len(root) and not (root.text or "").strip():
            raise Work24Error("missing_detail")
        raise Work24Error("unexpected_structure")
    if (root.text or "").strip() or any((child.tail or "").strip() for child in root):
        raise Work24Error("unexpected_structure")
    infos = root.findall("wantedInfo")
    if not infos:
        raise Work24Error("missing_detail")
    if len(infos) != 1:
        raise Work24Error("unexpected_structure")
    posting_id = _detail_text(root, "wantedAuthNo")
    if not posting_id:
        raise Work24Error("missing_identity")
    info = infos[0]
    if (info.text or "").strip() or any((child.tail or "").strip() for child in info):
        raise Work24Error("unexpected_structure")
    # A truly empty wantedInfo is valid. A nonempty, wholly unknown layout is not.
    if len(info) and not any(child.tag in set(DETAIL_XML_FIELDS.values()) | DETAIL_OTHER_TAGS
                             for child in info):
        raise Work24Error("unexpected_structure")
    evidence = {name: _detail_text(info, tag) for name, tag in DETAIL_XML_FIELDS.items()}
    keywords = []
    for keyword_list in info.findall("keywordList"):
        if (keyword_list.text or "").strip() or any(
            child.tag != "srchKeywordNm" or len(child) or (child.tail or "").strip()
            for child in keyword_list
        ):
            raise Work24Error("unexpected_structure")
        for child in keyword_list:
            value = (child.text or "").strip()
            if value:
                keywords.append(value)
    return cast(DetailEvidence, {
        "source": "work24", "posting_id": posting_id, **evidence, "keywords": keywords,
    })


def fetch_posting_detail(auth_key: str, wanted_auth_no: str) -> PostingDetail:
    """Fetch once, validate identity, then attach successful observation time."""
    if not auth_key or not auth_key.strip():
        raise ValueError("WORK24_AUTH_KEY is required")
    if not wanted_auth_no or not wanted_auth_no.strip():
        raise ValueError("wanted_auth_no is required")
    params = {
        "authKey": auth_key, "wantedAuthNo": wanted_auth_no,
        "callTp": "D", "returnType": "XML", "infoSvc": "VALIDATION",
    }
    url = f"{DETAIL_ENDPOINT}?{urllib.parse.urlencode(params)}"
    evidence = parse_posting_detail(_read_response(url))
    if evidence["posting_id"] != wanted_auth_no:
        raise Work24Error("identity_mismatch")
    return {**evidence, "fetched_at": datetime.now(timezone.utc).isoformat()}


def _node_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_list_response(xml_text: str) -> list[JobPosting]:
    root = _parse_xml(xml_text)
    if root.tag not in {"wantedRoot", "root"} or (root.text or "").strip():
        raise Work24Error("unexpected_structure")
    if any(child.tag not in {"wanted", "total", "startPage", "display"}
           or (child.tag != "wanted" and len(child))
           or (child.tail or "").strip() for child in root):
        raise Work24Error("unexpected_structure")
    postings: list[JobPosting] = []
    for wanted in root.findall("wanted"):
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
    if not auth_key or not auth_key.strip():
        raise ValueError("WORK24_AUTH_KEY is required")

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
        postings.extend(_parse_list_response(_read_response(url)))

    return postings
