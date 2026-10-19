"""WebEvidenceLedger v1 records scraper output, never LLM-generated text."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable
from urllib.parse import urlparse


SCHEMA_VERSION = "gpt_researcher.web_evidence_ledger.v1"
MIN_CONTENT_CHARS = 100


def build_records(sources: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create deduplicated, content-addressed records from successful scrapes."""
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        content = str(source.get("raw_content") or "").strip()
        if not _is_valid_success(url, content):
            continue
        content_sha256 = _sha256(content)
        key = (url, content_sha256)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "schema_version": SCHEMA_VERSION,
            "record_id": (
                f"WEB-SRC-{_sha256(f'{url}\n{content_sha256}')[:12].upper()}"
            ),
            "source_url": url,
            "title": str(source.get("title") or "").strip(),
            "extracted_content": content,
            "content_sha256": content_sha256,
            "fetch_status": "success",
            "retrieved_at": retrieved_at,
            "extractor": "gpt_researcher_scraper",
        })
    return records


def merge_records(*ledgers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only valid records and deduplicate retries by URL plus content hash."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ledger in ledgers:
        for record in ledger or []:
            if not is_verified_record(record):
                continue
            key = (record["source_url"], record["content_sha256"])
            if key not in seen:
                seen.add(key)
                merged.append(record)
    return merged


def is_verified_record(record: Any) -> bool:
    """A record is usable only if its successful extraction is self-consistent."""
    if not isinstance(record, dict):
        return False
    if record.get("schema_version") != SCHEMA_VERSION or record.get("fetch_status") != "success":
        return False
    url = str(record.get("source_url") or "").strip()
    content = str(record.get("extracted_content") or "").strip()
    return _is_valid_success(url, content) and record.get("content_sha256") == _sha256(content)


def _is_valid_success(url: str, content: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and len(content) >= MIN_CONTENT_CHARS


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
