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
    fields["green_space_ratio"] = fields.pop("green_space_ratio_percent") / 100
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


def test_form_maps_all_project_facts_and_updates_missing_documents():
    from multi_agents.demo_app import FORM_KEYS, _form, preview

    fields = preset_values("资料不完整")
    fields.update({
        "project_name": "现场办公楼", "district": "海淀区",
        "floor_area_m2": 38000, "above_ground_area_m2": 30000,
        "underground_area_m2": 8000, "building_height_m": 42,
        "above_ground_floors": 9, "underground_floors": 2,
        "plot_ratio": 2.1, "green_space_ratio_percent": 35,
        "provided_facts": fields["provided_facts"] + ["建筑能耗模拟"],
        "additional_notes": "待补充计算书",
    })
    args = tuple(fields[key] for key in FORM_KEYS)
    value = _form("资料不完整", *args)
    task = build_demo_task(value)

    assert (value.city, value.building_type, value.construction) == ("北京市", "普通办公楼", "新建")
    assert (value.precheck, value.gap_analysis, value.focus) == ("two_star", "three_star", "")
    assert task["project_profile"]["location"]["district"] == "海淀区"
    assert task["project_profile"]["building"]["above_ground_area_m2"] == 30000
    assert task["project_profile"]["building"]["green_space_ratio"] == 0.35
    assert task["greenspec_retrieve_request"]["project_profile"]["building"]["building_height_m"] == 42
    assert "绿地率35%" in task["project_doc"]
    assert task["greenspec_retrieve_request"]["query"] == task["query"]
    assert "建筑能耗模拟结果" not in task["project_profile"]["missing_fields"]
    assert "建筑能耗模拟报告" in task["project_profile"]["available_documents"]

    summary = preview("资料不完整", *args)
    assert "现场办公楼" in summary and "待补充计算书" in summary
    assert "海淀区" in summary and "绿地率 35%" in summary
    assert "2026-09-02" in summary and "不解析计算文件" in summary
    assert "本次问题" not in summary and "设计阶段" not in summary


def test_presets_fill_every_visible_field_and_unsupported_profile_can_preview():
    from multi_agents.demo_app import FORM_KEYS, preview, select_preset

    selected = select_preset("资料改善版")
    expected = preset_values("资料改善版")
    assert selected[:len(FORM_KEYS)] == tuple(expected[key] for key in FORM_KEYS)
    assert "建筑能耗模拟报告" in selected[-2]

    fields = dict(expected)
    fields.update({"province": "上海市", "city": "上海市", "building_type": "校园建筑"})
    summary = preview("资料改善版", *(fields[key] for key in FORM_KEYS))
    assert "上海市" in summary and "校园建筑" in summary
    assert "仅供填写与展示" in summary


def test_gradio_page_exposes_profile_inputs_without_research_question():
    from multi_agents.demo_app import create_app

    app = create_app()
    labels = {
        component.get("props", {}).get("label")
        for component in app.config["components"]
        if component.get("props", {}).get("label")
    }
    assert {
        "案例预设", "项目名称", "省／直辖市", "城市", "区／县", "气候区",
        "建筑类型", "总建筑面积（平方米）", "地上建筑面积（平方米）",
        "地下建筑面积（平方米）", "建筑高度（米）", "地上建筑层数",
        "地下建筑层数", "容积率", "绿地率（%）",
    } <= labels
    assert not any(
        term in label for label in labels
        for term in ("项目性质", "设计阶段", "研究重点", "研究问题", "预审目标", "差距分析目标")
    )
    run = next(
        dependency for dependency in app.config["dependencies"]
        if dependency.get("api_name") == "run_demo"
    )
    assert len(run["inputs"]) == 18  # Preset, sixteen project fields and previous-run state.


def test_demo_rejects_unsupported_scope_and_bad_date():
    with pytest.raises(DemoInputError, match="仅北京"):
        build_demo_task(make_input(city="上海"))
    with pytest.raises(DemoInputError, match="仅北京"):
        build_demo_task(make_input(building_type="校园建筑"))
    with pytest.raises(DemoInputError, match="YYYY-MM-DD"):
        build_demo_task(make_input(as_of_date="10/19/2026"))


def test_unsupported_profile_is_blocked_before_rag_call(monkeypatch):
    from multi_agents import demo_app

    fields = preset_values("资料改善版")
    fields.update({"province": "上海市", "city": "上海市", "building_type": "校园建筑"})
    monkeypatch.setattr(
        demo_app, "check_rag_health",
        lambda *_a: pytest.fail("unsupported profile reached RAG"),
    )
    result = demo_app.run_demo(
        "资料改善版", *(fields[key] for key in demo_app.FORM_KEYS), None,
    )
    assert "仅北京新建普通办公楼" in result[0]
    assert result[1:5] == ("", "", "", "")


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


def test_loopback_bypasses_proxy_without_dropping_existing_exclusions(monkeypatch):
    from multi_agents import demo_app

    monkeypatch.setenv("NO_PROXY", "example.local")
    if demo_app.os.name != "nt":
        monkeypatch.delenv("no_proxy", raising=False)

    demo_app._bypass_proxy_for_loopback()

    assert "example.local" in demo_app.os.environ["NO_PROXY"]
    for host in ("127.0.0.1", "localhost", "::1"):
        assert host in demo_app.os.environ["NO_PROXY"]
        assert host in demo_app.os.environ["no_proxy"]
