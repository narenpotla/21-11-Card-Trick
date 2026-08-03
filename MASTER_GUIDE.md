# The 21-Card Trick — Master Guide to Software Development, Django, and Web Fundamentals

This is a from-scratch teaching document. It assumes you can already write basic
code (variables, loops, functions, if/else) in *some* language, but nothing
about web development, Django, or this specific codebase. By the end, every
file in this repository should make sense to you, and you should understand
the general concepts well enough to apply them to a different project.

**How to use this doc:** read it top to bottom once. Then keep it open next to
the code and jump to sections as you explore specific files. Every section
points at real files with real line references — nothing here is abstract
theory without a concrete example beside it.

---

## Table of Contents

1. [Software Development Principles](#1-software-development-principles)
2. [How the Web Works](#2-how-the-web-works)
3. [Python Concepts This Project Uses](#3-python-concepts-this-project-uses)
4. [Django Framework, Piece by Piece](#4-django-framework-piece-by-piece)
5. [This Project's Backend Architecture](#5-this-projects-backend-architecture)
6. [Frontend Fundamentals](#6-frontend-fundamentals)
7. [This Project's Frontend Architecture](#7-this-projects-frontend-architecture)
8. [Testing Philosophy](#8-testing-philosophy)
9. [DevOps: Environments, Deployment, CI](#9-devops-environments-deployment-ci)
10. [Trace a Single Request, Start to Finish](#10-trace-a-single-request-start-to-finish)
11. [Glossary](#11-glossary)
12. [Self-Check Questions](#12-self-check-questions)

---

## 1. Software Development Principles

These aren't Django-specific or even web-specific — they're how professional
software gets written, and every one of them shows up somewhere in this repo.

### Separation of concerns

**The idea:** each piece of code should have one job, and shouldn't need to
know about the internals of other pieces to do that job.

**Where you see it here:** [`cardtrick/logic.py`](cardtrick/logic.py) contains
the entire 21-card-trick algorithm — shuffling, dealing, reassembling — and it
has **zero imports from Django**. It doesn't know what a web request is, what
a session is, or what HTML looks like. Meanwhile
[`cardtrick/views.py`](cardtrick/views.py) knows about requests, sessions, and
HTTP, but contains **no card-position math** — it just calls functions from
`logic.py` and shuffles data between the session and the template.

Why this matters practically: `cardtrick/tests/test_logic.py` tests the
algorithm using plain `unittest`, with no Django test client, no HTTP, no
database. That's only possible because the algorithm doesn't depend on any of
those things. If the math and the web-handling were tangled together in one
big view function, you couldn't test "does the algorithm always land on card
11" without also spinning up a fake web request every time.

### DRY (Don't Repeat Yourself) — and its limits

**The idea:** if you write the same logic in two places, they *will* drift
apart when one gets updated and the other doesn't.

**Where you see it here:**
[`templates/cardtrick/_card.html`](templates/cardtrick/_card.html) is a
single template partial for rendering one playing card (rank, suit, corner
pips). It's used by [`board.html`](templates/cardtrick/board.html) (21 times,
once per card) and [`reveal.html`](templates/cardtrick/reveal.html) (once, for
the big reveal card). Without this partial, the HTML for a card's corner pips
would be duplicated in two templates — and the first time someone fixed a bug
in one copy and forgot the other, they'd diverge silently.

**The limit of DRY:** don't over-apply it. `cardtrick/logic.py` has a
`CHOSEN_CARD_INDEX = CARDS_IN_PLAY // 2` — this *could* be "simplified" to
just the literal number `10`, saving a line. It isn't, on purpose: the name
documents *why* that number is what it is. A named constant that's used once
is not a DRY violation; a magic number that requires the reader to do algebra
in their head to understand is a readability bug.

### Single Responsibility (functions and files should do one thing)

**Where you see it:** every function in `logic.py` does exactly one
transformation:

```python
def deal_columns(pile: list[Card]) -> list[list[Card]]:
    """Deal a 21-card pile into 3 columns of 7, interleaved by position."""
    ...

def reassemble(columns: list[list[Card]], chosen_column: int) -> list[Card]:
    """Recombine 3 columns into one pile with the chosen column in the middle third."""
    ...

def play_round(pile: list[Card], chosen_column: int) -> list[Card]:
    """Deal + reassemble in one step: the full effect of one round."""
    return reassemble(deal_columns(pile), chosen_column)
```

`play_round` doesn't duplicate the logic of the other two — it *composes*
them. This is a common pattern: small functions that do one thing, and larger
functions that just call the small ones in the right order.

### Fail loudly, not silently

**Where you see it:** [`config/settings/base.py`](config/settings/base.py)
reads the production secret key from an environment variable with **no
fallback**:

```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
```

and [`config/settings/prod.py`](config/settings/prod.py) then does:

```python
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY environment variable must be set in production."
    )
```

If someone deploys this without setting the environment variable, the app
**refuses to start** rather than silently running with an insecure default.
Compare this to `dev.py`, which *does* provide a fallback key — because in
dev, "just works with zero setup" is more valuable than the hardening you want
in prod. Same codebase, different failure philosophy, because the stakes are
different.

### Trust boundaries: validate at the edges, trust internally

**The idea:** you don't need to defensively re-check things that your own
code already guarantees. You *do* need to validate anything coming from
outside your program's control (user input, external APIs).

**Where you see it:** [`cardtrick/views.py`](cardtrick/views.py)'s
`choose_column` view validates the `column` POST field strictly:

```python
raw_column = request.POST.get("column")
if raw_column not in {"0", "1", "2"}:
    messages.error(request, "Pick one of the three columns.")
    return redirect("cardtrick:index")
chosen_column = int(raw_column)
```

That's a trust boundary — the value came from outside (a browser, which a
user can manipulate with dev tools). But once `chosen_column` is a validated
int, `logic.py`'s `reassemble()` doesn't re-validate it defensively against
every possible bad value in a dozen more places — it trusts the caller
already checked. (It *does* still raise `ValueError` for genuinely
out-of-range input, as a safety net for programmer error, not user input —
see `cardtrick/tests/test_logic.py::ReassembleTests::test_invalid_column_raises`.)

---

## 2. How the Web Works

Before Django makes sense, you need the request/response model underneath it.

### Client and server

Your browser (**the client**) and the computer running Django (**the
server**) are two separate programs that talk over the network using HTTP.
Every single thing you see in a browser started as the client sending a
**request** and the server sending back a **response**.

### An HTTP request has:

- A **method** — the most common are `GET` ("give me this page") and `POST`
  ("here's some data, do something with it"). This project uses both:
  loading the board is `GET`, submitting which pile your card is in is
  `POST`.
- A **path** — e.g. `/choose/`, `/learn/`. Django maps these to Python
  functions (see [§4.1](#41-urls--routing)).
- **Headers** — metadata like cookies, content type.
- Optionally, a **body** — form data, for `POST` requests.

### An HTTP response has:

- A **status code** — `200` means OK, `302` means "redirect elsewhere",
  `403` means "forbidden" (this project uses that for failed CSRF checks —
  see `cardtrick/tests/test_views.py::test_post_without_csrf_token_is_rejected`),
  `404` means "not found", `405` means "method not allowed" (this project
  returns that if you `GET` `/start/` instead of `POST` — see
  `@require_POST` in `views.py`).
- **Headers**.
- A **body** — usually HTML, sometimes nothing (redirects have an empty body
  and a `Location` header telling the browser where to go next).

### Cookies and sessions

HTTP is **stateless** — the server doesn't inherently remember who you are
between requests. A cookie is a small piece of data the server tells the
browser to store, and the browser automatically re-sends it on every future
request to that same site. Django uses a cookie holding a random session ID
to look up **server-side session data** (in this project's dev setup, a row
in a database table; see [§5.2](#52-why-sessions-not-hidden-form-fields-not-client-js)
for why sessions specifically, and [§9](#9-devops-environments-deployment-ci)
for how production stores it differently).

### GET vs. POST, and why it matters here

A `GET` request should be **safe** — reading it shouldn't change anything on
the server. A `POST` request is expected to **cause a change** (start a game,
submit a choice). This project's [`cardtrick/views.py`](cardtrick/views.py)
follows that rule strictly: `index` (the `GET` view) never mutates the
session, only reads it. Every session-mutating action (`start_game`,
`choose_column`, `reset_game`) is `POST`-only, enforced by the
`@require_POST` decorator. This isn't just a style preference — browsers,
proxies, and search-engine crawlers assume `GET` is safe to repeat and
prefetch. If loading the board page silently advanced the round, refreshing
the page would break the game.

---

## 3. Python Concepts This Project Uses

A quick reference for the language features you'll see in `cardtrick/logic.py`
and `cardtrick/views.py`, in case any are new to you.

### Type hints

```python
def deal_columns(pile: list[Card]) -> list[list[Card]]:
```

`pile: list[Card]` means "this parameter should be a list of `Card` objects."
`-> list[list[Card]]` means "this function returns a list of lists of
`Card`s." Python doesn't *enforce* these at runtime — they're documentation
for humans (and tools like IDEs/type checkers) about what's expected, without
needing a comment.

### `@dataclass`

```python
@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
```

Writing a class normally requires an `__init__` method that assigns each
argument to `self`. `@dataclass` generates that boilerplate for you.
`frozen=True` means once a `Card` is created, its `rank`/`suit` can't be
reassigned — this project relies on that: `Card` objects are compared and
put in `set()`s (`cardtrick/tests/test_logic.py::BuildDeckTests`), which
requires them to be immutable and hashable.

### `Optional[Random]` and dependency injection for testability

```python
def start_pile(rng: Optional[Random] = None) -> list[Card]:
    rng = rng or Random()
```

`start_pile` needs *some* randomness, but instead of hard-coding "use
Python's global random module," it accepts an *optional* `Random` object.
Tests pass in `Random(seed)` — a **deterministic**, seeded random generator —
so the same test always produces the same shuffle, making the test
repeatable. Production code just calls `start_pile()` with no argument and
gets real randomness. This pattern (accepting a "thing that provides
randomness/time/external state" as a parameter instead of reaching for a
global) is called **dependency injection**, and it's one of the main tricks
that makes code testable.

### List slicing tricks

```python
return [pile[c::COLUMNS] for c in range(COLUMNS)]
```

`pile[c::3]` means "start at index `c`, take every 3rd element." For `c=0`
that's indices `0, 3, 6, 9...`; for `c=1` that's `1, 4, 7, 10...`. This is
how the deck gets interleaved into 3 piles in one line instead of a manual
loop — see [§5.1](#51-the-algorithm-logicpy) for why this specific pattern
matches the real-world "deal one card to each pile in turn" motion.

### Class methods as alternate constructors

```python
@classmethod
def from_dict(cls, data: dict) -> "Card":
    return cls(rank=data["rank"], suit=data["suit"])
```

A regular method is called on an *instance* (`my_card.some_method()`). A
`@classmethod` is called on the *class itself* (`Card.from_dict(...)`) and is
commonly used as an alternate way to construct an object — here, rebuilding a
`Card` from the plain dictionary that Django's session storage serialized it
to (see `serialize_pile`/`deserialize_pile` at the bottom of `logic.py`).

---

## 4. Django Framework, Piece by Piece

Django follows the **MVT** pattern — Model, View, Template. (It's a variant
of the more famous MVC; Django's "View" is closer to what other frameworks
call a "Controller," which trips people up at first.)

- **Model** — normally your database schema (Django ORM classes). This
  project has **no custom models** — see [§5.2](#52-why-sessions-not-hidden-form-fields-not-client-js)
  for why the game state lives in the session instead of a database table.
- **View** — a Python function (or class) that takes a request and returns a
  response. This is where your logic lives.
- **Template** — an HTML file with placeholders (`{{ variable }}`) that
  Django fills in with data the view provides.

### 4.1 URLs / routing

[`cardtrick/urls.py`](cardtrick/urls.py):

```python
urlpatterns = [
    path("", views.index, name="index"),
    path("start/", views.start_game, name="start_game"),
    path("choose/", views.choose_column, name="choose_column"),
    path("reset/", views.reset_game, name="reset_game"),
    path("learn/", views.learn_the_trick, name="learn"),
    path("why/", views.why_it_works, name="why"),
]
```

This is a lookup table: URL path → Python function. When a request for
`/choose/` arrives, Django calls `views.choose_column(request)`. The `name=`
argument lets templates and Python code refer to a URL by name instead of
hardcoding the string — `{% url 'cardtrick:choose_column' %}` in a template,
or `reverse("cardtrick:choose_column")` in Python (used throughout
`cardtrick/tests/test_views.py`). If the path ever changes from `/choose/` to
something else, you only edit it in one place.

[`config/urls.py`](config/urls.py) is the *project-level* router — it
delegates everything under `/` to this app's `urls.py` via `include()`. This
matters once a project has multiple apps: each app owns its own URL prefix.

### 4.2 Views

A view is just a function: `request` in, `HttpResponse` out.

```python
def index(request: HttpRequest) -> HttpResponse:
    result = request.session.pop(SESSION_RESULT_KEY, None)
    if result is not None:
        return render(request, "cardtrick/reveal.html", {"card": logic.Card.from_dict(result)})
    ...
    return render(request, "cardtrick/landing.html")
```

`render(request, template_name, context_dict)` is a shortcut that finds the
named template, fills it in with the context dictionary, and wraps the
result in an `HttpResponse`. `redirect(...)` is the other common return —
it sends back a `302` status with a `Location` header instead of a page body,
telling the browser to make a *new* request elsewhere (see
[§2](#2-how-the-web-works) for why this project always redirects after a
`POST` — the **Post/Redirect/Get** pattern, explained fully in
[§5.3](#53-postredirectget-and-the-round_token-guard)).

### 4.3 Templates

[`templates/cardtrick/board.html`](templates/cardtrick/board.html) (trimmed):

```django
{% extends "cardtrick/base.html" %}
{% block content %}
<p class="instructions">Which pile is your card in?</p>
<div class="board">
  {% for column in columns %}
    <div class="column" data-column="{{ forloop.counter0 }}">
      {% for card in column %}
        {% include "cardtrick/_card.html" with card=card i=forloop.counter0 %}
      {% endfor %}
    </div>
  {% endfor %}
</div>
{% endblock %}
```

- `{% extends %}` — this template inherits a shared shell from
  [`base.html`](templates/cardtrick/base.html) (the page `<head>`, the wood
  rail/felt table chrome, the title). Every page-specific template only fills
  in the `{% block content %}` slot.
- `{% for %}` — loops over the `columns` list the view put in the context.
  `forloop.counter0` is Django's built-in 0-indexed loop counter.
- `{% include %}` — inserts another template (`_card.html`) inline, passing
  extra variables with `with`. This is the DRY mechanism from
  [§1](#1-software-development-principles).
- `{{ variable }}` — outputs a value, automatically **HTML-escaped** to
  prevent XSS (cross-site scripting) — if `card.rank` somehow contained
  `<script>`, Django renders it as harmless text, not executable HTML. This
  auto-escaping is a template-engine-level security default, not something
  this project had to opt into.

### 4.4 Settings, and why they're split into three files

```
config/settings/
├── base.py   # shared by every environment
├── dev.py    # imports base, adds dev-only fallbacks
└── prod.py   # imports base, adds prod-only hardening
```

`dev.py`:
```python
from .base import *
DEBUG = True
if not SECRET_KEY:
    SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-production"
```

`prod.py`:
```python
from .base import *
DEBUG = False
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY environment variable must be set in production.")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
# ...more hardening
```

`DEBUG = True` is *convenient* in development (detailed error pages showing
you exactly what broke) and a **serious security hole** in production
(those same detailed error pages can leak source code, settings, and stack
traces to anyone who triggers an error on your live site). One settings
file with an `if DEBUG:` branch scattered everywhere gets error-prone fast;
two files that both start from the same shared base and diverge only where
they need to is easier to audit — you can read `prod.py` top to bottom and
see *exactly* what's different about production.

### 4.5 Middleware

Middleware is code that wraps *every* request, in order, before it reaches
your view (and wraps the response again on the way back out).
[`config/settings/base.py`](config/settings/base.py):

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

Order matters — `SessionMiddleware` has to run before anything that reads
`request.session` (which is everything downstream of it, including your
views). `WhiteNoiseMiddleware` serves static files (CSS/JS) directly, before
the request even reaches Django's URL routing, for anything under
`/static/`. `CsrfViewMiddleware` is what actually enforces the CSRF check
described in [§4.6](#46-csrf-protection) — it runs on every `POST` and
rejects ones without a valid token, before your view function ever executes.

### 4.6 CSRF protection

CSRF (Cross-Site Request Forgery) — imagine a malicious website embeds a
hidden auto-submitting form pointed at `your-site.com/reset/`. If your
browser has an active session cookie for your-site.com, it'll send that
cookie automatically... unless the server also requires a secret token that
only pages *your site actually served* would know.

Every `POST` form in this project includes:
```django
{% csrf_token %}
```
which renders a hidden `<input>` with a per-session secret value.
`CsrfViewMiddleware` rejects any `POST` missing a matching token with a `403`
— proven directly by a test, not just assumed:

```python
def test_post_without_csrf_token_is_rejected(self):
    self.client.get(reverse("cardtrick:index"))
    response = self.client.post(reverse("cardtrick:start_game"), {})
    self.assertEqual(response.status_code, 403)
```

### 4.7 Static files

`STATIC_URL = "static/"` tells Django/templates what URL prefix to use for
CSS/JS (`{% static 'cardtrick/css/base.css' %}` → `/static/cardtrick/css/base.css`).
In development, Django serves these files directly. In production
([§9.2](#92-static-files-whitenoise)), a separate tool (WhiteNoise) takes
over, because Django's own dev-mode static serving isn't built for real
traffic.

### 4.8 The Django test client

`cardtrick/tests/test_views.py` uses `django.test.Client` to simulate a
browser without actually running one:

```python
self.client = Client(enforce_csrf_checks=True)
response = self.client.post(reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token})
self.assertRedirects(response, reverse("cardtrick:index"))
```

This sends a real request through Django's full URL routing → middleware →
view → template pipeline, in-process, without a network round-trip — fast
enough to run dozens of times per second, realistic enough to catch actual
bugs in the request-handling chain (see [§8](#8-testing-philosophy)).

---

## 5. This Project's Backend Architecture

### 5.1 The algorithm (`logic.py`)

The file has zero Django imports — see [§1](#1-software-development-principles)
for why that's the whole point. The core pipeline:

```python
def start_pile(rng=None) -> list[Card]:      # shuffle deck, take 21
def deal_columns(pile) -> list[list[Card]]:   # split into 3 piles of 7
def reassemble(columns, chosen_column) -> list[Card]:  # chosen pile → middle
def play_round(pile, chosen_column) -> list[Card]:     # deal + reassemble
def revealed_card(pile) -> Card:              # pile[10], after 3 rounds
```

For the *mathematical* reason this always lands on card 11, see
[`LEARNING.md`](LEARNING.md) §1 — that document goes deep on the math
specifically; this guide focuses on the *engineering*, not re-deriving the
proof.

### 5.2 Why sessions, not hidden form fields, not client JS

Three real options existed for "where does the 21-card pile live between
requests":

1. **Client-side JavaScript variable** — fast, but the entire card
   arrangement sits in the browser's memory, inspectable via dev tools. This
   was literally the *original prototype* (`CT3.html`, a single static HTML
   file with the whole trick in a `<script>` tag) — see git history / early
   conversation. It works, but nothing about it is "server-side," which
   defeats the point of a backend demo.
2. **Hidden form fields**, resubmitted every round — stateless on the
   server, but the entire pile sits in the page's HTML source. Anyone
   curious could View Source mid-game and read every card.
3. **Django sessions** (chosen) — the pile lives server-side, keyed by an
   opaque cookie. The client only ever sees the *current round's dealt
   cards* — nothing that lets it compute future rounds.

```python
request.session[SESSION_PILE_KEY] = logic.serialize_pile(pile)
request.session[SESSION_ROUND_KEY] = 0
```

`serialize_pile`/`deserialize_pile` (bottom of `logic.py`) convert between
`Card` objects and plain dicts, because session storage has to be
JSON-serializable — you can't stuff an arbitrary Python object into it.

### 5.3 Post/Redirect/Get, and the `round_token` guard

If a `POST` view rendered the next page directly (instead of redirecting),
refreshing the browser afterward would trigger a "resubmit this form?"
prompt — and confirming it would replay the same choice against whatever the
session's *current* state now is, potentially double-advancing the round.
Every mutating view in this project ends with `redirect("cardtrick:index")`
instead — so a refresh always just re-`GET`s current state, which is safe to
repeat.

That handles *refresh*. It doesn't fully handle the browser **back
button**: going back to a stale rendered page from round 1 and submitting
that old form, after you're already on round 3. For that,
[`views.py`](cardtrick/views.py) stamps each rendered board with the round
number it was generated for:

```python
"round_token": request.session[SESSION_ROUND_TOKEN_KEY],
```

and `choose_column` compares the submitted token against the session's
*current* round before applying anything:

```python
submitted_token = request.POST.get("round_token")
current_token = str(request.session.get(SESSION_ROUND_TOKEN_KEY))
if submitted_token != current_token:
    return redirect("cardtrick:index")
```

A stale submission is silently ignored rather than corrupting the round
counter — tested directly in
`test_views.py::test_stale_round_token_is_ignored`.

### 5.4 Why function-based views, not class-based / DRF

Four small views, no reusable CRUD pattern, no API consumers. A class-based
`View` subclass adds dispatch-by-HTTP-method machinery this project doesn't
need (`@require_POST` already does that in one line); Django REST Framework
adds serializers and content negotiation for an API that doesn't exist here.
Function-based views keep "request in, response out" legible in one place
per view — matched to the actual complexity of the project, not the
complexity of what it *could* theoretically grow into.

---

## 6. Frontend Fundamentals

### HTML: structure and semantics

HTML describes *what things are*, not how they look. `<button>` is a
button — it's keyboard-focusable and screen-reader-announced as a button for
free, which a `<div onclick="...">` styled to look like a button is not.
Every pile-choice control in this project is a real `<button type="submit">`
(see [`board.html`](templates/cardtrick/board.html)), specifically so the
game works with JavaScript disabled — a real HTML form submission, not a JS
click handler pretending to be one.

### CSS: the box model

Every HTML element is a box with `content`, `padding` (space inside the
border), `border`, and `margin` (space outside the border).
[`static/cardtrick/css/base.css`](static/cardtrick/css/base.css) sets:

```css
* {
  box-sizing: border-box;
}
```

By default, CSS `width`/`height` apply only to *content*, so `padding` and
`border` add extra size on top of what you specified. `border-box` makes
`width`/`height` include padding and border, so a `100px` wide button with
`10px` padding is still exactly `100px` wide — much easier to reason about,
which is why nearly every modern project sets this globally on line 1.

### CSS: Flexbox

Flexbox arranges children in a row or column, distributing space between
them. [`static/cardtrick/css/base.css`](static/cardtrick/css/base.css):

```css
.app {
  display: flex;
  flex-direction: column;
}
```

Makes `.app`'s children (header, main content) stack vertically, each
taking up only the height it needs, unless told otherwise with `flex: 1 1
auto` (grow to fill remaining space) — see
[`board.css`](static/cardtrick/css/board.css)'s `.board-screen` and `.board`,
which use exactly that to make the card area consume whatever vertical room
is left after the header/instructions/buttons take theirs.

### CSS: Grid

Where Flexbox is one-dimensional (a row *or* a column), Grid is
two-dimensional. [`board.css`](static/cardtrick/css/board.css):

```css
.trick-page {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 2.3fr) minmax(0, 1.25fr);
}
```

Three columns: left side-panel, center board, right side-panel/spacer, with
the center column getting roughly twice the relative width (`2.3fr` vs.
`1.25fr`) of each side. `minmax(0, ...)` stops a column's *minimum* content
size from forcing the grid wider than its container — a common Grid gotcha
without it.

### CSS: custom properties (variables)

```css
:root {
  --gold: #e6c068;
  --gold-bright: #ffd976;
}
.landing__highlight {
  color: var(--gold-bright);
}
```

Defined once in `:root` (the top of the cascade), reused everywhere with
`var(--name)`. Change the hex code in one place, every element using it
updates — this is *exactly* the DRY principle from [§1](#1-software-development-principles),
applied to design tokens instead of logic.

### CSS: responsive sizing without media-query guesswork

```css
font-size: clamp(1.4rem, min(6.4vw, 4.6vh), 3.4rem);
```

`clamp(min, preferred, max)` says: use the *preferred* value, but never go
below *min* or above *max*. Here, the preferred value scales with both
viewport width (`vw`) and height (`vh`), so the title shrinks gracefully on
short/narrow screens and grows on large ones, capped at both ends — no need
to hand-write ten `@media` breakpoints. This project relies on the same
technique for the fit-to-viewport board layout — see
[§7.2](#72-fitting-21-cards-in-any-viewport-height-with-pure-css).

### JavaScript: the DOM and event listeners

The DOM (Document Object Model) is the browser's live, in-memory
representation of the page — JS can read and change it, and the screen
updates. [`static/cardtrick/js/interactions.js`](static/cardtrick/js/interactions.js):

```javascript
document.querySelectorAll(".column[data-column]").forEach((column) => {
  column.addEventListener("click", () => {
    selectPileAndSubmit(column.dataset.column);
  });
});
```

`querySelectorAll` finds every element matching a CSS selector.
`addEventListener("click", callback)` registers a function to run when that
element is clicked. `column.dataset.column` reads a `data-column="0"`
HTML attribute as JS — Django's template put that attribute there
(`data-column="{{ forloop.counter0 }}"` in `board.html`), so this is data
flowing from the *server-rendered* HTML into client-side JS, without any
API call.

### Progressive enhancement

The principle: build something that works with *just HTML*, then layer JS on
top as an enhancement, not a requirement. This project's pile buttons are
real `<button type="submit">` elements inside a real `<form>` — clicking one
submits the form and reloads the page, no JS required. `interactions.js`
intercepts that click (`event.preventDefault()`) only to play a brief
animation before *manually* submitting the same form
(`selectPileAndSubmit`, described in [§7.3](#73-the-selection-animation-a-worked-example)).
If JavaScript fails to load, the game still works — just without the
animation.

---

## 7. This Project's Frontend Architecture

### 7.1 The template inheritance chain

```
base.html               <- shell: <head>, wood rail, felt table, title, {% block content %}
├── landing.html         <- Start page
├── board.html            <- Trick page (game in progress)
├── reveal.html            <- Reveal page
├── learn.html              <- Static "how to perform it" page
└── why.html                 <- Static "why it works" page
```

`base.html` also has a `{% block body_class %}` — by default it's
`"page-fit"`, applied to game screens so they pin exactly to the viewport
with no scrolling (see [§7.2](#72-fitting-21-cards-in-any-viewport-height-with-pure-css)).
`learn.html`/`why.html` override that block to be empty, opting *out* of the
no-scroll behavior since those pages are meant to be read, not fit into one
screen.

### 7.2 Fitting 21 cards in any viewport height, with pure CSS

The hard layout constraint: 3 piles of 7 cards each must all be visible with
no scrollbar, on *any* screen from a 390px phone to a 4K monitor, without
JavaScript measuring anything. The solution is a flex "fill and shrink"
chain plus one calculated height:

```css
.card {
  height: calc((100% - 6 * var(--card-gap)) / 7);
  aspect-ratio: 5 / 7;
  width: auto;
}
```

Each card's height is *computed*, not guessed: "whatever height the column
has, minus the 6 gaps between 7 cards, divided by 7." The column's own
height comes from being a flex child (`flex: 1 1 auto; min-height: 0;`) of a
chain that's ultimately pinned to `100vh`. Width then just follows from
`aspect-ratio` — no media queries, no JS `ResizeObserver`, no breakpoint
guessing. It works identically at 1920×1080 and 390×844 because it's solved
algebraically, not by trial and error at a handful of tested sizes.

### 7.3 The selection animation: a worked example

This ties together backend, frontend, and progressive enhancement into one
concrete flow. When you click a pile:

```javascript
function selectPileAndSubmit(columnIndex) {
  document.querySelectorAll(".column[data-column]").forEach((col) => {
    col.classList.add(col.dataset.column === String(columnIndex) ? "is-selected" : "is-fading");
  });
  // ...
  setTimeout(() => form.submit(), SELECT_ANIMATION_MS);
}
```

1. JS adds `is-selected`/`is-fading` classes, which CSS
   ([`board.css`](static/cardtrick/css/board.css)) uses to glow the chosen
   pile and dim the others.
2. JS waits ~550ms (letting the CSS transition play), *then* actually
   submits the form.
3. The **real** form submission is identical to what would happen with zero
   JavaScript — same `POST` to `/choose/`, same server-side validation, same
   `round_token` check. The animation is a pure visual delay layered on top
   of an unmodified backend flow, not a replacement for it.

This is why the backend's redirect-based, session-driven design
([§5.3](#53-postredirectget-and-the-round_token-guard)) never had to change
for any of the visual/UX work — the two layers are genuinely decoupled.

### 7.4 The CSS file split

`static/cardtrick/css/` is split into 6 files loaded in a fixed order:
`base.css` (tokens, reset, page shell, title) → `landing.css` → `buttons.css`
→ `board.css` → `reveal.css` → `info-pages.css`. CSS cascades — a rule
defined later in the load order can override one defined earlier, if they
have equal specificity — so the *order* of these `<link>` tags in
`base.html` matters and mirrors the original single-file section order
exactly (verified with a byte-diff when the split happened, so no rule
silently moved).

---

## 8. Testing Philosophy

### Why test in the first place

A test is a way of asking "does this still work?" without a human manually
clicking through the app. The value compounds: the first time you change
`reassemble()` and a test breaks, it just saved you from shipping a bug that
a human might not have noticed for weeks.

### The test pyramid, applied to this project

```
        /\
       /  \      cardtrick/tests/test_views.py
      /    \     (fewer, slower, test the whole request/response cycle)
     /------\
    /        \   cardtrick/tests/test_logic.py
   /          \  (many, fast, test pure functions in isolation)
  /------------\
```

`test_logic.py` tests are **unit tests** — they test one function's behavior
in isolation, with no Django, no database, no HTTP. They're fast (the whole
suite runs in well under a second) so you run them constantly. `test_views.py`
tests are **integration tests** — they exercise the full request → middleware
→ view → session → template pipeline together, catching bugs that only show
up when the pieces interact (a working algorithm called from a *broken* view
would still fail an integration test, even though `test_logic.py` passes).

### Testing edge cases, not just the happy path

```python
def test_every_starting_position_is_correctly_revealed(self):
    """A card starting at each of the 21 positions must still be
    the one revealed at the end, regardless of where it began."""
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
```

One test proves correctness for *every possible starting position* on one
shuffle. The other proves it holds across *1000 different random shuffles*.
Together they're a much stronger correctness claim than "I tried it a few
times and it worked" — this is the difference between testing a happy path
and actually trying to falsify your own assumption.

### Testing that bad input fails safely, not just that good input works

```python
def test_stale_round_token_is_ignored(self):
    """Simulates hitting the browser back button mid-game and
    resubmitting an old round's form."""
    ...

def test_choosing_without_an_active_game_does_not_crash(self):
    ...

def test_post_without_csrf_token_is_rejected(self):
    ...
```

A test suite that only checks "does the correct flow work" misses an entire
category of bugs: what happens when a user does something *unexpected*
(double-clicks, hits back, resubmits, has an expired session)? These tests
exist because "what if the user does the wrong thing" is exactly the
question a professional reviewer asks that a first draft usually skips.

### `override_settings` for testing environment-dependent code

```python
@override_settings(DEBUG=True)
def test_dev_version_changes_over_time(self):
    first = asset_version(None)["ASSET_VERSION"]
    self.assertIsInstance(first, int)

@override_settings(DEBUG=False)
def test_prod_version_is_fixed_not_wall_clock(self):
    self.assertEqual(asset_version(None)["ASSET_VERSION"], "1")
```

`cardtrick/context_processors.py` behaves differently depending on
`settings.DEBUG`. `@override_settings` lets a test temporarily force that
setting to a specific value, run the code, and check the result — without
needing to actually launch the app twice under two different real
configurations.

---

## 9. DevOps: Environments, Deployment, CI

### 9.1 Why three settings files, revisited

Covered in [§4.4](#44-settings-and-why-theyre-split-into-three-files) — the
short version: `dev.py` optimizes for "runs instantly with zero setup,"
`prod.py` optimizes for "refuses to run insecurely." Same app, different
non-negotiables per environment.

### 9.2 Static files: WhiteNoise

In dev, `runserver` serves CSS/JS itself — fine for one developer, not built
for real traffic. In production, this project uses
[WhiteNoise](https://whitenoise.readthedocs.io/), configured in
[`config/settings/prod.py`](config/settings/prod.py):

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

The `manage.py collectstatic` command (run once at deploy time) gathers
every static file and renames each one to include a hash of its *content*
(e.g. `base.a3f9c1.css`). Browsers can then cache that file **forever**,
because the filename itself changes if the content ever does — no
"how long should the cache last" guessing game. This is also why
`cardtrick/context_processors.py`'s dev-only cache-busting timestamp
(`?v=1712345678`) is explicitly gated to `DEBUG` — in prod, the *filename*
already does that job better, and adding a constantly-changing query string
on top would have defeated it (a bug this project actually had and fixed —
see git history for "Optimization audit").

### 9.3 Environment variables and secrets

```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
```

Secrets (API keys, the Django secret key used to cryptographically sign
sessions/CSRF tokens) never get hardcoded into source code, because source
code ends up in git history forever, potentially on a public GitHub repo.
Instead, the *value* lives in the deployment platform's environment variable
settings (Render's dashboard, in this project's case), and the *code* just
reads whatever's there at runtime. `.env.example` in this repo documents
*which* variables are expected without containing real values;
`.gitignore` excludes the real `.env` file from ever being committed.

### 9.4 WSGI and gunicorn

Django's built-in `runserver` is explicitly not meant for production (it's
single-threaded and has no production hardening). **WSGI** (Web Server
Gateway Interface) is the standard Python interface between a web server and
a Python web application. **gunicorn** is a production-grade WSGI server —
`config/wsgi.py` exposes the Django `application` object, and the deployment
platform runs `gunicorn config.wsgi:application` instead of
`manage.py runserver`.

### 9.5 Continuous Integration (CI)

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs the full
test suite automatically on every `git push`:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: python manage.py test cardtrick -v 2
```

The point: tests that only run when a human remembers to run them locally
get skipped under deadline pressure. A CI pipeline makes "did the tests
pass" a fact GitHub itself verifies and displays (as a green checkmark on
every commit), not something that relies on human memory or honesty.

### 9.6 Session storage across deployments: a real production trade-off

This project's default session backend stores session data in the database
(`SESSION_ENGINE = "django.contrib.sessions.backends.db"`, set in
`base.py`). That's fine on a persistent server — but Render's free tier
wipes local disk (including the sqlite database) on every redeploy, which
would silently drop everyone's in-progress game. `prod.py` overrides this:

```python
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
```

Signed-cookie sessions store the data **in the cookie itself**, encrypted
with a signature so it can't be tampered with (only read) — no server-side
storage to lose on redeploy. The trade-off, documented directly in
`prod.py`'s comments: the pile data now round-trips through the client on
every request. That's a real (if minor) exposure — but distinctly different
from the hidden-form-field approach this project deliberately avoided (see
[§5.2](#52-why-sessions-not-hidden-form-fields-not-client-js)): reading it
requires opening browser dev tools and manually decoding a cookie, not
something "View Source" reveals by accident. This is the kind of trade-off
real deployments force you to make explicitly, with the reasoning written
down — not a "just pick the textbook-correct answer" situation, because the
textbook-correct answer (DB-backed sessions) doesn't survive this specific
host's constraints.

---

## 10. Trace a Single Request, Start to Finish

Concrete walkthrough of clicking "Pile 1" mid-game, tying every layer above
together.

1. **Browser**: user clicks the chip button. `interactions.js`'s click
   listener fires, calls `selectPileAndSubmit(0)`.
2. **JS animation**: adds `.is-selected`/`.is-fading` CSS classes, plays a
   sound via Web Audio, waits ~550ms.
3. **Real form submission**: browser sends `POST /choose/` with body
   `column=0&round_token=1&csrfmiddlewaretoken=...` and the session cookie.
4. **WhiteNoise middleware**: sees this isn't a `/static/` request, passes
   it through.
5. **SessionMiddleware**: reads the session cookie, loads session data into
   `request.session`.
6. **CsrfViewMiddleware**: checks the CSRF token in the POST body against
   the one tied to this session. Mismatch → `403`, stop here. Match →
   continue.
7. **URL routing** (`cardtrick/urls.py`): `/choose/` → `views.choose_column`.
8. **View function** (`cardtrick/views.py::choose_column`):
   - Reads `pile_data`/`round_number` from `request.session`.
   - Compares `round_token` — stale? Redirect immediately, ignore the
     submission.
   - Validates `column` is `"0"`, `"1"`, or `"2"` — else, error message +
     redirect.
   - Calls `logic.deserialize_pile(pile_data)` → `logic.play_round(pile, 0)`
     — **pure algorithm code, no Django**.
   - Round `< 3`? Save the new pile/round back to `request.session`. Round
     `== 3`? Call `logic.revealed_card(new_pile)`, clear the game session
     keys, stash the result under a one-time flash key.
   - Returns `redirect("cardtrick:index")` — a `302` response, empty body,
     `Location: /`.
9. **Browser** receives the `302`, automatically makes a **new** `GET /`
   request (this is what makes the whole thing safe to refresh — see
   [§5.3](#53-postredirectget-and-the-round_token-guard)).
10. **View function** (`index`): sees either the flash-reveal key (game
    over → render `reveal.html`) or an in-progress pile/round (→ render
    `board.html` for the next round) or neither (→ `landing.html`).
11. **Template rendering**: Django fills `board.html`/`reveal.html` with the
    context dict the view built, including the shared `base.html` shell.
12. **Response**: full HTML page, `200 OK`, sent back to the browser.
13. **Browser** repaints the page. `interactions.js`'s `DOMContentLoaded`
    listener re-runs, re-wiring click handlers on the new DOM, playing the
    deal-in card animation via CSS, and (if this was the reveal) spawning
    confetti + a win sound.

Thirteen steps, and every one of them is covered somewhere in this guide.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **Client / Server** | The browser (client) and the machine running your app (server); they talk over HTTP. |
| **Request / Response** | What the client sends, and what the server sends back. |
| **GET / POST** | HTTP methods. GET = "give me data, don't change anything." POST = "here's data, do something." |
| **Status code** | A number summarizing the response (200 OK, 302 redirect, 403 forbidden, 404 not found, 405 method not allowed). |
| **Cookie** | A small piece of data the server asks the browser to store and resend on future requests. |
| **Session** | Server-side storage, keyed by a cookie holding a random ID, used to remember state between requests. |
| **CSRF** | Cross-Site Request Forgery — an attack this project defends against with per-session tokens on every form. |
| **XSS** | Cross-Site Scripting — injecting malicious script into a page; Django templates auto-escape output to prevent this by default. |
| **Middleware** | Code that wraps every request/response, running in a fixed order, before/after your view. |
| **MVT** | Model-View-Template, Django's architecture pattern. |
| **ORM** | Object-Relational Mapper — lets you write Python instead of SQL to talk to a database. Not used in this project (no models). |
| **WSGI** | The standard interface between a Python web app and a production web server. |
| **Dependency injection** | Passing in a "thing that provides some behavior" (like randomness) as a parameter, instead of hard-coding a global — makes code testable. |
| **Unit test** | Tests one function/unit in isolation. |
| **Integration test** | Tests multiple pieces working together (e.g. the full HTTP request cycle). |
| **CI (Continuous Integration)** | Automatically running your test suite on every code push. |
| **Environment variable** | A value set outside your code (by the OS/host), read at runtime — the standard place to put secrets. |
| **Flexbox / Grid** | CSS layout systems: Flexbox for one dimension (a row or column), Grid for two (rows and columns together). |
| **DOM** | Document Object Model — the browser's live, in-memory, JS-editable representation of the page. |
| **Progressive enhancement** | Build a working baseline with plain HTML first, then layer JS on top as an optional improvement. |

---

## 12. Self-Check Questions

Try answering these without looking at the code first, then verify.

1. Why does `cardtrick/logic.py` import nothing from Django? What would get
   harder to test if it did?
2. Walk through what happens, step by step, if you click a pile button
   twice very quickly. (Hint: look at `isSubmitting` in `interactions.js`
   *and* `round_token` in `views.py` — there are two independent guards.)
3. Why is `SECRET_KEY` allowed to have a fallback value in `dev.py` but not
   in `prod.py`?
4. What specific problem does the `round_token` solve that Post/Redirect/Get
   alone doesn't?
5. If you deleted `{% csrf_token %}` from `board.html`'s form, what's the
   exact error a user would see when submitting it? Why?
6. Why does `.card`'s height use `calc()` instead of a handful of `@media`
   breakpoints for different screen sizes?
7. What's the actual difference between `test_logic.py` and
   `test_views.py` in terms of *what* they can catch that the other can't?
8. Why does production use signed-cookie sessions while development uses
   database-backed sessions — what specific constraint of the hosting
   platform forced that difference?
9. If you added a new page (say, a leaderboard), list every file you'd
   plausibly need to touch, in order, tracing the same path this guide's
   [§10](#10-trace-a-single-request-start-to-finish) walkthrough took.
10. What does `frozen=True` on the `Card` dataclass actually prevent, and
    why does the test suite depend on that behavior?

---

*This guide is deliberately code-grounded — every claim points at a real
file and line you can go read right now. For deeper math on the trick
itself, see [`LEARNING.md`](LEARNING.md).*
