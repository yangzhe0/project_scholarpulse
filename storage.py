import os
import re
import tempfile
from pathlib import Path

from text import paper_key


ARXIV_ID = re.compile(r"arxiv\.org/abs/([^\s)/]+)", re.I)


def read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content.rstrip() + "\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def known_ids(daily_dir: Path, index_file: Path) -> set[str]:
    paths = list(daily_dir.glob("*.md")) if daily_dir.exists() else []
    if index_file.exists():
        paths.append(index_file)
    ids = set()
    for path in paths:
        for value in ARXIV_ID.findall(path.read_text(encoding="utf-8")):
            ids.add(paper_key(value))
    return ids
