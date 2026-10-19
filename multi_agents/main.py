from pathlib import Path
from dotenv import load_dotenv
from copy import deepcopy
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from multi_agents.agents import ChiefEditorAgent
import asyncio
import json
from gpt_researcher.utils.enum import Tone

# Run with LangSmith if API key is set
if os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
load_dotenv(override=True)

def validate_task(task: dict) -> dict:
    """Validate either a file-backed task or an isolated UI task."""
    if not isinstance(task, dict) or not task:
        raise ValueError("Task must be a non-empty JSON object")
    missing_fields = [field for field in ("query",) if not task.get(field)]
    if not (isinstance(task.get("project_profile"), dict) or task.get("project_profile_path")):
        missing_fields.append("project_profile or project_profile_path")
    if not (isinstance(task.get("project_doc"), str) or task.get("project_doc_path")):
        missing_fields.append("project_doc or project_doc_path")
    if not task.get("local_clause_path") and not (
        task.get("greenspec_rag_url") and task.get("greenspec_retrieve_request")
    ):
        missing_fields.append("local_clause_path or greenspec_rag_url + greenspec_retrieve_request")
    if missing_fields:
        raise ValueError("Task file is missing required fields: " + ", ".join(missing_fields))
    return task


def open_task():
    repo_root = Path(__file__).resolve().parents[1]

    configured_path = os.environ.get(
        "GREENSPEC_TASK_PATH"
    )

    if configured_path:
        task_json_path = Path(configured_path)

        if not task_json_path.is_absolute():
            task_json_path = (
                    repo_root / task_json_path
            )
    else:
        task_json_path = (
                Path(__file__).resolve().parent
                / "task.json"
        )

    task_json_path = task_json_path.resolve()

    if not task_json_path.exists():
        raise FileNotFoundError(
            f"Task file does not exist: "
            f"{task_json_path}"
        )

    with open(
            task_json_path,
            "r",
            encoding="utf-8-sig",
    ) as file:
        task = json.load(file)

    validate_task(task)

    strategic_llm = os.environ.get(
        "STRATEGIC_LLM"
    )

    if strategic_llm:
        task["model"] = (
            strategic_llm.split(":", 1)[1]
            if ":" in strategic_llm
            else strategic_llm
        )

    return task
async def run_research_task(query, websocket=None, stream_output=None, tone=Tone.Objective, headers=None, task_override=None):
    task = deepcopy(task_override) if task_override is not None else open_task()
    task["query"] = query
    if isinstance(task.get("greenspec_retrieve_request"), dict):
        task["greenspec_retrieve_request"]["query"] = query
    validate_task(task)

    chief_editor = ChiefEditorAgent(task, websocket, stream_output, tone, headers)
    research_report = await chief_editor.run_research_task()

    if websocket and stream_output:
        await stream_output("logs", "research_report", research_report, websocket)

    return research_report

async def main():
    task = open_task()

    chief_editor = ChiefEditorAgent(task)
    research_report = await chief_editor.run_research_task()

    return research_report

if __name__ == "__main__":
    asyncio.run(main())
