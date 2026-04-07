"""
espn_leaderboard.py — Fetch the ESPN golf leaderboard and compute per-round
pool scores for each player.

Mirrors the logic previously done in Google Sheets formulas.

Column mapping from the scraped ESPN table (same as the Apps Script):
    PLAYER  - player name
    SCORE   - total to-par  (e.g. "-10", "E", "--")
    TODAY   - today's score to-par
    THRU    - holes completed today, or "F" for finished
    R1-R4   - actual stroke totals per round (e.g. "65"), or "--"

Scoring rules (replicating the spreadsheet formulas):
    r1_score = R1 - 72          if R1 is posted
             = TODAY             if player is live in R1 and TODAY is a number
             = 0                 otherwise (hasn't teed off, or today is "E"/"-")

    r2_score = R2 - 72          if R2 is posted
             = SCORE - r1        if player is live in R2 and scores are available
             = 0                 otherwise

    missed_cut = ESPN shows "CUT" OR (≥50 players have R2 posted AND r1+r2 > cut_line)
               — cut_line = score of the 50th player (top 50 + ties rule)
               — no cut applied until ALL players have finished R2

    r3_score = +5               if missed cut
             = R3 - 72          if R3 is posted
             = SCORE - r1 - r2  if player is live in R3
             = 0                otherwise

    r4_score = +5               if missed cut
             = R4 - 72          if R4 is posted
             = SCORE-r1-r2-r3   if player is live in R4
             = 0                otherwise
"""

import unicodedata
import requests
from bs4 import BeautifulSoup

PAR = 72
CUT_SPOTS = 50  # top 50 players + ties make the cut; cut line calculated dynamically


# Characters that NFD won't decompose — map them explicitly before stripping diacritics.
_CHAR_SUBS = [("æ", "ae"), ("ø", "o"), ("ð", "d"), ("þ", "th")]

# ESPN nickname → canonical pool-config name (both already normalized).
_NAME_ALIASES: dict[str, str] = {
    "nico echavarria": "nicolas echavarria",
}


def normalize_name(name: str) -> str:
    """
    Lowercase + strip diacritics so "Ludvig Åberg" matches "Ludvig Aberg".
    Also handles characters NFD won't decompose (ø→o, æ→ae, etc.) and
    ESPN nickname aliases (e.g. "Nico" → "Nicolas").
    Used for fuzzy player name matching between pool picks and ESPN data.
    """
    name = name.lower().strip()
    for old, new in _CHAR_SUBS:
        name = name.replace(old, new)
    nfd = unicodedata.normalize("NFD", name)
    normalized = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return _NAME_ALIASES.get(normalized, normalized)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _to_par(val: str) -> int | None:
    """
    Parse a to-par score string to an integer, or None if not available.
    "E" -> 0, "-3" -> -3, "+2" -> 2, "--" / "-" / "" -> None
    """
    if not val or val in ("--", "-"):
        return None
    if val == "E":
        return 0
    try:
        return int(val)
    except ValueError:
        return None


