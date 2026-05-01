from __future__ import annotations

import csv
from datetime import datetime
import io
from pathlib import Path
import tempfile
import zipfile

from .datasets import ABBR_SPEC, PROJ_SPEC, TRAN_SPEC, TYPE_SPEC, UNIT_SPEC
from .models import DatasetSpec, Issue, ProcessResult, SourceFile
from .profiles import get_profile
from .utils import (
    clean_ags_text,
    clean_by_type,
    find_input_column,
    infer_loca_id,
    infer_project_id,
    read_table,
)


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

DEFAULT_SETTINGS = {
    "tran_prod": "IGNE",
    "tran_stat": "Draft",
    "tran_desc": "Flowfinity export",
    "tran_recv": "Client",
    "tran_dlim": "|",
    "tran_rcon": "+",
    "default_loca_type": "TP",
    "default_loca_rem": "",
}


def collect_files(root: Path) -> list[Path]:
    files = []

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if "__MACOSX" not in path.parts:
                files.append(path)

    return sorted(files)


def detect_group_from_filename(path: Path, specs: list[DatasetSpec]) -> DatasetSpec | None:
    name = path.name.lower()

    for spec in specs:
        for pattern in spec.filename_patterns:
            if pattern.lower() in name:
                return spec

    return None


def normalise_dataframe(
    df,
    spec: DatasetSpec,
    path: Path,
    issues: list[Issue],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    inferred_project = infer_project_id(path)
    inferred_loca = infer_loca_id(path)

    project_col = find_input_column(df.columns, spec.aliases.get("PROJ_ID", []))
    loca_col = find_input_column(df.columns, spec.aliases.get("LOCA_ID", []))

    for index, source_row in df.iterrows():
        output: dict[str, str] = {}

        output["_PROJ_ID"] = clean_ags_text(source_row[project_col]) if project_col is not None else inferred_project
        output["_LOCA_ID"] = clean_ags_text(source_row[loca_col]) if loca_col is not None else inferred_loca

        if not output["_LOCA_ID"]:
            output["_LOCA_ID"] = inferred_loca

        for i, heading in enumerate(spec.headings):
            aliases = spec.aliases.get(heading, [heading])
            source_col = find_input_column(df.columns, aliases)

            ags_type = spec.types[i] if i < len(spec.types) else ""
            unit = spec.units[i] if i < len(spec.units) else ""

            if source_col is None:
                value = ""
            else:
                value = clean_by_type(source_row[source_col], ags_type, unit)

            if heading == "LOCA_ID" and not value:
                value = output["_LOCA_ID"]

            output[heading] = value

        if spec.group == "SAMP":
            if not output.get("SAMP_REF"):
                output["SAMP_REF"] = str(len(rows) + 1)

            if not output.get("SAMP_ID"):
                loca = output.get("LOCA_ID") or output["_LOCA_ID"]
                top = output.get("SAMP_TOP", "")
                stype = output.get("SAMP_TYPE", "S") or "S"
                ref = output.get("SAMP_REF", len(rows) + 1)
                top_token = str(top).replace(".", "")
                output["SAMP_ID"] = clean_ags_text(f"{loca}{top_token}{stype}{ref}")

        meaningful_values = [
            output.get(h, "")
            for h in spec.headings
            if h != "LOCA_ID"
        ]

        if not any(str(v).strip() for v in meaningful_values):
            continue

        location = output.get("LOCA_ID") or output.get("_LOCA_ID", "")

        for required_heading in spec.required:
            if not output.get(required_heading):
                issues.append(
                    Issue(
                        severity="warning",
                        group=spec.group,
                        file=path.name,
                        location=location,
                        message=f"Row {index + 2}: missing required value {required_heading}",
                    )
                )

        rows.append(output)

    return rows


def build_loca_rows(group_rows: dict[str, list[dict[str, str]]], settings: dict) -> list[dict[str, str]]:
    by_loca: dict[str, dict[str, str]] = {}

    for row in group_rows.get("LOCA", []):
        loca = row.get("LOCA_ID") or row.get("_LOCA_ID")
        if not loca:
            continue

        by_loca[loca] = {
            "LOCA_ID": loca,
            "LOCA_TYPE": row.get("LOCA_TYPE") or settings.get("default_loca_type", "TP"),
            "LOCA_REM": row.get("LOCA_REM") or settings.get("default_loca_rem", ""),
            "LOCA_FDEP": row.get("LOCA_FDEP", ""),
            "LOCA_STAR": row.get("LOCA_STAR", ""),
        }

    for group, rows in group_rows.items():
        if group == "LOCA":
            continue

        for row in rows:
            loca = row.get("LOCA_ID") or row.get("_LOCA_ID")
            if not loca:
                continue

            if loca not in by_loca:
                by_loca[loca] = {
                    "LOCA_ID": loca,
                    "LOCA_TYPE": settings.get("default_loca_type", "TP"),
                    "LOCA_REM": settings.get("default_loca_rem", ""),
                    "LOCA_FDEP": "",
                    "LOCA_STAR": "",
                }

    depth_fields = [
        ("GEOL", "GEOL_BASE"),
        ("DETL", "DETL_BASE"),
        ("BKFL", "BKFL_BASE"),
        ("HDPH", "HDPH_BASE"),
        ("SAMP", "SAMP_BASE"),
        ("IPID", "IPID_DPTH"),
        ("IVAN", "IVAN_DPTH"),
    ]

    for group, depth_heading in depth_fields:
        for row in group_rows.get(group, []):
            loca = row.get("LOCA_ID") or row.get("_LOCA_ID")
            if not loca or loca not in by_loca:
                continue

            try:
                depth = float(row.get(depth_heading, ""))
            except Exception:
                continue

            try:
                current = float(by_loca[loca].get("LOCA_FDEP", ""))
            except Exception:
                current = 0.0

            if depth > current:
                by_loca[loca]["LOCA_FDEP"] = f"{depth:.2f}"

    return [by_loca[k] for k in sorted(by_loca.keys())]


def build_project_row(group_rows: dict[str, list[dict[str, str]]], settings: dict) -> list[str]:
    project_id = settings.get("project_id", "").strip()
    project_name = settings.get("project_name", "").strip()

    if not project_id:
        for rows in group_rows.values():
            for row in rows:
                project_id = row.get("_PROJ_ID", "")
                if project_id:
                    break
            if project_id:
                break

    project_id = project_id or "UNKNOWN_PROJECT"
    project_name = project_name or project_id

    return [
        clean_ags_text(project_id),
        clean_ags_text(project_name),
        clean_ags_text(settings.get("project_location", "")),
        clean_ags_text(settings.get("project_client", "")),
        clean_ags_text(settings.get("project_contractor", "")),
        clean_ags_text(settings.get("project_engineer", "")),
        clean_ags_text(settings.get("project_memo", "")),
        "",
    ]


def build_trans_row(settings: dict, ags_version: str) -> list[str]:
    today = datetime.today().strftime("%Y-%m-%d")

    return [
        "1",
        today,
        clean_ags_text(settings.get("tran_prod", "IGNE")),
        clean_ags_text(settings.get("tran_stat", "Draft")),
        clean_ags_text(settings.get("tran_desc", "Flowfinity export")),
        clean_ags_text(ags_version),
        clean_ags_text(settings.get("tran_recv", "Client")),
        clean_ags_text(settings.get("tran_dlim", "|")),
        clean_ags_text(settings.get("tran_rcon", "+")),
        "",
        "",
    ]


def unit_rows() -> list[list[str]]:
    return [
        ["m", "metres", ""],
        ["kPa", "kilopascal", ""],
        ["ppmv", "parts per million by volume", ""],
        ["yyyy-mm-dd", "date format", ""],
    ]


def type_rows() -> list[list[str]]:
    return [
        ["ID", "Unique Identifier", ""],
        ["X", "Text", ""],
        ["XN", "Numeric value", ""],
        ["PA", "Pick list text listed in ABBR Group", ""],
        ["PT", "Pick list text listed in TYPE Group", ""],
        ["PU", "Pick list text listed in UNIT Group", ""],
        ["RL", "Record link", ""],
        ["2DP", "Value; required number of decimal places, 2", ""],
        ["DT", "Date time in international format", ""],
    ]


def abbr_rows() -> list[list[str]]:
    return [
        ["LOCA_TYPE", "TP", "Trial pit", "AGS4", "", ""],
        ["LOCA_TYPE", "BH", "Borehole", "AGS4", "", ""],
        ["LOCA_TYPE", "WS", "Window sample", "AGS4", "", ""],
        ["LOCA_STAT", "DRAFT", "Draft", "AGS4", "", ""],
        ["HDPH_TYPE", "TP", "Trial pit", "AGS4", "", ""],
        ["SAMP_TYPE", "B", "Bulk sample", "AGS4", "", ""],
        ["SAMP_TYPE", "D", "Disturbed sample", "AGS4", "", ""],
        ["SAMP_TYPE", "ES", "Environmental sample", "AGS4", "", ""],
    ]


def write_group(writer, spec: DatasetSpec, rows: list[list[str]]):
    writer.writerow(["GROUP", spec.group])
    writer.writerow(["HEADING", *spec.headings])
    writer.writerow(["UNIT", *spec.units])
    writer.writerow(["TYPE", *spec.types])

    for row in rows:
        writer.writerow(["DATA", *row])

    writer.writerow([])


def write_dataset_group(writer, spec: DatasetSpec, row_dicts: list[dict[str, str]]):
    data_rows = []

    for row in row_dicts:
        data_rows.append([row.get(h, "") for h in spec.headings])

    write_group(writer, spec, data_rows)


def build_ags_text(
    group_rows: dict[str, list[dict[str, str]]],
    settings: dict,
    profile_name: str,
    specs: list[DatasetSpec],
) -> str:
    ags_version, _ = get_profile(profile_name)

    output = io.StringIO()

    writer = csv.writer(
        output,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_ALL,
        lineterminator="\r\n",
    )

    write_group(writer, PROJ_SPEC, [build_project_row(group_rows, settings)])
    write_group(writer, TRAN_SPEC, [build_trans_row(settings, ags_version)])
    write_group(writer, UNIT_SPEC, unit_rows())
    write_group(writer, TYPE_SPEC, type_rows())
    write_group(writer, ABBR_SPEC, abbr_rows())

    group_rows = dict(group_rows)
    group_rows["LOCA"] = build_loca_rows(group_rows, settings)

    for spec in specs:
        rows = group_rows.get(spec.group, [])
        if rows:
            write_dataset_group(writer, spec, rows)

    return output.getvalue()


def run_from_folder(
    root: Path,
    settings: dict | None = None,
    profile_name: str = "AGS 4.0 compact",
) -> ProcessResult:
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    ags_version, specs = get_profile(profile_name)

    files = collect_files(root)
    group_rows: dict[str, list[dict[str, str]]] = {spec.group: [] for spec in specs}
    issues: list[Issue] = []
    skipped_files: list[str] = []
    source_files: list[SourceFile] = []

    for path in files:
        spec = detect_group_from_filename(path, specs)

        if spec is None:
            skipped_files.append(str(path.relative_to(root)))
            continue

        try:
            df = read_table(path)
            rows = normalise_dataframe(df, spec, path, issues)
            group_rows[spec.group].extend(rows)

            project_id = rows[0].get("_PROJ_ID", infer_project_id(path)) if rows else infer_project_id(path)
            loca_id = rows[0].get("_LOCA_ID", infer_loca_id(path)) if rows else infer_loca_id(path)

            source_files.append(
                SourceFile(
                    file_name=path.name,
                    relative_path=str(path.relative_to(root)),
                    group=spec.group,
                    project_id=project_id,
                    loca_id=loca_id,
                    rows=len(rows),
                )
            )

        except Exception as exc:
            issues.append(
                Issue(
                    severity="error",
                    group=spec.group,
                    file=path.name,
                    location=infer_loca_id(path),
                    message=str(exc),
                )
            )

    ags_text = build_ags_text(group_rows, settings, profile_name, specs)

    group_counts = {group: len(rows) for group, rows in group_rows.items()}
    location_counts: dict[str, int] = {}
    project_counts: dict[str, int] = {}

    loca_rows = build_loca_rows(group_rows, settings)

    for row in loca_rows:
        loca = row.get("LOCA_ID", "")
        if loca:
            location_counts[loca] = location_counts.get(loca, 0) + 1

    for rows in group_rows.values():
        for row in rows:
            proj = row.get("_PROJ_ID", "UNKNOWN_PROJECT")
            project_counts[proj] = project_counts.get(proj, 0) + 1

    summary = {
        "ags_profile": profile_name,
        "ags_version": ags_version,
        "files_found": len(files),
        "files_used": len(source_files),
        "files_skipped": len(skipped_files),
        "groups_with_rows": sum(1 for count in group_counts.values() if count > 0),
        "locations": len(loca_rows),
        "projects": len(project_counts) if project_counts else 1,
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


def run_from_zip_bytes(
    zip_bytes: bytes,
    settings: dict | None = None,
    profile_name: str = "AGS 4.0 compact",
) -> ProcessResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "upload.zip"

        zip_path.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path / "extract")

        return run_from_folder(tmp_path / "extract", settings, profile_name)
