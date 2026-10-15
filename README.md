# Lead Ops — Month-on-Month Scorecard Dashboard

A shareable dashboard where each team member signs in with their **alias** and
sees **only their own** month-on-month scorecard. The manager (`gnraya`) can view
everyone, pick any individual, or see a whole-team overview.

## Files

| File | Purpose |
|------|---------|
| `dashboard.py` | The Streamlit app (UI + access control). |
| `scorecard_data.py` | Parses `Lead Ops Scorecard 2026.xlsx` into a clean table. |
| `Lead Ops Scorecard 2026.xlsx` | Your source workbook (data lives here). |
| `requirements.txt` | Python dependencies. |

## Run it locally

```powershell
cd "C:\Users\gnraya\Desktop\Lead Ops Scorecards V2"
py -m pip install -r requirements.txt
py -m streamlit run dashboard.py
```

Your browser opens at `http://localhost:8501`.

- Team members log in with their alias (e.g. `qrishraj`, `rashmiki`).
- You log in with `gnraya` to get the manager view.

## How access control works

- On login, the alias is checked against the aliases found in the workbook,
  plus the manager alias `gnraya`.
- A normal member only ever queries rows where `alias == their alias`, so they
  cannot see anyone else's numbers.
- The manager alias unlocks a sidebar dropdown to view any member or the team
  overview.
- To add more managers, edit `MANAGER_ALIASES` at the top of `dashboard.py`.

## Updating the data

Just update `Lead Ops Scorecard 2026.xlsx` (same folder) with new months or
people and refresh the dashboard — it re-reads the workbook. Each month sheet
must keep the same layout: metric-group headers in the top row, the
`Login | Name | Level | Goal/Actual/Achieved… | Overall | Stack Rank` sub-header
in the second row, and the member's **alias** in the `Name` column. New month
sheets should be named like the existing ones (`January`, `February`, …, `Aug`,
`Sep`, and `October`/`November`/`December` are already recognized).

## Sharing with the whole team

Two common options:

### Option A — Streamlit Community Cloud (free, easiest)
1. Put this folder in a GitHub repo (keep it **private** — it contains team data).
2. Go to <https://share.streamlit.io>, connect the repo, pick `dashboard.py`.
3. Share the resulting URL with the team.

### Option B — Internal server / your machine
Run with:
```powershell
py -m streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```
Team members on the same network open `http://<your-ip>:8501`.

## Security note (please read)

The alias login keeps each person scoped to their own card, but on its own it is
**not strong authentication** — someone who knows a colleague's alias could type
it in. For real protection when sharing externally, add one of:

- A single shared app password (Streamlit Community Cloud supports this, or add a
  password field in `dashboard.py`).
- Streamlit's native authentication / your company SSO in front of the app.

Ask and I can wire up a password gate or per-user passwords.
