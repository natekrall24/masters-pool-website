# Slot Masters Pool — Project Spec

## Overview

A simple Flask web app for running a Masters golf fantasy pool. Entrants pick 6 golfers within a $50,000 salary cap, submit their roster, and follow along on a live leaderboard during the tournament. Submissions are stored directly in a Google Sheet (no database).

The site has two modes controlled by a config flag: **pre-tournament** (roster builder + submission form) and **tournament-live** (embedded Google Sheet leaderboard + lineup viewer).

---

## Tech Stack

- **Backend:** Flask (Python)
- **Frontend:** Jinja2 templates, vanilla HTML/CSS, vanilla JavaScript (one JS file for roster builder interactivity)
- **Data storage:** Google Sheets via `gspread` + Google Cloud service account
- **Deployment target:** Railway or Render (from GitHub repo)
- **Domain:** slotmasterspool.com

---

## Design Direction

Masters-themed. Think Augusta National: dark green (#006747), yellow/gold (#FFD700), white, and black. Clean, slightly prestigious feel — not corporate, but not goofy either. A tasteful golf aesthetic.

- Use a serif or semi-serif display font for headings (something classic, not generic)
- Clean sans-serif for body text
- The leaderboard page should feel like a real tournament leaderboard
- Mobile-responsive — many entrants will use their phones

---

## Config & Data

### Mode Toggle

A simple flag in the Flask config or an environment variable:

```python
SITE_MODE = "pre-tournament"  # or "tournament-live"
```

This controls which page is served at the root URL `/`.

### Player Data

Store in a Python file or JSON. Here is the full player list with salaries:

```python
PLAYERS = [
    {"name": "Scottie Scheffler", "salary": 12400},
    {"name": "Rory McIlroy", "salary": 11100},
    {"name": "Ludvig Aberg", "salary": 10800},
    {"name": "Collin Morikawa", "salary": 10500},
    {"name": "Jon Rahm", "salary": 10400},
    {"name": "Bryson DeChambeau", "salary": 9900},
    {"name": "Xander Schauffele", "salary": 9700},
    {"name": "Justin Thomas", "salary": 9600},
    {"name": "Hideki Matsuyama", "salary": 9500},
    {"name": "Brooks Koepka", "salary": 9400},
    {"name": "Joaquin Niemann", "salary": 9300},
    {"name": "Viktor Hovland", "salary": 9200},
    {"name": "Tommy Fleetwood", "salary": 9100},
    {"name": "Jordan Spieth", "salary": 9000},
    {"name": "Shane Lowry", "salary": 8800},
    {"name": "Patrick Cantlay", "salary": 8700},
    {"name": "Tyrrell Hatton", "salary": 8600},
    {"name": "Min Woo Lee", "salary": 8500},
    {"name": "Russell Henley", "salary": 8400},
    {"name": "Will Zalatoris", "salary": 8300},
    {"name": "Cameron Smith", "salary": 8200},
    {"name": "Akshay Bhatia", "salary": 8100},
    {"name": "Robert Macintyre", "salary": 8000},
    {"name": "Corey Conners", "salary": 7900},
    {"name": "Tony Finau", "salary": 7800},
    {"name": "Wyndham Clark", "salary": 7700},
    {"name": "Sahith Theegala", "salary": 7700},
    {"name": "Jason Day", "salary": 7600},
    {"name": "Sepp Straka", "salary": 7600},
    {"name": "Tom Kim", "salary": 7500},
    {"name": "Dustin Johnson", "salary": 7500},
    {"name": "Sam Burns", "salary": 7400},
    {"name": "Matt Fitzpatrick", "salary": 7400},
    {"name": "Patrick Reed", "salary": 7300},
    {"name": "Sungjae Im", "salary": 7300},
    {"name": "Justin Rose", "salary": 7200},
    {"name": "Adam Scott", "salary": 7200},
    {"name": "Maverick McNealy", "salary": 7100},
    {"name": "Daniel Berger", "salary": 7100},
    {"name": "Sergio Garcia", "salary": 7100},
    {"name": "Davis Thompson", "salary": 7000},
    {"name": "Cameron Young", "salary": 7000},
    {"name": "Keegan Bradley", "salary": 7000},
    {"name": "Thomas Detry", "salary": 6900},
    {"name": "Billy Horschel", "salary": 6900},
    {"name": "Nicolai Hojgaard", "salary": 6900},
    {"name": "J.J. Spaun", "salary": 6800},
    {"name": "Aaron Rai", "salary": 6800},
    {"name": "Brian Harman", "salary": 6800},
    {"name": "Byeong Hun An", "salary": 6800},
    {"name": "Rasmus Hojgaard", "salary": 6700},
    {"name": "Michael Kim", "salary": 6700},
    {"name": "Taylor Pendrith", "salary": 6700},
    {"name": "Phil Mickelson", "salary": 6700},
    {"name": "Cameron Davis", "salary": 6700},
    {"name": "Laurie Canter", "salary": 6600},
    {"name": "Max Greyserman", "salary": 6600},
    {"name": "Lucas Glover", "salary": 6600},
    {"name": "Christiaan Bezuidenhout", "salary": 6600},
    {"name": "Chris Kirk", "salary": 6600},
    {"name": "Max Homa", "salary": 6500},
    {"name": "Nick Dunlap", "salary": 6500},
    {"name": "Harris English", "salary": 6500},
    {"name": "Denny McCarthy", "salary": 6500},
    {"name": "J.T. Poston", "salary": 6500},
    {"name": "Nick Taylor", "salary": 6400},
    {"name": "Nicolas Echavarria", "salary": 6400},
    {"name": "Austin Eckroat", "salary": 6400},
    {"name": "Tom Hoge", "salary": 6400},
    {"name": "Davis Riley", "salary": 6400},
    {"name": "Matthieu Pavon", "salary": 6400},
    {"name": "Jhonattan Vegas", "salary": 6300},
    {"name": "Stephan Jaeger", "salary": 6300},
    {"name": "Joe Highsmith", "salary": 6300},
    {"name": "Matthew McCarty", "salary": 6300},
    {"name": "Kevin Yu", "salary": 6300},
    {"name": "Adam Schenk", "salary": 6300},
    {"name": "Thriston Lawrence", "salary": 6200},
    {"name": "Charl Schwartzel", "salary": 6200},
    {"name": "Patton Kizzire", "salary": 6200},
    {"name": "Danny Willett", "salary": 6200},
    {"name": "Brian Campbell", "salary": 6200},
    {"name": "Zach Johnson", "salary": 6200},
    {"name": "Bubba Watson", "salary": 6100},
    {"name": "Jose Luis Ballester", "salary": 6100},
    {"name": "Justin Hastings", "salary": 6100},
    {"name": "Bernhard Langer", "salary": 6100},
    {"name": "Evan Beck", "salary": 6100},
    {"name": "Vijay Singh", "salary": 6100},
    {"name": "Rafael Campos", "salary": 6000},
    {"name": "Hiroshi Tai", "salary": 6000},
    {"name": "Angel Cabrera", "salary": 6000},
    {"name": "Noah Kent", "salary": 6000},
    {"name": "Fred Couples", "salary": 6000},
    {"name": "Mike Weir", "salary": 6000},
    {"name": "Jose Maria Olazabal", "salary": 6000},
]
```

---

## Pages & Routes

### Route: `/` (root)

Controlled by `SITE_MODE`:

- **If `pre-tournament`:** renders the roster builder/submission form
- **If `tournament-live`:** renders the leaderboard page

### Route: `/lineups`

Displays all submitted rosters. Reads from the Google Sheet "Submissions" tab. Shows each entrant's name and their 6 picks with salaries, displayed as cards or a clean table.

### Route: `/submit` (POST only)

Receives the roster form submission. Validates:
1. Exactly 6 players selected
2. Total salary ≤ $50,000
3. Name and email are not empty
4. Venmo checkbox is checked

On success: writes a row to the Google Sheet "Submissions" tab and redirects to a confirmation page.
On failure: re-renders the form with error messages and the user's previous selections preserved.

### Route: `/confirmation`

Simple "You're in!" page showing the entrant's submitted team, total salary, and a reminder about the deadline/leaderboard.

---

## Roster Builder Page (Pre-Tournament) — Detailed Spec

This is the most interactive page. Here's exactly how it should work:

### Layout

- **Header:** "2025 Slot Masters Pool" title, brief welcome text
- **Rules section:** Collapsible or always-visible summary of the rules (scoring, payment structure, deadline). Pull from the content below.
- **Player list:** Scrollable list/table of all players with columns: checkbox, player name, salary (formatted as `$X,XXX`). Sorted by salary descending (highest first). Include a search/filter box at the top to filter by name.
- **Team summary sidebar (desktop) / sticky bottom bar (mobile):** Shows the 6 roster slots (filled or empty), running total salary, remaining budget out of $50,000. Updates instantly as players are checked/unchecked.
- **Submission fields:** Name (text input), Email (text input), Venmo confirmation checkbox.
- **Submit button:** Disabled until all validation passes (6 players, ≤$50k, name filled, email filled, Venmo checked).

### JavaScript Behavior

- Checking a player adds them to the team summary and updates the budget
- Unchecking removes them
- When 6 players are selected, all remaining unchecked players become disabled
- Players whose salary exceeds remaining budget are grayed out/disabled
- Budget display changes color (e.g., turns red) if somehow over $50k
- Search box filters the player list in real time by name

---

## Leaderboard Page (Tournament-Live) — Detailed Spec

- Masters-green themed header with pool name
- Embedded Google Sheet via iframe (published to web), sized to fill most of the viewport
- Auto-refresh the iframe every 60 seconds using a small JS snippet
- Nav link to `/lineups` page
- The Google Sheet URL will be configured in the Flask config (I'll fill it in once I publish the sheet)

---

## Lineups Page — Detailed Spec

- Reads all rows from the "Submissions" tab of the Google Sheet
- Displays each entrant as a card: name, and their 6 players with salaries
- Sorted alphabetically by entrant name
- Clean, simple layout — this is a reference page, not the main attraction

---

## Rules Content

Use this for the rules section on the roster builder page:

**How To Play:**
1. Select SIX players with salaries that add up to $50,000 or LESS
2. Enter your name and email
3. Venmo $25 to @SammyMarks21 BEFORE submitting
4. Submit by Wednesday, April 9th at 11:59 PM

**Scoring:**
- Tracked based on strokes per round and overall
- Missed cut = +5 strokes for each of rounds 3 and 4

**Payouts:**
- Overall Winner: 50% of pool
- Overall 2nd Place: 10%
- Round 1 Winner: 10%
- Round 2 Winner: 10%
- Round 3 Winner: 10%
- Round 4 Winner: 10%

**Other Rules:**
- It is YOUR responsibility to ensure your salary is ≤ $50,000. Invalid entries will be voided without refund.
- Player withdrawal BEFORE tee-off: you may request a replacement within budget. AFTER tee-off: player scores +5 per round.
- Questions? Email sammymarks03@gmail.com

---

## Google Sheets Integration

Use the `gspread` library with a Google Cloud service account.

### Setup (manual steps, not code):
1. Create a Google Cloud project
2. Enable the Google Sheets API
3. Create a service account and download the JSON credentials
4. Share the Google Sheet with the service account email (editor access)
5. Store the credentials JSON as `credentials.json` in the project root (add to .gitignore!)

### In the code:
- On form submission, append a row to the "Submissions" tab: `[timestamp, name, email, player1, player2, player3, player4, player5, player6, total_salary, venmo_confirmed]`
- On the `/lineups` page, read all rows from the "Submissions" tab to display rosters
- Handle the case where the sheet or tab doesn't exist gracefully

---

## File Structure

```
slot-masters-pool/
├── app.py                  # Flask app, all routes
├── config.py               # SITE_MODE, Google Sheet ID, player data
├── requirements.txt        # flask, gspread, google-auth
├── credentials.json        # Google service account (gitignored)
├── .gitignore
├── .env                    # Environment variables (optional)
├── static/
│   ├── style.css           # All styles, Masters theme
│   └── roster.js           # Roster builder interactivity
├── templates/
│   ├── base.html           # Base template with nav, head, footer
│   ├── roster_builder.html # Pre-tournament form page
│   ├── leaderboard.html    # Tournament-live leaderboard page
│   ├── lineups.html        # All submitted rosters
│   └── confirmation.html   # Post-submission confirmation
└── README.md
```

---

## Design Details

### Color Palette
- **Primary green:** #006747 (Augusta National green)
- **Accent gold:** #FFD700
- **Background:** #FFFDF7 (warm off-white)
- **Text:** #1a1a1a (near-black)
- **Secondary:** #2d5016 (darker green for hover states)
- **Error/warning:** #c0392b (red)

### Typography
- Headings: A classic serif like Playfair Display or similar (from Google Fonts)
- Body: A clean sans-serif like Lato, Source Sans Pro, or similar
- Player names in the roster builder: slightly bolder weight for readability

### General
- Mobile-first responsive design
- No heavy frameworks — keep the CSS clean and hand-written
- Subtle touches: maybe a thin gold border on the team summary card, green gradient in the header
- The submit button should feel satisfying — a solid green with a slight hover animation

---

## Deployment Notes

- The app should work with a `Procfile` or `railway.toml` for deployment
- All secrets (Google credentials, sheet ID) should come from environment variables in production
- Include a `requirements.txt` with pinned versions
- The `credentials.json` should be in `.gitignore` — in production, the credentials will be loaded from an environment variable containing the JSON string
