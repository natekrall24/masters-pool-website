from flask import Flask, render_template, request, redirect, url_for, make_response
from config import SITE_MODE, PLAYERS, GOOGLE_SHEET_ID
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import zoneinfo
import os
import json
import time
import traceback
from espn_leaderboard import get_player_scores, normalize_name
import csv

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


@app.context_processor
def inject_site_mode():
    return {"SITE_MODE": SITE_MODE}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PLAYER_MAP = {p["name"]: p for p in PLAYERS}

# ---------------------------------------------------------------------------
# Leaderboard cache — avoids hitting ESPN + Google Sheets on every request
# ---------------------------------------------------------------------------

_lb_cache: dict = {"data": None, "ts": 0.0}
CACHE_TTL = 60  # seconds


CSV_PATH = os.path.join(os.path.dirname(__file__), "entries.csv")

def _get_total_pot():
    """Count confirmed entries in entries.csv and return total pot (entries × $25)."""
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = sum(1 for row in reader if row.get("Name", "").strip())
        return count * 25
    except FileNotFoundError:
        return 0


def _get_entries_from_sheet():
    """Read all confirmed entries from entries.csv."""
    entries = []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip()
                players = [row.get(f"Player {i}", "").strip() for i in range(1, 7)]
                players = [p for p in players if p]
                if not name or len(players) < 6:
                    continue
                entries.append({"name": name, "players": players})
    except FileNotFoundError:
        app.logger.error("entries.csv not found at %s", CSV_PATH)
    return entries


def _rank_by(entries, sort_key):
    """
    Return a new list of dicts (shallow copies) sorted by sort_key ascending,
    with golf-style 'pos' assigned.  Original dicts are not modified.
    """
    ranked = sorted((dict(e) for e in entries), key=lambda e: (e[sort_key], e["name"].lower()))
    i = 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][sort_key] == ranked[i][sort_key]:
            j += 1
        label = f"T{i + 1}" if (j - i) > 1 else str(i + 1)
        for k in range(i, j):
            ranked[k]["pos"] = label
        i = j
    return ranked


def _compute_pool_standings():
    """Fetch live ESPN scores and sheet entries, return ranked pool standings."""
    player_scores = get_player_scores()
    score_map = {normalize_name(p["name"]): p for p in player_scores}

    # Determine which rounds have started, excluding MC penalty (+5) from the check
    non_mc = [p for p in player_scores if not p["missed_cut"]]
    rounds_started = {
        "r1": any(p["r1"] != 0 or p["r1_posted"] for p in non_mc),
        "r2": any(p["r2"] != 0 or p["r2_posted"] for p in non_mc),
        "r3": any(p["r3"] != 0 or p["r3_posted"] for p in non_mc),
        "r4": any(p["r4"] != 0 or p["r4_posted"] for p in non_mc),
    }
    started_round_keys = [r for r in ("r1", "r2", "r3", "r4") if rounds_started[r]]

    entries_raw = _get_entries_from_sheet()
    results = []
    for entry in entries_raw:
        r1 = r2 = r3 = r4 = 0
        golfers = []
        for player_name in entry["players"]:
            p = score_map.get(normalize_name(player_name))
            if p:
                r1 += p["r1"]
                r2 += p["r2"]
                r3 += p["r3"]
                r4 += p["r4"]
                golfers.append({
                    "name": p["name"],
                    "r1": p["r1"],
                    "r2": p["r2"],
                    "r3": p["r3"],
                    "r4": p["r4"],
                    "missed_cut": p["missed_cut"],
                    "thru": p.get("thru", "-"),
                })
            else:
                app.logger.warning("Player not found in ESPN data: %r", player_name)
                golfers.append({"name": player_name, "r1": 0, "r2": 0, "r3": 0, "r4": 0, "missed_cut": False})

        scores = {"r1": r1, "r2": r2, "r3": r3, "r4": r4}
        total = r1 + r2 + r3 + r4
        display_total = sum(scores[r] for r in started_round_keys) if started_round_keys else None
        results.append({
            "name": entry["name"],
            "r1": r1,
            "r2": r2,
            "r3": r3,
            "r4": r4,
            "total": total,
            "display_total": display_total,
            "golfers": golfers,
        })

    # Overall standings
    overall = _rank_by(results, "total")

    # Per-round standings (only when that round has started)
    r1_standings = _rank_by(results, "r1") if rounds_started["r1"] else []
    r2_standings = _rank_by(results, "r2") if rounds_started["r2"] else []

    return {
        "entries": overall,
        "r1_standings": r1_standings,
        "r2_standings": r2_standings,
        "rounds_started": rounds_started,
        "last_updated": datetime.now(zoneinfo.ZoneInfo("America/New_York")).strftime("%-I:%M %p ET"),
    }


