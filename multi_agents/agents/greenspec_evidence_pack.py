"""Optional client and adapter for GreenSpec's schema-validated EvidencePack v1."""
from __future__ import annotations

from typing import Any, Mapping

import requests


class GreenSpecEvidencePackError(ValueError):
    pass


def fetch_evidence_pack(
        *,
        base_url: str,
        retrieve_request: Mapping[str, Any],
        timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/v1/retrieve"
    try:
        response = requests.post(url, json=dict(retrieve_request), timeout=timeout_seconds)
    except requests.RequestException as exc:
        raise GreenSpecEvidencePackError(f"GreenSpec retrieval request failed: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise GreenSpecEvidencePackError("GreenSpec retrieval response is not JSON") from exc
    if response.status_code != 200:
        message = payload.get("error", {}).get("message", response.text)
        raise GreenSpecEvidencePackError(f"GreenSpec retrieval failed ({response.status_code}): {message}")
    pack = payload.get("evidence_pack")
    if not isinstance(pack, dict):
        raise GreenSpecEvidencePackError(
            "GreenSpec did not return evidence_pack.v1; require full hybrid retrieval rather than a degraded ranked list."
        )
    validate_evidence_pack(pack)
    return pack


def validate_evidence_pack(pack: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "evidence_pack_id", "retrieval_run_id",
        "index_manifest_id", "query", "items", "citations", "warnings",
        "needs_manual_review", "missing_facts", "degraded_modes",
    }
    missing = sorted(key for key in required if key not in pack)
    if pack.get("schema_version") != "evidence_pack.v1" or missing:
        raise GreenSpecEvidencePackError(
            f"unsupported or incomplete GreenSpec evidence pack; missing={missing}"
        )
    items = pack.get("items")
    citations = pack.get("citations")
    if not isinstance(items, list) or not isinstance(citations, list):
        raise GreenSpecEvidencePackError("GreenSpec evidence pack items and citations must be arrays")
    item_ids = {item.get("evidence_id") for item in items if isinstance(item, dict)}
    citation_ids = {item.get("evidence_id") for item in citations if isinstance(item, dict)}
    if not item_ids or not item_ids.issubset(citation_ids):
        raise GreenSpecEvidencePackError("every GreenSpec evidence item must have a citation")


def adapt_items(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Map external protocol fields into EvidenceVerifier's internal vocabulary."""
    citations = {
        str(citation["evidence_id"]): citation
        for citation in pack.get("citations", [])
        if isinstance(citation, dict) and citation.get("evidence_id")
    }
    converted = []
    for item in pack.get("items", []):
        if not isinstance(item, dict) or not item.get("evidence_id"):
            raise GreenSpecEvidencePackError("GreenSpec evidence item is missing evidence_id")
        evidence_id = str(item["evidence_id"])
        citation = citations.get(evidence_id)
        if not citation:
            raise GreenSpecEvidencePackError(f"GreenSpec citation missing for {evidence_id}")
        content_type = str(item.get("content_type") or "")
        verified = item.get("verification_status") == "verified"
        source_level = "T0" if verified and content_type.startswith("normative") else "T0_CANDIDATE"
        page_start = citation.get("pdf_page_start")
        page_end = citation.get("pdf_page_end")
        page = f"PDF p.{page_start}" if page_start == page_end else f"PDF pp.{page_start}-{page_end}"
        converted.append(
            {
                "evidence_id": evidence_id,
                "channel": "greenspec_rag",
                "source_level": source_level,
                "source_name": citation.get("standard_name"),
                "source_id": item.get("standard_id"),
                "clause_no": citation.get("clause_no"),
                "page": page,
                "url": None,
                "content": item.get("text") or "",
                "matched_topic": content_type,
                "confidence": 1.0 if verified else 0.5,
                "retrieval_score": item.get("rerank_score") or item.get("rrf_score") or 0.0,
                "metadata": {
                    "origin": "greenspec_evidence_pack.v1",
                    "greenspec_evidence_pack_id": pack.get("evidence_pack_id"),
                    "greenspec_retrieval_run_id": pack.get("retrieval_run_id"),
                    "index_manifest_id": pack.get("index_manifest_id"),
                    "clause_id": item.get("clause_id"),
                    "standard_version": citation.get("standard_version"),
                    "verification_status": item.get("verification_status"),
                    "pdf_page_start": page_start,
                    "pdf_page_end": page_end,
                    "printed_page_start": citation.get("printed_page_start"),
                    "printed_page_end": citation.get("printed_page_end"),
                    "table_id": citation.get("table_id"),
                    "formula_id": citation.get("formula_id"),
                    "parent_context": item.get("parent_context", []),
                },
            }
        )
    return converted
