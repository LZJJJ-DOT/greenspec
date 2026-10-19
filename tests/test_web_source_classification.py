import pytest
from multi_agents.evidence.web_evidence_ledger import build_records

from multi_agents.agents.evidence_supervisor import (
    EvidenceSupervisorAgent,
)


@pytest.fixture
def agent():
    return EvidenceSupervisorAgent()


@pytest.mark.parametrize(
    ("url", "expected_level"),
    [
        (
                "https://www.gov.cn/zhengce/index.html",
                "T1",
        ),
        (
                "https://subdomain.cnki.net/article/123",
                "T2",
        ),
        (
                "https://example.com/public-article",
                "T3",
        ),
    ],
)
def test_classify_web_source(
        agent,
        url,
        expected_level,
):
    source_level, reason, confidence = (
        agent._classify_web_source(url)
    )

    assert source_level == expected_level
    assert reason
    assert 0 <= confidence <= 1


@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "not-a-url",
    ],
)
def test_invalid_url_is_unclassified(
        agent,
        invalid_url,
):
    source_level, reason, confidence = (
        agent._classify_web_source(invalid_url)
    )

    assert source_level == "T1_T2_T3_UNCLASSIFIED"
    assert reason == "invalid_or_missing_hostname"
    assert confidence == 0.4


def test_collect_web_evidence_uses_verified_ledger_only(
        agent,
):
    url = "https://www.gov.cn/zhengce/example.html"
    ledger = build_records([{
        "url": url,
        "title": "official policy",
        "raw_content": "verified extracted content " * 12,
    }])

    evidence_items = (
        agent._collect_web_policy_evidence(
            ledger_records=ledger,
            top_k=12,
        )
    )

    assert len(evidence_items) == 1
    assert evidence_items[0]["url"] == url
    assert evidence_items[0]["source_level"] == "T1"
    assert evidence_items[0]["metadata"]["fetch_status"] == "success"
