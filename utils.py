from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

DEFAULT_OUTPUT_DIR = Path("~/Downloads/SosyalHaliSaha").expanduser()
VIDEO_EXTENSIONS = (".mp4", ".m3u8")


class UserFacingError(Exception):
    """Expected error that can be shown without a traceback."""


def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UserFacingError("Lutfen gecerli bir http/https URL girin.")
    return parsed.geturl()


def is_direct_video_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(VIDEO_EXTENSIONS)


def video_type_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".mp4"):
        return "mp4"
    if path.endswith(".m3u8"):
        return "m3u8"
    return "unknown"


def clamp_connections(value: int, minimum: int = 1, maximum: int = 32) -> int:
    return max(minimum, min(value, maximum))


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def sanitize_filename(value: str, default: str = "sosyal-halisaha-video") -> str:
    value = unquote(value).strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[\x00-\x1f\x7f]+", "", value)
    value = re.sub(r"\s+(\.[^.]+)$", r"\1", value)
    value = value.strip(" .-_")
    return value or default


def filename_from_url(url: str, fallback: str = "sosyal-halisaha-video.mp4") -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    safe_name = sanitize_filename(name, default=fallback)
    if "." not in safe_name and fallback:
        return fallback
    return safe_name


def downloadable_filename_from_url(url: str) -> str:
    file_name = filename_from_url(url)
    if file_name.lower().endswith(".m3u8"):
        return f"{file_name[:-5]}.mp4"
    return file_name
