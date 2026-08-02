"""
Core algorithm for the 21-card trick.

Pure Python, no Django imports — this module has to be importable and
testable on its own (see tests/test_logic.py), independent of any
request/session machinery. Views only orchestrate calls into this module;
they never compute card positions themselves.

Ported from the verified Java prototype (Trick1.java). See LEARNING.md for
why this arrangement always surfaces the chosen card at CHOSEN_CARD_INDEX
after ROUNDS passes.
"""

from dataclasses import dataclass
from random import Random
from typing import Optional

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("♠", "♣", "♥", "♦")  # Spades, Clubs, Hearts, Diamonds
RED_SUITS = frozenset({"♥", "♦"})

CARDS_IN_PLAY = 21
COLUMNS = 3
ROUNDS = 3
# Guaranteed landing spot after ROUNDS passes -- the middle card of the
# 21-card pile. Not a magic number: CARDS_IN_PLAY // 2, kept as a named
# constant because "10" alone would read as arbitrary everywhere else it's used.
CHOSEN_CARD_INDEX = CARDS_IN_PLAY // 2


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    def to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(rank=data["rank"], suit=data["suit"])


def build_deck() -> list[Card]:
    """Full 52-card deck in fixed suit/rank order (unshuffled)."""
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def start_pile(rng: Optional[Random] = None) -> list[Card]:
    """Shuffle a full deck and take the first CARDS_IN_PLAY cards.

    Accepts an optional Random instance so tests can seed the shuffle
    instead of depending on the global random module.
    """
    rng = rng or Random()
    deck = build_deck()
    rng.shuffle(deck)
    return deck[:CARDS_IN_PLAY]


def deal_columns(pile: list[Card]) -> list[list[Card]]:
    """Deal a 21-card pile into 3 columns of 7, interleaved by position.

    Matches Trick1.java's board[r][c] = pile[r*COLUMNS + c]: column c
    contains every card whose pile index is congruent to c (mod COLUMNS).
    This is the standard "deal left-right-left across three piles"
    motion, not a plain 3-way split of the list.
    """
    if len(pile) != CARDS_IN_PLAY:
        raise ValueError(f"pile must contain exactly {CARDS_IN_PLAY} cards, got {len(pile)}")
    return [pile[c::COLUMNS] for c in range(COLUMNS)]


def reassemble(columns: list[list[Card]], chosen_column: int) -> list[Card]:
    """Recombine 3 columns into one pile with the chosen column in the middle third.

    Which of the two non-chosen columns goes first is irrelevant to
    correctness -- only the chosen column's position (the middle third)
    determines where the target card ends up next round. See LEARNING.md.
    """
    if chosen_column not in range(COLUMNS):
        raise ValueError(f"chosen_column must be 0..{COLUMNS - 1}, got {chosen_column}")
    others = [c for c in range(COLUMNS) if c != chosen_column]
    return columns[others[0]] + columns[chosen_column] + columns[others[1]]


def play_round(pile: list[Card], chosen_column: int) -> list[Card]:
    """Deal + reassemble in one step: the full effect of one round."""
    return reassemble(deal_columns(pile), chosen_column)


def revealed_card(pile: list[Card]) -> Card:
    """The card the trick lands on. Only meaningful after ROUNDS rounds."""
    return pile[CHOSEN_CARD_INDEX]


def serialize_pile(pile: list[Card]) -> list[dict]:
    """Convert to a JSON-safe structure for storage in request.session."""
    return [card.to_dict() for card in pile]


def deserialize_pile(data: list[dict]) -> list[Card]:
    return [Card.from_dict(item) for item in data]
