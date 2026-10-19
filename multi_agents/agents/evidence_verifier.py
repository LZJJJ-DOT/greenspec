from typing import Any, Dict, List, Tuple


class EvidenceVerifier:
    """Verifies claims against the evidence contained in an evidence pack."""

    CLAIM_USE_POLICIES = {
        "precheck_conclusion": {
            "mode": "all",
            "requires_verified_t0": True,
            "requires_url": False,
        },
        "project_fact": {
            "mode": "all",
            "requires_verified_t0": False,
            "requires_url": False,
        },
        "policy_context": {
            "mode": "any",
            "requires_verified_t0": False,
            "requires_url": True,
        },
        "methodology": {
            "mode": "any",
            "requires_verified_t0": False,
            "requires_url": False,
        },
    }

    STATUS_SUPPORTED = "supported"
    STATUS_PARTIALLY_SUPPORTED = "partially_supported"
    STATUS_UNSUPPORTED = "unsupported"
    STATUS_NEEDS_MANUAL_REVIEW = "needs_manual_review"

    ACTION_ACCEPT = "accept"
    ACTION_REVISE = "revise"
    ACTION_RESEARCH_AGAIN = "research_again"

    SOURCE_PASS = "pass"
    SOURCE_FAIL = "fail"
    SOURCE_NEEDS_MANUAL_REVIEW = "needs_manual_review"

    def verify(self, evidence_pack: Dict[str, Any]) -> Dict[str, Any]:
        claims = evidence_pack.get("claims", []) or []
        evidence_items = evidence_pack.get("evidence_items", []) or []

        evidence_by_id = {
            item.get("evidence_id"): item
            for item in evidence_items
            if item.get("evidence_id")
        }

        items = [
            self._verify_claim(
                index=index,
                claim=claim,
                evidence_by_id=evidence_by_id,
            )
            for index, claim in enumerate(claims, start=1)
        ]

        summary = self._build_summary(items)
        decision = self._decide(items)
        research_again_queries = self._build_research_again_queries(items)

        return {
            "verification_id": "VER-001",
            "decision": decision,
            "summary": summary,
            "research_again_queries": research_again_queries,
            "items": items,
        }

    def _verify_claim(
            self,
            index: int,
            claim: Dict[str, Any],
            evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        claim_id = claim.get("claim_id") or f"CLAIM-{index:03d}"
        claim_text = str(claim.get("claim") or "")
        claim_use = claim.get("claim_use")
        required_levels = self._as_list(
            claim.get("required_source_levels")
        )
        evidence_ids = self._as_list(
            claim.get("supporting_evidence_ids")
        )

        configuration_issues = []

        if not claim.get("claim_id"):
            configuration_issues.append("ISSUE_CLAIM_ID_MISSING")

        if not claim_use:
            configuration_issues.append("ISSUE_CLAIM_USE_MISSING")

        if not required_levels:
            configuration_issues.append(
                "ISSUE_REQUIRED_SOURCE_LEVELS_MISSING"
            )

        if not evidence_ids:
            return self._build_item(
                index=index,
                claim_id=claim_id,
                claim_text=claim_text,
                status=self.STATUS_UNSUPPORTED,
                evidence_ids=[],
                required_levels=required_levels,
                actual_levels=[],
                source_level_check=self.SOURCE_FAIL,
                citation_check=self._empty_citation_check(),
                issues=configuration_issues + [
                    "ISSUE_NO_SUPPORTING_EVIDENCE"
                ],
                recommended_action=self.ACTION_RESEARCH_AGAIN,
            )

        resolved_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
        ]

        missing_evidence_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in evidence_by_id
        ]

        actual_levels = self._unique(
            [
                item.get("source_level")
                for item in resolved_evidence
                if item.get("source_level")
            ]
        )

        if missing_evidence_ids:
            citation_check = self._build_citation_check(
                evidence_items=resolved_evidence,
                requires_formal_clause="T0" in required_levels,
                requires_url=claim_use == "policy_context",
            )

            return self._build_item(
                index=index,
                claim_id=claim_id,
                claim_text=claim_text,
                status=self.STATUS_UNSUPPORTED,
                evidence_ids=evidence_ids,
                required_levels=required_levels,
                actual_levels=actual_levels,
                source_level_check=self.SOURCE_FAIL,
                citation_check=citation_check,
                issues=configuration_issues + [
                    "ISSUE_EVIDENCE_ID_NOT_FOUND: "
                    + ", ".join(missing_evidence_ids)
                ],
                recommended_action=self.ACTION_RESEARCH_AGAIN,
            )

        span_issues = self._check_evidence_spans(
            claim=claim,
            evidence_by_id=evidence_by_id,
            evidence_ids=evidence_ids,
        )

        source_check, qualifying_evidence, source_issues = (
            self._check_source_levels(
                claim_use=claim_use,
                required_levels=required_levels,
                evidence_items=resolved_evidence,
            )
        )

        citation_check = self._build_citation_check(
            evidence_items=qualifying_evidence or resolved_evidence,
            requires_formal_clause="T0" in required_levels,
            requires_url=claim_use == "policy_context",
        )

        citation_issues = self._build_citation_issues(
            citation_check=citation_check,
            requires_formal_clause="T0" in required_levels,
            requires_url=claim_use == "policy_context",
        )

        issues = (
            configuration_issues
            + span_issues
            + source_issues
            + citation_issues
        )

        if source_check == self.SOURCE_FAIL:
            return self._build_item(
                index=index,
                claim_id=claim_id,
                claim_text=claim_text,
                status=self.STATUS_UNSUPPORTED,
                evidence_ids=evidence_ids,
                required_levels=required_levels,
                actual_levels=actual_levels,
                source_level_check=source_check,
                citation_check=citation_check,
                issues=issues,
                recommended_action=self.ACTION_RESEARCH_AGAIN,
            )

        if (
                source_check == self.SOURCE_NEEDS_MANUAL_REVIEW
                or configuration_issues
        ):
            return self._build_item(
                index=index,
                claim_id=claim_id,
                claim_text=claim_text,
                status=self.STATUS_NEEDS_MANUAL_REVIEW,
                evidence_ids=evidence_ids,
                required_levels=required_levels,
                actual_levels=actual_levels,
                source_level_check=source_check,
                citation_check=citation_check,
                issues=issues,
                recommended_action=self.ACTION_REVISE,
            )

        if citation_issues or span_issues:
            return self._build_item(
                index=index,
                claim_id=claim_id,
                claim_text=claim_text,
                status=self.STATUS_PARTIALLY_SUPPORTED,
                evidence_ids=evidence_ids,
                required_levels=required_levels,
                actual_levels=actual_levels,
                source_level_check=source_check,
                citation_check=citation_check,
                issues=issues,
                recommended_action=self.ACTION_REVISE,
            )

        return self._build_item(
            index=index,
            claim_id=claim_id,
            claim_text=claim_text,
            status=self.STATUS_SUPPORTED,
            evidence_ids=evidence_ids,
            required_levels=required_levels,
            actual_levels=actual_levels,
            source_level_check=source_check,
            citation_check=citation_check,
            issues=[],
            recommended_action=self.ACTION_ACCEPT,
        )

    def _check_source_levels(
            self,
            claim_use: str,
            required_levels: List[str],
            evidence_items: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]], List[str]]:
        policy = self.CLAIM_USE_POLICIES.get(claim_use)

        if not policy:
            return (
                self.SOURCE_NEEDS_MANUAL_REVIEW,
                [],
                ["ISSUE_UNKNOWN_CLAIM_USE"],
            )

        if not required_levels:
            return (
                self.SOURCE_NEEDS_MANUAL_REVIEW,
                [],
                ["ISSUE_NO_SOURCE_LEVEL_POLICY"],
            )

        matching_evidence = {
            source_level: [
                item
                for item in evidence_items
                if self._matches_required_level(
                    item=item,
                    source_level=source_level,
                    requires_verified_t0=policy["requires_verified_t0"],
                )
            ]
            for source_level in required_levels
        }

        if policy["mode"] == "all":
            missing_levels = [
                source_level
                for source_level, matches in matching_evidence.items()
                if not matches
            ]

            if not missing_levels:
                qualifying_evidence = []
                for matches in matching_evidence.values():
                    qualifying_evidence.extend(matches)

                return (
                    self.SOURCE_PASS,
                    self._unique_evidence(qualifying_evidence),
                    [],
                )

            if self._has_candidate_source(
                    evidence_items=evidence_items,
                    required_levels=missing_levels,
            ):
                return (
                    self.SOURCE_NEEDS_MANUAL_REVIEW,
                    self._unique_evidence(evidence_items),
                    [
                        "ISSUE_SOURCE_REQUIRES_MANUAL_VERIFICATION: "
                        + ", ".join(missing_levels)
                    ],
                )

            return (
                self.SOURCE_FAIL,
                [],
                [
                    "ISSUE_REQUIRED_SOURCE_LEVEL_MISSING: "
                    + ", ".join(missing_levels)
                ],
            )

        qualifying_evidence = []
        for matches in matching_evidence.values():
            qualifying_evidence.extend(matches)

        if qualifying_evidence:
            return (
                self.SOURCE_PASS,
                self._unique_evidence(qualifying_evidence),
                [],
            )

        if self._has_candidate_source(
                evidence_items=evidence_items,
                required_levels=required_levels,
        ):
            return (
                self.SOURCE_NEEDS_MANUAL_REVIEW,
                self._unique_evidence(evidence_items),
                ["ISSUE_SOURCE_REQUIRES_MANUAL_VERIFICATION"],
            )

        return (
            self.SOURCE_FAIL,
            [],
            ["ISSUE_REQUIRED_SOURCE_LEVEL_MISSING"],
        )

    def _matches_required_level(
            self,
            item: Dict[str, Any],
            source_level: str,
            requires_verified_t0: bool,
    ) -> bool:
        actual_level = item.get("source_level")
        metadata = item.get("metadata", {}) or {}

        if source_level == "T0":
            return bool(
                item.get("channel") in {"local_clause", "greenspec_rag"}
                and actual_level == "T0"
                and (
                        not requires_verified_t0
                        or metadata.get("verification_status") == "verified"
                )
            )

        return actual_level == source_level

    def _check_evidence_spans(
            self,
            claim: Dict[str, Any],
            evidence_by_id: Dict[str, Dict[str, Any]],
            evidence_ids: List[str],
    ) -> List[str]:
        """Require an exact, locally resolvable quote for every cited ID.

        This does not attempt semantic entailment.  It prevents an agent from
        attaching a valid-looking evidence ID without showing the source span
        it relied on, and keeps that span independently reviewable.
        """
        spans = claim.get("evidence_spans")
        if not isinstance(spans, list):
            return ["ISSUE_EVIDENCE_SPANS_MISSING"]

        quote_by_id: Dict[str, str] = {}
        issues = []
        for span in spans:
            if not isinstance(span, dict):
                issues.append("ISSUE_EVIDENCE_SPAN_INVALID")
                continue
            evidence_id = span.get("evidence_id")
            quote = str(span.get("quote") or "").strip()
            if not evidence_id or not quote:
                issues.append("ISSUE_EVIDENCE_SPAN_INVALID")
                continue
            if evidence_id in quote_by_id:
                issues.append(f"ISSUE_EVIDENCE_SPAN_DUPLICATE: {evidence_id}")
                continue
            quote_by_id[str(evidence_id)] = quote

        cited = set(evidence_ids)
        for evidence_id in cited:
            quote = quote_by_id.get(evidence_id)
            content = str(
                evidence_by_id.get(evidence_id, {}).get("content")
                or ""
            )
            if not quote:
                issues.append(f"ISSUE_EVIDENCE_SPAN_MISSING: {evidence_id}")
            elif quote not in content:
                issues.append(f"ISSUE_EVIDENCE_QUOTE_NOT_FOUND: {evidence_id}")

        for evidence_id in quote_by_id:
            if evidence_id not in cited:
                issues.append(f"ISSUE_EVIDENCE_SPAN_NOT_CITED: {evidence_id}")
        return self._unique(issues)

    def _has_candidate_source(
            self,
            evidence_items: List[Dict[str, Any]],
            required_levels: List[str],
    ) -> bool:
        for item in evidence_items:
            actual_level = item.get("source_level")
            metadata = item.get("metadata", {}) or {}

            if (
                    "T0" in required_levels
                    and (
                    actual_level == "T0_CANDIDATE"
                    or (
                            actual_level == "T0"
                            and metadata.get("verification_status") != "verified"
                    )
            )
            ):
                return True

            if (
                    any(level in {"T1", "T2", "T3"} for level in required_levels)
                    and actual_level == "T1_T2_T3_UNCLASSIFIED"
            ):
                return True

        return False

    def _build_citation_check(
            self,
            evidence_items: List[Dict[str, Any]],
            requires_formal_clause: bool,
            requires_url: bool,
    ) -> Dict[str, bool]:
        source_present = bool(evidence_items) and all(
            bool(item.get("source_name"))
            and bool(item.get("source_id"))
            for item in evidence_items
        )

        if requires_formal_clause:
            local_clause_evidence = [
                item
                for item in evidence_items
                if item.get("channel") in {
                    "local_clause",
                    "greenspec_rag",
                }
            ]

            clause_no_present = bool(local_clause_evidence) and all(
                bool(item.get("clause_no"))
                for item in local_clause_evidence
            )

            page_present = bool(local_clause_evidence) and all(
                bool(item.get("page"))
                for item in local_clause_evidence
            )

            version_present = bool(local_clause_evidence) and all(
                bool(
                    (item.get("metadata", {}) or {}).get(
                        "standard_version"
                    )
                )
                for item in local_clause_evidence
            )
        else:
            clause_no_present = True
            page_present = True
            version_present = True

        if requires_url:
            url_present = bool(evidence_items) and all(
                bool(item.get("url"))
                for item in evidence_items
            )
        else:
            url_present = True

        return {
            "source_present": source_present,
            "clause_no_present": clause_no_present,
            "page_present": page_present,
            "version_present": version_present,
            "_url_present": url_present,
        }

    def _build_citation_issues(
            self,
            citation_check: Dict[str, bool],
            requires_formal_clause: bool,
            requires_url: bool,
    ) -> List[str]:
        issues = []

        if not citation_check["source_present"]:
            issues.append("ISSUE_SOURCE_NAME_OR_ID_MISSING")

        if requires_formal_clause:
            if not citation_check["clause_no_present"]:
                issues.append("ISSUE_CLAUSE_NO_MISSING")

            if not citation_check["page_present"]:
                issues.append("ISSUE_PAGE_MISSING")

            if not citation_check["version_present"]:
                issues.append("ISSUE_STANDARD_VERSION_MISSING")

        if requires_url and not citation_check["_url_present"]:
            issues.append("ISSUE_URL_MISSING")

        return issues

    def _build_item(
            self,
            index: int,
            claim_id: str,
            claim_text: str,
            status: str,
            evidence_ids: List[str],
            required_levels: List[str],
            actual_levels: List[str],
            source_level_check: str,
            citation_check: Dict[str, bool],
            issues: List[str],
            recommended_action: str,
    ) -> Dict[str, Any]:
        return {
            "verification_id": f"VER-CLAIM-{index:03d}",
            "claim_id": claim_id,
            "claim": claim_text,
            "status": status,
            "evidence_ids": evidence_ids,
            "required_source_levels": required_levels,
            "actual_source_levels": actual_levels,
            "source_level_check": source_level_check,
            "citation_check": {
                "source_present": citation_check["source_present"],
                "clause_no_present": citation_check[
                    "clause_no_present"
                ],
                "page_present": citation_check["page_present"],
                "version_present": citation_check["version_present"],
            },
            "issues": self._unique(issues),
            "recommended_action": recommended_action,
        }

    def _build_summary(
            self,
            items: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        counts = {
            self.STATUS_SUPPORTED: 0,
            self.STATUS_PARTIALLY_SUPPORTED: 0,
            self.STATUS_UNSUPPORTED: 0,
            self.STATUS_NEEDS_MANUAL_REVIEW: 0,
        }

        for item in items:
            status = item.get("status")
            if status in counts:
                counts[status] += 1

        return {
            "claims_total": len(items),
            "supported": counts[self.STATUS_SUPPORTED],
            "partially_supported": counts[
                self.STATUS_PARTIALLY_SUPPORTED
            ],
            "unsupported": counts[self.STATUS_UNSUPPORTED],
            "needs_manual_review": counts[
                self.STATUS_NEEDS_MANUAL_REVIEW
            ],
        }

    def _decide(self, items: List[Dict[str, Any]]) -> str:
        actions = {
            item.get("recommended_action")
            for item in items
        }

        if self.ACTION_RESEARCH_AGAIN in actions:
            return self.ACTION_RESEARCH_AGAIN

        if self.ACTION_REVISE in actions:
            return self.ACTION_REVISE

        return self.ACTION_ACCEPT

    def _build_research_again_queries(
            self,
            items: List[Dict[str, Any]],
    ) -> List[str]:
        queries = []

        for item in items:
            if (
                    item.get("recommended_action")
                    != self.ACTION_RESEARCH_AGAIN
            ):
                continue

            claim = str(
                item.get("claim") or ""
            )

            required_levels = set(
                item.get(
                    "required_source_levels",
                    [],
                )
                or []
            )

            actual_levels = set(
                item.get(
                    "actual_source_levels",
                    [],
                )
                or []
            )

            # Project evidence must come from project
            # documents, not public web research.
            if (
                    "PROJECT" in required_levels
                    and "PROJECT" not in actual_levels
            ):
                continue

            if (
                    "T0" in required_levels
                    and "T0" not in actual_levels
            ):
                queries.append(
                    "Find the verified official "
                    "standard clause, standard ID, "
                    "clause number, page and version "
                    f"for this claim: {claim}"
                )
                continue

            queries.append(
                "Find authoritative evidence with "
                "a clear source and URL for this "
                f"claim: {claim}"
            )

        return self._unique(queries)

    def _empty_citation_check(self) -> Dict[str, bool]:
        return {
            "source_present": False,
            "clause_no_present": False,
            "page_present": False,
            "version_present": False,
            "_url_present": False,
        }

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _unique(
            self,
            values: List[Any],
    ) -> List[Any]:
        seen = set()
        unique_values = []

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            unique_values.append(value)

        return unique_values

    def _unique_evidence(
            self,
            evidence_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        seen = set()
        unique_items = []

        for item in evidence_items:
            evidence_id = item.get("evidence_id")
            if not evidence_id or evidence_id in seen:
                continue

            seen.add(evidence_id)
            unique_items.append(item)

        return unique_items
