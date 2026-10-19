import json

import pytest

from multi_agents.agents.claim_contract import claim_set, validate_claim_set
from multi_agents.agents.greenspec_evidence_pack import (
    GreenSpecEvidencePackError,
    adapt_items,
    validate_evidence_pack,
)
from multi_agents.evaluation.claim_output_evaluator import evaluate_claim_output


def valid_claim():
    return {
        "claim_id": "CLAIM-001",
        "claim": "条文要求应被核验。",
        "claim_use": "precheck_conclusion",
        "required_source_levels": ["T0"],
        "supporting_evidence_ids": ["E-001"],
        "evidence_spans": [{"evidence_id": "E-001", "quote": "条文要求"}],
    }


def valid_upstream_pack():
    return {
        "schema_version": "evidence_pack.v1",
        "evidence_pack_id": "pack-001",
        "retrieval_run_id": "retrieve-001",
        "index_manifest_id": "index-001",
        "query": "测试",
        "items": [{
            "evidence_id": "E-001", "clause_id": "E-001",
            "content_type": "normative_clause", "text": "条文要求应被核验。",
            "standard_id": "GB_TEST", "verification_status": "verified",
            "rerank_score": 0.9, "rrf_score": 0.1,
        }],
        "citations": [{
            "evidence_id": "E-001", "standard_name": "测试规范",
            "standard_version": "2026", "clause_no": "1.0.1",
            "pdf_page_start": 1, "pdf_page_end": 1,
            "printed_page_start": 1, "printed_page_end": 1,
            "table_id": None, "formula_id": None,
        }],
        "warnings": [], "needs_manual_review": False,
        "missing_facts": [], "degraded_modes": [],
    }


def test_claim_set_rejects_unknown_fields():
    payload = claim_set(evidence_pack_id="pack", claims=[valid_claim()])
    payload["claims"][0]["invented"] = True
    with pytest.raises(ValueError, match="Claim set contract violation"):
        validate_claim_set(payload)


def test_adapter_preserves_greenspec_provenance():
    pack = valid_upstream_pack()
    validate_evidence_pack(pack)
    item = adapt_items(pack)[0]
    assert item["channel"] == "greenspec_rag"
    assert item["source_level"] == "T0"
    assert item["metadata"]["greenspec_evidence_pack_id"] == "pack-001"


def test_adapter_rejects_missing_citation():
    pack = valid_upstream_pack()
    pack["citations"] = []
    with pytest.raises(GreenSpecEvidencePackError, match="citation"):
        validate_evidence_pack(pack)


def test_real_claim_artifact_evaluator_builds_a_review_queue(tmp_path):
    pack = {
        "evidence_items": [{
            "evidence_id": "E-001", "channel": "greenspec_rag",
            "source_level": "T0", "source_name": "测试规范",
            "source_id": "GB_TEST", "clause_no": "1.0.1", "page": "PDF p.1",
            "content": "条文要求应被核验。", "url": None,
            "metadata": {"standard_version": "2026", "verification_status": "verified"},
        }],
        "claim_set": claim_set(evidence_pack_id="pack", claims=[valid_claim()]),
    }
    (tmp_path / "evidence_pack.json").write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    result, queue = evaluate_claim_output(tmp_path)
    assert result["metrics"]["supported_claim_rate"] == 1.0
    assert queue == []
