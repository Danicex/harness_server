# app/utils/toon.py
from typing import Any
from datetime import datetime

def _scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        return toon_encode(v)  # nested structures fall back to inline
    s = str(v)
    return s.replace(",", "\\,").replace("\n", " ")

def toon_encode(data: Any, key: str | None = None, indent: int = 0) -> str:
    pad = "  " * indent
    lines = []

    if isinstance(data, list):
        if not data:
            return f"{pad}{key}[0]:" if key else f"{pad}[0]:"
        if all(isinstance(item, dict) for item in data):
            fields = list(data[0].keys())
            header = f"{pad}{key}[{len(data)}]{{{','.join(fields)}}}:" if key else f"{pad}[{len(data)}]{{{','.join(fields)}}}:"
            lines.append(header)
            for item in data:
                row = ",".join(_scalar(item.get(f)) for f in fields)
                lines.append(f"{pad}  {row}")
        else:
            header = f"{pad}{key}[{len(data)}]:" if key else f"{pad}[{len(data)}]:"
            lines.append(header)
            for item in data:
                lines.append(f"{pad}  {_scalar(item)}")
        return "\n".join(lines)

    if isinstance(data, dict):
        if key:
            lines.append(f"{pad}{key}:")
            indent += 1
            pad = "  " * indent
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(toon_encode(v, key=k, indent=indent))
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(lines)

    return f"{pad}{key}: {_scalar(data)}" if key else f"{pad}{_scalar(data)}"