from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from camera import discover_camera_variants
from downloader import (
    check_tools,
    download_video,
    format_duration,
    format_speed,
    print_tool_status,
)
from extractor import VideoCandidate, get_video_candidates
from history import host_prefers_single_connection, read_history, record_download
from preflight import (
    PreflightInfo,
    fetch_preflight,
    format_bytes,
)
from utils import (
    DEFAULT_OUTPUT_DIR,
    UserFacingError,
    clamp_connections,
    downloadable_filename_from_url,
    is_direct_video_url,
    validate_url,
    video_type_from_url,
)

LOGGER = logging.getLogger("sosyal_halisaha_downloader")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sosyal Hali Saha mac videolarini indiren CLI araci."
    )
    parser.add_argument("url", nargs="?", help="Mac detay linki veya direkt video linki")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Indirme klasoru (varsayilan: ~/Downloads/SosyalHaliSaha)",
    )
    parser.add_argument("--use-ytdlp", action="store_true", help="yt-dlp kullan")
    parser.add_argument("--use-aria2", action="store_true", help="aria2c kullan")
    parser.add_argument(
        "--connections",
        default="auto",
        help="aria2c baglanti sayisi veya auto (varsayilan: auto, ust sinir: 32)",
    )
    parser.add_argument(
        "--discover-cameras",
        action="store_true",
        help="Direkt mp4 linkinden yakin kamera acisi varyantlarini ara",
    )
    parser.add_argument("--overwrite", action="store_true", help="Mevcut dosyayi indir")
    parser.add_argument("--output-name", help="Cikti dosya adi")
    parser.add_argument(
        "--select",
        type=int,
        help="Birden fazla link varsa interaktif sormadan secilecek numara",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Indirme oncesi HEAD kontrolunu atla",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Indirme yapmadan bulunan video linklerini goster",
    )
    parser.add_argument("--history", action="store_true", help="Son indirmeleri goster")
    parser.add_argument("--json", action="store_true", help="Sonucu JSON olarak yaz")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Gelisme ve hata ayiklama icin ayrintili log yaz",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        if args.history:
            _print_history(json_output=args.json)
            return 0

        if not args.url:
            raise UserFacingError("URL gerekli. Yardim icin --help kullanin.")

        url = validate_url(args.url)
        if not args.json:
            print_tool_status(check_tools())
        candidates = _resolve_candidates(
            url,
            discover_cameras=args.discover_cameras,
            json_output=args.json,
        )
        selected = _choose_candidate(
            candidates,
            dry_run=args.dry_run,
            selected_index=args.select,
            json_output=args.json,
        )
        preflight_info = None
        if not args.no_preflight:
            preflight_info = _run_preflight(
                selected.url,
                fail_hard=not args.dry_run,
                quiet=args.json,
            )
        connections = _resolve_connections(args.connections, selected.url, preflight_info)

        if args.dry_run:
            if args.json:
                _print_json(
                    {
                        "selected_url": selected.url,
                        "candidates": [_candidate_payload(candidate) for candidate in candidates],
                        "preflight": _preflight_payload(preflight_info),
                        "connections": connections,
                    }
                )
            elif preflight_info:
                _print_preflight(preflight_info)
            return 0

        result = download_video(
            selected.url,
            args.output,
            use_ytdlp=args.use_ytdlp,
            use_aria2=args.use_aria2,
            connections=connections,
            output_name=args.output_name,
            overwrite=args.overwrite,
            preflight_info=preflight_info,
            quiet=args.json,
        )
        record_download(
            url=selected.url,
            path=result.path,
            size=result.file_size,
            elapsed_seconds=result.elapsed_seconds,
            average_speed=result.average_speed,
            connections=result.connections,
            range_supported=preflight_info.range_supported if preflight_info else None,
        )
        if args.json:
            _print_json(
                {
                    "status": "ok",
                    "url": selected.url,
                    "path": str(result.path),
                    "elapsed_seconds": result.elapsed_seconds,
                    "duration": format_duration(result.elapsed_seconds),
                    "size": result.file_size,
                    "size_text": format_bytes(result.file_size),
                    "average_speed": result.average_speed,
                    "average_speed_text": format_speed(result.average_speed),
                    "connections": result.connections,
                    "range_supported": preflight_info.range_supported if preflight_info else None,
                }
            )
        else:
            print(f"Indirme tamamlandi. Konum: {result.path}")
            print(f"Süre: {format_duration(result.elapsed_seconds)}")
            print(f"Boyut: {format_bytes(result.file_size)}")
            print(f"Ortalama hiz: {format_speed(result.average_speed)}")
        return 0
    except UserFacingError as exc:
        if args.debug:
            LOGGER.exception("Hata")
        if getattr(args, "json", False):
            _print_json({"status": "error", "error": str(exc)})
        else:
            print(f"Hata: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nIslem iptal edildi. Yarım indirme dosyasi resume icin korunur.")
        return 130


