import itertools
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import yahoo_fantasy_api as yfa
from pydantic import BaseModel
from yahoo_oauth import OAuth2

# DISABLE LOGGING

oauth_logger = logging.getLogger("yahoo_oauth")
oauth_logger.disabled = True

# TYPES
Stats = Dict[str, float]  # Stat -> Value
TeamStats = Dict[str, Stats]  # Team -> Stat -> Value
TeamWins = Dict[str, int]  # Team -> Wins
TeamTotalRecord = Dict[str, Tuple[int, int, int]]  # Team -> [Wins, Losses, Ties]
Results = Tuple[TeamStats, TeamWins, TeamTotalRecord]
WeekResults = Dict[int, Results]  # Week -> Results


class LeagueMetadata(BaseModel):
    league_type: str
    league_id: str


class YahooLeague:
    league: yfa.League
    league_name: str
    league_url: str
    results_cache: WeekResults
    week_opts: List[int]

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

    def __init__(self, config_file: Optional[str], league_settings: LeagueMetadata):
        try:
            sc = self._get_auth(config_file)
        except Exception as e:
            raise Exception("Error authenticating with Yahoo API") from e

        try:
            self.league = self._get_league(sc, league_settings)
        except Exception as e:
            raise Exception("Error getting league info") from e

        # Default to week 1 for initial data
        response = self.league.matchups(1)["fantasy_content"]["league"]

        self.league_name = response[0]["name"]
        self.league_url = response[0]["url"]

        start_week = int(response[0]["start_week"])
        current_week = int(response[0]["current_week"])
        self.week_opts = range(start_week, current_week + 1)

        self.results_cache = dict()

    def _get_auth(self, config_file: Optional[str]) -> OAuth2:
        if config_file is None:
            consumer_key = os.getenv("consumer_key")
            consumer_secret = os.environ.get("consumer_secret")
            sc = OAuth2(consumer_key, consumer_secret)
            return sc
        else:
            sc = OAuth2(None, None, from_file=config_file)
            return sc

    def _get_league(self, sc: OAuth2, league_settings: LeagueMetadata) -> yfa.League:
        league_type = league_settings.league_type
        league_id = league_settings.league_id

        game_key = yfa.Game(sc, league_type).game_id()
        league_key = f"{game_key}.l.{league_id}"

        league = yfa.League(sc, league_key)
        return league

    def get_results_for_week(self, week: int) -> Results:
        if week in self.results_cache:
            return self.results_cache[week]

        response = self.league.matchups(week)["fantasy_content"]["league"]
        matchups = response[1]["scoreboard"]["0"]["matchups"]

        teams = self._get_team_stats_from_matchups(matchups)
        win_record, total_record = self._simulate_matchups(teams)

        self.results_cache[week] = (teams, win_record, total_record)
        return self.results_cache[week]

    def _get_team_stats_from_matchups(self, matchups: Dict[str, Any]) -> TeamStats:
        """
        Get dictionary of teams to their weekly stats
        """
        teams = dict()
        for team in self.league.teams().values():
            teams[team["name"]] = {stat: 0 for stat in self.STAT_ID_MAP.values()}

        for matchup in matchups.values():
            if not isinstance(matchup, dict):
                continue

            team_objs = matchup["matchup"]["0"]["teams"]
            for team_id in ["0", "1"]:
                team_name = team_objs[team_id]["team"][0][2]["name"]
                team_stats = team_objs[team_id]["team"][1]["team_stats"]["stats"]
                teams[team_name] = self._convert_team_stats(team_stats)
        return teams

    def _convert_team_stats(self, team_stats: Any) -> Stats:
        stats_map = {}
        for stats_obj in team_stats:
            key = stats_obj["stat"]["stat_id"]
            val = stats_obj["stat"]["value"]
            if key not in self.STAT_ID_MAP:
                continue
            stats_map[self.STAT_ID_MAP[key]] = float(val) if val else 0
        return stats_map

    def _simulate_matchups(self, teams: TeamStats) -> (TeamWins, TeamTotalRecord):
        """
        Simulate all matchups for the week. Return win record and total record for each team
        """
        win_record = {team: 0 for team in teams.keys()}  # team -> wins
        total_record = {team: [0, 0, 0] for team in teams.keys()}  # team -> [wins, losses, ties]

        all_pos_matchups = list(itertools.combinations(teams, 2))
        for t1_name, t2_name in all_pos_matchups:
            winner, t1_record, t2_record = self._simulate_matchup(t1_name, t2_name)

            if winner:
                win_record[winner][0] += 1

            total_record[t1_name] = [a + b for a, b in zip(t1_record, total_record[t1_name])]
            total_record[t2_name] = [a + b for a, b in zip(t2_record, total_record[t2_name])]

        return win_record, total_record

    def _simulate_matchup(
        self, teams: TeamStats, t1_name: str, t2_name: str
    ) -> (str, Tuple[int, int, int], Tuple[int, int, int]):
        t1_stats, t2_stats = teams[t1_name], teams[t2_name]
        t1_record, t2_record = [0, 0, 0], [0, 0, 0]  # [wins, losses, ties]
        for stat in t1_stats:
            team1_res, team2_res = self._process_stat(stat, t1_stats, t2_stats)
            t1_record[team1_res] += 1
            t2_record[team2_res] += 1

        winner = None
        if t1_record[0] > t2_record[0]:
            winner = t1_name
        elif t1_record[0] < t2_record[0]:
            winner = t2_name

        return winner, t1_record, t2_record

    def _process_stat(self, stat: str, t1_stats: Stats, t2_stats: Stats) -> (int, int):
        """
        Returns index of record to increment for each team
        """
        if t1_stats[stat] > t2_stats[stat]:
            if stat == "TO":
                return 1, 0  # team 2 wins
            else:
                return 0, 1  # team 1 wins
        elif t1_stats[stat] < t2_stats[stat]:
            if stat == "TO":
                return 0, 1  # team 1 wins
            else:
                return 1, 0  # team 2 wins
        else:
            return 2, 2  # tie
