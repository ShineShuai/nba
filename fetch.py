import json
import time
import re
import pandas as pd
from datetime import date, datetime
from nba_api.stats.endpoints import leaguegamefinder, shotchartdetail, boxscoretraditionalv3, boxscoresummaryv3
from nba_api.stats.endpoints import playbyplayv3
import argparse
import logging

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Team maps — built dynamically from nba_api.stats.static at import time
# ---------------------------------------------------------------------------
from nba_api.stats.static import teams as _nba_teams_static
from nba_api.stats import endpoints as _nba_endpoints
import nba_api

# ---------------------------------------------------------------------------
# Browser-like headers + timeout — prevents NBA API from blocking/timing out
# ---------------------------------------------------------------------------
_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://www.nba.com/",
    "Connection": "keep-alive",
    "Origin": "https://www.nba.com",
}
# default to 30, since longer timeout doesn't seem to help with reliability issues and may cause long hangs;
# it likely dues to the NBA API's internal load and rate-limiting, so fail fast and retry if needed.
_TIMEOUT = 30  # seconds


def _build_team_maps():
    id_map   = {}  # abbr -> team_id
    abbr_map = {}  # team_id -> abbr
    for t in _nba_teams_static.get_teams():
        abbr = t['abbreviation']
        tid  = t['id']
        id_map[abbr]  = tid
        abbr_map[tid] = abbr
    return id_map, abbr_map

TEAM_ID_MAP, TEAM_ABBR_MAP = _build_team_maps()

# ---------------------------------------------------------------------------
# Season ID helpers
# ---------------------------------------------------------------------------
SEASON_TYPE_MAP = {
    "1": "Pre Season",
    "2": "Regular Season",
    "3": "All Star",
    "4": "Playoffs",
    "5": "PlayIn",
}

def parse_season_id(season_id: str):
    """
    '42024' → season_type='Playoffs', season_nullable='2024-25'
    '22023' → season_type='Regular Season', season_nullable='2023-24'
    """
    prefix = season_id[0]
    year = int(season_id[1:])
    season_type = SEASON_TYPE_MAP.get(prefix, "Regular Season")
    season_str = f"{year}-{str(year + 1)[-2:]}"
    return season_type, season_str

def current_season_str() -> str:
    """Return NBA season string for today, e.g. '2025-26'."""
    today = date.today()
    # NBA season starts in October; before Oct → season that ended this year
    year = today.year if today.month >= 10 else today.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


# game_id digit at index 2: '0022500467' → '2' → Regular Season
# 006: In-Season Tournament group/knockout games, e.g. NBA cup finals
_GAME_ID_TYPE_MAP = {
    "1": "Pre Season", "2": "Regular Season", "3": "All Star",
    "4": "Playoffs",   "5": "PlayIn", "6": "IST",
}

def season_type_from_game_id(game_id: str) -> str:
    return _GAME_ID_TYPE_MAP.get(game_id[2], "Regular Season")

# ---------------------------------------------------------------------------
# Game ID resolution
# ---------------------------------------------------------------------------

# Excluded game type digits when no -s/-d given (Pre Season=1, All Star=3)
_DEFAULT_EXCLUDED_PREFIXES = {'1', '3'}

def resolve_game_ids(teams, n, from_date, season_id):
    # n=None means return all matching games
    if season_id:
        season_type, season_str = parse_season_id(season_id)
    else:
        season_type = None          # no filter -> all game types
        season_str  = current_season_str()

    query_team_id = TEAM_ID_MAP[teams[0]] if teams else None

    print(f"Querying LeagueGameFinder: season={season_str}, type={season_type or 'ALL'}, team={teams[0] if teams else 'ALL'}...")

    kwargs = dict(season_nullable=season_str)
    if season_type:
        kwargs["season_type_nullable"] = season_type
    if query_team_id:
        kwargs["team_id_nullable"] = query_team_id

    #print(f"LeagueGameFinder query parameters: {kwargs}")
    #gf = leaguegamefinder.LeagueGameFinder(**kwargs, headers=_HEADERS, timeout=_TIMEOUT)
    gf = leaguegamefinder.LeagueGameFinder(**kwargs)
    games = gf.get_data_frames()[0]

    if games.empty:
        print("No games found for the given parameters.")
        return [], season_type or "All", season_str, teams

    if len(teams) == 2:
        opponent = teams[1]
        games = games[games['MATCHUP'].str.contains(opponent, na=False)]

    if from_date:
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        games = games[games['GAME_DATE'] >= pd.Timestamp(from_date)]

    # Without -s and -d: strip Pre Season and All Star by game_id digit at index 2
    if not season_id and not from_date:
        games = games[~games['GAME_ID'].str[2].isin(_DEFAULT_EXCLUDED_PREFIXES)]

    unique_ids = (
        games.drop_duplicates(subset='GAME_ID')
             .sort_values('GAME_DATE')['GAME_ID']
             .tolist()
    )
    selected = unique_ids if n is None else unique_ids[-n:]
    # Build game_id -> GAME_DATE string map for selected games
    deduped = games.drop_duplicates(subset='GAME_ID').set_index('GAME_ID')
    game_date_map = {gid: str(deduped.loc[gid, 'GAME_DATE']) for gid in selected if gid in deduped.index}
    print(f"Located {len(selected)} game(s): {selected}")
    return selected, season_type or "All", season_str, teams, game_date_map


def build_series_label(teams, season_type, season_str, season_id, n):
    team_part = " vs ".join(teams) if teams else "All teams"
    sid_part  = f" [{season_id}]" if season_id else ""
    return f"Last {n} {season_type} games: {team_part} ({season_str}){sid_part}"

# ---------------------------------------------------------------------------
# Per-game fetch (unchanged logic, generalised team list)
# ---------------------------------------------------------------------------

def get_game_team_ids(game_id):
    """
    Resolve the two team IDs that played in a game via box score (period 1).
    Returns list of int team IDs.
    """
    try:
        box = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id, start_period=1, end_period=1, range_type=1
        )
        df = box.get_data_frames()[0]
        if df.empty:
            return []
        return list(df['teamId'].dropna().astype(int).unique())
    except Exception as e:
        logging.error(f"  Could not resolve team IDs for {game_id}: {e}")
        return []


