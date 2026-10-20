"""Local Gradio interview demo for the GreenSpec RAG multi-agent workflow."""

from __future__ import annotations

import asyncio
import os
import sys
import webbrowser
from pathlib import Path

import gradio as gr
import requests

from multi_agents.demo_config import (
    DEFAULT_AS_OF_DATE, DemoInput, DemoInputError, FACT_FIELDS, PRESET_PATHS,
    build_demo_task, check_rag_health, preset_values,
)


FORM_KEYS = ("project_name", "floor_area_m2", "provided_facts", "additional_notes")


def _form(preset, project_name, floor_area_m2, provided_facts, additional_notes) -> DemoInput:
    fixed = preset_values(preset)
    return DemoInput(
        preset=preset, project_name=project_name, city=fixed["city"],
        building_type=fixed["building_type"], construction=fixed["construction"],
        design_phase=fixed["design_phase"], floor_area_m2=floor_area_m2,
        precheck=fixed["precheck"], gap_analysis=fixed["gap_analysis"],
        provided_facts=list(provided_facts or []),
        additional_notes=additional_notes or "", focus="",
        as_of_date=DEFAULT_AS_OF_DATE,
    )


def preview(*values) -> str:
    try:
        value = _form(*values)
        task = build_demo_task(value)
    except DemoInputError as exc:
        return f"⚠️ {exc}"
    profile = task["project_profile"]
    documents = "、".join(profile["available_documents"])
    missing = "、".join(profile["missing_fields"]) or "暂无已标记的缺失资料"
    notes = value.additional_notes.strip()
    notes_line = f"**补充说明（待核实）：** {notes}\n\n" if notes else ""
    return (
        "### 本次项目资料\n\n"
        f"**项目：** {profile['project_name']}　"
        f"**总建筑面积：** {profile['building']['gross_floor_area_m2']:g} 平方米\n\n"
        f"**已标记已有资料：** {documents}\n\n"
        f"**未提供或待确认：** {missing}\n\n"
        f"{notes_line}"
        f"**规范检索基准日期：** {task['greenspec_retrieve_request']['filters']['as_of_date']}"
        "（历史案例复现日期，不代表当前规范状态）\n\n"
        "勾选仅表示资料状态，不代表计算结果已核验或星级达标；本演示不解析计算文件。"
    )


def select_preset(name: str):
    values = preset_values(name)
    form_values = tuple(values[key] for key in FORM_KEYS)
    return (*form_values, preview(name, *form_values), f"当前使用：{name}预设。")


def preview_edited(*values):
    return preview(*values), "✏️ 已编辑预设字段；以下摘要已按当前输入重新生成。"


def health_status() -> str:
    try:
        payload = check_rag_health()
    except DemoInputError as exc:
        return f"🔴 {exc}"
    return f"🟢 GreenSpec RAG 已就绪；索引：`{payload.get('active_index_manifest_id') or '未知'}`"


def _evidence_markdown(pack: dict) -> str:
    upstream = pack.get("upstream_evidence_pack") or {}
    applicable = {
        item.get("evidence_id"): item
        for item in pack.get("applicability_results", []) or []
    }
    lines = [
        "### GreenSpec RAG 规范证据",
        f"EvidencePack：`{upstream.get('evidence_pack_id', '未知')}`  ",
        f"检索运行：`{upstream.get('retrieval_run_id', '未知')}`  ",
        f"索引：`{upstream.get('index_manifest_id', '未知')}`",
    ]
    for index, item in enumerate(
        (entry for entry in pack.get("evidence_items", []) if entry.get("channel") == "greenspec_rag"),
        start=1,
    ):
        meta = item.get("metadata") or {}
        judgment = applicable.get(item.get("evidence_id"), {})
        source = item.get("source_name") or item.get("source_id") or "未知标准"
        citation = " ".join(str(part) for part in (
            source, meta.get("standard_version"), item.get("clause_no"), item.get("page"),
        ) if part)
        content = str(item.get("content") or "").replace("\n", " ")[:260]
        lines += [
            f"**{index}. {citation}**  ",
            f"证据 ID：`{item.get('evidence_id')}`；来源状态：`{meta.get('verification_status') or '未知'}`；"
            f"适用性：`{judgment.get('applicable_status') or '待判断'}`  ",
            f"> {content}",
        ]
    if len(lines) == 4:
        lines.append("本次未返回 GreenSpec RAG 条文证据。")
    return "\n\n".join(lines)


