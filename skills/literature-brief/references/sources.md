# Source routing and constraints

## Supported Sources

### arXiv
- Covers: Computing, mathematics, physics, astronomy, and quantitative biology.
- Endpoint: `https://export.arxiv.org/api/query`
- Direct PDF: `https://arxiv.org/pdf/{arxiv_id}.pdf`

### Crossref
- Covers: Formal journal publications and conference proceedings across global publishers (IEEE, ACM, Springer, Nature, Elsevier, Wiley).
- Endpoint: `https://api.crossref.org/works`
- Direct PDF: Extracted from `item.link` when `application/pdf` is provided.

### Europe PMC
- Covers: Biomedical and life-science literature, PubMed records, preprints, and open-access full text.
- Endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- Direct PDF: `https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/` when `pmcid` is available.

### bioRxiv and medRxiv
- Covers: Biological and medical preprints.
- Endpoint: `https://api.biorxiv.org/details/{server}/{from}/{to}/{cursor}`
- Direct PDF: `https://www.{server}.org/content/{doi}v1.full.pdf` when `doi` is available.

## Fallback Behavior

- If a source fails, continue with results from remaining sources.
- Report any source failures in the health table.
