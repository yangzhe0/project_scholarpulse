import json
from pathlib import Path


def load_config(path: str) -> dict:
    config_path = Path(path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("result_dir"):
        config["result_dir"] = str(_resolve(config_path.parent, config["result_dir"]))
    directions = config.get("directions")
    if not isinstance(directions, list) or not directions:
        raise ValueError("config must contain at least one direction")

    for direction in directions:
        for key in ("name", "daily_dir", "index_file", "queries"):
            if not direction.get(key):
                raise ValueError(f"direction is missing required field: {key}")
        direction["daily_dir"] = str(_resolve(config_path.parent, direction["daily_dir"]))
        direction["index_file"] = str(_resolve(config_path.parent, direction["index_file"]))
    return config


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()
