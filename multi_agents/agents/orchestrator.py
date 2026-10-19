import datetime
import uuid
from langgraph.graph import StateGraph, END

# from langgraph.checkpoint.memory import MemorySaver
from .utils.views import print_agent_output
from ..memory.research import ResearchState
from .utils.utils import sanitize_filename

# Import agent classes
from . import \
    WriterAgent, \
    EditorAgent, \
    PublisherAgent, \
    ResearchAgent, \
    HumanAgent, \
    EvidenceSupervisorAgent

from pathlib import Path
from ..observability import TraceRecorder
from ..evaluation import GreenSpecEvaluator


class ChiefEditorAgent:
    """Agent responsible for managing and coordinating editing tasks."""

    def __init__(self, task: dict, websocket=None, stream_output=None, tone=None, headers=None):
        self.task = task
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}
        self.tone = tone
        self.task_id = self._generate_task_id()
        self.output_dir = self._create_output_directory()
        self.trace_recorder = TraceRecorder(
            output_dir=self.output_dir,
            run_id=str(self.task_id),
        )

    def _generate_task_id(self):
        return uuid.uuid4().hex

    def _create_output_directory(self):
        repo_root = Path(__file__).resolve().parents[2]
        output_dir = repo_root / "outputs" / sanitize_filename(
            f"run_{self.task_id}_{self.task.get('query')[0:40]}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir)

    def _initialize_agents(self):
        editor = EditorAgent(
            self.websocket,
            self.stream_output,
            self.tone,
            self.headers,
            trace_recorder=self.trace_recorder,
        )

        return {
            "writer": WriterAgent(
                self.websocket,
                self.stream_output,
                self.headers,
            ),
            "editor": editor,
            "publisher": PublisherAgent(
                self.output_dir,
                self.websocket,
                self.stream_output,
                self.headers,
            ),
            "research": ResearchAgent(
                self.websocket,
                self.stream_output,
                self.tone,
                self.headers,
            ),
            "human": HumanAgent(
                self.websocket,
                self.stream_output,
                self.headers,
            ),
            "evidence": EvidenceSupervisorAgent(
                self.websocket,
                self.stream_output,
                self.headers,
                trace_recorder=self.trace_recorder,
            ),
        }

    def _create_workflow(self, agents):
        workflow = StateGraph(ResearchState)
        trace = self.trace_recorder.wrap

        workflow.add_node(
            "browser",
            trace(
                "browser",
                "ResearchAgent.run_initial_research",
                agents["research"].run_initial_research,
            ),
        )

        workflow.add_node(
            "planner",
            trace(
                "planner",
                "EditorAgent.plan_research",
                agents["editor"].plan_research,
            ),
        )

        workflow.add_node(
            "researcher",
            trace(
                "researcher",
                "EditorAgent.run_parallel_research",
                agents["editor"].run_parallel_research,
            ),
        )

        workflow.add_node(
            "evidence",
            trace(
                "evidence",
                "EvidenceSupervisorAgent.run",
                agents["evidence"].run,
            ),
        )

        workflow.add_node(
            "writer",
            trace(
                "writer",
                "WriterAgent.run",
                agents["writer"].run,
            ),
        )

        workflow.add_node(
            "publisher",
            trace(
                "publisher",
                "PublisherAgent.run",
                agents["publisher"].run,
            ),
        )

        workflow.add_node(
            "human",
            trace(
                "human",
                "HumanAgent.review_plan",
                agents["human"].review_plan,
            ),
        )

        self._add_workflow_edges(workflow)
        return workflow

    def _add_workflow_edges(self, workflow):
        workflow.add_edge('browser', 'planner')
        workflow.add_edge('planner', 'human')
        workflow.add_edge('researcher', 'evidence')
        workflow.add_edge('writer', 'publisher')
        workflow.set_entry_point("browser")
        workflow.add_edge('publisher', END)

        # Add human in the loop
        workflow.add_conditional_edges(
            "human",
            lambda review: (
                "accept"
                if review["human_feedback"] is None
                else "revise"
            ),
            {
                "accept": "researcher",
                "revise": "planner",
            },
        )

        workflow.add_conditional_edges(
            "evidence",
            self._route_after_evidence,
            {
                "accept": "writer",
                "revise": "writer",
                "research_again": "researcher",
            },
        )

    def init_research_team(self):
        """Initialize and create a workflow for the research team."""
        agents = self._initialize_agents()
        return self._create_workflow(agents)

    async def _log_research_start(self):
        message = f"Starting the research process for query '{self.task.get('query')}'..."
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "starting_research", message, self.websocket)
        else:
            print_agent_output(message, "MASTER")

    async def run_research_task(self):
        """
        Run a research task with the initialized research team.

        Returns:
            The result of the research task.
        """
        research_team = self.init_research_team()
        chain = research_team.compile()

        await self._log_research_start()

        config = {
            "configurable": {
                "thread_id": self.task_id,
                "thread_ts": datetime.datetime.utcnow()
            }
        }

        result = await chain.ainvoke(
            {"task": self.task},
            config=config,
        )

        repo_root = Path(__file__).resolve().parents[2]
        cases_path = (
                repo_root
                / "greenspec"
                / "evals"
                / "eval_cases.json"
        )

        evaluation = GreenSpecEvaluator(
            cases_path=cases_path
        ).evaluate(
            run_dir=self.output_dir
        )

        return {
            **result,
            "run_dir": str(Path(self.output_dir).resolve()),
            "evaluation": evaluation,
            "evaluation_status": evaluation["status"],
        }

    def _route_after_evidence(
            self,
            research_state: dict,
    ) -> str:
        decision = research_state.get(
            "verification_decision",
            "revise",
        )

        allowed_decisions = {
            "accept",
            "revise",
            "research_again",
        }

        if decision not in allowed_decisions:
            return "revise"

        return decision
