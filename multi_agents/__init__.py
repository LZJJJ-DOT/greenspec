"""Multi-agent research package with lazy public exports."""

_AGENT_EXPORTS = {
    "ResearchAgent", "WriterAgent", "PublisherAgent", "ReviserAgent",
    "ReviewerAgent", "EditorAgent", "ChiefEditorAgent",
}
_MEMORY_EXPORTS = {"DraftState", "ResearchState"}

__all__ = sorted(_AGENT_EXPORTS | _MEMORY_EXPORTS)


def __getattr__(name):
    if name in _AGENT_EXPORTS:
        from . import agents
        return getattr(agents, name)
    if name in _MEMORY_EXPORTS:
        from . import memory
        return getattr(memory, name)
    raise AttributeError(name)
