from .models import DatasetSpec


COMMON_PROJECT_ALIASES = [
    "PROJ_ID",
    "project_id",
    "project number",
    "project no",
    "project ref",
    "Project Number",
    "Project No",
]

COMMON_LOCATION_ALIASES = [
    "LOCA_ID",
    "Location ID",
    "LOCAID",
    "TP ID",
    "Trial Pit ID",
    "Exploratory Hole ID",
    "Location",
    "Hole ID",
]


PROJ_SPEC = DatasetSpec(
    group="PROJ",
    filename_patterns=[],
    headings=["PROJ_ID", "PROJ_NAME", "PROJ_LOC", "PROJ_CLNT", "PROJ_CONT", "PROJ_ENG", "PROJ_MEMO", "FILE_FSET"],
    units=["", "", "", "", "", "", "", ""],
    types=["ID", "X", "X", "X", "X", "X", "X", "X"],
    aliases={},
)

TRAN_SPEC = DatasetSpec(
    group="TRAN",
    filename_patterns=[],
    headings=["TRAN_ISNO", "TRAN_DATE", "TRAN_PROD", "TRAN_STAT", "TRAN_DESC", "TRAN_AGS", "TRAN_RECV", "TRAN_DLIM", "TRAN_RCON", "TRAN_REM", "FILE_FSET"],
    units=["", "yyyy-mm-dd", "", "", "", "", "", "", "", "", ""],
    types=["X", "DT", "X", "X", "X", "X", "X", "X", "X", "X", "X"],
    aliases={},
)

UNIT_SPEC = DatasetSpec(
    group="UNIT",
    filename_patterns=[],
    headings=["UNIT_UNIT", "UNIT_DESC", "FILE_FSET"],
    units=["", "", ""],
    types=["X", "X", "X"],
    aliases={},
)

TYPE_SPEC = DatasetSpec(
    group="TYPE",
    filename_patterns=[],
    headings=["TYPE_TYPE", "TYPE_DESC", "FILE_FSET"],
    units=["", "", ""],
    types=["X", "X", "X"],
    aliases={},
)

ABBR_SPEC = DatasetSpec(
    group="ABBR",
    filename_patterns=[],
    headings=["ABBR_HDNG", "ABBR_CODE", "ABBR_DESC", "ABBR_LIST", "ABBR_REM", "FILE_FSET"],
    units=["", "", "", "", "", ""],
    types=["X", "X", "X", "X", "X", "X"],
    aliases={},
)


LOCA_SPEC = DatasetSpec(
    group="LOCA",
    filename_patterns=["LOCA", "LOCALocationDetails", "LocationDetails", "LOCATION"],
    headings=["LOCA_ID", "LOCA_TYPE", "LOCA_REM", "LOCA_FDEP", "LOCA_STAR"],
    units=["", "", "", "m", "yyyy-mm-dd"],
    types=["ID", "PA", "X", "2DP", "DT"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "LOCA_TYPE": ["LOCA_TYPE", "Location Type", "Exploratory Hole Type", "Type"],
        "LOCA_REM": ["LOCA_REM", "Remarks", "Remark", "Comments", "Notes"],
        "LOCA_FDEP": ["LOCA_FDEP", "Final Depth", "final_depth", "Terminated Pit Depth (m)", "Depth", "Base"],
        "LOCA_STAR": ["LOCA_STAR", "Start Date", "Date", "Date & Time", "Created on", "Submission time"],
    },
    required=["LOCA_ID"],
)

HDPH_SPEC = DatasetSpec(
    group="HDPH",
    filename_patterns=["HDPH", "DepthRelatedExploratory"],
    headings=["LOCA_ID", "HDPH_TOP", "HDPH_BASE", "HDPH_TYPE", "HDPH_STAR", "HDPH_EXC", "HDPH_DIML", "HDPH_DIMW"],
    units=["", "m", "m", "", "yyyy-mm-dd", "", "m", "m"],
    types=["ID", "2DP", "2DP", "PA", "DT", "X", "2DP", "2DP"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "HDPH_TOP": ["HDPH_TOP", "top_depth", "top", "from", "depth_from", "Pit Top Depth (m)"],
        "HDPH_BASE": ["HDPH_BASE", "base_depth", "base", "to", "depth_to", "Terminated Pit Depth (m)"],
        "HDPH_TYPE": ["HDPH_TYPE", "type", "Exploratory Hole Type"],
        "HDPH_STAR": ["HDPH_STAR", "Start Date", "Date", "Date & Time"],
        "HDPH_EXC": ["HDPH_EXC", "plant used", "Plant Used", "Excavator"],
        "HDPH_DIML": ["HDPH_DIML", "length", "pit_trench_length", "Pit Length", "Trial Pit Length"],
        "HDPH_DIMW": ["HDPH_DIMW", "width", "pit_trench_width", "Pit Width", "Trial Pit Width"],
    },
    required=["LOCA_ID"],
)

GEOL_SPEC = DatasetSpec(
    group="GEOL",
    filename_patterns=["GEOL", "geologicaldescriptions", "Geology"],
    headings=["LOCA_ID", "GEOL_TOP", "GEOL_BASE", "GEOL_DESC"],
    units=["", "m", "m", ""],
    types=["ID", "2DP", "2DP", "X"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "GEOL_TOP": ["GEOL_TOP", "top_depth", "top", "from", "depth_from", "Depth From", "Top Depth"],
        "GEOL_BASE": ["GEOL_BASE", "base_depth", "base", "to", "depth_to", "Depth To", "Base Depth"],
        "GEOL_DESC": ["GEOL_DESC", "description", "desc", "strata", "soil description", "details", "Geological Description"],
    },
    required=["LOCA_ID"],
)

