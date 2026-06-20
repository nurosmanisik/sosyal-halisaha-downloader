from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from email.parser import Parser
from pathlib import Path
import re
from urllib.parse import unquote

from utils import UserFacingError, sanitize_filename, validate_url


@dataclass(frozen=True)
class PreflightInfo:
    url: str
    status_code: int | None = None
    content_length: int | None = None
    content_type: str | None = None
    accept_ranges: bool = False
    suggested_filename: str | None = None
    range_supported: bool | None = None

    @property
    def supports_resume(self) -> bool:
        return self.accept_ranges


def fetch_preflight(url: str, timeout: int = 15) -> PreflightInfo:
    try:
        import requests
    except ImportError as exc:
        raise UserFacingError(
            "Preflight kontrolu icin requests paketi gerekli. "
            "Kurulum: .venv/bin/python -m pip install -r requirements.txt"
        ) from exc

    url = validate_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        )
    }
    try:
        response = requests.head(
            url,
            headers=headers,
            allow_redirects=True,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise UserFacingError("Baglanti zaman asimina ugradi.") from exc
    except requests.RequestException as exc:
        raise UserFacingError(f"Baglanti kontrolu basarisiz oldu: {exc}") from exc

    _raise_for_status(response.status_code)
    content_length = _parse_content_length(response.headers.get("Content-Length"))
    range_supported = test_range_support(response.url, timeout=timeout)
    return PreflightInfo(
        url=response.url,
        status_code=response.status_code,
        content_length=content_length,
        content_type=response.headers.get("Content-Type"),
        accept_ranges=response.headers.get("Accept-Ranges", "").lower() == "bytes",
        suggested_filename=filename_from_content_disposition(
            response.headers.get("Content-Disposition")
        ),
        range_supported=range_supported,
    )


def test_range_support(url: str, timeout: int = 10) -> bool | None:
    try:
        import requests
    except ImportError:
        return None

    headers = {
        "Range": "bytes=0-0",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        ),
    }
    try:
        response = requests.get(
            validate_url(url),
            headers=headers,
            allow_redirects=True,
            stream=True,
            timeout=timeout,
        )
        response.close()
    except requests.RequestException:
        return None

    if response.status_code == 206:
        return True
    if response.status_code == 200:
        return False
    return None


def filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None

    encoded_match = re.search(r"filename\*=(?:\"?)([^;\"]+)", value, re.IGNORECASE)
    if encoded_match:
        encoded = encoded_match.group(1)
        if "''" in encoded:
            encoded = encoded.split("''", 1)[1]
        return sanitize_filename(unquote(encoded))

    message: Message = Parser().parsestr(f"Content-Disposition: {value}\n")
    filename = message.get_param("filename*", header="content-disposition")
    if filename:
        filename = str(filename)
    else:
        filename = message.get_param("filename", header="content-disposition")

    if not filename:
        return None
    return sanitize_filename(unquote(str(filename)))


def format_bytes(value: int | None) -> str:
    if value is None:
        return "bilinmiyor"

    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def existing_complete_file(path: Path, expected_size: int | None) -> bool:
    if not path.exists() or not path.is_file():
        return False
    if expected_size is None:
        return path.stat().st_size > 0
    return path.stat().st_size == expected_size


def _parse_content_length(value: str | None) -> int | None:
    if not value or not value.isdigit():
        return None
    return int(value)


def _raise_for_status(status_code: int) -> None:
    if status_code in {401, 403}:
        raise UserFacingError(
            "Erisim reddedildi. Link tarayicida acilmiyor olabilir veya oturum gerektiriyor."
        )
    if status_code == 404:
        raise UserFacingError("Video linki bulunamadi veya suresi dolmus olabilir.")
    if status_code >= 400:
        raise UserFacingError(f"Sunucu hata dondurdu. HTTP durum kodu: {status_code}")
