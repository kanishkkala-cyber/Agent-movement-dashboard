# Deploy on Streamlit Community Cloud (Excel data)

This app is **Streamlit-only** for production. Data comes from **`Data-day-wise/*.xlsx`** on the server (no Google Sheets, no separate API).

## What gets deployed

| Include in Git repo | Purpose |
|---------------------|---------|
| `app.py`, `*.py` | Application |
| `requirements.txt`, `runtime.txt` | Python deps (3.11) |
| `.streamlit/config.toml` | Server settings |
| `Data-day-wise/*.xlsx` | GPS punch data (~2 MB) |
| `Site Locations/*.xlsx` | Yard / service / store sites |

| Do **not** commit | |
|-------------------|---|
| `.env`, `.streamlit/secrets.toml` | Secrets |
| `field-ops-web/node_modules/` | Optional React UI |
| `__pycache__/` | Cache |

---

## Step 1 — Install Git (one time)

Git is required to push code to GitHub.

1. Download: https://git-scm.com/download/win  
2. Install with defaults.  
3. Restart Cursor / PowerShell.

Verify:

```powershell
git --version
```

---

## Step 2 — Create a GitHub repository

1. Go to https://github.com/new  
2. Name e.g. `agent-movement-dashboard`  
3. **Private** recommended (employee GPS data).  
4. Do **not** add README if you already have one locally.

---

## Step 3 — Push this project to GitHub

In PowerShell:

```powershell
cd "C:\Users\Kanishk Kala\Downloads\Agent Movement Dashboard"

git init
git add app.py *.py requirements.txt runtime.txt README.md DEPLOY.md FIELD_OPS.md .gitignore
git add .streamlit/config.toml .streamlit/secrets.toml.example .streamlit/credentials.toml
git add "Data-day-wise"
git add "Site Locations"
git add responsive_ui.py

git commit -m "Initial deploy: Streamlit field ops dashboard"

git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/agent-movement-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` and repo name with yours.

---

## Step 4 — Deploy on Streamlit Community Cloud

1. Sign in: https://share.streamlit.io  
2. **Create app** → pick your GitHub repo.  
3. **Main file path:** `app.py`  
4. **Branch:** `main`  
5. **App URL:** choose a subdomain (e.g. `turno-field-ops`).  
6. **Advanced settings → Python version:** 3.11 (matches `runtime.txt`).

### Secrets (required)

App → **Settings** → **Secrets** → paste:

```toml
ADMIN_PIN = "your-strong-password-here"
```

Save. Reboot app if prompted.

### First deploy

- Build takes 2–5 minutes.  
- Open the app URL.  
- Default page: **Daily Operations Overview**.  
- **Repo Agent Tracking** for maps.  
- **Admin uploads** uses `ADMIN_PIN`.

---

## Step 5 — Updating data after deploy

**Option A — Git (recommended for fixed snapshots)**  
Add new `.xlsx` under `Data-day-wise/`, commit, push. Cloud redeploys automatically.

**Option B — Admin uploads (no Git)**  
Sidebar → Admin uploads → sign in → upload `.xlsx`.  
Files are stored on the app container. They may be **lost on redeploy** unless the platform keeps persistent disk—prefer Git for production.

After new files: use **Refresh data** on Overview / Tracking pages.

---

## Local secrets (optional)

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Edit ADMIN_PIN in secrets.toml
```

Or use `.env`:

```
ADMIN_PIN=your-password
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on import | Check `requirements.txt`; Python 3.11 on Cloud |
| No data / empty dashboard | Ensure `Data-day-wise/` is in the repo and contains `.xlsx` |
| No visits / sites | Ensure `Site Locations/` xlsx files are in the repo |
| Admin login fails | Set `ADMIN_PIN` in Cloud **Secrets** exactly (reboot app) |
| Stale numbers | Click **Refresh data** or redeploy |
| Repo too large | You are ~2 MB today—fine for GitHub |

---

## Security notes

- Use a **private** GitHub repo.  
- Use a **strong** `ADMIN_PIN`.  
- Overview and Tracking are **not** login-protected today—anyone with the public Streamlit URL can view data. For production, add Streamlit authentication or restrict access via Streamlit Cloud sharing settings / SSO (Teams plan).

---

## Optional: VM / Docker instead of Cloud

If you cannot use GitHub, host on a Windows/Linux VM:

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Place `Data-day-wise/` and `Site Locations/` next to the app. Use a reverse proxy (nginx) + HTTPS for production.
