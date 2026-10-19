"""Machine-checkable claim contract for evidence-grounded report generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "greenspec" / "contracts" / "claim_set.schema.json"


def validate_claim_set(payload: Mapping[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: list(error.path),
    )
    if errors:
        error = errors[0]
        raise ValueError(f"Claim set contract violation at {list(error.path)}: {error.message}")


def claim_set(
        *,
        evidence_pack_id: str,
        claims: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Strip internal draft-only fields before applying the public contract."""
    fields = (
        "claim_id",
        "claim",
        "claim_use",
        "required_source_levels",
        "supporting_evidence_ids",
        "evidence_spans",
    )
    payload = {
        "schema_version": "greenspec.claim_set.v1",
        "evidence_pack_id": evidence_pack_id,
        "claims": [
            {field: claim.get(field) for field in fields}
            for claim in claims
        ],
    }
    validate_claim_set(payload)
    return payload
