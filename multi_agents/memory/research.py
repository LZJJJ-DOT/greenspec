from typing import TypedDict, List, Annotated
import operator


class ResearchState(TypedDict):
    task: dict
    initial_research: str
    sections: List[str]
    research_data: List[dict]
    human_feedback: str
    # Report layout
    title: str
    headers: dict
    date: str
    table_of_contents: str
    introduction: str
    conclusion: str
    sources: List[str]
    report: str
    evidence_pack: dict
    applicability_results: List[dict]
    risk_register: List[dict]
    evidence_verification: dict
    verification_decision: str
    research_again_queries: List[str]
    research_again_count: int
    evaluation: dict
    evaluation_status: str


