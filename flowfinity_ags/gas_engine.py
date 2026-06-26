from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl

from .models import Issue, ProcessResult, SourceFile


GROUP_ORDER = ["PROJ", "DICT", "TRAN", "MONG", "MOND", "LOCA", "UNIT", "ABBR", "TYPE"]

DICT_ROWS = [
    ["HEADING", "LOCA", "LOCA_CKBY", "OTHER", "X", "Checked By", "", "J. Smith", "", "", ""],
    ["HEADING", "LOCA", "LOCA_CKDT", "OTHER", "DT", "Checked Date", "yyyy-mm-dd", "2012-04-15", "", "", ""],
    ["HEADING", "LOCA", "LOCA_NATD", "OTHER", "X", "National Datum Referencing System used", "", "OD Newlyn", "", "", ""],
    ["HEADING", "LOCA", "LOCA_ORID", "OTHER", "X", "Original Hole ID", "", "BH1", "", "", ""],
    ["HEADING", "LOCA", "LOCA_ORJO", "OTHER", "X", "Original Job Reference", "", "ABC1234", "", "", ""],
    ["HEADING", "LOCA", "LOCA_ORCO", "OTHER", "X", "Originating Company", "", "Acme Consultants", "", "", ""],
    ["HEADING", "SAMP", "SAMP_RECL", "OTHER", "0DP", "Length of sample recovered", "mm", "205", "LOCA", "SAMP_RECL is intended primarily for tube samples.", ""],
]

UNIT_ROWS = [
    ["%", "percentage", ""],
    ["%vol", "percentage volume", ""],
    ["bar", "bar", ""],
    ["deg", "degree angle", ""],
    ["degC", "degree Celsius", ""],
    ["hh:mm", "hours minutes", ""],
    ["hh:mm:ss", "hours minutes seconds", ""],
    ["kPa", "kiloPascal", ""],
    ["l/hr", "litres per hour", ""],
    ["l/min", "litres per minute", ""],
    ["m", "metre", ""],
    ["Mg/m3", "megagrams per cubic metre", ""],
    ["mm", "millimetre", ""],
    ["mbar", "millibar", ""],
    ["Pa", "Pascal", ""],
    ["ppm", "parts per million", ""],
    ["yyyy-mm-dd", "year month day", ""],
    ["yyyy-mm-ddThh:mm", "year month day hours minutes", ""],
    ["dd/mm/yyyy hh:mm:ss", "day month year hours minutes seconds", ""],
]

ABBR_ROWS = [
    ["DICT_STAT", "OTHER", "Other field", "", ""],
    ["DICT_TYPE", "HEADING", "Flag to indicate definition is a HEADING", "", ""],
    ["MOND_TYPE", "BAR", "Barometric pressure at time of monitoring", "", ""],
    ["MOND_TYPE", "FLOW", "Flow", "", ""],
    ["MOND_TYPE", "GFLOS", "Gas flow steady", "", ""],
    ["MOND_TYPE", "GFLOP", "Gas flow peak", "", ""],
    ["MOND_TYPE", "GCD", "Carbon dioxide concentration", "", ""],
    ["MOND_TYPE", "GCM", "Carbon monoxide concentration", "", ""],
    ["MOND_TYPE", "GOX", "Oxygen concentration", "", ""],
    ["MOND_TYPE", "GPRS", "Differential Pressure", "", ""],
    ["MOND_TYPE", "HYS", "Hydrogen sulphide concentration", "", ""],
    ["MOND_TYPE", "PID", "Photoionisation detector reading", "", ""],
    ["MOND_TYPE", "TGM", "Total methane concentration", "", ""],
    ["MOND_TYPE", "WDEP", "Depth to water from LOCA_ID datum", "", ""],
    ["MONG_TYPE", "SP", "Standpipe", "", ""],
]

TYPE_ROWS = [
    ["0DP", "Value; required number of decimal places, 0", ""],
    ["1DP", "Value; required number of decimal places, 1", ""],
    ["2DP", "Value; required number of decimal places, 2", ""],
    ["DMS", "Degrees:Minutes:Seconds", ""],
    ["DT", "Date time in international format", ""],
    ["ID", "Unique Identifier", ""],
    ["PA", "Pick list text listed in ABBR Group", ""],
    ["PT", "Pick list text listed in TYPE Group", ""],
    ["PU", "Pick list text listed in UNIT Group", ""],
    ["RL", "Record link", ""],
    ["T", "Elapsed time", ""],
    ["U", "Value with variable format", ""],
    ["X", "Text", ""],
    ["XN", "Text / numeric", ""],
]

