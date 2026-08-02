"""
Unit tests for cardtrick.logic — deliberately unittest.TestCase, not
django.test.TestCase, to prove the algorithm has zero Django dependency.
`python manage.py test` still discovers and runs these normally.
"""

import unittest
from random import Random

from cardtrick.logic import (
    CARDS_IN_PLAY,
    CHOSEN_CARD_INDEX,
    COLUMNS,
    ROUNDS,
    Card,
    build_deck,
    deal_columns,
    deserialize_pile,
    play_round,
    reassemble,
    revealed_card,
    serialize_pile,
    start_pile,
)


def _find_column(columns: list[list[Card]], target: Card) -> int:
    """Test helper: which column currently holds `target`."""
    for index, column in enumerate(columns):
        if target in column:
            return index
    raise AssertionError(f"{target} not found in any column")


def _play_full_trick(pile: list[Card], target: Card) -> Card:
    """Simulate a player who always answers correctly, for ROUNDS rounds."""
    for _ in range(ROUNDS):
        columns = deal_columns(pile)
        chosen_column = _find_column(columns, target)
        pile = reassemble(columns, chosen_column)
    return revealed_card(pile)


class BuildDeckTests(unittest.TestCase):
    def test_deck_has_52_unique_cards(self):
        deck = build_deck()
        self.assertEqual(len(deck), 52)
        self.assertEqual(len(set(deck)), 52)


class StartPileTests(unittest.TestCase):
    def test_pile_has_21_unique_cards(self):
        pile = start_pile(rng=Random(42))
        self.assertEqual(len(pile), CARDS_IN_PLAY)
        self.assertEqual(len(set(pile)), CARDS_IN_PLAY)

    def test_pile_is_subset_of_full_deck(self):
        deck = set(build_deck())
        pile = start_pile(rng=Random(1))
        self.assertTrue(set(pile).issubset(deck))

    def test_repeated_runs_produce_different_shuffles(self):
        # Not a proof of randomness, just a sanity check that shuffling is
        # actually happening rather than always returning the same slice.
        pile_a = start_pile()
        pile_b = start_pile()
        self.assertNotEqual(pile_a, pile_b)


class DealColumnsTests(unittest.TestCase):
    def test_deals_three_columns_of_seven(self):
        pile = start_pile(rng=Random(7))
        columns = deal_columns(pile)
        self.assertEqual(len(columns), COLUMNS)
        for column in columns:
            self.assertEqual(len(column), CARDS_IN_PLAY // COLUMNS)

    def test_columns_are_interleaved_not_split(self):
        pile = [Card(str(i), "♠") for i in range(CARDS_IN_PLAY)]
        columns = deal_columns(pile)
        # card 0 -> column 0, card 1 -> column 1, card 2 -> column 2, card 3 -> column 0 ...
        self.assertEqual(columns[0][0], pile[0])
        self.assertEqual(columns[1][0], pile[1])
        self.assertEqual(columns[2][0], pile[2])
        self.assertEqual(columns[0][1], pile[3])

    def test_wrong_length_pile_raises(self):
        with self.assertRaises(ValueError):
            deal_columns([Card("A", "♠")] * 20)
        with self.assertRaises(ValueError):
            deal_columns([Card("A", "♠")] * 22)


class ReassembleTests(unittest.TestCase):
    def test_chosen_column_lands_in_middle_third(self):
        pile = [Card(str(i), "♠") for i in range(CARDS_IN_PLAY)]
        columns = deal_columns(pile)
        for chosen in range(COLUMNS):
            new_pile = reassemble(columns, chosen)
            middle_third = new_pile[7:14]
            self.assertEqual(set(middle_third), set(columns[chosen]))

    def test_invalid_column_raises(self):
        pile = start_pile(rng=Random(3))
        columns = deal_columns(pile)
        with self.assertRaises(ValueError):
            reassemble(columns, 3)
        with self.assertRaises(ValueError):
            reassemble(columns, -1)


class FullTrickTests(unittest.TestCase):
    def test_every_starting_position_is_correctly_revealed(self):
        """Edge case: a card starting at each of the 21 positions must
        still be the one revealed at the end, regardless of where it began."""
        pile = start_pile(rng=Random(99))
        for index in range(CARDS_IN_PLAY):
            target = pile[index]
            result = _play_full_trick(list(pile), target)
            self.assertEqual(result, target)

    def test_random_shuffles_1000_iterations(self):
        """The trick must hold for arbitrary shuffles, not just one fixed deck."""
        rng = Random(2024)
        for _ in range(1000):
            pile = start_pile(rng=rng)
            target_index = rng.randrange(CARDS_IN_PLAY)
            target = pile[target_index]
            result = _play_full_trick(list(pile), target)
            self.assertEqual(result, target)

    def test_play_round_matches_deal_then_reassemble(self):
        pile = start_pile(rng=Random(5))
        columns = deal_columns(pile)
        expected = reassemble(columns, 1)
        self.assertEqual(play_round(pile, 1), expected)


class SerializationTests(unittest.TestCase):
    def test_round_trip_preserves_pile(self):
        pile = start_pile(rng=Random(11))
        data = serialize_pile(pile)
        # JSON-safe: only str/dict/list, matching what Django's session
        # JSON serializer accepts.
        self.assertTrue(all(isinstance(d, dict) for d in data))
        self.assertEqual(deserialize_pile(data), pile)


if __name__ == "__main__":
    unittest.main()
