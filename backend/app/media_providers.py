"""Search providers for external prototype B-roll.

The providers return metadata only.  Assets are downloaded later into a task
directory, verified there, and never rendered from a remote URL.
"""

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Literal, Protocol

import requests

from .config import Settings
from .schemas import ManualMediaCandidateInput, MediaCandidate


class MediaProviderError(RuntimeError):
    """A recoverable external-media search or download configuration error."""


MediaKind = Literal["external_image", "external_video"]


class ExternalMediaProvider(Protocol):
    name: str

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]: ...


def _candidate_id(provider: str, query: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{provider}\0{query}\0{source_url}".encode("utf-8")).hexdigest()[:20]
    return f"candidate_{provider}_{digest}"


def _plain_metadata(value: object, default: str) -> str:
    if not isinstance(value, dict):
        return default
    raw = value.get("value")
    if not isinstance(raw, str):
        return default
    text = re.sub(r"<[^>]*>", "", html.unescape(raw)).strip()
    return text or default


class MockMediaProvider:
    """Keeps the default Mock pipeline fully offline and deterministic."""

    name = "mock"

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        del query, asset_kind
        return []


class ManualMediaProvider:
    """Signals that the reviewer should add an explicit candidate URL."""

    name = "manual"

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        del query, asset_kind
        raise MediaProviderError(
            "MEDIA_PROVIDER=manual has no automatic search. Add a reviewed source URL in the media review panel."
        )


class WikimediaCommonsProvider:
    """No-key Wikimedia Commons search, suitable for effect-prototype B-roll."""

    name = "wikimedia_commons"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, timeout_seconds: int = 20, session: requests.Session | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        try:
            response = self.session.get(
                self.endpoint,
                params={
                    "action": "query", "format": "json", "generator": "search", "gsrsearch": query,
                    "gsrnamespace": 6, "gsrlimit": 18, "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 960,
                },
                headers={"User-Agent": "semantic-video-animation-agent/0.1 prototype contact"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {}).values()
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise MediaProviderError(f"Wikimedia Commons search failed: {exc}") from exc

        candidates: list[MediaCandidate] = []
        for page in pages:
            info_items = page.get("imageinfo") if isinstance(page, dict) else None
            if not isinstance(info_items, list) or not info_items or not isinstance(info_items[0], dict):
                continue
            info = info_items[0]
            mime_type = str(info.get("mime", ""))
            kind: MediaKind | None = "external_image" if mime_type.startswith("image/") else "external_video" if mime_type.startswith("video/") else None
            if kind != asset_kind:
                continue
            # A generated thumbnail is preferred for images; it is much safer
            # to download and render than an original multi-megabyte photograph.
            source_url = info.get("thumburl") if kind == "external_image" else info.get("url")
            if not isinstance(source_url, str) or not source_url.startswith("https://"):
                continue
            metadata = info.get("extmetadata", {})
            license_name = _plain_metadata(metadata.get("LicenseShortName"), "Unverified Wikimedia Commons license")
            author = _plain_metadata(metadata.get("Artist"), "Wikimedia Commons contributor")
            title = str(page.get("title", "Wikimedia Commons media"))[5:]
            candidates.append(MediaCandidate(
                id=_candidate_id(self.name, query, source_url), provider=self.name, query=query, asset_kind=kind,
                source_url=source_url, source_page_url=info.get("descriptionurl"), title=title[:240] or "Wikimedia Commons media",
                author_or_provider=author[:160], license=license_name[:240], mime_type=mime_type,
                width=info.get("thumbwidth") or info.get("width"), height=info.get("thumbheight") or info.get("height"),
            ))
        return candidates


class OpenLibraryBooksProvider:
    """Resolve exact book entities through Open Library's no-key APIs."""

    name = "open_library"
    endpoint = "https://openlibrary.org/search.json"
    cover_endpoint = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

    def __init__(self, timeout_seconds: int = 20, session: requests.Session | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @staticmethod
    def _search_fields(query: str) -> tuple[str, str | None]:
        compact = re.sub(r"\s+", " ", query).strip()
        if "psychology and life" in compact.lower():
            return "Psychology and Life", "Richard J. Gerrig"
        match = re.match(r"(.+?)\s+(?:by|作者[:：]?)\s*(.+)$", compact, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return compact, None

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        if asset_kind != "external_image":
            return []
        title, author = self._search_fields(query)
        params = {"title": title, "fields": "key,title,author_name,cover_i", "limit": 12}
        if author:
            params["author"] = author
        try:
            response = self.session.get(
                self.endpoint,
                params=params,
                headers={"User-Agent": "semantic-video-animation-agent/0.1 prototype contact"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            documents = response.json().get("docs", [])
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise MediaProviderError(f"Open Library book search failed: {exc}") from exc

        candidates: list[MediaCandidate] = []
        for document in documents if isinstance(documents, list) else []:
            if not isinstance(document, dict) or not isinstance(document.get("cover_i"), int):
                continue
            work_key = document.get("key")
            if not isinstance(work_key, str) or not work_key.startswith("/"):
                continue
            book_title = str(document.get("title") or title).strip()
            authors = document.get("author_name")
            author_text = ", ".join(str(value) for value in authors) if isinstance(authors, list) else "Open Library"
            cover_url = self.cover_endpoint.format(cover_id=document["cover_i"])
            display_title = f"{book_title} — {author_text}"[:240]
            candidates.append(MediaCandidate(
                id=_candidate_id(self.name, query, cover_url), provider=self.name, query=query,
                asset_kind="external_image", source_url=cover_url,
                source_page_url=f"https://openlibrary.org{work_key}", title=display_title,
                author_or_provider=author_text[:160],
                license="Open Library cover source; image rights require human review",
                mime_type="image/jpeg",
            ))
        return candidates


class KnowledgeMediaProvider:
    """Use exact book lookup for marked entities and Commons for other B-roll."""

    name = "knowledge"

    def __init__(
        self,
        timeout_seconds: int = 20,
        *,
        book_provider: ExternalMediaProvider | None = None,
        commons_provider: ExternalMediaProvider | None = None,
    ) -> None:
        self.book_provider = book_provider or OpenLibraryBooksProvider(timeout_seconds)
        self.commons_provider = commons_provider or WikimediaCommonsProvider(timeout_seconds)

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        if query.lower().startswith("book:"):
            return self.book_provider.search(query.split(":", 1)[1].strip(), asset_kind)
        return self.commons_provider.search(query, asset_kind)


class PexelsProvider:
    """Optional keyed photo/video provider.  It is never contacted without a key."""

    name = "pexels"

    def __init__(self, api_key: str | None, timeout_seconds: int = 20, session: requests.Session | None = None) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def search(self, query: str, asset_kind: MediaKind) -> list[MediaCandidate]:
        if not self.api_key:
            raise MediaProviderError(
                "PEXELS_API_KEY is required for MEDIA_PROVIDER=pexels. Set it, switch to MEDIA_PROVIDER=wikimedia_commons, or add a manual candidate URL."
            )
        endpoint = "https://api.pexels.com/v1/search" if asset_kind == "external_image" else "https://api.pexels.com/videos/search"
        try:
            response = self.session.get(
                endpoint, params={"query": query, "per_page": 12}, headers={"Authorization": self.api_key},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            items = response.json().get("photos" if asset_kind == "external_image" else "videos", [])
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise MediaProviderError(f"Pexels search failed: {exc}") from exc

        candidates: list[MediaCandidate] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if asset_kind == "external_image":
                source_url = item.get("src", {}).get("large2x")
                mime_type = "image/jpeg"
            else:
                files = item.get("video_files", [])
                usable = next((file for file in files if isinstance(file, dict) and file.get("file_type") == "video/mp4"), None)
                source_url = usable.get("link") if usable else None
                mime_type = "video/mp4"
            if not isinstance(source_url, str) or not source_url.startswith("https://"):
                continue
            author = str(item.get("photographer") or item.get("user", {}).get("name") or "Pexels contributor")
            candidates.append(MediaCandidate(
                id=_candidate_id(self.name, query, source_url), provider=self.name, query=query, asset_kind=asset_kind,
                source_url=source_url, source_page_url=item.get("url"), title=f"Pexels: {query}", author_or_provider=author[:160],
                license="Pexels source; commercial rights require human review", mime_type=mime_type,
                width=item.get("width"), height=item.get("height"), duration_seconds=item.get("duration"),
            ))
        return candidates


def get_media_provider_by_name(name: str, settings: Settings) -> ExternalMediaProvider:
    if name == "mock":
        return MockMediaProvider()
    if name == "manual":
        return ManualMediaProvider()
    if name == "wikimedia_commons":
        return WikimediaCommonsProvider(settings.media_search_timeout_seconds)
    if name == "knowledge":
        return KnowledgeMediaProvider(settings.media_search_timeout_seconds)
    if name == "pexels":
        return PexelsProvider(settings.pexels_api_key, settings.media_search_timeout_seconds)
    raise MediaProviderError("MEDIA_PROVIDER must be mock, manual, knowledge, wikimedia_commons, or pexels")


def get_media_provider(settings: Settings) -> ExternalMediaProvider:
    return get_media_provider_by_name(settings.media_provider, settings)


def manual_candidate(request: ManualMediaCandidateInput) -> MediaCandidate:
    return MediaCandidate(
        id=_candidate_id("manual", request.query, request.source_url), provider="manual", query=request.query,
        asset_kind=request.asset_kind, source_url=request.source_url, source_page_url=request.source_page_url,
        title=request.title, author_or_provider=request.author_or_provider, license=request.license,
        mime_type=request.mime_type, width=request.width, height=request.height, duration_seconds=request.duration_seconds,
    )


def candidate_manifest_path(task_dir: Path) -> Path:
    return task_dir / "media_candidates.json"


def load_candidates(task_dir: Path) -> list[MediaCandidate]:
    path = candidate_manifest_path(task_dir)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [MediaCandidate.model_validate(item) for item in payload]
    except (OSError, ValueError, TypeError) as exc:
        raise MediaProviderError(f"Task media candidate manifest is invalid: {exc}") from exc


def save_candidates(task_dir: Path, candidates: list[MediaCandidate]) -> list[MediaCandidate]:
    existing = {candidate.id: candidate for candidate in load_candidates(task_dir)}
    existing.update({candidate.id: candidate for candidate in candidates})
    ordered = sorted(existing.values(), key=lambda candidate: (candidate.query, candidate.id))
    candidate_manifest_path(task_dir).write_text(
        json.dumps([candidate.model_dump() for candidate in ordered], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return ordered
