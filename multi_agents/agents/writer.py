from datetime import datetime
import json as standard_json
import json5 as json
from .utils.views import print_agent_output
from .utils.llms import call_model

sample_json = """
{
  "table_of_contents": A table of contents in markdown syntax (using '-') based on the research headers and subheaders,
  "introduction": An indepth introduction to the topic in markdown syntax and hyperlink references to relevant sources,
  "conclusion": A conclusion to the entire research based on all research data in markdown syntax and hyperlink references to relevant sources,
  "sources": A list with strings of all used source links in the entire research data in markdown syntax and apa citation format. For example: ['-  Title, year, Author [source url](source)', ...]
}
"""


class WriterAgent:
    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers

    def get_headers(self, research_state: dict):
        return {
            "title": research_state.get("title"),
            "date": "Date",
            "introduction": "Introduction",
            "table_of_contents": "Table of Contents",
            "conclusion": "Conclusion",
            "references": "References",
        }
    def _build_verification_instruction(
            self,
            research_state: dict,
    ) -> str:
        verification = (
            research_state.get("evidence_verification")
            or research_state.get(
                "evidence_pack",
                {},
            ).get("evidence_verification")
            or {}
        )

        if not verification:
            return ""

        verification_text = standard_json.dumps(
            verification,
            ensure_ascii=False,
            indent=2,
        )

        return f"""
    Evidence verification result:
    {verification_text}
    
    Writing requirements based on evidence verification:
    
    1. Do not present unsupported claims as established facts.
    2. For partially_supported claims, use qualified wording and state the evidence limitation.
    3. For needs_manual_review claims, explicitly state that professional human review is required.
    4. For claims whose recommended_action is revise, weaken, qualify, or remove unsupported wording.
    5. For claims whose recommended_action is research_again, do not write a definitive conclusion.
    6. Do not treat T0_CANDIDATE as verified formal evidence.
    7. Do not treat unclassified web evidence as authoritative.
    8. Do not claim final green building certification unless the evidence supports it.
    """

    def _needs_section_revision(self, research_state: dict) -> bool:
        if research_state.get("_sections_already_revised"):
            return False

        verification = (
                research_state.get("evidence_verification")
                or research_state.get("evidence_pack", {}).get(
            "evidence_verification"
        )
                or {}
        )

        decision = (
                research_state.get("verification_decision")
                or verification.get("decision")
        )

        if decision == "revise":
            return True

        return any(
            item.get("recommended_action") in {
                "revise",
                "research_again",
            }
            for item in verification.get("items", []) or []
        )

    def _normalize_sections(self, research_data: list) -> list[str]:
        sections = []

        for item in research_data or []:
            if isinstance(item, dict):
                for title, content in item.items():
                    if content is None:
                        raise ValueError(
                            f"Research section is empty: {title}"
                        )

                    sections.append(
                        f"## {title}\n\n{content}"
                    )
            elif item is not None:
                sections.append(str(item))
            else:
                raise ValueError(
                    "Research data contains an empty section"
                )

        return sections

    async def revise_research_sections(
            self,
            research_state: dict,
    ) -> list:
        research_data = (
                research_state.get("research_data", [])
                or []
        )

        if not self._needs_section_revision(
                research_state
        ):
            return research_data

        sections = self._normalize_sections(
            research_data
        )

        verification = (
                research_state.get("evidence_verification")
                or research_state.get(
            "evidence_pack", {}
        ).get("evidence_verification")
                or {}
        )

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are an evidence-aware report editor. "
                    "Revise report sections according to the "
                    "evidence verification result."
                ),
            },
            {
                "role": "user",
                "content": f"""
    Evidence verification:
    {standard_json.dumps(verification, ensure_ascii=False, indent=2)}
    
    Original report sections:
    {standard_json.dumps(sections, ensure_ascii=False, indent=2)}
    
    Requirements:
    1. Return exactly the same number of sections.
    2. Preserve Markdown headings and valid source links.
    3. Do not present unsupported claims as facts.
    4. Qualify partially_supported claims.
    5. Mark needs_manual_review conclusions as requiring professional review.
    6. Remove definitive wording for research_again claims.
    7. Preserve supported content.
    
    Return only this JSON structure:
    {{
      "research_data": [
        "revised Markdown section 1",
        "revised Markdown section 2"
      ]
    }}
    """,
            },
        ]

        task = research_state.get("task", {}) or {}

        response = await call_model(
            prompt=prompt,
            model=task.get("model"),
            response_format="json",
        )

        revised_sections = response.get(
            "research_data"
        )

        if not isinstance(revised_sections, list):
            raise ValueError(
                "Section revision response must contain "
                "a research_data list"
            )

        if len(revised_sections) != len(sections):
            raise ValueError(
                "Section revision changed section count: "
                f"expected={len(sections)}, "
                f"actual={len(revised_sections)}"
            )

        if not all(
                isinstance(section, str)
                and section.strip()
                for section in revised_sections
        ):
            raise ValueError(
                "Revised sections must be non-empty strings"
            )

        # Evidence summaries are deterministic pipeline outputs and must
        # remain byte-for-byte equivalent to the original state item.
        for index, original_item in enumerate(research_data):
            if (
                    isinstance(original_item, dict)
                    and "Evidence Pack Summary" in original_item
            ):
                revised_sections[index] = original_item

        return revised_sections

    async def write_sections(self, research_state: dict):
        query = research_state.get("title")
        data = research_state.get("research_data", []) or []
        task = research_state.get("task", {}) or {}
        follow_guidelines = task.get("follow_guidelines")
        guidelines = task.get("guidelines", [])

        verification_instruction = (
            self._build_verification_instruction(
                research_state
            )
        )

        needs_revision = self._needs_section_revision(
            research_state
        )

        if needs_revision:
            section_instruction = """
    Revise every item in research_data according to the evidence
    verification result.
    
    Requirements:
    1. Preserve the list length and item structure.
    2. Remove unsupported definitive conclusions.
    3. Qualify partially supported conclusions.
    4. Mark needs_manual_review conclusions as requiring professional review.
    5. Preserve Evidence Pack Summary items without changing their facts.
    6. Return the revised list in the research_data field.
    """
            output_format = """
    {
      "research_data": [],
      "table_of_contents": "Markdown table of contents",
      "introduction": "Markdown introduction",
      "conclusion": "Markdown conclusion",
      "sources": []
    }
    """
        else:
            section_instruction = (
                "Do not rewrite research_data."
            )
            output_format = sample_json

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a research writer. Write a report "
                    "strictly from the supplied research and "
                    "evidence verification results."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Today's date: "
                    f"{datetime.now().strftime('%d/%m/%Y')}\n"
                    f"Query or topic: {query}\n"
                    "Research data:\n"
                    f"{standard_json.dumps(data, ensure_ascii=False)}\n\n"
                    f"{verification_instruction}\n"
                    f"{section_instruction}\n"
                    f"{'Guidelines: ' + str(guidelines) if follow_guidelines else ''}\n"
                    "Return only one JSON object in this format:\n"
                    f"{output_format}"
                ),
            },
        ]

        response = await call_model(
            prompt=prompt,
            model=task.get("model"),
            response_format="json",
        )

        if needs_revision:
            revised_data = response.get("research_data")

            if not isinstance(revised_data, list):
                raise ValueError(
                    "Writer revision must return a "
                    "research_data list"
                )

            if len(revised_data) != len(data):
                raise ValueError(
                    "Writer revision changed the number "
                    "of research sections"
                )

            # Evidence summaries are deterministic outputs and
            # must not be rewritten by the LLM.
            for index, original_item in enumerate(data):
                if (
                        isinstance(original_item, dict)
                        and "Evidence Pack Summary" in original_item
                ):
                    revised_data[index] = original_item
        else:
            response["research_data"] = data

        return response

    async def revise_headers(self, task: dict, headers: dict):
        prompt = [
            {
                "role": "system",
                "content": """You are a research writer. 
Your sole purpose is to revise the headers data based on the given guidelines.""",
            },
            {
                "role": "user",
                "content": f"""Your task is to revise the given headers JSON based on the guidelines given.
You are to follow the guidelines but the values should be in simple strings, ignoring all markdown syntax.
You must return nothing but a JSON in the same format as given in headers data.
Guidelines: {task.get("guidelines")}\n
Headers Data: {headers}\n
""",
            },
        ]

        response = await call_model(
            prompt,
            task.get("model"),
            response_format="json",
        )
        return {"headers": response}

    async def run(self, research_state: dict):
        if self.websocket and self.stream_output:
            await self.stream_output(
                "logs",
                "writing_report",
                f"Writing final research report based on research data...",
                self.websocket,
            )
        else:
            print_agent_output(
                f"Writing final research report based on research data...",
                agent="WRITER",
            )

        revised_research_data = (
            await self.revise_research_sections(
                research_state
            )
        )

        working_state = {
            **research_state,
            "research_data": revised_research_data,
            "_sections_already_revised": True,
        }

        research_layout_content = await self.write_sections(
            working_state
        )

        if research_state.get("task").get("verbose"):
            if self.websocket and self.stream_output:
                research_layout_content_str = json.dumps(
                    research_layout_content, indent=2
                )
                await self.stream_output(
                    "logs",
                    "research_layout_content",
                    research_layout_content_str,
                    self.websocket,
                )
            else:
                print_agent_output(research_layout_content, agent="WRITER")

        headers = self.get_headers(research_state)
        if research_state.get("task").get("follow_guidelines"):
            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "rewriting_layout",
                    "Rewriting layout based on guidelines...",
                    self.websocket,
                )
            else:
                print_agent_output(
                    "Rewriting layout based on guidelines...", agent="WRITER"
                )
            headers = await self.revise_headers(
                task=research_state.get("task"), headers=headers
            )
            headers = headers.get("headers")

        return {**research_layout_content,
                "headers": headers,
                "research_data": revised_research_data,}
