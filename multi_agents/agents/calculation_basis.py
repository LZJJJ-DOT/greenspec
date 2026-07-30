from typing import Any, Dict, List, Tuple


FACT_REQUIREMENTS: List[
    Tuple[str, Tuple[str, ...]]
] = [
    (
        "建筑能耗模拟结果",
        ("has_energy_simulation_result",),
    ),
    (
        "采光模拟结果",
        ("has_daylight_simulation_result",),
    ),
    (
        "绿色建筑评分计算",
        ("has_green_score_calculation",),
    ),
    (
        "专项计算书",
        ("has_formal_calculation_report",),
    ),
    (
        "围护结构热工参数",
        ("has_envelope_thermal_parameters",),
    ),
    (
        "暖通空调系统方案",
        ("has_hvac_system_scheme",),
    ),
    (
        "照明功率密度",
        ("has_lighting_power_density",),
    ),
    (
        "可再生能源系统方案",
        ("has_renewable_energy_scheme",),
    ),
    (
        "水资源利用方案",
        ("has_water_saving_scheme",),
    ),
    (
        "节水器具等级",
        ("has_water_saving_scheme",),
    ),
    (
        "非传统水源利用方案",
        ("has_water_saving_scheme",),
    ),
    (
        "材料比例统计",
        ("has_green_material_ratio",),
    ),
    (
        "模拟计算结果",
        (
            "has_energy_simulation_result",
            "has_daylight_simulation_result",
            "has_green_score_calculation",
        ),
    ),
    (
        "专项报告",
        ("has_formal_calculation_report",),
    ),
]

DEFAULT_CALCULATION_FLAGS = (
    "has_green_score_calculation",
    "has_formal_calculation_report",
)


def missing_calculation_facts(
        metadata: Dict[str, Any],
        project_profile: Dict[str, Any],
) -> List[str]:
    if metadata.get("requires_calculation") is not True:
        return []

    known = (
            project_profile.get("known_parameters", {})
            or {}
    )
    required_facts = (
            metadata.get("requires_project_facts", [])
            or []
    )

    recognized = []
    missing = []

    for fact in required_facts:
        fact_text = str(fact)

        for keyword, accepted_flags in FACT_REQUIREMENTS:
            if keyword not in fact_text:
                continue

            recognized.append(fact_text)

            if not any(
                    known.get(flag) is True
                    for flag in accepted_flags
            ):
                missing.append(fact_text)

            break

    if not recognized and not any(
            known.get(flag) is True
            for flag in DEFAULT_CALCULATION_FLAGS
    ):
        missing.append("通用专项计算或评分依据")

    return list(dict.fromkeys(missing))