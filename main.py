#!/usr/bin/python
from collections import defaultdict
from yahoo_oauth import OAuth2

import itertools
import yahoo_fantasy_api as yfa
import sys


# MANUAL INPUTS
LEAGUE_TYPE = "nba"  # only tested for NBA 2021
LEAGUE_ID = "144817"


# READ + VALIDATE WEEK INPUT
if len(sys.argv) != 2:
    raise TypeError("Requires only 1 input - the week to measure")

try:
    int(sys.argv[1])
except Exception as e:
    raise e


# SETUP YFA + SET LEAGUE INPUTS
sc = OAuth2(None, None, from_file="private.json")

GAME_KEY = yfa.Game(sc, LEAGUE_TYPE).game_id()
LEAGUE_KEY = f"{GAME_KEY}.l.{LEAGUE_ID}"
WEEK = sys.argv[1]
STAT_ID_MAP = {
    "5": "FG%",
    "8": "FT%",
    "10": "3PTM",
    "12": "PTS",
    "15": "REB",
    "16": "AST",
    "17": "ST",
    "18": "BLK",
    "19": "TO",
}


# HELPER METHODS
def digest_team_stats(stats_obj):
    stat_map = {}
    for stat_obj in stats_obj:
        key = stat_obj["stat"]["stat_id"]
        val = stat_obj["stat"]["value"]
        if key not in STAT_ID_MAP:
            continue
        stat_map[STAT_ID_MAP[key]] = float(val) if val else 0
    return stat_map


def digest_matchup_stats(team_obj):
    team_name = team_obj["team"][0][2]["name"]
    team_stats = team_obj["team"][1]["team_stats"]["stats"]
    teams[team_name] = digest_team_stats(team_stats)


def simulate_matchup(team1, team2):
    team1_stats = teams[team1]
    team2_stats = teams[team2]
    team1_record = [0, 0, 0]  # wins,losses,ties
    team2_record = [0, 0, 0]  # wins,losses,ties
    for stat in team1_stats:
        if team1_stats[stat] > team2_stats[stat]:
            if stat == "TO":
                team1_record[1] += 1
                team2_record[0] += 1
            else:
                team1_record[0] += 1
                team2_record[1] += 1
        elif team1_stats[stat] < team2_stats[stat]:
            if stat == "TO":
                team1_record[0] += 1
                team2_record[1] += 1
            else:
                team1_record[1] += 1
                team2_record[0] += 1
        else:
            team1_record[2] += 1
            team2_record[2] += 1
    return team1_record, team2_record


def update_win_record(name, record):
    wins[name] += 1 if record[0] > record[1] else 0
    if name not in total_record:
        total_record[name] = record
    else:
        total_record[name] = [a + b for a, b in zip(record, total_record[name])]


# 1. PULL DATA FROM YAHOO MATCHUPS
league = yfa.League(sc, LEAGUE_KEY)
response = league.matchups(WEEK)["fantasy_content"]["league"]
league_name = response[0]["name"]
matchups = response[1]["scoreboard"]["0"]["matchups"]

current_week = int(response[0]["current_week"])
if not (0 < int(WEEK) <= current_week):
    raise ValueError(f"Week needs to be > 1 and <= current week ({current_week})")


# 2. DIGEST STATS INFO INTO TEAMS DICT
teams = {value["name"]: {} for value in league.teams().values()}

for matchup in matchups.values():
    if not isinstance(matchup, dict):
        continue
    team_ids = matchup["matchup"]["0"]["teams"]
    digest_matchup_stats(team_ids["0"])
    digest_matchup_stats(team_ids["1"])


# 3. CALCULATE WINS AGAINST ALL OTHER TEAMS AND TOTAL CATS WON
all_pos_matchups = list(itertools.combinations(teams, 2))
wins = defaultdict(int)
total_record = {}

for team1, team2 in all_pos_matchups:
    team1_record, team2_record = simulate_matchup(team1, team2)
    update_win_record(team1, team1_record)
    update_win_record(team2, team2_record)


# 4. PRINT INFO
def pretty_print(title, items):
    print("**", title.upper(), "**")
    for item in items:
        print(f'{item[0]:<25s}{item[1]}')
    print()


print("***", league_name, "-- WEEK", WEEK, " ***", end="\n\n")
pretty_print("Stats", teams.items())
pretty_print("Total", sorted(total_record.items(), key=lambda x: (x[1][0], -x[1][1]), reverse=True))
pretty_print("Wins", sorted(wins.items(), key=lambda x: (x[1], total_record[x[0]][0], -total_record[x[0]][1]), reverse=True))
