import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class LocalClauseRetriever:
    """Retrieves verified local clause evidence with metadata filters and keyword scoring.

    This retriever only handles local authoritative clause evidence.
    It does not call web search, read project documents, write reports, or make compliance decisions.
    """

    def __init__(self, clause_path: str | Path):
        self.clause_path = Path(clause_path)
        self.clauses = self._load_clauses(self.clause_path)

    def retrieve(
            self,
            query: str,
            sections: Optional[List[str]],
            project_profile: Dict[str, Any],
            top_k: int = 12,
    ) -> List[Dict[str, Any]]:
        sections = sections or []
        candidates = self._metadata_filter(project_profile)
        scored = []

        for clause in candidates:
            score = self._score_clause(clause, query, sections, project_profile)
            if score <= 0:
                continue

            evidence_item = self._to_evidence_item(clause, score)
            scored.append(evidence_item)

        scored.sort(
            key=lambda item: (
                item.get("retrieval_score", 0),
                item.get("confidence", 0),
            ),
            reverse=True,
        )

        return scored[:top_k]

    def _load_clauses(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []

        clauses = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                clauses.append(json.loads(line))

        return clauses

    def _metadata_filter(self, project_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        location = project_profile.get("location", {})
        building = project_profile.get("building", {})
        green_target = project_profile.get("green_building_target", {})

        project_region = self._normalize_region(location.get("city") or location.get("province"))
        project_building_category = building.get("building_category")
        project_building_type = building.get("building_type")
        project_design_phase = building.get("design_phase")

        target_scopes = []
        if green_target.get("precheck") == "two_star":
            target_scopes.append("two_star_precheck")
        if green_target.get("gap_analysis") == "three_star":
            target_scopes.append("three_star_gap_analysis")

        filtered = []

        for clause in self.clauses:
            if not self._region_matches(clause.get("region"), project_region):
                continue

            if not self._list_field_matches(
                    clause.get("building_type", []),
                    [project_building_category, project_building_type],
                    allow_empty=True,
            ):
                continue

            if not self._list_field_matches(
                    clause.get("design_phase", []),
                    [project_design_phase],
                    allow_empty=True,
            ):
                continue

            if target_scopes and not self._list_field_matches(
                    clause.get("green_target_scope", []),
                    target_scopes,
                    allow_empty=True,
            ):
                continue

            filtered.append(clause)

        return filtered

    def _score_clause(
            self,
            clause: Dict[str, Any],
            query: str,
            sections: List[str],
            project_profile: Dict[str, Any],
    ) -> int:
        score = 0
        query_text = self._normalize_text(query)
        section_text = self._normalize_text(" ".join(str(section) for section in sections))
        search_text = f"{query_text} {section_text}"

        clause_title = self._normalize_text(clause.get("clause_title", ""))
        clause_summary = self._normalize_text(clause.get("clause_summary", ""))
        clause_text = self._normalize_text(clause.get("clause_text", ""))
        topic_text = self._normalize_text(" ".join(clause.get("topic", []) or []))
        keyword_text = self._normalize_text(" ".join(clause.get("keywords", []) or []))

        for keyword in clause.get("keywords", []) or []:
            keyword_norm = self._normalize_text(keyword)
            if not keyword_norm:
                continue

            if keyword_norm in query_text:
                score += 4
            if keyword_norm in section_text:
                score += 3
            if keyword_norm in topic_text:
                score += 1

        for token in self._query_tokens(search_text):
            if token in clause_title:
                score += 4
            if token in clause_summary:
                score += 3
            if token in topic_text:
                score += 2
            if token in keyword_text:
                score += 2
            if token in clause_text:
                score += 1

        score += self._metadata_score(clause, project_profile)
        score += self._quality_score(clause)

        return score

    def _metadata_score(self, clause: Dict[str, Any], project_profile: Dict[str, Any]) -> int:
        score = 0
        location = project_profile.get("location", {})
        building = project_profile.get("building", {})
        green_target = project_profile.get("green_building_target", {})

        project_region = self._normalize_region(location.get("city") or location.get("province"))
        if self._region_matches(clause.get("region"), project_region):
            score += 2

        if self._list_field_matches(
                clause.get("building_type", []),
                [building.get("building_category"), building.get("building_type")],
                allow_empty=False,
        ):
            score += 3

        if self._list_field_matches(
                clause.get("design_phase", []),
                [building.get("design_phase")],
                allow_empty=False,
        ):
            score += 3

        target_scopes = []
        if green_target.get("precheck") == "two_star":
            target_scopes.append("two_star_precheck")
        if green_target.get("gap_analysis") == "three_star":
            target_scopes.append("three_star_gap_analysis")

        if self._list_field_matches(
                clause.get("green_target_scope", []),
                target_scopes,
                allow_empty=False,
        ):
            score += 2

        return score

    def _quality_score(self, clause: Dict[str, Any]) -> int:
        score = 0

        if clause.get("source_level") == "T0":
            score += 5
        elif clause.get("source_level") == "T0_CANDIDATE":
            score += 1

        if clause.get("verification_status") == "verified":
            score += 5
        elif clause.get("verification_status") == "needs_manual_check":
            score -= 3

        if clause.get("clause_no"):
            score += 2
        if clause.get("source_page"):
            score += 2

        return score

    def _to_evidence_item(self, clause: Dict[str, Any], score: int) -> Dict[str, Any]:
        max_reasonable_score = 40
        confidence = min(0.95, 0.45 + score / max_reasonable_score)

        return {
            "evidence_id": clause.get("clause_id"),
            "channel": "local_clause",
            "source_level": clause.get("source_level"),
            "source_name": clause.get("standard_name"),
            "source_id": clause.get("standard_id"),
            "clause_no": clause.get("clause_no"),
            "page": clause.get("source_page"),
            "url": None,
            "content": clause.get("clause_summary") or clause.get("clause_text") or "",
            "matched_topic": " / ".join(clause.get("topic", []) or []),
            "confidence": round(confidence, 2),
            "retrieval_score": score,
            "metadata": {
                "clause_id": clause.get("clause_id"),
                "standard_version": clause.get("standard_version"),
                "source_file": clause.get("source_file"),
                "clause_title": clause.get("clause_title"),
                "clause_type": clause.get("clause_type"),
                "evidence_use": clause.get("evidence_use"),
                "requires_project_facts": clause.get("requires_project_facts", []),
                "requires_calculation": clause.get("requires_calculation"),
                "requires_manual_review": clause.get("requires_manual_review"),
                "verification_status": clause.get("verification_status"),
                "risk_level_hint": clause.get("risk_level_hint"),
                "keywords": clause.get("keywords", []),
                "clause_text": clause.get("clause_text"),
                "region": clause.get("region"),
                "building_type": clause.get("building_type", []),
                "design_phase": clause.get("design_phase", []),
                "green_target_scope": clause.get("green_target_scope", []),
                "applies_when": clause.get("applies_when", []),


            },
        }

    def _region_matches(self, clause_region: Any, project_region: str) -> bool:
        if not clause_region:
            return True

        if isinstance(clause_region, list):
            clause_regions = [self._normalize_region(region) for region in clause_region]
        else:
            clause_regions = [self._normalize_region(str(clause_region))]

        return "national" in clause_regions or project_region in clause_regions

    def _normalize_region(self, value: Any) -> str:
        text = self._normalize_text(str(value or ""))

        if "北京" in text:
            return "beijing"
        if text in ["national", "国家", "全国"]:
            return "national"

        return text

    def _list_field_matches(
            self,
            clause_values: Any,
            project_values: List[Any],
            allow_empty: bool = True,
    ) -> bool:
        if not clause_values:
            return allow_empty

        if not isinstance(clause_values, list):
            clause_values = [clause_values]

        clean_clause_values = {
            self._normalize_text(str(value))
            for value in clause_values
            if value is not None
        }
        clean_project_values = {
            self._normalize_text(str(value))
            for value in project_values
            if value is not None and str(value).strip()
        }

        if not clean_project_values:
            return allow_empty

        return bool(clean_clause_values & clean_project_values)

    def _query_tokens(self, text: str) -> List[str]:
        seed_tokens = [
            "绿色建筑",
            "二星",
            "三星",
            "预审",
            "差距",
            "控制项",
            "评分项",
            "加分项",
            "节能",
            "可再生能源",
            "围护结构",
            "照明",
            "空调",
            "水资源",
            "节水",
            "室内空气",
            "声环境",
            "采光",
            "热湿环境",
            "自然通风",
            "交通",
            "无障碍",
            "公共服务",
            "绿色建材",
            "雨水",
            "风环境",
            "热岛",
            "BIM",
            "碳排放",
            "创新",
        ]

        return [token for token in seed_tokens if self._normalize_text(token) in text]

    def _normalize_text(self, value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "")