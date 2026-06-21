import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from text import clean, paper_key


API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


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
        headers={"User-Agent": "ScholarPulse/0.1"},
    )
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        root = ET.fromstring(response.read())

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
        raise RuntimeError("all arXiv queries failed")
    return papers
