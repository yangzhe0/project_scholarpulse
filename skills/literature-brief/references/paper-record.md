# Normalized paper record

The search helper returns a JSON object with `selected`, all deduplicated `candidates`, `screening_summary`, `source_health`, `errors`, `windows_searched`, topic resolution, and search provenance. Each paper uses the following normalized fields.

```json
{
  "canonical_id": "doi:10.xxxx/example",
  "title": "Original paper title",
  "abstract": "Original abstract",
  "authors": ["Author One", "Author Two"],
  "first_available_date": "2026-08-20",
  "publication_date": "2026-08-27",
  "updated_date": "2026-08-27",
  "publication_status": "published",
  "publication_types": ["JournalArticle"],
  "venue": "Journal or repository",
  "categories": ["cs.AI"],
  "identifiers": {
    "doi": "10.xxxx/example",
    "arxiv": "2608.12345",
    "pmid": "12345678"
  },
  "sources": ["arxiv", "crossref"],
  "links": [
    {"source": "doi", "url": "https://doi.org/10.xxxx/example"}
  ],
  "evidence_level": "abstract",
  "relevance_score": 18,
  "selection_reason": "标题与摘要直接匹配检索主题"
}
```

Every candidate also receives `screening_decision` (`selected` or `excluded`) and an `exclusion_reason`. Deterministic reasons include `missing-title`, `no-query-signal`, `anchor-topic-mismatch`, `near-duplicate-of-selected`, and `below-selection-cutoff`. These reasons make screening auditable but do not replace agent review of borderline cases.

## Identifier priority

Use DOI, then base arXiv ID, PMID/PMCID, and finally a normalized title key. Strip DOI URL prefixes and lowercase DOI values. Strip arXiv version suffixes such as `v2`.

## Version merging

- Merge records sharing a stable identifier.
- Also merge highly similar normalized titles when author overlap supports the match.
- Preserve all `sources`, `links`, and known identifiers.
- `first_available_date` is the earliest public date across versions.
- `publication_date` is the formal publication date when known.
- Prefer the richest available abstract, not necessarily the record from the display source.
- Prefer `published` over `preprint` for display status, while retaining preprint provenance.

## Date interpretation

- `first_available_date`: earliest public appearance; use for default “latest” filtering.
- `publication_date`: online or print publication date of the formal version.
- `updated_date`: most recent revision or metadata update.

Do not silently substitute an indexing or metadata-deposit date for a publication date.

## Evidence level

- `abstract`: substantive analysis may use only title and abstract.
- `metadata`: do not make substantive method or result claims.
- `full-text`: set only after the agent actually retrieves and reads an accessible primary full text.
