import asyncio
from pathlib import Path

from dotenv import load_dotenv

from gpt_researcher import GPTResearcher


async def main():
    load_dotenv(override=True)

    query = "What are the key technical challenges of building reliable AI Agent systems?"
    researcher = GPTResearcher(
        query=query,
        report_type="research_report",
        report_source="web",
        verbose=True,
    )

    await researcher.conduct_research()
    report = await researcher.write_report()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "day1_basic_query.md"
    output_path.write_text(report, encoding="utf-8")

    print(f"Saved report to {output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
