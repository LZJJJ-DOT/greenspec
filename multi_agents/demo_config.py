"""One-source input mapping for the GreenSpec RAG interview demo."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
PRESET_PATHS = {
    "资料不完整": REPO_ROOT / "greenspec/profiles/beijing_office_demo.json",
    "资料改善版": REPO_ROOT / "greenspec/profiles/beijing_office_improved_demo.json",
}
DEFAULT_AS_OF_DATE = "2026-09-02"  # Historical demonstration baseline, visible in the UI.


@dataclass(frozen=True)
class FactField:
    key: str
    missing_name: str
    document_name: str


FACT_FIELDS = {
    "围护结构热工参数": FactField("has_envelope_thermal_parameters", "围护结构热工参数", "围护结构热工参数表"),
    "窗墙比统计": FactField("has_window_to_wall_ratio", "窗墙比", "窗墙比统计表"),
    "照明功率密度": FactField("has_lighting_power_density", "照明功率密度", "照明功率密度计算书"),
    "建筑能耗模拟": FactField("has_energy_simulation_result", "建筑能耗模拟结果", "建筑能耗模拟报告"),
    "采光模拟": FactField("has_daylight_simulation_result", "采光模拟结果", "采光模拟报告"),
    "可再生能源方案": FactField("has_renewable_energy_scheme", "可再生能源系统方案", "可再生能源专项方案"),
    "绿色建筑评分计算": FactField("has_green_score_calculation", "绿色建筑评分计算结果", "绿色建筑评分计算表"),
    "正式专项计算报告": FactField("has_formal_calculation_report", "正式专项计算报告", "正式专项计算报告"),
    "绿色建材比例": FactField("has_green_material_ratio", "绿色建材比例", "绿色建材比例统计"),
}


@dataclass(frozen=True)
class DemoInput:
    preset: str
    project_name: str
    city: str
    building_type: str
    construction: str
    design_phase: str
    floor_area_m2: float
    precheck: str
    gap_analysis: str
    provided_facts: list[str]
    province: str = "北京市"
    district: str = "朝阳区"
    climate_zone: str = "寒冷地区"
    above_ground_area_m2: float = 32000
    underground_area_m2: float = 10000
    building_height_m: float = 45
    above_ground_floors: int = 10
    underground_floors: int = 2
    plot_ratio: float = 2.5
    green_space_ratio: float = 0.3
    additional_notes: str = ""
    focus: str = ""
    as_of_date: str = DEFAULT_AS_OF_DATE


class DemoInputError(ValueError):
    """Input or GreenSpec service state cannot support a live demo run."""


def load_preset(name: str) -> dict:
    if name not in PRESET_PATHS:
        raise DemoInputError(f"未知案例：{name}")
    return json.loads(PRESET_PATHS[name].read_text(encoding="utf-8-sig"))


def preset_values(name: str) -> dict:
    profile = load_preset(name)
    known = profile.get("known_parameters", {})
    missing = set(profile.get("missing_fields", []))
    provided = [
        label for label, field in FACT_FIELDS.items()
        if known.get(field.key, field.missing_name not in missing) is True
    ]
    return {
        "project_name": profile["project_name"],
        "province": profile["location"]["province"],
        "city": profile["location"]["city"],
        "district": profile["location"]["district"],
        "climate_zone": profile["location"]["climate_zone"],
        "building_type": profile["building"]["building_type"],
        "construction": "新建" if profile["building"].get("new_or_existing") == "new_building" else "既有",
        "design_phase": "方案深化" if profile["building"].get("design_phase") == "scheme_or_preliminary_design" else "初步设计",
        "floor_area_m2": profile["building"]["gross_floor_area_m2"],
        "above_ground_area_m2": profile["building"]["above_ground_area_m2"],
        "underground_area_m2": profile["building"]["underground_area_m2"],
        "building_height_m": profile["building"]["building_height_m"],
        "above_ground_floors": profile["building"]["above_ground_floors"],
        "underground_floors": profile["building"]["underground_floors"],
        "plot_ratio": profile["building"]["plot_ratio"],
        "green_space_ratio_percent": profile["building"]["green_space_ratio"] * 100,
        "precheck": profile["green_building_target"]["precheck"],
        "gap_analysis": profile["green_building_target"]["gap_analysis"],
        "provided_facts": provided,
        "additional_notes": "",
        "focus": "",
        "as_of_date": DEFAULT_AS_OF_DATE,
    }


def _validate_input(value: DemoInput, *, require_supported_scope: bool = True) -> None:
    if value.preset not in PRESET_PATHS:
        raise DemoInputError("请选择一个已验证的案例预设")
    if not value.project_name.strip():
        raise DemoInputError("请填写项目名称")
    if not all(isinstance(field, str) and field.strip() for field in (
        value.province, value.city, value.district, value.climate_zone,
    )):
        raise DemoInputError("请填写省、市、区和气候区")
    if value.building_type not in {"普通办公楼", "校园建筑", "其他"}:
        raise DemoInputError("请选择页面列出的建筑类型")
    for label, number, positive in (
        ("总建筑面积", value.floor_area_m2, True),
        ("地上建筑面积", value.above_ground_area_m2, False),
        ("地下建筑面积", value.underground_area_m2, False),
        ("建筑高度", value.building_height_m, True),
        ("容积率", value.plot_ratio, False),
    ):
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not math.isfinite(number) or number < 0
                or (positive and number == 0)):
            requirement = "正数" if positive else "非负数"
            raise DemoInputError(f"{label}必须是有效的{requirement}")
    for label, number in (
        ("地上层数", value.above_ground_floors),
        ("地下层数", value.underground_floors),
    ):
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not float(number).is_integer() or number < 0:
            raise DemoInputError(f"{label}必须是非负整数")
    if value.above_ground_floors == 0:
        raise DemoInputError("地上层数必须大于 0")
    if (isinstance(value.green_space_ratio, bool)
            or not isinstance(value.green_space_ratio, (int, float))
            or not math.isfinite(value.green_space_ratio)
            or not 0 <= value.green_space_ratio <= 1):
        raise DemoInputError("绿地率须在 0% 到 100% 之间")
    if set(value.provided_facts) - set(FACT_FIELDS):
        raise DemoInputError("资料清单包含未知项目")
    try:
        date.fromisoformat(value.as_of_date)
    except (TypeError, ValueError) as exc:
        raise DemoInputError("检索基准日期请使用 YYYY-MM-DD 格式") from exc
    if require_supported_scope and not is_supported_scope(value):
        raise DemoInputError(
            "当前仅北京新建普通办公楼（二星级目标提升至三星级目标）可运行分析；"
            "其他地点或建筑类型可填写并预览画像。北京项目的气候区请填“寒冷地区”。"
        )


def is_supported_scope(value: DemoInput) -> bool:
    return (
        value.province.strip() in {"北京", "北京市"}
        and value.city.strip() in {"北京", "北京市"}
        and value.climate_zone.strip() == "寒冷地区"
        and value.building_type == "普通办公楼"
        and value.construction == "新建"
        and value.design_phase in {"方案深化", "初步设计"}
        and value.precheck == "two_star"
        and value.gap_analysis == "three_star"
    )


def build_demo_profile(value: DemoInput) -> dict:
    """Resolve a preset and all edited fields for preview or supported analysis."""
    _validate_input(value, require_supported_scope=False)
    profile = deepcopy(load_preset(value.preset))
    profile["project_name"] = value.project_name.strip()
    profile["location"].update({
        "province": value.province.strip(),
        "city": value.city.strip(),
        "district": value.district.strip(),
        "climate_zone": value.climate_zone.strip(),
    })
    profile["building"]["building_type"] = value.building_type.strip()
    profile["building"]["building_type_code"] = "office" if value.building_type == "普通办公楼" else None
    profile["building"]["building_category"] = "public_building" if value.building_type == "普通办公楼" else None
    profile["building"]["new_or_existing"] = "new_building"
    profile["building"]["design_phase"] = "scheme_or_preliminary_design"
    profile["building"].update({
        "gross_floor_area_m2": value.floor_area_m2,
        "above_ground_area_m2": value.above_ground_area_m2,
        "underground_area_m2": value.underground_area_m2,
        "building_height_m": value.building_height_m,
        "above_ground_floors": int(value.above_ground_floors),
        "underground_floors": int(value.underground_floors),
        "plot_ratio": value.plot_ratio,
        "green_space_ratio": value.green_space_ratio,
    })
    profile["green_building_target"]["precheck"] = value.precheck
    profile["green_building_target"]["gap_analysis"] = value.gap_analysis

    selected = set(value.provided_facts)
    known = profile.setdefault("known_parameters", {})
    for label, field in FACT_FIELDS.items():
        known[field.key] = label in selected
    controlled_missing = {field.missing_name for field in FACT_FIELDS.values()}
    profile["missing_fields"] = [
        field for field in profile.get("missing_fields", []) if field not in controlled_missing
    ] + [field.missing_name for label, field in FACT_FIELDS.items() if label not in selected]
    core_documents = ["项目参数表", "建筑设计说明", "节能专篇", "绿色建筑策划表"]
    profile["available_documents"] = core_documents + [
        field.document_name for label, field in FACT_FIELDS.items() if label in selected
    ]
    return profile


def build_demo_task(value: DemoInput, *, rag_url: str | None = None) -> dict:
    """Create an isolated task, document summary and RAG request from one form."""
    _validate_input(value)
    profile = build_demo_profile(value)
    known = profile["known_parameters"]

    query = value.focus.strip() or (
        f"请针对{value.city.strip()}新建普通办公楼{value.design_phase}阶段，研究绿色建筑二星级预审"
        "与三星级差距分析所需的规范证据、适用条件和资料缺口。"
    )
    provided_text = "、".join(profile["available_documents"])
    missing_text = "、".join(profile["missing_fields"]) or "暂无已标记的缺失资料"
    location_text = value.province.strip()
    if value.city.strip() != location_text:
        location_text += value.city.strip()
    location_text += value.district.strip()
    project_doc = (
        f"# {profile['project_name']} · 资料摘要\n\n"
        f"项目位于{location_text}，"
        f"为新建普通办公楼，处于{value.design_phase}阶段，总建筑面积约{value.floor_area_m2:g}平方米，"
        f"其中地上{value.above_ground_area_m2:g}平方米、地下{value.underground_area_m2:g}平方米；"
        f"建筑高度{value.building_height_m:g}米，地上{int(value.above_ground_floors)}层、"
        f"地下{int(value.underground_floors)}层，容积率{value.plot_ratio:g}，"
        f"绿地率{value.green_space_ratio * 100:g}%，气候区为{value.climate_zone.strip()}。"
        "目标为绿色建筑二星级预审和三星级差距分析。\n\n"
        f"已提供资料：{provided_text}。\n\n"
        f"尚未提供或待确认：{missing_text}。\n\n"
        "以上资料状态来自本次表单；未提供不等于不满足规范要求。\n\n"
        "本分析仅用于方案/初设阶段咨询预审；星级认定、专项计算和申报结论须由专业人员复核。\n"
    )
    if value.additional_notes.strip():
        project_doc += f"\n## 用户补充说明（待人工核实，不覆盖以上表单事实）\n\n{value.additional_notes.strip()}\n"

    task = json.loads((REPO_ROOT / "multi_agents/task.json").read_text(encoding="utf-8-sig"))
    task.pop("local_clause_path", None)
    task.pop("project_profile_path", None)
    task.pop("project_doc_path", None)
    task["query"] = query
    task["project_profile"] = profile
    task["project_doc"] = project_doc
    task["project_doc_source_id"] = "gradio_form"
    task["greenspec_rag_url"] = (rag_url or os.getenv("GREENSPEC_RAG_URL") or "http://127.0.0.1:8787").rstrip("/")
    task["greenspec_retrieve_request"] = {
        "query": query,
        "project_profile": {
            "location": {**profile["location"], "region": "北京"},
            "building": {**profile["building"], "building_category": "公共建筑", "design_phase": value.design_phase},
            "green_building_target": deepcopy(profile["green_building_target"]),
            "known_parameters": deepcopy(known),
            "missing_fields": list(profile["missing_fields"]),
        },
        "filters": {
            "standard_ids": [], "clause_nos": [], "as_of_date": value.as_of_date,
            "must_be_current": True, "include_commentary": False,
        },
        "top_k": 10,
        "allow_degraded": False,
    }
    return task


def check_rag_health(base_url: str | None = None) -> dict:
    url = (base_url or os.getenv("GREENSPEC_RAG_URL") or "http://127.0.0.1:8787").rstrip("/") + "/health"
    try:
        response = requests.get(url, timeout=5)
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DemoInputError("GreenSpec RAG 服务不可连接；请先启动 Qdrant 与 rag-api") from exc
    if not isinstance(payload, dict) or response.status_code != 200 or payload.get("ready") is not True:
        dependencies = payload.get("dependencies", {}) if isinstance(payload, dict) else {}
        unavailable = [name for name, state in dependencies.items() if state.get("status") != "ready"]
        detail = "、".join(unavailable) or "索引或模型依赖"
        raise DemoInputError(f"GreenSpec RAG 尚未就绪：{detail}")
    return payload
