"""通用数据加载、保存和日期解析工具。"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def load_data(path: str | Path) -> Any:
    """根据文件扩展名加载 JSON、JSONL、YAML 或文本文件。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8")

    if suffix == ".json":
        return json.loads(text)

    if suffix == ".jsonl":
        records = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{file_path} 第 {line_number} 行不是有效 JSON"
                ) from error
        return records

    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)

    if suffix in {".txt", ".text", ".md"}:
        return text

    raise ValueError(f"不支持的文件格式：{suffix}")


def save_data(path: str | Path, data: Any) -> None:
    """按文件扩展名保存 JSON、JSONL、YAML 或文本，并在需要时创建父目录。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        text = json.dumps(data, ensure_ascii=False, indent=2)
    elif suffix == ".jsonl":
        if not isinstance(data, list):
            raise ValueError("JSONL 文件需要保存一个列表")
        text = "\n".join(json.dumps(item, ensure_ascii=False) for item in data)
    elif suffix in {".yaml", ".yml"}:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).rstrip("\n")
    elif suffix in {".txt", ".text", ".md"}:
        if not isinstance(data, str):
            raise ValueError("文本文件需要保存字符串")
        text = data
    else:
        raise ValueError(f"不支持的文件格式：{suffix}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"{text}\n", encoding="utf-8")


def parse_date(value: date | str) -> date:
    """把日期或 YYYY-MM-DD、YYYY.M.D 字符串解析为 date。"""
    if isinstance(value, date):
        return value
    text = value.strip().replace(".", "-")
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        text = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"日期必须是 YYYY-MM-DD：{value}") from error
