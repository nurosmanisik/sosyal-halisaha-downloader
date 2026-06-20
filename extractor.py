from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

from utils import UserFacingError, validate_url


VIDEO_URL_PATTERN = re.compile(
    r"""(?P<url>(?:https?:)?//[^'"\s<>]+?\.(?:mp4|m3u8)(?:\?[^'"\s<>]*)?|/[^'"\s<>]+?\.(?:mp4|m3u8)(?:\?[^'"\s<>]*)?)""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VideoCandidate:
    url: str
    source: str = "html"


def fetch_html(url: str, timeout: int = 20) -> str:
    try:
        import requests
    except ImportError as exc:
        raise UserFacingError(
            "Sayfa analizi icin requests paketi gerekli. "
            "Kurulum: python3 -m pip install -r requirements.txt"
        ) from exc

    url = validate_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise UserFacingError("Sayfa zaman asimina ugradi. Baglantiyi kontrol edin.") from exc
    except requests.RequestException as exc:
        raise UserFacingError(f"Sayfa indirilemedi: {exc}") from exc
    return response.text


def extract_video_links(page_url: str, html_text: str) -> list[VideoCandidate]:
    candidates: list[VideoCandidate] = []
    seen: set[str] = set()

    for raw_url in _candidate_strings(html_text):
        normalized = _normalize_video_url(page_url, raw_url)
        if normalized and normalized not in seen:
            candidates.append(VideoCandidate(url=normalized))
            seen.add(normalized)

    return candidates


def get_video_candidates(page_url: str) -> list[VideoCandidate]:
    html_text = fetch_html(page_url)
    candidates = extract_video_links(page_url, html_text)
    if not candidates:
        raise UserFacingError(
            "Sayfada .mp4 veya .m3u8 video linki bulunamadi. "
            "Video tarayicida gorunuyorsa direkt video linkini deneyin."
        )
    return candidates


def _candidate_strings(html_text: str) -> Iterable[str]:
    decoded = html.unescape(html_text)
    decoded_js_urls = decoded.replace("\\/", "/")

    for match in VIDEO_URL_PATTERN.finditer(decoded_js_urls):
        yield match.group("url")

    for quoted in re.findall(
        r"""["']([^"']+\.(?:mp4|m3u8)(?:\?[^"']*)?)["']""",
        decoded_js_urls,
        re.I,
    ):
        yield quoted

    for script_json in _json_like_blocks(decoded):
        for value in _walk_json_values(script_json):
            if isinstance(value, str) and re.search(r"\.(mp4|m3u8)(\?|$)", value, re.I):
                yield value


def _normalize_video_url(page_url: str, raw_url: str) -> str | None:
    cleaned = raw_url.strip().replace("\\/", "/")
    cleaned = cleaned.rstrip("),.;]")
    if cleaned.startswith("//"):
        cleaned = "https:" + cleaned
    absolute = urljoin(page_url, cleaned)
    try:
        return validate_url(absolute)
    except UserFacingError:
        return None


def _json_like_blocks(html_text: str) -> Iterable[object]:
    for block in re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            yield json.loads(block.strip())
        except json.JSONDecodeError:
            continue


def _walk_json_values(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_json_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json_values(item)
    else:
        yield value
