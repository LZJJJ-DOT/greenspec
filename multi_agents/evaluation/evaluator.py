import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


class GreenSpecEvaluator:
    """Runs deterministic evaluations against one output directory."""

    # ``local_clause`` is the original local-knowledge-base channel.  The
    # GreenSpec adapter emits the same kind of normative evidence under the
    # more explicit ``greenspec_rag`` channel.
    LOCAL_CLAUSE_CHANNELS = frozenset({
        "local_clause",
        "greenspec_rag",
    })

    def __init__(self, cases_path: str | Path):
        self.cases_path = Path(cases_path)

        self.checks = {
            "sections_count": self._check_sections_count,
            "sections_keyword_coverage": (
                self._check_sections_keyword_coverage
            ),
            "local_clause_count": (
                self._check_local_clause_count
            ),
            "expected_clause_hit": (
                self._check_expected_clause_hit
            ),
            "web_levels_allowed": (
                self._check_web_levels_allowed
            ),
            "web_sources_classified": (
                self._check_web_sources_classified
            ),
            "risk_levels_allowed": (
                self._check_risk_levels_allowed
            ),
            "critical_missing_has_high_risk": (
                self._check_critical_missing_has_high_risk
            ),
            "report_headings": (
                self._check_report_headings
            ),
            "report_quality": (
                self._check_report_quality
            ),
        }

    def evaluate(
            self,
            run_dir: str | Path,
    ) -> Dict[str, Any]:
        run_dir = Path(run_dir)
        context = self._load_context(run_dir)

        cases_document = self._read_json(
            self.cases_path,
            {"cases": []},
        )
        cases = cases_document.get("cases", [])

        results = []

        for case in cases:
            check_name = case.get("check")
            check = self.checks.get(check_name)

            if check is None:
                passed = False
                details = (
                    f"Unknown check: {check_name}"
                )
            else:
                try:
                    passed, details = check(
                        context,
                        case.get("params", {}),
                    )
                except Exception as exc:
                    passed = False
                    details = (
                        f"{type(exc).__name__}: {exc}"
                    )

            results.append(
                {
                    "id": case.get("id"),
                    "category": case.get("category"),
                    "name": case.get("name"),
                    "passed": passed,
                    "details": details,
                }
            )

        report = self._render_report(
            run_dir=run_dir,
            results=results,
        )

        report_path = run_dir / "eval_report.md"
        report_path.write_text(
            report,
            encoding="utf-8",
        )

        passed_count = sum(
            1 for result in results
            if result["passed"]
        )

        failed_count = len(results) - passed_count

        return {
            "status": (
                "passed"
                if failed_count == 0
                else "failed"
            ),
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "report_path": str(report_path),
        }

    def _load_context(
            self,
            run_dir: Path,
    ) -> Dict[str, Any]:
        trace = self._read_json(
            run_dir / "trace.json",
            {},
            )
        evidence_pack = self._read_json(
            run_dir / "evidence_pack.json",
            {},
            )
        risk_register = self._read_json(
            run_dir / "risk_register.json",
            [],
            )

        report_path = self._find_report(run_dir)

        if report_path is None:
            report_text = ""
        else:
            report_text = report_path.read_text(
                encoding="utf-8",
            )

        return {
            "trace": trace,
            "evidence_pack": evidence_pack,
            "risk_register": risk_register,
            "report_text": report_text,
            "report_path": (
                str(report_path)
                if report_path
                else None
            ),
        }

    def _check_sections_count(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        sections = self._planner_sections(context)

        minimum = int(params.get("min", 1))
        maximum = int(params.get("max", 20))

        passed = minimum <= len(sections) <= maximum

        return (
            passed,
            f"sections={len(sections)}, "
            f"expected={minimum}..{maximum}",
        )

    def _check_sections_keyword_coverage(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        planner_output = self._planner_output(context)

        values = [
            planner_output.get("title", ""),
            *(
                    planner_output.get("sections", [])
                    or []
            ),
        ]

        text = " ".join(
            str(value)
            for value in values
        ).lower()

        concept_groups = (
                params.get("concept_groups", [])
                or []
        )

        matched_groups = []

        for group in concept_groups:
            aliases = group.get("aliases", []) or []

            if any(
                    str(alias).lower() in text
                    for alias in aliases
            ):
                matched_groups.append(
                    group.get("name")
                )

        minimum = int(
            params.get("min_groups", 1)
        )

        return (
            len(matched_groups) >= minimum,
            (
                f"matched_groups={matched_groups}, "
                f"required={minimum}"
            ),
        )

    def _check_local_clause_count(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        local_items = self._local_clause_items(context)

        minimum = int(params.get("min", 1))

        return (
            len(local_items) >= minimum,
            f"local_clause_count={len(local_items)}",
        )

    def _check_expected_clause_hit(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        actual_ids = set()

        for item in self._local_clause_items(context):
            metadata = item.get("metadata", {}) or {}
            clause_id = (
                    metadata.get("clause_id")
                    or item.get("evidence_id")
            )

            if clause_id:
                actual_ids.add(str(clause_id))

            actual_ids.update(
                self._legacy_greenspec_clause_aliases(item)
            )

        expected = set(
            params.get("expected_any", [])
        )
        matched = sorted(actual_ids & expected)

        return (
            bool(matched),
            f"matched_clause_ids={matched}",
        )

    def _check_web_levels_allowed(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        web_items = self._web_items(context)
        allowed = set(params.get("allowed", []))

        invalid = [
            {
                "evidence_id": item.get("evidence_id"),
                "source_level": item.get(
                    "source_level"
                ),
            }
            for item in web_items
            if item.get("source_level") not in allowed
        ]

        passed = bool(web_items) and not invalid

        return (
            passed,
            f"web_count={len(web_items)}, "
            f"invalid={invalid}",
        )

    def _check_web_sources_classified(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        web_items = self._web_items(context)
        explicit_levels = set(
            params.get("explicit_levels", [])
        )

        invalid = [
            {
                "evidence_id": item.get("evidence_id"),
                "source_level": item.get(
                    "source_level"
                ),
                "url": item.get("url"),
            }
            for item in web_items
            if (
                    item.get("source_level")
                    not in explicit_levels
                    or not item.get("url")
            )
        ]

        passed = bool(web_items) and not invalid

        return (
            passed,
            f"web_count={len(web_items)}, "
            f"unclassified_or_missing_url={invalid}",
        )

    def _check_risk_levels_allowed(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        risks = context.get("risk_register", [])
        allowed = set(params.get("allowed", []))
        minimum = int(params.get("min", 1))

        invalid = [
            risk.get("risk_level")
            for risk in risks
            if risk.get("risk_level") not in allowed
        ]

        passed = (
                len(risks) >= minimum
                and not invalid
        )

        return (
            passed,
            f"risk_count={len(risks)}, "
            f"invalid_levels={invalid}",
        )

    def _check_critical_missing_has_high_risk(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        profile = (
            context.get("evidence_pack", {})
            .get("project_profile", {})
        )

        known_parameters = profile.get(
            "known_parameters",
            {},
        ) or {}

        parameter_keys = params.get(
            "parameter_keys",
            [],
        ) or []

        missing = [
            key
            for key in parameter_keys
            if known_parameters.get(key) is False
        ]
        unknown = [
            key
            for key in parameter_keys
            if (
                    known_parameters.get(key) is not True
                    and known_parameters.get(key) is not False
            )
        ]

        expected_levels = set(
            params.get("expected_levels", [])
        )

        high_risk_items = [
            risk
            for risk in context.get(
                "risk_register",
                [],
            ) or []
            if risk.get("risk_level")
                        in expected_levels
        ]
        high_risks = [
            risk.get("risk_id")
            for risk in high_risk_items
        ]

        gaps = (
                context.get("evidence_pack", {})
                .get("gaps", [])
                or []
        )
        related_gap_ids = {
            gap.get("gap_id")
            for gap in gaps
            if gap.get("gap_id")
            and any(
                key in json.dumps(
                    gap,
                    ensure_ascii=False,
                    default=str,
                )
                for key in parameter_keys
            )
        }
        related_high_risks = [
            risk.get("risk_id")
            for risk in high_risk_items
            if related_gap_ids.intersection(
                risk.get("trigger_gap_ids", []) or []
            )
        ]

        if unknown:
            passed = False
            evaluation_mode = (
                "critical_parameters_unknown"
            )
        elif missing:
            passed = bool(
                related_high_risks
                if related_gap_ids
                else high_risks
            )
            evaluation_mode = (
                "critical_parameters_missing"
            )
        else:
            passed = not bool(related_high_risks)
            evaluation_mode = (
                "critical_parameters_present"
            )

        return (
            passed,
            f"mode={evaluation_mode}, "
            f"missing={missing}, "
            f"unknown={unknown}, "
            f"high_risks={high_risks}, "
            f"related_high_risks={related_high_risks}",
        )

    def _check_report_headings(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        report = context.get(
            "report_text",
            "",
        )

        level_two_headings = []

        for line in report.splitlines():
            stripped = line.strip()

            if (
                    stripped.startswith("## ")
                    and not stripped.startswith("### ")
            ):
                level_two_headings.append(
                    stripped[3:].strip().lower()
                )

        missing_groups = []

        for group in params.get(
                "required_groups",
                [],
        ):
            aliases = [
                str(alias).lower()
                for alias in group.get(
                    "aliases",
                    [],
                )
            ]

            matched = any(
                any(
                    alias in heading
                    for alias in aliases
                )
                for heading in level_two_headings
            )

            if not matched:
                missing_groups.append(
                    group.get("name")
                )

        return (
            not missing_groups,
            (
                f"headings={level_two_headings}, "
                f"missing_groups={missing_groups}"
            ),
        )

    def _check_report_quality(
            self,
            context: Dict[str, Any],
            params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        report = context.get(
            "report_text",
            "",
        )

        minimum = int(
            params.get("min_chars", 1)
        )

        forbidden = [
            value
            for value in params.get(
                "forbidden",
                [],
            )
            if str(value).lower() in report.lower()
        ]

        passed = (
                len(report) >= minimum
                and not forbidden
        )

        return (
            passed,
            f"characters={len(report)}, "
            f"forbidden_found={forbidden}",
        )

    def _planner_output(
            self,
            context: Dict[str, Any],
    ) -> Dict[str, Any]:
        events = (
            context.get("trace", {})
            .get("events", [])
        )

        planner_events = [
            event
            for event in events
            if (
                    event.get("node_name") == "planner"
                    and event.get("status") == "success"
            )
        ]

        if not planner_events:
            return {}

        output = (
                planner_events[-1].get("output")
                or {}
        )

        return (
            output
            if isinstance(output, dict)
            else {}
        )

    def _planner_sections(
            self,
            context: Dict[str, Any],
    ) -> List[Any]:
        return (
                self._planner_output(context)
                .get("sections", [])
                or []
        )

    def _evidence_items(
            self,
            context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return (
                context.get("evidence_pack", {})
                .get("evidence_items", [])
                or []
        )

    def _local_clause_items(
            self,
            context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            item
            for item in self._evidence_items(context)
            if item.get("channel") in self.LOCAL_CLAUSE_CHANNELS
        ]

    def _legacy_greenspec_clause_aliases(
            self,
            item: Dict[str, Any],
    ) -> set[str]:
        """Map the three legacy GB/T 50378 eval IDs to canonical evidence.

        The old fixture grouped 3.2.6--3.2.8 under one ID and used a
        separate ID for table 3.2.8.  GreenSpec keeps the canonical clause
        and table identifiers, so only these documented equivalences are
        accepted; unrelated GreenSpec evidence is never treated as a hit.
        """
        if item.get("channel") != "greenspec_rag":
            return set()

        source_id = self._normalise_standard_id(
            item.get("source_id")
        )
        if source_id != "GBT503782019":
            return set()

        aliases = set()
        clause_no = str(item.get("clause_no") or "").strip()
        metadata = item.get("metadata", {}) or {}
        canonical_id = str(
            metadata.get("clause_id")
            or item.get("evidence_id")
            or ""
        ).lower()

        if clause_no == "3.2.5":
            aliases.add("GBT50378-2019-003")
        if clause_no in {"3.2.6", "3.2.7", "3.2.8"}:
            aliases.add("GBT50378-2019-004")
        if "table-3.2.8" in canonical_id:
            aliases.add("GBT50378-2019-005")

        return aliases

    @staticmethod
    def _normalise_standard_id(value: Any) -> str:
        return "".join(
            character
            for character in str(value or "").upper()
            if character.isalnum()
        )

    def _web_items(
            self,
            context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            item
            for item in self._evidence_items(context)
            if item.get("channel") == "web_policy"
        ]

    def _find_report(
            self,
            run_dir: Path,
    ) -> Path | None:
        candidates = [
            path
            for path in run_dir.glob("*.md")
            if path.name != "eval_report.md"
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda path: path.stat().st_mtime,
        )

    def _read_json(
            self,
            path: Path,
            default: Any,
    ) -> Any:
        if not path.exists():
            return default

        with open(
                path,
                "r",
                encoding="utf-8-sig",
        ) as file:
            return json.load(file)

    def _render_report(
            self,
            run_dir: Path,
            results: List[Dict[str, Any]],
    ) -> str:
        passed = sum(
            1 for result in results
            if result["passed"]
        )
        total = len(results)

        lines = [
            "# GreenSpec Eval Report",
            "",
            f"- Run directory: `{run_dir}`",
            (
                    "- Generated at: "
                    + datetime.now(
                timezone.utc
            ).isoformat()
            ),
            f"- Score: **{passed}/{total}**",
            "",
            "## Results",
            "",
            "| ID | Category | Result | Name | Details |",
            "| --- | --- | --- | --- | --- |",
        ]

        for result in results:
            status = (
                "PASS"
                if result["passed"]
                else "FAIL"
            )

            details = str(
                result.get("details", "")
            )
            details = details.replace(
                "|",
                "\\|",
            ).replace(
                "\n",
                " ",
            )

            lines.append(
                f"| {result['id']} "
                f"| {result['category']} "
                f"| {status} "
                f"| {result['name']} "
                f"| {details} |"
            )

        failed = [
            result
            for result in results
            if not result["passed"]
        ]

        lines.extend(
            [
                "",
                "## Failed Cases",
                "",
            ]
        )

        if not failed:
            lines.append("No failed cases.")
        else:
            for result in failed:
                lines.append(
                    f"- `{result['id']}` "
                    f"{result['name']}: "
                    f"{result['details']}"
                )

        lines.append("")
        return "\n".join(lines)