def fetch_game(game_id, index, all_team_ids, season_str, season_type, game_date=None):
    """
    Fetch shot chart + box score for one game_id.
    all_team_ids: team IDs supplied via -t; if empty, resolved from box score.
    game_date: date string from LeagueGameFinder (YYYY-MM-DD), enriched with
               game time from BoxScoreTraditionalV3 summary if available.
    """
    print(f"Extracting Game {index} (ID: {game_id})...")

    # Enrich game_date with tip-off time from BoxScoreSummaryV3 if available
    try:
        summary = boxscoresummaryv3.BoxScoreSummaryV3(
            game_id=game_id
        )
        # Frame 0 = GameSummary; contains gameTimeUTC, gameStatusText, and other metadata
        gs = summary.get_data_frames()[0]
        if not gs.empty:
            date_raw = str(gs.iloc[0].get('gameTimeUTC', ''))
            date_utc = date_raw.split('T')[0]
            status   = str(gs.iloc[0].get('gameStatusText', '')).strip()
            print(f"  Original date: {game_date}, raw date: {date_raw}, UTC date: {date_utc}, status: {status}")
            # status is e.g. 'Final', '7:30 pm ET', 'PPD'
            import re as _re
            if _re.search(r'\d+:\d+', status):  # contains a time
                game_date = f"{date_utc} {status}" if date_utc else status
            elif date_utc:
                game_date = date_raw
    except Exception as e:
        logging.error(f"  game date/time note for {game_id}: {e}")

    # Derive correct season_type_all_star from game_id prefix — overrides aggregate label
    shot_season_type = season_type_from_game_id(game_id)

    # Always fetch shot data for both teams in the game, regardless of -t filter
    team_ids = get_game_team_ids(game_id)
    if not team_ids:
        print(f"  No team IDs found for {game_id}, skipping shot chart.")
        team_ids = []

    print(f"  team IDs for shot chart: {[TEAM_ABBR_MAP.get(id, str(id)) for id in team_ids]} date {game_date} season_type {shot_season_type}")

    # --- PART A: SHOT CHART (per-team, matching original approach) ---
    shot_data = []
    period = 1
    while True:
        period_label = f"OT{period - 4}" if period > 4 else f"Q{period}"
        period_has_shots = False

        shot_cnt = 0
        for team_id in team_ids:
            try:
                sc = shotchartdetail.ShotChartDetail(
                    league_id='00',
                    team_id=team_id,
                    player_id=0,
                    game_id_nullable=game_id,
                    season_nullable=season_str,
                    season_type_all_star=shot_season_type,
                    context_measure_simple='FGA',
                    period=period,
                    timeout=_TIMEOUT,
                )
                frames = sc.get_data_frames()
                if not frames or frames[0].empty:
                    continue
                period_has_shots = True
                sc_df = frames[0]
                abbr = TEAM_ABBR_MAP.get(team_id, str(team_id))
                for _, row in sc_df.iterrows():
                    shot_data.append({
                        "game_id":     game_id,
                        "player_name": row['PLAYER_NAME'],
                        "team":        abbr,
                        "period":      period_label,
                        "shot_type":   row['SHOT_TYPE'],
                        "shot_zone":   row['SHOT_ZONE_BASIC'],
                        "result":      "Made" if int(row['SHOT_MADE_FLAG']) == 1 else "Missed",
                        "loc_x":       int(row['LOC_X']),
                        "loc_y":       int(row['LOC_Y']),
                    })
                shot_cnt += len(sc_df)
            except Exception as e:
                logging.error(f"  Shot chart note game {game_id} team {team_id} {period_label}: {e}")

        if not period_has_shots and period >= 4:
            break
        if period_has_shots:
            print(f"  Extracted {period_label} {shot_cnt} shots for game {game_id}")
        period += 1

    # --- PART B: BOX SCORE ---
    box_metrics = []
    try:
        period = 1
        while True:
            period_label = f"OT{period - 4}" if period > 4 else f"Q{period}"
            try:
                box = boxscoretraditionalv3.BoxScoreTraditionalV3(
                    game_id=game_id,
                    start_period=period,
                    end_period=period,
                    range_type=1,
                    timeout=_TIMEOUT,
                )
            except AttributeError:
                break

            data_frames = box.get_data_frames()
            if not data_frames or len(data_frames) == 0:
                break
            box_df = data_frames[0]
            if box_df.empty:
                break

            active_players = box_df[
                (box_df['minutes'].notna()) &
                (box_df['minutes'] != "") &
                (box_df['minutes'] != "00:00")
            ]
            if active_players.empty:
                break

            print(f"  Extracting {period_label} {len(active_players)} box score for game {game_id}...")

            for _, row in active_players.iterrows():
                fg3m = int(row.get('threePointersMade', 0))
                fg3a = int(row.get('threePointersAttempted', 0))
                ftm  = int(row.get('freeThrowsMade', 0))
                fta  = int(row.get('freeThrowsAttempted', 0))

                box_metrics.append({
                    "game_id":             game_id,
                    "player_name":         f"{row['firstName']} {row['familyName']}",
                    "team":                row['teamTricode'],
                    "period":              period_label,
                    "minutes":             row['minutes'],
                    "rebounds":            int(row.get('reboundsTotal', 0)),
                    "assists":             int(row.get('assists', 0)),
                    "blocks":              int(row.get('blocks', 0)),
                    "steals":              int(row.get('steals', 0)),
                    "turnovers":           int(row.get('turnovers', 0)),
                    "three_pointers_made":   fg3m,
                    "three_pointers_missed": max(0, fg3a - fg3m),
                    "free_throws_made":      ftm,
                    "free_throws_missed":    max(0, fta - ftm),
                    "oreb":                int(row.get('reboundsOffensive', 0)),
                    "dreb":                int(row.get('reboundsDefensive', 0)),
                    "fouls_personal":      int(row.get('foulsPersonal', 0)),
                    "plus_minus_points":   int(row.get('plusMinusPoints', 0)),
                })

            period += 1
    except Exception as e:
        logging.error(f"  Box score note game {game_id} {period_label}: {e}")

    return {
        "game_number":     index,
        "game_id":         game_id,
        "game_date":       game_date,
        "shot_plot_data":  shot_data,
        "box_score_metrics": box_metrics,
    }

