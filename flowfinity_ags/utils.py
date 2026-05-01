from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pandas as pd


def clean_ags_text(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value)

    replacements = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "…": "...",
        "\t": " ",
        "\r": " ",
        "\n": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.encode("ascii", errors="ignore").decode("ascii")
    text = " ".join(text.split())
    return text.strip()


def clean_date(value) -> str:
    text = clean_ags_text(value)
    if not text:
        return ""

    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y, %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    return text


def clean_number(value, decimals: int = 2) -> str:
    text = clean_ags_text(value)
    if not text:
        return ""

    try:
        number = float(text)
        return f"{number:.{decimals}f}"
    except Exception:
        return text


def clean_by_type(value, ags_type: str, unit: str = "") -> str:
    ags_type = (ags_type or "").upper()
    unit = unit or ""

    if ags_type == "DT" or "yyyy" in unit.lower():
        return clean_date(value)

    if ags_type == "2DP":
        return clean_number(value, 2)

    if ags_type == "1DP":
        return clean_number(value, 1)

    if ags_type == "3DP":
        return clean_number(value, 3)

    if ags_type == "XN":
        return clean_number(value, 2)

    return clean_ags_text(value)


def find_input_column(df_columns, aliases: list[str]):
    lookup = {str(c).strip().lower(): c for c in df_columns}

    for alias in aliases:
        key = str(alias).strip().lower()
        if key in lookup:
            return lookup[key]

    return None


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()

    if suffix == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp1252")

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)

    raise ValueError(f"Unsupported file type: {suffix}")


def infer_project_id(path: Path) -> str:
    text = " ".join([path.stem, path.parent.name])
    match = re.search(r"\b(\d{4,8})\b", text)
    if match:
        return match.group(1)
    return "UNKNOWN_PROJECT"


def infer_loca_id(path: Path) -> str:
    text = " ".join([path.stem, path.parent.name]).upper()

    patterns = [
        r"\b(TP[\s_\-]*\d+[A-Z]?)\b",
        r"\b(BH[\s_\-]*\d+[A-Z]?)\b",
        r"\b(WS[\s_\-]*\d+[A-Z]?)\b",
        r"\b(CP[\s_\-]*\d+[A-Z]?)\b",
        r"\b(HP[\s_\-]*\d+[A-Z]?)\b",
        r"\b(SA[\s_\-]*\d+[A-Z]?)\b",
        r"\b(RC[\s_\-]*\d+[A-Z]?)\b",
        r"\b(TT[\s_\-]*\d+[A-Z]?)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"[\s_\-]+", "", match.group(1))

    parent = path.parent.name.strip()
    if parent and parent not in {".", ""}:
        return parent

    return path.stem
