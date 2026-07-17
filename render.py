import re
from pathlib import Path

from text import clean, markdown_cell


def relevance(paper: dict) -> tuple[str, str]:
    value = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
    if "model context protocol" in value or re.search(r"\bmcp\b", value):
        return "高", "MCP"
    if "rag" in value or "retrieval-augmented" in value:
        return "高", "RAG"
    if "agent" in value:
        return "高", "AI-Agent"
    return "中", "AI"


def fallback_summary(paper: dict, topic: str) -> str:
    return "\n".join([
        "#### 一句话结论", "",
        "基于 arXiv 元数据收录，具体贡献需要阅读原文后确认。", "",
        "#### 核心内容", "",
        f"- 标题显示该条目与 `{topic}` 相关。",
        "- 原始摘要已保留在下方，避免在信息不足时过度推断。",
        "- 正式引用或发布前需要核对论文全文。", "",
        "#### 方法与数据", "", "- 摘要未明确或自动摘要暂不可用。", "",
        "#### 价值判断", "",
        "- **值得关注**：作为今日主题候选文献。",
        "- **可复用点**：待从方法、数据或系统设计部分提取。",
        "- **局限/待核查**：当前仅基于 arXiv 元数据和摘要。",
    ])


def frontmatter(date: str, direction: dict, index: bool = False) -> str:
    description = direction.get("index_description", f"{direction['name']} 学术信息监测索引。") if index else direction.get("description", f"{direction['name']} 学术简报。")
    tags = direction.get("tags", [direction["name"], "学术监测"])
    lines = ["---", f"published: {date}", f"description: {description}", "tags:"]
    lines.extend(f"  - {tag}" for tag in tags)
    lines.extend([f"category: {direction.get('category', '科研')}", "---", ""])
    return "\n".join(lines)


def daily(papers: list[dict], date: str, direction: dict) -> str:
    lines = [frontmatter(date, direction), "## 今日速览", "", "| 序号 | 标题 | 来源 | 日期 | 主题 | 推荐等级 |", "| --- | --- | --- | --- | --- | --- |"]
    for number, paper in enumerate(papers, 1):
        rank, topic = relevance(paper)
        lines.append(f"| {number} | {markdown_cell(paper['title'])} | arXiv | {paper.get('published') or '未知'} | {topic} | {rank} |")

    lines.extend(["", "## 重点论文与技术动态", ""])
    for number, paper in enumerate(papers, 1):
        rank, topic = relevance(paper)
        authors = ", ".join(paper.get("authors", [])[:6]) or "未知"
        categories = ", ".join(paper.get("categories", [])) or "未知"
        lines.extend([
            f"### {number}. {paper['title']}", "",
            f"- **来源**：[arXiv]({paper['link']})",
            f"- **日期**：{paper.get('published') or '未知'}",
            f"- **作者/机构**：{authors}",
            f"- **主题标签**：`{topic}`, `arXiv`",
            f"- **推荐等级**：{rank}",
            f"- **分类**：{categories}", "",
            paper["chinese_summary"], "",
            "> [!abstract]- 摘要", f"> {paper.get('summary') or '未知'}", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def parse_daily(note: str) -> tuple[list[str], list[dict]]:
    topics = []
    for line in note.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit() and cells[4]:
            topics.append(cells[4])

    papers = []
    for match in re.finditer(r"(?ms)^###\s+\d+\.\s+(.+?)\n(.*?)(?=^###\s+\d+\.|\Z)", note):
        block = match.group(2)
        source = re.search(r"- \*\*来源\*\*：\[[^]]+\]\(([^)]+)\)", block)
        sentence = re.search(r"(?ms)^#### 一句话结论\s*(.*?)(?=^#### |^### |\Z)", block)
        papers.append({
            "title": markdown_cell(match.group(1)),
            "link": source.group(1).strip() if source else "",
            "summary": markdown_cell(sentence.group(1) if sentence else "摘要待补充。")[:180],
        })
    return list(dict.fromkeys(topics)), papers


def index(daily_dir: Path, date: str, direction: dict) -> str:
    daily_rows = []
    paper_rows = []
    latest_date = date
    for path in sorted(daily_dir.glob("*.md")):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", path.name):
            continue
        note_date = path.stem
        latest_date = max(latest_date, note_date)
        topics, papers = parse_daily(path.read_text(encoding="utf-8"))
        daily_rows.append(f"| [[{note_date}]] | {len(papers)} | {'、'.join(topics) or '暂无'} |")
        for paper in papers:
            title = f"[{paper['title']}]({paper['link']})" if paper["link"] else paper["title"]
            paper_rows.append(f"| [[{note_date}]] | {paper['summary']} | {title} |")

    lines = [
        frontmatter(latest_date, direction, index=True),
        "## 概览",
        f"当前已收录 {len(daily_rows)} 天、{len(paper_rows)} 篇去重 arXiv 条目。",
        "## 日报", "", "| 日期 | 条目数 | 主题 |", "| --- | --- | --- |", *daily_rows,
        "", "## 去重清单", "", f"当前共 {len(paper_rows)} 篇，按 arXiv ID 去重：", "",
        "| 日期 | 总结摘要 | 标题 |", "| --- | --- | --- |", *paper_rows,
    ]
    if direction.get("related_note"):
        lines.extend(["", "## 相关笔记", f"- {direction['related_note']}"])
    return "\n".join(lines).rstrip() + "\n"