# ---------------------------------------------------------------------------
# Continue / patch helpers
# ---------------------------------------------------------------------------

def _period_label(period: int) -> str:
    return f"OT{period - 4}" if period > 4 else f"Q{period}"

def _period_int(label: str) -> int:
    if label.startswith("OT"):
        return 4 + int(label[2:])
    return int(label[1:])  # "Q1" -> 1


_FULL_REFETCH_SENTINEL = object()  # returned by audit_game when full re-fetch needed


def get_finished_periods(game_id: str) -> set:
    """
    Query BoxScoreSummaryV3 to get the set of period labels that actually
    occurred in a finished game.  Falls back to {Q1,Q2,Q3,Q4} on error.
    """
    try:
        summary = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id)
        frames  = summary.get_data_frames()
        period_set = set()
        for df in frames:
            cols_lower = [c.lower() for c in df.columns]
            if 'period' in cols_lower:
                col = df.columns[cols_lower.index('period')]
                for v in df[col].dropna().unique():
                    try:
                        period_set.add(_period_label(int(v)))
                    except (ValueError, TypeError):
                        pass
        if period_set:
            return period_set
    except Exception as e:
        logging.error(f"    get_finished_periods note {game_id}: {e}")
    return {_period_label(p) for p in range(1, 5)}


def audit_game(game: dict):
    """
    Return (missing_shot_periods, missing_box_periods) as sets of period labels,
    or _FULL_REFETCH_SENTINEL if the game has no data at all.

    Uses BoxScoreSummaryV3 as ground truth for period count so partial fetches
    (crash after Q1, etc.) are correctly detected.
    """
    shot_periods = {r["period"] for r in game.get("shot_plot_data", [])}
    box_periods  = {r["period"] for r in game.get("box_score_metrics", [])}

    if not shot_periods and not box_periods:
        return _FULL_REFETCH_SENTINEL

    expected = get_finished_periods(game["game_id"])

    missing_shot = expected - shot_periods
    missing_box  = expected - box_periods

    return missing_shot, missing_box


def fetch_shot_period(game_id: str, period: int, team_ids: list,
                      season_str: str, season_type: str) -> list:
    """Fetch shot chart for one period; return list of shot dicts."""
    shot_season_type = season_type_from_game_id(game_id)
    shots = []
    for team_id in team_ids:
        try:
            sc = shotchartdetail.ShotChartDetail(
                league_id='00',
                team_id=team_id,
                player_id=0,
                game_id_nullable=game_id,
                season_nullable=season_str,
                season_type_all_star=shot_season_type,
                context_measure_simple='FGA',
                period=period,
                timeout=_TIMEOUT,
            )
            frames = sc.get_data_frames()
            if not frames or frames[0].empty:
                continue
            abbr = TEAM_ABBR_MAP.get(team_id, str(team_id))
            for _, row in frames[0].iterrows():
                shots.append({
                    "game_id":     game_id,
                    "player_name": row['PLAYER_NAME'],
                    "team":        abbr,
                    "period":      _period_label(period),
                    "shot_type":   row['SHOT_TYPE'],
                    "shot_zone":   row['SHOT_ZONE_BASIC'],
                    "result":      "Made" if int(row['SHOT_MADE_FLAG']) == 1 else "Missed",
                    "loc_x":       int(row['LOC_X']),
                    "loc_y":       int(row['LOC_Y']),
                })
        except Exception as e:
            logging.error(f"    Shot patch note {game_id} team {team_id} {_period_label(period)}: {e}")
    return shots


