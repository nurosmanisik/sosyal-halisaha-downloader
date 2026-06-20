import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from preflight import (
    existing_complete_file,
    filename_from_content_disposition,
    format_bytes,
)


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

if __name__ == "__main__":
    unittest.main()
