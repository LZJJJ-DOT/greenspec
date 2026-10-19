import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT_DIR = Path(__file__).resolve().parents[1]

CONTRACT_CASES = [
    (
        "applicability_results",
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "applicability_results.schema.json",
        ROOT_DIR
        / "greenspec"
        / "examples"
        / "applicability_results.example.json",
    ),
    (
        "risk_register",
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "risk_register.schema.json",
        ROOT_DIR
        / "greenspec"
        / "examples"
        / "risk_register.example.json",
    ),
    (
        "evidence_verification",
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "evidence_verification.schema.json",
        ROOT_DIR
        / "greenspec"
        / "examples"
        / "evidence_verification.example.json",
    ),
    (
        "claim_set",
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "claim_set.schema.json",
        ROOT_DIR
        / "greenspec"
        / "examples"
        / "claim_set.example.json",
    ),
]


def load_json(path: Path):
    with open(
            path,
            "r",
            encoding="utf-8-sig",
    ) as file:
        return json.load(file)


@pytest.mark.parametrize(
    "contract_name,schema_path,example_path",
    CONTRACT_CASES,
    ids=[
        case[0]
        for case in CONTRACT_CASES
    ],
)
def test_example_matches_output_contract(
        contract_name,
        schema_path,
        example_path,
):
    schema = load_json(schema_path)
    example = load_json(example_path)

    Draft202012Validator.check_schema(
        schema
    )

    validator = Draft202012Validator(
        schema
    )

    errors = sorted(
        validator.iter_errors(example),
        key=lambda error: list(error.path),
    )

    error_messages = [
        (
            f"{contract_name}: "
            f"path={list(error.path)}: "
            f"{error.message}"
        )
        for error in errors
    ]

    assert not errors, "\n".join(
        error_messages
    )

ARTIFACT_CONTRACTS = {
    "applicability_results.json": (
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "applicability_results.schema.json"
    ),
    "risk_register.json": (
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "risk_register.schema.json"
    ),
    "evidence_verification.json": (
        ROOT_DIR
        / "greenspec"
        / "contracts"
        / "evidence_verification.schema.json"
    ),
}


def assert_artifact_matches_schema(
        artifact_path: Path,
        schema_path: Path,
):
    schema = load_json(schema_path)
    artifact = load_json(artifact_path)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(artifact),
        key=lambda error: list(error.path),
    )

    assert not errors, "\n".join(
        f"{artifact_path}: "
        f"path={list(error.path)}: "
        f"{error.message}"
        for error in errors
    )


SAMPLE_CASES = [
    (sample_dir.name, artifact_name)
    for sample_dir in sorted(
        (ROOT_DIR / "samples").iterdir()
    )
    if sample_dir.is_dir()
    for artifact_name in ARTIFACT_CONTRACTS
]


@pytest.mark.parametrize(
    "sample_name,artifact_name",
    SAMPLE_CASES,
)
def test_sample_matches_output_contract(
        sample_name,
        artifact_name,
):
    assert_artifact_matches_schema(
        ROOT_DIR / "samples" / sample_name / artifact_name,
        ARTIFACT_CONTRACTS[artifact_name],
    )


def test_latest_complete_run_matches_output_contract():
    outputs_dir = ROOT_DIR / "outputs"
    if not outputs_dir.is_dir():
        pytest.skip("No outputs directory is available")

    complete_runs = sorted(
        (
            run_dir
            for run_dir in outputs_dir.iterdir()
            if run_dir.is_dir()
            and all(
                (run_dir / artifact_name).is_file()
                for artifact_name in ARTIFACT_CONTRACTS
            )
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not complete_runs:
        pytest.skip(
            "No complete output run contains all "
            "contract artifacts"
        )

    latest_run = complete_runs[0]
    for artifact_name, schema_path in (
            ARTIFACT_CONTRACTS.items()
    ):
        assert_artifact_matches_schema(
            latest_run / artifact_name,
            schema_path,
        )
