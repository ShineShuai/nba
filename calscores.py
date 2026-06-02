import json
import sys

def calculate_scores_from_json(json_data):
    """
    Calculate game scores and quarter scores from NBA playoff shot data.
    
    Args:
        json_data: Dictionary containing NBA game data with shot_plot and box_score_metrics
        
    Returns:
        Dictionary with game scores and quarter scores
    """
    results = {
        "series": json_data.get("series", "Unknown Series"),
        "games": []
    }
    
    for game_idx, game in enumerate(json_data["games"]):
        game_number = game["game_number"]
        game_id = game["game_id"]
        
        print(f"Processing Game {game_number}...")
        
        # Initialize score tracking
        game_scores = {
            "game_number": game_number,
            "game_id": game_id,
            "total": {"OKC": 0, "SAS": 0},
            "quarters": {}
        }
        
        # Process shot plot data to calculate scores by quarter
        shot_count = 0
        for shot in game["shot_plot_data"]:
            # Debug: Print first few shots to see structure
            if shot_count < 3:
                print(f"  Sample shot {shot_count + 1}: {shot.keys()}")
            
            # Get period - it exists in your data
            period = shot.get("period")
            if not period:
                shot_count += 1
                continue
                
            team = shot.get("team")
            result = shot.get("result")
            shot_type = shot.get("shot_type")
            
            # Skip if any required field is missing
            if not team or not result or not shot_type:
                shot_count += 1
                continue
            
            # Initialize quarter if not exists
            if period not in game_scores["quarters"]:
                game_scores["quarters"][period] = {"OKC": 0, "SAS": 0}
            
            # Calculate points based on shot type and result
            if result == "Made":
                if shot_type == "3PT Field Goal":
                    points = 3
                elif shot_type == "2PT Field Goal":
                    points = 2
                else:
                    points = 0
                
                if team in game_scores["quarters"][period]:
                    game_scores["quarters"][period][team] += points
                    game_scores["total"][team] += points
            
            shot_count += 1
        
        print(f"  Processed {shot_count} shots")
        
        # Process box score metrics to add free throws
        metric_count = 0
        for metric in game["box_score_metrics"]:
            period = metric.get("period")
            team = metric.get("team")
            
            if not period or not team:
                metric_count += 1
                continue
            
            # Free throws made
            free_throws_made = metric.get("free_throws_made", 0)
            
            if free_throws_made > 0:
                if period not in game_scores["quarters"]:
                    game_scores["quarters"][period] = {"OKC": 0, "SAS": 0}
                
                if team in game_scores["quarters"][period]:
                    game_scores["quarters"][period][team] += free_throws_made
                    game_scores["total"][team] += free_throws_made
            
            metric_count += 1
        
        print(f"  Processed {metric_count} metrics")
        print(f"  Current total: OKC={game_scores['total']['OKC']}, SAS={game_scores['total']['SAS']}")
        
        # Sort quarters in order (Q1, Q2, Q3, Q4, OT1, OT2, etc.)
        def quarter_sort_key(q):
            if q == "Q1": return 1
            if q == "Q2": return 2
            if q == "Q3": return 3
            if q == "Q4": return 4
            if q.startswith("OT"):
                try:
                    return 5 + int(q[2:]) if len(q) > 2 else 5
                except:
                    return 5
            return 99
        
        sorted_quarters = sorted(game_scores["quarters"].items(), key=lambda x: quarter_sort_key(x[0]))
        game_scores["quarters"] = dict(sorted_quarters)
        
        results["games"].append(game_scores)
    
    return results


def print_scores(results):
    """
    Print the calculated scores in a readable format.
    
    Args:
        results: Dictionary with calculated scores
    """
    print("\n" + "=" * 70)
    print(f"Series: {results['series']}")
    print("=" * 70)
    
    for game in results["games"]:
        print(f"\n📊 Game {game['game_number']} (ID: {game['game_id']})")
        print("-" * 60)
        
        # Print quarter scores
        print(f"{'Quarter':<10} {'OKC Thunder':<15} {'SAS Spurs':<15} {'Running Diff':<15}")
        print("-" * 60)
        
        running_okc = 0
        running_sas = 0
        
        for quarter, scores in game["quarters"].items():
            running_okc += scores['OKC']
            running_sas += scores['SAS']
            diff = running_okc - running_sas
            print(f"{quarter:<10} {scores['OKC']:<15} {scores['SAS']:<15} {diff:+d}")
        
        # Print total
        if game["quarters"]:
            print("-" * 60)
            total_diff = game['total']['OKC'] - game['total']['SAS']
            print(f"{'TOTAL':<10} {game['total']['OKC']:<15} {game['total']['SAS']:<15} {total_diff:+d}")
            
            winner = 'OKC' if game['total']['OKC'] > game['total']['SAS'] else 'SAS'
            print(f"\n🏆 Winner: {winner}")
            print(f"📊 Margin: {abs(game['total']['OKC'] - game['total']['SAS'])} points")
            
            # Check if game went to overtime
            has_ot = any(q.startswith('OT') for q in game["quarters"].keys())
            if has_ot:
                print("⏱️  Game went to Overtime!")
        else:
            print("⚠️  No quarter data available for this game")


