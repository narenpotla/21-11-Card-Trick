"""
Views: HTTP + session orchestration only. No card-position math lives
here -- every computation is delegated to cardtrick.logic so the algorithm
stays testable independent of Django (see tests/test_logic.py).

Flow (POST/Redirect/GET):
  GET  /            -> index: renders whatever state the session says
                        (landing page, current round's board, or a
                        one-time reveal) and never mutates anything.
  POST /start/       -> start_game: creates a fresh pile, stores it in the
                        session, redirects to /.
  POST /choose/      -> choose_column: advances one round, redirects to /.
  POST /reset/       -> reset_game: abandons the in-progress game, redirects to /.

Redirecting after every POST (rather than rendering directly) means a
page refresh always re-GETs current state instead of resubmitting a
form -- that's what stops "hitting back and resubmitting" from
corrupting the game.
"""

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import logic

SESSION_PILE_KEY = "trick_pile"
SESSION_ROUND_KEY = "trick_round"
SESSION_RESULT_KEY = "trick_result"
SESSION_ROUND_TOKEN_KEY = "trick_round_token"

# One per round -- presentation-only, shown in the board's right-hand
# panel. Indexed by round_number (0, 1, 2), so it changes each round.
FUN_FACTS = [
    "A standard 52-card deck can be shuffled into 8×10⁶⁷ different "
    "orders — more than the number of atoms on Earth.",
    "This routine is called the 21-Card Trick and has been performed by "
    "magicians since at least the 1700s.",
    "Three rounds isn't arbitrary: 3 × 3 × 3 = 27, just enough "
    "combinations to pin down 1 card out of 21.",
]


def index(request: HttpRequest) -> HttpResponse:
    # One-time flash data: a finished game leaves its result here so the
    # reveal survives the choose_column -> redirect -> index round trip,
    # then gets popped so refreshing the reveal page doesn't re-show it
    # forever.
    result = request.session.pop(SESSION_RESULT_KEY, None)
    if result is not None:
        return render(request, "cardtrick/reveal.html", {"card": logic.Card.from_dict(result)})

    pile_data = request.session.get(SESSION_PILE_KEY)
    round_number = request.session.get(SESSION_ROUND_KEY)
    if pile_data is not None and round_number is not None:
        pile = logic.deserialize_pile(pile_data)
        columns = logic.deal_columns(pile)
        return render(
            request,
            "cardtrick/board.html",
            {
                "columns": columns,
                "round_display": round_number + 1,
                "total_rounds": logic.ROUNDS,
                "round_token": request.session[SESSION_ROUND_TOKEN_KEY],
                # presentation-only: which dot in the round indicator is lit
                "round_dots": [i == round_number for i in range(logic.ROUNDS)],
                "fun_fact": FUN_FACTS[round_number % len(FUN_FACTS)],
            },
        )

    return render(request, "cardtrick/landing.html")


@require_POST
def start_game(request: HttpRequest) -> HttpResponse:
    pile = logic.start_pile()
    request.session[SESSION_PILE_KEY] = logic.serialize_pile(pile)
    request.session[SESSION_ROUND_KEY] = 0
    request.session[SESSION_ROUND_TOKEN_KEY] = 0
    return redirect("cardtrick:index")


@require_POST
def choose_column(request: HttpRequest) -> HttpResponse:
    pile_data = request.session.get(SESSION_PILE_KEY)
    round_number = request.session.get(SESSION_ROUND_KEY)
    if pile_data is None or round_number is None:
        # No game in the session -- e.g. it was reset in another tab, or
        # expired. Nothing to apply the choice to; just go back to a
        # clean landing page instead of raising.
        messages.error(request, "That game session has ended. Start a new one.")
        return redirect("cardtrick:index")

    # A stale form (resubmitted via browser back-button after the game
    # already moved on) carries the round number it was rendered for.
    # If it no longer matches the session's current round, drop it
    # silently -- the user is looking at an out-of-date page, not making
    # a new choice.
    submitted_token = request.POST.get("round_token")
    current_token = str(request.session.get(SESSION_ROUND_TOKEN_KEY))
    if submitted_token != current_token:
        return redirect("cardtrick:index")

    raw_column = request.POST.get("column")
    if raw_column not in {"0", "1", "2"}:
        messages.error(request, "Pick one of the three columns.")
        return redirect("cardtrick:index")
    chosen_column = int(raw_column)

    pile = logic.deserialize_pile(pile_data)
    new_pile = logic.play_round(pile, chosen_column)
    round_number += 1

    if round_number >= logic.ROUNDS:
        card = logic.revealed_card(new_pile)
        del request.session[SESSION_PILE_KEY]
        del request.session[SESSION_ROUND_KEY]
        del request.session[SESSION_ROUND_TOKEN_KEY]
        request.session[SESSION_RESULT_KEY] = card.to_dict()
    else:
        request.session[SESSION_PILE_KEY] = logic.serialize_pile(new_pile)
        request.session[SESSION_ROUND_KEY] = round_number
        request.session[SESSION_ROUND_TOKEN_KEY] = round_number

    return redirect("cardtrick:index")


@require_POST
def reset_game(request: HttpRequest) -> HttpResponse:
    for key in (SESSION_PILE_KEY, SESSION_ROUND_KEY, SESSION_RESULT_KEY, SESSION_ROUND_TOKEN_KEY):
        request.session.pop(key, None)
    return redirect("cardtrick:index")


def learn_the_trick(request: HttpRequest) -> HttpResponse:
    """Static walkthrough of how to perform the trick with a real deck.
    No session/game state involved -- reachable any time, from anywhere."""
    return render(request, "cardtrick/learn.html")


def why_it_works(request: HttpRequest) -> HttpResponse:
    """Static explanation of the trick's logic. No session/game state."""
    return render(request, "cardtrick/why.html")
