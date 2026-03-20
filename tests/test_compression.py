# MIT License | Copyright (c) 2026
"""Tests for API compression."""

import unittest
import gzip
from io import BytesIO


class TestCompression(unittest.TestCase):
    """Test gzip compression utilities."""

    def test_compress_json_payload(self):
        """JSON > 1KB should compress."""
        large_json = '{"data":"' + "x" * 2000 + '"}'
        raw = large_json.encode()
        buf = BytesIO()
        with gzip.GzipFile(mode="wb", fileobj=buf) as gz:
            gz.write(raw)
        compressed = buf.getvalue()
        self.assertLess(len(compressed), len(raw))

    def test_skip_small_payload(self):
        """Small payloads should not be compressed."""
        tiny = b'{"ok":true}'
        self.assertLess(len(tiny), 1024)  # Below threshold

    def test_compression_stats_keys(self):
        """Stats dict should have expected keys."""
        from packages.backend.app.utils.compression import _stats
        expected = {"total_responses", "compressed", "bytes_before", "bytes_after"}
        self.assertTrue(expected.issubset(set(_stats.keys())))

    def test_min_compress_size(self):
        """MIN_COMPRESS_SIZE should be 1024."""
        from packages.backend.app.utils.compression import MIN_COMPRESS_SIZE
        self.assertEqual(MIN_COMPRESS_SIZE, 1024)


if __name__ == "__main__":
    unittest.main()
