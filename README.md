# Mochu's Monthly Productivity Dashboard - Streamlit

This Streamlit app recreates the Excel dashboard as a prettier web app with month/year selection, editable task list, daily checkboxes, monthly KPI cards, streaks, charts, focus lists, and monthly reflection notes.

## Free hosting + free online database

Recommended free stack:

1. **Database:** Supabase Free Plan
2. **Hosting:** Streamlit Community Cloud Free Plan

## Setup

### 1. Create Supabase database

Create a free Supabase project, open **SQL Editor**, paste the contents of `schema.sql`, and run it.

### 2. Add secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` locally and fill:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"
```

On Streamlit Cloud, add the same values under **App > Settings > Secrets**.

### 3. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 4. Deploy free

Push this folder to GitHub, then go to Streamlit Community Cloud and create a new app pointing to `app.py`.

## Notes

- If Supabase secrets are missing, the app runs in local SQLite demo mode using `mochu_local.db`. For hosted state persistence, use Supabase.
- Each month/year has its own saved task state and completion grid.
- Use **Clone previous month** to carry tasks forward into a new month.
