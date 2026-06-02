import json
import sys
import os
from collections import defaultdict

def calculate_game_scores(game_data):
    """
    Calculate scores for a single game.
    Returns dictionary with team scores and detailed stats.
    """
    scores = defaultdict(lambda: {'2PT': 0, '3PT': 0, 'FT': 0, 'total': 0})
    
    # Process shot plot data for field goals
    for shot in game_data['shot_plot_data']:
        team = shot['team']
        result = shot['result']
        
        if result == 'Made':
            if shot['shot_type'] == '2PT Field Goal':
                scores[team]['2PT'] += 2
            elif shot['shot_type'] == '3PT Field Goal':
                scores[team]['3PT'] += 3
    
    # Process box score metrics for free throws
    for player in game_data['box_score_metrics']:
        team = player['team']
        scores[team]['FT'] += player['free_throws_made']
    
    # Calculate totals
    for team in scores:
        scores[team]['total'] = scores[team]['2PT'] + scores[team]['3PT'] + scores[team]['FT']
    
    return scores

def print_game_results(game_num, scores, series_info=None):
    """
    Print detailed results for a single game.
    """
    print(f"\n{'='*60}")
    print(f"Game {game_num}")
    if series_info:
        print(f"Series: {series_info}")
    print(f"{'='*60}")
    
    # Sort teams alphabetically for consistent display
    for team in sorted(scores.keys()):
        print(f"\n{team}:")
        print(f"  2PT Field Goals: {scores[team]['2PT']//2} made → {scores[team]['2PT']} points")
        print(f"  3PT Field Goals: {scores[team]['3PT']//3} made → {scores[team]['3PT']} points")
        print(f"  Free Throws:     {scores[team]['FT']} made → {scores[team]['FT']} points")
        print(f"  TOTAL:           {scores[team]['total']} points")
    
    print(f"\n{'─'*60}")
    
    # Determine winner
    teams = list(scores.keys())
    if len(teams) == 2:
        if scores[teams[0]]['total'] > scores[teams[1]]['total']:
            print(f"FINAL SCORE: {teams[0]} {scores[teams[0]]['total']} - {scores[teams[1]]['total']} {teams[1]}")
            print(f"✅ WINNER: {teams[0]}")
            return teams[0]
        else:
            print(f"FINAL SCORE: {teams[0]} {scores[teams[0]]['total']} - {scores[teams[1]]['total']} {teams[1]}")
            print(f"✅ WINNER: {teams[1]}")
            return teams[1]
    else:
        print("⚠️  Unexpected number of teams in game")
        return None

def calculate_series_winner(all_games):
    """
    Calculate series winner across all games.
    Returns dictionary with win counts and game results.
    """
    wins = defaultdict(int)
    game_results = []
    
    for game in all_games:
        game_num = game['game_number']
        
        # Calculate scores for this game
        scores = calculate_game_scores(game)
        
        # Determine winner
        teams = list(scores.keys())
        if len(teams) == 2:
            if scores[teams[0]]['total'] > scores[teams[1]]['total']:
                winner = teams[0]
            else:
                winner = teams[1]
            
            wins[winner] += 1
            game_results.append({
                'game_number': game_num,
                'winner': winner,
                'scores': {teams[0]: scores[teams[0]]['total'], 
                          teams[1]: scores[teams[1]]['total']}
            })
    
    return wins, game_results

def print_series_summary(wins, game_results, series_name=None):
    """
    Print series summary.
    """
    print(f"\n{'='*60}")
    print(f"SERIES SUMMARY")
    if series_name:
        print(f"Series: {series_name}")
    print(f"{'='*60}")
    
    for result in game_results:
        teams = list(result['scores'].keys())
        print(f"Game {result['game_number']}: {teams[0]} {result['scores'][teams[0]]} - {result['scores'][teams[1]]} {teams[1]} → Winner: {result['winner']}")
    
    print(f"\n{'─'*60}")
    
    # Determine series winner
    if len(wins) == 2:
        teams = list(wins.keys())
        print(f"FINAL SERIES RESULT: {teams[0]} {wins[teams[0]]} - {wins[teams[1]]} {teams[1]}")
        
        if wins[teams[0]] > wins[teams[1]]:
            print(f"🏆 {teams[0]} WIN THE SERIES! 🏆")
        else:
            print(f"🏆 {teams[1]} WIN THE SERIES! 🏆")
    else:
        print("⚠️  Could not determine series winner (unexpected number of teams)")

def load_json_file(filename):
    """
    Load JSON file with error handling.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format in '{filename}': {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """
    Main function to run the script.
    """
    # Get filename from command line or user input
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = input("Enter the JSON filename: ").strip()
    
    # Check if file exists
    if not os.path.exists(filename):
        print(f"❌ Error: File '{filename}' not found.")
        return
    
    # Load the JSON data
    data = load_json_file(filename)
    if not data:
        return
    
    # Extract series information
    series_name = data.get('series', 'Unknown Series')
    games = data.get('games', [])
    
    if not games:
        print("❌ Error: No games found in the JSON file.")
        return
    
    print(f"\n📊 Processing: {series_name}")
    print(f"Total games: {len(games)}")
    
    # Process each game and display results
    game_winners = []
    for game in games:
        game_num = game.get('game_number', '?')
        scores = calculate_game_scores(game)
        winner = print_game_results(game_num, scores, series_name)
        game_winners.append(winner)
    
    # Calculate and display series summary
    wins, game_results = calculate_series_winner(games)
    print_series_summary(wins, game_results, series_name)
    
    # Optional: Save results to file
    save_output = input(f"\n💾 Save results to file? (y/n): ").strip().lower()
    if save_output == 'y':
        output_filename = filename.replace('.json', '_scores.txt')
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(f"Series: {series_name}\n")
            f.write(f"{'='*60}\n\n")
            for result in game_results:
                teams = list(result['scores'].keys())
                f.write(f"Game {result['game_number']}: {teams[0]} {result['scores'][teams[0]]} - {result['scores'][teams[1]]} {teams[1]} (Winner: {result['winner']})\n")
            f.write(f"\nFinal Series: {list(wins.keys())[0]} {wins[list(wins.keys())[0]]} - {wins[list(wins.keys())[1]]} {list(wins.keys())[1]}\n")
        print(f"✅ Results saved to: {output_filename}")

if __name__ == "__main__":
    main()