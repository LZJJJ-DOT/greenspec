import json
from unittest.mock import AsyncMock

import pytest

from multi_agents.agents.editor import EditorAgent
from multi_agents.agents.evidence_supervisor import (
    EvidenceSupervisorAgent,
)
from multi_agents.agents.researcher import ResearchAgent
from multi_agents.observability import TraceRecorder


def test_project_document_source_id_is_dynamic():
    items = (
        EvidenceSupervisorAgent()
        ._collect_project_doc_evidence(
            project_doc="project facts",
            project_profile={
                "project_name": "demo project"
            },
            source_id="improved.md",
        )
    )

    assert items[0]["source_id"] == "improved.md"


@pytest.mark.asyncio
async def test_subtopic_research_propagates_error(
        monkeypatch,
):
    agent = ResearchAgent()
    monkeypatch.setattr(
        agent,
        "research",
        AsyncMock(
            side_effect=RuntimeError("research failed")
        ),
    )

    with pytest.raises(
            RuntimeError,
            match="research failed",
    ):
        await agent.run_subtopic_research(
            parent_query="parent",
            subtopic="topic",
        )


def test_editor_deduplicates_research_again_data():
    editor = EditorAgent()
    duplicate = {"topic": "same content"}

    result = editor._deduplicate_research_data([
        duplicate,
        duplicate,
        {"Evidence Pack Summary": "old"},
    ])

    assert result == [duplicate]


def test_editor_limits_section_revisions():
    editor = EditorAgent()
    state = {
        "task": {
            "max_section_revision_count": 2,
        },
        "review": "revise again",
        "revision_count": 1,
    }

    assert editor._route_after_review(state) == "revise"

    state["revision_count"] = 2
    assert editor._route_after_review(state) == "accept"

    state["review"] = None
    assert editor._route_after_review(state) == "accept"


@pytest.mark.asyncio
async def test_trace_redacts_payload_and_records_components(
        tmp_path,
):
    recorder = TraceRecorder(
        output_dir=str(tmp_path),
        run_id="test-run",
    )

    wrapped = recorder.wrap(
        node_name="test_node",
        agent_name="TestAgent.run",
        handler=lambda state: {
            "content": "private output"
        },
    )
    await wrapped({
        "research_data": ["private input"],
    })

    supervisor = EvidenceSupervisorAgent(
        trace_recorder=recorder,
    )
    for node_name in (
        "applicability_judge",
        "risk_gap_analyst",
        "evidence_verifier",
    ):
        await supervisor._run_component(
            node_name=node_name,
            agent_name=node_name,
            handler=lambda value: value,
            payload={"value": 1},
        )

    trace = json.loads(
        (tmp_path / "trace.json").read_text(
            encoding="utf-8",
        )
    )
    serialized = json.dumps(
        trace,
        ensure_ascii=False,
    )
    node_names = {
        event["node_name"]
        for event in trace["events"]
    }

    assert "private input" not in serialized
    assert "private output" not in serialized
    assert {
        "applicability_judge",
        "risk_gap_analyst",
        "evidence_verifier",
    }.issubset(node_names)
    assert (
        trace["events"][0]["input"]
        ["research_data"]["redacted"]
        is True
    )
