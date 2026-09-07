# Chinese research brief format

Adapt the detail to the papers; do not force empty prose. Preserve original titles and use Chinese for analysis unless requested otherwise.

```markdown
# {主题} 研究简报

- **日期范围**：YYYY-MM-DD 至 YYYY-MM-DD
- **主题解析**：中文原词 → `canonical English term`；扩展词：`synonym`；方式：预存词表 / 联网核验 / 用户英文
- **检索时间**：YYYY-MM-DD HH:mm TZ
- **检索来源**：arXiv、Crossref、Europe PMC 等
- **排序规则**：首次公开日期倒序 / 相关性得分降序
- **分析层级**：摘要级研判（零配置开放学术检索）

## 来源状态

| 来源 | 状态 | 请求数 | 返回记录 | 说明 |
| --- | --- | ---: | ---: | --- |
| arXiv | 成功且有结果 | 3 | 10 | 正常 |
| Crossref | 成功且有结果 | 3 | 90 | 正常 |

## 今日速览

| 序号 | 标题 | 状态 | 日期 | PDF直达 | 入选理由 |
| --- | --- | --- | --- | --- | --- |
| 1 | [Paper Title](url) | 预印本 / 已发表 | YYYY-MM-DD | [PDF下载](pdf_url) | 入选理由说明 |

## 重点论文研判

### 1. Original paper title

- **作者**：Author One, Author Two, Author Three
- **首次公开日期**：YYYY-MM-DD
- **文献状态**：预印本 (Preprint) / 已正式发表
- **发表载体/分类**：Journal Name / Category
- **来源链接**：[DOI](...) · [ARXIV](...) · **[直达PDF全文](...)**
- **分析依据**：论文摘要（Abstract-level analysis）

#### 一句话结论

> 本文声称或证明了什么（根据摘要总结核心贡献）。

#### 核心内容与动机

- **研究背景**：针对什么现实痛点或科学问题；
- **主要工作**：提出了何种框架、模型、机制或实验方案；
- **与主题关联**：如何体现与 `{主题}` 领域的深层协同。

#### 方法与数据依据

- **实验环境/数据集**：摘要明确标注的数据与基线（若无请标“摘要未说明”）；
- **关键指标与结果**：核心性能提升幅度或关键实验结论。

#### 价值判断与启发

- **关注理由**：对课题研究或技术落地的借鉴意义；
- **复用潜力**：可迁移的方法论、代码实现或算法思路。

#### 局限性与待核验点

- 摘要自述局限或需精读全文进一步确认的关键细节。

> [!abstract]- 英文原始摘要
> Original abstract text...

```bibtex
@article{CiteKey,
  title = {Paper Title},
  author = {Authors},
  year = {YYYY},
  journal = {Venue},
  doi = {10.xxx/xxx},
  url = {https://...}
}
```

## 检索说明

- 检索范围覆盖请求来源，优先抓取开放获取直接 PDF 下载链接；
- 所有事实性结论均严格追溯至学术检索元数据与原始摘要，未编造未经核验的实验指标；
- 本报告生成于本地对话环境，无需配置外部商业 API Key。
```

## Writing rules

- Keep the overview scannable; detailed evidence belongs under each paper.
- If a direct PDF download link (`pdf_url`) is available, display `[PDF下载](url)` prominently in the table and paper section.
- Do not translate numerical results loosely. Preserve units, denominators, confidence intervals, and comparison baselines.
- Use “论文称”“摘要报告” when the result has not been independently verified.
- A DOI proves registration, not peer review. Use publication type and venue metadata, and say “已发表” rather than “已同行评审” when review status is not established.
- Keep the BibTeX block valid and ready for copy-pasting into citation managers (Zotero, Mendeley, Overleaf).
