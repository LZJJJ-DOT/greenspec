import argparse
import json
import shutil
from collections import Counter
from pathlib import Path


REQUIRED_FILES = [
    "applicability_results.json",
    "risk_register.json",
    "evidence_verification.json",
    "eval_report.md",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--sample-name", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    sample_dir = repo_root / "samples" / args.sample_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    for name in REQUIRED_FILES:
        source = run_dir / name

        if not source.exists():
            raise FileNotFoundError(source)

        shutil.copy2(source, sample_dir / name)

    reports = [
        path for path in run_dir.glob("*.md")
        if path.name != "eval_report.md"
    ]

    if not reports:
        raise FileNotFoundError("No generated Markdown report found")

    report = max(reports, key=lambda path: path.stat().st_mtime)
    shutil.copy2(report, sample_dir / "report.md")

    trace = load_json(run_dir / "trace.json")
    events = trace.get("events", [])

    summary = {
        "trace_id": trace.get("trace_id"),
        "run_id": trace.get("run_id"),
        "created_at": trace.get("created_at"),
        "events_total": len(events),
        "status_counts": dict(
            Counter(event.get("status") for event in events)
        ),
        "node_counts": dict(
            Counter(event.get("node_name") for event in events)
        ),
        "total_duration_ms": round(sum(
            event.get("duration_ms") or 0
            for event in events
        ), 2),
        "events": [
            {
                "event_id": event.get("event_id"),
                "sequence": event.get("sequence"),
                "node_name": event.get("node_name"),
                "agent_name": event.get("agent_name"),
                "status": event.get("status"),
                "duration_ms": event.get("duration_ms"),
                "has_error": bool(event.get("error")),
            }
            for event in events
        ],
        "redaction": {
            "raw_inputs_removed": True,
            "raw_outputs_removed": True,
            "errors_reduced_to_boolean": True
        }
    }

    with open(
            sample_dir / "trace.summary.json",
            "w",
            encoding="utf-8",
    ) as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print(f"Sample archived to: {sample_dir}")


if __name__ == "__main__":
    main()