#!/usr/bin/env python3
"""Search and normalize recent scholarly literature using only the Python stdlib."""

from __future__ import annotations

import argparse
import concurrent.futures
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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from topic_expansion import resolve_topic

USER_AGENT = "literature-brief/2.0.0 (+local Codex/Claude skill)"
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
    "cancer", "cell", "epidemiology", "neuroscience", "pharmacology", "vaccine",
    "immunotherapy", "antibody", "virus", "infection",
}
ARXIV_TERMS = {
    "agent", "algorithm", "artificial intelligence", "computer", "computing",
    "deep learning", "language model", "machine learning", "mathematics", "physics",
    "robot", "statistics", "transformer", "quantum", "vision", "astronomy",
    "astrophysics", "cosmology", "planetary", "satellite", "moon", "saturn",
    "neptune", "triton", "phoebe", "exoplanet", "diffusion", "mllm", "lora",
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
    cleaned = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", word.lower())
    if len(cleaned) > 4 and cleaned.endswith("ies"):
        return cleaned[:-3] + "y"
    if len(cleaned) > 3 and cleaned.endswith("es"):
        return cleaned[:-2]
    if len(cleaned) > 3 and cleaned.endswith("s") and not cleaned.endswith("ss"):
        return cleaned[:-1]
    return cleaned


def query_tokens(query: str) -> list[str]:
    raw = [normalize_word(w) for w in re.findall(r"[a-z0-9]+", query.lower())]
    filtered = [w for w in raw if w and w not in STOPWORDS]
    return filtered or raw


def relevance_score(paper: dict[str, Any], queries: list[str]) -> int:
    title_text = paper.get("title", "").lower()
    abstract_text = paper.get("abstract", "").lower()
    score = 0
    anchor_tokens = query_tokens(queries[0]) if queries else []
    for query in queries:
        tokens = query_tokens(query)
        if not tokens:
            continue
        phrase = " ".join(tokens)
        if phrase in title_text:
            score += 12
        if phrase in abstract_text:
            score += 6
        title_matches = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", title_text))
        abstract_matches = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", abstract_text))
        score += title_matches * 3 + abstract_matches
    if anchor_tokens:
        matched_anchor = sum(1 for token in anchor_tokens if re.search(rf"\b{re.escape(token)}\b", f"{title_text} {abstract_text}"))
        if matched_anchor < max(1, len(anchor_tokens) // 2):
            score -= 10
    if paper.get("evidence_level") == "abstract":
        score += 2
    if paper.get("publication_status") == "published":
        score += 1
    return score


def query_match_count(paper: dict[str, Any], query: str) -> int:
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    tokens = query_tokens(query)
    return sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", text))


def query_terms_are_close(paper: dict[str, Any], query: str) -> bool:
    tokens = query_tokens(query)
    if len(tokens) <= 1:
        return True
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    words = re.findall(r"[a-z0-9]+", text)
    positions = [i for i, w in enumerate(words) if normalize_word(w) in tokens]
    if len(positions) < 2:
        return False
    return any(positions[j + 1] - positions[j] <= 18 for j in range(len(positions) - 1))


def sufficiently_relevant(paper: dict[str, Any], queries: list[str]) -> bool:
    for query in queries:
        components = re.split(r"\s+AND\s+", query, flags=re.I)
        if len(components) > 1:
            component_matches = True
            for component in components:
                component_tokens = query_tokens(component)
                component_required = 1 if len(component_tokens) == 1 else (len(component_tokens) * 2 + 2) // 3
                if (
                    query_match_count(paper, component) < component_required
                    or not query_terms_are_close(paper, component)
                ):
                    component_matches = False
                    break
            if component_matches:
                return True
            continue
        tokens = query_tokens(query)
        if not tokens:
            continue
        phrase = " ".join(tokens)
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
        if phrase in text:
            return True
        # Two matching words are too permissive for compound topics: a paper
        # about an artificial-satellite network can otherwise pass a query for
        # natural-satellite orbital evolution. Require broader query coverage
        # as the number of meaningful terms grows.
        required = 1 if len(tokens) <= 1 else max(2, (len(tokens) * 3 + 4) // 5)
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
        except (ssl.SSLError, urllib.error.URLError, OSError) as exc:
            # On Windows with local proxies, VPNs or MITM certs, fallback to unverified SSL context
            if attempt == 0:
                context = ssl._create_unverified_context()
                continue
            raise
    raise RuntimeError("unreachable HTTP retry state")


def request_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 35) -> dict[str, Any]:
    return json.loads(request_bytes(url, headers=headers, timeout=timeout))


def blank_paper(source: str) -> dict[str, Any]:
    return {
        "canonical_id": "", "title": "", "abstract": "", "authors": [],
        "first_available_date": "", "publication_date": "", "updated_date": "",
        "publication_status": "unknown", "publication_types": [], "venue": "",
        "categories": [], "identifiers": {}, "sources": [source], "links": [],
        "pdf_url": "", "open_access_url": "",
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
    elif re.search(r"\s+AND\s+", query, flags=re.I):
        parts = re.split(r"\s+AND\s+", query, flags=re.I)
        expression = " AND ".join(f'all:"{part.replace(chr(34), " ")}"' for part in parts if part.strip())
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
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""
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
            "pdf_url": pdf_url,
            "open_access_url": link,
            "evidence_level": "abstract" if abstract else "metadata",
        })
        add_link(paper, "arxiv", link)
        if pdf_url:
            add_link(paper, "pdf", pdf_url)
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        set_canonical_id(paper)
        if paper["title"]:
            papers.append(paper)
    return papers


def search_crossref(query: str, start: str, end: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    query_for_api = re.sub(r"\s+AND\s+", " ", query, flags=re.I)
    params: dict[str, Any] = {
        "query.bibliographic": query_for_api,
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
        pdf_url = ""
        for link_item in item.get("link") or []:
            content_type = clean_text(link_item.get("content-type")).lower()
            if "application/pdf" in content_type and link_item.get("URL"):
                pdf_url = clean_text(link_item.get("URL"))
                break
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
            "pdf_url": pdf_url,
            "open_access_url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
            "evidence_level": "abstract" if abstract else "metadata",
        })
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        if pdf_url:
            add_link(paper, "pdf", pdf_url)
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
        pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/" if pmcid else ""
        oa_url = f"https://europepmc.org/article/{source}/{record_id}" if record_id and source else ""
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
            "pdf_url": pdf_url,
            "open_access_url": oa_url,
            "evidence_level": "abstract" if abstract else "metadata",
        })
        if doi:
            add_link(paper, "doi", f"https://doi.org/{doi}")
        if pmid:
            add_link(paper, "pubmed", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        if pmcid:
            add_link(paper, "pmc", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/")
        if pdf_url:
            add_link(paper, "pdf", pdf_url)
        if record_id and source:
            add_link(paper, "europe-pmc", oa_url)
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
            pdf_url = f"https://www.{server}.org/content/{doi}v1.full.pdf" if doi else ""
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
                "pdf_url": pdf_url,
                "open_access_url": f"https://doi.org/{doi}" if doi else "",
                "evidence_level": "abstract" if abstract else "metadata",
            })
            if published_doi:
                add_link(paper, "doi", f"https://doi.org/{published_doi}")
            if doi:
                add_link(paper, server, f"https://doi.org/{doi}")
            if pdf_url:
                add_link(paper, "pdf", pdf_url)
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
    merged: list[Any] = []
    for item in [*left, *right]:
        if item not in merged:
            merged.append(item)
    return merged


