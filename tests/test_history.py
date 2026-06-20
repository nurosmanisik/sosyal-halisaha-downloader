import tempfile
import unittest
from pathlib import Path

from history import host_prefers_single_connection, read_history, record_download


class HistoryTestCase(unittest.TestCase):
    def test_record_and_read_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_file = Path(tmp_dir) / "downloads.jsonl"
            record_download(
                url="https://cdn.example.com/video.mp4",
                path=Path("/tmp/video.mp4"),
                size=123,
                elapsed_seconds=2.5,
                average_speed=49.2,
                connections=1,
                range_supported=False,
                history_file=history_file,
            )
            records = read_history(history_file)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].url, "https://cdn.example.com/video.mp4")
        self.assertEqual(records[0].connections, 1)

    def test_host_prefers_single_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_file = Path(tmp_dir) / "downloads.jsonl"
            record_download(
                url="https://cdn.example.com/video.mp4",
                path=Path("/tmp/video.mp4"),
                size=123,
                elapsed_seconds=2.5,
                average_speed=49.2,
                connections=1,
                range_supported=False,
                history_file=history_file,
            )

            self.assertTrue(
                host_prefers_single_connection(
                    "https://cdn.example.com/other.mp4",
                    history_file=history_file,
                )
            )


if __name__ == "__main__":
    unittest.main()
