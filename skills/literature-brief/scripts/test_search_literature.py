#!/usr/bin/env python3
"""Offline smoke and regression tests for literature-brief helpers."""

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


def paper(source, title, doi="", abstract="", date="2026-08-20", status="unknown", pdf_url=""):
    value = MODULE.blank_paper(source)
    value.update({
        "title": title, "abstract": abstract, "first_available_date": date,
        "publication_status": status, "identifiers": {"doi": doi} if doi else {},
        "pdf_url": pdf_url,
        "evidence_level": "abstract" if abstract else "metadata",
    })
    MODULE.set_canonical_id(value)
    return value


def main():
    # 1. Topic expansion tests (including newly added topics)
    phoebe = TOPIC_MODULE.resolve_topic("土卫9表面地质")
    assert phoebe["anchor_query"] == "Phoebe Saturn"
    assert "Saturn IX" in phoebe["queries"]
    assert phoebe["sources"] == ["arxiv", "crossref"]

    diffusion = TOPIC_MODULE.resolve_topic("生成扩散模型图像生成")
    assert diffusion["matched"] is True
    assert diffusion["anchor_query"] == "diffusion model"

    mllm = TOPIC_MODULE.resolve_topic("视觉语言多模态大模型")
    assert mllm["matched"] is True
    assert mllm["anchor_query"] == "multimodal large language model"

    unknown_zh = TOPIC_MODULE.resolve_topic("某个尚未收录的专门术语")
    assert unknown_zh["needs_web_resolution"] is True
    assert unknown_zh["queries"] == []

    compound = TOPIC_MODULE.resolve_topic("天然卫星轨道演化")
    assert compound["resolution_method"] == "curated-glossary-composed"
    assert compound["anchor_query"] == "natural satellite AND orbital evolution"
    assert all("satellite" in query or "moon" in query for query in compound["queries"])
    assert all("evolution" in query or "orbit" in query for query in compound["queries"])
    assert any(query.startswith("planetary moons AND") for query in compound["queries"])

    nested = TOPIC_MODULE.resolve_topic("智能体记忆")
    assert nested["resolution_method"] == "curated-glossary"
    assert nested["anchor_query"] == "memory for language model agents"
    lstm_collision = paper(
        "crossref",
        "Long Short-Term Memory Residual Learning for Agricultural Vehicles",
        abstract="An LSTM improves localization under attitude disturbances.",
    )
    assert MODULE.sufficiently_relevant(lstm_collision, nested["queries"]) is False

    all_topics = TOPIC_MODULE.list_topics()
    assert len(all_topics) >= 50

    # 2. Normalization tests
    assert MODULE.normalize_doi("https://doi.org/10.1234/ABC.1") == "10.1234/abc.1"
    assert MODULE.normalize_arxiv("https://arxiv.org/abs/2608.12345v2") == "2608.12345"
    assert MODULE.date_windows("2026-08-01", "2026-08-29") == [("2026-08-01", "2026-08-29")]

    # 3. Deduplication & PDF preservation tests
    p1 = paper("arxiv", "Memory for Agents", "10.1234/example", "Abstract 1", status="preprint", pdf_url="https://arxiv.org/pdf/2608.12345.pdf")
    p2 = paper("crossref", "Memory for Agents", "10.1234/example", "A much longer abstract for memory agents.", status="published")
    merged = MODULE.deduplicate([p1, p2])
    assert len(merged) == 1
    assert merged[0]["publication_status"] == "published"
    assert merged[0]["pdf_url"] == "https://arxiv.org/pdf/2608.12345.pdf"
    assert merged[0]["sources"] == ["arxiv", "crossref"]

    # 4. Selection & Exclusion tests
    older_relevant = paper("arxiv", "Agent Memory Retrieval", abstract="agent memory retrieval", date="2026-08-20")
    newer_relevant = paper("arxiv", "Compact Agent Memory", abstract="agent memory", date="2026-08-28")
    unrelated = paper("crossref", "Marine Sediment Chemistry", abstract="Ocean chemistry")
    lexical_collision = paper(
        "crossref",
        "Emergency Communication over LEO Satellite Networks",
        abstract="The satellite network uses orbital infrastructure and differential evolution for optimization.",
    )
    pulsar_collision = paper(
        "crossref",
        "Orbital Variability and Evolution of a Millisecond Pulsar",
        abstract="We report the orbital evolution of a pulsar binary.",
    )
    compound_queries = TOPIC_MODULE.resolve_topic("天然卫星轨道演化")["queries"]
    assert MODULE.sufficiently_relevant(lexical_collision, compound_queries) is False
    assert MODULE.sufficiently_relevant(pulsar_collision, compound_queries) is False

    selected = MODULE.select_papers([older_relevant, newer_relevant, unrelated], ["agent memory"], 2, "latest")
    assert len(selected) == 2
    assert selected[0]["first_available_date"] == "2026-08-28"

    # Exclude newer paper
    excluded_selected = MODULE.select_papers(
        [older_relevant, newer_relevant, unrelated],
        ["agent memory"], 2, "latest",
        exclude_ids={newer_relevant["canonical_id"]}
    )
    assert len(excluded_selected) == 1
    assert excluded_selected[0]["canonical_id"] == older_relevant["canonical_id"]

    # 5. BibTeX generation test
    bib = MODULE.paper_bibtex(merged[0])
    assert "@article{" in bib
    assert "doi = {10.1234/example}" in bib
    assert "url = {https://arxiv.org/pdf/2608.12345.pdf}" in bib

    # 6. Markdown skeleton rendering test
    mock_result = {
        "topic": "智能体记忆",
        "date_from": "2026-08-01",
        "date_to": "2026-08-29",
        "retrieved_at": "2026-08-29T12:00:00+08:00",
        "sources_requested": ["arxiv", "crossref"],
        "source_health": {
            "arxiv": {"status": "success-with-results", "requests_attempted": 1, "records_returned": 5, "errors": []},
            "crossref": {"status": "success-with-results", "requests_attempted": 1, "records_returned": 20, "errors": []},
        },
        "selected": [merged[0]],
    }
    md = MODULE.render_markdown_brief(mock_result)
    assert "# 智能体记忆 研究简报" in md
    assert "来源状态" in md
    assert "今日速览" in md
    assert "PDF下载" in md
    assert "```bibtex" in md

    print("all offline tests passed successfully!")


if __name__ == "__main__":
    main()