def _strokes(val: str) -> int | None:
    """Parse an actual stroke count ('65') to int, or None if '--'."""
    if not val or val in ("--", "-"):
        return None
    try:
        return int(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# ESPN fetch
# ---------------------------------------------------------------------------

def fetch_raw_rows() -> list[list[str]]:
    """
    Fetch https://www.espn.com/golf/leaderboard and return the first HTML
    table as a list of rows (each row is a list of cell text strings).
    Returns an empty list if no table is found.
    """
    url = "https://www.espn.com/golf/leaderboard"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def parse_player_scores(rows: list[list[str]]) -> list[dict]:
    """
    Given raw table rows from the ESPN leaderboard, locate the header row,
    then compute per-round pool scores for every player.

    Returns a list of dicts:
        name        str   – player name
        score       str   – raw to-par total from ESPN (e.g. "-10", "E")
        today       str   – raw today score from ESPN
        thru        str   – "F" or hole number or "-"
        r1          int   – round 1 score to par
        r2          int   – round 2 score to par
        r3          int   – round 3 score to par (5 if missed cut)
        r4          int   – round 4 score to par (5 if missed cut)
        missed_cut  bool  – True if r1+r2 > CUT_LINE
    """
    if not rows:
        return []

    # Find the header row (contains "PLAYER")
    header_idx = None
    for i, row in enumerate(rows):
        if any(c.upper() == "PLAYER" for c in row):
            header_idx = i
            break
    if header_idx is None:
        return []

    header = [c.upper() for c in rows[header_idx]]
    data_rows = rows[header_idx + 1:]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return None

    ci_player = col("PLAYER")
    ci_score  = col("SCORE", "TO PAR", "TOPAR")
    ci_today  = col("TODAY")
    ci_thru   = col("THRU")
    ci_r1     = col("R1")
    ci_r2     = col("R2")
    ci_r3     = col("R3")
    ci_r4     = col("R4")

    if ci_player is None:
        return []

    # ── Pass 1: compute R1, R2, and raw data for every player ────────────────
    pass1 = []
    for row in data_rows:
        if not row:
            continue

        def g(ci, default="--"):
            return row[ci].strip() if ci is not None and ci < len(row) else default

        name      = g(ci_player)
        # Strip ESPN's amateur indicator, e.g. "Sam Bennett (a)" → "Sam Bennett"
        if name.endswith(" (a)"):
            name = name[:-4].rstrip()
        score_str = g(ci_score)
        today_str = g(ci_today)
        thru_str  = g(ci_thru)
        r1_str    = g(ci_r1)
        r2_str    = g(ci_r2)
        r3_str    = g(ci_r3)
        r4_str    = g(ci_r4)

        if not name or name.upper() in ("PLAYER", ""):
            continue

        score      = _to_par(score_str)
        today      = _to_par(today_str)
        r1_strokes = _strokes(r1_str)
        r2_strokes = _strokes(r2_str)
        r3_strokes = _strokes(r3_str)
        r4_strokes = _strokes(r4_str)

        # ── R1 ────────────────────────────────────────────────────────────
        if r1_strokes is not None:
            r1 = r1_strokes - PAR
        elif today_str in ("-", "E", "--") or today is None:
            r1 = 0
        else:
            r1 = today

        # ── R2 ────────────────────────────────────────────────────────────
        if r2_strokes is not None:
            r2 = r2_strokes - PAR
        elif today_str in ("-", "E", "--") or today is None:
            r2 = 0
        elif score_str in ("E", "--", "-") or score is None:
            r2 = 0
        else:
            r2 = score - r1

        pass1.append({
            "name": name, "score_str": score_str, "today_str": today_str,
            "thru_str": thru_str, "score": score, "today": today,
            "r1": r1, "r2": r2,
            "r1_strokes": r1_strokes, "r2_strokes": r2_strokes,
            "r3_strokes": r3_strokes, "r4_strokes": r4_strokes,
        })

    # ── Calculate dynamic cut line (top 50 + ties) ───────────────────────────
    # Only applies once R2 strokes are posted for at least 50 players.
    # ESPN's "CUT" label is always authoritative regardless.
    players_with_r2 = [p for p in pass1 if p["r2_strokes"] is not None]
    r2_complete = len(players_with_r2) == len(pass1) and len(pass1) > 0
    if r2_complete:
        two_round_scores = sorted(p["r1"] + p["r2"] for p in players_with_r2)
        cut_line = two_round_scores[CUT_SPOTS - 1]  # score of the 50th player (0-indexed)
    else:
        cut_line = None  # R2 not finished yet; no formula-based cut applied

    # ── Pass 2: apply missed cut, then compute R3/R4 ─────────────────────────
    results = []
    for p in pass1:
        r1, r2 = p["r1"], p["r2"]
        score_str = p["score_str"]
        r3_strokes = p["r3_strokes"]
        r4_strokes = p["r4_strokes"]
        score = p["score"]

        # Missed cut: ESPN label is authoritative; formula only once cut_line known
        missed_cut = (
            score_str.upper() == "CUT"
            or (cut_line is not None and (r1 + r2) > cut_line)
        )

        # ── R3 ────────────────────────────────────────────────────────────
        if missed_cut:
            r3 = 5
        elif r3_strokes is not None:
            r3 = r3_strokes - PAR
        else:
            base = 0 if (score_str in ("-", "E", "--") or score is None) else score
            r3 = base - r1 - r2

        # ── R4 ────────────────────────────────────────────────────────────
        if missed_cut:
            r4 = 5
        elif r4_strokes is not None:
            r4 = r4_strokes - PAR
        else:
            base = 0 if (score_str in ("-", "E", "--") or score is None) else score
            r4 = base - r1 - r2 - r3

        results.append({
            "name":       p["name"],
            "score":      score_str,
            "today":      p["today_str"],
            "thru":       p["thru_str"],
            "r1":         r1,
            "r2":         r2,
            "r3":         r3,
            "r4":         r4,
            "missed_cut": missed_cut,
            "r1_posted":  p["r1_strokes"] is not None,
            "r2_posted":  p["r2_strokes"] is not None,
            "r3_posted":  r3_strokes is not None,
            "r4_posted":  r4_strokes is not None,
        })

    return results


def get_player_scores() -> list[dict]:
    """Fetch ESPN data and return computed player scores."""
    rows = fetch_raw_rows()
    return parse_player_scores(rows)


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching ESPN leaderboard...")
    rows = fetch_raw_rows()

    if not rows:
        print("ERROR: No table found in ESPN page. The page may be JavaScript-rendered.")
        print("Try viewing the page source to confirm a <table> is present.")
    else:
        print(f"Found {len(rows)} raw rows (including header).\n")
        scores = parse_player_scores(rows)

        if not scores:
            print("ERROR: Could not parse player rows. Check column names:")
            print("  Header row found:", rows[0] if rows else "none")
        else:
            fmt = "{:<30} {:>6} {:>6} {:>5} {:>4} {:>4} {:>4} {:>4} {:>4}"
            print(fmt.format("PLAYER", "SCORE", "TODAY", "THRU", "R1", "R2", "R3", "R4", "CUT"))
            print("-" * 80)
            for p in scores:
                cut = "MC" if p["missed_cut"] else ""
                print(fmt.format(
                    p["name"][:30], p["score"], p["today"], p["thru"],
                    p["r1"], p["r2"], p["r3"], p["r4"], cut,
                ))
