# Fantasy Weekly Winner for H2H 1 Win (9 Cat)

## Yahoo Fantasy API
Read https://yahoo-fantasy-api.readthedocs.io/en/latest/introduction.html for app / auth setup.
Update credentials in `private.json`.

## Manual Inputs in File
1. Set league_type, one of (nba, nfl, mlb, nhl, etc)
2. Find league_id from league URL, eg. "144817" from "https://basketball.fantasysports.yahoo.com/nba/144817"
3. Edit `STAT_ID_MAP` if not using `['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']`

## Usage
Run
```
python3 main.py <WEEK NUMBER>
```
eg
```
python3 main.py 1
```