def fetch_box_period(game_id: str, period: int) -> list:
    """Fetch box score for one period; return list of metric dicts."""
    metrics = []
    try:
        box = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id,
            start_period=period,
            end_period=period,
            range_type=1,
            timeout=_TIMEOUT,
        )
        frames = box.get_data_frames()
        if not frames or frames[0].empty:
            return metrics
        active = frames[0]
        active = active[
            (active['minutes'].notna()) &
            (active['minutes'] != "") &
            (active['minutes'] != "00:00")
        ]
        period_label = _period_label(period)
        for _, row in active.iterrows():
            fg3m = int(row.get('threePointersMade', 0))
            fg3a = int(row.get('threePointersAttempted', 0))
            ftm  = int(row.get('freeThrowsMade', 0))
            fta  = int(row.get('freeThrowsAttempted', 0))
            metrics.append({
                "game_id":               game_id,
                "player_name":           f"{row['firstName']} {row['familyName']}",
                "team":                  row['teamTricode'],
                "period":                period_label,
                "minutes":               row['minutes'],
                "rebounds":              int(row.get('reboundsTotal', 0)),
                "assists":               int(row.get('assists', 0)),
                "blocks":                int(row.get('blocks', 0)),
                "steals":                int(row.get('steals', 0)),
                "turnovers":             int(row.get('turnovers', 0)),
                "three_pointers_made":   fg3m,
                "three_pointers_missed": max(0, fg3a - fg3m),
                "free_throws_made":      ftm,
                "free_throws_missed":    max(0, fta - ftm),
                "oreb":                  int(row.get('reboundsOffensive', 0)),
                "dreb":                  int(row.get('reboundsDefensive', 0)),
                "fouls_personal":        int(row.get('foulsPersonal', 0)),
                "plus_minus_points":     int(row.get('plusMinusPoints', 0)),
            })
    except Exception as e:
        logging.error(f"    Box patch note {game_id} {_period_label(period)}: {e}")
    return metrics


def patch_game(game: dict, season_str: str, season_type: str,
               game_index: int = 0, all_team_ids: list = None, game_date: str = None) -> bool:
    """
    Audit game dict and fetch+append any missing period data.
    If the game has no data at all, does a full re-fetch in place.
    Returns True if anything was patched.
    """
    game_id = game["game_id"]
    result  = audit_game(game)

    if result is _FULL_REFETCH_SENTINEL:
        print(f"  Game {game_id}: no data — full re-fetch...")
        fresh = fetch_game(game_id, game_index, all_team_ids or [], season_str,
                           season_type, game_date=game_date)
        game.update(fresh)
        return True

    missing_shot, missing_box = result

    if not missing_shot and not missing_box:
        print(f"  Game {game_id}: complete, skipping.")
        return False

    team_ids = get_game_team_ids(game_id)

    patched = False

    for label in sorted(missing_shot, key=_period_int):
        p = _period_int(label)
        print(f"  Game {game_id}: fetching missing shot period {label}...")
        new_shots = fetch_shot_period(game_id, p, team_ids, season_str, season_type)
        game["shot_plot_data"].extend(new_shots)
        print(f"    → {len(new_shots)} shot(s) added for {label}")
        patched = True
        time.sleep(0.6)

    for label in sorted(missing_box, key=_period_int):
        p = _period_int(label)
        print(f"  Game {game_id}: fetching missing box period {label}...")
        new_metrics = fetch_box_period(game_id, p)
        game["box_score_metrics"].extend(new_metrics)
        print(f"    → {len(new_metrics)} player row(s) added for {label}")
        patched = True
        time.sleep(0.6)

    return patched


