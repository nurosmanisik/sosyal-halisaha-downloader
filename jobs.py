from __future__ import annotations

import re
import subprocess
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from downloader import (
    _build_aria2_command,
    _effective_connections,
    _resolve_file_name,
    _skip_if_complete,
    check_tools,
    format_duration,
    format_speed,
)
from history import record_download
from preflight import PreflightInfo, format_bytes
from utils import UserFacingError, ensure_output_dir, video_type_from_url

ARIA2_PROGRESS_RE = re.compile(
    r"(?P<done>[\d.]+[KMGT]?i?B)"
    r"(?:/(?P<total>[\d.]+[KMGT]?i?B))?"
    r"(?:\((?P<percent>\d+)%\))?"
    r".*?DL:(?P<speed>[\d.]+[KMGT]?i?B)"
    r"(?:\s+ETA:(?P<eta>[^\]\s]+))?"
)
YTDLP_PERCENT_RE = re.compile(r"\[download\]\s+(?P<percent>[\d.]+)%")
YTDLP_TOTAL_RE = re.compile(r"\bof\s+~?(?P<total>[\d.]+[KMGT]?i?B)")
YTDLP_SPEED_RE = re.compile(r"\bat\s+(?P<speed>[\d.]+[KMGT]?i?B/s)")
YTDLP_ETA_RE = re.compile(r"\bETA\s+(?P<eta>\S+)")


@dataclass
class ProgressSnapshot:
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    percent: float | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None


@dataclass
class DownloadJob:
    id: str
    url: str
    output_dir: Path
    use_ytdlp: bool
    use_aria2: bool
    connections: int
    output_name: str | None
    overwrite: bool
    preflight_info: PreflightInfo | None
    status: str = "queued"
    tool: str | None = None
    output_path: Path | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    percent: float | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None
    message: str = "Sirada"
    process_pid: int | None = None
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    history_recorded: bool = False
    process: subprocess.Popen[str] | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)

    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.monotonic()
        return max(0.0, end - self.started_at)


class DownloadJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, DownloadJob] = {}
        self._lock = threading.RLock()

    def start(
        self,
        *,
        url: str,
        output_dir: Path,
        use_ytdlp: bool = False,
        use_aria2: bool = False,
        connections: int = 16,
        output_name: str | None = None,
        overwrite: bool = False,
        preflight_info: PreflightInfo | None = None,
    ) -> DownloadJob:
        job = DownloadJob(
            id=uuid.uuid4().hex,
            url=url,
            output_dir=ensure_output_dir(output_dir),
            use_ytdlp=use_ytdlp,
            use_aria2=use_aria2,
            connections=connections,
            output_name=output_name,
            overwrite=overwrite,
            preflight_info=preflight_info,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._launch(job)
        return job

    def get(self, job_id: str) -> DownloadJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise UserFacingError("Indirme isi bulunamadi.")
            return job

    def list_recent(self, limit: int = 20) -> list[DownloadJob]:
        with self._lock:
            return list(self._jobs.values())[-limit:]

    def pause(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        with self._lock:
            if job.status not in {"queued", "running"}:
                return job
            job.status = "paused"
            job.message = "Duraklatildi. Devam edince kaldigi yerden surer."
            self._stop_process(job)
        return job

    def cancel(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        with self._lock:
            if job.status in {"completed", "cancelled"}:
                return job
            job.status = "cancelled"
            job.completed_at = time.monotonic()
            job.message = "Iptal edildi. Yarım dosya resume icin korunur."
            self._stop_process(job)
        return job

    def resume(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        with self._lock:
            if job.status == "running":
                return job
            if job.status == "completed":
                raise UserFacingError("Tamamlanmis indirme tekrar devam ettirilemez.")
            job.status = "queued"
            job.error = None
            job.message = "Devam icin sirada"
            job.completed_at = None
        self._launch(job)
        return job

    def payload(self, job: DownloadJob) -> dict[str, object]:
        with self._lock:
            path = str(job.output_path) if job.output_path else None
            elapsed = job.elapsed_seconds()
            size = _current_file_size(job.output_path)
            downloaded = job.downloaded_bytes if job.downloaded_bytes is not None else size
            total = job.total_bytes
            percent = job.percent
            if percent is None and downloaded is not None and total:
                percent = min(100.0, downloaded / total * 100)
            average_speed = size / elapsed if size is not None and elapsed > 0 else None
            remaining = None
            if total is not None and downloaded is not None:
                remaining = max(0, total - downloaded)
            eta, eta_source, progress_quality = _eta_details(
                status=job.status,
                eta_seconds=job.eta_seconds,
                total_bytes=total,
                downloaded_bytes=downloaded,
                live_speed=job.speed_bytes_per_second,
                average_speed=average_speed,
            )
            return {
                "status": job.status,
                "job_id": job.id,
                "url": job.url,
                "tool": job.tool,
                "path": path,
                "file_name": job.output_path.name if job.output_path else None,
                "connections": job.connections,
                "downloaded_bytes": downloaded,
                "downloaded_text": format_bytes(downloaded),
                "total_bytes": total,
                "total_text": format_bytes(total),
                "remaining_bytes": remaining,
                "remaining_text": format_bytes(remaining),
                "percent": round(percent, 2) if percent is not None else None,
                "speed": job.speed_bytes_per_second,
                "speed_text": format_speed(job.speed_bytes_per_second),
                "eta_seconds": eta,
                "eta_text": _format_eta(eta),
                "eta_source": eta_source,
                "progress_quality": progress_quality,
                "elapsed_seconds": elapsed,
                "duration": format_duration(elapsed),
                "size": size,
                "size_text": format_bytes(size),
                "average_speed": average_speed,
                "average_speed_text": format_speed(average_speed),
                "message": job.message,
                "error": job.error,
            }

    def _launch(self, job: DownloadJob) -> None:
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        with self._lock:
            job.thread = thread
        thread.start()

    def _run_job(self, job: DownloadJob) -> None:
        with self._lock:
            job.status = "running"
            job.started_at = job.started_at or time.monotonic()
            job.message = "Indirme basladi"
        try:
            self._run_with_strategy(job)
            self._mark_completed(job)
        except UserFacingError as exc:
            self._mark_failed(job, str(exc))
        except Exception:
            self._mark_failed(job, "Beklenmeyen indirme hatasi olustu.")

    def _run_with_strategy(self, job: DownloadJob) -> None:
        status = check_tools()
        video_type = video_type_from_url(job.url)
        if job.use_ytdlp and job.use_aria2:
            raise UserFacingError("yt-dlp ve aria2c ayni anda zorlanamaz.")
        if job.use_aria2 and video_type == "m3u8":
            raise UserFacingError(".m3u8 linkleri icin yt-dlp kullanilmali.")

        if job.use_ytdlp or video_type == "m3u8" or not status.aria2c:
            if not status.yt_dlp:
                raise UserFacingError("yt-dlp kurulu degil. Kurulum: brew install yt-dlp")
            self._run_ytdlp(job)
            return

        try:
            self._run_aria2(job, job.connections)
        except UserFacingError as exc:
            if job.use_aria2 or not status.yt_dlp:
                if job.connections > 1:
                    self._run_aria2(job, 1)
                    return
                raise
            with self._lock:
                job.message = f"aria2c basarisiz oldu, yt-dlp deneniyor: {exc}"
            self._run_ytdlp(job)

    def _run_aria2(self, job: DownloadJob, connections: int) -> None:
        status = check_tools()
        if not status.aria2c:
            raise UserFacingError("aria2c kurulu degil. Kurulum: brew install aria2")
        file_name = _resolve_file_name(job.url, job.output_name, job.preflight_info)
        target = job.output_dir / file_name
        _skip_if_complete(target, job.preflight_info, job.overwrite)
        conn = _effective_connections(connections, job.preflight_info)
        command = _build_aria2_command(job.url, job.output_dir, file_name, conn)
        command.insert(-1, "--summary-interval=1")
        command.insert(-1, "--console-log-level=notice")
        with self._lock:
            job.tool = "aria2c"
            job.connections = conn
            job.output_path = target
            job.total_bytes = job.preflight_info.content_length if job.preflight_info else None
            job.message = "aria2c ile indiriliyor"
        self._run_process(job, command, parse_aria2_progress)

    def _run_ytdlp(self, job: DownloadJob) -> None:
        status = check_tools()
        if not status.yt_dlp:
            raise UserFacingError("yt-dlp kurulu degil. Kurulum: brew install yt-dlp")
        file_name = _resolve_file_name(job.url, job.output_name, job.preflight_info)
        if file_name.lower().endswith(".m3u8"):
            file_name = f"{file_name[:-5]}.mp4"
        target = job.output_dir / file_name
        _skip_if_complete(target, job.preflight_info, job.overwrite)
        command = [
            "yt-dlp",
            "--newline",
            "-N",
            "8",
            "--continue",
            "--retries",
            "5",
            "--fragment-retries",
            "5",
            "-f",
            "bv*+ba/best",
            "--merge-output-format",
            "mp4",
            "-P",
            str(job.output_dir),
            "-o",
            file_name,
            job.url,
        ]
        with self._lock:
            job.tool = "yt-dlp"
            job.connections = 8
            job.output_path = target
            job.total_bytes = job.preflight_info.content_length if job.preflight_info else None
            job.message = "yt-dlp ile indiriliyor"
        self._run_process(job, command, parse_ytdlp_progress)

    def _run_process(
        self,
        job: DownloadJob,
        command: list[str],
        parser,
    ) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise UserFacingError(f"Komut bulunamadi: {command[0]}") from exc
        with self._lock:
            job.process = process
            job.process_pid = process.pid
        assert process.stdout is not None
        for line in _iter_progress_lines(process.stdout):
            snapshot = parser(line)
            if snapshot:
                self._apply_progress(job, snapshot)
            if self.get(job.id).status in {"paused", "cancelled"}:
                break
        return_code = process.wait()
        with self._lock:
            requested_status = job.status
            job.process = None
            job.process_pid = None
        if requested_status in {"paused", "cancelled"}:
            raise UserFacingError(requested_status)
        if return_code != 0:
            raise UserFacingError(f"{command[0]} basarisiz oldu. Cikis kodu: {return_code}")

    def _apply_progress(self, job: DownloadJob, snapshot: ProgressSnapshot) -> None:
        with self._lock:
            if snapshot.downloaded_bytes is not None:
                job.downloaded_bytes = snapshot.downloaded_bytes
            if snapshot.total_bytes is not None:
                job.total_bytes = snapshot.total_bytes
            if snapshot.percent is not None:
                job.percent = snapshot.percent
            if snapshot.speed_bytes_per_second is not None:
                job.speed_bytes_per_second = snapshot.speed_bytes_per_second
            if snapshot.eta_seconds is not None:
                job.eta_seconds = snapshot.eta_seconds
            job.message = "Indiriliyor"

    def _mark_completed(self, job: DownloadJob) -> None:
        with self._lock:
            if job.status in {"paused", "cancelled"}:
                return
            job.status = "completed"
            job.completed_at = time.monotonic()
            job.percent = 100.0
            job.message = "Indirme tamamlandi"
            size = _current_file_size(job.output_path)
            job.downloaded_bytes = size or job.downloaded_bytes
            job.total_bytes = job.total_bytes or size
            should_record = not job.history_recorded
            job.history_recorded = True
        if should_record and job.output_path:
            elapsed = job.elapsed_seconds()
            size = _current_file_size(job.output_path)
            average = size / elapsed if size is not None and elapsed > 0 else None
            record_download(
                url=job.url,
                path=job.output_path,
                size=size,
                elapsed_seconds=elapsed,
                average_speed=average,
                connections=job.connections,
                range_supported=(
                    job.preflight_info.range_supported if job.preflight_info else None
                ),
            )

    def _mark_failed(self, job: DownloadJob, message: str) -> None:
        if message in {"paused", "cancelled"}:
            return
        with self._lock:
            if job.status in {"paused", "cancelled"}:
                return
            job.status = "failed"
            job.completed_at = time.monotonic()
            job.error = message
            job.message = message

    def _stop_process(self, job: DownloadJob) -> None:
        process = job.process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def parse_aria2_progress(line: str) -> ProgressSnapshot | None:
    match = ARIA2_PROGRESS_RE.search(line)
    if not match:
        return None
    return ProgressSnapshot(
        downloaded_bytes=parse_size(match.group("done")),
        total_bytes=parse_size(match.group("total")),
        percent=float(match.group("percent")) if match.group("percent") else None,
        speed_bytes_per_second=parse_size(match.group("speed")),
        eta_seconds=parse_eta(match.group("eta")),
    )


def parse_ytdlp_progress(line: str) -> ProgressSnapshot | None:
    percent_match = YTDLP_PERCENT_RE.search(line)
    if not percent_match:
        return None
    total_match = YTDLP_TOTAL_RE.search(line)
    speed_match = YTDLP_SPEED_RE.search(line)
    eta_match = YTDLP_ETA_RE.search(line)
    percent = float(percent_match.group("percent"))
    total = parse_size(total_match.group("total") if total_match else None)
    downloaded = int(total * percent / 100) if total is not None else None
    return ProgressSnapshot(
        downloaded_bytes=downloaded,
        total_bytes=total,
        percent=percent,
        speed_bytes_per_second=parse_size(speed_match.group("speed") if speed_match else None),
        eta_seconds=parse_eta(eta_match.group("eta") if eta_match else None),
    )


def parse_size(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("/s"):
        cleaned = cleaned[:-2]
    match = re.fullmatch(r"([\d.]+)\s*([KMGT]?i?B|B)", cleaned, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {
        "b": 1,
        "kb": 1000,
        "kib": 1024,
        "mb": 1000**2,
        "mib": 1024**2,
        "gb": 1000**3,
        "gib": 1024**3,
        "tb": 1000**4,
        "tib": 1024**4,
    }
    return int(number * multipliers[unit])


def parse_eta(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip().lower()
    unit_match = re.fullmatch(
        r"(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s?)?",
        value,
    )
    if unit_match and any(unit_match.groupdict().values()):
        return (
            int(unit_match.group("hours") or 0) * 3600
            + int(unit_match.group("minutes") or 0) * 60
            + int(unit_match.group("seconds") or 0)
        )
    parts = value.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def _format_eta(seconds: int | None) -> str:
    if seconds is None:
        return "hesaplaniyor"
    if seconds <= 0:
        return "tamamlandi"
    return format_duration(float(seconds))


def _eta_details(
    *,
    status: str,
    eta_seconds: int | None,
    total_bytes: int | None,
    downloaded_bytes: int | None,
    live_speed: float | None,
    average_speed: float | None,
) -> tuple[int | None, str, str]:
    if status == "completed":
        return 0, "completed", "live"
    if eta_seconds is not None:
        return eta_seconds, "tool", "live"
    speed = live_speed or average_speed
    if (
        total_bytes is not None
        and downloaded_bytes is not None
        and speed is not None
        and speed > 0
    ):
        remaining = max(0, total_bytes - downloaded_bytes)
        return int(round(remaining / speed)), "calculated", "estimated"
    return None, "unknown", "limited"


def _current_file_size(path: Path | None) -> int | None:
    if path and path.exists() and path.is_file():
        return path.stat().st_size
    return None


def _iter_progress_lines(stream: Iterable[str]) -> Iterable[str]:
    for raw_line in stream:
        for line in raw_line.replace("\r", "\n").splitlines():
            if line.strip():
                yield line.strip()
