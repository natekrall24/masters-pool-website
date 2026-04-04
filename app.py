from flask import Flask, render_template, request, redirect, url_for, flash
from config import SITE_MODE, PLAYERS, GOOGLE_SHEET_ID, LEADERBOARD_EMBED_URL
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        import json
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return spreadsheet.worksheet("Website Responses")


@app.route("/")
def index():
    if SITE_MODE == "tournament-live":
        return render_template("leaderboard.html", embed_url=LEADERBOARD_EMBED_URL)
    return render_template("roster_builder.html", players=PLAYERS, salary_cap=50000)


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    venmo = request.form.get("venmo_confirmed")
    selected = request.form.getlist("players")

    errors = []

    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    if not venmo:
        errors.append("You must confirm your Venmo payment.")
    if len(selected) != 6:
        errors.append(f"You must select exactly 6 players (you selected {len(selected)}).")

    # Build selected player objects and validate salary cap
    player_map = {p["name"]: p for p in PLAYERS}
    selected_players = []
    total_salary = 0
    for name_str in selected:
        if name_str in player_map:
            selected_players.append(player_map[name_str])
            total_salary += player_map[name_str]["salary"]
        else:
            errors.append(f"Unknown player: {name_str}")

    if total_salary > 50000:
        errors.append(f"Total salary ${total_salary:,} exceeds the $50,000 cap.")

    if errors:
        return render_template(
            "roster_builder.html",
            players=PLAYERS,
            salary_cap=50000,
            errors=errors,
            form_name=name,
            form_email=email,
            selected_names=selected,
        )

    # Write to Google Sheet
    try:
        sheet = get_sheet()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, name, email] + selected + [total_salary, "Yes"]
        sheet.append_row(row)
    except Exception as e:
        import traceback
        app.logger.error(f"Failed to write to Google Sheet: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        return render_template(
            "roster_builder.html",
            players=PLAYERS,
            salary_cap=50000,
            errors=["There was a problem submitting your team. Please try again or contact sammymarks03@gmail.com."],
            form_name=name,
            form_email=email,
            selected_names=selected,
        )

    return redirect(url_for(
        "confirmation",
        name=name,
        email=email,
        total=total_salary,
        p1=selected[0] if len(selected) > 0 else "",
        p2=selected[1] if len(selected) > 1 else "",
        p3=selected[2] if len(selected) > 2 else "",
        p4=selected[3] if len(selected) > 3 else "",
        p5=selected[4] if len(selected) > 4 else "",
        p6=selected[5] if len(selected) > 5 else "",
    ))


@app.route("/confirmation")
def confirmation():
    name = request.args.get("name", "")
    email = request.args.get("email", "")
    total = int(request.args.get("total", 0))
    player_names = [
        request.args.get("p1", ""),
        request.args.get("p2", ""),
        request.args.get("p3", ""),
        request.args.get("p4", ""),
        request.args.get("p5", ""),
        request.args.get("p6", ""),
    ]
    player_map = {p["name"]: p for p in PLAYERS}
    selected_players = [player_map[n] for n in player_names if n in player_map]

    return render_template(
        "confirmation.html",
        name=name,
        email=email,
        total=total,
        players=selected_players,
    )


@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html", embed_url=LEADERBOARD_EMBED_URL)


@app.route("/lineups")
def lineups():
    # TODO: Read from Google Sheet (next step)
    # For now, render with empty list
    entries = []
    return render_template("lineups.html", entries=entries)


if __name__ == "__main__":
    app.run(debug=True)
