# Online topic resolution

Read this only when `scripts/topic_expansion.py` returns `needs_web_resolution: true`, or when a matched term remains ambiguous in the user's context.

## Required outcome

Resolve the Chinese topic into:

- one compact canonical English anchor query;
- zero to three established English synonyms, abbreviations, or historical names that improve recall;
- the research domain and appropriate zero-configuration sources;
- the authoritative pages used to verify the mapping.

## Verification process

1. Search the web for the Chinese concept plus likely English terminology. Do not rely on the model's translation alone.
2. Prefer primary, maintained authorities: IAU or NASA for astronomical names; NCBI MeSH, WHO, or a relevant standards body for biomedical terminology; original papers, standards, or official project documentation for computing and AI terms.
3. Confirm that the English term refers to the user's intended entity or concept. Check abbreviations and namesakes before adding them as queries.
4. Use the narrowest term that preserves the user's meaning as the first query. Add only synonyms that refer to the same target; broader related concepts must not become anchor queries.
5. Run the search helper with repeated `--query` values. Record the mapping, resolution method `online-authority`, and verification links in the brief.

Example for an unresolved Chinese term:

```bash
python3 scripts/search_literature.py \
  --topic "中文主题" \
  --query "verified canonical English term" \
  --query "verified synonym" \
  --count 2 \
  --pretty
```

If authoritative sources support multiple materially different meanings and the request does not disambiguate them, ask the user which meaning they intend. Do not silently choose one. Do not automatically write newly inferred mappings into the curated glossary during a literature request; glossary changes require separate review.
