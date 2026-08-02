# LEARNING.md — 21-Card Trick (Django)

Study guide for this project. Read this after you've played the app once
and skimmed the code — the explanations below assume you've seen
`cardtrick/logic.py`, `cardtrick/views.py`, and the templates at least once.

---

## 1. The algorithm — why it works

### The trick, restated precisely

- Shuffle a 52-card deck. Take the first 21 cards. A spectator picks one
  mentally and never says which.
- Deal the 21 cards into 3 piles of 7, one card at a time, left-middle-right-left-middle-right...
  (this is the "interleaved" deal — card index `i` goes to pile `i % 3`).
- Ask which pile holds their card. Pick that pile up and place it **in
  the middle** of the other two (order of the other two doesn't matter).
- Repeat the deal-ask-restack step 2 more times (3 rounds total).
- The spectator's card is now always at position 11 (index 10, 0-based)
  of the 21-card pile — dead center.

### Why the middle placement is the whole trick

Think of it as narrowing down *where the card can be*, not tracking the
specific card.

- Before round 1: the card could be anywhere among 21 positions.
- After round 1: the spectator told you which pile (7 cards) it's in.
  When you restack with that pile in the **middle third**, you've
  guaranteed the card is now somewhere in positions 8–14 (1-indexed) —
  the middle 7 of the new 21.
- After round 2: same move, on the same logic, applied *again* — but
  this time it's applied to a pile where the card is already confined to
  the middle 7. Restacking with the (new) chosen pile in the middle again
  narrows the possible range to the middle 7 of *that* middle 7 — which,
  arithmetically, is centered on the same absolute position as before:
  the middle third of the middle third is still the middle third of the
  whole 21.
- After round 3: the "possible range" has been intersected with "middle
  third" three times. The only position that survives being in the
  middle third on every single round, no matter which pile was chosen
  each time, is the exact center: index 10 of 21 (11th card, 1-indexed).

The key insight for a whiteboard: **you never need to know which
specific card it is to do this.** You only need to know "it's in this
pile," and the middle-placement rule guarantees whichever pile that is,
the card in it lands closer to center after every round. Do it 3 times
with 3 piles of 7 (3³ = 27 ≥ 21, and specifically 7 = ⌈21/3⌉), and the
range collapses to exactly 1 card, centered.

Why 3 piles of 7 and not some other split? With `p` piles of `p` cards
each (`p² ` total, here `p=3` won't square to 21... more precisely: this
trick generalizes to `n` piles dealt `n` times over `n²` cards, landing
on the center card at index `⌊n²/2⌋`. Here `n=3`, `n²=9`... but we used
21, not 9 — the reconciliation is that this classic variant fixes `n=3`
piles and repeats 3 times regardless of pile size, and pile size 7 is
chosen specifically because `3 × 7 = 21` and 21 divides cleanly into
thirds at every round (7 stays 7 after redealing 21 cards into 3 piles
again). The number of *rounds* needed to guarantee convergence to one
card is `⌈log₃(21)⌉ = 3` (since each round divides the "possible
positions" by 3). That's the real mathematical reason: 3 rounds because
3ⁿ ≥ 21 first becomes true at n = 3 (3³ = 27 ≥ 21).

### Why the outer-pile order doesn't matter

`cardtrick/logic.py`'s `reassemble()` always puts the chosen pile in the
middle but doesn't care which of the other two goes left vs. right. That's
correct: convergence only depends on the chosen pile occupying the
*middle third* each round. Try both orderings on paper — the final index
is identical either way, only the identity of the *other* cards around it
shuffles. `Trick1.java` and this Django port pick opposite conventions for
outer-pile order and both are correct.

---

## 2. Django concepts used, and why

### Sessions (`django.contrib.sessions`)

A session is server-side storage keyed by an opaque ID that Django puts
in a cookie on the visitor's browser. The browser only ever holds the
ID; the actual data (here: the 21-card pile and round number) lives in
the `django_session` database table.

**Why sessions and not something else here:** the game has to survive
*across 3 separate HTTP requests* (one per round) for one visitor, with
no login system. Sessions are exactly the built-in tool for "remember
something about this specific browser between requests, without
authentication." The alternative (see architecture section) would be
passing the pile through hidden form fields on every request — that
works but leaks the entire card arrangement into the page's HTML source,
which a spectator could trivially view-source and see the trick spoiled.
Session data never reaches the client.

### URL routing (`urls.py`, `path()`, `include()`, `app_name`)

`config/urls.py` is the project-level router; it delegates anything
under `/` to `cardtrick/urls.py` via `include()`. The app's own
`urls.py` defines 4 routes (`index`, `start_game`, `choose_column`,
`reset_game`) each named (`app_name = "cardtrick"` + `name=...`) so
templates and views refer to them by name (`{% url 'cardtrick:index' %}`)
instead of hardcoded paths — if a URL's path string ever changes, nothing
else in the codebase needs to.

### Template context and inheritance

Views pass a `dict` of context variables into `render()`; templates
receive them as top-level names (`{{ card.rank }}`, `{% for column in
columns %}`). `base.html` defines the page shell with `{% block content
%}`; `landing.html`, `board.html`, `reveal.html` each `{% extends
"cardtrick/base.html" %}` and fill in just that block. This avoids
repeating the `<head>`, static-file links, and messages banner in three
places.

### Middleware

Middleware is code that runs on *every* request/response, wrapped around
the view. This project relies on three from the default stack:
`SessionMiddleware` (attaches `request.session`, reading/writing the
session cookie), `CsrfViewMiddleware` (see next section), and
`MessageMiddleware` (backs `django.contrib.messages`, used here for the
"pick a valid pile" / "session ended" error banners — one-request-only
flash messages, conceptually similar to how the reveal card is flashed
through the session).

### CSRF protection

Every POST form here (`start_game`, `choose_column`, `reset_game`)
includes `{% csrf_token %}`, which renders a hidden input containing a
per-session secret token. `CsrfViewMiddleware` rejects any POST that
doesn't include a matching token. Without this, a malicious page on
another site could embed a hidden form that auto-submits to
`/reset/` (or worse, `/choose/`) using the victim's browser session —
CSRF tokens prove the request actually originated from a page this
Django app served, not a forged cross-site request. `test_views.py`'s
`test_post_without_csrf_token_is_rejected` asserts the middleware
actually enforces this.

### Static file handling

`STATIC_URL = 'static/'` plus `STATICFILES_DIRS` tells Django where to
find `style.css` / `interactions.js` in development (`runserver` serves
them directly when `DEBUG=True`); in production, `collectstatic` gathers
everything into one directory that a real web server (nginx, WhiteNoise,
etc.) serves instead — Django itself does not serve static files
efficiently at scale, so this split exists on purpose.

### Settings management (`config/settings/base.py`, `dev.py`, `prod.py`)

One settings module can't safely serve both environments: dev wants
`DEBUG=True` and a working fallback `SECRET_KEY` so `runserver` works
with zero setup; production must have `DEBUG=False` (leaking stack
traces publicly is a real vulnerability) and *must* fail to start rather
than silently run with an insecure default key. Splitting into
`base.py` (shared) + `dev.py` / `prod.py` (environment-specific
overrides), with secrets read from environment variables
(`python-dotenv` + `os.environ`) rather than committed to source, is the
standard way to satisfy both needs from one codebase. `.env` is
git-ignored; `.env.example` documents what variables are expected
without containing real secrets.

---

## 3. Frontend concepts used

### CSS custom properties (variables) for staggered animation

`--i` (card's position within its pile) and `--col-delay` (per-pile
offset) are set inline via Django template `style="--i:{{
forloop.counter0 }}"`, then read inside a single `@keyframes` /
`animation-delay: calc(...)` rule in `style.css`. This produces the
"cards deal in one at a time" effect without any JavaScript — the
server-rendered HTML carries just enough data (`--i`) for pure CSS to
compute each card's individual delay.

### `@keyframes` and `transform`/`opacity` transitions

`deal-in` (cards sliding/rotating into place) and `reveal-pop` (the
final card scaling up with a bounce, via `cubic-bezier`) are both
GPU-friendly properties (`transform`, `opacity`) rather than animating
`width`/`top`/`left`, which would force expensive layout recalculation
on every frame.

### `prefers-reduced-motion`

A media query that disables the deal/reveal animations for users who've
told their OS they get motion sickness or distraction from animation —
an accessibility consideration, not a nice-to-have.

### Progressive enhancement via `interactions.js`

The game is **fully playable with JavaScript disabled** — the pile
buttons are real `<button type="submit">` elements inside real
`<form>`s that POST and get a full-page response. `interactions.js`
only adds: confetti on reveal, and making the whole pile div clickable
(not just the small button) by forwarding the click to the real submit
button. If the script fails to load, nothing about game correctness
breaks — this is the practical meaning of "JS handles polish, not
logic," applied all the way down to fallback behavior.

### Mobile-first responsive CSS

Base styles target small screens; a single `@media (min-width: 480px)`
block *adds* a larger card size for bigger viewports, rather than
starting from a desktop layout and cramming it down with a `max-width`
query. `flex-wrap: wrap` on `.board` lets the 3 piles reflow instead of
overflowing on narrow phones.

---

## 4. Architecture decisions — how to defend them in an interview

**Why is the algorithm in `logic.py`, not `views.py`?**
Because a view function is inherently tied to HTTP (it takes a
`request`, returns a `response`). Testing the *algorithm* shouldn't
require spinning up Django's test client, a session, or a database. By
making `logic.py` import nothing from Django, `test_logic.py` runs as
plain `unittest` — faster, and it proves the math is correct
independent of how (or whether) it's ever wired to the web. This is the
"hexagonal architecture" / "ports and adapters" idea in miniature: the
core domain logic doesn't know its caller is a web framework.

**Why session state, not passing state through the request (hidden form
fields), and not client-side JS state?**
Three real options existed:
1. *Client-side JS state* (what the original `CT3.html` prototype did):
   fast, zero server round-trips, but the entire 21-card arrangement
   sits in browser memory/JS — inspectable via devtools, and there's
   nothing "server" about it, which defeats the assignment's goal of
   demonstrating backend state management.
2. *Pass state through the request* (hidden `<input>` fields carrying
   the current pile, resubmitted every round): stateless on the server
   (arguably more "RESTful"), but it means the full card arrangement is
   sitting in the page's HTML source on every round — trivially visible
   via view-source, which spoils the trick for anyone curious, and it
   bloats every form with 21 hidden inputs.
3. *Django sessions* (chosen): the pile lives server-side, keyed by an
   opaque session ID cookie. The client only ever sees the current
   round's *dealt* cards (which it needs to display) — never anything
   that would let it compute future rounds. This is also the option
   that actually demonstrates "server owns the state" for a resume
   project, which was the explicit goal.

**Why Post/Redirect/Get (every POST view ends in `redirect()`, never
`render()`)?**
If `choose_column` rendered the next round's HTML directly as the POST
response, refreshing the browser after a choice would prompt "resubmit
this form?" — and confirming it would silently replay the same column
choice against whatever the *current* session state is, potentially
skipping a round or double-advancing. Redirecting to a GET-only `index`
view means refreshing always just re-reads current session state, which
is idempotent and safe to repeat.

**Why the `round_token` hidden field?**
Belt-and-suspenders on top of PRG: it guards against the browser *back*
button specifically — going back to a stale rendered form (e.g., round
1's page after you're already on round 3) and submitting it. The token
mirrors the round number the form was rendered for; if it doesn't match
the session's *current* round when the POST arrives, the view treats it
as a stale, ignorable submission instead of applying it. Concretely
tested in `test_views.py::test_stale_round_token_is_ignored`.

**Why function-based views instead of class-based views or DRF?**
Four small views, no reusable CRUD pattern, no API consumers — a
class-based `View` subclass or DRF `APIView` would add machinery
(dispatch-by-HTTP-method, serializers) this project has no use for.
Function-based views keep the request-in, response-out logic legible in
one place per view, which matches the project's actual complexity.

**Why `Card` as a frozen dataclass instead of a dict everywhere?**
`Card(rank, suit)` gives equality-by-value for free (`Card("K", "♥") ==
Card("K", "♥")` is `True`), which the test suite leans on directly
(`_find_column` in `test_logic.py` uses `in` on a list of `Card`s).
`frozen=True` also makes cards hashable, so they could go in a `set`
(used in a couple of tests to check uniqueness) — a plain `dict` can't.
The `to_dict()` / `from_dict()` pair is the explicit, narrow boundary
where a `Card` becomes JSON-safe for session storage; nothing outside
that boundary needs to know or care about the conversion.

---

## 5. Interview questions to test yourself against this document

1. Walk me through why the chosen card always ends up at index 10 after
   exactly 3 rounds. Why not 2 rounds, or 4?
2. Does it matter which of the two non-chosen piles goes on the left vs.
   right when reassembling? Why or why not?
3. Why does `logic.py` import nothing from Django? What would break (or
   get harder) if the algorithm functions took `request` as an argument?
4. What's actually stored in the session between rounds, and where does
   that data physically live?
5. Walk through, step by step, what happens on the server for one full
   game: what does session state look like after `start_game`, after
   each `choose_column`, and after the reveal?
6. Why redirect after every POST instead of rendering the next page
   directly? What specific bug does this prevent?
7. What does the `round_token` protect against that Post/Redirect/Get
   alone doesn't?
8. Why is CSRF protection necessary here specifically — what's the worst
   case if `{% csrf_token %}` were removed from `choose_column`'s form?
9. Why are `dev.py` and `prod.py` separate files instead of one
   `settings.py` with `if DEBUG:` branches?
10. If you were asked to add a "high score" or "games played" counter
    that needs to persist across browser sessions (not just one
    session), what would you add to this architecture, and why would
    that require a database model when the trick state itself doesn't?