def _gaps_markdown(pack: dict) -> str:
    gaps = pack.get("gaps") or []
    applicable = pack.get("applicability_results") or []
    needs_review = [item for item in applicable if item.get("manual_review_required")]
    lines = ["### 资料缺口与人工复核", f"资料缺口：**{len(gaps)}** 项；待人工复核条文：**{len(needs_review)}** 项。"]
    lines += [f"- {gap.get('description', '')}" for gap in gaps]
    if not gaps:
        lines.append("- 本次未识别出表单所列的缺失资料；仍须核验实际项目文件。")
    return "\n\n".join(lines)


def _comparison(previous: dict | None, current: dict) -> str:
    if not previous:
        return "### 与上次运行对比\n\n首次运行。再次运行后可查看实际输出差异。"
    before, after = set(previous["gaps"]), set(current["gaps"])
    lines = ["### 与上次运行对比", f"资料缺口：{len(before)} → {len(after)} 项。"]
    if "manual_review_count" in previous:
        lines.append(
            f"待人工复核条文：{previous['manual_review_count']} → "
            f"{current['manual_review_count']} 项。"
        )
    if previous.get("retrieval_run_id") and current.get("retrieval_run_id"):
        lines.append(
            f"检索运行 ID：`{previous['retrieval_run_id']}` → "
            f"`{current['retrieval_run_id']}`。"
        )
    if before - after:
        lines.append("本次不再出现：" + "、".join(sorted(before - after)))
    if after - before:
        lines.append("本次新增：" + "、".join(sorted(after - before)))
    if not (before ^ after):
        lines.append("资料缺口未变化；可继续比较规范证据和报告内容。")
    return "\n\n".join(lines)


def run_demo(preset, project_name, floor_area_m2, provided_facts,
             additional_notes, previous,
             progress=gr.Progress()):
    try:
        task = build_demo_task(_form(
            preset, project_name, floor_area_m2, provided_facts, additional_notes,
        ))
        progress(0.05, desc="检查 GreenSpec RAG 服务")
        health = check_rag_health(task["greenspec_rag_url"])
        progress(0.15, desc="研究、规范检索、证据核验与报告生成中")
        from multi_agents.main import run_research_task
        result = asyncio.run(run_research_task(task["query"], task_override=task))
        pack = result.get("evidence_pack") or {}
        upstream = pack.get("upstream_evidence_pack") or {}
        if not upstream.get("evidence_pack_id"):
            raise DemoInputError("本次研究未生成 GreenSpec RAG EvidencePack")
        run_dir = Path(result["run_dir"])
        report_files = [path for path in run_dir.glob("*.md") if path.name != "eval_report.md"]
        report_file = str(max(report_files, key=lambda path: path.stat().st_mtime)) if report_files else None
        evidence_file_path = run_dir / "evidence_pack.json"
        evidence_file = str(evidence_file_path) if evidence_file_path.is_file() else None
        gaps = [str(gap.get("description") or "") for gap in pack.get("gaps", [])]
        current = {
            "gaps": gaps,
            "evidence_pack_id": upstream["evidence_pack_id"],
            "retrieval_run_id": upstream.get("retrieval_run_id"),
            "manual_review_count": sum(
                bool(item.get("manual_review_required"))
                for item in pack.get("applicability_results", [])
            ),
        }
        progress(1, desc="分析完成")
        status = (
            f"🟢 本次分析完成。索引：`{health.get('active_index_manifest_id')}`；"
            f"检索基准日期：`{DEFAULT_AS_OF_DATE}`；运行目录：`{run_dir.name}`。"
        )
        return (status, _evidence_markdown(pack), _gaps_markdown(pack),
                result.get("report") or "", _comparison(previous, current),
                report_file, evidence_file, current)
    except Exception as exc:
        # Clear every result panel so a failed run cannot look like a live result.
        message = str(exc) if isinstance(exc, DemoInputError) else f"运行失败：{exc}"
        return (f"🔴 {message}", "", "", "", "", None, None, previous)


