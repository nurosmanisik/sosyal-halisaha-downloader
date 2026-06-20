import tempfile
import unittest
from pathlib import Path

from jobs import (
    DownloadJob,
    DownloadJobManager,
    parse_aria2_progress,
    parse_eta,
    parse_size,
    parse_ytdlp_progress,
)


class JobsTestCase(unittest.TestCase):
    def test_parse_size(self) -> None:
        self.assertEqual(parse_size("1KiB"), 1024)
        self.assertEqual(parse_size("1.5MiB"), 1572864)
        self.assertEqual(parse_size("2MB/s"), 2000000)

    def test_parse_eta(self) -> None:
        self.assertEqual(parse_eta("12"), 12)
        self.assertEqual(parse_eta("01:05"), 65)
        self.assertEqual(parse_eta("01:02:03"), 3723)
        self.assertEqual(parse_eta("20s"), 20)
        self.assertEqual(parse_eta("2m31s"), 151)
        self.assertEqual(parse_eta("1h02m"), 3720)

    def test_parse_aria2_progress(self) -> None:
        line = "[#abc 123MiB/609MiB(20%) CN:16 DL:3.2MiB ETA:02:31]"
        snapshot = parse_aria2_progress(line)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.downloaded_bytes, 128974848)
        self.assertEqual(snapshot.total_bytes, 638582784)
        self.assertEqual(snapshot.percent, 20.0)
        self.assertEqual(snapshot.speed_bytes_per_second, 3355443)
        self.assertEqual(snapshot.eta_seconds, 151)

    def test_parse_ytdlp_progress(self) -> None:
        line = "[download]  45.2% of 120.00MiB at 2.00MiB/s ETA 00:32"
        snapshot = parse_ytdlp_progress(line)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.percent, 45.2)
        self.assertEqual(snapshot.total_bytes, 125829120)
        self.assertEqual(snapshot.speed_bytes_per_second, 2097152)
        self.assertEqual(snapshot.eta_seconds, 32)

    def test_payload_calculates_eta_when_tool_eta_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"12345")
            job = DownloadJob(
                id="job-1",
                url="https://cdn.example.com/video.mp4",
                output_dir=Path(tmp_dir),
                use_ytdlp=False,
                use_aria2=False,
                connections=4,
                output_name=None,
                overwrite=False,
                preflight_info=None,
                status="running",
                output_path=target,
                downloaded_bytes=50,
                total_bytes=100,
                speed_bytes_per_second=10,
            )
            payload = DownloadJobManager().payload(job)

        self.assertEqual(payload["remaining_bytes"], 50)
        self.assertEqual(payload["eta_seconds"], 5)
        self.assertEqual(payload["eta_source"], "calculated")
        self.assertEqual(payload["progress_quality"], "estimated")

    def test_payload_for_paused_job_keeps_resume_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"12345")
            job = DownloadJob(
                id="job-1",
                url="https://cdn.example.com/video.mp4",
                output_dir=Path(tmp_dir),
                use_ytdlp=False,
                use_aria2=False,
                connections=4,
                output_name=None,
                overwrite=False,
                preflight_info=None,
                status="paused",
                output_path=target,
                downloaded_bytes=5,
                total_bytes=10,
            )
            payload = DownloadJobManager().payload(job)

        self.assertEqual(payload["status"], "paused")
        self.assertEqual(payload["remaining_bytes"], 5)
        self.assertEqual(payload["file_name"], "video.mp4")


if __name__ == "__main__":
    unittest.main()
