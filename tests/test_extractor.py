import unittest

from extractor import extract_video_links


class ExtractorTestCase(unittest.TestCase):
    def test_extract_video_links_finds_absolute_mp4(self) -> None:
        html = '<video src="https://s1.sosyalhalisaha.com/matches/a.mp4"></video>'
        links = extract_video_links("https://sosyalhalisaha.com/mac-detay/1", html)
        self.assertEqual(
            [link.url for link in links],
            ["https://s1.sosyalhalisaha.com/matches/a.mp4"],
        )

    def test_extract_video_links_finds_relative_m3u8(self) -> None:
        html = '<source src="/matches/build/playlist.m3u8?x=1">'
        links = extract_video_links("https://sosyalhalisaha.com/mac-detay/1", html)
        self.assertEqual(
            [link.url for link in links],
            ["https://sosyalhalisaha.com/matches/build/playlist.m3u8?x=1"],
        )

    def test_extract_video_links_deduplicates(self) -> None:
        html = """
        <video src="https://cdn.example.com/a.mp4"></video>
        <a href="https://cdn.example.com/a.mp4">same</a>
        """
        links = extract_video_links("https://sosyalhalisaha.com/mac-detay/1", html)
        self.assertEqual(len(links), 1)

    def test_extract_video_links_handles_protocol_relative_urls(self) -> None:
        html = '<video src="//s1.sosyalhalisaha.com/matches/a.mp4"></video>'
        links = extract_video_links("https://sosyalhalisaha.com/mac-detay/1", html)
        self.assertEqual(links[0].url, "https://s1.sosyalhalisaha.com/matches/a.mp4")

    def test_extract_video_links_handles_escaped_script_urls(self) -> None:
        html = r"""<script>window.video = "https:\/\/cdn.example.com\/a.mp4";</script>"""
        links = extract_video_links("https://sosyalhalisaha.com/mac-detay/1", html)
        self.assertEqual(links[0].url, "https://cdn.example.com/a.mp4")


if __name__ == "__main__":
    unittest.main()