def get_cached_leaderboard():
    """Return pool standings, refreshing from ESPN/Sheets if the cache is stale."""
    now = time.time()
    # In tournament-over mode the cache never expires — use whatever was last fetched
    if SITE_MODE == "tournament-over" and _lb_cache["data"]:
        return _lb_cache["data"]
    if _lb_cache["data"] and now - _lb_cache["ts"] < CACHE_TTL:
        return _lb_cache["data"]
    data = _compute_pool_standings()
    _lb_cache["data"] = data
    _lb_cache["ts"] = now
    return data


def _ordinal(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def _build_payout_rows(entries, pcts, total_pot, place_suffix=""):
    """
    Walk through entries in rank order, grouping ties by their shared pos label.
    Tied players split the combined prize money for all slots they occupy.
    """
    rows = []
    slot = 0  # index into pcts
    i = 0     # index into entries
    while i < len(entries) and slot < len(pcts):
        current_pos = entries[i]["pos"]
        # Collect all entries sharing this pos label
        j = i + 1
        while j < len(entries) and entries[j]["pos"] == current_pos:
            j += 1
        tie_count = j - i
        # How many prize slots this group consumes (may be fewer than tie_count
        # if the group extends beyond the paid positions)
        slots_consumed = min(tie_count, len(pcts) - slot)
        prize = int(sum(pcts[slot:slot + slots_consumed]) * total_pot / tie_count)
        place_num = slot + 1
        prefix = "T" if tie_count > 1 else ""
        label = f"{prefix}{_ordinal(place_num)}"
        if place_suffix:
            label += f" {place_suffix}"
        for k in range(i, j):
            rows.append({"place": label, "name": entries[k]["name"], "amount": prize})
        slot += slots_consumed
        i = j
    return rows


def _compute_payout_summary(overall, r1_standings, r2_standings, total_pot):
    """Build a structured payout summary for the results page."""
    # Overall positions 1–5
    overall_rows = _build_payout_rows(overall, [0.23, 0.14, 0.09, 0.05, 0.04, 0.03, 0.02, 0.01], total_pot, "Place")

    # Last place — find all entries tied at the bottom
    if overall:
        last_pos = overall[-1]["pos"]
        last_group = [e for e in overall if e["pos"] == last_pos]
        last_amount = int(total_pot * 0.01 / len(last_group))
        last_label = "Last Place" if len(last_group) == 1 else "Last Place (Tied)"
        for e in last_group:
            overall_rows.append({"place": last_label, "name": e["name"], "amount": last_amount})

    sections = [{"section": "Overall", "entries": overall_rows}]

    round_pcts = [0.08, 0.05, 0.03, 0.02, 0.01]
    for standings, label in [(r1_standings, "Round 1"), (r2_standings, "Round 2")]:
        if standings:
            sections.append({
                "section": label,
                "entries": _build_payout_rows(standings, round_pcts, total_pot),
            })
    return sections


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

Feel free to share the pool with your friends — the more the merrier!

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
        app.logger.error(f"Failed to send confirmation email: {e}\n{traceback.format_exc()}")


def _render_leaderboard():
    """Render the pool leaderboard in tournament-live mode."""
    total_pot = _get_total_pot()
    try:
        lb = get_cached_leaderboard()
        return render_template("leaderboard.html", **lb, error=False,
                               total_pot=total_pot, tournament_over=False, payout_summary=[])
    except Exception as e:
        app.logger.error("Leaderboard error: %s\n%s", e, traceback.format_exc())
        return render_template(
            "leaderboard.html",
            entries=[],
            r1_standings=[],
            r2_standings=[],
            rounds_started={"r1": False, "r2": False, "r3": False, "r4": False},
            last_updated=None,
            error=True,
            total_pot=total_pot,
            tournament_over=False,
            payout_summary=[],
        )


def _render_results():
    """Render the final results page in tournament-over mode."""
    total_pot = _get_total_pot()
    try:
        lb = get_cached_leaderboard()
        payout_summary = _compute_payout_summary(
            lb["entries"], lb["r1_standings"], lb["r2_standings"], total_pot
        )
        return render_template("leaderboard.html", **lb, error=False,
                               total_pot=total_pot, tournament_over=True,
                               payout_summary=payout_summary)
    except Exception as e:
        app.logger.error("Results error: %s\n%s", e, traceback.format_exc())
        return render_template(
            "leaderboard.html",
            entries=[],
            r1_standings=[],
            r2_standings=[],
            rounds_started={"r1": False, "r2": False, "r3": False, "r4": False},
            last_updated=None,
            error=True,
            total_pot=total_pot,
            tournament_over=True,
            payout_summary=[],
        )


@app.route("/")
def index():
    if SITE_MODE == "tournament-live":
        return _render_leaderboard()
    if SITE_MODE == "tournament-over":
        return _render_results()

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet = get_sheet()
        row = [timestamp, name, email] + selected + [total_salary, "Yes"]
        sheet.append_row(row)
    except Exception as e:
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


@app.route("/champions")
def champions():
    return render_template("champions.html")


@app.route("/leaderboard")
def leaderboard():
    if SITE_MODE == "tournament-live":
        return _render_leaderboard()
    if SITE_MODE == "tournament-over":
        return _render_results()
    return render_template("leaderboard.html",
                           entries=[],
                           r1_standings=[],
                           r2_standings=[],
                           rounds_started={"r1": False, "r2": False, "r3": False, "r4": False},
                           last_updated=None,
                           error=False,
                           total_pot=_get_total_pot(),
                           tournament_over=False,
                           payout_summary=[])


@app.route("/lineups")
def lineups():
    my_name = None
    submission = request.cookies.get("submission")
    if submission:
        try:
            data = json.loads(submission)
            my_name = data.get("name", "").strip().lower()
        except Exception:
            pass

    if SITE_MODE not in ("tournament-live", "tournament-over"):
        return render_template("lineups.html", entries=[], player_counts=[], my_name=my_name,
                               rounds_started={"r1": False, "r2": False, "r3": False, "r4": False})

    try:
        lb = get_cached_leaderboard()
        scored_entries = lb["entries"]  # already has golfers + per-round scores
        rounds_started = lb["rounds_started"]
    except Exception as e:
        app.logger.error("Failed to load lineups scores: %s", e)
        scored_entries = []
        rounds_started = {"r1": False, "r2": False, "r3": False, "r4": False}

    started_round_keys = [r for r in ("r1", "r2", "r3", "r4") if rounds_started[r]]

    # Build lineups entries with golfer scores attached
    entries = []
    for entry in scored_entries:
        golfers = entry.get("golfers", [])
        # Compute display score per golfer (sum of started rounds only)
        enriched_golfers = []
        for g in golfers:
            g_score = sum(g[r] for r in started_round_keys) if started_round_keys else None
            enriched_golfers.append({**g, "display_score": g_score})
        team_total = entry.get("display_total")  # sum of started rounds for the team
        entries.append({
            "name": entry["name"],
            "players": [g["name"] for g in golfers],
            "golfers": enriched_golfers,
            "team_total": team_total,
        })

    # Sort by team total (best = lowest), then alphabetically
    any_scores = any(e["team_total"] is not None for e in entries)
    if any_scores:
        entries = sorted(entries, key=lambda e: (e["team_total"] if e["team_total"] is not None else 9999, e["name"].lower()))
    else:
        entries = sorted(entries, key=lambda e: e["name"].lower())

    # Count how many entries each player appears in, preserving config.py order
    counts = {}
    for entry in entries:
        for p in entry["players"]:
            counts[p] = counts.get(p, 0) + 1
    player_counts = sorted(
        [{"name": p["name"], "salary": p["salary"], "count": counts.get(p["name"], 0)} for p in PLAYERS],
        key=lambda x: (-x["count"], -x["salary"])
    )

    return render_template("lineups.html", entries=entries, player_counts=player_counts, my_name=my_name,
                           rounds_started=rounds_started)


if __name__ == "__main__":
    app.run(debug=True)
