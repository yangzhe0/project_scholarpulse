#!/usr/bin/env python3
"""Search and normalize recent scholarly literature using only the Python stdlib."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from topic_expansion import resolve_topic

USER_AGENT = "literature-brief/1.0.0-beta (+local Codex skill)"
ALL_SOURCES = {
    "arxiv", "crossref", "europe-pmc", "biorxiv", "medrxiv",
}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "of", "on", "or", "the", "to", "using", "with", "study",
    "paper", "research", "model", "models", "method", "methods",
}
BIOMEDICAL_TERMS = {
    "biomedical", "biology", "clinical", "disease", "drug", "genome", "genomic",
    "health", "medicine", "medical", "patient", "protein", "rna", "therapy",
    "cancer", "cell", "epidemiology", "neuroscience", "pharmacology",
}
ARXIV_TERMS = {
    "agent", "algorithm", "artificial intelligence", "computer", "computing",
    "deep learning", "language model", "machine learning", "mathematics", "physics",
    "robot", "statistics", "transformer", "quantum", "vision", "astronomy",
    "astrophysics", "cosmology", "planetary", "satellite", "moon", "saturn",
    "neptune", "triton", "phoebe", "exoplanet",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    match = re.search(r"\b(\d{4})\b", text)
    return f"{match.group(1)}-01-01" if match else ""


def date_parts(value: Any) -> str:
    if isinstance(value, dict):
        parts = value.get("date-parts") or []
        value = parts[0] if parts else []
    if not isinstance(value, list) or not value:
        return ""
    try:
        year = int(value[0])
        month = int(value[1]) if len(value) > 1 else 1
        day = int(value[2]) if len(value) > 2 else 1
        return dt.date(year, month, day).isoformat()
    except (TypeError, ValueError):
        return ""


def normalize_doi(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text.rstrip(" .") if text.startswith("10.") and "/" in text else ""


def normalize_arxiv(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text, flags=re.I)
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.I)
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    return re.sub(r"v\d+$", "", text, flags=re.I).lower()


def normalized_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def normalize_word(word: str) -> str:
    word = word.lower().strip(".-")
    if len(word) > 5 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "is", "us")):
        return word[:-1]
    return word


def query_tokens(queries: list[str]) -> set[str]:
    words: set[str] = set()
    for query in queries:
        for word in re.findall(r"[a-z0-9][a-z0-9+.-]*", query.lower()):
            word = normalize_word(word)
            if len(word) > 2 and word not in STOPWORDS and word not in {"all", "abs", "ti", "cat"}:
                words.add(word)
    return words


def relevance_score(paper: dict[str, Any], queries: list[str]) -> int:
    title = clean_text(paper.get("title")).lower()
    abstract = clean_text(paper.get("abstract")).lower()
    metadata = " ".join(paper.get("categories") or []).lower()
    title_words = [normalize_word(v) for v in re.findall(r"[a-z0-9][a-z0-9+.-]*", title)]
    abstract_words = [normalize_word(v) for v in re.findall(r"[a-z0-9][a-z0-9+.-]*", abstract)]
    metadata_words = {normalize_word(v) for v in re.findall(r"[a-z0-9][a-z0-9+.-]*", metadata)}
    score = 0
    for token in query_tokens(queries):
        score += 5 * title_words.count(token)
        score += min(3, abstract_words.count(token))
        score += 2 if token in metadata_words else 0
    for query in queries:
        phrase = clean_text(re.sub(r"\b(?:and|or|not)\b", " ", query, flags=re.I)).lower()
        phrase = re.sub(r"\s+", " ", phrase).strip(' "')
        if len(phrase) >= 5:
            if phrase in title:
                score += 12
            elif phrase in abstract:
                score += 5
    return score


def query_match_count(paper: dict[str, Any], query: str) -> int:
    haystack = " ".join([
        clean_text(paper.get("title")), clean_text(paper.get("abstract")),
        " ".join(paper.get("categories") or []),
    ]).lower()
    tokens = query_tokens([query])
    words = {normalize_word(v) for v in re.findall(r"[a-z0-9][a-z0-9+.-]*", haystack)}
    return sum(1 for token in tokens if token in words)


def query_terms_are_close(paper: dict[str, Any], query: str) -> bool:
    terms = list(query_tokens([query]))
    if not terms:
        return False
    haystack = " ".join([
        clean_text(paper.get("title")), clean_text(paper.get("abstract")),
        " ".join(paper.get("categories") or []),
    ]).lower()
    words = [normalize_word(v) for v in re.findall(r"[a-z0-9][a-z0-9+.-]*", haystack)]
    if len(terms) == 1:
        return terms[0] in words
    required = len(terms) if len(terms) <= 3 else max(3, (len(terms) + 1) // 2)
    for start in range(len(words)):
        window = set(words[start : start + 13])
        if sum(1 for term in terms if term in window) >= required:
            return True
    return False


def sufficiently_relevant(paper: dict[str, Any], queries: list[str]) -> bool:
    for query in queries:
        tokens = query_tokens([query])
        required = 1 if len(tokens) <= 1 else 2
        if query_match_count(paper, query) >= required and query_terms_are_close(paper, query):
            return True
    return False


def request_bytes(url: str, *, headers: dict[str, str] | None = None, timeout: int = 35) -> bytes:
    merged = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml;q=0.9, */*;q=0.8",
    }
    if headers:
        merged.update(headers)
    context = ssl.create_default_context()
    for attempt in range(2):
        request = urllib.request.Request(url, headers=merged)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if attempt or exc.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = exc.headers.get("Retry-After", "1") if exc.headers else "1"
            try:
                delay = min(max(float(retry_after), 0.25), 2.0)
            except ValueError:
                delay = 1.0
            time.sleep(delay)
    raise RuntimeError("unreachable HTTP retry state")


def request_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 35) -> dict[str, Any]:
    return json.loads(request_bytes(url, headers=headers, timeout=timeout))


def blank_paper(source: str) -> dict[str, Any]:
    return {
        "canonical_id": "", "title": "", "abstract": "", "authors": [],
        "first_available_date": "", "publication_date": "", "updated_date": "",
        "publication_status": "unknown", "publication_types": [], "venue": "",
        "categories": [], "identifiers": {}, "sources": [source], "links": [],
        "evidence_level": "metadata", "relevance_score": 0, "selection_reason": "",
    }


def set_canonical_id(paper: dict[str, Any]) -> None:
    ids = paper.get("identifiers") or {}
    for kind in ("doi", "arxiv", "pmid", "pmcid"):
        if ids.get(kind):
            paper["canonical_id"] = f"{kind}:{str(ids[kind]).lower()}"
            return
    paper["canonical_id"] = f"title:{normalized_title(paper.get('title'))}"


def add_link(paper: dict[str, Any], source: str, url: Any) -> None:
    url = clean_text(url)
    if url and url.startswith(("http://", "https://")):
        paper["links"].append({"source": source, "url": url})


def search_arxiv(query: str, start: str, end: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    atom = "{http://www.w3.org/2005/Atom}"
    arxiv_ns = "{http://arxiv.org/schemas/atom}"
    if re.search(r"\b(?:all|ti|abs|cat):", query):
        expression = query
    else:
        expression = f'all:"{query.replace(chr(34), " ")}"'
    expression = f"({expression}) AND submittedDate:[{start.replace('-', '')}0000 TO {end.replace('-', '')}2359]"
    params = urllib.parse.urlencode({
        "search_query": expression, "start": 0, "max_results": min(limit, 100),
        "sortBy": "submittedDate", "sortOrder": "descending",
    })
    root = ET.fromstring(request_bytes(f"https://export.arxiv.org/api/query?{params}", timeout=timeout))
    papers = []
    for entry in root.findall(f"{atom}entry"):
        paper = blank_paper("arxiv")
        raw_link = clean_text(entry.findtext(f"{atom}id"))
        arxiv_id = normalize_arxiv(raw_link)
        link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else re.sub(r"^http://", "https://", raw_link)
        doi = normalize_doi(entry.findtext(f"{arxiv_ns}doi"))
        abstract = clean_text(entry.findtext(f"{atom}summary"))
        paper.update({
            "title": clean_text(entry.findtext(f"{atom}title")),
            "abstract": abstract,
            "authors": [clean_text(a.findtext(f"{atom}name")) for a in entry.findall(f"{atom}author")],
            "first_available_date": parse_date(entry.findtext(f"{atom}published")),
            "updated_date": parse_date(entry.findtext(f"{atom}updated")),
            "publication_status": "published" if doi else "preprint",
            "publication_types": ["preprint"], "venue": "arXiv",
            "categories": [c.attrib.get("term", "") for c in entry.findall(f"{atom}category") if c.attrib.get("term")],
            "identifiers": {k: v for k, v in {"arxiv": arxiv_id, "doi": doi}.items() if v},
            "evidence_level": "abstract" if abstract else "metadata",
        })
        add_link(paper, "arxiv", link)
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        set_canonical_id(paper)
        if paper["title"]:
            papers.append(paper)
    return papers


def search_crossref(query: str, start: str, end: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "query.bibliographic": query,
        "filter": f"from-pub-date:{start},until-pub-date:{end}",
        "rows": min(limit, 100), "sort": "published", "order": "desc",
    }
    data = request_json(f"https://api.crossref.org/works?{urllib.parse.urlencode(params)}", timeout=timeout)
    papers = []
    for item in ((data.get("message") or {}).get("items") or []):
        title_values = item.get("title") or []
        title = clean_text(title_values[0] if title_values else "")
        doi = normalize_doi(item.get("DOI"))
        publication_date = (
            date_parts(item.get("published-online")) or date_parts(item.get("published-print"))
            or date_parts(item.get("published")) or date_parts(item.get("issued"))
        )
        authors = []
        for author in item.get("author") or []:
            name = clean_text(" ".join(v for v in [author.get("given", ""), author.get("family", "")] if v))
            if name:
                authors.append(name)
        venue_values = item.get("container-title") or []
        abstract = clean_text(item.get("abstract"))
        crossref_type = clean_text(item.get("type"))
        is_preprint = crossref_type == "posted-content" or clean_text(item.get("subtype")).lower() == "preprint"
        paper = blank_paper("crossref")
        paper.update({
            "title": title, "abstract": abstract, "authors": authors,
            "first_available_date": publication_date,
            "publication_date": "" if is_preprint else publication_date,
            "publication_status": "preprint" if is_preprint else "published",
            "publication_types": [crossref_type] if crossref_type else [],
            "venue": clean_text(venue_values[0] if venue_values else ""),
            "categories": [clean_text(v) for v in item.get("subject") or [] if clean_text(v)],
            "identifiers": {"doi": doi} if doi else {},
            "evidence_level": "abstract" if abstract else "metadata",
        })
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        add_link(paper, "publisher", item.get("URL"))
        set_canonical_id(paper)
        if title:
            papers.append(paper)
    return papers


def search_europe_pmc(query: str, start: str, end: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    expression = f'({query}) AND FIRST_PDATE:[{start} TO {end}] sort_date:y'
    params = urllib.parse.urlencode({
        "query": expression, "format": "json", "resultType": "core", "pageSize": min(limit, 100),
    })
    data = request_json(
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}", timeout=timeout,
    )
    papers = []
    for item in ((data.get("resultList") or {}).get("result") or []):
        doi = normalize_doi(item.get("doi"))
        pmid = clean_text(item.get("pmid"))
        pmcid = clean_text(item.get("pmcid"))
        publication_date = parse_date(
            item.get("firstPublicationDate")
            or (item.get("journalInfo") or {}).get("printPublicationDate")
            or item.get("pubYear")
        )
        source = clean_text(item.get("source"))
        record_id = clean_text(item.get("id"))
        types = [clean_text(v) for v in ((item.get("pubTypeList") or {}).get("pubType") or []) if clean_text(v)]
        is_preprint = source.upper() in {"PPR", "CTX"} or any("preprint" in v.lower() for v in types)
        author_list = (item.get("authorList") or {}).get("author") or []
        authors = [clean_text(a.get("fullName")) for a in author_list if clean_text(a.get("fullName"))]
        abstract = clean_text(item.get("abstractText"))
        paper = blank_paper("europe-pmc")
        paper.update({
            "title": clean_text(item.get("title")), "abstract": abstract,
            "authors": authors or [v.strip() for v in clean_text(item.get("authorString")).split(",") if v.strip()],
            "first_available_date": publication_date,
            "publication_date": "" if is_preprint else publication_date,
            "publication_status": "preprint" if is_preprint else "published",
            "publication_types": types,
            "venue": clean_text(item.get("journalTitle") or ((item.get("journalInfo") or {}).get("journal") or {}).get("title")),
            "identifiers": {k: v for k, v in {"doi": doi, "pmid": pmid, "pmcid": pmcid}.items() if v},
            "evidence_level": "abstract" if abstract else "metadata",
        })
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        if pmid:
            add_link(paper, "pubmed", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        if pmcid:
            add_link(paper, "pmc", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/")
        if record_id and source:
            add_link(paper, "europe-pmc", f"https://europepmc.org/article/{source}/{record_id}")
        set_canonical_id(paper)
        if paper["title"]:
            papers.append(paper)
    return papers


def search_biorxiv_server(server: str, query: str, start: str, end: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    cursor = 0
    max_scan = min(max(limit * 10, 100), 300)
    while cursor < max_scan:
        data = request_json(f"https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}", timeout=timeout)
        collection = data.get("collection") or []
        if not collection:
            break
        for item in collection:
            doi = normalize_doi(item.get("doi"))
            published_doi = normalize_doi(item.get("published"))
            identifiers = {"doi": published_doi or doi}
            if published_doi and doi:
                identifiers["preprint_doi"] = doi
            abstract = clean_text(item.get("abstract"))
            paper = blank_paper(server)
            paper.update({
                "title": clean_text(item.get("title")), "abstract": abstract,
                "authors": [v.strip() for v in clean_text(item.get("authors")).split(";") if v.strip()],
                "first_available_date": parse_date(item.get("date")),
                "publication_date": "",
                "publication_status": "published" if published_doi else "preprint",
                "publication_types": ["preprint"], "venue": server,
                "categories": [clean_text(item.get("category"))] if item.get("category") else [],
                "identifiers": identifiers,
                "evidence_level": "abstract" if abstract else "metadata",
            })
            if published_doi:
                add_link(paper, "doi", f"https://doi.org/{published_doi}")
            if doi:
                add_link(paper, server, f"https://doi.org/{doi}")
            set_canonical_id(paper)
            if paper["title"] and sufficiently_relevant(paper, [query]):
                papers.append(paper)
        cursor += len(collection)
        totals = []
        for message in data.get("messages") or []:
            try:
                totals.append(int(message.get("total", 0)))
            except (TypeError, ValueError):
                pass
        total = max(totals, default=0)
        if len(collection) < 30 or (total and cursor >= total):
            break
    return papers


def paper_keys(paper: dict[str, Any]) -> list[str]:
    ids = paper.get("identifiers") or {}
    keys = []
    for kind in ("doi", "preprint_doi", "arxiv", "pmid", "pmcid"):
        if ids.get(kind):
            keys.append(f"{kind}:{str(ids[kind]).lower()}")
    title_key = normalized_title(paper.get("title"))
    if title_key:
        keys.append(f"title:{title_key}")
    return keys


def merge_lists(left: list[Any], right: list[Any]) -> list[Any]:
    result = list(left)
    seen = {json.dumps(item, sort_keys=True, ensure_ascii=False) for item in result}
    for item in right:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def merge_paper(target: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for field in ("authors", "publication_types", "categories", "sources", "links"):
        target[field] = merge_lists(target.get(field) or [], incoming.get(field) or [])
    target["identifiers"] = {**(target.get("identifiers") or {}), **(incoming.get("identifiers") or {})}
    for field in ("title", "venue"):
        if len(clean_text(incoming.get(field))) > len(clean_text(target.get(field))):
            target[field] = incoming[field]
    if len(clean_text(incoming.get("abstract"))) > len(clean_text(target.get("abstract"))):
        target["abstract"] = incoming["abstract"]
        target["evidence_level"] = incoming.get("evidence_level", "abstract")
    dates = [v for v in [target.get("first_available_date"), incoming.get("first_available_date")] if v]
    target["first_available_date"] = min(dates) if dates else ""
    publication_dates = [v for v in [target.get("publication_date"), incoming.get("publication_date")] if v]
    target["publication_date"] = min(publication_dates) if publication_dates else ""
    updated_dates = [v for v in [target.get("updated_date"), incoming.get("updated_date")] if v]
    target["updated_date"] = max(updated_dates) if updated_dates else ""
    if incoming.get("publication_status") == "published" or target.get("publication_status") == "published":
        target["publication_status"] = "published"
    elif incoming.get("publication_status") == "preprint" or target.get("publication_status") == "preprint":
        target["publication_status"] = "preprint"
    set_canonical_id(target)
    return target


def deduplicate(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    lookup: dict[str, int] = {}
    for paper in papers:
        matching = {lookup[key] for key in paper_keys(paper) if key in lookup}
        if matching:
            index = min(matching)
            merge_paper(merged[index], paper)
        else:
            index = len(merged)
            merged.append(paper)
        for key in paper_keys(merged[index]):
            lookup[key] = index
    return merged


def title_similarity(left: str, right: str) -> float:
    a = set(re.findall(r"[a-z0-9]+", left.lower())) - STOPWORDS
    b = set(re.findall(r"[a-z0-9]+", right.lower())) - STOPWORDS
    return len(a & b) / len(a | b) if a and b else 0.0


def select_papers(
    papers: list[dict[str, Any]], queries: list[str], count: int, sort_mode: str = "latest"
) -> list[dict[str, Any]]:
    for paper in papers:
        paper["relevance_score"] = relevance_score(paper, queries)
    anchor_query = queries[0]
    eligible = [
        p for p in papers
        if p["relevance_score"] > 0
        and p.get("title")
        and sufficiently_relevant(p, [anchor_query])
    ]
    if sort_mode == "relevance":
        eligible.sort(key=lambda p: (
            p["relevance_score"], 1 if p.get("abstract") else 0,
            p.get("first_available_date") or "",
        ), reverse=True)
    else:
        eligible.sort(key=lambda p: (
            p.get("first_available_date") or "", p["relevance_score"],
            1 if p.get("abstract") else 0,
        ), reverse=True)
    selected: list[dict[str, Any]] = []
    for paper in eligible:
        if sort_mode == "relevance" and any(
            title_similarity(paper["title"], other["title"]) >= 0.82 for other in selected
        ):
            continue
        topical_reason = (
            "标题和摘要直接匹配检索主题"
            if paper.get("abstract") and paper["relevance_score"] >= 8
            else "标题或元数据与检索主题匹配"
        )
        paper["selection_reason"] = (
            topical_reason if sort_mode == "relevance" else f"在主题相关结果中首次公开日期较新；{topical_reason}"
        )
        if len(paper.get("sources") or []) > 1:
            paper["selection_reason"] += f"，并由 {len(paper['sources'])} 个来源交叉收录"
        selected.append(paper)
        if len(selected) >= count:
            break
    return selected


def annotate_screening(
    papers: list[dict[str, Any]], selected: list[dict[str, Any]], queries: list[str]
) -> dict[str, int]:
    selected_ids = {paper.get("canonical_id") for paper in selected}
    selected_titles = [paper.get("title", "") for paper in selected]
    summary: dict[str, int] = {}
    for paper in papers:
        if paper.get("canonical_id") in selected_ids:
            decision = "selected"
            reason = ""
        elif not paper.get("title"):
            decision = "excluded"
            reason = "missing-title"
        elif paper.get("relevance_score", 0) <= 0:
            decision = "excluded"
            reason = "no-query-signal"
        elif not sufficiently_relevant(paper, [queries[0]]):
            decision = "excluded"
            reason = "anchor-topic-mismatch"
        elif any(title_similarity(paper["title"], title) >= 0.82 for title in selected_titles):
            decision = "excluded"
            reason = "near-duplicate-of-selected"
        else:
            decision = "excluded"
            reason = "below-selection-cutoff"
        paper["screening_decision"] = decision
        paper["exclusion_reason"] = reason
        key = "selected" if decision == "selected" else reason
        summary[key] = summary.get(key, 0) + 1
    return summary


def choose_auto_sources(topic_and_queries: str) -> list[str]:
    text = topic_and_queries.lower()
    if any(term in text for term in BIOMEDICAL_TERMS):
        return ["europe-pmc", "biorxiv", "medrxiv", "crossref"]
    if any(term in text for term in ARXIV_TERMS):
        return ["arxiv", "crossref"]
    return ["arxiv", "crossref"]


def parse_sources(raw: str, topic_and_queries: str) -> list[str]:
    if raw == "auto":
        return choose_auto_sources(topic_and_queries)
    if raw == "all":
        return sorted(ALL_SOURCES)
    sources = []
    for value in raw.split(","):
        value = value.strip().lower()
        if value and value not in sources:
            sources.append(value)
    unknown = sorted(set(sources) - ALL_SOURCES)
    if unknown:
        raise ValueError(f"unknown source(s): {', '.join(unknown)}")
    if not sources:
        raise ValueError("at least one source is required")
    return sources


def date_windows(date_from: str | None, date_to: str | None) -> list[tuple[str, str]]:
    today = dt.date.today()
    if date_from or date_to:
        end = dt.date.fromisoformat(date_to) if date_to else today
        start = dt.date.fromisoformat(date_from) if date_from else end - dt.timedelta(days=6)
        if start > end:
            raise ValueError("--from must be on or before --to")
        return [(start.isoformat(), end.isoformat())]
    return [
        ((today - dt.timedelta(days=days - 1)).isoformat(), today.isoformat())
        for days in (7, 30, 90)
    ]


def source_searcher(source: str) -> Callable[[str, str, str, int, int], list[dict[str, Any]]]:
    if source == "arxiv":
        return search_arxiv
    if source == "crossref":
        return search_crossref
    if source == "europe-pmc":
        return search_europe_pmc
    if source in {"biorxiv", "medrxiv"}:
        return lambda query, start, end, limit, timeout: search_biorxiv_server(
            source, query, start, end, limit, timeout
        )
    raise ValueError(f"unsupported source: {source}")


def search(args: argparse.Namespace) -> dict[str, Any]:
    resolution = resolve_topic(args.topic)
    if args.query:
        queries = args.query
        resolution = {
            **resolution,
            "anchor_query": queries[0],
            "queries": queries,
            "resolution_method": "explicit-queries",
            "needs_web_resolution": False,
        }
    elif resolution["needs_web_resolution"]:
        raise ValueError(
            "Chinese topic is not in the curated glossary. Resolve its canonical English "
            "term and synonyms online, then pass the verified queries with repeated --query."
        )
    else:
        queries = resolution["queries"]
    source_argument = args.sources
    if source_argument == "auto" and resolution.get("sources"):
        source_argument = ",".join(resolution["sources"])
    sources = parse_sources(source_argument, " ".join([args.topic, *queries]))
    windows = date_windows(args.date_from, args.date_to)
    all_papers: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    searched: list[dict[str, Any]] = []
    successful_sources: set[str] = set()
    health: dict[str, dict[str, Any]] = {
        source: {
            "status": "failed", "requests_attempted": 0,
            "requests_succeeded": 0, "records_returned": 0,
            "errors": [],
        }
        for source in sources
    }

    for start, end in windows:
        window_sources: list[str] = []
        for source in sources:
            searcher = source_searcher(source)
            source_queries = [queries[0]] if source in {"biorxiv", "medrxiv"} else queries
            for query in source_queries:
                health[source]["requests_attempted"] += 1
                try:
                    papers = searcher(query, start, end, args.max_source_results, args.timeout)
                    all_papers.extend(papers)
                    successful_sources.add(source)
                    health[source]["requests_succeeded"] += 1
                    health[source]["records_returned"] += len(papers)
                    if source not in window_sources:
                        window_sources.append(source)
                except Exception as exc:  # Providers fail independently by design.
                    error = {
                        "source": source, "window": f"{start}/{end}", "query": query,
                        "error": clean_text(exc),
                    }
                    errors.append(error)
                    health[source]["errors"].append(error)
                if args.delay:
                    time.sleep(args.delay)
        normalized = deduplicate(all_papers)
        selected = select_papers(normalized, queries, args.count, args.sort)
        searched.append({
            "from": start, "to": end, "sources_completed": window_sources,
            "candidate_count": len(normalized),
        })
        if len(selected) >= args.count or args.date_from or args.date_to:
            break

    candidates = deduplicate(all_papers)
    selected = select_papers(candidates, queries, args.count, args.sort)
    screening_summary = annotate_screening(candidates, selected, queries)
    if args.sort == "relevance":
        candidates.sort(
            key=lambda p: (p.get("relevance_score", 0), p.get("first_available_date", "")),
            reverse=True,
        )
    else:
        candidates.sort(
            key=lambda p: (p.get("first_available_date", ""), p.get("relevance_score", 0)),
            reverse=True,
        )
    final_window = searched[-1] if searched else {"from": "", "to": ""}
    for source_health in health.values():
        if source_health["requests_succeeded"] == 0:
            source_health["status"] = "failed"
        elif source_health["records_returned"] == 0:
            source_health["status"] = "success-no-results"
        else:
            source_health["status"] = "success-with-results"
    return {
        "topic": args.topic, "topic_resolution": resolution,
        "queries": queries, "mode": args.mode, "requested_count": args.count,
        "sort": args.sort,
        "returned_count": len(selected), "date_from": final_window.get("from", ""),
        "date_to": final_window.get("to", ""),
        "date_policy": "explicit" if args.date_from or args.date_to else "latest-7-30-90",
        "sources_requested": sources, "sources_succeeded": sorted(successful_sources),
        "source_health": health,
        "windows_searched": searched, "candidate_count": len(candidates),
        "screening_summary": screening_summary,
        "selected": selected, "candidates": candidates,
        "errors": errors,
        "retrieved_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search multiple scholarly sources and return normalized JSON."
    )
    parser.add_argument("--topic", required=True, help="Human-readable topic label")
    parser.add_argument("--query", action="append", help="English scholarly query; first value is the required topical anchor, later values are synonyms")
    parser.add_argument("--from", dest="date_from", help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=("brief", "scan"), default="brief", help="brief selects 2 papers; scan selects 8 unless --count overrides it")
    parser.add_argument("--count", type=int, help="Number of papers to select (default: 2 in brief, 8 in scan)")
    parser.add_argument("--sort", choices=("latest", "relevance"), default="latest", help="Selection order after relevance filtering (default: latest)")
    parser.add_argument("--sources", default="auto", help="auto, all, or comma-separated source names")
    parser.add_argument("--max-source-results", type=int, default=30, help="Maximum candidates requested per source/query")
    parser.add_argument("--timeout", type=int, default=35, help="Per-request timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.0, help="Optional delay between provider requests")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.count is None:
        args.count = 2 if args.mode == "brief" else 8
    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.max_source_results < args.count:
        parser.error("--max-source-results must be at least --count")
    try:
        result = search(args)
    except ValueError as exc:
        parser.error(str(exc))
    payload = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
