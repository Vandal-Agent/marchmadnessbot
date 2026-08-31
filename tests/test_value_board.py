from __future__ import annotations

import unittest
from types import SimpleNamespace

from football_board import rank_value_board


def make_value(
    matchup: str,
    net_edge: float,
    sportsbook_samples: int = 2,
):
    return SimpleNamespace(
        sport="ncaaf",
        matchup=matchup,
        net_edge=net_edge,
        sportsbook_samples=sportsbook_samples,
        fair_probability=0.50,
    )


class ValueBoardTests(unittest.TestCase):
    def test_returns_five_distinct_games_ranked_by_net_edge(self):
        values = [
            make_value("Game A", 0.10),
            make_value("Game A", 0.09),
            make_value("Game B", 0.08),
            make_value("Game C", 0.07),
            make_value("Game D", 0.06),
            make_value("Game E", 0.05),
            make_value("Game F", 0.04),
            make_value("One-book Game", 0.20, sportsbook_samples=1),
        ]

        board = rank_value_board(values)

        self.assertEqual(
            [value.matchup for value in board],
            ["Game A", "Game B", "Game C", "Game D", "Game E"],
        )


if __name__ == "__main__":
    unittest.main()
