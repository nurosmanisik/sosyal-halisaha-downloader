import unittest

from utils import (
    UserFacingError,
    clamp_connections,
    downloadable_filename_from_url,
    filename_from_url,
    is_direct_video_url,
    sanitize_filename,
    validate_url,
    video_type_from_url,
)


class UtilsTestCase(unittest.TestCase):
    def test_validate_url_accepts_http_and_https(self) -> None:
        self.assertEqual(
            validate_url("https://example.com/video.mp4"),
            "https://example.com/video.mp4",
        )
        self.assertEqual(validate_url("http://example.com"), "http://example.com")

    def test_validate_url_rejects_non_http_urls(self) -> None:
        with self.assertRaises(UserFacingError):
            validate_url("file:///tmp/video.mp4")

    def test_sanitize_filename_removes_unsafe_characters(self) -> None:
        self.assertEqual(sanitize_filename(' mac:/detay*?"<>| .mp4 '), "mac-detay-.mp4")

    def test_sanitize_filename_uses_default_for_empty_name(self) -> None:
        self.assertEqual(sanitize_filename('   .-_ "  '), "sosyal-halisaha-video")

    def test_sanitize_filename_removes_control_characters(self) -> None:
        self.assertEqual(sanitize_filename("mac\x00final\x1f.mp4"), "macfinal.mp4")

    def test_filename_from_url_decodes_and_sanitizes(self) -> None:
        url = "https://cdn.example.com/a%20b/video:1.mp4?token=abc"
        self.assertEqual(filename_from_url(url), "video-1.mp4")

    def test_is_direct_video_url(self) -> None:
        self.assertTrue(is_direct_video_url("https://example.com/a.mp4"))
        self.assertTrue(is_direct_video_url("https://example.com/a.m3u8"))
        self.assertFalse(is_direct_video_url("https://example.com/mac-detay/123"))

    def test_downloadable_filename_converts_m3u8_to_mp4(self) -> None:
        self.assertEqual(
            downloadable_filename_from_url("https://example.com/playlist.m3u8"),
            "playlist.mp4",
        )

    def test_video_type_from_url(self) -> None:
        self.assertEqual(video_type_from_url("https://example.com/a.mp4?x=1"), "mp4")
        self.assertEqual(video_type_from_url("https://example.com/a.m3u8"), "m3u8")
        self.assertEqual(video_type_from_url("https://example.com/page"), "unknown")

    def test_clamp_connections(self) -> None:
        self.assertEqual(clamp_connections(0), 1)
        self.assertEqual(clamp_connections(16), 16)
        self.assertEqual(clamp_connections(99), 32)


if __name__ == "__main__":
    unittest.main()
