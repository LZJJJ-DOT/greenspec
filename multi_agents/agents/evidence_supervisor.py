import json
import hashlib
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, List

from .utils.views import print_agent_output
from .local_clause_retriever import LocalClauseRetriever
from .applicability_judge import ApplicabilityJudge
from .risk_gap_analyst import RiskGapAnalyst
from .evidence_verifier import EvidenceVerifier
from .claim_contract import claim_set
from .greenspec_evidence_pack import adapt_items as adapt_greenspec_items, fetch_evidence_pack
from ..evidence.web_evidence_ledger import is_verified_record




class EvidenceSupervisorAgent:
    """Collects GreenSpec clauses, web research, and project documents."""
    T1_DOMAINS = {
        "gov.cn",
    }

    T2_DOMAINS = {
        "doi.org",
        "sciencedirect.com",
        "springer.com",
        "wiley.com",
        "tandfonline.com",
        "cnki.net",
        "nrdc.org",
        "bsria.com",
    }

    def _host_matches(
            self,
            host: str,
            domains: set,
    ) -> bool:
        return any(
            host == domain
            or host.endswith(f".{domain}")
            for domain in domains
        )

    def _classify_web_source(
            self,
            url: str,
    ) -> tuple[str, str, float]:
        host = (
                urlparse(url).hostname
                or ""
        ).lower()

        if self._host_matches(
                host,
                self.T1_DOMAINS,
        ):
            return (
                "T1",
                "official_government_domain",
                0.85,
            )

        if self._host_matches(
                host,
                self.T2_DOMAINS,
        ):
            return (
                "T2",
                "recognized_research_or_industry_source",
                0.75,
            )

        if host:
            return (
                "T3",
                "identifiable_public_web_source",
                0.6,
            )

        return (
            "T1_T2_T3_UNCLASSIFIED",
            "invalid_or_missing_hostname",
            0.4,
        )

    def __init__(
            self,
            websocket=None,
            stream_output=None,
            headers=None,
            trace_recorder=None,
    ):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}
        self.trace_recorder = trace_recorder
        self.repo_root = Path(__file__).resolve().parents[2]



    async def run(self, research_state: Dict[str, Any]) -> Dict[str, Any]:

        task = research_state.get("task", {}) or {}
        research_again_count = (
                research_state.get("research_again_count", 0) or 0
        )

        max_research_again_count = int(
            task.get("max_research_again_count", 2)
        )

        research_data = research_state.get("research_data", []) or []
        web_evidence_ledger = research_state.get("web_evidence_ledger", []) or []
        sections = research_state.get("sections", []) or []
        query = task.get("query", "")
        #因为 LangGraph 每个节点都会接收 research_state，然后返回新增状态，所以这里然后读取你准备好的三个文件：beijing_office_demo.json/clauses.jsonl/beijing_office_demo.md

        await self._log("Building evidence pack from GreenSpec RAG, web research, and project documents...")

        project_profile = task.get("project_profile")
        if not isinstance(project_profile, dict):
            project_profile = self._load_json(task.get("project_profile_path"), required=True)
        local_clause_path = self._resolve_path(
            task.get("local_clause_path"),
            required=not bool(task.get("greenspec_rag_url")),
            field_name="local_clause_path",
        )
        project_doc = task.get("project_doc")
        if not isinstance(project_doc, str):
            project_doc = self._load_text(task.get("project_doc_path"), required=True)

        upstream_evidence_pack = None
        if task.get("greenspec_rag_url"):
            retrieve_request = task.get("greenspec_retrieve_request")
            if not isinstance(retrieve_request, dict):
                raise ValueError(
                    "greenspec_retrieve_request must be a complete GreenSpec /v1/retrieve request object"
                )
            upstream_evidence_pack = fetch_evidence_pack(
                base_url=str(task["greenspec_rag_url"]),
                retrieve_request=retrieve_request,
                timeout_seconds=float(task.get("greenspec_timeout_seconds", 30)),
            )
            local_clause_evidence = adapt_greenspec_items(upstream_evidence_pack)
        else:
            local_clause_evidence = self._retrieve_local_clause_evidence(
                local_clause_path=local_clause_path,
                query=query,
                sections=sections,
                project_profile=project_profile,
                top_k=12,
            )

        web_policy_evidence = (
            self._collect_web_policy_evidence(
                ledger_records=web_evidence_ledger,
                top_k=12,
            )
        )

        project_doc_evidence = (
            self._collect_project_doc_evidence(
                project_doc=project_doc,
                project_profile=project_profile,
                source_id=task.get("project_doc_source_id")
                or Path(task.get("project_doc_path") or "demo_form").name,
            )
        )

        evidence_items = []
        evidence_items.extend(
            local_clause_evidence
        )
        evidence_items.extend(
            web_policy_evidence
        )
        evidence_items.extend(
            project_doc_evidence
        )

        gaps = self._build_gaps(project_profile, project_doc)
        #这里的gap会读取beijing_office_demo.json中的"missing_fields"以及"known_parameters"从而知道缺少什么信息，产生资料缺口
        claims = self._build_claims(evidence_items, gaps)
        #claims生成最小结论并且绑定证据链，解释说明这个结论由哪些 evidence item 支撑。

        applicability_results = await self._run_component(
            node_name="applicability_judge",
            agent_name="ApplicabilityJudge.judge",
            handler=ApplicabilityJudge().judge,
            payload={
                "project_profile": project_profile,
                "evidence_items": evidence_items,
                "project_doc": project_doc,
            },
        )

        evidence_pack = {
            "schema_version": "gpt_researcher.evidence_pack.v1",
            "query": query,
            "project_profile": project_profile,
            "upstream_evidence_pack": upstream_evidence_pack,
            "channels": {
                ("greenspec_rag" if upstream_evidence_pack else "local_clause"): {
                    "enabled": bool(local_clause_evidence),
                    "description": (
                        "GreenSpec evidence_pack.v1" if upstream_evidence_pack
                        else "Local clause knowledge base, used as candidate authoritative clause evidence."
                    )
                },
                "web_policy": {
                    "enabled": bool(web_policy_evidence),
                    "description": "Successfully fetched pages recorded in WebEvidenceLedger v1."
                },
                "project_doc": {
                    "enabled": bool(project_doc),
                    "description": "Project-side document facts and missing information."
                }
            },
            "evidence_items": evidence_items,
            "applicability_results": applicability_results,
            "claims": claims,
            "gaps": gaps,
            "notes": [
                "This evidence pack is an MVP output.",
                "Unverified GreenSpec clauses require manual review before final compliance use.",
                "Web evidence is heuristically classified as T1/T2/T3 from URL domains and still requires human verification.",
                "Project document facts should be confirmed by human reviewers."
            ]
        }
        evidence_pack["claim_set"] = claim_set(
            evidence_pack_id=str(
                (upstream_evidence_pack or {}).get("evidence_pack_id")
                or f"internal_{research_again_count}"
            ),
            claims=claims,
        )


        risk_register = await self._run_component(
            node_name="risk_gap_analyst",
            agent_name="RiskGapAnalyst.analyze",
            handler=RiskGapAnalyst().analyze,
            payload={
                "project_profile": project_profile,
                "applicability_results": applicability_results,
                "evidence_pack": evidence_pack,
            },
        )

        evidence_pack["risk_register"] = risk_register

        evidence_verification = await self._run_component(
            node_name="evidence_verifier",
            agent_name="EvidenceVerifier.verify",
            handler=EvidenceVerifier().verify,
            payload={
                "evidence_pack": evidence_pack,
            },
        )

        evidence_verification = self._apply_research_retry_limit(
            evidence_verification=evidence_verification,
            research_again_count=research_again_count,
            max_research_again_count=max_research_again_count,
        )

        evidence_pack["evidence_verification"] = evidence_verification

        evidence_summary = self._build_evidence_summary(evidence_pack)

        return {
            "evidence_pack": evidence_pack,
            "applicability_results": applicability_results,
            "risk_register": risk_register,
            "evidence_verification": evidence_verification,
            "verification_decision": evidence_verification["decision"],
            "research_again_queries": evidence_verification[
                "research_again_queries"
            ],
            "research_again_count": research_again_count,
            "research_data": research_data + [{"Evidence Pack Summary": evidence_summary}]
        }


    async def _log(self, message: str):
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "evidence_supervisor", message, self.websocket)
        else:
            print_agent_output(message, agent="EVIDENCE")

    async def _run_component(
            self,
            node_name: str,
            agent_name: str,
            handler,
            payload: Dict[str, Any],
    ):
        def invoke(component_input):
            return handler(**component_input)

        if self.trace_recorder is None:
            return invoke(payload)

        traced_handler = self.trace_recorder.wrap(
            node_name=node_name,
            agent_name=agent_name,
            handler=invoke,
        )
        return await traced_handler(payload)

    def _resolve_path(
            self,
            path_value: str | None,
            required: bool = False,
            field_name: str = "input_path",
    ) -> Path | None:
        if not path_value:
            if required:
                raise FileNotFoundError(
                    f"Required input path is missing: {field_name}"
                )
            return None

        path = Path(path_value)
        if not path.is_absolute():
            path = self.repo_root / path

        path = path.resolve()
        if required and not path.is_file():
            raise FileNotFoundError(
                f"Required input file does not exist: {path}"
            )

        return path

    def _load_json(
            self,
            path_value: str | None,
            required: bool = False,
    ) -> Dict[str, Any]:
        path = self._resolve_path(
            path_value,
            required=required,
            field_name="project_profile_path",
        )
        if not path or not path.exists():
            return {}

        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _load_jsonl(
            self,
            path_value: str | None,
            required: bool = False,
    ) -> List[Dict[str, Any]]:
        path = self._resolve_path(
            path_value,
            required=required,
            field_name="local_clause_path",
        )
        if not path or not path.exists():
            return []

        items = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items

    def _load_text(
            self,
            path_value: str | None,
            required: bool = False,
    ) -> str:
        path = self._resolve_path(
            path_value,
            required=required,
            field_name="project_doc_path",
        )
        if not path or not path.exists():
            return ""

        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    def _retrieve_local_clause_evidence(
            self,
            local_clause_path: Path | None,
            query: str,
            sections: List[str],
            project_profile: Dict[str, Any],
            top_k: int = 12,
        ) -> List[Dict[str, Any]]:
            if not local_clause_path or not local_clause_path.exists():
                return []

            retriever = LocalClauseRetriever(local_clause_path)
            return retriever.retrieve(
                query=query,
                sections=sections,
                project_profile=project_profile,
                top_k=top_k,
            )


    def _collect_local_clause_evidence(
            self,
            clauses: List[Dict[str, Any]],
            sections: List[str],
            project_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        evidence_items = []

        building_category = (
                project_profile.get("building", {}).get("building_category")
                or project_profile.get("building", {}).get("building_type")
                or ""
        )
        region = project_profile.get("location", {}).get("city", "")

        for index, clause in enumerate(clauses[:12], start=1):
            topics = clause.get("topic", [])
            matched_topic = " / ".join(topics) if isinstance(topics, list) else str(topics)

            confidence = 0.72
            if building_category and building_category in str(clause.get("building_type", "")):
                confidence += 0.1
            if "北京" in region and clause.get("region") in ["beijing", "national"]:
                confidence += 0.05

            evidence_items.append({
                "evidence_id": clause.get("evidence_id", f"LC-{index:03d}"),
                "channel": "local_clause",
                "source_level": clause.get("source_level", "T0_CANDIDATE"),
                "source_name": clause.get("standard_name"),
                "source_id": clause.get("standard_id"),
                "clause_no": clause.get("clause_no"),
                "page": clause.get("source_page"),
                "url": None,
                "content": clause.get("content_summary") or clause.get("clause_text") or "",
                "matched_topic": matched_topic,
                "confidence": round(min(confidence, 0.95), 2),
                "metadata": {
                    "clause_type": clause.get("clause_type"),
                    "requires_project_facts": clause.get("requires_project_facts", []),
                    "requires_calculation": clause.get("requires_calculation"),
                    "requires_manual_review": clause.get("requires_manual_review"),
                    "verification_status": clause.get("verification_status")

                }
            })

        return evidence_items

    def _collect_web_policy_evidence(
            self,
            ledger_records: List[Dict[str, Any]],
            top_k: int = 12,
    ) -> List[Dict[str, Any]]:
        """Adapt only successful scraper records; never parse LLM report text."""
        evidence_items = []
        seen_urls = set()

        for record in ledger_records or []:
            if not is_verified_record(record):
                continue
            url = record["source_url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            source_level, classification_reason, confidence = self._classify_web_source(url)
            host = (urlparse(url).hostname or "").lower()
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12].upper()
            evidence_items.append({
                "evidence_id": f"WEB-{digest}",
                "channel": "web_policy",
                "source_level": source_level,
                "source_name": host,
                "source_id": url,
                "clause_no": None,
                "page": None,
                "url": url,
                "content": record["extracted_content"][:1200],
                "matched_topic": "verified web extraction",
                "confidence": confidence,
                "metadata": {
                    "ledger_record_id": record["record_id"],
                    "content_sha256": record["content_sha256"],
                    "fetch_status": record["fetch_status"],
                    "retrieved_at": record["retrieved_at"],
                    "extractor": record["extractor"],
                    "needs_source_ranking": False,
                    "classification_reason": classification_reason,
                    "url_host": host,
                },
            })
            if len(evidence_items) >= top_k:
                return evidence_items

        return evidence_items

    def _collect_project_doc_evidence(
            self,
            project_doc: str,
            project_profile: Dict[str, Any],
            source_id: str,
    ) -> List[Dict[str, Any]]:
        if not project_doc:
            return []

        project_name = project_profile.get("project_name", "project document")

        return [
            {
                "evidence_id": "DOC-001",
                "channel": "project_doc",
                "source_level": "PROJECT",
                "source_name": project_name,
                "source_id": source_id,
                "clause_no": None,
                "page": None,
                "url": None,
                "content": project_doc[:1800],
                "matched_topic": "项目事实与资料缺口",
                "confidence": 0.75,
                "metadata": {
                    "needs_human_confirmation": True,
                    "document_type": "demo_project_document"
                }
            }
        ]

    def _build_gaps(self, project_profile: Dict[str, Any], project_doc: str) -> List[Dict[str, Any]]:
        gaps = []

        for field in project_profile.get("missing_fields", []):
            gaps.append({
                "gap_id": f"GAP-{len(gaps) + 1:03d}",
                "gap_type": "missing_project_fact",
                "description": f"项目资料缺少：{field}",
                "next_action": "human_review"
            })

        known_parameters = project_profile.get("known_parameters", {})
        for key, value in known_parameters.items():
            if value is False:
                gaps.append({
                    "gap_id": f"GAP-{len(gaps) + 1:03d}",
                    "gap_type": "missing_or_unconfirmed_parameter",
                    "description": f"项目参数未提供或未确认：{key}",
                    "next_action": "request_project_document_or_manual_review"
                })

        if not project_doc:
            gaps.append({
                "gap_id": f"GAP-{len(gaps) + 1:03d}",
                "gap_type": "missing_project_document",
                "description": "未读取到项目资料文档，无法从 project_doc channel 获取项目事实。",
                "next_action": "check_project_doc_path"
            })

        return gaps

    def _build_claims(
            self,
            evidence_items: List[Dict[str, Any]],
            gaps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        local_ids = [
                        item["evidence_id"]
                        for item in evidence_items
                        if item.get("channel") in {
                            "local_clause",
                            "greenspec_rag",
                        }
                    ][:3]

        web_items = [
            item
            for item in evidence_items
            if item.get("channel") == "web_policy"
        ]

        preferred_web_items = [
            item
            for item in web_items
            if item.get("source_level")
               in {"T1", "T2"}
        ]

        fallback_web_items = [
            item
            for item in web_items
            if item.get("source_level")
               not in {"T1", "T2"}
        ]

        ordered_web_items = (
                preferred_web_items
                + fallback_web_items
        )

        web_ids = [
            item["evidence_id"]
            for item in ordered_web_items[:2]
        ]

        doc_ids = [
                      item["evidence_id"]
                      for item in evidence_items
                      if item.get("channel") == "project_doc"
                  ][:1]

        evidence_by_id = {
            str(item.get("evidence_id")): item
            for item in evidence_items
            if item.get("evidence_id")
        }

        def evidence_spans(evidence_ids: List[str]) -> List[Dict[str, str]]:
            spans = []
            for evidence_id in evidence_ids:
                content = str(
                    evidence_by_id.get(evidence_id, {}).get("content")
                    or ""
                ).strip()
                if content:
                    spans.append(
                        {
                            "evidence_id": evidence_id,
                            "quote": content[:240],
                        }
                    )
            return spans

        claim_one_evidence = local_ids + doc_ids
        claim_two_evidence = local_ids + web_ids + doc_ids
        claim_three_evidence = doc_ids
        normative_source = (
            "GreenSpec RAG 规范证据"
            if any(item.get("channel") == "greenspec_rag" for item in evidence_items)
            else "本地条文"
        )

        return [
            {
                "claim_id": "CLAIM-001",
                "claim": "本项目可先按北京普通办公楼方案/初设阶段进行绿色建筑二星级预审，并对三星级目标做差距分析。",
                "claim_use": "precheck_conclusion",
                "required_source_levels": ["T0", "PROJECT"],
                "supporting_evidence_ids": claim_one_evidence,
                "evidence_spans": evidence_spans(claim_one_evidence),
                "status": "weakly_supported",
                "reason": (
                    "二星预审需要已核验的正式条文证据和项目事实证据；"
                    "当前仍存在计算资料和项目参数缺口。"
                ),
            },
            {
                "claim_id": "CLAIM-002",
                "claim": f"系统应结合{normative_source}、联网研究和项目资料开展绿色建筑预审分析",
                "claim_use": "methodology",
                "required_source_levels": ["T1", "T2"],
                "supporting_evidence_ids": claim_two_evidence,
                "evidence_spans": evidence_spans(claim_two_evidence),
                "status": "supported_for_demo",
                "reason": "当前 evidence_pack 已合并规范、Web 政策与项目资料三类证据。"
            },
            {
                "claim_id": "CLAIM-003",
                "claim": "当前项目存在资料缺口，不能直接给出三星级达标结论。",
                "claim_use": "project_fact",
                "required_source_levels": ["PROJECT"],
                "supporting_evidence_ids": claim_three_evidence,
                "evidence_spans": evidence_spans(claim_three_evidence),
                "status": "supported",
                "reason": f"识别到 {len(gaps)} 个资料缺口或待确认项。"
            }
        ]

    def _build_evidence_summary(self, evidence_pack: Dict[str, Any]) -> str:
        evidence_items = evidence_pack.get("evidence_items", [])
        gaps = evidence_pack.get("gaps", [])
        claims = evidence_pack.get("claims", [])

        channel_counts = {}
        for item in evidence_items:
            channel = item.get("channel", "unknown")
            channel_counts[channel] = channel_counts.get(channel, 0) + 1

        lines = [
            "## Evidence Pack Summary",
            "",
            "This section was generated by EvidenceSupervisorAgent.",
            "",
            "### Evidence Channels",
            *(f"- {channel}: {channel_counts.get(channel, 0)} items"
              for channel in ("greenspec_rag", "local_clause")
              if channel_counts.get(channel, 0)),
            f"- web_policy: {channel_counts.get('web_policy', 0)} items",
            f"- project_doc: {channel_counts.get('project_doc', 0)} items",
            "",
            "### Claims",
        ]

        for claim in claims:
            lines.append(
                f"- {claim.get('claim')} "
                f"[status: {claim.get('status')}; evidence: {', '.join(claim.get('supporting_evidence_ids', []))}]"
            )

        lines.extend([
            "",
            "### Gaps",
        ])

        for gap in gaps[:8]:
            lines.append(
                f"- {gap.get('description')} [next_action: {gap.get('next_action')}]"
            )

        lines.extend([
            "",
            "### Evidence Boundary",
            "- GreenSpec RAG items with unverified sources or incomplete applicability need manual review.",
            "- Web research items require later source ranking as T1/T2/T3.",
            "- Project document facts require human confirmation.",
        ])

        return "\n".join(lines)

    def _apply_research_retry_limit(
            self,
            evidence_verification: Dict[str, Any],
            research_again_count: int,
            max_research_again_count: int,
    ) -> Dict[str, Any]:
        decision = evidence_verification.get("decision")
        queries = (
                evidence_verification.get("research_again_queries", [])
                or []
        )

        if decision != "research_again":
            return evidence_verification

        retry_limit_reached = (
                research_again_count >= max_research_again_count
        )
        missing_queries = not queries

        if not retry_limit_reached and not missing_queries:
            return evidence_verification

        if retry_limit_reached:
            issue_code = "ISSUE_RESEARCH_RETRY_LIMIT_REACHED"
        else:
            issue_code = "ISSUE_RESEARCH_AGAIN_QUERY_MISSING"

        for item in evidence_verification.get("items", []):
            if item.get("recommended_action") != "research_again":
                continue

            item["status"] = "needs_manual_review"
            item["recommended_action"] = "revise"

            issues = item.get("issues", []) or []
            if issue_code not in issues:
                issues.append(issue_code)
            item["issues"] = issues

        evidence_verification["decision"] = "revise"
        evidence_verification["research_again_queries"] = []
        evidence_verification["summary"] = (
            self._build_verification_summary(
                evidence_verification.get("items", [])
            )
        )

        return evidence_verification


    def _build_verification_summary(
            self,
            items: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        counts = {
            "supported": 0,
            "partially_supported": 0,
            "unsupported": 0,
            "needs_manual_review": 0,
        }

        for item in items:
            status = item.get("status")
            if status in counts:
                counts[status] += 1

        return {
            "claims_total": len(items),
            "supported": counts["supported"],
            "partially_supported": counts[
                "partially_supported"
            ],
            "unsupported": counts["unsupported"],
            "needs_manual_review": counts[
                "needs_manual_review"
            ],
        }
