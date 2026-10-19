from multi_agents.agents.evidence_verifier import (
    EvidenceVerifier,
)


def build_claim(evidence_ids):
    return {
        "claim_id": "CLAIM-001",
        "claim": "项目可以开展绿色建筑二星级预审。",
        "claim_use": "precheck_conclusion",
        "required_source_levels": [
            "T0",
        ],
        "supporting_evidence_ids": evidence_ids,
        "evidence_spans": [
            {
                "evidence_id": evidence_id,
                "quote": "绿色建筑等级",
            }
            for evidence_id in evidence_ids
        ],
    }


def build_evidence(
        evidence_id="GBT50378-2019-004",
        source_level="T0",
        verification_status="verified",
):
    return {
        "evidence_id": evidence_id,
        "channel": "local_clause",
        "source_level": source_level,
        "source_name": "绿色建筑评价标准",
        "source_id": "GBT50378-2019",
        "clause_no": "3.2.6-3.2.8",
        "page": "14",
        "url": None,
        "content": "绿色建筑等级划分和评分要求。",
        "metadata": {
            "clause_id": evidence_id,
            "standard_version": "2019",
            "verification_status": verification_status,
        },
    }


def verify_one(claim, evidence_items):
    evidence_pack = {
        "claims": [claim],
        "evidence_items": evidence_items,
    }

    verification = EvidenceVerifier().verify(
        evidence_pack
    )

    assert len(verification["items"]) == 1

    return verification, verification["items"][0]


def test_no_supporting_evidence_is_unsupported():
    claim = build_claim([])

    verification, item = verify_one(
        claim=claim,
        evidence_items=[],
    )

    assert item["status"] == "unsupported"
    assert item["recommended_action"] == "research_again"
    assert item["source_level_check"] == "fail"
    assert "ISSUE_NO_SUPPORTING_EVIDENCE" in item["issues"]
    assert verification["decision"] == "research_again"


def test_missing_evidence_id_is_unsupported():
    claim = build_claim([
        "MISSING-EVIDENCE-001",
    ])

    verification, item = verify_one(
        claim=claim,
        evidence_items=[],
    )

    assert item["status"] == "unsupported"
    assert item["recommended_action"] == "research_again"
    assert item["source_level_check"] == "fail"
    assert any(
        issue.startswith(
            "ISSUE_EVIDENCE_ID_NOT_FOUND"
        )
        for issue in item["issues"]
    )
    assert verification["decision"] == "research_again"


def test_t0_candidate_requires_manual_review():
    evidence = build_evidence(
        source_level="T0_CANDIDATE",
        verification_status="candidate",
    )

    claim = build_claim([
        evidence["evidence_id"],
    ])

    verification, item = verify_one(
        claim=claim,
        evidence_items=[evidence],
    )

    assert item["status"] == "needs_manual_review"
    assert item["recommended_action"] == "revise"
    assert item["source_level_check"] == "needs_manual_review"
    assert verification["decision"] == "revise"


def test_complete_verified_t0_is_supported():
    evidence = build_evidence(
        source_level="T0",
        verification_status="verified",
    )

    claim = build_claim([
        evidence["evidence_id"],
    ])

    verification, item = verify_one(
        claim=claim,
        evidence_items=[evidence],
    )

    assert item["status"] == "supported"
    assert item["recommended_action"] == "accept"
    assert item["source_level_check"] == "pass"
    assert item["citation_check"] == {
        "source_present": True,
        "clause_no_present": True,
        "page_present": True,
        "version_present": True,
    }
    assert item["issues"] == []
    assert verification["decision"] == "accept"


def test_unresolvable_evidence_quote_requires_revision():
    evidence = build_evidence()
    claim = build_claim([evidence["evidence_id"]])
    claim["evidence_spans"][0]["quote"] = "不存在的原文"

    verification, item = verify_one(
        claim=claim,
        evidence_items=[evidence],
    )

    assert item["status"] == "partially_supported"
    assert item["recommended_action"] == "revise"
    assert "ISSUE_EVIDENCE_QUOTE_NOT_FOUND: GBT50378-2019-004" in item["issues"]
    assert verification["decision"] == "revise"
