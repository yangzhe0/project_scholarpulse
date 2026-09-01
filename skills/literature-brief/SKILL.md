---
name: literature-brief
description: Search no-configuration scholarly sources for recent papers on a user-specified topic and produce a concise, traceable Chinese research brief. Use for requests to find the latest or date-bounded academic literature, select a small number of relevant papers, compare preprints with published versions, or turn search results into a ScholarPulse-style brief. Do not use for exhaustive systematic reviews, citation-network studies, or a deep review of a paper the user has already supplied.
license: MIT
metadata:
  version: "1.0.0-beta"
  status: "beta"
---

# Literature Brief

Produce a useful research brief, not merely a list of search results. Preserve the user's topic and constraints while making every factual claim traceable to retrieved metadata or text.

## Defaults

- Require a topic. Infer it from the request when clear; ask only if no meaningful topic can be determined.
- Use `brief` mode and select 2 papers unless the user requests another number. Use `scan` mode for an exploratory 5–10-paper overview; its default is 8. Do not present either mode as a systematic review.
- When no date is supplied, search the latest 7 days, then widen to 30 and 90 days only if there are too few relevant papers.
- Treat a supplied date range as inclusive and do not silently widen it.
- Use abstract-level analysis by default. Read full text only when the user requests it or the abstract is inadequate and an accessible primary copy is available.
- Return the brief in the conversation. Save Markdown or JSON only when the user requests a file or supplies an output path.
- Write the brief in Chinese unless the user requests another language. Preserve original paper titles.
- Require no API keys, accounts, email addresses, environment variables, or local configuration.

## Search

1. Resolve the topic before searching:
   - Run `python3 scripts/topic_expansion.py --topic "<user topic>" --pretty`.
   - If the curated glossary matches, use its English anchor, synonyms, and source routing. The main search helper does this automatically when `--query` is omitted.
   - If a Chinese topic is unresolved or ambiguous, do not guess its translation. Read [references/topic-resolution.md](references/topic-resolution.md), verify the canonical English term and useful synonyms online, then pass them as repeated `--query` values. Put the compact topical anchor first; a candidate must match it to qualify.
   - English topics may be searched directly. Treat user-supplied queries as authoritative unless they are clearly malformed or ambiguous.
2. Choose sources by domain:
   - Computing, mathematics, physics, astronomy, and AI: arXiv and Crossref.
   - Medicine and life sciences: Europe PMC, bioRxiv, medRxiv, and Crossref.
   - General or interdisciplinary topics: arXiv and Crossref, adding a domain repository when appropriate.
   - Honor explicit source, peer-review, preprint, and open-access constraints.
3. Run `scripts/search_literature.py`. For a glossary-covered topic, `--topic` alone is sufficient. For an online-resolved topic, pass the verified core term as the first `--query`, then repeat `--query` for meaningful synonyms. Use `--sources` only when overriding automatic routing. The script normalizes metadata, merges cross-source duplicates, ranks candidates, and returns topic-resolution provenance plus search results. It defaults to `--sort latest`; use `--sort relevance` only when the user asks for the most relevant or representative work rather than the newest work.
4. Inspect `source_health`, `errors`, `windows_searched`, `screening_summary`, and `selected`. Distinguish `success-with-results`, `success-no-results`, and `failed`; never describe a failed source as having no papers. A partial source failure is acceptable when other sources provide enough evidence; disclose material gaps. If results are weak, refine the query once. Do not keep widening or retrying indefinitely.

Example:

```bash
python3 scripts/search_literature.py \
  --topic "智能体记忆" \
  --mode brief \
  --count 2 \
  --pretty
```

Read [references/sources.md](references/sources.md) when choosing or troubleshooting sources. Read [references/paper-record.md](references/paper-record.md) when interpreting normalized fields, dates, versions, or duplicate records.

## Select and analyze

- First exclude papers that do not directly match the topic. Among qualifying papers, prefer first-available date by default, then relevance and evidence completeness. Use relevance-first ranking only when the user asks for it.
- Do not use citation count as a primary ranking signal for recent work.
- Do not fill the requested quota with weakly related papers. Report the actual count when fewer papers meet the bar.
- Preserve the helper's candidate records and deterministic exclusion reasons in saved JSON when the user requests an artifact. These are an audit trail, not a substitute for semantic judgment; review borderline exclusions before finalizing a scan.
- Treat a preprint and its journal version as versions of one work. Prefer the published record for display while retaining the preprint link and first-available date.
- Distinguish `preprint`, `published`, and `unknown` status. Do not infer peer review merely from a DOI.
- Base method, dataset, result, and limitation claims only on retrieved abstracts or full text. Label missing details as “摘要未说明”; never manufacture them.
- Describe an abstract-only assessment as “摘要级研判.”

## Write the brief

Follow [references/brief-format.md](references/brief-format.md). Include:

- Topic resolution (original topic, canonical English anchor, synonyms, and glossary/online method), inclusive date range, sources searched, actual queries, retrieval time, ranking policy, and evidence level.
- A compact overview table with the selected papers and why each was selected.
- For each paper: bibliographic metadata, publication status, source links, one-sentence conclusion, core content, methods/data, value, limitations or verification needs, and the original abstract in a collapsed block when Markdown supports it.
- A short search note when sources failed, the date window widened, fewer papers qualified, or versions were merged.
- A compact source-health table showing each requested source's three-state status and returned-record count.

Use direct primary links such as DOI, repository, PubMed, or publisher pages. Keep source provenance visible and avoid presenting aggregator metadata as full-text verification.
