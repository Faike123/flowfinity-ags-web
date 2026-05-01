from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    group: str
    filename_patterns: list[str]
    headings: list[str]
    units: list[str]
    types: list[str]
    aliases: dict[str, list[str]]
    required: list[str] = field(default_factory=list)


@dataclass
class Issue:
    severity: str
    group: str
    file: str
    location: str
    message: str


@dataclass
class SourceFile:
    file_name: str
    relative_path: str
    group: str
    project_id: str
    loca_id: str
    rows: int


@dataclass
class ProcessResult:
    ags_text: str
    summary: dict[str, Any]
    group_counts: dict[str, int]
    location_counts: dict[str, int]
    project_counts: dict[str, int]
    source_files: list[SourceFile]
    issues: list[Issue]
    skipped_files: list[str]
