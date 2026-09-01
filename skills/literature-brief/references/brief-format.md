# Chinese research brief format

Adapt the detail to the papers; do not force empty prose. Preserve original titles and use Chinese for analysis unless requested otherwise.

```markdown
# {主题}研究简报

- **日期范围**：YYYY-MM-DD 至 YYYY-MM-DD
- **主题解析**：中文原词 → `canonical English term`；扩展词：`synonym`；方式：预存词表 / 联网核验 / 用户英文
- **检索时间**：YYYY-MM-DD HH:mm TZ
- **检索来源**：arXiv、Crossref
- **检索式**：`query one`；`query two`
- **排序规则**：相关性门槛内按首次公开日期倒序
- **分析层级**：摘要级研判

## 来源状态

| 来源 | 状态 | 返回记录 | 说明 |
| --- | --- | ---: | --- |
| arXiv | 成功且有结果 / 成功但无结果 / 失败 | 0 | ... |

## 今日速览

| 序号 | 标题 | 状态 | 日期 | 一句话结论 | 入选理由 |
| --- | --- | --- | --- | --- | --- |
| 1 | ... | 预印本 | ... | ... | ... |

## 重点论文

### 1. Original paper title

- **作者**：...
- **首次公开**：...
- **正式发表**：...（未知则省略）
- **文献状态**：预印本 / 已发表 / 未知
- **来源**：[DOI](...)、[arXiv](...)、[PubMed](...)
- **期刊/分类**：...
- **分析依据**：摘要

#### 一句话结论

用一句话说明论文真正声称或证明了什么。

#### 核心内容

- 研究问题或动机。
- 主要贡献或发现。
- 与主题的直接关系。

#### 方法与数据

- 仅写摘要明确提供的方法、数据集、样本规模、基线和指标。
- 缺失的信息写“摘要未说明”。

#### 价值判断

- 为什么值得关注。
- 可能的复用价值或影响。
- 不把推测写成论文结论。

#### 局限与待验证点

- 摘要明确承认的局限。
- 只有阅读全文才能确认的关键问题。

> [!abstract]- 英文原始摘要
> ...

## 检索说明

- 日期窗口是否扩大。
- 未收录中文主题使用了哪些权威页面核验术语；存在歧义时如何消歧。
- 哪些来源失败或未返回摘要。
- 是否合并了预印本与正式出版版本。
- 若不足请求数量，说明没有用低相关结果凑数。
```

## Writing rules

- Keep the overview scannable; detailed evidence belongs under each paper.
- Do not translate numerical results loosely. Preserve units, denominators, confidence intervals, and comparison baselines.
- Use “论文称”“摘要报告” when the result has not been independently verified.
- A DOI proves registration, not peer review. Use publication type and venue metadata, and say “已发表” rather than “已同行评审” when review status is not established.
- Omit the raw abstract when it is unavailable; do not reconstruct it.
