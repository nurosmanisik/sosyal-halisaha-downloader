from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from preflight import PreflightInfo, fetch_preflight
from utils import UserFacingError, validate_url


def discover_camera_variants(url: str, timeout: int = 5) -> list[PreflightInfo]:
    candidates = _camera_variant_urls(validate_url(url))
    discovered: list[PreflightInfo] = []

    with ThreadPoolExecutor(max_workers=min(6, len(candidates))) as executor:
        futures = {
            executor.submit(fetch_preflight, candidate, timeout): candidate
            for candidate in candidates
        }
        for future in as_completed(futures):
            try:
                discovered.append(future.result())
            except UserFacingError:
                continue

    return sorted(discovered, key=lambda item: item.url)


def _camera_variant_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    match = re.search(r"(?P<prefix>\.)\d+-\d+\.mp4$", parsed.path)
    if not match:
        return [url]

    prefix_end = match.start("prefix") + 1
    path_prefix = parsed.path[:prefix_end]
    variants: list[str] = []
    for first in range(1, 4):
        for second in range(1, 4):
            variant_path = f"{path_prefix}{first}-{second}.mp4"
            variants.append(parsed._replace(path=variant_path).geturl())
    return variants
