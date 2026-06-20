from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from utils import DEFAULT_OUTPUT_DIR

DEFAULT_HISTORY_FILE = DEFAULT_OUTPUT_DIR / "downloads.jsonl"


@dataclass(frozen=True)
class DownloadHistoryRecord:
    url: str
    path: str
    size: int | None
    elapsed_seconds: float
    average_speed: float | None
    connections: int
    range_supported: bool | None
    created_at: str


def record_download(
    *,
    url: str,
    path: Path,
    size: int | None,
    elapsed_seconds: float,
    average_speed: float | None,
    connections: int,
    range_supported: bool | None,
    history_file: Path = DEFAULT_HISTORY_FILE,
) -> DownloadHistoryRecord:
    record = DownloadHistoryRecord(
        url=url,
        path=str(path),
        size=size,
        elapsed_seconds=elapsed_seconds,
        average_speed=average_speed,
        connections=connections,
        range_supported=range_supported,
        created_at=datetime.now(UTC).isoformat(),
    )
    history_file = history_file.expanduser()
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
    return record


def read_history(
    history_file: Path = DEFAULT_HISTORY_FILE,
    *,
    limit: int = 10,
) -> list[DownloadHistoryRecord]:
    history_file = history_file.expanduser()
    if not history_file.exists():
        return []

    records: list[DownloadHistoryRecord] = []
    with history_file.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                data = json.loads(line)
                records.append(DownloadHistoryRecord(**data))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
    return records[-limit:]


def host_prefers_single_connection(
    url: str,
    history_file: Path = DEFAULT_HISTORY_FILE,
) -> bool:
    host = urlparse(url).netloc
    for record in reversed(read_history(history_file, limit=50)):
        if urlparse(record.url).netloc != host:
            continue
        if record.range_supported is False or record.connections == 1:
            return True
        if record.connections > 1:
            return False
    return False
