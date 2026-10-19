"""Deterministically evaluate a real gpt-researcher claim artifact.

This evaluator intentionally does not claim report-text semantic faithfulness.
It verifies the production claim contract and produces a compact queue for the
human semantic review that follows a real run.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multi_agents.agents.claim_contract import validate_claim_set
from multi_agents.agents.evidence_verifier import EvidenceVerifier


def evaluate_claim_output(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pack_path = run_dir / "evidence_pack.json"
    if not pack_path.is_file():
        raise FileNotFoundError(f"missing production artifact: {pack_path}")
    evidence_pack = json.loads(pack_path.read_text(encoding="utf-8-sig"))
    claim_set = evidence_pack.get("claim_set")
    if not isinstance(claim_set, dict):
        raise ValueError("evidence_pack.json does not contain claim_set")
    validate_claim_set(claim_set)

    verification = EvidenceVerifier().verify(
        {
            "claims": claim_set["claims"],
            "evidence_items": evidence_pack.get("evidence_items", []),
        }
    )
    items = verification["items"]
    queue = [
        {
            "claim_id": item["claim_id"],
            "claim": item["claim"],
            "evidence_ids": item["evidence_ids"],
            "issues": item["issues"],
            "recommended_action": item["recommended_action"],
            "manual_review_required": item["status"] != "supported",
            "reviewer": None,
            "reviewed_at": None,
            "semantic_support": None,
            "notes": None,
        }
        for item in items
        if item["status"] != "supported"
    ]
    report_candidates = list(run_dir.glob("*.md"))
    return {
        "schema_version": "greenspec.claim_output_evaluation.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "claim_set_schema_valid": True,
        "report_artifact_present": bool(report_candidates),
        "evidence_pack_id": claim_set["evidence_pack_id"],
        "verification": verification,
        "metrics": {
            "claims_total": verification["summary"]["claims_total"],
            "supported_claim_rate": (
                verification["summary"]["supported"]
                / verification["summary"]["claims_total"]
                if verification["summary"]["claims_total"] else None
            ),
            "manual_review_required": len(queue),
        },
        "scope": (
            "Contract, ID provenance, quote resolvability, source-level and citation-locator checks. "
            "Human review must still judge whether each quoted span semantically entails its claim."
        ),
    }, queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a production gpt-researcher claim artifact.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-queue", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.review_queue.exists():
        raise FileExistsError("refusing to overwrite an existing claim evaluation artifact")
    report, queue = evaluate_claim_output(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.review_queue.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in queue),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "review_queue": str(args.review_queue), "metrics": report["metrics"], "decision": report["verification"]["decision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
