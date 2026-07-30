import pytest

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


def test_extract_urls_removes_trailing_punctuation(
        agent,
):
    content = (
        "Government source: "
        "https://www.gov.cn/zhengce/index.html, "
        "public source: "
        "https://example.com/article.html."
    )

    urls = agent._extract_urls(content)

    assert urls == [
        "https://www.gov.cn/zhengce/index.html",
        "https://example.com/article.html",
    ]


def test_extract_urls_removes_duplicates(
        agent,
):
    content = (
        "First citation: https://www.gov.cn/policy.html. "
        "Repeated citation: https://www.gov.cn/policy.html."
    )

    urls = agent._extract_urls(content)

    assert urls == [
        "https://www.gov.cn/policy.html",
    ]


def test_collect_web_evidence_deduplicates_across_items(
        agent,
):
    url = "https://www.gov.cn/zhengce/example.html"

    research_data = [
        {
            "green building policy": (
                f"First research result: {url}"
            ),
        },
        {
            "energy policy": (
                f"Second research result: {url}"
            ),
        },
    ]

    evidence_items = (
        agent._collect_web_policy_evidence(
            research_data=research_data,
            sections=[],
            top_k=12,
        )
    )

    assert len(evidence_items) == 1
    assert evidence_items[0]["url"] == url
    assert evidence_items[0]["source_level"] == "T1"