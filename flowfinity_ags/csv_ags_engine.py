from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import OrderedDict
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import openpyxl

from .models import Issue, ProcessResult, SourceFile


AUTO_GROUP_ORDER = ["PROJ", "TRAN"]


def run_csv_ags_from_uploaded_sources(
    uploaded_sources: list[dict[str, Any]],
    settings: dict | None = None,
    profile_name: str = "AGS 4.0 compact",
) -> ProcessResult:
    settings = settings or {}

    expanded_sources = expand_uploaded_sources(uploaded_sources)
    issues: list[Issue] = []
    skipped_files: list[str] = []

    parsed_groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
    source_files: list[SourceFile] = []

    project_id = clean(settings.get("project_id")) or infer_project_id(expanded_sources) or "UNKNOWN_PROJECT"

    for source in expanded_sources:
        source_name = source["name"]
        source_type = source["type"]
        source_bytes = source["bytes"]

        try:
            if source_type == "csv":
                group_name = group_name_from_path(source_name)
                rows = read_csv_rows(source_bytes)
                parsed = parse_table_as_group(rows, group_name, source_name, project_id, issues)
                if parsed:
                    merge_group(parsed_groups, parsed)
                    source_files.append(
                        SourceFile(
                            file_name=source_name,
                            relative_path=source_name,
                            group=parsed["group"],
                            project_id=project_id,
                            loca_id=first_loca_id(parsed["headings"], parsed["rows"]),
                            rows=len(parsed["rows"]),
                        )
                    )

            elif source_type == "xlsx":
                workbook = openpyxl.load_workbook(io.BytesIO(source_bytes), data_only=True)

                for worksheet in workbook.worksheets:
                    if worksheet.title.lower().strip().startswith("lookup"):
                        continue

                    rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
                    group_name = safe_group_name(worksheet.title)
                    parsed = parse_table_as_group(rows, group_name, f"{source_name}/{worksheet.title}", project_id, issues)

                    if parsed:
                        merge_group(parsed_groups, parsed)
                        source_files.append(
                            SourceFile(
                                file_name=source_name,
                                relative_path=f"{source_name}/{worksheet.title}",
                                group=parsed["group"],
                                project_id=project_id,
                                loca_id=first_loca_id(parsed["headings"], parsed["rows"]),
                                rows=len(parsed["rows"]),
                            )
                        )

        except Exception as exc:
            skipped_files.append(source_name)
            issues.append(Issue("error", "FILE", source_name, "", f"Could not parse source: {exc}"))

    if not parsed_groups:
        issues.append(Issue("error", "FILE", "", "", "No AGS table groups were detected."))

    add_auto_groups(parsed_groups, project_id, settings)

    ags_text = build_ags_text(parsed_groups)

    group_counts = {group: len(payload["rows"]) for group, payload in parsed_groups.items()}
    location_counts = build_location_counts(parsed_groups)
    project_counts = {project_id: max(1, len(location_counts))}

    summary = {
        "ags_version": "4.0",
        "files_found": len(expanded_sources),
        "files_used": len(source_files),
        "files_skipped": len(skipped_files),
        "groups_with_rows": sum(1 for payload in parsed_groups.values() if payload["rows"]),
        "locations": len(location_counts),
        "projects": 1,
        "warnings": sum(1 for issue in issues if issue.severity == "warning"),
        "errors": sum(1 for issue in issues if issue.severity == "error"),
    }

    return ProcessResult(
        ags_text=ags_text,
        summary=summary,
        group_counts=group_counts,
        location_counts=location_counts,
        project_counts=project_counts,
        source_files=source_files,
        issues=issues,
        skipped_files=skipped_files,
    )


