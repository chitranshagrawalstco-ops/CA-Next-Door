# Render Deployment Guide (Free Plan)

## 1) Push code to GitHub
- Commit and push this project with:
  - `requirements.txt`
  - `render.yaml`
  - `Procfile`

## 2) Create Render service
- Open Render dashboard.
- Click `New +` -> `Web Service`.
- Connect your GitHub repo.
- Branch: your deployment branch.
- Render can auto-detect `render.yaml`, or set manually:
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`

## 3) Set environment variables in Render
- `SECRET_KEY`: any strong random string.
- `BACKEND_API_KEY`: strong secret key for client->backend auth.
- `GOOGLE_SHEET_ID`: spreadsheet ID.
- `GOOGLE_SHEET_TAB`: `users` (or your tab name).

Choose one Google auth mode:

### Mode A (Recommended): Service account JSON in env
- `GOOGLE_SERVICE_ACCOUNT_JSON`: paste full JSON content (single-line or multiline supported by Render).
- Do NOT set `GOOGLE_API_KEY`.

### Mode B: Google API key (read-only style)
- `GOOGLE_API_KEY`: your Google API key (`AIza...`).
- Do NOT set `GOOGLE_SERVICE_ACCOUNT_JSON`.

## 4) Google Sheet permissions

For Mode A:
- Share your sheet with service account email as `Editor`.

For Mode B:
- Ensure Sheets API key restrictions are correct.
- Sheet must be API-readable.

## 5) Deploy and get backend URL
- After deploy, copy Render URL:
  - Example: `https://your-service.onrender.com`
- Backend endpoint:
  - `https://your-service.onrender.com/api/v1/auth`

## 6) Configure desktop app clients
- In app admin panel (`/admin-panel`) set:
  - `Backend API URL` = `https://your-service.onrender.com/api/v1/auth`
  - `Backend API Key` = same `BACKEND_API_KEY`
- Clients no longer need Google JSON locally.

## 7) Test checklist
- Open app -> login with user credentials from sheet.
- Set a user `active/status = FALSE` in sheet -> relogin should fail.
- If drive connected, login should attempt cloud load.

## 8) Free plan notes
- Free services sleep when idle (cold start delay on first request).
- Keep secrets only in Render environment variables, never in git.
