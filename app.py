"""
Repo Agent Tracking — entry point.

Run: streamlit run app.py

GPS data: Google Sheet (set GOOGLE_SHEET_URL in .env) or Excel in Data-day-wise/.
Calculations and dashboards run in Streamlit — no API required.

Daily Operations Overview is the default leadership page in the sidebar.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Repo Agent Tracking",
    layout="wide",
    initial_sidebar_state="expanded",
)

tracking = st.Page("tracking.py", title="Repo Agent Tracking", icon="📍")
daily = st.Page("daily_overview.py", title="Daily Operations Overview", icon="📊", default=True)
admin = st.Page("admin_uploads.py", title="Admin uploads", icon="📤")

st.navigation([daily, tracking, admin]).run()