def _resolve_candidates(
    url: str,
    *,
    discover_cameras: bool,
    json_output: bool,
) -> list[VideoCandidate]:
    if is_direct_video_url(url):
        if discover_cameras and video_type_from_url(url) == "mp4":
            variants = discover_camera_variants(url)
            if variants:
                return [
                    VideoCandidate(url=variant.url, source="camera-discovery")
                    for variant in variants
                ]
        return [VideoCandidate(url=url, source="direct")]

    if not json_output:
        print("Mac detay sayfasi analiz ediliyor...")
    return get_video_candidates(url)


def _choose_candidate(
    candidates: list[VideoCandidate],
    *,
    dry_run: bool,
    selected_index: int | None,
    json_output: bool,
) -> VideoCandidate:
    if not candidates:
        raise UserFacingError("Indirilebilir video linki bulunamadi.")

    candidates = sorted(candidates, key=_candidate_sort_key)
    if not json_output:
        print("Bulunan video linkleri:")
        for index, candidate in enumerate(candidates, start=1):
            video_type = video_type_from_url(candidate.url)
            file_name = downloadable_filename_from_url(candidate.url)
            print(f"{index}. [{video_type}] {file_name}")
            print(f"   {candidate.url}")

    if selected_index is not None:
        if 1 <= selected_index <= len(candidates):
            return candidates[selected_index - 1]
        raise UserFacingError(
            f"--select degeri 1 ile {len(candidates)} arasinda olmali."
        )

    if dry_run or len(candidates) == 1:
        return candidates[0]

    while True:
        choice = input(f"Indirilecek videoyu secin [1-{len(candidates)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Gecersiz secim. Lutfen listedeki numaralardan birini girin.")


def _candidate_sort_key(candidate: VideoCandidate) -> tuple[int, str]:
    video_type = video_type_from_url(candidate.url)
    priority = 0 if video_type == "mp4" else 1
    return priority, candidate.url


def _run_preflight(
    url: str,
    *,
    fail_hard: bool,
    quiet: bool = False,
) -> PreflightInfo | None:
    try:
        return fetch_preflight(url)
    except UserFacingError as exc:
        if fail_hard:
            raise
        if not quiet:
            print(f"Preflight uyarisi: {exc}")
        return None


def _print_preflight(info: PreflightInfo) -> None:
    print("Preflight bilgisi:")
    print(f"- HTTP durum: {info.status_code or 'bilinmiyor'}")
    print(f"- Boyut: {format_bytes(info.content_length)}")
    print(f"- Icerik turu: {info.content_type or 'bilinmiyor'}")
    print(f"- Resume destegi: {'var' if info.supports_resume else 'bilinmiyor/yok'}")
    if info.range_supported is not None:
        print(f"- Parcali indirme: {'var' if info.range_supported else 'yok'}")
    if info.suggested_filename:
        print(f"- Sunucu dosya adi: {info.suggested_filename}")


def _resolve_connections(
    value: str,
    url: str,
    preflight_info: PreflightInfo | None,
) -> int:
    if value.lower() != "auto":
        if not value.isdigit():
            raise UserFacingError("--connections sayi veya auto olmali.")
        return clamp_connections(int(value))

    size = preflight_info.content_length if preflight_info else None
    if preflight_info and preflight_info.range_supported is False:
        return 1
    if host_prefers_single_connection(url):
        return 1
    if size is not None and size < 100 * 1024 * 1024:
        return 8
    return 16


def _candidate_payload(candidate: VideoCandidate) -> dict[str, str]:
    return {
        "url": candidate.url,
        "source": candidate.source,
        "type": video_type_from_url(candidate.url),
        "filename": downloadable_filename_from_url(candidate.url),
    }


def _preflight_payload(info: PreflightInfo | None) -> dict[str, object] | None:
    if info is None:
        return None
    return {
        "url": info.url,
        "status_code": info.status_code,
        "content_length": info.content_length,
        "content_type": info.content_type,
        "accept_ranges": info.accept_ranges,
        "range_supported": info.range_supported,
        "suggested_filename": info.suggested_filename,
    }


def _print_json(payload: dict[str, object] | list[object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_history(*, json_output: bool) -> None:
    records = read_history(limit=20)
    if json_output:
        _print_json([record.__dict__ for record in records])
        return

    if not records:
        print("Indirme gecmisi yok.")
        return

    print("Son indirmeler:")
    for record in records:
        print(f"- {record.created_at} | {format_bytes(record.size)} | {format_duration(record.elapsed_seconds)}")
        print(f"  {record.path}")
        print(f"  {record.url}")


if __name__ == "__main__":
    raise SystemExit(main())
