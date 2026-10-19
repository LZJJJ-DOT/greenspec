"""Critical paths for the interactive GreenSpec RAG demo."""

import asyncio
from copy import deepcopy

import pytest

from multi_agents.demo_config import (
    DemoInput, DemoInputError, build_demo_task, check_rag_health, preset_values,
)
from multi_agents.agents.applicability_judge import ApplicabilityJudge
from multi_agents.agents.evidence_supervisor import EvidenceSupervisorAgent
from multi_agents.agents.greenspec_evidence_pack import (
    GreenSpecEvidencePackError, fetch_evidence_pack,
)


def make_input(preset="资料不完整", **overrides):
    fields = preset_values(preset)
    fields.update(overrides)
    return DemoInput(preset=preset, **fields)


def test_presets_and_edited_fact_share_one_source_of_truth():
    incomplete = build_demo_task(make_input())
    improved = build_demo_task(make_input("资料改善版"))
    assert "建筑能耗模拟结果" in incomplete["project_profile"]["missing_fields"]
    assert "建筑能耗模拟结果" not in improved["project_profile"]["missing_fields"]

    selected = list(preset_values("资料不完整")["provided_facts"]) + ["建筑能耗模拟"]
    task = build_demo_task(make_input(provided_facts=selected, focus="请重点分析建筑能耗模拟证据。"))
    request = task["greenspec_retrieve_request"]
    assert task["query"] == request["query"] == "请重点分析建筑能耗模拟证据。"
    assert task["project_profile"]["known_parameters"]["has_energy_simulation_result"] is True
    assert request["project_profile"]["known_parameters"]["has_energy_simulation_result"] is True
    assert "建筑能耗模拟结果" not in task["project_profile"]["missing_fields"]
    assert "建筑能耗模拟报告" in task["project_doc"]
    assert "建筑能耗模拟报告" in task["project_profile"]["available_documents"]
    assert request["project_profile"]["location"]["region"] == "北京"
    assert request["allow_degraded"] is False
    assert "local_clause_path" not in task


def test_demo_rejects_unsupported_scope_and_bad_date():
    with pytest.raises(DemoInputError, match="仅验证北京"):
        build_demo_task(make_input(city="上海"))
    with pytest.raises(DemoInputError, match="YYYY-MM-DD"):
        build_demo_task(make_input(as_of_date="10/19/2026"))


def test_rag_health_must_be_ready(monkeypatch):
    class Response:
        status_code = 503

        def json(self):
            return {"ready": False, "dependencies": {"qdrant": {"status": "unavailable"}}}

    monkeypatch.setattr("multi_agents.demo_config.requests.get", lambda *_a, **_kw: Response())
    with pytest.raises(DemoInputError, match="qdrant"):
        check_rag_health("http://127.0.0.1:8787")


def test_rag_client_rejects_degraded_pack(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"evidence_pack": {
                "schema_version": "evidence_pack.v1", "evidence_pack_id": "pack-1",
                "retrieval_run_id": "run-1", "index_manifest_id": "idx-1",
                "query": "current question", "items": [{"evidence_id": "E-1"}],
                "citations": [{"evidence_id": "E-1"}], "warnings": [],
                "needs_manual_review": True, "missing_facts": [],
                "degraded_modes": ["bm25_only"],
            }}

    monkeypatch.setattr("multi_agents.agents.greenspec_evidence_pack.requests.post", lambda *_a, **_kw: Response())
    with pytest.raises(GreenSpecEvidencePackError, match="degraded"):
        fetch_evidence_pack(base_url="http://127.0.0.1:8787", retrieve_request={"query": "current question"})


def test_applicability_judge_reads_rag_channel():
    profile = build_demo_task(make_input())["project_profile"]
    item = {
        "evidence_id": "E-1", "channel": "greenspec_rag", "source_level": "T0_CANDIDATE",
        "source_name": "测试规范", "source_id": "GB_TEST", "clause_no": "1.0.1",
        "page": "PDF p.1", "content": "测试条文", "confidence": 0.5,
        "metadata": {"requires_manual_review": True},
    }
    results = ApplicabilityJudge().judge(profile, [item])
    assert len(results) == 1
    assert results[0]["manual_review_required"] is True


def test_multi_agent_entry_uses_current_query_without_mutating_input(monkeypatch):
    from multi_agents import main as entry

    original = build_demo_task(make_input())
    unchanged = deepcopy(original)
    captured = {}

    class FakeChiefEditor:
        def __init__(self, task, *_args, **_kwargs):
            captured["task"] = task

        async def run_research_task(self):
            return {"report": "ok"}

    monkeypatch.setattr(entry, "ChiefEditorAgent", FakeChiefEditor)
    result = asyncio.run(entry.run_research_task("现场输入的新问题", task_override=original))
    assert result["report"] == "ok"
    assert captured["task"]["query"] == "现场输入的新问题"
    assert captured["task"]["greenspec_retrieve_request"]["query"] == "现场输入的新问题"
    assert original == unchanged


def test_rag_evidence_summary_uses_current_channel_name():
    supervisor = EvidenceSupervisorAgent()
    items = [{"evidence_id": "RAG-1", "channel": "greenspec_rag", "content": "规范条文"}]
    claims = supervisor._build_claims(items, [])
    summary = supervisor._build_evidence_summary({
        "evidence_items": items, "gaps": [], "claims": claims,
    })

    assert "GreenSpec RAG 规范证据" in claims[1]["claim"]
    assert "- greenspec_rag: 1 items" in summary
    assert "- local_clause: 0 items" not in summary


def test_comparison_shows_actual_gap_and_review_changes():
    from multi_agents.demo_app import _comparison

    previous = {
        "gaps": ["采光模拟结果", "绿色建材比例"],
        "manual_review_count": 8,
        "retrieval_run_id": "run-before",
    }
    current = {
        "gaps": ["绿色建材比例"],
        "manual_review_count": 7,
        "retrieval_run_id": "run-after",
    }

    rendered = _comparison(previous, current)
    assert "资料缺口：2 → 1" in rendered
    assert "待人工复核条文：8 → 7" in rendered
    assert "本次不再出现：采光模拟结果" in rendered
    assert "run-before" in rendered and "run-after" in rendered


def test_launch_reuses_running_demo(monkeypatch, capsys):
    from multi_agents import demo_app

    class Response:
        status_code = 200

        def json(self):
            return {"title": "GreenSpec 绿建预审演示"}

    opened = []
    monkeypatch.setattr(demo_app.requests, "get", lambda *_a, **_k: Response())
    monkeypatch.setattr(demo_app.webbrowser, "open", opened.append)
    monkeypatch.setattr(demo_app, "create_app", lambda: pytest.fail("duplicate server started"))

    demo_app.launch_demo()

    assert opened == ["http://127.0.0.1:7860/"]
    assert "已在运行" in capsys.readouterr().out


def test_launch_respects_port_override(monkeypatch):
    from multi_agents import demo_app

    class FakeApp:
        def queue(self, **_kwargs):
            return self

        def launch(self, **kwargs):
            observed.update(kwargs)

    observed = {}
    monkeypatch.setenv("GRADIO_SERVER_PORT", "7861")
    monkeypatch.setattr(demo_app.requests, "get", lambda *_a, **_k: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(demo_app, "create_app", FakeApp)

    demo_app.launch_demo()

    assert observed["server_port"] == 7861