def expand_uploaded_sources(uploaded_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []

    for item in uploaded_sources:
        name = str(item.get("name", "uploaded_file"))
        data = item.get("bytes", b"")

        if not isinstance(data, (bytes, bytearray)):
            continue

        lower_name = name.lower()

        if lower_name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
                for member in archive.namelist():
                    member_lower = member.lower()
                    basename = Path(member).name

                    if not basename or basename.startswith("~$"):
                        continue

                    if member_lower.endswith(".csv"):
                        expanded.append({"name": member, "bytes": archive.read(member), "type": "csv"})
                    elif member_lower.endswith((".xlsx", ".xlsm")):
                        expanded.append({"name": member, "bytes": archive.read(member), "type": "xlsx"})

        elif lower_name.endswith(".csv"):
            expanded.append({"name": name, "bytes": bytes(data), "type": "csv"})
        elif lower_name.endswith((".xlsx", ".xlsm")):
            expanded.append({"name": name, "bytes": bytes(data), "type": "xlsx"})

    return expanded


def read_csv_rows(data: bytes) -> list[list[Any]]:
    text = decode_csv_bytes(data)

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    return [row for row in reader]


def decode_csv_bytes(data: bytes) -> str:
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")


def parse_table_as_group(
    raw_rows: list[list[Any]],
    fallback_group: str,
    source_name: str,
    project_id: str,
    issues: list[Issue],
) -> dict[str, Any] | None:
    rows = strip_empty_edges(raw_rows)

    if not rows:
        issues.append(Issue("warning", fallback_group, source_name, "", "Empty table skipped."))
        return None

    first_index = first_non_empty_row_index(rows)

    if first_index is None:
        issues.append(Issue("warning", fallback_group, source_name, "", "Blank table skipped."))
        return None

    first_row = rows[first_index]
    first_cell = clean(first_row[0] if first_row else "").upper()

    if first_cell == "GROUP":
        group_name = safe_group_name(clean(first_row[1] if len(first_row) > 1 else fallback_group))
        heading_index = find_control_row(rows, "HEADING", start=first_index + 1)
        unit_index = find_control_row(rows, "UNIT", start=first_index + 1)
        type_index = find_control_row(rows, "TYPE", start=first_index + 1)

        if heading_index is None:
            issues.append(Issue("error", group_name, source_name, "", "GROUP block has no HEADING row."))
            return None

        return parse_controlled_group(rows, group_name, heading_index, unit_index, type_index, source_name, issues)

    if first_cell == "HEADING":
        group_name = safe_group_name(fallback_group)
        unit_index = first_index + 1 if row_control_name(rows, first_index + 1) == "UNIT" else None
        type_index = first_index + 2 if row_control_name(rows, first_index + 2) == "TYPE" else None

        return parse_controlled_group(rows, group_name, first_index, unit_index, type_index, source_name, issues)

    return parse_plain_table(rows, fallback_group, first_index, source_name, project_id, issues)


def parse_controlled_group(
    rows: list[list[Any]],
    group_name: str,
    heading_index: int,
    unit_index: int | None,
    type_index: int | None,
    source_name: str,
    issues: list[Issue],
) -> dict[str, Any] | None:
    heading_row = rows[heading_index]
    headings = [clean(value) for value in heading_row[1:]]
    headings = trim_trailing_empty(headings)

    if not headings:
        issues.append(Issue("error", group_name, source_name, "", "HEADING row has no AGS headings."))
        return None

    column_count = len(headings)

    units = []
    if unit_index is not None and unit_index < len(rows):
        units = [clean(value) for value in rows[unit_index][1:1 + column_count]]
    units = pad_list(units, column_count, "")

    types = []
    if type_index is not None and type_index < len(rows):
        types = [clean(value) for value in rows[type_index][1:1 + column_count]]
    types = pad_list(types, column_count, "X")

    data_start = max(index for index in [heading_index, unit_index or heading_index, type_index or heading_index]) + 1

    data_rows: list[list[str]] = []

    for raw_row in rows[data_start:]:
        if row_is_blank(raw_row):
            continue

        first_cell = clean(raw_row[0] if raw_row else "").upper()

        if first_cell in {"GROUP", "HEADING", "UNIT", "TYPE"}:
            break

        values = raw_row[1:1 + column_count]

        if not any_valid_value(values):
            continue

        data_rows.append(
            [
                format_value(values[index] if index < len(values) else "", units[index], types[index])
                for index in range(column_count)
            ]
        )

    return {
        "group": safe_group_name(group_name),
        "headings": headings,
        "units": units,
        "types": types,
        "rows": data_rows,
    }


def parse_plain_table(
    rows: list[list[Any]],
    fallback_group: str,
    header_index: int,
    source_name: str,
    project_id: str,
    issues: list[Issue],
) -> dict[str, Any] | None:
    group_name = safe_group_name(fallback_group)

    headings = [clean(value) for value in rows[header_index]]
    headings = trim_trailing_empty(headings)

    if not headings:
        issues.append(Issue("error", group_name, source_name, "", "Plain table has no heading row."))
        return None

    column_count = len(headings)
    source_data_rows = [
        row[:column_count]
        for row in rows[header_index + 1:]
        if not row_is_blank(row[:column_count])
    ]

    units = [infer_unit(heading) for heading in headings]
    types = [infer_type(heading, [row[index] if index < len(row) else "" for row in source_data_rows]) for index, heading in enumerate(headings)]

    data_rows: list[list[str]] = []

    for raw_row in source_data_rows:
        values = [
            format_value(raw_row[index] if index < len(raw_row) else "", units[index], types[index])
            for index in range(column_count)
        ]

        if any_valid_value(values):
            data_rows.append(values)

    return {
        "group": group_name,
        "headings": headings,
        "units": units,
        "types": types,
        "rows": data_rows,
    }


def merge_group(parsed_groups: OrderedDict[str, dict[str, Any]], parsed: dict[str, Any]) -> None:
    group = parsed["group"]

    if group not in parsed_groups:
        parsed_groups[group] = parsed
        return

    existing = parsed_groups[group]

    if existing["headings"] == parsed["headings"]:
        existing["rows"].extend(parsed["rows"])
        return

    suffix = 2
    while f"{group}_{suffix}" in parsed_groups:
        suffix += 1

    parsed["group"] = f"{group}_{suffix}"
    parsed_groups[parsed["group"]] = parsed


def add_auto_groups(parsed_groups: OrderedDict[str, dict[str, Any]], project_id: str, settings: dict) -> None:
    if "PROJ" not in parsed_groups:
        parsed_groups.update(
            {
                "__AUTO_PROJ__": {
                    "group": "PROJ",
                    "headings": ["PROJ_ID", "PROJ_NAME", "PROJ_LOC", "PROJ_CLNT", "PROJ_CONT", "PROJ_ENG", "PROJ_MEMO"],
                    "units": ["", "", "", "", "", "", ""],
                    "types": ["ID", "X", "X", "X", "X", "X", "X"],
                    "rows": [[
                        project_id,
                        clean(settings.get("project_name")),
                        clean(settings.get("project_location")),
                        clean(settings.get("project_client")),
                        clean(settings.get("project_contractor")),
                        clean(settings.get("project_engineer")),
                        clean(settings.get("project_memo")),
                    ]],
                }
            }
        )

    if "TRAN" not in parsed_groups:
        parsed_groups.update(
            {
                "__AUTO_TRAN__": {
                    "group": "TRAN",
                    "headings": ["TRAN_ISNO", "TRAN_DATE", "TRAN_PROD", "TRAN_STAT", "TRAN_DESC", "TRAN_AGS", "TRAN_RECV", "TRAN_DLIM", "TRAN_RCON", "TRAN_REM", "FILE_FSET"],
                    "units": ["", "yyyy-mm-dd", "", "", "", "", "", "", "", "", ""],
                    "types": ["X", "DT", "X", "X", "X", "X", "X", "X", "X", "X", "X"],
                    "rows": [[
                        "1",
                        datetime.today().strftime("%Y-%m-%d"),
                        clean(settings.get("tran_prod")) or "IGNE",
                        clean(settings.get("tran_stat")) or "Draft",
                        clean(settings.get("tran_desc")) or "CSV / Excel AGS table import",
                        "4.0",
                        clean(settings.get("tran_recv")) or "Client",
                        clean(settings.get("tran_dlim")) or "|",
                        clean(settings.get("tran_rcon")) or "+",
                        "",
                        "",
                    ]],
                }
            }
        )

    ordered: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for auto_key in ["__AUTO_PROJ__", "__AUTO_TRAN__"]:
        if auto_key in parsed_groups:
            payload = parsed_groups.pop(auto_key)
            ordered[payload["group"]] = payload

    for group in AUTO_GROUP_ORDER:
        if group in parsed_groups:
            ordered[group] = parsed_groups.pop(group)

    for group, payload in parsed_groups.items():
        ordered[group] = payload

    parsed_groups.clear()
    parsed_groups.update(ordered)


def build_ags_text(parsed_groups: OrderedDict[str, dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")

    for _, payload in parsed_groups.items():
        group = payload["group"]
        headings = payload["headings"]
        units = pad_list(payload["units"], len(headings), "")
        types = pad_list(payload["types"], len(headings), "X")

        writer.writerow(["GROUP", group])
        writer.writerow(["HEADING", *headings])
        writer.writerow(["UNIT", *units])
        writer.writerow(["TYPE", *types])

        for row in payload["rows"]:
            writer.writerow(["DATA", *pad_list(row, len(headings), "")[:len(headings)]])

        writer.writerow([])

    return output.getvalue().rstrip() + "\n"


def build_location_counts(parsed_groups: OrderedDict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for payload in parsed_groups.values():
        headings = payload["headings"]
        loca_index = find_heading_index(headings, "LOCA_ID")

        if loca_index is None:
            continue

        for row in payload["rows"]:
            if loca_index < len(row):
                loca_id = clean(row[loca_index])
                if loca_id:
                    counts[loca_id] = counts.get(loca_id, 0) + 1

    return counts


def first_loca_id(headings: list[str], rows: list[list[str]]) -> str:
    loca_index = find_heading_index(headings, "LOCA_ID")

    if loca_index is None:
        return ""

    for row in rows:
        if loca_index < len(row):
            loca_id = clean(row[loca_index])
            if loca_id:
                return loca_id

    return ""


def find_heading_index(headings: list[str], wanted: str) -> int | None:
    wanted_norm = clean(wanted).upper()

    for index, heading in enumerate(headings):
        if clean(heading).upper() == wanted_norm:
            return index

    return None


def infer_project_id(expanded_sources: list[dict[str, Any]]) -> str:
    for source in expanded_sources:
        match = re.search(r"\b(\d{4,8})\b", str(source.get("name", "")))
        if match:
            return match.group(1)

    return ""


def group_name_from_path(path: str) -> str:
    return safe_group_name(Path(path).stem)


def safe_group_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", clean(value).upper()).strip("_")

    if not cleaned:
        return "DATA"

    return cleaned[:20]


def strip_empty_edges(rows: list[list[Any]]) -> list[list[Any]]:
    cleaned_rows = [list(row) for row in rows]

    while cleaned_rows and row_is_blank(cleaned_rows[0]):
        cleaned_rows.pop(0)

    while cleaned_rows and row_is_blank(cleaned_rows[-1]):
        cleaned_rows.pop()

    return cleaned_rows


def first_non_empty_row_index(rows: list[list[Any]]) -> int | None:
    for index, row in enumerate(rows):
        if not row_is_blank(row):
            return index

    return None


def find_control_row(rows: list[list[Any]], control_name: str, start: int = 0) -> int | None:
    wanted = control_name.upper()

    for index in range(start, len(rows)):
        if row_control_name(rows, index) == wanted:
            return index

    return None


def row_control_name(rows: list[list[Any]], index: int) -> str:
    if index < 0 or index >= len(rows):
        return ""

    row = rows[index]

    if not row:
        return ""

    return clean(row[0]).upper()


def trim_trailing_empty(values: list[str]) -> list[str]:
    output = list(values)

    while output and clean(output[-1]) == "":
        output.pop()

    return output


def pad_list(values: list[Any], length: int, fill: str) -> list[str]:
    output = [clean(value) for value in values]

    while len(output) < length:
        output.append(fill)

    return output


def any_valid_value(values: list[Any]) -> bool:
    return any(clean(value) for value in values)


def row_is_blank(row: list[Any] | tuple[Any, ...]) -> bool:
    return not any(clean(value) for value in row)


def infer_unit(heading: str) -> str:
    h = clean(heading).upper()

    if h.endswith("_DATE") or h in {"DATE"}:
        return "yyyy-mm-dd"

    if h.endswith("_TIME") or h.endswith("_DURN") or h in {"TIME", "DURATION"}:
        return "hh:mm:ss"

    if any(token in h for token in ["_DPTH", "_TOP", "_BASE", "_BOTT", "_PLEN", "_PWID", "_THCK", "_DEPTH"]):
        return "m"

    if h.endswith("_MC") or "MOISTURE" in h or "PERCENT" in h:
        return "%"

    if h.endswith("_SEAT"):
        return "N"

    if h.endswith("_SURC"):
        return "kPa"

    return ""


def infer_type(heading: str, values: list[Any]) -> str:
    h = clean(heading).upper()

    if h == "LOCA_ID":
        return "ID"

    if h.endswith("_DATE") or h == "DATE":
        return "DT"

    if h.endswith("_TIME") or h.endswith("_DURN"):
        return "T"

    if any(token in h for token in ["_DPTH", "_TOP", "_BASE", "_BOTT", "_PLEN", "_PWID", "_THCK", "_DEPTH"]):
        return "2DP"

    non_blank = [value for value in values if clean(value)]

    if not non_blank:
        return "X"

    numeric_values = []

    for value in non_blank:
        try:
            numeric_values.append(float(clean(value)))
        except ValueError:
            return "X"

    if numeric_values and all(float(value).is_integer() for value in numeric_values):
        return "0DP"

    return "2DP"


def format_value(value: Any, unit: str = "", ags_type: str = "") -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        if unit == "yyyy-mm-dd" or ags_type == "DT":
            return value.strftime("%Y-%m-%d")

        return value.strftime("%Y-%m-%dT%H:%M:%S")

    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

        return f"{value:.10f}".rstrip("0").rstrip(".")

    text = clean(value)

    if not text:
        return ""

    return text


def clean(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    text = str(value).strip()

    if text.startswith("#") or text.startswith("="):
        return ""

    return re.sub(r"\s+", " ", text).strip()