def continue_fetch(path: str, all_team_ids: list, season_str: str,
                   season_type: str, game_ids: list, game_date_map: dict,
                   series_label: str):
    """
    Load existing JSON at `path`, patch missing periods, add missing games,
    then overwrite the file.
    """
    try:
        with open(path) as f:
            data = json.load(f)
        print(f"Loaded {path}: {len(data['games'])} game(s) found.")
    except FileNotFoundError:
        print(f"{path} not found — running full fetch.")
        data = {"series": series_label, "games": []}
    except json.JSONDecodeError as e:
        print(f"JSON parse error in {path}: {e}. Aborting.")
        return

    existing_ids = {g["game_id"]: i for i, g in enumerate(data["games"])}
    any_change = False

    # 1. Patch existing games
    id_order = {gid: i for i, gid in enumerate(game_ids)}
    for game in data["games"]:
        gid   = game["game_id"]
        idx   = id_order.get(gid, 0) + 1
        gdate = game_date_map.get(gid) or game.get("game_date")
        if patch_game(game, season_str, season_type,
                      game_index=idx, all_team_ids=all_team_ids, game_date=gdate):
            any_change = True

    # 2. Fetch games not yet in the file
    for idx, gid in enumerate(game_ids, start=1):
        if gid not in existing_ids:
            print(f"Game {gid} missing from JSON — full fetch...")
            game_payload = fetch_game(gid, idx, all_team_ids, season_str,
                                      season_type, game_date=game_date_map.get(gid))
            data["games"].append(game_payload)
            any_change = True

    if not any_change:
        print("No gaps found. File unchanged.")
        return

    # Re-sort by game_number/game_id order from resolved list
    id_order = {gid: i for i, gid in enumerate(game_ids)}
    data["games"].sort(key=lambda g: id_order.get(g["game_id"], 9999))

    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Done. Updated {path}")


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Fetch NBA game stats into a self-contained JSON file.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-o", "--output",    default="nba_game.json",
                        help="Output JSON file path (default: nba_game.json)")
    parser.add_argument("-n", "--num-games", type=int, default=None,
                        help="Max games to fetch. Default: all games matching filters,\n"
                             "excluding Pre Season and All Star when no -s/-d given.")
    parser.add_argument("-t", "--teams",     nargs="+", metavar="TEAM",
                        help="1 or 2 team abbreviations, e.g.  -t OKC  or  -t OKC SAS")
    parser.add_argument("-d", "--date",      metavar="YYYY-MM-DD",
                        help="Lower-bound date; fetch last N games from this date to today")
    parser.add_argument("-s", "--season-id", metavar="SEASON_ID",
                        help="Season ID, e.g. '42024' (2024-25 Playoffs), '22023' (2023-24 Regular)")
    parser.add_argument("-c", "--continue",  dest="continue_mode", action="store_true",
                        help="Continue/patch mode: load existing -o JSON, fetch only missing\n"
                             "periods (shot plot or box score) and add any new games.")
    args = parser.parse_args()

    # Validate teams
    teams = []
    if args.teams:
        for t in args.teams[:2]:
            t = t.upper()
            if t not in TEAM_ID_MAP:
                parser.error(f"Unknown team abbreviation: {t}")
            teams.append(t)

    # Validate date
    from_date = None
    if args.date:
        try:
            from_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            parser.error(f"Invalid date format: {args.date} (expected YYYY-MM-DD)")

    # Validate season_id
    if args.season_id:
        if not re.match(r'^[12345]\d{4}$', args.season_id):
            parser.error(f"Invalid season_id '{args.season_id}'. Expected format: prefix(1-5) + 4-digit year, e.g. '42024'")

    # Resolve game IDs
    game_ids, season_type, season_str, teams, game_date_map = resolve_game_ids(
        teams, args.num_games, from_date, args.season_id
    )

    if not game_ids:
        print("No games found. Exiting.")
        return

    n_label = args.num_games if args.num_games is not None else len(game_ids)
    series_label = build_series_label(teams, season_type, season_str, args.season_id, n_label)
    print(f"Series label: {series_label}")

    # Determine team IDs for shot chart (empty → team_id=0 covers all)
    all_team_ids = [TEAM_ID_MAP[t] for t in teams]

    if args.continue_mode:
        continue_fetch(
            path=args.output,
            all_team_ids=all_team_ids,
            season_str=season_str,
            season_type=season_type,
            game_ids=game_ids,
            game_date_map=game_date_map,
            series_label=series_label,
        )
        return

    all_games = []
    for idx, gid in enumerate(game_ids, start=1):
        game_payload = fetch_game(gid, idx, all_team_ids, season_str, season_type,
                                  game_date=game_date_map.get(gid))
        all_games.append(game_payload)

    result = json.dumps({"series": series_label, "games": all_games}, indent=4)

    with open(args.output, "w") as f:
        f.write(result)
    print(f"Done. {len(all_games)} game(s) saved to {args.output}")


if __name__ == "__main__":
    main()