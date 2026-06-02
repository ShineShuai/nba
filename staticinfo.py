import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder
import inspect
from nba_api.stats import endpoints


def list_all_teams():
    nba_teams = teams.get_teams()
    df_teams = pd.DataFrame(nba_teams)

    df_teams.columns = [col.upper().replace('_', ' ') for col in df_teams.columns]

    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000)

    print(f"\n==================================================")
    print("🛡️ NBA Teams:")
    print(df_teams)

def list_latest_games():
    # By default, this endpoint returns games across multiple seasons and types
    game_finder = leaguegamefinder.LeagueGameFinder(player_or_team_abbreviation='T')
    games_df = game_finder.get_data_frames()[0]

    # Important columns returned:
    # - 'GAME_ID': Unique identifier for the match
    # - 'TEAM_ID': Unique identifier for the team 
    # - 'TEAM_NAME': The full name of the team
    # - 'MATCHUP': Displays who played whom (e.g., "GSW vs. LAL" or "GSW @ LAL")
    # - 'SEASON_ID': Encodes the Game Type and Season Year
    relevant_games = games_df[['GAME_ID', 'TEAM_ID', 'TEAM_NAME', 'MATCHUP', 'SEASON_ID']]
    print(f"\n==================================================")
    print("🏀 Latest Games:")
    print(games_df.head())
    print(relevant_games.head(10))  # Display the first 10 rows to verify structure

# Define the specific endpoints you want to extract fields from
target_endpoints = {
    "LeagueGameFinder": endpoints.leaguegamefinder.LeagueGameFinder,
    "PlayByPlay": endpoints.playbyplayv3.PlayByPlayV3,
    "ShotChartDetail": endpoints.shotchartdetail.ShotChartDetail,
    "BoxScoreTraditional": endpoints.boxscoretraditionalv3.BoxScoreTraditionalV3
}

def clean_print_fields(fields):
    """Formats list elements cleanly in compact rows of 4."""
    chunked_fields = [fields[i:i + 4] for i in range(0, len(fields), 4)]
    for chunk in chunked_fields:
        formatted_line = ", ".join([f"[{f}]" for f in chunk])
        print(f"     {formatted_line}")

def list_all_endpoint_fields(endpoint_dict):
    for name, endpoint_class in endpoint_dict.items():
        print(f"\n==================================================")
        print(f" 📦 ENDPOINT: {name} ({endpoint_class.__name__})")
        print(f"==================================================")
        
        # 1. Fetch initialization signature parameters 
        init_params = inspect.signature(endpoint_class.__init__).parameters
        param_list = [p for p in init_params if p != 'self']
        print(f"💡 Query Parameters: {', '.join(param_list)}")
        print(f"--------------------------------------------------")
        
        # 2. STRATEGY A: Fast local lookup via metadata
        if hasattr(endpoint_class, 'expected_data_sets') and endpoint_class.expected_data_sets:
            for dataset_name, fields in endpoint_class.expected_data_sets.items():
                print(f"📊 Table/DataSet (Static Match): '{dataset_name}'")
                print(f"   ↳ Total Fields ({len(fields)}):")
                clean_print_fields(fields)
            continue
            
        # 3. STRATEGY B: Live Fallback Pipeline
        print("⏳ Empty package metadata. Launching live fallback query...")
        try:
            # Inject custom valid parameters depending on what the endpoint requires
            if name == "LeagueGameFinder":
                live_instance = endpoint_class(player_or_team_abbreviation='T', team_id_nullable=0)
            elif name == "ShotChartDetail":
                # ShotChartDetail requires a specific measure and structural IDs to execute
                live_instance = endpoint_class(
                    context_measure_simple='FGA',
                    team_id=0,
                    player_id=0,
                    season_nullable='2023-24'
                )
            else:
                # Target a safe generic sample game ID string format for V3 endpoints
                live_instance = endpoint_class(game_id='0022300001')
            
            # --- Check if the endpoint outputs raw dataframes directly ---
            if hasattr(live_instance, 'get_data_frames'):
                dfs = live_instance.get_data_frames()
                
                # Handle endpoints that return a list of multiple dataframes (e.g. BoxScores)
                if isinstance(dfs, list):
                    # Use internal mapping keys if available, otherwise fallback to index labels
                    for idx, df in enumerate(dfs):
                        fields = list(df.columns)
                        print(f"📊 Table/DataSet (Live DataFrame {idx + 1}):")
                        print(f"   ↳ Total Fields ({len(fields)}):")
                        clean_print_fields(fields)
                else:
                    fields = list(dfs.columns)
                    print(f"📊 Table/DataSet (Live DataFrame):")
                    print(f"   ↳ Total Fields ({len(fields)}):")
                    clean_print_fields(fields)
                continue

            # --- Legacy fallback handler for standard JSON objects ---
            raw_dict = live_instance.get_dict()
            result_sets = raw_dict.get('resultSets', []) or raw_dict.get('resultSet', [])
            if isinstance(result_sets, dict): 
                result_sets = [result_sets]
                
            for table in result_sets:
                dataset_name = table.get('name')
                fields = table.get('headers', [])
                print(f"📊 Table/DataSet (Live Legacy Fallback): '{dataset_name}'")
                print(f"   ↳ Total Fields ({len(fields)}):")
                clean_print_fields(fields)
                
        except Exception as e:
            print(f"⚠️ Error parsing live layout data structure for {name}: {str(e)}")

if __name__ == "__main__":
    list_all_teams()
    list_latest_games()
    list_all_endpoint_fields(target_endpoints)
