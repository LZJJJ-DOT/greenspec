import pytest

from gpt_researcher.skills.researcher import ResearchConductor


@pytest.mark.asyncio
async def test_search_snippet_is_sent_to_scraper(monkeypatch):
    researcher = object.__new__(ResearchConductor)
    researcher.researcher = type("Parent", (), {
        "retrievers": [],
        "visited_urls": set(),
        "verbose": False,
        "add_research_sources": lambda *_: None,
    })()

    class SnippetRetriever:
        __name__ = "SnippetRetriever"

        def __init__(self, *_, **__):
            pass

        def search(self, **_):
            return [{"href": "https://example.com/policy", "body": "search snippet" * 20}]

    researcher.researcher.retrievers = [SnippetRetriever]
    researcher.researcher.cfg = type("Cfg", (), {"max_search_results_per_query": 5})()
    urls, prefetched = await researcher._search_relevant_source_urls("policy")

    assert urls == ["https://example.com/policy"]
    assert prefetched == []
