import unittest
from unittest.mock import patch

from finder import (
    FinderOption,
    SosyalHaliSahaFinder,
    _field_score,
    _find_option,
    _match_from_payload,
    _options_from_json,
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
        self.assertEqual(_field_score("Üst Saha 1", "Ust Saha"), 80)
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

    def test_cached_options_reloads_after_ttl(self) -> None:
        finder = object.__new__(SosyalHaliSahaFinder)
        finder._cache_ttl = 10.0
        finder._option_cache = {}
        calls = 0

        def loader() -> list[FinderOption]:
            nonlocal calls
            calls += 1
            return [FinderOption(id=calls, name="İstanbul")]

        with patch("finder.time.monotonic", side_effect=[100.0, 105.0, 111.0]):
            first = finder._cached_options("cities", loader)
            second = finder._cached_options("cities", loader)
            third = finder._cached_options("cities", loader)

        self.assertEqual(first[0].id, 1)
        self.assertEqual(second[0].id, 1)
        self.assertEqual(third[0].id, 2)
        self.assertEqual(calls, 2)

    def test_post_filter_refreshes_token_once_after_json_error(self) -> None:
        finder = object.__new__(SosyalHaliSahaFinder)
        finder.base_url = "https://sosyalhalisaha.com"
        finder.timeout = 15
        finder._token = "old-token"
        tokens: list[str] = []

        class Response:
            def __init__(self, payload: dict[str, object]) -> None:
                self._payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return self._payload

        class Session:
            def __init__(self) -> None:
                self.calls = 0

            def post(self, _url, *, data, headers, timeout):
                self.calls += 1
                tokens.append(str(data["_token"]))
                if self.calls == 1:
                    return Response({"status": "error"})
                return Response({"status": "success", "data": []})

        session = Session()
        finder.session = session

        def ensure_token() -> str:
            if finder._token is None:
                finder._token = "new-token"
            return finder._token

        finder._ensure_token = ensure_token

        data = finder._post_filter({"city": 34, "type": "getdistrict"})

        self.assertEqual(data["status"], "success")
        self.assertEqual(tokens, ["old-token", "new-token"])
        self.assertEqual(session.calls, 2)


if __name__ == "__main__":
    unittest.main()
