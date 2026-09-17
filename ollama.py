import json
import urllib.request


DEFAULT_PROMPT = """请基于以下 arXiv 论文元数据和英文摘要，输出中文 Markdown，总字数 250-350 字。必须严格基于摘要，不要编造。
结构固定为：
#### 一句话结论
一段话。

#### 核心内容
- 3条要点。

#### 方法与数据
- 1-2条要点，未知就写“摘要未明确”。

#### 价值判断
- **值得关注**：...
- **可复用点**：...
- **局限/待核查**：...

标题：{title}
作者：{authors}
分类：{categories}
摘要：{summary}
"""


def summarize(paper: dict, direction: dict, config: dict) -> str:
    ollama = config.get("ollama", {})
    if not ollama.get("enabled", True):
        raise RuntimeError("Ollama is disabled")

    fields = {
        **paper,
        "authors": ", ".join(paper.get("authors", [])[:8]),
        "categories": ", ".join(paper.get("categories", [])),
    }
    prompt = direction.get("prompt") or config.get("prompt") or DEFAULT_PROMPT
    payload = json.dumps({
        "model": ollama.get("model", "qwen3:30b"),
        "prompt": prompt.format(**fields),
        "stream": False,
        "think": ollama.get("think", "low"),
        "options": {"temperature": ollama.get("temperature", 0.2)},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama.get('base_url', 'http://127.0.0.1:11434').rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    summary = (result.get("response") or "").strip()
    if not summary:
        raise RuntimeError("Ollama returned an empty summary")
    return summary
