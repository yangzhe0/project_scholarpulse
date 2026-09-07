#!/usr/bin/env python3
"""Resolve common Chinese research topics into verified English search queries."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
        # Drop broad aliases contained in a more specific match (for example,
        # "智能体" inside "智能体记忆"), but retain separate concepts so a
        # compound topic such as "天然卫星轨道演化" is not reduced to one half.
        specific = []
        for match in matches:
            alias_norm = normalize_topic(match[2])
            if any(
                alias_norm != normalize_topic(other[2])
                and alias_norm in normalize_topic(other[2])
                for other in matches
            ):
                continue
            specific.append(match)

        entries = []
        seen_entries: set[int] = set()
        for match in sorted(specific, key=lambda item: normalized.find(normalize_topic(item[2]))):
            entry_id = id(match[3])
            if entry_id not in seen_entries:
                entries.append((match[2], match[3]))
                seen_entries.add(entry_id)

        if len(entries) == 1:
            alias, entry = entries[0]
            queries = [entry["anchor_en"], *(entry.get("synonyms_en") or [])]
            anchor = queries[0]
            method = "curated-glossary"
            matched_alias: str | list[str] = alias
        else:
            # Combine concepts instead of issuing broad component queries. One
            # anchor plus a few synonym combinations gives useful recall while
            # preserving every part of the user's intended topic.
            term_options = [
                [entry["anchor_en"], *(entry.get("synonyms_en") or [])]
                for _, entry in entries
            ]
            zeroes = tuple(0 for _ in term_options)
            index_sets = [zeroes]
            # Diversify one concept at a time before trying Cartesian
            # combinations, so a small query budget covers synonyms from every
            # component rather than exhausting variants of only the last one.
            for component, options in enumerate(term_options):
                for variant in range(1, len(options)):
                    indices = list(zeroes)
                    indices[component] = variant
                    index_sets.append(tuple(indices))
            for indices in itertools.product(*(range(len(options)) for options in term_options)):
                if indices not in index_sets:
                    index_sets.append(indices)
            queries = []
            for indices in index_sets:
                combined = " AND ".join(options[index] for options, index in zip(term_options, indices))
                if combined not in queries:
                    queries.append(combined)
                if len(queries) == 4:
                    break
            anchor = queries[0]
            method = "curated-glossary-composed"
            matched_alias = [alias for alias, _ in entries]

        domains = list(dict.fromkeys(entry.get("domain", "general") for _, entry in entries))
        source_lists = [entry.get("sources") or [] for _, entry in entries]
        common_sources = [source for source in source_lists[0] if all(source in values for values in source_lists[1:])]
        sources = common_sources or list(dict.fromkeys(source for values in source_lists for source in values))
        return {
            "input_topic": topic,
            "matched": True,
            "matched_alias": matched_alias,
            "anchor_query": anchor,
            "queries": list(dict.fromkeys(queries)),
            "domain": domains[0] if len(domains) == 1 else "multidisciplinary",
            "sources": sources,
            "resolution_method": method,
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


def list_topics(path: Path = GLOSSARY_PATH) -> list[dict[str, Any]]:
    entries = load_glossary(path).get("entries", [])
    result = []
    for entry in entries:
        result.append({
            "domain": entry.get("domain", "general"),
            "aliases_zh": entry.get("aliases_zh", []),
            "anchor_en": entry.get("anchor_en", ""),
            "sources": entry.get("sources", []),
        })
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve a topic into English scholarly queries.")
    parser.add_argument("--topic", help="Chinese or English research topic")
    parser.add_argument("--list", action="store_true", help="List all pre-curated topics in glossary")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.list:
        topics = list_topics()
        json.dump(topics, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0
    if not args.topic:
        parser.error("--topic is required unless --list is specified")
    try:
        result = resolve_topic(args.topic)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
