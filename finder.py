from __future__ import annotations

import html
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

from extractor import VideoCandidate, get_video_candidates
from utils import UserFacingError, validate_url

BASE_URL = "https://sosyalhalisaha.com"
DEFAULT_CITY = "İstanbul"
DEFAULT_DISTRICT = "Üsküdar"
DEFAULT_PLACE = "Ufuk Halı Saha"
DEFAULT_FIELD = "Üst Saha"
DEFAULT_TIME = "11:00"


@dataclass(frozen=True)
class FinderDefaults:
    city: str = DEFAULT_CITY
    district: str = DEFAULT_DISTRICT
    place: str = DEFAULT_PLACE
    field: str = DEFAULT_FIELD
    time: str = DEFAULT_TIME
    date: str = ""


@dataclass(frozen=True)
class FinderOption:
    id: int
    name: str


@dataclass(frozen=True)
class MatchSearchQuery:
    city: str
    district: str
    place: str
    date: str
    time: str
    field: str = DEFAULT_FIELD
    city_id: int | None = None
    district_id: int | None = None
    place_id: int | None = None


@dataclass(frozen=True)
class MatchResult:
    url: str
    date: str
    title: str
    place_name: str
    image: str | None
    watch_count: int | None
    score: int


@dataclass(frozen=True)
class MatchSearchResult:
    matches: list[MatchResult]
    preferred_url: str | None
    filter_url: str
    source: str = "http"


