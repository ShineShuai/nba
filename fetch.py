import json
import time
import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, shotchartdetail, boxscoretraditionalv3
from nba_api.stats.endpoints import playbyplayv3
import argparse


# It takes quite long to fetch play-by-play data, use it if you have to.
def get_max_period_optimized(game_id):
    """
    Find max period by checking sequentially until no data is returned.
    More efficient for games without OT.
    """
    period = 1
    max_period = 0
    
    while True:
        try:
            # Fetch just one period at a time
            pbp = playbyplayv3.PlayByPlayV3(
                game_id=game_id, 
                start_period=period, 
                end_period=period
            )
            pbp_df = pbp.get_data_frames()[0]
            
            # If dataframe is empty, no more periods exist
            if pbp_df.empty:
                break
                
            max_period = period
            period += 1
            
        except Exception as e:
            # Error likely means period doesn't exist
            break
    
    return max_period if max_period > 0 else 4


def get_okc_spurs_2026_series():
    print("Querying NBA backend for 2026 Western Conference Finals...")
    
    okc_id = 1610612760
    sas_id = 1610612759
    
    # 1. Pull game history via OKC team log
    okc_games_list = leaguegamefinder.LeagueGameFinder(team_id_nullable=okc_id).get_data_frames()
    okc_games = okc_games_list[0] # Extract the primary DataFrame
    
    # Filter for the specific 2026 playoff matchup
    series_games = okc_games[
        (okc_games['SEASON_ID'].str.endswith('2025')) & 
        (okc_games['MATCHUP'].str.contains('SAS', na=False)) &
        (okc_games['GAME_ID'].str.startswith('004'))  # 004 designates Playoff brackets
    ]
    game_ids = sorted(list(series_games['GAME_ID'].unique()))

    print(f"Successfully located {len(game_ids)} played series games: {game_ids}")
    all_series_payload = []
    
    # 2. Iterate through each game
    for index, game_id in enumerate(game_ids, start=1):
        print(f"Extracting Game {index} (ID: {game_id})...")
        time.sleep(2.0)  # Safe rate-limit defense to prevent API blocks
        
        # --- PART A: COORDINATES FETCH (ShotChartDetail) ---
        shot_data = []
        # shotchart detail of total game
        #for team_id in [okc_id, sas_id]:
        #    try:
        #        sc = shotchartdetail.ShotChartDetail(
        #            league_id='00',             # CRITICAL FIX: Removed '_nullable' suffix
        #            team_id=team_id,
        #            player_id=0,                # 0 pulls all players on the roster
        #            game_id_nullable=game_id,
        #            season_nullable='2025-26',   # Matches 2026 calendar cycle
        #            season_type_all_star='Playoffs',
        #            context_measure_simple='FGA' # Returns BOTH made and missed shots
        #        )
        #        sc_df = sc.get_data_frames()[0]  # Safely parse the primary data frame
        #        
        #        for _, row in sc_df.iterrows():
        #            shot_data.append({
        #                "player_name": row['PLAYER_NAME'],
        #                "team": "OKC" if row['TEAM_ID'] == okc_id else "SAS",
        #                "shot_type": row['SHOT_TYPE'],          # e.g., '2PT Field Goal' or '3PT Field Goal'
        #                "shot_zone": row['SHOT_ZONE_BASIC'],    # e.g., 'Restricted Area', 'Corner 3'
        #                "result": "Made" if int(row['SHOT_MADE_FLAG']) == 1 else "Missed",
        #                "loc_x": int(row['LOC_X']),             # Horizontal court spot (-250 to 250)
        #                "loc_y": int(row['LOC_Y'])              # Vertical court spot (-52 to 400+)
        #            })
        #    except Exception as e:
        #        print(f"Shot Chart extraction note on game {game_id} for Team {team_id}: {e}")

        # shotchart detail per quarter and OT
        period = 1
        
        while True:
            period_label = f"OT{period - 4}" if period > 4 else f"Q{period}"
            period_has_shots = False  # Track if any team logged actions this period
            
            for team_id in [okc_id, sas_id]:
                try:
                    sc = shotchartdetail.ShotChartDetail(
                        league_id='00',             
                        team_id=team_id,
                        player_id=0,                # 0 pulls all players on the roster
                        game_id_nullable=game_id,
                        season_nullable='2025-26',   
                        season_type_all_star='Playoffs',
                        context_measure_simple='FGA', # Returns BOTH made and missed shots
                        period=period               # Dynamically requests current quarter/OT
                    )
                    
                    frames = sc.get_data_frames()
                    if not frames or len(frames) == 0:
                        continue
                        
                    sc_df = frames[0]
                    if sc_df.empty:
                        continue
                    
                    # If execution reaches here, this period contains valid shot records
                    period_has_shots = True
                    
                    for _, row in sc_df.iterrows():
                        shot_data.append({
                            "game_id": game_id,
                            "player_name": row['PLAYER_NAME'],
                            "team": "OKC" if int(row['TEAM_ID']) == okc_id else "SAS",
                            "period": period_label,
                            "shot_type": row['SHOT_TYPE'],          
                            "shot_zone": row['SHOT_ZONE_BASIC'],    
                            "result": "Made" if int(row['SHOT_MADE_FLAG']) == 1 else "Missed",
                            "loc_x": int(row['LOC_X']),             
                            "loc_y": int(row['LOC_Y'])              
                        })
                except Exception as e:
                    print(f"Shot Chart extraction note on game {game_id} for Team {team_id} in {period_label}: {e}")
            
            # CRITICAL DYNAMIC EXIT: If neither team attempted a shot, the game is over
            if not period_has_shots:
                # Fallback: Regulation games must always check at least 4 periods
                if period >= 4:
                    break
                    
            print(f"Extracted {period_label} shots for game {game_id}...")
            period += 1  # Progress to the next period (Q2, Q3, Q4, OT1, OT2...)

                
        # --- PART B: BOX SCORE FETCH (BoxScoreTraditionalV3) ---
        box_metrics = []
        try:
            # scores of total game
            #box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            #box_df = box.get_data_frames()[0] # Target the PlayerStats index frame
            
            #for _, row in box_df.iterrows():
            #    if pd.isna(row['minutes']) or row['minutes'] == "":
            #        continue
            #        
            #    fg3m = int(row.get('threePointersMade', 0))
            #    fg3a = int(row.get('threePointersAttempted', 0))
            #    fg3_missed = max(0, fg3a - fg3m)
            #    
            #    ftm = int(row.get('freeThrowsMade', 0))
            #    fta = int(row.get('freeThrowsAttempted', 0))
            #    ft_missed = max(0, fta - ftm)
            #    
            #    box_metrics.append({
            #        "player_name": f"{row['firstName']} {row['familyName']}",
            #        "team": row['teamTricode'],
            #        "rebounds": int(row.get('reboundsTotal', 0)),
            #        "assists": int(row.get('assists', 0)),
            #        "blocks": int(row.get('blocks', 0)),
            #        "steals": int(row.get('steals', 0)),
            #        "turnovers": int(row.get('turnovers', 0)),
            #        "three_pointers_made": fg3m,
            #        "three_pointers_missed": fg3_missed,
            #        "free_throws_made": ftm,
            #        "free_throws_missed": ft_missed
            #    })
            # scores per quarter and OT
            # 1. Fetch full game data once using V3 to determine total periods played
            full_game = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            period = 1
            while True:
                try:
                    box = boxscoretraditionalv3.BoxScoreTraditionalV3(
                        game_id=game_id,
                        start_period=period,
                        end_period=period,
                        range_type=1  # 1 forces the API to isolate this exact period
                    )
                except AttributeError as e:
                    # This error often indicates we've requested a period that doesn't exist (e.g., OT3 when only 2 OTs were played)
                    break

                data_frames = box.get_data_frames()
                if not data_frames or len(data_frames) == 0:
                    break
                box_df = data_frames[0]
                # If the dataframe is empty, we've gone past the last overtime period
                if box_df.empty:
                    break
                    
                # If no one played any minutes in this period, we've finished the game
                active_players = box_df[
                    (box_df['minutes'].notna()) & 
                    (box_df['minutes'] != "") & 
                    (box_df['minutes'] != "00:00")
                ]
                if active_players.empty:
                    break
                    
                # Label period contextually
                period_label = f"OT{period - 4}" if period > 4 else f"Q{period}"
                print(f"Extracting {period_label} scores for game {game_id}...")

                for _, row in active_players.iterrows():
                    fg3m = int(row.get('threePointersMade', 0))
                    fg3a = int(row.get('threePointersAttempted', 0))
                    fg3_missed = max(0, fg3a - fg3m)
                    
                    ftm = int(row.get('freeThrowsMade', 0))
                    fta = int(row.get('freeThrowsAttempted', 0))
                    ft_missed = max(0, fta - ftm)
                    
                    box_metrics.append({
                        "game_id": game_id,
                        "player_name": f"{row['firstName']} {row['familyName']}",
                        "team": row['teamTricode'],
                        "period": period_label,
                        "minutes": row['minutes'],
                        "rebounds": int(row.get('reboundsTotal', 0)),
                        "assists": int(row.get('assists', 0)),
                        "blocks": int(row.get('blocks', 0)),
                        "steals": int(row.get('steals', 0)),
                        "turnovers": int(row.get('turnovers', 0)),
                        "three_pointers_made": fg3m,
                        "three_pointers_missed": fg3_missed,
                        "free_throws_made": ftm,
                        "free_throws_missed": ft_missed,
                        'oreb': int(row.get('reboundsOffensive', 0)),
                        'dreb': int(row.get('reboundsDefensive', 0)),
                        'fouls_personal': int(row.get('foulsPersonal', 0)),
                        'plus_minus_points': int(row.get('plusMinusPoints', 0))

                    })
                    
                period += 1  # Move to the next period (Q2, Q3, Q4, OT1...)
        except Exception as e:
            print(f"Box score extraction note on game {game_id} for period {period}: {e}")

        # Assemble unified game dictionary block
        all_series_payload.append({
            "game_number": index,
            "game_id": game_id,
            "shot_plot_data": shot_data,
            "box_score_metrics": box_metrics
        })
        
    return json.dumps({"series": "2026 WCF: OKC vs SAS", "games": all_series_payload}, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch NBA game stats")
    parser.add_argument("--output", "-o", default="nba_game.json", help="Output JSON file path")
    args = parser.parse_args()

    output_json = get_okc_spurs_2026_series()
    with open(args.output, "w") as file:
        file.write(output_json)
    print("Process Complete. Spatial data and box scores saved successfully.")
