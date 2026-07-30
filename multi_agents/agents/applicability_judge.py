from typing import Any, Dict, List, Optional
from .calculation_basis import (
    missing_calculation_facts,
)

class ApplicabilityJudge:
    """Judges whether local clause evidence applies to the current project.

    This class only produces applicability results.
    It does not perform risk analysis, write files, or generate reports.
    """

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"

    BUILDING_TYPE_ALIASES = {
        "office": {
            "office",
            "办公楼",
            "办公建筑",
            "普通办公楼",
        },
        "public_building": {
            "public_building",
            "公共建筑",
        },
        "residential": {
            "residential",
            "住宅",
            "住宅建筑",
        },
    }



    def judge(
            self,
            project_profile: Dict[str, Any],
            evidence_items: List[Dict[str, Any]],
            project_doc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        local_clause_items = [
            item for item in evidence_items
            if item.get("channel") == "local_clause"
        ]

        results = []
        for index, item in enumerate(local_clause_items, start=1):
            results.append(
                self._judge_one(
                    index=index,
                    evidence_item=item,
                    project_profile=project_profile,
                    project_doc=project_doc or "",
                )
            )

        return results

    def _judge_one(
            self,
            index: int,
            evidence_item: Dict[str, Any],
            project_profile: Dict[str, Any],
            project_doc: str,
    ) -> Dict[str, Any]:
        metadata = evidence_item.get("metadata", {}) or {}

        project_matches = {
            "region": self._region_matches(metadata, project_profile),
            "building_type": self._building_type_matches(metadata, project_profile),
            "design_phase": self._design_phase_matches(metadata, project_profile),
            "green_target_scope": self._green_target_scope_matches(metadata, project_profile),
        }

        reason_codes = []

        if not project_matches["region"]:
            reason_codes.append("REGION_NOT_MATCHED")
            return self._build_result(
                index=index,
                evidence_item=evidence_item,
                metadata=metadata,
                applicable_status=self.NOT_APPLICABLE,
                confidence=0.9,
                reason_codes=reason_codes,
                project_matches=project_matches,
                missing_facts=[],
                manual_review_required=False,
            )
        reason_codes.append("REGION_MATCHED")

        if not project_matches["building_type"]:
            reason_codes.append("BUILDING_TYPE_NOT_MATCHED")
            return self._build_result(
                index=index,
                evidence_item=evidence_item,
                metadata=metadata,
                applicable_status=self.NOT_APPLICABLE,
                confidence=0.9,
                reason_codes=reason_codes,
                project_matches=project_matches,
                missing_facts=[],
                manual_review_required=False,
            )
        reason_codes.append("BUILDING_TYPE_MATCHED")

        if not project_matches["design_phase"]:
            reason_codes.append("DESIGN_PHASE_NOT_MATCHED")
            return self._build_result(
                index=index,
                evidence_item=evidence_item,
                metadata=metadata,
                applicable_status=self.NOT_APPLICABLE,
                confidence=0.9,
                reason_codes=reason_codes,
                project_matches=project_matches,
                missing_facts=[],
                manual_review_required=False,
            )
        reason_codes.append("DESIGN_PHASE_MATCHED")

        if not project_matches["green_target_scope"]:
            reason_codes.append("GREEN_TARGET_SCOPE_NOT_MATCHED")
            return self._build_result(
                index=index,
                evidence_item=evidence_item,
                metadata=metadata,
                applicable_status=self.NOT_APPLICABLE,
                confidence=0.9,
                reason_codes=reason_codes,
                project_matches=project_matches,
                missing_facts=[],
                manual_review_required=False,
            )
        reason_codes.append("GREEN_TARGET_SCOPE_MATCHED")
        reason_codes.append("PROJECT_SCOPE_MATCHED")

        missing_facts = self._find_missing_facts(
            metadata=metadata,
            project_profile=project_profile,
        )

        missing_calculation = missing_calculation_facts(
            metadata=metadata,
            project_profile=project_profile,
        )

        missing_facts = self._unique(
            missing_facts + missing_calculation
        )

        if missing_facts:
            reason_codes.append(
                "PROJECT_FACTS_MISSING"
            )

        if missing_calculation:
            reason_codes.append(
                "REQUIRES_CALCULATION"
            )

        clause_requires_manual_review = bool(
            metadata.get("requires_manual_review")
        )

        if clause_requires_manual_review:
            reason_codes.append(
                "MANUAL_REVIEW_REQUIRED"
            )

        manual_review_required = bool(
            missing_facts
            or clause_requires_manual_review
        )

        applicable_status = (
            self.NEEDS_MANUAL_REVIEW
            if manual_review_required
            else self.APPLICABLE
        )

        confidence = self._calculate_confidence(
            evidence_item=evidence_item,
            applicable_status=applicable_status,
            missing_facts=missing_facts,
            manual_review_required=manual_review_required,
        )

        return self._build_result(
            index=index,
            evidence_item=evidence_item,
            metadata=metadata,
            applicable_status=applicable_status,
            confidence=confidence,
            reason_codes=reason_codes,
            project_matches=project_matches,
            missing_facts=missing_facts,
            manual_review_required=manual_review_required,
        )

    def _build_result(
            self,
            index: int,
            evidence_item: Dict[str, Any],
            metadata: Dict[str, Any],
            applicable_status: str,
            confidence: float,
            reason_codes: List[str],
            project_matches: Dict[str, bool],
            missing_facts: List[str],
            manual_review_required: bool,
    ) -> Dict[str, Any]:
        evidence_id = evidence_item.get("evidence_id")

        return {
            "result_id": f"APP-{index:03d}",
            "evidence_id": evidence_id,
            "clause_id": metadata.get("clause_id") or evidence_id,
            "clause_no": evidence_item.get("clause_no"),
            "applicable_status": applicable_status,
            "confidence": round(confidence, 2),
            "reason_codes": self._unique(reason_codes),
            "project_matches": project_matches,
            "missing_facts": missing_facts,
            "manual_review_required": manual_review_required,
        }

    def _canonical_building_types(
            self,
            values: List[Any],
    ) -> set[str]:
        canonical_values = set()

        for value in values:
            if value is None:
                continue

            normalized_value = self._normalize_text(value)

            if not normalized_value:
                continue

            matched_code = None

            for code, aliases in self.BUILDING_TYPE_ALIASES.items():
                normalized_aliases = {
                    self._normalize_text(alias)
                    for alias in aliases
                }

                if normalized_value in normalized_aliases:
                    matched_code = code
                    break

            if matched_code:
                canonical_values.add(matched_code)
            else:
                canonical_values.add(normalized_value)

        return canonical_values

    def _region_matches(
            self,
            metadata: Dict[str, Any],
            project_profile: Dict[str, Any],
    ) -> bool:
        clause_region = metadata.get("region")
        if not clause_region:
            return True

        project_location = project_profile.get("location", {}) or {}
        project_region = self._normalize_region(
            project_location.get("city") or project_location.get("province")
        )

        clause_regions = self._as_list(clause_region)
        normalized_clause_regions = [
            self._normalize_region(region) for region in clause_regions
        ]

        return (
                "national" in normalized_clause_regions
                or project_region in normalized_clause_regions
        )

    def _building_type_matches(
            self,
            metadata: Dict[str, Any],
            project_profile: Dict[str, Any],
    ) -> bool:
        clause_values = self._as_list(metadata.get("building_type"))
        if not clause_values:
            return True

        building = project_profile.get("building", {}) or {}
        project_values = [
            building.get("building_category"),
            building.get("building_type_code"),
            building.get("building_type"),
        ]
        clause_codes = self._canonical_building_types(
            clause_values
        )
        project_codes = self._canonical_building_types(
            project_values
        )

        if not clause_codes:
            return True

        if not project_codes:
            return False

        return bool(clause_codes & project_codes)

    def _design_phase_matches(
            self,
            metadata: Dict[str, Any],
            project_profile: Dict[str, Any],
    ) -> bool:
        clause_values = self._as_list(metadata.get("design_phase"))
        if not clause_values:
            return True

        building = project_profile.get("building", {}) or {}
        project_values = [building.get("design_phase")]

        return self._list_intersects(clause_values, project_values)

    def _green_target_scope_matches(
            self,
            metadata: Dict[str, Any],
            project_profile: Dict[str, Any],
    ) -> bool:
        clause_values = self._as_list(metadata.get("green_target_scope"))
        if not clause_values:
            return True

        green_target = project_profile.get("green_building_target", {}) or {}

        project_values = []
        if green_target.get("precheck") == "two_star":
            project_values.append("two_star_precheck")
        if green_target.get("gap_analysis") == "three_star":
            project_values.append("three_star_gap_analysis")

        return self._list_intersects(clause_values, project_values)

    def _find_missing_facts(
            self,
            metadata: Dict[str, Any],
            project_profile: Dict[str, Any],
    ) -> List[str]:
        required_facts = self._as_list(metadata.get("requires_project_facts"))
        if not required_facts:
            return []

        missing_fields = set(
            self._normalize_text(field)
            for field in project_profile.get("missing_fields", []) or []
        )

        known_parameters = project_profile.get("known_parameters", {}) or {}

        missing = []
        for fact in required_facts:
            if self._fact_is_missing(fact, missing_fields, known_parameters):
                missing.append(str(fact))

        return missing

    def _fact_is_missing(
            self,
            fact: Any,
            missing_fields: set,
            known_parameters: Dict[str, Any],
    ) -> bool:
        normalized_fact = self._normalize_text(fact)

        if normalized_fact in missing_fields:
            return True

        fact_to_parameter = {
            "围护结构热工参数": "has_envelope_thermal_parameters",
            "暖通空调系统方案": "has_hvac_system_scheme",
            "照明功率密度": "has_lighting_power_density",
            "可再生能源系统方案": "has_renewable_energy_scheme",
            "水资源利用方案": "has_water_saving_scheme",
            "节水器具等级": "has_water_saving_scheme",
            "绿色建材比例": "has_green_material_ratio",
            "模拟计算结果": "has_energy_simulation_result",
            "建筑能耗模拟结果": "has_energy_simulation_result",
            "采光模拟结果": "has_daylight_simulation_result",
            "绿色建筑评分计算": "has_green_score_calculation",
            "专项计算书": "has_formal_calculation_report",
        }

        for keyword, parameter_key in fact_to_parameter.items():
            normalized_keyword = self._normalize_text(keyword)

            if normalized_keyword in normalized_fact:
                return known_parameters.get(parameter_key) is False

        return False


    def _calculate_confidence(
            self,
            evidence_item: Dict[str, Any],
            applicable_status: str,
            missing_facts: List[str],
            manual_review_required: bool,
    ) -> float:
        base_confidence = float(evidence_item.get("confidence") or 0.75)

        if applicable_status == self.NOT_APPLICABLE:
            return min(base_confidence, 0.9)

        if missing_facts:
            base_confidence -= 0.12

        if manual_review_required:
            base_confidence -= 0.08

        return max(0.4, min(base_confidence, 0.95))

    def _list_intersects(self, left: List[Any], right: List[Any]) -> bool:
        normalized_left = {
            self._normalize_text(value)
            for value in left
            if value is not None and str(value).strip()
        }

        normalized_right = {
            self._normalize_text(value)
            for value in right
            if value is not None and str(value).strip()
        }

        if not normalized_left:
            return True

        if not normalized_right:
            return False

        return bool(normalized_left & normalized_right)

    def _normalize_region(self, value: Any) -> str:
        text = self._normalize_text(value)

        if "北京" in text or "鍖椾含" in text:
            return "beijing"

        if text in {"national", "全国", "国家", "鍏ㄥ浗", "鍥藉"}:
            return "national"

        return text

    def _normalize_text(self, value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "")

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _unique(self, values: List[str]) -> List[str]:
        seen = set()
        unique_values = []

        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)

        return unique_values