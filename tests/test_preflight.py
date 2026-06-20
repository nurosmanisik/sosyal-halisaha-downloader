import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from preflight import (
    _raise_for_status,
    existing_complete_file,
    filename_from_content_disposition,
    format_bytes,
)
from utils import UserFacingError


class PreflightTestCase(unittest.TestCase):
    def test_filename_from_content_disposition_plain(self) -> None:
        self.assertEqual(
            filename_from_content_disposition('attachment; filename="mac-final.mp4"'),
            "mac-final.mp4",
        )

    def test_filename_from_content_disposition_encoded(self) -> None:
        self.assertEqual(
            filename_from_content_disposition("attachment; filename*=UTF-8''mac%201.mp4"),
            "mac 1.mp4",
        )

    def test_format_bytes(self) -> None:
        self.assertEqual(format_bytes(None), "bilinmiyor")
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(1024 * 1024), "1.0 MB")

    def test_existing_complete_file_uses_expected_size(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "video.mp4"
            path.write_bytes(b"123")
            self.assertTrue(existing_complete_file(path, 3))
            self.assertFalse(existing_complete_file(path, 4))

    def test_raise_for_status_maps_common_user_errors(self) -> None:
        for status_code in (401, 403, 404, 500):
            with self.subTest(status_code=status_code):
                with self.assertRaises(UserFacingError):
                    _raise_for_status(status_code)

    def test_raise_for_status_accepts_success(self) -> None:
        self.assertIsNone(_raise_for_status(200))

if __name__ == "__main__":
    unittest.main()
