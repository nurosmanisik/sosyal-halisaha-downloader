from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from camera import discover_camera_variants
from downloader import (
    check_tools,
)
from extractor import VideoCandidate, get_video_candidates
from finder import FinderOption, MatchResult, MatchSearchQuery, default_finder
from history import read_history
from jobs import DownloadJobManager
from main import _resolve_connections
from preflight import PreflightInfo, fetch_preflight, format_bytes
from utils import (
    DEFAULT_OUTPUT_DIR,
    UserFacingError,
    downloadable_filename_from_url,
    is_direct_video_url,
    validate_url,
    video_type_from_url,
)

app = Flask(__name__)
job_manager = DownloadJobManager()
finder = default_finder()


@app.get("/")
def index():
    return render_template("index.html", default_output=str(DEFAULT_OUTPUT_DIR))


@app.get("/api/tools")
def api_tools():
    status = check_tools()
    return jsonify(
        {
            "yt_dlp": status.yt_dlp,
            "aria2c": status.aria2c,
            "ffmpeg": status.ffmpeg,
        }
    )


@app.get("/api/history")
def api_history():
    limit = _int_value(request.args.get("limit"), default=20)
    return jsonify([record.__dict__ for record in read_history(limit=limit)])


@app.get("/api/finder/defaults")
def api_finder_defaults():
    return jsonify(finder.defaults().__dict__)


@app.get("/api/finder/cities")
def api_finder_cities():
    try:
        return jsonify([_option_payload(option) for option in finder.list_cities()])
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.get("/api/finder/districts")
def api_finder_districts():
    try:
        city_id = _required_int(request.args.get("city_id"), "il")
        return jsonify([_option_payload(option) for option in finder.list_districts(city_id)])
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.get("/api/finder/places")
def api_finder_places():
    try:
        district_id = _required_int(request.args.get("district_id"), "ilce")
        return jsonify([_option_payload(option) for option in finder.list_places(district_id)])
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/finder/fields")
def api_finder_fields():
    try:
        payload = request.get_json(silent=True) or {}
        fields = finder.list_fields(
            city_id=_required_int(payload.get("city_id"), "il"),
            district_id=_required_int(payload.get("district_id"), "ilce"),
            place_id=_required_int(payload.get("place_id"), "tesis"),
            date=str(payload.get("date", "")),
            time=str(payload.get("time", "")),
        )
        return jsonify([_option_payload(option) for option in fields])
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/finder/search")
def api_finder_search():
    try:
        payload = request.get_json(silent=True) or {}
        result = finder.search(
            MatchSearchQuery(
                city=str(payload.get("city", "")),
                district=str(payload.get("district", "")),
                place=str(payload.get("place", "")),
                city_id=_optional_int(payload.get("city_id")),
                district_id=_optional_int(payload.get("district_id")),
                place_id=_optional_int(payload.get("place_id")),
                date=str(payload.get("date", "")),
                time=str(payload.get("time", "")),
                field=str(payload.get("field", "")),
            )
        )
        return jsonify(
            {
                "status": "ok",
                "source": result.source,
                "filter_url": result.filter_url,
                "preferred_url": result.preferred_url,
                "matches": [
                    _match_payload(match, result.preferred_url)
                    for match in result.matches
                ],
                "message": _finder_message(result.preferred_url, len(result.matches)),
            }
        )
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/finder/extract")
def api_finder_extract():
    try:
        payload = request.get_json(silent=True) or {}
        url = validate_url(str(payload.get("match_url", "")))
        skip_preflight = bool(payload.get("no_preflight", False))
        candidates = finder.extract_videos(url)
        if not candidates:
            raise UserFacingError("Mac icin indirilebilir video linki bulunamadi.")
        selected_url = str(payload.get("selected_url") or candidates[0].url)
        preflight = None if skip_preflight else _safe_preflight(selected_url)
        connections = _resolve_connections(
            str(payload.get("connections", "auto")),
            selected_url,
            preflight,
        )
        return jsonify(
            {
                "status": "ok",
                "match_url": url,
                "selected_url": selected_url,
                "candidates": [_candidate_payload(candidate) for candidate in candidates],
                "preflight": _preflight_payload(preflight),
                "connections": connections,
            }
        )
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/dry-run")
def api_dry_run():
    try:
        payload = request.get_json(silent=True) or {}
        url = validate_url(str(payload.get("url", "")))
        discover_cameras = bool(payload.get("discover_cameras", False))
        skip_preflight = bool(payload.get("no_preflight", False))
        candidates = _resolve_candidates(url, discover_cameras=discover_cameras)
        if not candidates:
            raise UserFacingError("Indirilebilir video linki bulunamadi.")
        selected_url = str(payload.get("selected_url") or candidates[0].url)
        preflight = None if skip_preflight else _safe_preflight(selected_url)
        connections = _resolve_connections(
            str(payload.get("connections", "auto")),
            selected_url,
            preflight,
        )
        return jsonify(
            {
                "status": "ok",
                "selected_url": selected_url,
                "candidates": [_candidate_payload(candidate) for candidate in candidates],
                "preflight": _preflight_payload(preflight),
                "connections": connections,
            }
        )
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/download")
def api_download():
    try:
        payload = request.get_json(silent=True) or {}
        url = validate_url(str(payload.get("url", "")))
        output_dir = Path(str(payload.get("output") or DEFAULT_OUTPUT_DIR))
        skip_preflight = bool(payload.get("no_preflight", False))
        preflight = None if skip_preflight else fetch_preflight(url)
        connections = _resolve_connections(
            str(payload.get("connections", "auto")),
            url,
            preflight,
        )
        job = job_manager.start(
            url=url,
            output_dir=output_dir,
            use_ytdlp=bool(payload.get("use_ytdlp", False)),
            use_aria2=bool(payload.get("use_aria2", False)),
            connections=connections,
            output_name=_optional_string(payload.get("output_name")),
            overwrite=bool(payload.get("overwrite", False)),
            preflight_info=preflight,
        )
        return jsonify({"status": "ok", "job_id": job.id})
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.get("/api/jobs")
def api_jobs():
    limit = _int_value(request.args.get("limit"), default=20)
    return jsonify([job_manager.payload(job) for job in job_manager.list_recent(limit)])


