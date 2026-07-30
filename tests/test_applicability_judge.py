import json
from pathlib import Path

from multi_agents.agents.applicability_judge import (
    ApplicabilityJudge,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
        ROOT_DIR
        / "greenspec"
        / "evals"
        / "fixtures"
        / "applicability_judge_cases.json"
)


def load_fixture():
    with open(
            FIXTURE_PATH,
            "r",
            encoding="utf-8-sig",
    ) as file:
        return json.load(file)


def test_applicability_statuses():
    fixture = load_fixture()

    judge = ApplicabilityJudge()

    results = judge.judge(
        project_profile=fixture["project_profile"],
        evidence_items=fixture["evidence_items"],
        project_doc="",
    )

    results_by_evidence_id = {
        result["evidence_id"]: result
        for result in results
    }

    expected_status = fixture["expected_status"]

    for evidence_id, expected in expected_status.items():
        assert evidence_id in results_by_evidence_id

        actual = results_by_evidence_id[evidence_id][
            "applicable_status"
        ]

        assert actual == expected


def test_residential_clause_is_not_applicable():
    fixture = load_fixture()

    judge = ApplicabilityJudge()

    results = judge.judge(
        project_profile=fixture["project_profile"],
        evidence_items=[
            fixture["evidence_items"][0]
        ],
        project_doc="",
    )

    result = results[0]

    assert result["applicable_status"] == "not_applicable"
    assert result["project_matches"]["building_type"] is False
    assert "BUILDING_TYPE_NOT_MATCHED" in result["reason_codes"]
    assert result["manual_review_required"] is False


def test_office_alias_matches_chinese_project_type():
    fixture = load_fixture()

    judge = ApplicabilityJudge()

    office_evidence = fixture["evidence_items"][2]

    results = judge.judge(
        project_profile=fixture["project_profile"],
        evidence_items=[office_evidence],
        project_doc="",
    )

    result = results[0]

    assert result["project_matches"]["building_type"] is True
    assert result["applicable_status"] == "applicable"


def test_missing_project_fact_requires_manual_review():
    fixture = load_fixture()

    judge = ApplicabilityJudge()

    missing_fact_evidence = fixture["evidence_items"][1]

    results = judge.judge(
        project_profile=fixture["project_profile"],
        evidence_items=[missing_fact_evidence],
        project_doc="",
    )

    result = results[0]

    assert result["applicable_status"] == "needs_manual_review"
    assert result["manual_review_required"] is True
    assert "PROJECT_FACTS_MISSING" in result["reason_codes"]
    assert "照明功率密度" in result["missing_facts"]