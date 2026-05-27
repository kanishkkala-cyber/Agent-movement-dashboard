# Field Operations Dashboard (Streamlit)

**No API required.** GPS lat/long is read from your **Google Sheet** (or local Excel), calculations run in Python, and results show in Streamlit.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sidebar: **Daily Operations Overview** (default) · **Repo Agent Tracking** · **Admin uploads**

## Google Sheet setup (recommended)

1. In Google Sheets, use columns (names can vary slightly):
   - **Employee Name** (or Employee / Name)
   - **Time Stamp** (or Timestamp / Date Time)
   - **Latitude**
   - **Longitude**

2. Share the sheet: **Anyone with the link → Viewer** (or publish to web).

3. Copy the CSV export URL. Either:
   - Full URL in `.env`:
     ```env
     GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_ID/export?format=csv&gid=0
     ```
   - Or sheet ID + tab:
     ```env
     GOOGLE_SHEET_ID=your_id_here
     GOOGLE_SHEET_GID=0
     ```

4. Restart Streamlit (or click **Refresh data** on any page after you update the sheet).

Keka-style sheets with a title row and **Employee Number** header row are supported automatically.

## Local Excel (fallback)

If `GOOGLE_SHEET_URL` / `GOOGLE_SHEET_ID` is not set, the app reads `.xlsx` files from `Data-day-wise/` (upload via **Admin uploads**).

## Fixed sites (optional)

Place yard / service / store locations under `Site Locations/` — used for productive time and visit detection.

## Optional React UI

`field-ops-web/` + `api/` are **optional** and need a separate API server. Ignore them if you only use Streamlit + Google Sheets.
