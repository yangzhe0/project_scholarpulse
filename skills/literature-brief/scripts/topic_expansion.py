#!/usr/bin/env python3
"""Resolve common Chinese research topics into verified English search queries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "references" / "topic-glossary.json"
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


def load_glossary(path: Path = GLOSSARY_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("entries"), list):
        raise ValueError("topic glossary must contain an entries list")
    return data


def normalize_topic(value: str) -> str:
    return re.sub(r"[\s·_—–-]+", "", value).casefold()


def contains_chinese(value: str) -> bool:
    return bool(CJK_PATTERN.search(value))


def resolve_topic(topic: str, path: Path = GLOSSARY_PATH) -> dict[str, Any]:
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")
    normalized = normalize_topic(topic)
    matches: list[tuple[int, int, str, dict[str, Any]]] = []
    for entry_index, entry in enumerate(load_glossary(path)["entries"]):
        for alias in entry.get("aliases_zh") or []:
            normalized_alias = normalize_topic(alias)
            if normalized_alias and normalized_alias in normalized:
                matches.append((len(normalized_alias), entry_index, alias, entry))
    if matches:
        _, _, alias, entry = max(matches, key=lambda item: (item[0], item[1]))
        queries = [entry["anchor_en"], *(entry.get("synonyms_en") or [])]
        return {
            "input_topic": topic,
            "matched": True,
            "matched_alias": alias,
            "anchor_query": queries[0],
            "queries": list(dict.fromkeys(queries)),
            "domain": entry.get("domain", "general"),
            "sources": entry.get("sources") or [],
            "resolution_method": "curated-glossary",
            "needs_web_resolution": False,
        }
    if contains_chinese(topic):
        return {
            "input_topic": topic,
            "matched": False,
            "matched_alias": "",
            "anchor_query": "",
            "queries": [],
            "domain": "unknown",
            "sources": [],
            "resolution_method": "unresolved",
            "needs_web_resolution": True,
        }
    return {
        "input_topic": topic,
        "matched": False,
        "matched_alias": "",
        "anchor_query": topic,
        "queries": [topic],
        "domain": "unknown",
        "sources": [],
        "resolution_method": "user-english",
        "needs_web_resolution": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve a topic into English scholarly queries.")
    parser.add_argument("--topic", required=True, help="Chinese or English research topic")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = resolve_topic(args.topic)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
