from typing import Any, Dict, List, Set
from .calculation_basis import (
    missing_calculation_facts,
)


class RiskGapAnalyst:
    """这个文件只做风险分析，不写文件、不生成报告、不调用 LLM。
    """

    CORE_FACT_KEYWORDS = [
        "energy_simulation",
        "building_energy_simulation",
        "calculation",
        "score",
        "rating",
        "star",
        "control_item",
        "thermal",
        "envelope",
        "hvac",
        "lighting_power_density",
        "renewable_energy",
        "能耗模拟",
        "模拟计算",
        "计算",
        "得分",
        "评分",
        "星级",
        "控制项",
        "围护结构",
        "热工",
        "暖通",
        "照明功率密度",
        "可再生能源",
    ]

    PARAMETER_LABELS = {
        "has_energy_special_report": "energy_special_report",
        "has_green_building_plan": "green_building_plan",
        "has_envelope_thermal_parameters": "envelope_thermal_parameters",
        "has_hvac_system_scheme": "hvac_system_scheme",
        "has_lighting_power_density": "lighting_power_density",
        "has_renewable_energy_scheme": "renewable_energy_scheme",
        "has_water_saving_scheme": "water_saving_scheme",
        "has_green_material_ratio": "green_material_ratio",
    }

    def analyze(
            self,
            project_profile: Dict[str, Any],
            applicability_results: List[Dict[str, Any]],
            evidence_pack: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        evidence_items = evidence_pack.get("evidence_items", []) or []
        gaps = evidence_pack.get("gaps", []) or []

        evidence_by_id = {
            item.get("evidence_id"): item
            for item in evidence_items
            if item.get("evidence_id")
        }

        gap_ids = [
            gap.get("gap_id")
            for gap in gaps
            if gap.get("gap_id")
        ]

        risks = []

        project_missing_risk = self._build_project_missing_risk(
            project_profile=project_profile,
            applicability_results=applicability_results,
            gap_ids=gap_ids,
        )
        if project_missing_risk:
            risks.append(project_missing_risk)

        calculation_risk = self._build_calculation_risk(
            project_profile=project_profile,
            applicability_results=applicability_results,
            evidence_by_id=evidence_by_id,
            evidence_pack=evidence_pack,
            gap_ids=gap_ids,
        )
        if calculation_risk:
            risks.append(calculation_risk)

        manual_review_risk = self._build_manual_review_risk(
            applicability_results=applicability_results,
            evidence_by_id=evidence_by_id,
        )
        if manual_review_risk:
            risks.append(manual_review_risk)

        documentation_risk = self._build_documentation_risk(
            evidence_pack=evidence_pack,
            evidence_items=evidence_items,
        )
        if documentation_risk:
            risks.append(documentation_risk)

        return self._renumber_risks(risks)

    def _build_project_missing_risk(
            self,
            project_profile: Dict[str, Any],
            applicability_results: List[Dict[str, Any]],
            gap_ids: List[str],
    ) -> Dict[str, Any] | None:
        missing_fields = [
            str(field)
            for field in project_profile.get("missing_fields", []) or []
            if str(field).strip()
        ]

        false_parameters = [
            self.PARAMETER_LABELS.get(key, key)
            for key, value in (project_profile.get("known_parameters", {}) or {}).items()
            if value is False
        ]

        all_missing = missing_fields + false_parameters
        if not all_missing:
            return None

        related_clause_ids = self._clause_ids_with_missing_facts(applicability_results)
        related_evidence_refs = self._evidence_refs_with_missing_facts(applicability_results)

        risk_level = "P0" if self._has_core_missing_fact(all_missing) else "P2"

        if risk_level == "P0":
            title = "Core project information is missing and blocks star-level judgment"
            impact = "The system cannot form a reliable two-star precheck or three-star gap conclusion."
        else:
            title = "Project information is incomplete"
            impact = "The analysis remains usable as a preliminary screen, but completeness and credibility are reduced."

        return {
            "risk_id": "RISK-000",
            "risk_level": risk_level,
            "title": title,
            "description": (
                    "The project profile contains missing fields or unconfirmed parameters: "
                    + ", ".join(all_missing)
            ),
            "trigger_clause_ids": related_clause_ids,
            "trigger_gap_ids": gap_ids,
            "impact": impact,
            "mitigation": "Provide the missing project facts and confirm all false known_parameters before final review.",
            "next_action": "request_project_documents",
            "evidence_refs": related_evidence_refs,
        }

    def _build_calculation_risk(
            self,
            project_profile: Dict[str, Any],
            applicability_results: List[Dict[str, Any]],
            evidence_by_id: Dict[str, Dict[str, Any]],
            evidence_pack: Dict[str, Any],
            gap_ids: List[str],
    ) -> Dict[str, Any] | None:
        calculation_results = [
            result
            for result in applicability_results
            if "REQUIRES_CALCULATION" in (result.get("reason_codes", []) or [])
        ]

        calculation_evidence_ids = self._evidence_ids_requiring_calculation(evidence_by_id)

        unresolved_evidence_ids = [
            evidence_id
            for evidence_id in calculation_evidence_ids
            if missing_calculation_facts(
                (evidence_by_id[evidence_id].get("metadata", {}) or {}),
                project_profile,
            )
        ]

        if not calculation_results and not unresolved_evidence_ids:
            return None

        trigger_clause_ids = self._unique(
            [result.get("clause_id") for result in calculation_results]
            + [
                self._clause_id_for_evidence(evidence_by_id.get(evidence_id))
                for evidence_id in unresolved_evidence_ids
            ]
        )

        evidence_refs = self._unique(
            [result.get("evidence_id") for result in calculation_results]
            + unresolved_evidence_ids
        )

        return {
            "risk_id": "RISK-000",
            "risk_level": "P1",
            "title": "Required calculation basis is missing",
            "description": (
                "Some applicable clauses require calculation, but the project does not provide enough "
                "calculation basis such as simulation results, score calculation, or dedicated calculation reports."
            ),
            "trigger_clause_ids": trigger_clause_ids,
            "trigger_gap_ids": gap_ids,
            "impact": "The missing calculation basis may change the star-level conclusion or gap analysis result.",
            "mitigation": "Provide calculation reports, simulation outputs, and scoring worksheets for clauses requiring calculation.",
            "next_action": "perform_calculation",
            "evidence_refs": evidence_refs,
        }

    def _build_manual_review_risk(
            self,
            applicability_results: List[Dict[str, Any]],
            evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        manual_results = [
            result
            for result in applicability_results
            if result.get("manual_review_required") is True
               or "MANUAL_REVIEW_REQUIRED" in (result.get("reason_codes", []) or [])
        ]

        metadata_manual_evidence_ids = [
            evidence_id
            for evidence_id, evidence in evidence_by_id.items()
            if (evidence.get("metadata", {}) or {}).get("requires_manual_review") is True
        ]

        if not manual_results and not metadata_manual_evidence_ids:
            return None

        trigger_clause_ids = self._unique(
            [result.get("clause_id") for result in manual_results]
            + [
                self._clause_id_for_evidence(evidence_by_id.get(evidence_id))
                for evidence_id in metadata_manual_evidence_ids
            ]
        )

        evidence_refs = self._unique(
            [result.get("evidence_id") for result in manual_results]
            + metadata_manual_evidence_ids
        )

        return {
            "risk_id": "RISK-000",
            "risk_level": "P2",
            "title": "Manual review is required for applicable clauses",
            "description": (
                "Some clauses are applicable or potentially applicable, but they require human review "
                "because of professional judgment boundaries, missing facts, or clause-level review requirements."
            ),
            "trigger_clause_ids": trigger_clause_ids,
            "trigger_gap_ids": [],
            "impact": "The automated result can be used as a precheck aid, but cannot be treated as a final review conclusion.",
            "mitigation": "Assign qualified reviewers to verify clause applicability, calculation assumptions, and evidence sufficiency.",
            "next_action": "perform_manual_review",
            "evidence_refs": evidence_refs,
        }

    def _build_documentation_risk(
            self,
            evidence_pack: Dict[str, Any],
            evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        weak_refs = []

        for item in evidence_items:
            channel = item.get("channel")
            source_level = item.get("source_level")

            if channel == "local_clause":
                if (
                        not item.get("clause_no")
                        or not item.get("page")
                        or source_level == "T0_CANDIDATE"
                ):
                    weak_refs.append(
                        item.get("evidence_id")
                    )

            if channel == "web_policy":
                if (
                        source_level
                        == "T1_T2_T3_UNCLASSIFIED"
                        or not item.get("url")
                        or not item.get("source_id")
                ):
                    weak_refs.append(
                        item.get("evidence_id")
                    )

        weak_refs = self._unique(weak_refs)

        if not weak_refs:
            return None

        return {
            "risk_id": "RISK-000",
            "risk_level": "P3",
            "title": "Evidence documentation or source classification needs cleanup",
            "description": (
                "Some evidence may need better clause references, page references, or source-level classification "
                "before it is used in a formal compliance-facing report."
            ),
            "trigger_clause_ids": [],
            "trigger_gap_ids": [],
            "impact": "This does not usually change the technical conclusion, but it reduces auditability and report quality.",
            "mitigation": "Verify clause numbers, page references, source levels, and web evidence ranking.",
            "next_action": "check_source_reference",
            "evidence_refs": self._unique(weak_refs),
        }

    def _clause_ids_with_missing_facts(
            self,
            applicability_results: List[Dict[str, Any]],
    ) -> List[str]:
        return self._unique([
            result.get("clause_id")
            for result in applicability_results
            if result.get("missing_facts")
        ])

    def _evidence_refs_with_missing_facts(
            self,
            applicability_results: List[Dict[str, Any]],
    ) -> List[str]:
        return self._unique([
            result.get("evidence_id")
            for result in applicability_results
            if result.get("missing_facts")
        ])

    def _evidence_ids_requiring_calculation(
            self,
            evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        evidence_ids = []

        for evidence_id, evidence in evidence_by_id.items():
            metadata = evidence.get("metadata", {}) or {}
            if metadata.get("requires_calculation") is True:
                evidence_ids.append(evidence_id)

        return self._unique(evidence_ids)


    def _has_core_missing_fact(self, missing_items: List[str]) -> bool:
        normalized_items = [
            self._normalize_text(item)
            for item in missing_items
        ]

        for item in normalized_items:
            for keyword in self.CORE_FACT_KEYWORDS:
                if self._normalize_text(keyword) in item:
                    return True

        return False

    def _clause_id_for_evidence(self, evidence: Dict[str, Any] | None) -> str | None:
        if not evidence:
            return None

        metadata = evidence.get("metadata", {}) or {}
        return metadata.get("clause_id") or evidence.get("evidence_id")

    def _renumber_risks(self, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ordered_levels = {
            "P0": 0,
            "P1": 1,
            "P2": 2,
            "P3": 3,
        }

        risks.sort(key=lambda risk: ordered_levels.get(risk.get("risk_level"), 99))

        for index, risk in enumerate(risks, start=1):
            risk["risk_id"] = f"RISK-{index:03d}"

        return risks

    def _unique(self, values: List[Any]) -> List[str]:
        seen: Set[str] = set()
        unique_values = []

        for value in values:
            if value is None:
                continue

            text = str(value)
            if not text:
                continue

            if text in seen:
                continue

            seen.add(text)
            unique_values.append(text)

        return unique_values

    def _normalize_text(self, value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "").replace("-", "_")