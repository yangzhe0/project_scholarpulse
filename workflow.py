import json
from pathlib import Path

from arxiv import collect_papers, tls_context
from ollama import summarize
from render import daily, fallback_summary, index, parse_daily, relevance
from storage import known_ids, write


def run(config: dict, date: str, force: bool = False, selected: str | None = None) -> int:
    context = tls_context(config)
    directions = config["directions"]
    if selected:
        directions = [item for item in directions if item["name"] == selected]
        if not directions:
            print(f"error: unknown direction: {selected}")
            return 2

    exit_code = 0
    reports = []
    errors = []
    for direction in directions:
        daily_dir = Path(direction["daily_dir"])
        index_file = Path(direction["index_file"])
        daily_file = daily_dir / f"{date}.md"
        if daily_file.exists() and not force:
            if not index_file.exists():
                write(index_file, index(daily_dir, date, direction))
                print(f"indexed: {index_file}")
            reports.append(_report(direction, daily_file, "existing"))
            print(f"exists: {daily_file}")
            continue

        try:
            papers = collect_papers(direction, known_ids(daily_dir, index_file), context)
        except Exception as exc:
            print(f"error: {direction['name']}: {exc}")
            errors.append({"direction": direction["name"], "error": str(exc)})
            exit_code = 1
            continue
        if not papers:
            print(f"no new papers: {direction['name']}")
            errors.append({"direction": direction["name"], "error": "no new papers"})
            continue

        for paper in papers:
            _, topic = relevance(paper)
            try:
                paper["chinese_summary"] = summarize(paper, direction, config)
            except Exception as exc:
                print(f"warning: Ollama summary failed for {paper['id']}: {exc}")
                paper["chinese_summary"] = fallback_summary(paper, topic)

        write(daily_file, daily(papers, date, direction))
        write(index_file, index(daily_dir, date, direction))
        reports.append(_report(direction, daily_file, "generated"))
        print(f"saved: {daily_file}")
        print(f"indexed: {index_file}")

    result_dir = config.get("result_dir")
    if result_dir:
        payload = {
            "date": date,
            "reports": reports,
            "errors": errors,
            "message": _message(date, reports, errors),
        }
        result_file = Path(result_dir) / f"{date}.json"
        write(result_file, json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"result: {result_file}")
    return exit_code


def _report(direction: dict, daily_file: Path, status: str) -> dict:
    topics, papers = parse_daily(daily_file.read_text(encoding="utf-8"))
    knowledge_dir = direction.get("knowledge_dir")
    note = f"{knowledge_dir.rstrip('/')}/{daily_file.name}" if knowledge_dir else str(daily_file)
    return {
        "direction": direction["name"],
        "status": status,
        "note": note,
        "topics": topics,
        "papers": papers,
    }


def _message(date: str, reports: list[dict], errors: list[dict]) -> str:
    lines = [f"ScholarPulse {date} 已更新"]
    for report in reports:
        papers = report["papers"]
        lines.extend(["", f"{report['direction']}：收录 {len(papers)} 篇"])
        for number, paper in enumerate(papers, 1):
            lines.extend(["", f"{number}. {paper['title']}", paper["summary"]])
        lines.extend(["", f"知识库：{report['note']}"])
    for error in errors:
        lines.extend(["", f"{error['direction']}：{error['error']}"])
    return "\n".join(lines)
