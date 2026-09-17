import html
import re
import ssl
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from text import clean, paper_key


API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "ScholarPulse/0.2 (personal academic research monitor)"
MIN_REQUEST_INTERVAL = 3.1
MAX_ATTEMPTS = 2
_last_request_at = 0.0


def tls_context(config: dict) -> ssl.SSLContext:
    tls = config.get("tls", {})
    if not tls.get("verify", True):
        return ssl._create_unverified_context()
    return ssl.create_default_context(cafile=tls.get("ca_file") or None)


def query_arxiv(query: str, count: int, context: ssl.SSLContext) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": count,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    global _last_request_at
    for attempt in range(MAX_ATTEMPTS):
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        try:
            _last_request_at = time.monotonic()
            with urllib.request.urlopen(request, timeout=20, context=context) as response:
                root = ET.fromstring(response.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS - 1:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 15.0 * (2 ** attempt)
            time.sleep(min(delay, 30.0))
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(10.0 * (2 ** attempt))

    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        link = clean(entry.findtext(f"{ATOM}id", ""))
        title = clean(entry.findtext(f"{ATOM}title", ""))
        if not link or not title:
            continue
        papers.append({
            "id": link.rstrip("/").rsplit("/", 1)[-1],
            "title": title,
            "summary": clean(entry.findtext(f"{ATOM}summary", "")),
            "link": link,
            "published": clean(entry.findtext(f"{ATOM}published", ""))[:10],
            "authors": [
                clean(author.findtext(f"{ATOM}name", ""))
                for author in entry.findall(f"{ATOM}author")
            ],
            "categories": [
                category.attrib["term"]
                for category in entry.findall(f"{ATOM}category")
                if category.attrib.get("term")
            ],
        })
    return papers


def query_rss(categories: list[str], keywords: list[str], context: ssl.SSLContext) -> list[dict]:
    """Use arXiv's official RSS feed when the search API is unavailable."""
    lowered_keywords = [keyword.casefold() for keyword in keywords]
    papers = []
    for category in categories:
        request = urllib.request.Request(
            f"https://rss.arxiv.org/rss/{urllib.parse.quote(category)}",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            root = ET.fromstring(response.read())
        for item in root.findall("./channel/item"):
            title = clean(item.findtext("title", ""))
            link = clean(item.findtext("link", ""))
            raw_summary = item.findtext("description", "")
            summary = clean(html.unescape(re.sub(r"<[^>]+>", " ", raw_summary)))
            haystack = f"{title} {summary}".casefold()
            if lowered_keywords and not any(keyword in haystack for keyword in lowered_keywords):
                continue
            identifier = link.rstrip("/").rsplit("/", 1)[-1]
            if not title or not identifier:
                continue
            creator = clean(item.findtext("{http://purl.org/dc/elements/1.1/}creator", ""))
            published = clean(item.findtext("{http://purl.org/dc/elements/1.1/}date", ""))[:10]
            if not published:
                pub_date = clean(item.findtext("pubDate", ""))
                if pub_date:
                    try:
                        published = parsedate_to_datetime(pub_date).date().isoformat()
                    except (TypeError, ValueError, OverflowError):
                        pass
            papers.append({
                "id": identifier,
                "title": title,
                "summary": summary,
                "link": link,
                "published": published,
                "authors": [creator] if creator else [],
                "categories": [category],
            })
    return papers


def submission_date_from_abs(paper: dict, context: ssl.SSLContext) -> str:
    """Resolve the original submission date; RSS only exposes announcement time."""
    request = urllib.request.Request(
        f"https://arxiv.org/abs/{urllib.parse.quote(paper['id'])}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        page = response.read().decode("utf-8", errors="replace")
    match = re.search(r"Submitted on\s+(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})", page)
    return datetime.strptime(match.group(1), "%d %b %Y").date().isoformat() if match else paper.get("published", "")


def collect_papers(direction: dict, excluded: set[str], context: ssl.SSLContext) -> list[dict]:
    limit = max(1, int(direction.get("limit", 2)))
    seen = set(excluded)
    papers = []
    successful_queries = 0

    for query in direction["queries"]:
        try:
            candidates = query_arxiv(query, max(10, limit * 6), context)
        except Exception as exc:
            print(f"warning: arXiv query failed: {query}: {exc}")
            # A 429 applies to this client/IP, so trying the remaining search
            # queries immediately only prolongs the outage. Switch to RSS.
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                break
            continue
        successful_queries += 1
        for paper in candidates:
            key = paper_key(paper["id"])
            if key in seen:
                continue
            seen.add(key)
            papers.append(paper)
            if len(papers) == limit:
                return papers

    if successful_queries == 0:
        categories = direction.get("fallback_categories", [])
        keywords = direction.get("fallback_keywords", [])
        if categories:
            try:
                candidates = query_rss(categories, keywords, context)
            except Exception as exc:
                raise RuntimeError(f"all arXiv queries and RSS fallback failed: {exc}") from exc
            for paper in candidates:
                key = paper_key(paper["id"])
                if key in seen:
                    continue
                try:
                    paper["published"] = submission_date_from_abs(paper, context)
                except Exception as exc:
                    print(f"warning: arXiv date lookup failed for {paper['id']}: {exc}")
                seen.add(key)
                papers.append(paper)
                if len(papers) == limit:
                    return papers
        if not papers:
            raise RuntimeError("all arXiv queries failed and RSS fallback found no matching papers")
    return papers
