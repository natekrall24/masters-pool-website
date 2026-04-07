"""
check_names.py — Verify that all picked players can be matched to the live ESPN leaderboard.

Run this on April 9th (or any time the Masters leaderboard is live) before flipping
SITE_MODE to tournament-live:

    python check_names.py
"""

import csv
import os
from espn_leaderboard import get_player_scores, normalize_name

CSV_PATH = os.path.join(os.path.dirname(__file__), "entries.csv")

def get_all_entries():
    entries = []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                players = [row.get(f"Player {i}", "").strip() for i in range(1, 7)]
                players = [p for p in players if p]
                if name and len(players) == 6:
                    entries.append({"name": name, "players": players})
    except FileNotFoundError:
        print(f"ERROR: entries.csv not found at {CSV_PATH}")
    return entries

def main():
    print("Fetching ESPN leaderboard...")
    try:
        player_scores = get_player_scores()
    except Exception as e:
        print(f"ERROR: Could not fetch ESPN data — {e}")
        return

    if not player_scores:
        print("ERROR: ESPN returned no players. The Masters leaderboard may not be live yet.")
        return

    print(f"ESPN returned {len(player_scores)} players.\n")
    espn_names = {normalize_name(p["name"]): p["name"] for p in player_scores}

    entries = get_all_entries()
    if not entries:
        print("ERROR: No entries found in entries.csv.")
        return

    print(f"Checking {len(entries)} pool entries...\n")

    mismatches = {}  # normalized_pick -> list of entrant names
    matched = set()

    for entry in entries:
        for pick in entry["players"]:
            key = normalize_name(pick)
            if key in espn_names:
                matched.add(pick)
            else:
                mismatches.setdefault(pick, []).append(entry["name"])

    if not mismatches:
        print(f"All {len(matched)} picked players matched successfully!")
        return

    print(f"MATCHED:   {len(matched)} players")
    print(f"UNMATCHED: {len(mismatches)} players\n")
    print("The following picks could not be found in ESPN data:")
    print("-" * 50)
    for pick, entrants in sorted(mismatches.items()):
        print(f"  {pick:<30} picked by: {', '.join(entrants)}")

    print("\nESPN player names (for reference):")
    print("-" * 50)
    for p in sorted(player_scores, key=lambda x: x["name"]):
        print(f"  {p['name']}")

if __name__ == "__main__":
    main()
