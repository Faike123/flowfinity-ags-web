from __future__ import annotations

import pandas as pd
import streamlit as st

from flowfinity_ags.engine import DEFAULT_SETTINGS, run_from_zip_bytes
from flowfinity_ags.profiles import AGS_PROFILE_OPTIONS


st.set_page_config(
    page_title="Flowfinity Dump to AGS",
    page_icon="🧪",
    layout="wide",
)

st.title("Flowfinity Dump → AGS Exporter")
st.caption("Upload ZIP → select detected project → inspect groups/locations/files → export AGS.")

with st.sidebar:
    st.header("1. AGS export profile")

    profile_name = st.selectbox(
        "Selected AGS format",
        AGS_PROFILE_OPTIONS,
        index=0,
    )

    st.caption(
        "Current profiles are compact Flowfinity export profiles. "
        "Full official AGS heading profiles can be added later."
    )

    st.divider()
    st.header("2. TRAN metadata")

    tran_prod = st.text_input("TRAN_PROD", value=DEFAULT_SETTINGS["tran_prod"])
    tran_stat = st.text_input("TRAN_STAT", value=DEFAULT_SETTINGS["tran_stat"])
    tran_desc = st.text_input("TRAN_DESC", value=DEFAULT_SETTINGS["tran_desc"])
    tran_recv = st.text_input("TRAN_RECV", value=DEFAULT_SETTINGS["tran_recv"])
    tran_dlim = st.text_input("TRAN_DLIM", value=DEFAULT_SETTINGS["tran_dlim"])
    tran_rcon = st.text_input("TRAN_RCON", value=DEFAULT_SETTINGS["tran_rcon"])

    st.divider()
    st.header("3. Location defaults")

    default_loca_type = st.text_input("Default LOCA_TYPE", value=DEFAULT_SETTINGS["default_loca_type"])
    default_loca_rem = st.text_input("Default LOCA_REM", value=DEFAULT_SETTINGS["default_loca_rem"])


base_settings = {
    "tran_prod": tran_prod,
    "tran_stat": tran_stat,
    "tran_desc": tran_desc,
    "tran_recv": tran_recv,
    "tran_dlim": tran_dlim,
    "tran_rcon": tran_rcon,
    "default_loca_type": default_loca_type,
    "default_loca_rem": default_loca_rem,
}


uploaded = st.file_uploader(
    "Upload Flowfinity ZIP",
    type=["zip"],
    accept_multiple_files=False,
)

if uploaded is None:
    st.info("Upload one ZIP containing the Flowfinity export folders/files.")
    st.stop()


process_clicked = st.button("Process ZIP", type="primary")

if process_clicked:
    with st.spinner("Reading ZIP and detecting projects, locations and groups..."):
        result = run_from_zip_bytes(
            uploaded.getvalue(),
            settings=base_settings,
            profile_name=profile_name,
        )

    st.session_state["result"] = result
    st.session_state["profile_name"] = profile_name
    st.session_state["uploaded_zip_bytes"] = uploaded.getvalue()


result = st.session_state.get("result")

if result is None:
    st.stop()


# ============================================================
# SOURCE FILE DATAFRAME
# ============================================================

source_file_rows = [
    {
        "File": f.file_name,
        "Path": f.relative_path,
        "Group": f.group,
        "Project": f.project_id,
        "LOCA_ID": f.loca_id,
        "Rows": f.rows,
    }
    for f in result.source_files
]

files_df = pd.DataFrame(source_file_rows)

if files_df.empty:
    st.error("No supported Flowfinity files were detected.")
    st.stop()


project_ids = sorted(files_df["Project"].dropna().astype(str).unique().tolist())

st.subheader("Detected projects")

project_summary_df = (
    files_df.groupby("Project", dropna=False)
    .agg(
        Files=("File", "count"),
        Locations=("LOCA_ID", "nunique"),
        Groups=("Group", "nunique"),
        Rows=("Rows", "sum"),
    )
    .reset_index()
    .sort_values("Project")
)

st.dataframe(project_summary_df, use_container_width=True, hide_index=True)

selected_project = st.selectbox(
    "Select project to inspect",
    project_ids,
    index=0,
)

project_files_df = files_df[files_df["Project"].astype(str) == str(selected_project)].copy()

summary = result.summary

project_file_count = len(project_files_df)
project_location_count = project_files_df["LOCA_ID"].nunique()
project_group_count = project_files_df["Group"].nunique()
project_row_count = int(project_files_df["Rows"].sum())

st.subheader(f"Project view: {selected_project}")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("AGS version", summary["ags_version"])
col2.metric("Files used", project_file_count)
col3.metric("Locations", project_location_count)
col4.metric("Groups", project_group_count)
col5.metric("Rows", project_row_count)
col6.metric("Total ZIP files", summary["files_found"])

st.divider()


# ============================================================
# PROJECT METADATA REVIEW
# ============================================================

st.subheader("Selected project metadata")

metadata_df = pd.DataFrame(
    [
        {
            "PROJ_ID": selected_project,
            "PROJ_NAME": selected_project,
            "PROJ_LOC": "",
            "PROJ_CLNT": "",
            "PROJ_CONT": "",
            "PROJ_ENG": "",
            "PROJ_MEMO": "",
        }
    ]
)

