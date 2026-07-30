import asyncio
import hashlib
import inspect
import json
import os
import time
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable


class TraceRecorder:
    """Records Agent inputs and outputs into trace.json."""

    SENSITIVE_KEY_PARTS = {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
    }

    SENSITIVE_PAYLOAD_KEYS = {
        "content",
        "draft",
        "initial_research",
        "project_doc",
        "report",
        "research_data",
    }

    def __init__(
            self,
            output_dir: str,
            run_id: str,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.output_path = self.output_dir / "trace.json"
        self.temp_path = self.output_dir / "trace.json.tmp"

        self.run_id = str(run_id)
        self.trace_id = f"TRACE-{self.run_id}"
        self.created_at = self._now()

        self.events = []
        self.sequence = 0
        self.lock = asyncio.Lock()

        self._flush()

    def wrap(
            self,
            node_name: str,
            agent_name: str,
            handler: Callable,
    ) -> Callable:
        """Wrap an async or sync LangGraph node."""

        @wraps(handler)
        async def traced_handler(state):
            event_id = await self._start_event(
                node_name=node_name,
                agent_name=agent_name,
                input_value=state,
            )

            started = time.perf_counter()

            try:
                result = handler(state)

                if inspect.isawaitable(result):
                    result = await result

            except Exception as exc:
                duration_ms = round(
                    (time.perf_counter() - started) * 1000,
                    2,
                    )

                await self._finish_event(
                    event_id=event_id,
                    status="error",
                    output_value=None,
                    duration_ms=duration_ms,
                    error=(
                        f"{type(exc).__name__}: {exc}"
                    ),
                )
                raise

            duration_ms = round(
                (time.perf_counter() - started) * 1000,
                2,
                )

            await self._finish_event(
                event_id=event_id,
                status="success",
                output_value=result,
                duration_ms=duration_ms,
                error=None,
            )

            return result

        return traced_handler

    async def _start_event(
            self,
            node_name: str,
            agent_name: str,
            input_value: Any,
    ) -> str:
        async with self.lock:
            self.sequence += 1
            event_id = f"EVT-{self.sequence:04d}"

            self.events.append(
                {
                    "event_id": event_id,
                    "sequence": self.sequence,
                    "node_name": node_name,
                    "agent_name": agent_name,
                    "status": "running",
                    "started_at": self._now(),
                    "ended_at": None,
                    "duration_ms": None,
                    "input": self._json_safe(input_value),
                    "output": None,
                    "error": None,
                }
            )

            self._flush()
            return event_id

    async def _finish_event(
            self,
            event_id: str,
            status: str,
            output_value: Any,
            duration_ms: float,
            error: str | None,
    ) -> None:
        async with self.lock:
            for event in self.events:
                if event["event_id"] != event_id:
                    continue

                event["status"] = status
                event["ended_at"] = self._now()
                event["duration_ms"] = duration_ms
                event["output"] = self._json_safe(
                    output_value
                )
                event["error"] = error
                break

            self._flush()

    def _flush(self) -> None:
        payload = {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "events": self.events,
        }

        with open(
                self.temp_path,
                "w",
                encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            self.temp_path,
            self.output_path,
        )

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(
                value,
                (str, int, float, bool),
        ):
            return value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, dict):
            result = {}

            for key, item in value.items():
                key_text = str(key)

                if self._is_sensitive_key(key_text):
                    result[key_text] = "[REDACTED]"
                elif (
                        key_text.lower()
                        in self.SENSITIVE_PAYLOAD_KEYS
                ):
                    result[key_text] = (
                        self._redacted_payload_summary(item)
                    )
                else:
                    result[key_text] = self._json_safe(
                        item
                    )

            return result

        if isinstance(value, (list, tuple, set)):
            return [
                self._json_safe(item)
                for item in value
            ]

        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return repr(value)

    def _redacted_payload_summary(
            self,
            value: Any,
    ) -> dict:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        return {
            "redacted": True,
            "value_type": type(value).__name__,
            "length": len(serialized),
            "sha256": hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest(),
        }

    def _is_sensitive_key(self, key: str) -> bool:
        normalized = key.lower()

        return any(
            part in normalized
            for part in self.SENSITIVE_KEY_PARTS
        )

    def _now(self) -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()