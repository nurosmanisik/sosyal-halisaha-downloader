from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from preflight import PreflightInfo, existing_complete_file, format_bytes
from utils import (
    UserFacingError,
    clamp_connections,
    command_exists,
    downloadable_filename_from_url,
    ensure_output_dir,
    filename_from_url,
    video_type_from_url,
)

LOGGER = logging.getLogger("sosyal_halisaha_downloader")


@dataclass(frozen=True)
class ToolStatus:
    yt_dlp: bool
    aria2c: bool
    ffmpeg: bool


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    elapsed_seconds: float
    file_size: int | None
    connections: int

    @property
    def average_speed(self) -> float | None:
        if self.file_size is None or self.elapsed_seconds <= 0:
            return None
        return self.file_size / self.elapsed_seconds


def check_tools() -> ToolStatus:
    return ToolStatus(
        yt_dlp=command_exists("yt-dlp"),
        aria2c=command_exists("aria2c"),
        ffmpeg=command_exists("ffmpeg"),
    )


def print_tool_status(status: ToolStatus) -> None:
    print("Bagimlilik kontrolu:")
    print(f"- yt-dlp: {'var' if status.yt_dlp else 'yok'}")
    print(f"- aria2c: {'var' if status.aria2c else 'yok'}")
    print(f"- ffmpeg: {'var' if status.ffmpeg else 'yok'}")
    if not status.yt_dlp or not status.aria2c or not status.ffmpeg:
        print("Eksik araclar icin onerilen komut: brew install yt-dlp aria2 ffmpeg")


def download_video(
    url: str,
    output_dir: Path,
    *,
    use_ytdlp: bool = False,
    use_aria2: bool = False,
    connections: int = 16,
    output_name: str | None = None,
    overwrite: bool = False,
    preflight_info: PreflightInfo | None = None,
    quiet: bool = False,
) -> DownloadResult:
    started_at = time.monotonic()
    output_dir = ensure_output_dir(output_dir)
    status = check_tools()
    used_connections = 1

    if use_ytdlp and use_aria2:
        raise UserFacingError("--use-ytdlp ve --use-aria2 ayni anda kullanilamaz.")

    video_type = video_type_from_url(url)

    if use_ytdlp:
        path = _download_with_ytdlp(
            url,
            output_dir,
            status,
            output_name=output_name,
            overwrite=overwrite,
            preflight_info=preflight_info,
            quiet=quiet,
        )
        return _result(path, started_at, used_connections)

    if use_aria2:
        if video_type == "m3u8":
            raise UserFacingError(
                ".m3u8 linkleri icin aria2c yerine yt-dlp kullanin."
            )
        path, used_connections = _download_with_aria2(
            url,
            output_dir,
            connections,
            status,
            output_name=output_name,
            overwrite=overwrite,
            preflight_info=preflight_info,
            quiet=quiet,
        )
        return _result(path, started_at, used_connections)

    if video_type == "mp4" and status.aria2c:
        try:
            path, used_connections = _download_with_aria2(
                url,
                output_dir,
                connections,
                status,
                output_name=output_name,
                overwrite=overwrite,
                preflight_info=preflight_info,
                quiet=quiet,
            )
            return _result(path, started_at, used_connections)
        except UserFacingError as exc:
            if not status.yt_dlp:
                raise
            LOGGER.info("aria2c basarisiz oldu, yt-dlp ile tekrar deneniyor...")
            LOGGER.info("Not: Sorun devam ederse --connections 4 deneyin.")
            path = _download_with_ytdlp(
                url,
                output_dir,
                status,
                fallback_reason=exc,
                output_name=output_name,
                overwrite=overwrite,
                preflight_info=preflight_info,
                quiet=quiet,
            )
            return _result(path, started_at, used_connections)

    if status.yt_dlp:
        path = _download_with_ytdlp(
            url,
            output_dir,
            status,
            output_name=output_name,
            overwrite=overwrite,
            preflight_info=preflight_info,
            quiet=quiet,
        )
        return _result(path, started_at, used_connections)

    if video_type == "m3u8":
        raise UserFacingError(
            ".m3u8 indirmek icin yt-dlp gerekli. "
            "Kurulum: brew install yt-dlp ffmpeg"
        )

    raise UserFacingError(
        "Indirme icin yt-dlp veya aria2c bulunamadi. "
        "Kurulum: brew install yt-dlp aria2 ffmpeg"
    )


