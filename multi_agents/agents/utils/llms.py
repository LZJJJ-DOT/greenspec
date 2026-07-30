import asyncio
import json_repair
from langchain_community.adapters.openai import convert_openai_messages
from langchain_core.utils.json import parse_json_markdown
from loguru import logger

from gpt_researcher.config.config import Config
from gpt_researcher.utils.llm import create_chat_completion


async def call_model(
        prompt: list,
        model: str,
        response_format: str | None = None,
        timeout_seconds: float = 300,
):
    cfg = Config()
    lc_messages = convert_openai_messages(prompt)

    try:
        response = await asyncio.wait_for(
            create_chat_completion(
                model=model,
                messages=lc_messages,
                temperature=0,
                llm_provider=cfg.smart_llm_provider,
                llm_kwargs=cfg.llm_kwargs,
            ),
            timeout=timeout_seconds,
        )

    except asyncio.TimeoutError as exc:
        message = (
            f"LLM call timed out after "
            f"{timeout_seconds} seconds: "
            f"model={model}"
        )
        logger.error(message)
        raise TimeoutError(message) from exc

    except Exception:
        logger.exception(
            f"LLM call failed: model={model}"
        )
        raise

    if not response:
        raise RuntimeError(
            f"LLM returned an empty response: "
            f"model={model}"
        )

    if response_format == "json":
        try:
            parsed = parse_json_markdown(
                response,
                parser=json_repair.loads,
            )
        except Exception as exc:
            logger.exception(
                "Failed to parse LLM response as JSON"
            )
            raise ValueError(
                "LLM response is not valid JSON"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Expected LLM JSON response "
                "to be an object"
            )

        return parsed

    return response