class SosyalHaliSahaFinder:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 15) -> None:
        try:
            import requests
        except ImportError as exc:
            raise UserFacingError(
                "Otomatik mac bulma icin requests paketi gerekli. "
                "Kurulum: python3 -m pip install -r requirements.txt"
            ) from exc

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._requests = requests
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._token: str | None = None
        self._cache_ttl = 900.0
        self._option_cache: dict[str, tuple[float, list[FinderOption]]] = {}

    def defaults(self) -> FinderDefaults:
        return FinderDefaults(date=date.today().isoformat())

    def list_cities(self) -> list[FinderOption]:
        return self._cached_options("cities", self._city_options)

    def list_districts(self, city_id: int) -> list[FinderOption]:
        return self._cached_options(
            f"districts:{city_id}",
            lambda: self._district_options(city_id),
        )

    def list_places(self, district_id: int) -> list[FinderOption]:
        return self._cached_options(
            f"places:{district_id}",
            lambda: self._place_options(district_id),
        )

    def list_fields(
        self,
        *,
        city_id: int,
        district_id: int,
        place_id: int,
        date: str,
        time: str,
    ) -> list[FinderOption]:
        result = self.search(
            MatchSearchQuery(
                city="",
                district="",
                place="",
                city_id=city_id,
                district_id=district_id,
                place_id=place_id,
                date=date,
                time=time,
                field="",
            )
        )
        seen: set[str] = set()
        fields: list[FinderOption] = []
        for index, match in enumerate(result.matches, start=1):
            key = normalize(match.title)
            if not key or key in seen:
                continue
            seen.add(key)
            fields.append(FinderOption(id=index, name=match.title))
        return fields

    def search(self, query: MatchSearchQuery) -> MatchSearchResult:
        self._validate_query(query)
        city_id = query.city_id or self._resolve_city(query.city).id
        district_id = query.district_id or self._resolve_district(city_id, query.district).id
        place_id = query.place_id or self._resolve_place(district_id, query.place).id
        filter_key = (
            f"{city_id}_{district_id}_{place_id}_{query.date}_{query.time}_"
        )
        filter_url = f"{self.base_url}/filtre/{filter_key}"

        # The public page initializes the session used by the XHR endpoint.
        self._get(filter_url)
        payload = self._get_json(f"{self.base_url}/xhr/filtre/{filter_key}")
        raw_matches = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(raw_matches, list):
            raise UserFacingError("Mac arama sonucu okunamadi.")

        matches = [
            _match_from_payload(item, query.field)
            for item in raw_matches
            if isinstance(item, dict) and item.get("url")
        ]
        matches.sort(key=lambda item: (-item.score, item.date, item.title))
        preferred = matches[0].url if matches and matches[0].score >= 80 else None
        return MatchSearchResult(
            matches=matches,
            preferred_url=preferred,
            filter_url=filter_url,
        )

    def extract_videos(self, match_url: str) -> list[VideoCandidate]:
        return get_video_candidates(validate_url(match_url))

    def _resolve_city(self, name: str) -> FinderOption:
        return _find_option(self.list_cities(), name, "il")

    def _resolve_district(self, city_id: int, name: str) -> FinderOption:
        return _find_option(self.list_districts(city_id), name, "ilce")

    def _resolve_place(self, district_id: int, name: str) -> FinderOption:
        return _find_option(self.list_places(district_id), name, "tesis")

    def _cached_options(
        self,
        key: str,
        loader: Callable[[], list[FinderOption]],
    ) -> list[FinderOption]:
        cached = self._option_cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl:
            return list(cached[1])
        options = loader()
        self._option_cache[key] = (now, list(options))
        return options

    def _city_options(self) -> list[FinderOption]:
        text = self._get(f"{self.base_url}/")
        options: list[FinderOption] = []
        for value, label in re.findall(
            r'<option\s+value="(\d+)"[^>]*class="dataValue"[^>]*>(.*?)</option>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            options.append(FinderOption(id=int(value), name=_clean_text(label)))
        return options

    def _district_options(self, city_id: int) -> list[FinderOption]:
        data = self._post_filter({"city": city_id, "type": "getdistrict"})
        return _options_from_json(data, "name")

    def _place_options(self, district_id: int) -> list[FinderOption]:
        data = self._post_filter({"district": district_id, "type": "getplace"})
        return _options_from_json(data, "title")

    def _post_filter(self, data: dict[str, object]) -> dict[str, Any]:
        return self._post_filter_once(data, retry=True)

    def _get_json(self, url: str) -> dict[str, Any]:
        response = self.session.get(
            url,
            headers=_ajax_headers(),
            timeout=self.timeout,
        )
        return self._json_response(response)

    def _post_filter_once(
        self,
        data: dict[str, object],
        *,
        retry: bool,
    ) -> dict[str, Any]:
        token = self._ensure_token()
        payload = {"_token": token, **data}
        response = self.session.post(
            f"{self.base_url}/filtre",
            data=payload,
            headers=_ajax_headers(),
            timeout=self.timeout,
        )
        try:
            return self._json_response(response)
        except UserFacingError:
            if not retry:
                raise
            self._token = None
            return self._post_filter_once(data, retry=False)

    def _get(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except self._requests.Timeout as exc:
            raise UserFacingError("Sosyal Hali Saha zaman asimina ugradi.") from exc
        except self._requests.RequestException as exc:
            raise UserFacingError(f"Sosyal Hali Saha sayfasi okunamadi: {exc}") from exc
        self._remember_token(response.text)
        return response.text

    def _json_response(self, response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            data = response.json()
        except self._requests.Timeout as exc:
            raise UserFacingError("Sosyal Hali Saha zaman asimina ugradi.") from exc
        except ValueError as exc:
            raise UserFacingError("Sosyal Hali Saha beklenen JSON cevabini vermedi.") from exc
        except self._requests.RequestException as exc:
            raise UserFacingError(f"Sosyal Hali Saha istegi basarisiz oldu: {exc}") from exc
        if not isinstance(data, dict) or data.get("status") != "success":
            raise UserFacingError("Sosyal Hali Saha arama istegi basarisiz oldu.")
        return data

    def _ensure_token(self) -> str:
        if not self._token:
            self._get(f"{self.base_url}/")
        if not self._token:
            raise UserFacingError("Sosyal Hali Saha token bilgisi alinamadi.")
        return self._token

    def _remember_token(self, text: str) -> None:
        match = re.search(r'<meta\s+name="token"\s+content="([^"]+)"', text)
        if match:
            self._token = match.group(1)

    def _validate_query(self, query: MatchSearchQuery) -> None:
        for label, value in {
            "tarih": query.date,
            "saat": query.time,
        }.items():
            if not str(value).strip():
                raise UserFacingError(f"Lutfen {label} bilgisini girin.")
        if query.city_id is None and not query.city.strip():
            raise UserFacingError("Lutfen il bilgisini girin.")
        if query.district_id is None and not query.district.strip():
            raise UserFacingError("Lutfen ilce bilgisini girin.")
        if query.place_id is None and not query.place.strip():
            raise UserFacingError("Lutfen tesis bilgisini girin.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", query.date):
            raise UserFacingError("Tarih YYYY-AA-GG formatinda olmali.")
        if not re.fullmatch(r"\d{2}:\d{2}", query.time):
            raise UserFacingError("Saat HH:MM formatinda olmali.")


def default_finder() -> SosyalHaliSahaFinder:
    return SosyalHaliSahaFinder()


def _ajax_headers() -> dict[str, str]:
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }


def _options_from_json(data: dict[str, Any], label_key: str) -> list[FinderOption]:
    raw_options = data.get("data")
    if not isinstance(raw_options, list):
        return []
    options: list[FinderOption] = []
    for item in raw_options:
        if not isinstance(item, dict):
            continue
        try:
            options.append(FinderOption(id=int(item["id"]), name=str(item[label_key])))
        except (KeyError, TypeError, ValueError):
            continue
    return options


def _find_option(options: list[FinderOption], wanted: str, label: str) -> FinderOption:
    wanted_key = normalize(wanted)
    for option in options:
        if normalize(option.name) == wanted_key:
            return option
    for option in options:
        if wanted_key in normalize(option.name) or normalize(option.name) in wanted_key:
            return option
    available = ", ".join(option.name for option in options[:8])
    suffix = f" Ornekler: {available}" if available else ""
    raise UserFacingError(f"{wanted} icin {label} bulunamadi.{suffix}")


def _match_from_payload(item: dict[str, Any], wanted_field: str) -> MatchResult:
    url = validate_url(urljoin(BASE_URL, str(item["url"])))
    title = _clean_text(str(item.get("title") or ""))
    place = item.get("place") if isinstance(item.get("place"), dict) else {}
    place_name = _clean_text(str(place.get("name") or ""))
    score = _field_score(title, wanted_field)
    watch_count = item.get("watch_count")
    return MatchResult(
        url=url,
        date=_clean_text(str(item.get("date") or "")),
        title=title,
        place_name=place_name,
        image=str(item.get("image")) if item.get("image") else None,
        watch_count=int(watch_count) if isinstance(watch_count, int) else None,
        score=score,
    )


def _field_score(title: str, wanted_field: str) -> int:
    title_key = normalize(title)
    wanted_key = normalize(wanted_field)
    if not wanted_key:
        return 0
    if title_key == wanted_key:
        return 100
    if wanted_key in title_key:
        return 80
    return 0


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize(value: str) -> str:
    value = value.casefold().replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()