DETL_SPEC = DatasetSpec(
    group="DETL",
    filename_patterns=["DETL", "StratumDetailDescriptions", "Detail"],
    headings=["LOCA_ID", "DETL_TOP", "DETL_BASE", "DETL_DESC"],
    units=["", "m", "m", ""],
    types=["ID", "2DP", "2DP", "X"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "DETL_TOP": ["DETL_TOP", "top_depth", "top", "from", "depth_from"],
        "DETL_BASE": ["DETL_BASE", "base_depth", "base", "to", "depth_to"],
        "DETL_DESC": ["DETL_DESC", "description", "desc", "strata", "soil description", "details"],
    },
    required=["LOCA_ID"],
)

BKFL_SPEC = DatasetSpec(
    group="BKFL",
    filename_patterns=["BKFL", "Backfill", "Backfiill"],
    headings=["LOCA_ID", "BKFL_TOP", "BKFL_BASE", "BKFL_DESC"],
    units=["", "m", "m", ""],
    types=["ID", "2DP", "2DP", "X"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "BKFL_TOP": ["BKFL_TOP", "top_depth", "top", "from", "depth_from", "Pit Top Depth (m)"],
        "BKFL_BASE": ["BKFL_BASE", "base_depth", "base", "to", "depth_to", "Terminated Pit Depth (m)"],
        "BKFL_DESC": ["BKFL_DESC", "description", "desc", "Pit Backfiill Details", "Pit Backfill Details"],
    },
    required=["LOCA_ID"],
)

SAMP_SPEC = DatasetSpec(
    group="SAMP",
    filename_patterns=["SAMP", "Samples"],
    headings=["LOCA_ID", "SAMP_TOP", "SAMP_REF", "SAMP_TYPE", "SAMP_ID", "SAMP_BASE"],
    units=["", "m", "", "", "", "m"],
    types=["ID", "2DP", "X", "PA", "ID", "2DP"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "SAMP_TOP": ["SAMP_TOP", "top_depth", "top", "from", "depth_from", "Sample Top"],
        "SAMP_REF": ["SAMP_REF", "reference", "Sample reference", "Sample Ref"],
        "SAMP_TYPE": ["SAMP_TYPE", "type", "Sample Type"],
        "SAMP_ID": ["SAMP_ID", "sample_ID", "Sample ID", "sample id"],
        "SAMP_BASE": ["SAMP_BASE", "base_depth", "base", "to", "depth_to", "Sample Base"],
    },
    required=["LOCA_ID"],
)

IPID_SPEC = DatasetSpec(
    group="IPID",
    filename_patterns=["IPID", "PID", "PhotoIonisationDetector"],
    headings=["LOCA_ID", "IPID_DPTH", "IPID_TESN", "IPID_DATE", "IPID_RES"],
    units=["", "m", "", "yyyy-mm-dd", "ppmv"],
    types=["ID", "2DP", "X", "DT", "XN"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "IPID_DPTH": ["IPID_DPTH", "depth", "base_depth", "base", "to", "depth_to"],
        "IPID_TESN": ["IPID_TESN", "reference", "test reference", "Test reference"],
        "IPID_DATE": ["IPID_DATE", "date", "Date"],
        "IPID_RES": ["IPID_RES", "result", "PID result", "PID", "Reading"],
    },
    required=["LOCA_ID"],
)

IVAN_SPEC = DatasetSpec(
    group="IVAN",
    filename_patterns=["IVAN", "HandVane", "Vane"],
    headings=["LOCA_ID", "IVAN_DPTH", "IVAN_TESN", "IVAN_TYPE", "IVAN_IVAN", "IVAN_IVAR", "IVAN_DATE"],
    units=["", "m", "", "", "kPa", "kPa", "yyyy-mm-dd"],
    types=["ID", "2DP", "X", "PA", "XN", "XN", "DT"],
    aliases={
        "PROJ_ID": COMMON_PROJECT_ALIASES,
        "LOCA_ID": COMMON_LOCATION_ALIASES,
        "IVAN_DPTH": ["IVAN_DPTH", "depth", "base_depth", "base", "to", "depth_to"],
        "IVAN_TESN": ["IVAN_TESN", "Test reference", "reference"],
        "IVAN_TYPE": ["IVAN_TYPE", "vane type", "Vane type"],
        "IVAN_IVAN": ["IVAN_IVAN", "vane result", "test result", "Vane result", "Test result"],
        "IVAN_IVAR": ["IVAN_IVAR", "vane residual result", "test residual result", "Vane residual result", "Test residual result"],
        "IVAN_DATE": ["IVAN_DATE", "date", "Date"],
    },
    required=["LOCA_ID"],
)


BASE_DATASET_SPECS = [
    LOCA_SPEC,
    HDPH_SPEC,
    GEOL_SPEC,
    DETL_SPEC,
    BKFL_SPEC,
    SAMP_SPEC,
    IPID_SPEC,
    IVAN_SPEC,
]