def save_scores_to_json(results, output_file="game_scores.json"):
    """
    Save the calculated scores to a JSON file.
    
    Args:
        results: Dictionary with calculated scores
        output_file: Name of the output file
    """
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Scores saved to {output_file}")


def calculate_detailed_stats(json_data):
    """
    Calculate detailed statistics from the JSON data.
    
    Args:
        json_data: Dictionary containing NBA game data
    """
    print("\n" + "=" * 70)
    print("DETAILED GAME STATISTICS")
    print("=" * 70)
    
    for game in json_data["games"]:
        game_number = game["game_number"]
        game_id = game["game_id"]
        
        print(f"\nGame {game_number} (ID: {game_id})")
        print("-" * 50)
        
        # Calculate field goals by team
        team_stats = {"OKC": {"fgm": 0, "fga": 0, "tpm": 0, "tpa": 0}, 
                     "SAS": {"fgm": 0, "fga": 0, "tpm": 0, "tpa": 0}}
        
        for shot in game["shot_plot_data"]:
            team = shot.get("team")
            result = shot.get("result")
            shot_type = shot.get("shot_type")
            
            if team and shot_type in ["2PT Field Goal", "3PT Field Goal"]:
                team_stats[team]["fga"] += 1
                if result == "Made":
                    team_stats[team]["fgm"] += 1
                
                if shot_type == "3PT Field Goal":
                    team_stats[team]["tpa"] += 1
                    if result == "Made":
                        team_stats[team]["tpm"] += 1
        
        for team in ["OKC", "SAS"]:
            stats = team_stats[team]
            if stats["fga"] > 0:
                fg_pct = (stats["fgm"] / stats["fga"]) * 100
                three_pct = (stats["tpm"] / stats["tpa"]) * 100 if stats["tpa"] > 0 else 0
                print(f"\n{team}:")
                print(f"  FG: {stats['fgm']}/{stats['fga']} ({fg_pct:.1f}%)")
                print(f"  3PT: {stats['tpm']}/{stats['tpa']} ({three_pct:.1f}%)")
        
        # Show first and last shots for debugging
        if game["shot_plot_data"]:
            print(f"\n  First shot: {game['shot_plot_data'][0].get('player_name')} - {game['shot_plot_data'][0].get('shot_type')}")
            print(f"  Last shot: {game['shot_plot_data'][-1].get('player_name')} - {game['shot_plot_data'][-1].get('shot_type')}")


# Main execution
if __name__ == "__main__":
    # Get filename from command line arguments or use default
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "nba_playoffs_okc_sas_2026.json"
    
    try:
        # Load the JSON data
        with open(filename, "r") as f:
            nba_data = json.load(f)
        
        print(f"✅ Loaded data from {filename}")
        print(f"📋 Series: {nba_data.get('series', 'Unknown')}")
        print(f"🏀 Number of games: {len(nba_data.get('games', []))}")
        
        # Calculate detailed stats first to verify data
        calculate_detailed_stats(nba_data)
        
        # Calculate scores
        print("\n" + "=" * 70)
        print("CALCULATING SCORES")
        print("=" * 70)
        scores = calculate_scores_from_json(nba_data)
        
        # Print results
        print_scores(scores)
        
        # Save to JSON file
        save_scores_to_json(scores)
        
        # Print summary
        print("\n" + "=" * 70)
        print("SERIES SUMMARY")
        print("=" * 70)
        
        okc_wins = sum(1 for game in scores["games"] if game["total"]["OKC"] > game["total"]["SAS"])
        sas_wins = sum(1 for game in scores["games"] if game["total"]["SAS"] > game["total"]["OKC"])
        
        print(f"OKC Thunder: {okc_wins} win(s)")
        print(f"SAS Spurs: {sas_wins} win(s)")
        
        if okc_wins > sas_wins:
            print(f"\n🏆 Series Winner: OKC Thunder (leads {okc_wins}-{sas_wins})")
        elif sas_wins > okc_wins:
            print(f"\n🏆 Series Winner: SAS Spurs (leads {sas_wins}-{okc_wins})")
        else:
            print(f"\n🤝 Series Tied: {okc_wins}-{sas_wins}")
        
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)