import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as webapp
from downloader import ToolStatus
from finder import FinderDefaults, FinderOption, MatchSearchResult, MatchResult
from extractor import VideoCandidate
from jobs import DownloadJob
from preflight import PreflightInfo
from utils import UserFacingError


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        webapp.app.config.update(TESTING=True)
        self.client = webapp.app.test_client()

    def test_tools_endpoint(self) -> None:
        with patch.object(
            webapp,
            "check_tools",
            return_value=ToolStatus(yt_dlp=True, aria2c=False, ffmpeg=True),
        ):
            response = self.client.get("/api/tools")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["yt_dlp"], True)
        self.assertEqual(response.get_json()["aria2c"], False)

    def test_index_has_user_friendly_advanced_settings(self) -> None:
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Gelismis ayarlar", html)
        self.assertIn("Normalde degistirmen gerekmez.", html)
        self.assertIn("Secili Videoyu Indir", html)
        self.assertIn("Ayni macin diger kamera kayitlarini bulmayi dener.", html)
        self.assertIn("Preflight sorun cikartirsa kullan.", html)
        self.assertIn("Indirme ilerlemesi", html)
        self.assertIn("Duraklat", html)
        self.assertIn("Devam Et", html)
        self.assertIn("Iptal Et", html)
        self.assertIn("Kalan Boyut", html)
        self.assertIn("Klasorde Goster", html)
        self.assertIn("Yolu Kopyala", html)
        self.assertIn("Maci otomatik bul", html)
        self.assertIn("finderCityInput", html)
        self.assertIn("finderDistrictInput", html)
        self.assertIn("finderPlaceInput", html)

    def test_history_endpoint(self) -> None:
        with patch.object(webapp, "read_history", return_value=[]):
            response = self.client.get("/api/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_finder_defaults_endpoint(self) -> None:
        with patch.object(
            webapp.finder,
            "defaults",
            return_value=FinderDefaults(date="2026-06-19"),
        ):
            response = self.client.get("/api/finder/defaults")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["city"], "İstanbul")
        self.assertEqual(data["place"], "Ufuk Halı Saha")
        self.assertEqual(data["date"], "2026-06-19")

    def test_finder_option_endpoints(self) -> None:
        with patch.object(
            webapp.finder,
            "list_cities",
            return_value=[FinderOption(id=34, name="İSTANBUL")],
        ), patch.object(
            webapp.finder,
            "list_districts",
            return_value=[FinderOption(id=437, name="ÜSKÜDAR")],
        ), patch.object(
            webapp.finder,
            "list_places",
            return_value=[FinderOption(id=40, name="Ufuk Halı Saha")],
        ):
            cities = self.client.get("/api/finder/cities")
            districts = self.client.get("/api/finder/districts?city_id=34")
            places = self.client.get("/api/finder/places?district_id=437")

        self.assertEqual(cities.get_json()[0]["id"], 34)
        self.assertEqual(districts.get_json()[0]["id"], 437)
        self.assertEqual(places.get_json()[0]["name"], "Ufuk Halı Saha")

    def test_finder_fields_endpoint(self) -> None:
        with patch.object(
            webapp.finder,
            "list_fields",
            return_value=[
                FinderOption(id=1, name="Alt Saha"),
                FinderOption(id=2, name="Üst Saha"),
            ],
        ):
            response = self.client.post(
                "/api/finder/fields",
                json={
                    "city_id": 34,
                    "district_id": 437,
                    "place_id": 40,
                    "date": "2026-06-19",
                    "time": "23:00",
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in data], ["Alt Saha", "Üst Saha"])

    def test_finder_search_endpoint(self) -> None:
        with patch.object(
            webapp.finder,
            "search",
            return_value=MatchSearchResult(
                matches=[
                    MatchResult(
                        url="https://sosyalhalisaha.com/mac-detay/174415967",
                        date="19 Haziran 2026 23:00",
                        title="Üst Saha",
                        place_name="Ufuk Halı Saha",
                        image=None,
                        watch_count=39,
                        score=100,
                    )
                ],
                preferred_url="https://sosyalhalisaha.com/mac-detay/174415967",
                filter_url="https://sosyalhalisaha.com/filtre/...",
            ),
        ):
            response = self.client.post(
                "/api/finder/search",
                json={
                    "city_id": 34,
                    "district_id": 437,
                    "place_id": 40,
                    "date": "2026-06-19",
                    "time": "23:00",
                    "field": "Üst Saha",
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["preferred_url"], "https://sosyalhalisaha.com/mac-detay/174415967")
        self.assertEqual(data["matches"][0]["title"], "Üst Saha")

    def test_finder_extract_endpoint(self) -> None:
        with patch.object(
            webapp.finder,
            "extract_videos",
            return_value=[
                VideoCandidate(
                    url="https://cdn.example.com/video.mp4",
                    source="html",
                )
            ],
        ), patch.object(
            webapp,
            "fetch_preflight",
            return_value=PreflightInfo(
                url="https://cdn.example.com/video.mp4",
                content_length=1024,
            ),
        ):
            response = self.client.post(
                "/api/finder/extract",
                json={"match_url": "https://sosyalhalisaha.com/mac-detay/174415967"},
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["selected_url"], "https://cdn.example.com/video.mp4")
        self.assertEqual(data["candidates"][0]["type"], "mp4")

    def test_dry_run_rejects_invalid_url(self) -> None:
        response = self.client.post("/api/dry-run", json={"url": "file:///tmp/a.mp4"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "error")

    def test_dry_run_direct_mp4(self) -> None:
        with patch.object(
            webapp,
            "fetch_preflight",
            return_value=PreflightInfo(
                url="https://cdn.example.com/video.mp4",
                content_length=1024,
                content_type="video/mp4",
                range_supported=True,
            ),
        ):
            response = self.client.post(
                "/api/dry-run",
                json={"url": "https://cdn.example.com/video.mp4"},
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["candidates"][0]["type"], "mp4")
        self.assertEqual(data["preflight"]["content_length"], 1024)

    def test_download_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            job = DownloadJob(
                id="job-1",
                url="https://cdn.example.com/video.mp4",
                output_dir=Path(tmp_dir),
                use_ytdlp=False,
                use_aria2=False,
                connections=1,
                output_name=None,
                overwrite=False,
                preflight_info=PreflightInfo(url="https://cdn.example.com/video.mp4"),
            )
            with patch.object(
                webapp,
                "fetch_preflight",
                return_value=PreflightInfo(url="https://cdn.example.com/video.mp4"),
            ), patch.object(
                webapp.job_manager,
                "start",
                return_value=job,
            ):
                response = self.client.post(
                    "/api/download",
                    json={"url": "https://cdn.example.com/video.mp4"},
                )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["job_id"], "job-1")

    def test_job_status_endpoint(self) -> None:
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
                percent=25.0,
                output_path=target,
                downloaded_bytes=5,
                total_bytes=10,
                speed_bytes_per_second=1,
            )
            with patch.object(webapp.job_manager, "get", return_value=job):
                response = self.client.get("/api/jobs/job-1")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["job_id"], "job-1")
        self.assertEqual(data["percent"], 25.0)
        self.assertEqual(data["remaining_bytes"], 5)
        self.assertEqual(data["eta_seconds"], 5)
        self.assertEqual(data["eta_source"], "calculated")
        self.assertEqual(data["file_name"], "video.mp4")

    def test_reveal_endpoint_uses_open_reveal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "video.mp4"
            target.write_bytes(b"123")
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
                status="completed",
                output_path=target,
            )
            with patch.object(webapp.job_manager, "get", return_value=job), patch.object(
                webapp.subprocess,
                "run",
            ) as run:
                response = self.client.post("/api/jobs/job-1/reveal")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(run.call_args.args[0], ["open", "-R", str(target)])

    def test_download_user_error(self) -> None:
        with patch.object(webapp, "fetch_preflight", side_effect=UserFacingError("bad")):
            response = self.client.post(
                "/api/download",
                json={"url": "https://cdn.example.com/video.mp4"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "bad")


if __name__ == "__main__":
    unittest.main()
