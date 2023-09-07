import json
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List

import pandas as pd
import streamlit as st

from league import LeagueMetadata, YahooLeague


def print_obj_map(
    title: str,
    obj_map: Dict[str, Any],
    comparator_fn: Callable[[Any], Any] = None,
    value_fn: Callable[[Any], List[Any]] = None,
    value_columns: List[str] = None,
):
    items = obj_map.items()
    if comparator_fn:
        items = sorted(items, key=comparator_fn, reverse=True)

    d = {team: value_fn(value) if value_fn else value for team, value in items}
    df = pd.DataFrame.from_dict(d, orient="index", columns=value_columns)

    st.write(f"##### {title}")
    st.write(df)


def main():
    with NamedTemporaryFile(suffix=".json") as auth_file:
        yahoo_auth = st.secrets["YAHOO_AUTH"].to_dict()
        auth_file.write(bytes(json.dumps(yahoo_auth).encode("utf-8")))
        auth_file.seek(0)  # reset for read

        league_type = st.secrets["LEAGUE_TYPE"]
        league_id = st.secrets["LEAGUE_ID"]
        metadata = LeagueMetadata(league_type=league_type, league_id=league_id)

        yl = YahooLeague(auth_file.name, metadata)

    st.markdown("# Fantasy Basketball Weekly Scoring")

    st.markdown("#### Week")
    default_week = len(yl.week_opts) - 1
    week = st.selectbox("Week", yl.week_opts, index=default_week, label_visibility="collapsed")

    teams, win_record, total_record = yl.get_results_for_week(week)

    identifier = "Winner" if yl.week_opts.index(week) != len(yl.week_opts) - 1 else "Leader"
    win_comparator = lambda x: (x[1], total_record[x[0]][0], -total_record[x[0]][1])
    winner = max(win_record.items(), key=win_comparator)[0]
    st.markdown(f"#### :rainbow[{identifier}: {winner}]")

    # st.markdown(f"#### Week {week}")
    print_obj_map(
        title="Wins",
        obj_map=win_record,
        comparator_fn=win_comparator,
        value_fn=lambda x: [x],
        value_columns=["Wins"],
    )
    print_obj_map(
        title="Total",
        obj_map=total_record,
        comparator_fn=lambda x: (x[1][0], -x[1][1]),
        value_columns=["Wins", "Losses", "Ties"],
    )
    print_obj_map(
        title="Stats",
        obj_map=teams,
        value_fn=lambda x: x.values(),
        value_columns=yl.STAT_ID_MAP.values(),
    )

    st.markdown("#### Appendix")
    st.markdown(f"League: [{yl.league_name}]({yl.league_url})")


if __name__ == "__main__":
    main()