def merge_paper(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in ("title", "venue", "first_available_date", "publication_date", "updated_date", "pdf_url", "open_access_url"):
        if not target.get(field) and source.get(field):
            target[field] = source[field]
    if len(source.get("abstract", "")) > len(target.get("abstract", "")):
        target["abstract"] = source["abstract"]
    if source.get("evidence_level") == "abstract" and target.get("evidence_level") != "abstract":
        target["evidence_level"] = "abstract"
    if source.get("publication_status") == "published":
        target["publication_status"] = "published"
    elif target.get("publication_status") == "unknown" and source.get("publication_status"):
        target["publication_status"] = source["publication_status"]
    target["sources"] = merge_lists(target.get("sources") or [], source.get("sources") or [])
    target["categories"] = merge_lists(target.get("categories") or [], source.get("categories") or [])
    target["publication_types"] = merge_lists(target.get("publication_types") or [], source.get("publication_types") or [])
    existing_links = {(item.get("source"), item.get("url")) for item in target.get("links") or []}
    for item in source.get("links") or []:
        pair = (item.get("source"), item.get("url"))
        if pair not in existing_links:
            target.setdefault("links", []).append(item)
            existing_links.add(pair)
    ids = target.setdefault("identifiers", {})
    for key, value in (source.get("identifiers") or {}).items():
        if not ids.get(key) and value:
            ids[key] = value
    set_canonical_id(target)


def deduplicate(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    deduped: list[dict[str, Any]] = []
    for paper in papers:
        keys = paper_keys(paper)
        existing = None
        for key in keys:
            if key in by_key:
                existing = by_key[key]
                break
        if not existing:
            title = paper.get("title", "")
            for candidate in deduped:
                if title_similarity(title, candidate.get("title", "")) >= 0.88:
                    existing = candidate
                    break
        if existing:
            merge_paper(existing, paper)
            for key in keys:
                by_key[key] = existing
        else:
            deduped.append(paper)
            for key in keys:
                by_key[key] = paper
    return deduped


def title_similarity(left: str, right: str) -> float:
    t1 = set(query_tokens(left))
    t2 = set(query_tokens(right))
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def select_papers(
    papers: list[dict[str, Any]], queries: list[str], count: int, sort_policy: str = "latest",
    exclude_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    filtered = []
    for paper in papers:
        if exclude_ids:
            canonical = (paper.get("canonical_id") or "").lower()
            ids = [canonical] + [f"{k}:{v}".lower() for k, v in (paper.get("identifiers") or {}).items()]
            if any(ident in exclude_ids for ident in ids if ident):
                continue
        if sufficiently_relevant(paper, queries):
            paper["relevance_score"] = relevance_score(paper, queries)
            filtered.append(paper)
    if sort_policy == "relevance":
        filtered.sort(
            key=lambda p: (p.get("relevance_score", 0), p.get("first_available_date", ""), len(p.get("abstract", ""))),
            reverse=True,
        )
    else:
        filtered.sort(
            key=lambda p: (p.get("first_available_date", ""), p.get("relevance_score", 0), len(p.get("abstract", ""))),
            reverse=True,
        )
    selected = filtered[:count]
    for index, paper in enumerate(selected, 1):
        reason = "相关性门槛达标，在选定窗口内首次公开时间最新"
        if sort_policy == "relevance":
            reason = "主题契合度与关键词匹配得分最高"
        paper["selection_reason"] = f"第 {index} 顺位选中：{reason}（评分 {paper.get('relevance_score', 0)}）"
    return selected


def annotate_screening(candidates: list[dict[str, Any]], selected: list[dict[str, Any]], queries: list[str]) -> dict[str, Any]:
    selected_ids = {p.get("canonical_id") for p in selected}
    excluded = []
    for candidate in candidates:
        if candidate.get("canonical_id") in selected_ids:
            continue
        if not sufficiently_relevant(candidate, queries):
            reason = "主题不匹配：标题或摘要缺少足够的核心词近邻匹配"
        else:
            reason = "达到相关性门槛，但在最新时间或排序截断中落选"
        excluded.append({
            "canonical_id": candidate.get("canonical_id"),
            "title": candidate.get("title"),
            "source": (candidate.get("sources") or ["unknown"])[0],
            "first_available_date": candidate.get("first_available_date"),
            "relevance_score": candidate.get("relevance_score", 0),
            "reason": reason,
        })
    return {
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "excluded": excluded,
    }


def choose_auto_sources(topic: str) -> list[str]:
    lowered = topic.lower()
    if any(term in lowered for term in BIOMEDICAL_TERMS):
        return ["europe-pmc", "biorxiv", "medrxiv", "crossref"]
    if any(term in lowered for term in ARXIV_TERMS):
        return ["arxiv", "crossref"]
    return ["arxiv", "crossref"]


def parse_sources(value: str, topic: str) -> list[str]:
    cleaned = value.strip().lower()
    if not cleaned or cleaned == "auto":
        return choose_auto_sources(topic)
    if cleaned == "all":
        return sorted(ALL_SOURCES)
    requested = [s.strip() for s in cleaned.split(",") if s.strip()]
    invalid = [s for s in requested if s not in ALL_SOURCES]
    if invalid:
        raise ValueError(f"unknown source(s): {', '.join(invalid)}")
    return requested


def date_windows(date_from: str | None, date_to: str | None) -> list[tuple[str, str]]:
    if date_from or date_to:
        start = date_from or "1970-01-01"
        end = date_to or dt.date.today().isoformat()
        return [(start, end)]
    today = dt.date.today()
    return [
        ((today - dt.timedelta(days=7)).isoformat(), today.isoformat()),
        ((today - dt.timedelta(days=30)).isoformat(), (today - dt.timedelta(days=8)).isoformat()),
        ((today - dt.timedelta(days=90)).isoformat(), (today - dt.timedelta(days=31)).isoformat()),
    ]


def source_searcher(name: str) -> Callable[..., list[dict[str, Any]]]:
    if name == "arxiv":
        return search_arxiv
    if name == "crossref":
        return search_crossref
    if name == "europe-pmc":
        return search_europe_pmc
    if name == "biorxiv":
        return lambda q, s, e, l, t: search_biorxiv_server("biorxiv", q, s, e, l, t)
    if name == "medrxiv":
        return lambda q, s, e, l, t: search_biorxiv_server("medrxiv", q, s, e, l, t)
    raise ValueError(f"unsupported source: {name}")


def paper_bibtex(paper: dict[str, Any]) -> str:
    title = paper.get("title", "Untitled")
    authors = paper.get("authors") or ["Anonymous"]
    first_author = re.sub(r"\W+", "", authors[0].split()[-1]) if authors else "Paper"
    year = (paper.get("first_available_date") or dt.date.today().isoformat())[:4]
    first_word = re.sub(r"\W+", "", title.split()[0]) if title else "Work"
    cite_key = f"{first_author}{year}{first_word}"
    author_str = " and ".join(authors[:6])
    lines = [
        f"@article{{{cite_key},",
        f"  title = {{{title}}},",
        f"  author = {{{author_str}}},",
        f"  year = {{{year}}},",
    ]
    venue = paper.get("venue")
    if venue:
        lines.append(f"  journal = {{{venue}}},")
    doi = (paper.get("identifiers") or {}).get("doi")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    arxiv = (paper.get("identifiers") or {}).get("arxiv")
    if arxiv:
        lines.append(f"  eprint = {{{arxiv}}},")
        lines.append(f"  archivePrefix = {{arXiv}},")
    if paper.get("pdf_url"):
        lines.append(f"  url = {{{paper['pdf_url']}}},")
    elif paper.get("links"):
        lines.append(f"  url = {{{paper['links'][0]['url']}}},")
    lines.append("}")
    return "\n".join(lines)


def health_check(timeout: int = 6) -> dict[str, Any]:
    probes = {
        "arxiv": "https://export.arxiv.org/api/query?search_query=all:electron&start=0&max_results=1",
        "crossref": "https://api.crossref.org/works?query.bibliographic=electron&rows=1",
        "europe-pmc": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=electron&format=json&pageSize=1",
        "biorxiv": "https://api.biorxiv.org/details/biorxiv/2026-08-01/2026-08-02/0",
        "medrxiv": "https://api.biorxiv.org/details/medrxiv/2026-08-01/2026-08-02/0",
    }
    def probe(name: str, url: str) -> tuple[str, dict[str, Any]]:
        t0 = time.perf_counter()
        try:
            _ = request_bytes(url, timeout=timeout)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            return name, {"status": "ok", "latency_ms": elapsed, "error": None}
        except Exception as e:
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            return name, {"status": "error", "latency_ms": elapsed, "error": clean_text(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(probes)) as executor:
        completed = dict(executor.map(lambda item: probe(*item), probes.items()))
    return {name: completed[name] for name in probes}


def render_markdown_brief(result: dict[str, Any], include_bibtex: bool = True) -> str:
    topic = result.get("topic", "未知主题")
    date_from = result.get("date_from", "")
    date_to = result.get("date_to", "")
    resolution = result.get("topic_resolution") or {}
    queries = result.get("queries") or []
    retrieved_at = result.get("retrieved_at", "")
    sources = ", ".join(result.get("sources_requested") or [])
    sort_policy = "相关性降序" if result.get("sort") == "relevance" else "首次公开日期倒序"
    selected = result.get("selected") or []
    health = result.get("source_health") or {}

    lines = [
        f"# {topic} 研究简报",
        "",
        f"- **日期范围**：{date_from} 至 {date_to}",
        f"- **主题解析**：{resolution.get('input_topic', topic)} → `{resolution.get('anchor_query', queries[0] if queries else '')}`；扩展词：`{', '.join(queries[1:]) or '无'}`",
        f"- **检索来源**：{sources}",
        f"- **检索时间**：{retrieved_at}",
        f"- **排序策略**：{sort_policy}",
        "- **证据层级**：摘要级研判（零配置开放检索）",
        "",
        "## 来源状态",
        "",
        "| 来源 | 状态 | 请求数 | 返回记录 | 说明 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    status_map = {
        "success-with-results": "成功且有结果",
        "success-no-results": "成功但无结果",
        "failed": "请求失败",
    }
    for src, info in health.items():
        status_zh = status_map.get(info.get("status"), info.get("status"))
        err_msg = info.get("errors", [{}])[0].get("error", "正常") if info.get("errors") else "正常"
        lines.append(
            f"| {src} | {status_zh} | {info.get('requests_attempted', 0)} | {info.get('records_returned', 0)} | {err_msg[:40]} |"
        )

    lines.extend([
        "",
        "## 今日速览",
        "",
        "| 序号 | 标题 | 文献状态 | 日期 | PDF直达 | 入选理由 |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    if not selected:
        lines.append("| - | 未检索到符合门槛的候选文献 | - | - | - | 请扩大检索日期窗口或补充关键词 |")
    else:
        for idx, p in enumerate(selected, 1):
            title = p.get("title", "Untitled")
            status = "已发表" if p.get("publication_status") == "published" else "预印本"
            date = p.get("first_available_date") or "未知"
            pdf_link = f"[PDF下载]({p['pdf_url']})" if p.get("pdf_url") else "暂无直链"
            reason = p.get("selection_reason", "符合主题要求")
            main_url = p.get("open_access_url") or (p["links"][0]["url"] if p.get("links") else "")
            title_display = f"[{title}]({main_url})" if main_url else title
            lines.append(f"| {idx} | {title_display} | {status} | {date} | {pdf_link} | {reason} |")

    lines.extend(["", "## 重点论文研判", ""])
    for idx, p in enumerate(selected, 1):
        title = p.get("title", "Untitled")
        authors = ", ".join(p.get("authors") or []) or "未知"
        status = "已正式发表" if p.get("publication_status") == "published" else "预印本 (Preprint)"
        venue = p.get("venue") or "未收录期刊信息"
        date = p.get("first_available_date") or "未知"
        link_items = [f"[{lk['source'].upper()}]({lk['url']})" for lk in p.get("links") or []]
        links_str = " · ".join(link_items) or "无外部链接"
        pdf_badge = f" · **[直达PDF全文]({p['pdf_url']})**" if p.get("pdf_url") else ""

        lines.extend([
            f"### {idx}. {title}",
            "",
            f"- **作者**：{authors}",
            f"- **首次公开日期**：{date}",
            f"- **文献状态**：{status}",
            f"- **发表载体/分类**：{venue}",
            f"- **来源链接**：{links_str}{pdf_badge}",
            "- **分析依据**：论文摘要（Abstract-level analysis）",
            "",
            "#### 一句话结论",
            f"> 本文声称或证明了什么（根据摘要总结核心贡献）。",
            "",
            "#### 核心内容与动机",
            f"- **研究背景**：针对什么现实痛点或科学问题；",
            f"- **主要工作**：提出了何种框架、模型、机制或实验方案；",
            f"- **与主题关联**：如何体现与 `{topic}` 领域的深层协同。",
            "",
            "#### 方法与数据依据",
            f"- **实验环境/数据集**：摘要明确标注的数据与基线（若无请标“摘要未说明”）；",
            f"- **关键指标与结果**：核心性能提升幅度或关键实验结论。",
            "",
            "#### 价值判断与启发",
            "- **关注理由**：对课题研究或技术落地的借鉴意义；",
            "- **复用潜力**：可迁移的方法论、代码实现或算法思路。",
            "",
            "#### 局限性与待核验点",
            "- 摘要自述局限或需精读全文进一步确认的关键细节。",
            "",
            "> [!abstract]- 英文原始摘要",
            f"> {p.get('abstract') or '无可用摘要文本'}",
            "",
        ])
        if include_bibtex:
            lines.extend([
                "```bibtex",
                paper_bibtex(p),
                "```",
                "",
            ])

    lines.extend([
        "## 检索说明",
        "",
        f"- 检索范围覆盖 {sources}，优先抓取全文/开源直接下载链接；",
        "- 所有事实性结论均严格追溯至学术检索元数据与原始摘要，未编造未经核验的实验指标；",
        "- 本报告生成于本地对话环境，无需配置外部商业 API Key。",
        "",
    ])
    return "\n".join(lines)


def search(args: argparse.Namespace) -> dict[str, Any]:
    resolution = resolve_topic(args.topic)
    queries: list[str] = []
    if args.query:
        queries.extend(args.query)
    elif resolution.get("queries"):
        queries.extend(resolution["queries"])
    else:
        queries.append(args.topic)
    queries = list(dict.fromkeys(queries))

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

    exclude_set: set[str] = set()
    if args.exclude_ids:
        raw_val = args.exclude_ids.strip()
        path = Path(raw_val)
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                exclude_set = {line.strip().lower() for line in content.splitlines() if line.strip()}
            except Exception:
                pass
        else:
            exclude_set = {v.strip().lower() for v in raw_val.split(",") if v.strip()}

    def search_one_source(source: str, start: str, end: str) -> tuple[str, list[dict[str, Any]], list[dict[str, str]], int]:
        papers_found: list[dict[str, Any]] = []
        source_errors: list[dict[str, str]] = []
        succeeded = 0
        searcher = source_searcher(source)
        source_queries = [queries[0]] if source in {"biorxiv", "medrxiv"} else queries
        for query in source_queries:
            try:
                papers_found.extend(searcher(query, start, end, args.max_source_results, args.timeout))
                succeeded += 1
            except Exception as exc:
                source_errors.append({
                    "source": source, "window": f"{start}/{end}", "query": query,
                    "error": clean_text(exc),
                })
            if args.delay:
                time.sleep(args.delay)
        return source, papers_found, source_errors, succeeded

    for start, end in windows:
        window_sources: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as executor:
            outcomes = executor.map(lambda source: search_one_source(source, start, end), sources)
            for source, papers, source_errors, succeeded in outcomes:
                attempted = 1 if source in {"biorxiv", "medrxiv"} else len(queries)
                health[source]["requests_attempted"] += attempted
                health[source]["requests_succeeded"] += succeeded
                health[source]["records_returned"] += len(papers)
                health[source]["errors"].extend(source_errors)
                all_papers.extend(papers)
                errors.extend(source_errors)
                if succeeded:
                    successful_sources.add(source)
                    window_sources.append(source)
        normalized = deduplicate(all_papers)
        selected = select_papers(normalized, queries, args.count, args.sort, exclude_ids=exclude_set)
        searched.append({
            "from": start, "to": end, "sources_completed": window_sources,
            "candidate_count": len(normalized),
        })
        if len(selected) >= args.count or args.date_from or args.date_to:
            break

    candidates = deduplicate(all_papers)
    selected = select_papers(candidates, queries, args.count, args.sort, exclude_ids=exclude_set)
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
    final_window = {
        "from": searched[-1].get("from", "") if searched else "",
        "to": searched[0].get("to", "") if searched else "",
    }
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
        description="Search multiple scholarly sources and return normalized JSON or Markdown brief."
    )
    parser.add_argument("--topic", help="Human-readable topic label")
    parser.add_argument("--query", action="append", help="English scholarly query; first value is the topical anchor, later values are synonyms")
    parser.add_argument("--from", dest="date_from", help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=("brief", "scan"), default="brief", help="brief selects 2 papers; scan selects 8 unless --count overrides it")
    parser.add_argument("--count", type=int, help="Number of papers to select (default: 2 in brief, 8 in scan)")
    parser.add_argument("--sort", choices=("latest", "relevance"), default="latest", help="Selection order after relevance filtering (default: latest)")
    parser.add_argument("--sources", default="auto", help="auto, all, or comma-separated source names")
    parser.add_argument("--max-source-results", type=int, default=30, help="Maximum candidates requested per source/query")
    parser.add_argument("--timeout", type=int, default=35, help="Per-request timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.0, help="Optional delay between provider requests")
    parser.add_argument("--exclude-ids", help="Comma-separated IDs or path to file with seen IDs to exclude")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Output format: json or formatted markdown skeleton")
    parser.add_argument("--health-check", action="store_true", help="Perform a fast 5-source connectivity probe and exit")
    parser.add_argument("--output", help="Write output to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.health_check:
        results = health_check()
        payload = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return 0

    if not args.topic:
        parser.error("--topic is required unless --health-check is specified")

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

    if args.format == "markdown":
        payload = render_markdown_brief(result) + "\n"
    else:
        payload = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
