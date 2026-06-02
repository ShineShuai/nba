
```
jq '[.games[].shot_plot_data[].shot_type] | unique' nba/nba_playoffs_okc_sas_2026.json
[
  "2PT Field Goal",
  "3PT Field Goal"
]
```

```
jq '[.games[].shot_plot_data[].shot_zone] | unique' nba/nba_playoffs_okc_sas_2026.json
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