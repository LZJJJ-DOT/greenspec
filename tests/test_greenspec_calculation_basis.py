from multi_agents.agents.applicability_judge import (
    ApplicabilityJudge,
)
from multi_agents.agents.calculation_basis import (
    missing_calculation_facts,
)
from multi_agents.agents.risk_gap_analyst import (
    RiskGapAnalyst,
)


def build_project_profile():
    return {
        "location": {
            "city": "北京市",
        },
        "building": {
            "building_category": "public_building",
            "building_type_code": "office",
            "building_type": "普通办公楼",
            "design_phase": (
                "scheme_or_preliminary_design"
            ),
        },
        "green_building_target": {
            "precheck": "two_star",
            "gap_analysis": "three_star",
        },
        "known_parameters": {
            "has_energy_special_report": True,
            "has_energy_simulation_result": False,
            "has_daylight_simulation_result": False,
            "has_green_score_calculation": False,
            "has_formal_calculation_report": False,
            "has_envelope_thermal_parameters": False,
            "has_hvac_system_scheme": True,
            "has_lighting_power_density": False,
            "has_renewable_energy_scheme": False,
            "has_water_saving_scheme": True,
            "has_green_material_ratio": False,
        },
        "missing_fields": [
            "建筑能耗模拟结果",
        ],
    }


def build_calculation_evidence(
        required_fact="建筑能耗模拟结果",
        evidence_id="TEST-CALC-001",
):
    return {
        "evidence_id": evidence_id,
        "channel": "local_clause",
        "source_level": "T0",
        "source_name": "绿色建筑评价标准",
        "source_id": "GBT50378-2019",
        "clause_no": "7.2.1",
        "page": "32",
        "confidence": 0.9,
        "metadata": {
            "clause_id": evidence_id,
            "standard_version": "2019",
            "verification_status": "verified",
            "region": "national",
            "building_type": [
                "public_building",
                "office",
            ],
            "design_phase": [
                "scheme_or_preliminary_design",
            ],
            "green_target_scope": [
                "two_star_precheck",
                "three_star_gap_analysis",
            ],
            "requires_project_facts": [
                required_fact,
            ],
            "requires_calculation": True,
            "requires_manual_review": False,
        },
    }


def build_evidence_pack(
        profile,
        evidence,
        gap_description,
):
    return {
        "project_profile": profile,
        "evidence_items": [evidence],
        "gaps": [
            {
                "gap_id": "GAP-CALC-001",
                "gap_type": "missing_project_fact",
                "description": gap_description,
                "next_action": (
                    "request_project_documents"
                ),
            },
        ],
        "channels": {
            "web_policy": {
                "enabled": False,
            },
        },
    }


def test_energy_report_without_results_is_not_calculation_basis():
    profile = build_project_profile()

    metadata = {
        "requires_calculation": True,
        "requires_project_facts": [
            "建筑能耗模拟结果",
        ],
    }

    missing = missing_calculation_facts(
        metadata=metadata,
        project_profile=profile,
    )

    assert missing == [
        "建筑能耗模拟结果",
    ]


def test_energy_result_satisfies_energy_requirement():
    profile = build_project_profile()

    profile["known_parameters"][
        "has_energy_simulation_result"
    ] = True

    metadata = {
        "requires_calculation": True,
        "requires_project_facts": [
            "建筑能耗模拟结果",
        ],
    }

    missing = missing_calculation_facts(
        metadata=metadata,
        project_profile=profile,
    )

    assert missing == []


def test_energy_result_does_not_satisfy_daylight_requirement():
    profile = build_project_profile()

    profile["known_parameters"].update({
        "has_energy_simulation_result": True,
        "has_daylight_simulation_result": False,
    })

    metadata = {
        "requires_calculation": True,
        "requires_project_facts": [
            "采光模拟结果",
        ],
    }

    missing = missing_calculation_facts(
        metadata=metadata,
        project_profile=profile,
    )

    assert missing == [
        "采光模拟结果",
    ]


def test_generic_simulation_result_is_still_missing():
    profile = build_project_profile()
    known_parameters = profile[
        "known_parameters"
    ]

    result = ApplicabilityJudge()._fact_is_missing(
        fact="模拟计算结果",
        missing_fields=set(),
        known_parameters=known_parameters,
    )

    assert result is True


def test_requires_calculation_adds_reason_code():
    profile = build_project_profile()
    evidence = build_calculation_evidence()

    results = ApplicabilityJudge().judge(
        project_profile=profile,
        evidence_items=[evidence],
        project_doc=(
            "建筑能耗模拟结果尚未提供。"
        ),
    )

    assert len(results) == 1

    result = results[0]

    assert (
            result["applicable_status"]
            == "needs_manual_review"
    )
    assert result[
               "manual_review_required"
           ] is True
    assert (
            "REQUIRES_CALCULATION"
            in result["reason_codes"]
    )
    assert (
            "PROJECT_FACTS_MISSING"
            in result["reason_codes"]
    )
    assert (
            "建筑能耗模拟结果"
            in result["missing_facts"]
    )


def test_missing_calculation_result_creates_p1_risk():
    profile = build_project_profile()
    evidence = build_calculation_evidence()

    applicability_results = (
        ApplicabilityJudge().judge(
            project_profile=profile,
            evidence_items=[evidence],
            project_doc=(
                "建筑能耗模拟结果尚未提供。"
            ),
        )
    )

    evidence_pack = build_evidence_pack(
        profile=profile,
        evidence=evidence,
        gap_description=(
            "缺少建筑能耗模拟结果"
        ),
    )

    risks = RiskGapAnalyst().analyze(
        project_profile=profile,
        applicability_results=(
            applicability_results
        ),
        evidence_pack=evidence_pack,
    )

    p1_risks = [
        risk
        for risk in risks
        if risk["risk_level"] == "P1"
    ]

    assert len(p1_risks) >= 1
    assert (
            "TEST-CALC-001"
            in p1_risks[0][
                "trigger_clause_ids"
            ]
    )
    assert (
            p1_risks[0]["next_action"]
            == "perform_calculation"
    )


def test_daylight_gap_still_creates_p1_when_energy_result_exists():
    profile = build_project_profile()

    profile["known_parameters"].update({
        "has_energy_simulation_result": True,
        "has_daylight_simulation_result": False,
    })
    profile["missing_fields"] = [
        "采光模拟结果",
    ]

    evidence = build_calculation_evidence(
        required_fact="采光模拟结果",
        evidence_id="TEST-DAYLIGHT-001",
    )

    applicability_results = (
        ApplicabilityJudge().judge(
            project_profile=profile,
            evidence_items=[evidence],
            project_doc=(
                "能耗模拟已经提供，"
                "采光模拟结果尚未提供。"
            ),
        )
    )

    result = applicability_results[0]

    assert (
            "REQUIRES_CALCULATION"
            in result["reason_codes"]
    )
    assert (
            "采光模拟结果"
            in result["missing_facts"]
    )

    evidence_pack = build_evidence_pack(
        profile=profile,
        evidence=evidence,
        gap_description=(
            "缺少采光模拟结果"
        ),
    )

    risks = RiskGapAnalyst().analyze(
        project_profile=profile,
        applicability_results=(
            applicability_results
        ),
        evidence_pack=evidence_pack,
    )

    assert any(
        risk["risk_level"] == "P1"
        and "TEST-DAYLIGHT-001"
        in risk["trigger_clause_ids"]
        for risk in risks
    )