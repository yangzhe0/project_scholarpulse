#!/usr/bin/env python3
"""Offline smoke tests for search_literature helpers."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("search_literature.py")
SPEC = importlib.util.spec_from_file_location("search_literature", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TOPIC_MODULE_PATH = Path(__file__).with_name("topic_expansion.py")
TOPIC_SPEC = importlib.util.spec_from_file_location("topic_expansion_test", TOPIC_MODULE_PATH)
assert TOPIC_SPEC and TOPIC_SPEC.loader
TOPIC_MODULE = importlib.util.module_from_spec(TOPIC_SPEC)
TOPIC_SPEC.loader.exec_module(TOPIC_MODULE)


def paper(source, title, doi="", abstract="", date="2026-08-20", status="unknown"):
    value = MODULE.blank_paper(source)
    value.update({
        "title": title, "abstract": abstract, "first_available_date": date,
        "publication_status": status, "identifiers": {"doi": doi} if doi else {},
        "evidence_level": "abstract" if abstract else "metadata",
    })
    MODULE.set_canonical_id(value)
    return value


def main():
    phoebe = TOPIC_MODULE.resolve_topic("土卫9表面地质")
    assert phoebe["anchor_query"] == "Phoebe Saturn"
    assert "Saturn IX" in phoebe["queries"]
    assert phoebe["sources"] == ["arxiv", "crossref"]

    triton = TOPIC_MODULE.resolve_topic("海卫一")
    assert triton["anchor_query"] == "Triton Neptune"
    assert triton["needs_web_resolution"] is False

    memory = TOPIC_MODULE.resolve_topic("大语言模型的智能体记忆")
    assert memory["matched_alias"] == "智能体记忆"
    assert memory["anchor_query"] == "memory for language model agents"

    unknown_zh = TOPIC_MODULE.resolve_topic("某个尚未收录的专门术语")
    assert unknown_zh["needs_web_resolution"] is True
    assert unknown_zh["queries"] == []

    english = TOPIC_MODULE.resolve_topic("graph neural networks")
    assert english["queries"] == ["graph neural networks"]
    assert english["resolution_method"] == "user-english"

    assert MODULE.normalize_doi("https://doi.org/10.1234/ABC.1") == "10.1234/abc.1"
    assert MODULE.normalize_arxiv("https://arxiv.org/abs/2608.12345v2") == "2608.12345"
    assert MODULE.date_windows("2026-08-01", "2026-08-29") == [("2026-08-01", "2026-08-29")]

    preprint = paper(
        "arxiv", "Memory Systems for Language Model Agents", "10.1234/example",
        "Short abstract", status="preprint",
    )
    published = paper(
        "crossref", "Memory Systems for Language Model Agents", "10.1234/example",
        "A longer abstract about memory systems for language model agents.", status="published",
    )
    merged = MODULE.deduplicate([preprint, published])
    assert len(merged) == 1
    assert merged[0]["publication_status"] == "published"
    assert merged[0]["sources"] == ["arxiv", "crossref"]
    assert merged[0]["abstract"].startswith("A longer")

    unrelated = paper(
        "crossref", "Marine Sediment Chemistry", abstract="Ocean chemistry measurements"
    )
    selected = MODULE.select_papers([merged[0], unrelated], ["language model agent memory"], 2)
    assert len(selected) == 1
    assert selected[0]["title"].startswith("Memory Systems")

    cancer_only = paper(
        "crossref", "New cancer treatment", abstract="A study of cancer surgery outcomes"
    )
    assert not MODULE.sufficiently_relevant(cancer_only, ["cancer immunotherapy"])

    expansion_only = paper(
        "crossref", "Language Models for Program Repair",
        abstract="Language model agents coordinate program repair through staged reasoning.",
        date="2026-08-29",
    )
    anchor_filtered = MODULE.select_papers(
        [merged[0], expansion_only],
        ["agent memory", "language model agents"],
        2,
        "latest",
    )
    assert len(anchor_filtered) == 1

    older_relevant = paper(
        "arxiv", "Agent Memory Retrieval", abstract="agent memory retrieval", date="2026-08-20"
    )
    newer_relevant = paper(
        "arxiv", "Compact Agent Memory", abstract="agent memory", date="2026-08-28"
    )
    ranked = MODULE.select_papers(
        [older_relevant, newer_relevant], ["agent memory"], 2, "latest"
    )
    assert ranked[0]["first_available_date"] == "2026-08-28"
    summary = MODULE.annotate_screening(
        [older_relevant, newer_relevant, unrelated], [newer_relevant], ["agent memory"]
    )
    assert summary["selected"] == 1
    assert older_relevant["exclusion_reason"] == "below-selection-cutoff"
    assert unrelated["exclusion_reason"] in {"no-query-signal", "anchor-topic-mismatch"}

    assert MODULE.parse_sources("auto", "clinical cancer therapy")[:3] == [
        "europe-pmc", "biorxiv", "medrxiv",
    ]
    assert MODULE.parse_sources("auto", "language model agent") == [
        "arxiv", "crossref",
    ]
    assert MODULE.parse_sources("auto", "Triton moon of Neptune") == [
        "arxiv", "crossref",
    ]
    assert "semantic-scholar" not in MODULE.ALL_SOURCES
    print("offline smoke tests passed")


if __name__ == "__main__":
    main()
