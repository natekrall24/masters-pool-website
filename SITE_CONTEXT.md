# Slot Masters Pool — Site Context for Developers

## Overview

A Flask web app for running a Masters golf fantasy pool. Entrants pick 6 players within a $50,000 cost cap, submit their roster, and follow along on a leaderboard during the tournament. Submissions are stored in a Google Sheet. The site has two modes controlled by an environment variable.

**Live URL:** slotmasterspool.com  
**GitHub repo:** (your repo URL here)  
**Hosting:** Railway (auto-deploys on push to main)  
**Domain registrar:** Squarespace  

---

## Tech Stack

- **Backend:** Flask (Python), served via Gunicorn
- **Frontend:** Jinja2 templates, vanilla HTML/CSS, vanilla JS
- **Data storage:** Google Sheets via `gspread` + Google Cloud service account
- **Email:** SendGrid (via Twilio) for confirmation emails
- **Deployment:** Railway

---

## File Structure

```
slot-masters-pool/
├── app.py                  # Flask app, all routes
├── config.py               # SITE_MODE, player data, sheet/embed URLs
├── requirements.txt
├── Procfile                # gunicorn app:app
├── credentials.json        # Google service account (gitignored, local only)
├── .gitignore
├── static/
│   ├── style.css
│   ├── roster.js           # Roster builder interactivity
│   └── (images)
└── templates/
    ├── base.html
    ├── roster_builder.html
    ├── leaderboard.html
    ├── lineups.html
    ├── confirmation.html
    └── champions.html
```

---

## Environment Variables (set in Railway)

| Variable | Description |
|---|---|
| `SITE_MODE` | `pre-tournament` or `tournament-live` |
| `GOOGLE_SHEET_ID` | `147wIFWr0bmi4bg5s7kC8Zvn38BVJ6Oh9LQUWIiX2NSY` |
| `GOOGLE_CREDENTIALS_JSON` | Full contents of `credentials.json` as a JSON string |
| `LEADERBOARD_EMBED_URL` | Google Sheets published embed URL (set when tournament starts) |
| `SENDGRID_API_KEY` | SendGrid API key for confirmation emails |

Locally, `credentials.json` is used directly (file must be in project root, gitignored).

---

## Site Modes

### `pre-tournament` (current live mode)

- `/` serves `roster_builder.html` — the player selection + submission form
- Users pick 6 players within a $50,000 cost cap
- On submission: row written to Google Sheet "Website Responses" tab, confirmation email sent via SendGrid, submission cookie set (30-day expiry)
- Returning visitors with a cookie see their confirmation page instead of the form
- `/lineups` shows placeholder "No cheating" message (entries hidden until all submitted)
- `/leaderboard` shows placeholder "Check back April 9th" message with an image

### `tournament-live` (activate on April 9th)

- `/` serves `leaderboard.html` with the embedded Google Sheet leaderboard
- The roster builder is no longer accessible from the home page
- `/lineups` should show all submitted rosters (Google Sheet integration is a TODO — see below)
- `/leaderboard` also serves the same leaderboard (nav tab still present)

**To flip the switch:** In Railway → Variables, change `SITE_MODE` to `tournament-live` and set `LEADERBOARD_EMBED_URL` to the published Google Sheet URL. Railway redeploys in ~60 seconds. No code push needed.

---

## Google Sheets Integration

### Credentials

In production, credentials are loaded from the `GOOGLE_CREDENTIALS_JSON` environment variable (a JSON string of the full service account credentials file). Locally, `credentials.json` in the project root is used.

```python
def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return spreadsheet.worksheet("Website Responses")
```

### Submissions Tab Schema

The "Website Responses" tab columns (in order):

| Column | Content |
|---|---|
| A | Timestamp (YYYY-MM-DD HH:MM:SS) |
| B | Entrant name |
| C | Entrant email |
| D–I | Player 1–6 names |
| J | Total cost |
| K | Venmo confirmed ("Yes") |

### Lineups Page (TODO)

The `/lineups` route currently returns an empty list. When the tournament goes live and lineups are ready to be revealed, this should be wired up to read all rows from the "Website Responses" tab and display them. The route passes `entries` (list of dicts) and `my_name` (from cookie, lowercased) to `lineups.html`. The template is already built to render lineup cards — it just needs real data.

Expected entry dict format:
```python
{
    "name": "John Smith",
    "total_salary": 49800,
    "players": [
        {"name": "Scottie Scheffler", "salary": 14000},
        ...
    ]
}
```

---

## Leaderboard — What Needs to Be Built

The current leaderboard implementation (`tournament-live` mode) embeds a Google Sheet via iframe. The next developer's job is to replace this with a **fully custom real-time leaderboard**.

### Current iframe approach (to be replaced)

In `leaderboard.html`, when `embed_url` is set, an iframe is rendered pointing to a published Google Sheet URL. The iframe auto-refreshes every 60 seconds via JS. This works but is ugly and not customizable.

### What the custom leaderboard should do

- Read scoring data from the Google Sheet (a separate tab from "Website Responses")
- Read submitted rosters from the "Website Responses" tab
- Compute each entrant's total score by summing their 6 players' scores
- Display a ranked leaderboard with entrant name, player breakdown, and total score
- Update in real-time or near-real-time (polling or websocket)

### Scoring rules

- Each entrant's score = sum of their 6 players' strokes across all completed rounds
- Lower is better (stroke play)
- Missed cut = +5 strokes for each of rounds 3 and 4 (i.e. +10 total for a missed cut)
- Player withdrawal before tee-off: replacement allowed within budget
- Player withdrawal after tee-off: +5 strokes per round not finished

### Payout structure (for reference, not displayed in leaderboard)

- Overall: 1st 25%, 2nd 15%, 3rd 9%, 4th 5%, 5th 4%, Last place 4%
- Rounds 1 & 2: 1st 8%, 2nd 5%, 3rd 3%, 4th 2%, 5th 1%
- Percentages are of the total pool; dollar amounts calculated once all entries in

---

## Player Data

Player list and costs are in `config.py` as `PLAYERS` — a list of dicts with `name` and `salary` keys. Sorted by cost descending. There are 90 players for the 2026 Masters.

Cost cap: $50,000. Entrants pick exactly 6 players.

---

## Confirmation & Cookie System

On successful submission:
1. Row written to Google Sheet
2. Confirmation email sent via SendGrid from `noreply@slotmasterspool.com`
3. A `submission` cookie is set (30-day expiry) containing: `{name, email, players: [...], total}`
4. User is redirected to `/confirmation`

On return visit to `/`:
- If `submission` cookie exists and `SITE_MODE=pre-tournament`, the confirmation page is shown instead of the form (prevents double submission)
- The `/lineups` route reads the cookie to identify `my_name` for highlighting the user's own lineup

---

## Past Champions

`/champions` — static page, no backend. Currently shows:
- 2025: Jason Datta
- 2024: Nate Krall

Photos are in `static/`. Update `templates/champions.html` each year.

---

## Design System

- **Primary green:** `#006747` (Augusta National green)
- **Gold accent:** `#FFD700`
- **Background:** `#ffffff`
- **Text:** `#1a1a1a`
- **Fonts:** Playfair Display (headings), Lato (body) — loaded from Google Fonts
- Mobile-first responsive; on mobile the team summary becomes a bottom drawer that auto-expands when 6 players are selected
