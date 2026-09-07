---
name: literature-brief
description: Search public scholarly sources for recent or date-bounded papers, extract open PDF links when available, and produce a traceable Chinese research brief with abstract-grounded analysis and BibTeX. Use for literature discovery, topic scans, source diagnostics, or introductions to this skill; no API key is required.
license: MIT
metadata:
  version: "2.0.0"
  status: "stable"
---

# Literature Brief

Zero-configuration scholarly search and Chinese research-brief generator.

## Introduction

When asked what this skill is or how to use it, lead with these two concise lines and adapt examples only if useful:

- 一句话介绍：Literature Brief 是一个无需 API Key 的多源学术检索助手，可查找最新论文、提取开放 PDF，并生成有证据链的中文研究简报。
- 一句话用法：调用 `$literature-brief` 并告诉我研究主题、篇数及可选日期范围，例如“检索 2 篇关于天然卫星轨道演化的最新论文”。

## Defaults

- Mode: `brief` selects 2 papers by default; `scan` selects 8.
- Date window: Default latest 7 days; widens to 30 and 90 days only if needed.
- Direct PDF first: Always include `pdf_url` (`[PDF下载](url)`) when available.
- Output destination: Return directly in conversation by default. Save to disk only when explicitly requested.
- Language: Chinese for brief prose; preserve original English titles.
- Zero credentials: Do not require API keys, accounts, or local configuration.

## Execution Workflow

1. **Resolve the topic once**:
   - Run the glossary helper from this skill directory. It composes distinct matched concepts, so topics such as “木卫二轨道共振” retain both meanings.
     ```powershell
     python scripts/topic_expansion.py --topic "<user topic>" --pretty
     ```
   - Only if `needs_web_resolution` is true or the meaning remains ambiguous, read [references/topic-resolution.md](references/topic-resolution.md), verify the term, and pass the verified English expressions with repeated `--query`.
2. **Search once**:
   - Use the deterministic Markdown skeleton for ordinary briefs. The helper searches routed sources concurrently, widens the default date window only when needed, deduplicates records, and reports partial failures.
     ```powershell
     python scripts/search_literature.py --topic "<user topic>" --format markdown
     ```
   - Respect the user's `--count`, dates, sort order, sources, or exclusions when provided. Use JSON only when candidate-level auditing is needed.
   - For a source-only diagnostic request, run:
     ```powershell
     python scripts/search_literature.py --health-check
     ```
3. **Complete the brief**:
   - Replace the analysis prompts in the Markdown skeleton using only retrieved titles, metadata, and abstracts. Do not rerun the same search merely to change prose.
   - Treat cross-disciplinary lexical matches as screening signals, not proof of relevance; exclude or explicitly flag them.
   - Label unsupported details “摘要未说明”. Do not claim peer review from DOI registration alone, and do not describe metadata-only records as abstract-level evidence.
   - Preserve direct PDF links, original abstracts, source health, and valid BibTeX. Follow [references/brief-format.md](references/brief-format.md).

If no paper clears the relevance threshold, report that outcome and suggest a wider date range or a refined query; never fill the requested count with unrelated work.
