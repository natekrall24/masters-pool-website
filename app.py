from flask import Flask, render_template, request, redirect, url_for, make_response
from config import SITE_MODE, PLAYERS, GOOGLE_SHEET_ID, LEADERBOARD_EMBED_URL
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PLAYER_MAP = {p["name"]: p for p in PLAYERS}


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


def send_confirmation_email(name, email, players, total_salary):
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        app.logger.warning("SENDGRID_API_KEY not set — skipping confirmation email")
        return

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        player_lines = "\n".join(
            f"  • {p['name']} — ${p['salary']:,}" for p in players
        )

        body = f"""Hi {name},

Your team has been submitted for the 2026 Slot Masters Pool!

Your Team:
{player_lines}

Total Cost: ${total_salary:,}

Reminders:
  • Make sure you've sent $25 to @SammyMarks21 on Venmo
  • Submission deadline: Wednesday, April 8th at 11:59 PM
  • The leaderboard goes live at slotmasterspool.com on April 9th

Good luck!
— Slot Masters Pool
"""

        message = Mail(
            from_email="noreply@slotmasterspool.com",
            to_emails=email,
            subject="You're in! Your 2026 Slot Masters Pool Team",
            plain_text_content=body,
        )

        sg = SendGridAPIClient(api_key)
        sg.send(message)
    except Exception as e:
        import traceback
        app.logger.error(f"Failed to send confirmation email: {e}\n{traceback.format_exc()}")


@app.route("/")
def index():
    if SITE_MODE == "tournament-live":
        return render_template("leaderboard.html", embed_url=LEADERBOARD_EMBED_URL)

    # Check for existing submission cookie
    submission = request.cookies.get("submission")
    if submission:
        try:
            data = json.loads(submission)
            players = [PLAYER_MAP[n] for n in data.get("players", []) if n in PLAYER_MAP]
            return render_template(
                "confirmation.html",
                name=data.get("name", ""),
                email=data.get("email", ""),
                total=data.get("total", 0),
                players=players,
                from_cookie=True,
            )
        except Exception:
            pass  # Bad cookie — fall through to show the form

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

    selected_players = []
    total_salary = 0
    for name_str in selected:
        if name_str in PLAYER_MAP:
            selected_players.append(PLAYER_MAP[name_str])
            total_salary += PLAYER_MAP[name_str]["salary"]
        else:
            errors.append(f"Unknown player: {name_str}")

    if total_salary > 50000:
        errors.append(f"Total cost ${total_salary:,} exceeds the $50,000 cap.")

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

    # Send confirmation email
    send_confirmation_email(name, email, selected_players, total_salary)

    # Build response with submission cookie (expires after 30 days)
    cookie_data = json.dumps({
        "name": name,
        "email": email,
        "players": selected,
        "total": total_salary,
    })

    resp = make_response(redirect(url_for("confirmation")))
    resp.set_cookie("submission", cookie_data, max_age=60 * 60 * 24 * 30, samesite="Lax")
    return resp


@app.route("/confirmation")
def confirmation():
    # Try cookie first
    submission = request.cookies.get("submission")
    if submission:
        try:
            data = json.loads(submission)
            players = [PLAYER_MAP[n] for n in data.get("players", []) if n in PLAYER_MAP]
            return render_template(
                "confirmation.html",
                name=data.get("name", ""),
                email=data.get("email", ""),
                total=data.get("total", 0),
                players=players,
            )
        except Exception:
            pass

    # Fallback — no cookie, redirect home
    return redirect(url_for("index"))


@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html", embed_url=LEADERBOARD_EMBED_URL)


@app.route("/lineups")
def lineups():
    entries = []
    my_name = None

    submission = request.cookies.get("submission")
    if submission:
        try:
            data = json.loads(submission)
            my_name = data.get("name", "").strip().lower()
        except Exception:
            pass

    return render_template("lineups.html", entries=entries, my_name=my_name)


if __name__ == "__main__":
    app.run(debug=True)
