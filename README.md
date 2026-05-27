# Agent Movement Dashboard

Field operations dashboard for GPS punch tracking (Keka Excel exports), leadership daily overview, and per-agent route analytics.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Data

- **GPS punches:** `Data-day-wise/*.xlsx`
- **Fixed sites:** `Site Locations/` (yards, service centres, stores)
- **Admin uploads:** sidebar → Admin uploads (password in `.env` or Streamlit secrets)

## Deploy

See **[DEPLOY.md](DEPLOY.md)** for Streamlit Community Cloud (recommended).
