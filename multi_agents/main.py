from pathlib import Path
from dotenv import load_dotenv
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

    if not isinstance(task, dict) or not task:
        raise ValueError(
            f"Task file must contain a "
            f"non-empty JSON object: "
            f"{task_json_path}"
        )

    required_fields = [
        "query",
        "project_profile_path",
        "local_clause_path",
        "project_doc_path",
    ]

    missing_fields = [
        field
        for field in required_fields
        if not task.get(field)
    ]

    if missing_fields:
        raise ValueError(
            "Task file is missing required fields: "
            + ", ".join(missing_fields)
        )

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
async def run_research_task(query, websocket=None, stream_output=None, tone=Tone.Objective, headers=None):
    task = open_task()
    task["query"] = query

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
