"""
Admin only: upload Excel punch files. No map.
Counts come from files on disk — no database required.
"""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

from core import (
    DATA_SUBDIR,
    clear_punch_data_cache,
    delete_punch_file,
    google_sheet_export_url,
    list_punch_files,
    load_excel_from_path,
    load_punch_data_cached,
    preview_upload,
    punch_data_dir,
    punch_data_source_label,
    save_punch_upload,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SESSION_ADMIN_OK = "admin_authenticated"
ADMIN_PAGE_CSS = """
<style>
    [data-testid="stMain"] > div:first-child { padding-top: 0.75rem; }
</style>
"""


def _expected_pin() -> str:
    return os.environ.get("ADMIN_PIN", "TURNO@123")


def _require_admin() -> bool:
    if st.session_state.get(SESSION_ADMIN_OK):
        return True

    st.markdown(ADMIN_PAGE_CSS, unsafe_allow_html=True)
    st.title("Admin uploads")
    st.caption("Password required.")

    with st.form("admin_login"):
        pin = st.text_input("Password", type="password", autocomplete="off")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        if pin == _expected_pin():
            st.session_state[SESSION_ADMIN_OK] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


def _upload_panel() -> None:
    st.markdown(ADMIN_PAGE_CSS, unsafe_allow_html=True)
    st.title("Admin uploads")
    sheet_url = google_sheet_export_url()
    if sheet_url:
        st.info(
            f"GPS punches load from **Google Sheet** ({punch_data_source_label()}). "
            "Update the sheet in Google; use **Refresh data** on the overview or tracking page. "
            "Excel upload below is only used when no sheet URL is set in `.env`."
        )
        if st.button("Refresh sheet data now"):
            clear_punch_data_cache()
            st.rerun()
        st.divider()
    else:
        st.caption(
            "Optional: set `GOOGLE_SHEET_URL` in `.env` to load lat/long directly from Google Sheets. "
            "Otherwise upload Keka **.xlsx** files here."
        )

    top = st.columns([1, 1, 1])
    files = list_punch_files()
    n_files = len(files)
    try:
        df_all = load_punch_data_cached()
        n_rows = len(df_all)
    except Exception:
        n_rows = 0
    with top[0]:
        st.metric("Excel files on server" if not sheet_url else "Data source", "Google Sheet" if sheet_url else n_files)
    with top[1]:
        st.metric("Total punch rows", n_rows if n_rows else "—")
    with top[2]:
        if st.button("Sign out"):
            st.session_state.pop(SESSION_ADMIN_OK, None)
            st.rerun()

    if not sheet_url:
        st.divider()
        uploads = st.file_uploader(
            "Choose Excel file(s)",
            type=["xlsx"],
            accept_multiple_files=True,
            help="Microsoft Excel .xlsx only.",
        )

        if st.button("Submit uploads", type="primary", disabled=not uploads):
            if not uploads:
                st.warning("Choose at least one file first.")
            else:
                saved = 0
                for f in uploads:
                    raw = f.getvalue()
                    ok, msg, n = preview_upload(raw, f.name)
                    if not ok:
                        st.error(f"**{f.name}** — {msg}")
                        continue
                    dest = save_punch_upload(f.name, raw)
                    st.success(f"Saved **{dest.name}** ({n} valid punches).")
                    saved += 1
                if saved:
                    clear_punch_data_cache()
                    st.rerun()

    st.divider()
    st.subheader("Uploaded files")

    if sheet_url:
        st.caption("Local Excel files are ignored while Google Sheet URL is configured.")
        return

    if not files:
        st.info(f"No `.xlsx` in `{DATA_SUBDIR}/` yet.")
        return

    for path in files:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = stat.st_size / 1024
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{path.name}**")
            try:
                df = load_excel_from_path(path)
                st.caption(f"{len(df)} punches · {modified} · {size_kb:.0f} KB")
            except Exception as e:
                st.caption(f"Read error — {e}")
        with c2:
            if st.button("Delete", key=f"del_{path.name}"):
                delete_punch_file(path)
                clear_punch_data_cache()
                st.rerun()


def run() -> None:
    if not _require_admin():
        st.stop()
    _upload_panel()


run()
