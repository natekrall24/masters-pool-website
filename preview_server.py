"""
preview_server.py — Run the site in tournament-live mode with mock pool entries.

Uses real live ESPN scores (whatever tournament is active) so the scoring logic
and leaderboard UI can be previewed without Google Sheets credentials.

Usage:
    python preview_server.py
Then open http://localhost:5001/leaderboard
"""

import os
os.environ["SITE_MODE"] = "tournament-live"

import app as flask_app

# ---------------------------------------------------------------------------
# Mock pool entries — 8 fake participants, each picking 6 players whose names
# appear in the current ESPN leaderboard so real scores are used.
# ---------------------------------------------------------------------------
MOCK_ENTRIES = [
    {
        "name": "Nick M",
        "players": [
            "J.J. Spaun", "Robert MacIntyre", "Michael Kim",
            "Ludvig Aberg", "Tommy Fleetwood", "Kristoffer Reitan",
        ],
    },
    {
        "name": "Sammy Marks",
        "players": [
            "J.J. Spaun", "Si Woo Kim", "Hideki Matsuyama",
            "Marco Penge", "Maverick McNealy", "Jordan Spieth",
        ],
    },
    {
        "name": "Jason D",
        "players": [
            "Michael Kim", "Robert MacIntyre", "Ludvig Aberg",
            "Si Woo Kim", "Alex Noren", "Nick Taylor",
        ],
    },
    {
        "name": "Nate K",
        "players": [
            "Robert MacIntyre", "Tommy Fleetwood", "Hideki Matsuyama",
            "J.J. Spaun", "Maverick McNealy", "Andrew Novak",
        ],
    },
    {
        "name": "Dan T",
        "players": [
            "J.J. Spaun", "Ludvig Aberg", "Sepp Straka",
            "Tommy Fleetwood", "Kristoffer Reitan", "Sami Valimaki",
        ],
    },
    {
        "name": "Mike P",
        "players": [
            "Michael Kim", "Si Woo Kim", "Marco Penge",
            "Brian Harman", "Matt McCarty", "Andrew Novak",
        ],
    },
    {
        "name": "Chris B",
        "players": [
            "Tommy Fleetwood", "Hideki Matsuyama", "Jordan Spieth",
            "Russell Henley", "Max Homa", "Alex Noren",
        ],
    },
    {
        "name": "Rachel S",
        "players": [
            "J.J. Spaun", "Robert MacIntyre", "Ludvig Aberg",
            "Marco Penge", "Nick Taylor", "Brian Harman",
        ],
    },
]

# Patch both the leaderboard and lineups sheet reads
flask_app._get_entries_from_sheet = lambda: MOCK_ENTRIES

if __name__ == "__main__":
    print("Preview server running at http://localhost:5001")
    print("SITE_MODE=tournament-live with mock pool entries\n")
    flask_app.app.run(debug=False, port=5001)
