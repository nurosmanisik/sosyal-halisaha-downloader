import unittest
from unittest.mock import patch

import camera
from camera import discover_camera_variants
from preflight import PreflightInfo
from utils import UserFacingError


class CameraTestCase(unittest.TestCase):
    def test_discover_camera_variants_checks_expected_urls(self) -> None:
        seen: list[str] = []

        def fake_fetch(url: str, timeout: int = 5) -> PreflightInfo:
            seen.append(url)
            if url.endswith(".1-2.mp4"):
                return PreflightInfo(url=url)
            raise UserFacingError("skip")

        with patch.object(camera, "fetch_preflight", side_effect=fake_fetch):
            found = discover_camera_variants("https://cdn.example.com/a.1-1.mp4")

        self.assertEqual(
            [item.url for item in found],
            ["https://cdn.example.com/a.1-2.mp4"],
        )
        self.assertIn("https://cdn.example.com/a.3-3.mp4", seen)


if __name__ == "__main__":
    unittest.main()
