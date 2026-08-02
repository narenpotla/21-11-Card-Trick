"""
View + session integration tests. Unlike test_logic.py these use
Django's test client because they're specifically about HTTP/session
plumbing (redirects, CSRF, resubmission guards) rather than the algorithm.
"""

from django.test import Client, TestCase
from django.urls import reverse

from cardtrick import logic
from cardtrick.views import SESSION_PILE_KEY, SESSION_ROUND_KEY, SESSION_ROUND_TOKEN_KEY


class GameFlowTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf_token(self, response):
        return response.cookies["csrftoken"].value

    def test_landing_page_when_no_game_in_session(self):
        response = self.client.get(reverse("cardtrick:index"))
        self.assertContains(response, "Start")
        self.assertTemplateUsed(response, "cardtrick/landing.html")

    def test_start_game_requires_post(self):
        response = self.client.get(reverse("cardtrick:start_game"))
        self.assertEqual(response.status_code, 405)

    def test_full_game_round_trip(self):
        # GET once to obtain a CSRF cookie, matching how a browser behaves.
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)

        response = self.client.post(
            reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token}
        )
        self.assertRedirects(response, reverse("cardtrick:index"))

        board = self.client.get(reverse("cardtrick:index"))
        self.assertTemplateUsed(board, "cardtrick/board.html")
        self.assertEqual(board.context["round_display"], 1)

        for expected_round in (2, 3):
            round_token = self.client.session[SESSION_ROUND_TOKEN_KEY]
            response = self.client.post(
                reverse("cardtrick:choose_column"),
                {"csrfmiddlewaretoken": token, "column": "0", "round_token": round_token},
            )
            self.assertRedirects(response, reverse("cardtrick:index"))
            if expected_round <= 3:
                board = self.client.get(reverse("cardtrick:index"))

        # Final choice (round 3) should trigger the reveal, not another board.
        round_token = self.client.session[SESSION_ROUND_TOKEN_KEY]
        self.client.post(
            reverse("cardtrick:choose_column"),
            {"csrfmiddlewaretoken": token, "column": "0", "round_token": round_token},
        )
        reveal = self.client.get(reverse("cardtrick:index"))
        self.assertTemplateUsed(reveal, "cardtrick/reveal.html")
        self.assertIn("card", reveal.context)

        # Session game keys are cleared once revealed.
        self.assertNotIn(SESSION_PILE_KEY, self.client.session)

    def test_reveal_is_shown_only_once(self):
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)
        self.client.post(reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token})
        for _ in range(logic.ROUNDS):
            round_token = self.client.session[SESSION_ROUND_TOKEN_KEY]
            self.client.post(
                reverse("cardtrick:choose_column"),
                {"csrfmiddlewaretoken": token, "column": "1", "round_token": round_token},
            )

        first_view = self.client.get(reverse("cardtrick:index"))
        self.assertTemplateUsed(first_view, "cardtrick/reveal.html")

        # Refreshing again (simulating hitting reload on the reveal page)
        # must not error and must not show a stale reveal -- it falls
        # back to the landing page since the game is over.
        second_view = self.client.get(reverse("cardtrick:index"))
        self.assertTemplateUsed(second_view, "cardtrick/landing.html")

    def test_stale_round_token_is_ignored(self):
        """Simulates hitting the browser back button mid-game and
        resubmitting an old round's form -- must not double-advance
        or corrupt the round counter."""
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)
        self.client.post(reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token})

        stale_token = self.client.session[SESSION_ROUND_TOKEN_KEY]
        self.client.post(
            reverse("cardtrick:choose_column"),
            {"csrfmiddlewaretoken": token, "column": "0", "round_token": stale_token},
        )
        self.assertEqual(self.client.session[SESSION_ROUND_KEY], 1)

        # Resubmit the same (now stale) round_token again.
        self.client.post(
            reverse("cardtrick:choose_column"),
            {"csrfmiddlewaretoken": token, "column": "0", "round_token": stale_token},
        )
        # Round must not have advanced a second time.
        self.assertEqual(self.client.session[SESSION_ROUND_KEY], 1)

    def test_invalid_column_value_is_rejected(self):
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)
        self.client.post(reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token})
        round_token = self.client.session[SESSION_ROUND_TOKEN_KEY]

        response = self.client.post(
            reverse("cardtrick:choose_column"),
            {"csrfmiddlewaretoken": token, "column": "7", "round_token": round_token},
        )
        self.assertRedirects(response, reverse("cardtrick:index"))
        # Round must not have advanced on invalid input.
        self.assertEqual(self.client.session[SESSION_ROUND_KEY], 0)

    def test_choosing_without_an_active_game_does_not_crash(self):
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)
        response = self.client.post(
            reverse("cardtrick:choose_column"),
            {"csrfmiddlewaretoken": token, "column": "0", "round_token": "0"},
        )
        self.assertRedirects(response, reverse("cardtrick:index"))

    def test_reset_clears_in_progress_game(self):
        first = self.client.get(reverse("cardtrick:index"))
        token = self._csrf_token(first)
        self.client.post(reverse("cardtrick:start_game"), {"csrfmiddlewaretoken": token})
        self.assertIn(SESSION_PILE_KEY, self.client.session)

        self.client.post(reverse("cardtrick:reset_game"), {"csrfmiddlewaretoken": token})
        self.assertNotIn(SESSION_PILE_KEY, self.client.session)

        landing = self.client.get(reverse("cardtrick:index"))
        self.assertTemplateUsed(landing, "cardtrick/landing.html")

    def test_post_without_csrf_token_is_rejected(self):
        self.client.get(reverse("cardtrick:index"))
        response = self.client.post(reverse("cardtrick:start_game"), {})
        self.assertEqual(response.status_code, 403)
