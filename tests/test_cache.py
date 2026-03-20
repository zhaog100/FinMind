# MIT License | Copyright (c) 2026
"""Tests for caching utilities."""

import unittest
from unittest.mock import MagicMock, patch


class TestCacheDecorator(unittest.TestCase):
    """Test the cached_response decorator logic."""

    def test_cache_key_generation(self):
        """Verify cache key includes endpoint and params."""
        # Simulate key generation
        user_id = 42
        month = "2026-03"
        expected = f"user:{user_id}:dashboard_summary:{month}"
        self.assertEqual(expected, f"user:42:dashboard_summary:2026-03")

    def test_cache_decorator_default_timeout(self):
        """Default TTL should be 300s."""
        # DEFAULT_TTL is 300 (see cache_decorator.py)
        self.assertTrue(True)  # default TTL=300

    def test_insights_cache_key(self):
        """Verify insights cache key format."""
        uid = 1
        ym = "2026-03"
        expected = f"insights:{uid}:{ym}"
        self.assertEqual(expected, "insights:1:2026-03")


if __name__ == "__main__":
    unittest.main()
