## Example Usage
```bash
# list static info supported by nba api client, e.g. game, team, fields of endpoints
python3 staticinfo.py
# fetch data from nba stats via nba api client
uv run --with nba_api --with pandas fetch.py -o data/nba_playoffs_okc_sas_2026.json
# generate an HTML to visualize the data
python3 nbajson2html.py data/nba_playoffs_okc_sas_2026.json statsboard.html
```

## Sample data from NBA stats
```bash
jq '[.games[].shot_plot_data[].shot_type] | unique' data/nba_playoffs_okc_sas_2026.json
[
  "2PT Field Goal",
  "3PT Field Goal"
]
```

```bash
jq '[.games[].shot_plot_data[].shot_zone] | unique' data/nba_playoffs_okc_sas_2026.json
[
  "Above the Break 3",
  "Backcourt",
  "In The Paint (Non-RA)",
  "Left Corner 3",
  "Mid-Range",
  "Restricted Area",
  "Right Corner 3"
]
```

## Season ID
```python
def decode_season_id(season_id_str):
    """
    Converts an NBA API 5-digit SEASON_ID string into a human-readable format.
    Example: '22023' -> '2023-24 Regular Season'
             '42024' -> '2024-25 Playoffs'
    """
    if not season_id_str or len(str(season_id_str)) != 5:
        return "Unknown Season"
    
    # Convert to string to ensure zero-padding matches if numeric
    s_id = str(season_id_str)
    
    # 1. Map the first digit to the Game Type
    type_digit = s_id[0]
    type_map = {
        "1": "Pre-season",
        "2": "Regular Season",
        "3": "All-Star",
        "4": "Playoffs",
        "5": "Play-In"
    }
    game_type = type_map.get(type_digit, "Unknown Type")
    
    # 2. Extract the 4-digit start year
    start_year = int(s_id[1:5])
    end_year_short = str(start_year + 1)[-2:]  # Gets the last 2 digits of the next year
    
    # 3. Handle specific single-year formats if applicable (like All-Star)
    if game_type == "All-Star":
        return f"{start_year} {game_type}"
        
    return f"{start_year}-{end_year_short} {game_type}"
```

