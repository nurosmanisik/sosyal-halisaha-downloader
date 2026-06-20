import unittest

from finder import (
    FinderOption,
    SosyalHaliSahaFinder,
    _options_from_json,
    _field_score,
    _find_option,
    _match_from_payload,
    normalize,
)


class FinderTestCase(unittest.TestCase):
    def test_normalize_handles_turkish_characters(self) -> None:
        self.assertEqual(normalize("Üst Saha"), "ust saha")
        self.assertEqual(normalize("İstanbul / Üsküdar"), "istanbul uskudar")

    def test_find_option_accepts_case_and_accent_differences(self) -> None:
        option = _find_option(
            [FinderOption(id=437, name="ÜSKÜDAR")],
            "uskudar",
            "ilce",
        )

        self.assertEqual(option.id, 437)

    def test_field_score_prefers_exact_upper_field(self) -> None:
        self.assertEqual(_field_score("Üst Saha", "Ust Saha"), 100)
        self.assertEqual(_field_score("Alt Saha", "Ust Saha"), 0)

    def test_match_from_payload_normalizes_match(self) -> None:
        match = _match_from_payload(
            {
                "url": "https://sosyalhalisaha.com/mac-detay/174415967",
                "date": "19 Haziran 2026 23:00",
                "title": "Üst Saha",
                "image": "https://example.com/a.jpg",
                "watch_count": 39,
                "place": {"name": "Ufuk Halı Saha"},
            },
            "Ust Saha",
        )

        self.assertEqual(match.url, "https://sosyalhalisaha.com/mac-detay/174415967")
        self.assertEqual(match.place_name, "Ufuk Halı Saha")
        self.assertEqual(match.score, 100)

    def test_options_from_json_reads_site_shape(self) -> None:
        options = _options_from_json(
            {
                "status": "success",
                "data": [
                    {"id": 437, "name": "ÜSKÜDAR"},
                    {"id": 400, "name": "ADALAR"},
                ],
            },
            "name",
        )

        self.assertEqual(options[0], FinderOption(id=437, name="ÜSKÜDAR"))

    def test_cached_options_reuses_recent_loader_result(self) -> None:
        finder = object.__new__(SosyalHaliSahaFinder)
        finder._cache_ttl = 900.0
        finder._option_cache = {}
        calls = 0

        def loader() -> list[FinderOption]:
            nonlocal calls
            calls += 1
            return [FinderOption(id=34, name="İstanbul")]

        first = finder._cached_options("cities", loader)
        second = finder._cached_options("cities", loader)

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