edited_metadata_df = st.data_editor(
    metadata_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key=f"project_metadata_editor_{selected_project}",
)

selected_project_metadata = edited_metadata_df.iloc[0].to_dict() if not edited_metadata_df.empty else {}

export_settings = {
    **base_settings,
    "project_id": selected_project_metadata.get("PROJ_ID", ""),
    "project_name": selected_project_metadata.get("PROJ_NAME", ""),
    "project_location": selected_project_metadata.get("PROJ_LOC", ""),
    "project_client": selected_project_metadata.get("PROJ_CLNT", ""),
    "project_contractor": selected_project_metadata.get("PROJ_CONT", ""),
    "project_engineer": selected_project_metadata.get("PROJ_ENG", ""),
    "project_memo": selected_project_metadata.get("PROJ_MEMO", ""),
}

st.caption(
    "The UI is now project-aware. Export is still currently one combined AGS rebuilt with the selected project metadata. "
    "Next step is true per-project AGS export."
)

rebuild_clicked = st.button("Rebuild AGS with selected project metadata")

if rebuild_clicked:
    zip_bytes = st.session_state.get("uploaded_zip_bytes")

    if zip_bytes:
        with st.spinner("Rebuilding AGS with selected project metadata..."):
            result = run_from_zip_bytes(
                zip_bytes,
                settings=export_settings,
                profile_name=profile_name,
            )

        st.session_state["result"] = result
        st.success("AGS rebuilt with selected project metadata.")
        st.rerun()


# ============================================================
# PROJECT-SCOPED TABS
# ============================================================

tab_groups, tab_locations, tab_files, tab_issues, tab_export = st.tabs(
    ["Detected groups", "Locations", "Source files", "Issues", "Export"]
)


with tab_groups:
    st.subheader(f"Detected AGS groups for project {selected_project}")

    group_df = (
        project_files_df.groupby("Group", dropna=False)
        .agg(
            Files=("File", "count"),
            Locations=("LOCA_ID", "nunique"),
            Rows=("Rows", "sum"),
        )
        .reset_index()
        .sort_values("Group")
    )

    st.dataframe(group_df, use_container_width=True, hide_index=True)


with tab_locations:
    st.subheader(f"Detected locations for project {selected_project}")

    location_df = (
        project_files_df.groupby("LOCA_ID", dropna=False)
        .agg(
            Files=("File", "count"),
            Groups=("Group", "nunique"),
            Rows=("Rows", "sum"),
        )
        .reset_index()
        .sort_values("LOCA_ID")
    )

    st.dataframe(location_df, use_container_width=True, hide_index=True)

    selected_location_options = location_df["LOCA_ID"].dropna().astype(str).tolist()

    if selected_location_options:
        selected_location = st.selectbox(
            "Select location to inspect",
            selected_location_options,
            index=0,
        )

        location_files_df = project_files_df[
            project_files_df["LOCA_ID"].astype(str) == str(selected_location)
        ]

        st.markdown(f"### Location view: `{selected_location}`")

        location_group_df = (
            location_files_df.groupby("Group", dropna=False)
            .agg(
                Files=("File", "count"),
                Rows=("Rows", "sum"),
            )
            .reset_index()
            .sort_values("Group")
        )

        st.dataframe(location_group_df, use_container_width=True, hide_index=True)


with tab_files:
    st.subheader(f"Source files for project {selected_project}")

    st.dataframe(
        project_files_df.sort_values(["LOCA_ID", "Group", "File"]),
        use_container_width=True,
        hide_index=True,
    )

    if result.skipped_files:
        with st.expander("Skipped files from full ZIP"):
            for skipped in result.skipped_files:
                st.write(skipped)


with tab_issues:
    st.subheader(f"Issues for project {selected_project}")

    issue_rows = [
        {
            "Severity": issue.severity,
            "Group": issue.group,
            "Location": issue.location,
            "File": issue.file,
            "Message": issue.message,
        }
        for issue in result.issues
    ]

    issues_df = pd.DataFrame(issue_rows)

    if issues_df.empty:
        st.success("No processing issues detected.")
    else:
        project_loca_ids = set(project_files_df["LOCA_ID"].astype(str).tolist())
        project_issue_df = issues_df[
            issues_df["Location"].astype(str).isin(project_loca_ids)
        ]

        if project_issue_df.empty:
            st.success("No processing issues detected for this project.")
        else:
            st.dataframe(project_issue_df, use_container_width=True, hide_index=True)


with tab_export:
    st.subheader("Export AGS")

    st.warning(
        "Current export still creates one combined AGS from the full ZIP. "
        "The next engine patch will allow true export of only the selected project."
    )

    project_token = export_settings.get("project_id", "").strip() or str(selected_project)
    selected_profile = st.session_state.get("profile_name", profile_name).replace(" ", "_").replace(".", "_")
    filename = f"{project_token}_{selected_profile}.ags"

    st.download_button(
        label="Download AGS file",
        data=result.ags_text.encode("utf-8"),
        file_name=filename,
        mime="text/plain",
        type="primary",
    )

    with st.expander("Preview first 20,000 characters"):
        st.code(result.ags_text[:20000], language="text")
