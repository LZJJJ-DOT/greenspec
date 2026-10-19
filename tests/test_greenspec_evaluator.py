from multi_agents.evaluation import (
    GreenSpecEvaluator,
)


PARAMS = {
    "parameter_keys": [
        "has_envelope_thermal_parameters",
        "has_lighting_power_density",
        "has_renewable_energy_scheme",
    ],
    "expected_levels": ["P0", "P1"],
}


def make_evaluator():
    return GreenSpecEvaluator(
        cases_path="greenspec/evals/eval_cases.json"
    )


def test_eval_008_passes_when_missing_has_high_risk():
    context = {
        "evidence_pack": {
            "project_profile": {
                "known_parameters": {
                    "has_envelope_thermal_parameters": False,
                    "has_lighting_power_density": False,
                    "has_renewable_energy_scheme": False,
                }
            }
        },
        "risk_register": [
            {
                "risk_id": "RISK-001",
                "risk_level": "P0",
            }
        ],
    }

    passed, details = (
        make_evaluator()
        ._check_critical_missing_has_high_risk(
            context,
            PARAMS,
        )
    )

    assert passed is True
    assert "critical_parameters_missing" in details


def test_eval_008_fails_when_missing_has_no_high_risk():
    context = {
        "evidence_pack": {
            "project_profile": {
                "known_parameters": {
                    "has_envelope_thermal_parameters": False,
                    "has_lighting_power_density": True,
                    "has_renewable_energy_scheme": True,
                }
            }
        },
        "risk_register": [
            {
                "risk_id": "RISK-001",
                "risk_level": "P2",
            }
        ],
    }

    passed, _ = (
        make_evaluator()
        ._check_critical_missing_has_high_risk(
            context,
            PARAMS,
        )
    )

    assert passed is False


def test_eval_008_passes_when_all_parameters_present():
    context = {
        "evidence_pack": {
            "project_profile": {
                "known_parameters": {
                    "has_envelope_thermal_parameters": True,
                    "has_lighting_power_density": True,
                    "has_renewable_energy_scheme": True,
                }
            }
        },
        "risk_register": [
            {
                "risk_id": "RISK-001",
                "risk_level": "P2",
            }
        ],
    }

    passed, details = (
        make_evaluator()
        ._check_critical_missing_has_high_risk(
            context,
            PARAMS,
        )
    )

    assert passed is True
    assert (
            "critical_parameters_present"
            in details
    )

def test_eval_008_fails_when_parameter_is_unknown():
    context = {
        "evidence_pack": {
            "project_profile": {
                "known_parameters": {
                    "has_envelope_thermal_parameters": True,
                    "has_lighting_power_density": None,
                    "has_renewable_energy_scheme": True,
                }
            }
        },
        "risk_register": [],
    }

    passed, details = (
        make_evaluator()
        ._check_critical_missing_has_high_risk(
            context,
            PARAMS,
        )
    )

    assert passed is False
    assert "critical_parameters_unknown" in details


def test_eval_008_fails_on_conflicting_related_high_risk():
    context = {
        "evidence_pack": {
            "project_profile": {
                "known_parameters": {
                    "has_envelope_thermal_parameters": True,
                    "has_lighting_power_density": True,
                    "has_renewable_energy_scheme": True,
                }
            },
            "gaps": [
                {
                    "gap_id": "GAP-001",
                    "description": (
                        "has_lighting_power_density"
                    ),
                }
            ],
        },
        "risk_register": [
            {
                "risk_id": "RISK-001",
                "risk_level": "P1",
                "trigger_gap_ids": ["GAP-001"],
            }
        ],
    }

    passed, details = (
        make_evaluator()
        ._check_critical_missing_has_high_risk(
            context,
            PARAMS,
        )
    )

    assert passed is False
    assert "related_high_risks=['RISK-001']" in details

def test_evaluate_returns_failed_status(
        tmp_path,
):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        """{
          "cases": [
            {
              "id": "TEST-001",
              "check": "unknown_check"
            }
          ]
        }""",
        encoding="utf-8",
    )

    result = GreenSpecEvaluator(
        cases_path=cases_path
    ).evaluate(run_dir=tmp_path)

    assert result["status"] == "failed"
    assert result["failed"] == 1


def test_local_clause_count_accepts_greenspec_rag():
    context = {
        "evidence_pack": {
            "evidence_items": [
                {
                    "channel": "greenspec_rag",
                    "evidence_id": "GB50378-2019:3.2.6",
                }
            ]
        }
    }

    passed, details = (
        make_evaluator()
        ._check_local_clause_count(context, {"min": 1})
    )

    assert passed is True
    assert details == "local_clause_count=1"


def test_expected_clause_hit_maps_legacy_id_to_canonical_greenspec():
    context = {
        "evidence_pack": {
            "evidence_items": [
                {
                    "channel": "greenspec_rag",
                    "evidence_id": "GB50378-2019:3.2.8",
                    "source_id": "GB_T_50378_2019",
                    "clause_no": "3.2.8",
                    "metadata": {
                        "clause_id": "GB50378-2019:3.2.8",
                    },
                }
            ]
        }
    }

    passed, details = (
        make_evaluator()
        ._check_expected_clause_hit(
            context,
            {"expected_any": ["GBT50378-2019-004"]},
        )
    )

    assert passed is True
    assert "GBT50378-2019-004" in details


def test_expected_clause_hit_does_not_accept_unrelated_greenspec():
    context = {
        "evidence_pack": {
            "evidence_items": [
                {
                    "channel": "greenspec_rag",
                    "evidence_id": "GB50378-2019:3.1.3",
                    "source_id": "GB_T_50378_2019",
                    "clause_no": "3.1.3",
                }
            ]
        }
    }

    passed, details = (
        make_evaluator()
        ._check_expected_clause_hit(
            context,
            {"expected_any": ["GBT50378-2019-004"]},
        )
    )

    assert passed is False
    assert details == "matched_clause_ids=[]"