def create_app() -> gr.Blocks:
    first_preset = "资料不完整"
    initial = preset_values(first_preset)
    with gr.Blocks(title="GreenSpec 绿建预审演示") as app:
        gr.Markdown(
            "# GreenSpec｜北京新建办公楼二星升三星预审\n"
            "北京新建普通办公楼从二星级目标提升到三星级目标的**证据与资料缺口预审助手**。"
            "规范证据来自 GreenSpec RAG，报告由 GPT Researcher 多智能体流程生成；"
            "结论须由专业人员复核。"
        )
        with gr.Row():
            preset = gr.Dropdown(list(PRESET_PATHS), value=first_preset, label="案例预设")
            health_button = gr.Button("检查 RAG 服务")
        health = gr.Markdown("点击“检查 RAG 服务”查看在线状态。")
        gr.Markdown("选择案例，调整项目资料状态，再点击「开始分析」。")
        with gr.Row():
            project_name = gr.Textbox(value=initial["project_name"], label="项目名称")
            floor_area = gr.Number(value=initial["floor_area_m2"], label="总建筑面积（平方米）")
        facts = gr.CheckboxGroup(
            list(FACT_FIELDS), value=initial["provided_facts"],
            label="已有资料（仅声明有无；未勾选＝未提供/待确认）",
        )
        notes = gr.Textbox(
            value="", lines=2, label="补充项目说明（可选；文字备注，待人工核实）",
        )
        form_components = [preset, project_name, floor_area, facts, notes]
        edit_status = gr.Markdown(f"当前使用：{first_preset}预设。")
        preview_panel = gr.Markdown(preview(first_preset, *(initial[key] for key in FORM_KEYS)))
        preset.change(select_preset, inputs=preset, outputs=form_components[1:] + [preview_panel, edit_status])
        for component in form_components[1:]:
            component.input(preview_edited, inputs=form_components, outputs=[preview_panel, edit_status])
        health_button.click(health_status, outputs=health)
        run_button = gr.Button("开始分析", variant="primary")
        status = gr.Markdown()
        evidence = gr.Markdown()
        gaps = gr.Markdown()
        comparison = gr.Markdown()
        report = gr.Markdown()
        with gr.Row():
            report_file = gr.File(label="下载报告 Markdown")
            evidence_file = gr.File(label="下载证据 JSON")
        previous = gr.State(None)
        run_button.click(
            run_demo, inputs=form_components + [previous],
            outputs=[status, evidence, gaps, report, comparison, report_file, evidence_file, previous],
            concurrency_limit=1,
        )
    return app


def _bypass_proxy_for_loopback() -> None:
    """Keep Gradio's localhost startup request out of an external proxy."""
    loopback_hosts = ("127.0.0.1", "localhost", "::1")
    for variable in ("NO_PROXY", "no_proxy"):
        existing = [part.strip() for part in os.getenv(variable, "").split(",") if part.strip()]
        if "*" in existing:
            continue
        present = {part.lower() for part in existing}
        os.environ[variable] = ",".join(
            existing + [host for host in loopback_hosts if host.lower() not in present]
        )


def launch_demo() -> None:
    """Start the local UI or reuse one already listening on the chosen port."""
    _bypass_proxy_for_loopback()
    raw_port = os.getenv("GRADIO_SERVER_PORT", "7860")
    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as exc:
        raise SystemExit("GRADIO_SERVER_PORT 必须是 1 到 65535 之间的端口号") from exc

    url = f"http://127.0.0.1:{port}/"
    try:
        response = requests.get(f"{url}config", timeout=2)
        already_running = (
            response.status_code == 200
            and response.json().get("title") == "GreenSpec 绿建预审演示"
        )
    except (requests.RequestException, ValueError):
        already_running = False
    if already_running:
        print(f"GreenSpec 演示页面已在运行：{url}")
        webbrowser.open(url)
        return

    try:
        create_app().queue(default_concurrency_limit=1).launch(
            server_name="127.0.0.1", server_port=port, share=False,
            inbrowser=True,
            allowed_paths=[str((Path(__file__).resolve().parents[1] / "outputs").resolve())],
        )
    except OSError as exc:
        raise SystemExit(
            f"端口 {port} 已被其他程序占用。可设置 "
            "`$env:GRADIO_SERVER_PORT = '7861'` 后重试，并访问相应端口。"
        ) from exc


if __name__ == "__main__":
    # The upstream streaming LLM provider prints generated text. Windows may
    # otherwise use GBK and retry a successful request on an encoding error.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    launch_demo()