GROUP_DEFS = {
    "PROJ": (
        ["PROJ_ID"],
        [""],
        ["ID"],
    ),
    "DICT": (
        ["DICT_TYPE", "DICT_GRP", "DICT_HDNG", "DICT_STAT", "DICT_DTYP", "DICT_DESC", "DICT_UNIT", "DICT_EXMP", "DICT_PGRP", "DICT_REM", "FILE_FSET"],
        ["", "", "", "", "", "", "", "", "", "", ""],
        ["PA", "X", "X", "PA", "PT", "X", "PU", "X", "X", "X", "X"],
    ),
    "TRAN": (
        ["TRAN_ISNO", "TRAN_DATE", "TRAN_PROD", "TRAN_STAT", "TRAN_DESC", "TRAN_AGS", "TRAN_RECV", "TRAN_DLIM", "TRAN_RCON", "TRAN_REM", "FILE_FSET"],
        ["", "yyyy-mm-dd", "", "", "", "", "", "", "", "", ""],
        ["X", "DT", "X", "X", "X", "X", "X", "X", "X", "X", "X"],
    ),
    "MONG": (
        ["LOCA_ID", "MONG_ID", "MONG_DIS", "PIPE_REF", "MONG_DATE", "MONG_TYPE", "MONG_DETL", "MONG_TRZ", "MONG_BRZ", "MONG_BRGA", "MONG_BRGB", "MONG_BRGC", "MONG_INCA", "MONG_INCB", "MONG_INCC", "MONG_RSCA", "MONG_RSCB", "MONG_RSCC", "MONG_REM", "MONG_CONT", "FILE_FSET"],
        ["", "", "m", "", "yyyy-mm-dd", "", "", "m", "m", "deg", "deg", "deg", "deg", "deg", "deg", "", "", "", "", "", ""],
        ["ID", "X", "2DP", "X", "DT", "PA", "X", "2DP", "2DP", "0DP", "0DP", "0DP", "0DP", "0DP", "0DP", "X", "X", "X", "X", "X", "X"],
    ),
    "MOND": (
        ["LOCA_ID", "MONG_ID", "MONG_DIS", "MOND_DTIM", "MOND_TYPE", "MOND_REF", "MOND_INST", "MOND_RDNG", "MOND_UNIT", "MOND_METH", "MOND_LIM", "MOND_ULIM", "MOND_NAME", "MOND_CRED", "MOND_CONT", "MOND_REM", "FILE_FSET"],
        ["", "", "m", "dd/mm/yyyy hh:mm:ss", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["ID", "X", "2DP", "DT", "PA", "X", "X", "XN", "PU", "X", "U", "U", "X", "X", "X", "X", "X"],
    ),
    "LOCA": (
        ["LOCA_ID"],
        [""],
        ["ID"],
    ),
    "UNIT": (
        ["UNIT_UNIT", "UNIT_DESC", "FILE_FSET"],
        ["", "", ""],
        ["X", "X", "X"],
    ),
    "ABBR": (
        ["ABBR_HDNG", "ABBR_CODE", "ABBR_DESC", "ABBR_LIST", "FILE_FSET"],
        ["", "", "", "", ""],
        ["X", "X", "X", "X", "X"],
    ),
    "TYPE": (
        ["TYPE_TYPE", "TYPE_DESC", "FILE_FSET"],
        ["", "", ""],
        ["X", "X", "X"],
    ),
}

READING_MAP = {
    # Flow readings. Keep steady and peak separate.
    "gas flow steady": ("GFLOS", "l/hr"),
    "flow steady": ("GFLOS", "l/hr"),
    "steady flow": ("GFLOS", "l/hr"),
    "steady": ("GFLOS", "l/hr"),
    "gflos": ("GFLOS", "l/hr"),

    "gas flow peak": ("GFLOP", "l/hr"),
    "flow peak": ("GFLOP", "l/hr"),
    "peak flow": ("GFLOP", "l/hr"),
    "peak": ("GFLOP", "l/hr"),
    "gflop": ("GFLOP", "l/hr"),

    # Fallback for generic flow columns.
    "flow": ("GFLOS", "l/hr"),

    # Pressure / water.
    "barometric pressure": ("BAR", "mbar"),
    "atmospheric pressure": ("BAR", "mbar"),
    "atmospheric": ("BAR", "mbar"),
    "atm pressure": ("BAR", "mbar"),
    "bar": ("BAR", "mbar"),

    "differential pressure": ("GPRS", "Pa"),
    "diff pressure": ("GPRS", "Pa"),
    "gas pressure": ("GPRS", "Pa"),
    "gprs": ("GPRS", "Pa"),

    "water level": ("WDEP", "m"),
    "water depth": ("WDEP", "m"),
    "wdep": ("WDEP", "m"),

    # Gas concentrations.
    "ch4": ("TGM", "%vol"),
    "methane": ("TGM", "%vol"),
    "co2": ("GCD", "%vol"),
    "carbon dioxide": ("GCD", "%vol"),
    "o2": ("GOX", "%vol"),
    "oxygen": ("GOX", "%vol"),
    "h2s": ("HYS", "ppm"),
    "hydrogen sulphide": ("HYS", "ppm"),
    "hydrogen sulfide": ("HYS", "ppm"),
    "carbon monoxide": ("GCM", "ppm"),
    "co": ("GCM", "ppm"),
    "pid": ("PID", "ppm"),
}


def run_gas_from_uploaded_sources(
    uploaded_sources: list[dict[str, Any]],
    settings: dict | None = None,
    profile_name: str = "AGS 4.0 compact",
) -> ProcessResult:
    settings = settings or {}

    source_workbooks = expand_uploaded_sources(uploaded_sources)
    issues: list[Issue] = []
    skipped_files: list[str] = []

    group_rows: dict[str, list[list[str]]] = {group: [] for group in GROUP_ORDER}
    location_ids: set[str] = set()
    source_files: list[SourceFile] = []

    project_id = clean(settings.get("project_id")) or infer_project_from_sources(source_workbooks) or "UNKNOWN_PROJECT"

    group_rows["PROJ"] = [[project_id]]
    group_rows["DICT"] = DICT_ROWS.copy()
    group_rows["TRAN"] = [[
        "1",
        datetime.today().strftime("%Y-%m-%d"),
        clean(settings.get("tran_prod")) or "IGNE",
        clean(settings.get("tran_stat")) or "Draft",
        clean(settings.get("tran_desc")) or "Field gas monitoring export",
        "4.0",
        clean(settings.get("tran_recv")) or "Client",
        clean(settings.get("tran_dlim")) or "|",
        clean(settings.get("tran_rcon")) or "+",
        "",
        "",
    ]]
    group_rows["UNIT"] = UNIT_ROWS.copy()
    group_rows["ABBR"] = ABBR_ROWS.copy()
    group_rows["TYPE"] = TYPE_ROWS.copy()

    for source_name, workbook_bytes in source_workbooks:
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=True)
        except Exception as exc:
            skipped_files.append(source_name)
            issues.append(Issue("error", "FILE", source_name, "", f"Could not read workbook: {exc}"))
            continue

        for worksheet in workbook.worksheets:
            if worksheet.title.lower().strip().startswith("lookup"):
                continue

            parsed = parse_gas_sheet(worksheet, source_name, project_id, settings, issues)
            if parsed is None:
                continue

            loca_id = parsed["loca_id"]
            location_ids.add(loca_id)

            group_rows["MONG"].append(parsed["mong_row"])
            group_rows["MOND"].extend(parsed["mond_rows"])

            source_files.extend([
                SourceFile(source_name, f"{source_name}/{worksheet.title}", "MONG", project_id, loca_id, 1),
                SourceFile(source_name, f"{source_name}/{worksheet.title}", "MOND", project_id, loca_id, len(parsed["mond_rows"])),
                SourceFile(source_name, f"{source_name}/{worksheet.title}", "LOCA", project_id, loca_id, 1),
            ])

    group_rows["LOCA"] = [[loca_id] for loca_id in sorted(location_ids)]

    if not source_workbooks:
        issues.append(Issue("error", "FILE", "", "", "No uploaded gas monitoring files were supplied."))

    if not group_rows["MOND"] and source_workbooks:
        issues.append(Issue("warning", "MOND", "", "", "No valid gas monitoring readings were detected."))

    ags_text = build_ags_text(group_rows)

    group_counts = {group: len(rows) for group, rows in group_rows.items()}

    location_counts: dict[str, int] = {loca_id: 0 for loca_id in sorted(location_ids)}
    for row in group_rows["MOND"]:
        if row:
            location_counts[row[0]] = location_counts.get(row[0], 0) + 1

    project_counts = {project_id: len(location_ids) or 1}

    summary = {
        "ags_version": "4.0",
        "files_found": len(source_workbooks),
        "files_used": len([sf for sf in source_files if sf.group == "MOND"]),
        "files_skipped": len(skipped_files),
        "groups_with_rows": sum(1 for rows in group_rows.values() if rows),
        "locations": len(location_ids),
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


def expand_uploaded_sources(uploaded_sources: list[dict[str, Any]]) -> list[tuple[str, bytes]]:
    expanded: list[tuple[str, bytes]] = []

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
                    if member_lower.endswith((".xlsx", ".xlsm", ".xls")) and not Path(member).name.startswith("~$"):
                        expanded.append((member, archive.read(member)))
        elif lower_name.endswith((".xlsx", ".xlsm", ".xls")) and not Path(name).name.startswith("~$"):
            expanded.append((name, bytes(data)))

    return expanded


def parse_gas_sheet(worksheet, source_name: str, project_id: str, settings: dict, issues: list[Issue]) -> dict[str, Any] | None:
    rows = list(worksheet.iter_rows(values_only=True))
    flat_text = " ".join(clean(cell) for row in rows[:40] for cell in row if clean(cell)).lower()

    if "mong" not in flat_text and "mond" not in flat_text:
        return None

    loca_id = find_label_value(rows, ["borehole id", "location id", "loca id", "hole id"]) or worksheet.title
    pipe_ref = find_label_value(rows, ["install pipe no", "install/pipe no", "pipe no", "installation no"]) or "1"
    mong_type = find_label_value(rows, ["type"]) or "SP"
    mong_dis = find_label_value(rows, ["standpipe base", "base", "depth", "install depth"]) or ""

    weather = find_label_value(rows, ["weathered conditions", "weather conditions", "weather"])
    comments = find_label_value(rows, ["notes/comments", "notes", "comments"])
    remarks = "; ".join(part for part in [weather, comments] if part)

    sections = find_sections(rows)
    if not sections:
        issues.append(Issue("warning", "FILE", source_name, loca_id, f"No MONG or MOND sections found on sheet {worksheet.title}."))
        return None

    mond_rows: list[list[str]] = []

    for section in sections:
        parsed_rows = parse_section_rows(rows, section, loca_id, mong_dis, remarks)
        mond_rows.extend(parsed_rows)

    if not mond_rows:
        issues.append(Issue("warning", "MOND", source_name, loca_id, f"No valid readings found on sheet {worksheet.title}."))

    mong_row = [
        loca_id,
        loca_id,
        as_2dp(mong_dis),
        pipe_ref,
        "",
        mong_type if mong_type else "SP",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    return {
        "loca_id": loca_id,
        "mong_row": mong_row,
        "mond_rows": mond_rows,
    }


def find_sections(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    markers: list[tuple[str, int]] = []

    for index, row in enumerate(rows):
        for cell in row:
            value = clean(cell).upper()
            if value in {"MONG", "MOND"}:
                markers.append((value, index))
                break

    sections: list[dict[str, Any]] = []

    for marker_index, (name, row_index) in enumerate(markers):
        end_index = markers[marker_index + 1][1] if marker_index + 1 < len(markers) else len(rows)
        header_index = row_index + 1
        subheader_index = header_index + 1

        header_rows = [rows[header_index] if header_index < len(rows) else tuple()]
        data_start = header_index + 1

        if subheader_index < end_index:
            subheader = rows[subheader_index]
            first_two_blank = not clean(subheader[0] if len(subheader) > 0 else None) and not clean(subheader[1] if len(subheader) > 1 else None)
            has_subheader_text = any(clean(cell) for cell in subheader[2:])
            if first_two_blank and has_subheader_text:
                header_rows.append(subheader)
                data_start = subheader_index + 1

        headers = build_combined_headers(header_rows)

        sections.append(
            {
                "name": name,
                "start": data_start,
                "end": end_index,
                "headers": headers,
            }
        )

    return sections


def build_combined_headers(header_rows: list[tuple[Any, ...]]) -> list[str]:
    max_columns = max((len(row) for row in header_rows), default=0)
    headers: list[str] = []

    for col in range(max_columns):
        parts: list[str] = []
        for row in header_rows:
            value = clean(row[col] if col < len(row) else None)
            if value:
                parts.append(value)
        headers.append(normalise(" ".join(parts)))

    return headers


def parse_section_rows(
    rows: list[tuple[Any, ...]],
    section: dict[str, Any],
    loca_id: str,
    mong_dis: str,
    remarks: str,
) -> list[list[str]]:
    output: list[list[str]] = []

    headers = section["headers"]
    time_col = find_header_col(headers, ["time", "date time", "datetime"])
    read_col = find_header_col(headers, ["reading", "minute", "read"])

    reading_columns: list[tuple[int, str, str]] = []

    for col, header in enumerate(headers):
        if col == time_col or col == read_col:
            continue

        mapped = map_header_to_reading(header)
        if mapped is not None:
            reading_columns.append((col, mapped[0], mapped[1]))

    for row_index in range(section["start"], section["end"]):
        row = rows[row_index]

        if row_is_blank(row):
            continue

        ref = clean(row[read_col]) if read_col is not None and read_col < len(row) else ""

        if ref and not is_allowed_time_reference(ref):
            continue

        date_time = format_datetime(row[time_col]) if time_col is not None and time_col < len(row) else ""

        if not date_time:
            continue

        for col, code, unit in reading_columns:
            value = row[col] if col < len(row) else None

            if not is_valid_reading(value):
                continue

            output.append(
                [
                    loca_id,
                    loca_id,
                    as_2dp(mong_dis),
                    date_time,
                    code,
                    "",
                    "",
                    format_reading(value),
                    unit,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    remarks,
                    "",
                ]
            )

    return output


def map_header_to_reading(header: str) -> tuple[str, str] | None:
    if not header:
        return None

    header = normalise(header)

    for key, mapped in READING_MAP.items():
        if key in header:
            return mapped

    return None


def find_header_col(headers: list[str], aliases: list[str]) -> int | None:
    for index, header in enumerate(headers):
        for alias in aliases:
            if alias in header:
                return index

    return None


def find_label_value(rows: list[tuple[Any, ...]], labels: list[str]) -> str:
    wanted = [normalise(label) for label in labels]

    for row in rows[:40]:
        for index, cell in enumerate(row):
            cell_text = normalise(cell)

            if not cell_text:
                continue

            if any(label in cell_text or cell_text in label for label in wanted):
                for offset in range(1, 5):
                    if index + offset < len(row):
                        value = clean(row[index + offset])
                        if value:
                            return value

    return ""


def infer_project_from_sources(source_workbooks: list[tuple[str, bytes]]) -> str:
    for name, _ in source_workbooks:
        match = re.search(r"\b(\d{4,8})\b", name)
        if match:
            return match.group(1)

    return ""


def build_ags_text(group_rows: dict[str, list[list[str]]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")

    for group in GROUP_ORDER:
        headings, units, types = GROUP_DEFS[group]

        writer.writerow(["GROUP", group])
        writer.writerow(["HEADING", *headings])
        writer.writerow(["UNIT", *units])
        writer.writerow(["TYPE", *types])

        for row in group_rows.get(group, []):
            writer.writerow(["DATA", *row])

        writer.writerow([])

    return output.getvalue().rstrip() + "\n"


def clean(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")

    text = str(value).strip()

    if text.startswith("#"):
        return ""

    if text.startswith("="):
        return ""

    return re.sub(r"\s+", " ", text).strip()


def normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", clean(value).lower()).strip()


def row_is_blank(row: tuple[Any, ...]) -> bool:
    return not any(clean(cell) for cell in row)


def is_allowed_time_reference(value: str) -> bool:
    ref = normalise(value)

    if not ref:
        return True

    if ref in {"1st", "first", "start", "initial"}:
        return True

    match = re.match(r"^(\d+)\s*(sec|secs|second|seconds|min|mins|minute|minutes)$", ref)

    if not match:
        return True

    amount = int(match.group(1))
    unit = match.group(2)

    if unit.startswith("sec"):
        return amount % 60 == 0

    return True


def format_datetime(value: Any) -> str:
    """
    MOND_DTIM target format for this transformer:
    DD/MM/YYYY hh:mm:ss
    """
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M:%S")

    raw = clean(value)

    if not raw:
        return ""

    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", raw)

    if match:
        day, month, year, hour, minute, second = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year} {int(hour):02d}:{int(minute):02d}:{int(second or 0):02d}"

    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2}):(\d{2})(?::(\d{2}))?", raw)

    if match:
        year, month, day, hour, minute, second = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year} {int(hour):02d}:{int(minute):02d}:{int(second or 0):02d}"

    return ""


def is_valid_reading(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped or stripped.startswith("#") or stripped.startswith("="):
            return False

    return clean(value) != ""


def format_reading(value: Any) -> str:
    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

        return f"{value:.10f}".rstrip("0").rstrip(".")

    return clean(value)


def as_2dp(value: Any) -> str:
    raw = clean(value)

    if not raw:
        return ""

    try:
        return f"{float(raw):.2f}"
    except ValueError:
        return raw