@app.get("/api/jobs/<job_id>")
def api_job_status(job_id: str):
    try:
        return jsonify(job_manager.payload(job_manager.get(job_id)))
    except UserFacingError as exc:
        return _error(str(exc), 404)


@app.post("/api/jobs/<job_id>/pause")
def api_job_pause(job_id: str):
    try:
        return jsonify(job_manager.payload(job_manager.pause(job_id)))
    except UserFacingError as exc:
        return _error(str(exc), 404)


@app.post("/api/jobs/<job_id>/resume")
def api_job_resume(job_id: str):
    try:
        return jsonify(job_manager.payload(job_manager.resume(job_id)))
    except UserFacingError as exc:
        return _error(str(exc), 400)


@app.post("/api/jobs/<job_id>/cancel")
def api_job_cancel(job_id: str):
    try:
        return jsonify(job_manager.payload(job_manager.cancel(job_id)))
    except UserFacingError as exc:
        return _error(str(exc), 404)


@app.post("/api/jobs/<job_id>/reveal")
def api_job_reveal(job_id: str):
    try:
        job = job_manager.get(job_id)
        if job.output_path is None or not job.output_path.exists():
            raise UserFacingError("Dosya henuz bulunamiyor.")
        if platform.system() != "Darwin":
            raise UserFacingError("Klasorde gosterme ozelligi sadece macOS icin desteklenir.")
        subprocess.run(["open", "-R", str(job.output_path)], check=False)
        return jsonify({"status": "ok"})
    except UserFacingError as exc:
        return _error(str(exc), 404)


def _resolve_candidates(url: str, *, discover_cameras: bool) -> list[VideoCandidate]:
    if is_direct_video_url(url):
        if discover_cameras and video_type_from_url(url) == "mp4":
            variants = discover_camera_variants(url)
            if variants:
                return [
                    VideoCandidate(url=variant.url, source="camera-discovery")
                    for variant in variants
                ]
        return [VideoCandidate(url=url, source="direct")]
    return get_video_candidates(url)


def _safe_preflight(url: str) -> PreflightInfo | None:
    try:
        return fetch_preflight(url)
    except UserFacingError:
        return None


def _candidate_payload(candidate: VideoCandidate) -> dict[str, str]:
    return {
        "url": candidate.url,
        "source": candidate.source,
        "type": video_type_from_url(candidate.url),
        "filename": downloadable_filename_from_url(candidate.url),
    }


def _match_payload(match: MatchResult, preferred_url: str | None) -> dict[str, object]:
    return {
        "url": match.url,
        "date": match.date,
        "title": match.title,
        "place_name": match.place_name,
        "image": match.image,
        "watch_count": match.watch_count,
        "score": match.score,
        "preferred": match.url == preferred_url,
    }


def _option_payload(option: FinderOption) -> dict[str, object]:
    return {"id": option.id, "name": option.name}


def _finder_message(preferred_url: str | None, count: int) -> str:
    if preferred_url:
        return "Ust Saha eslesmesi bulundu."
    if count:
        return "Maclar bulundu ama Ust Saha ile net eslesme yok."
    return "Bu tarih ve saatte mac bulunamadi."


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
        "size_text": format_bytes(info.content_length),
    }


def _error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"status": "error", "error": message}), status_code


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_value(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _required_int(value: object, label: str) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        raise UserFacingError(f"Lutfen gecerli {label} secimi yapin.")
    return parsed


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
