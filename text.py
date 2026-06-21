import html
import re


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def paper_key(value: str) -> str:
    return re.sub(r"v\d+$", "", value.lower())


def markdown_cell(value: str) -> str:
    return clean(value).replace("|", "｜")
