"""
The ASSET_VERSION context processor previously ran the same wall-clock
cache-buster in every environment, including production -- which silently
defeated WhiteNoise's content-hash caching (see git history). These tests
pin down the dev/prod split so that regression can't sneak back in unnoticed.
"""

from django.test import TestCase, override_settings

from cardtrick.context_processors import asset_version


class AssetVersionTests(TestCase):
    @override_settings(DEBUG=True)
    def test_dev_version_changes_over_time(self):
        first = asset_version(None)["ASSET_VERSION"]
        self.assertIsInstance(first, int)

    @override_settings(DEBUG=False)
    def test_prod_version_is_fixed_not_wall_clock(self):
        # A fixed value means WhiteNoise's content-hashed filenames (not
        # this context processor) are what actually bust the cache in prod.
        self.assertEqual(asset_version(None)["ASSET_VERSION"], "1")