def _download_with_aria2(
    url: str,
    output_dir: Path,
    connections: int,
    status: ToolStatus,
    output_name: str | None = None,
    overwrite: bool = False,
    preflight_info: PreflightInfo | None = None,
    quiet: bool = False,
) -> tuple[Path, int]:
    if not status.aria2c:
        raise UserFacingError("aria2c kurulu degil. Kurulum: brew install aria2")

    file_name = _resolve_file_name(url, output_name, preflight_info)
    target = output_dir / file_name
    _skip_if_complete(target, preflight_info, overwrite)
    conn = _effective_connections(connections, preflight_info)
    cmd = _build_aria2_command(url, output_dir, file_name, conn)
    try:
        _run_command(cmd, "aria2c ile indirme basarisiz oldu.", quiet=quiet)
        return target, conn
    except UserFacingError:
        if conn == 1:
            raise
        LOGGER.info("aria2c coklu baglanti basarisiz oldu, tek baglanti deneniyor...")
        _run_command(
            _build_aria2_command(url, output_dir, file_name, 1),
            "aria2c tek baglanti ile de basarisiz oldu.",
            quiet=quiet,
        )
        return target, 1


def _build_aria2_command(
    url: str,
    output_dir: Path,
    file_name: str,
    connections: int,
) -> list[str]:
    return [
        "aria2c",
        "-x",
        str(connections),
        "-s",
        str(connections),
        "-k",
        "1M",
        "--min-split-size=1M",
        "--continue=true",
        "--file-allocation=none",
        "--max-tries=5",
        "--retry-wait=3",
        "--timeout=30",
        "--connect-timeout=15",
        "--dir",
        str(output_dir),
        "--out",
        file_name,
        url,
    ]


def _download_with_ytdlp(
    url: str,
    output_dir: Path,
    status: ToolStatus,
    fallback_reason: UserFacingError | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    preflight_info: PreflightInfo | None = None,
    quiet: bool = False,
) -> Path:
    if not status.yt_dlp:
        if fallback_reason:
            raise UserFacingError(
                f"{fallback_reason} Ayrica yt-dlp kurulu degil."
            ) from fallback_reason
        raise UserFacingError("yt-dlp kurulu degil. Kurulum: brew install yt-dlp")

    file_name = _resolve_file_name(url, output_name, preflight_info)
    if file_name.lower().endswith(".m3u8"):
        file_name = f"{file_name[:-5]}.mp4"
    target = output_dir / file_name
    _skip_if_complete(target, preflight_info, overwrite)
    cmd = [
        "yt-dlp",
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
        str(output_dir),
        "-o",
        file_name,
        url,
    ]
    _run_command(cmd, "yt-dlp ile indirme basarisiz oldu.", quiet=quiet)
    return target


def _resolve_file_name(
    url: str,
    output_name: str | None,
    preflight_info: PreflightInfo | None,
) -> str:
    if output_name:
        from utils import sanitize_filename

        return sanitize_filename(output_name)
    if preflight_info and preflight_info.suggested_filename:
        return preflight_info.suggested_filename
    if video_type_from_url(url) == "m3u8":
        return downloadable_filename_from_url(url)
    return filename_from_url(url)


def _skip_if_complete(
    target: Path,
    preflight_info: PreflightInfo | None,
    overwrite: bool,
) -> None:
    if overwrite:
        return
    expected_size = preflight_info.content_length if preflight_info else None
    if expected_size is not None and target.exists() and target.is_file():
        current_size = target.stat().st_size
        if current_size == expected_size:
            raise UserFacingError(
                f"Dosya zaten mevcut ve tamamlanmis gorunuyor: {target}. "
                "Yeniden indirmek icin --overwrite kullanin."
            )
        if current_size > expected_size:
            raise UserFacingError(
                f"Dosya var ama boyutu beklenenle uyusmuyor: {target}. "
                "Yeniden indirmek icin --overwrite kullanin."
            )
        return
    if existing_complete_file(target, expected_size):
        raise UserFacingError(
            f"Dosya zaten mevcut ve tamamlanmis gorunuyor: {target}. "
            "Yeniden indirmek icin --overwrite kullanin."
        )


def _run_command(cmd: list[str], error_message: str, *, quiet: bool = False) -> None:
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
    except FileNotFoundError as exc:
        raise UserFacingError(f"Komut bulunamadi: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise UserFacingError(f"{error_message} Cikis kodu: {exc.returncode}") from exc


def _effective_connections(
    connections: int,
    preflight_info: PreflightInfo | None,
) -> int:
    if preflight_info and preflight_info.range_supported is False:
        LOGGER.info("Sunucu Range/parcali indirmeyi desteklemiyor; tek baglanti kullaniliyor.")
        return 1
    return clamp_connections(connections)


def _result(path: Path, started_at: float, connections: int) -> DownloadResult:
    elapsed = time.monotonic() - started_at
    size = path.stat().st_size if path.exists() else None
    return DownloadResult(
        path=path,
        elapsed_seconds=elapsed,
        file_size=size,
        connections=connections,
    )


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} sa {minutes} dk {secs} sn"
    if minutes:
        return f"{minutes} dk {secs} sn"
    return f"{secs} sn"


def format_speed(bytes_per_second: float | None) -> str:
    if bytes_per_second is None:
        return "bilinmiyor"
    return f"{format_bytes(int(bytes_per_second))}/s"
