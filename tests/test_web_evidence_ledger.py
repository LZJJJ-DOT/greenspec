import json

import pytest

from multi_agents.agents.publisher import PublisherAgent
from multi_agents.evidence.web_evidence_ledger import (
    build_records,
    is_verified_record,
    merge_records,
)


def test_ledger_accepts_only_successful_extracted_pages():
    records = build_records([
        {"url": "https://example.com/ok", "raw_content": "x" * 100},
        {"url": "https://example.com/empty", "raw_content": "too short"},
        {"url": "", "raw_content": "x" * 100},
    ])
    assert len(records) == 1
    assert is_verified_record(records[0])


def test_ledger_rejects_tampered_content_and_deduplicates_retries():
    record = build_records([
        {"url": "https://example.com/a", "raw_content": "a" * 120},
    ])[0]
    tampered = dict(record)
    tampered["extracted_content"] = "changed" * 30
    assert not is_verified_record(tampered)
    assert merge_records([record], [record], [tampered]) == [record]


def test_ledger_keeps_distinct_versions_of_the_same_url_separate():
    records = build_records([
        {"url": "https://example.com/a", "raw_content": "a" * 120},
        {"url": "https://example.com/a", "raw_content": "b" * 120},
    ])

    assert len(records) == 2
    assert records[0]["record_id"] != records[1]["record_id"]


@pytest.mark.asyncio
async def test_publisher_writes_independent_ledger_artifact(tmp_path):
    record = build_records([
        {"url": "https://example.com/a", "raw_content": "a" * 120},
    ])[0]
    await PublisherAgent(str(tmp_path)).write_web_evidence_ledger(
        {"web_evidence_ledger": [record]}
    )

    artifact = json.loads(
        (tmp_path / "web_evidence_ledger.json").read_text(encoding="utf-8")
    )
    assert artifact["records"] == [record]
