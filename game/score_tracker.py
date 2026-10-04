"""ScoreTracker — tallies face wins per player and determines the overall result."""

from typing import Optional

from game.enums import Player


class ScoreTracker:
    """Tracks how many faces each player has won.

    Responsible for recording wins, reporting scores, and determining
    the overall game result. Knows nothing about boards, turns, or UI.
    """

    def __init__(self) -> None:
        self._scores: dict[Player, int] = {Player.X: 0, Player.O: 0}

    def record_win(self, player: Player) -> None:
        """Increment the given player's score by 1."""
        self._scores[player] += 1

    def get_scores(self) -> dict[Player, int]:
        """Return a copy of the current scores."""
        return dict(self._scores)

    def get_winner(self) -> Optional[Player]:
        """Return the player with the higher score, or None if tied."""
        x_score = self._scores[Player.X]
        o_score = self._scores[Player.O]

        if x_score > o_score:
            return Player.X
        if o_score > x_score:
            return Player.O
        return None

    def get_result_text(self) -> str:
        """Return a human-readable result string."""
        x_score = self._scores[Player.X]
        o_score = self._scores[Player.O]
        winner = self.get_winner()

        if winner is not None:
            return f"Player {winner.symbol} wins {self._scores[winner]}-{self._scores[winner.next()]}!"
        return f"It's a tie! {x_score}-{o_score}"
