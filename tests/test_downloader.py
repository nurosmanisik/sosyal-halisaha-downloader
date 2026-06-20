import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import downloader
from downloader import ToolStatus, download_video, format_duration, format_speed
from preflight import PreflightInfo
from utils import UserFacingError


class DownloaderTestCase(unittest.TestCase):
    def test_mp4_uses_aria2_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(downloader.subprocess, "run") as run:
                target = download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                    connections=64,
                )

        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "aria2c")
        self.assertIn("--max-tries=5", cmd)
        self.assertEqual(cmd[cmd.index("-x") + 1], "32")
        self.assertEqual(target.path.name, "video.mp4")

    def test_m3u8_uses_ytdlp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(downloader.subprocess, "run") as run:
                target = download_video(
                    "https://cdn.example.com/playlist.m3u8",
                    Path(tmp_dir),
                )

        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "yt-dlp")
        self.assertIn("bv*+ba/best", cmd)
        self.assertEqual(target.path.name, "playlist.mp4")

    def test_aria2_multi_connection_failure_tries_single_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(
                downloader.subprocess,
                "run",
                side_effect=[subprocess.CalledProcessError(1, ["aria2c"]), None],
            ) as run, patch.object(downloader, "print", create=True):
                target = download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][0], "aria2c")
        self.assertEqual(run.call_args_list[1].args[0][0], "aria2c")
        self.assertEqual(run.call_args_list[1].args[0][run.call_args_list[1].args[0].index("-x") + 1], "1")
        self.assertEqual(target.path.name, "video.mp4")

    def test_aria2_total_failure_falls_back_to_ytdlp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(
                downloader.subprocess,
                "run",
                side_effect=[
                    subprocess.CalledProcessError(1, ["aria2c"]),
                    subprocess.CalledProcessError(1, ["aria2c"]),
                    None,
                ],
            ) as run, patch.object(downloader, "print", create=True):
                target = download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                )

        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[0].args[0][0], "aria2c")
        self.assertEqual(run.call_args_list[1].args[0][0], "aria2c")
        self.assertEqual(run.call_args_list[2].args[0][0], "yt-dlp")
        self.assertEqual(target.path.name, "video.mp4")

    def test_forced_aria2_rejects_m3u8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ):
                with self.assertRaises(UserFacingError):
                    download_video(
                        "https://cdn.example.com/playlist.m3u8",
                        Path(tmp_dir),
                        use_aria2=True,
                    )

    def test_output_name_overrides_url_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(downloader.subprocess, "run") as run:
                target = download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                    output_name="Mac 1:/final.mp4",
                )

        cmd = run.call_args.args[0]
        self.assertEqual(target.path.name, "Mac 1-final.mp4")
        self.assertEqual(cmd[cmd.index("--out") + 1], "Mac 1-final.mp4")

    def test_no_range_support_uses_single_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(downloader.subprocess, "run") as run:
                download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                    connections=16,
                    preflight_info=PreflightInfo(
                        url="https://cdn.example.com/video.mp4",
                        range_supported=False,
                    ),
                )

        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("-x") + 1], "1")

    def test_complete_existing_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"12345")
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ):
                with self.assertRaises(UserFacingError):
                    download_video(
                        "https://cdn.example.com/video.mp4",
                        Path(tmp_dir),
                        preflight_info=PreflightInfo(
                            url="https://cdn.example.com/video.mp4",
                            content_length=5,
                        ),
                    )

    def test_smaller_existing_file_can_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"123")
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ), patch.object(downloader.subprocess, "run") as run:
                download_video(
                    "https://cdn.example.com/video.mp4",
                    Path(tmp_dir),
                    preflight_info=PreflightInfo(
                        url="https://cdn.example.com/video.mp4",
                        content_length=5,
                    ),
                )

        self.assertEqual(run.call_args.args[0][0], "aria2c")

    def test_larger_existing_file_requires_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"123456")
            with patch.object(
                downloader,
                "check_tools",
                return_value=ToolStatus(yt_dlp=True, aria2c=True, ffmpeg=True),
            ):
                with self.assertRaises(UserFacingError):
                    download_video(
                        "https://cdn.example.com/video.mp4",
                        Path(tmp_dir),
                        preflight_info=PreflightInfo(
                            url="https://cdn.example.com/video.mp4",
                            content_length=5,
                        ),
                    )

    def test_format_duration_and_speed(self) -> None:
        self.assertEqual(format_duration(1717), "28 dk 37 sn")
        self.assertEqual(format_speed(1024), "1.0 KB/s")


if __name__ == "__main__":
    unittest.main()
