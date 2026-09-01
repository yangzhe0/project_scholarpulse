# Source routing and constraints

Use only the sources needed for the user's domain. Querying every provider increases latency, duplicates, and rate-limit failures without necessarily improving the brief.

## arXiv

- Best for current computing, mathematics, physics, quantitative biology, quantitative finance, statistics, economics, and related preprints.
- Search endpoint: `https://export.arxiv.org/api/query`.
- The Atom API requires no account or API key.
- Treat the base arXiv identifier as the work identifier and strip version suffixes for deduplication.
- `published` is the initial submission date; `updated` is a revision date.

Official API manual: https://info.arxiv.org/help/api/user-manual.html

## Crossref

- Best for resolving DOI metadata, journal or conference venue, publication dates, and relations between records.
- Search endpoint: `https://api.crossref.org/works`.
- Abstract coverage varies. Do not treat a record without an abstract as sufficient evidence for substantive analysis.
- The public REST API requires no sign-up or credentials. The helper uses it without user configuration.

Official REST API documentation: https://www.crossref.org/documentation/retrieve-metadata/rest-api/

## Europe PMC

- Preferred discovery source for biomedical and life-science literature, including PubMed records, preprints, abstracts, and links to some open full text.
- Search endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`.
- The helper uses the public endpoint without credentials.
- Use `FIRST_PDATE` for the first-publication date range and `resultType=core` for abstracts and richer metadata.

Official REST API documentation: https://europepmc.org/RestfulWebService

## bioRxiv and medRxiv

- Domain repositories for recent biology and medical preprints.
- Date endpoint: `https://api.biorxiv.org/details/{server}/{from}/{to}/{cursor}`.
- The public endpoints require no account or API key.
- The endpoint filters by date and category but not arbitrary full-text topic queries. The helper fetches a bounded date set and applies local title/abstract relevance filtering.
- A linked published DOI is a version relationship, not a second paper.

Official API documentation: https://api.biorxiv.org/

## Fallback behavior

- Continue when one provider fails and other providers return enough relevant evidence.
- Disclose failed providers in the search note.
- Retry a failed search at most once with a refined query or smaller source set.
- Do not scrape Google Scholar as a default fallback. Prefer stable APIs and primary publisher or repository pages.
- Do not add a source whose reliable use requires an API key, account, email address, paid plan, or environment variable. Fewer working sources are better than nominal coverage that regularly fails.
