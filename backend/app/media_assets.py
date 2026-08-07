"""Task-local preparation and provenance recording for prototype media visuals.

External files are visual B-roll only.  They are deliberately not treated as a
source of factual information and every admitted file stays inside its task
directory with a recorded source URL and SHA-256 digest.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from pydantic import ValidationError

from .config import SETTINGS
from .media_providers import ExternalMediaProvider, MediaProviderError, get_media_provider_by_name, load_candidates, save_candidates
from .schemas import AnimationPlan, MediaAssetAudit, MediaCandidate


_PROTOTYPE_USAGE = (
    "External-material prototype only. It may be resized, cropped, composited, and overlaid for effect validation, "
    "but it is not cleared for commercial publication and requires human rights/source review."
)
_GENERATED_USAGE = (
    "Original task-local information graphic for prototype rendering. It may be resized, cropped, composited, and overlaid."
)
_EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/ogg": ".ogv",
}


def _escape_xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fallback_svg(title: str, theme: str, accent: str) -> str:
    """Make a designed original concept card, not a book-cover placeholder."""
    label = _escape_xml(title[:22])
    theme_label = _escape_xml(theme.upper())
    icon = {
        "book": "▤", "factory": "▥", "product": "◇", "money": "¥", "learning": "↗",
        "people": "●●", "place": "⌖", "concept": "✦", "wellbeing": "◌", "business": "▦", "technology": "⌘",
    }.get(theme, "✦")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="980" viewBox="0 0 720 980">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111827"/><stop offset="1" stop-color="#263650"/></linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{accent}"/><stop offset="1" stop-color="#FFFFFF" stop-opacity=".30"/></linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000" flood-opacity=".35"/></filter>
</defs>
<rect width="720" height="980" rx="54" fill="url(#bg)"/>
<circle cx="612" cy="118" r="166" fill="{accent}" opacity=".18"/><circle cx="72" cy="884" r="210" fill="{accent}" opacity=".12"/>
<g filter="url(#shadow)"><rect x="58" y="60" width="604" height="860" rx="40" fill="#0B1220" fill-opacity=".66" stroke="#FFFFFF" stroke-opacity=".14" stroke-width="2"/></g>
<rect x="96" y="105" width="218" height="54" rx="27" fill="{accent}"/><text x="205" y="141" text-anchor="middle" fill="#101827" font-family="Microsoft YaHei, sans-serif" font-size="25" font-weight="800">KNOWLEDGE B-ROLL</text>
<text x="96" y="298" fill="url(#accent)" font-family="Microsoft YaHei, sans-serif" font-size="146" font-weight="800">{icon}</text>
<text x="96" y="380" fill="#D3DDF0" font-family="Arial, sans-serif" font-size="28" font-weight="700" letter-spacing="5">{theme_label}</text>
<text x="96" y="484" fill="#FFFFFF" font-family="Microsoft YaHei, sans-serif" font-size="52" font-weight="800">{label}</text>
<path d="M96 560h522" stroke="#FFFFFF" stroke-opacity=".18" stroke-width="2"/>
<g fill="none" stroke="{accent}" stroke-width="16" stroke-linecap="round"><path d="M112 655h202"/><path d="M112 725h396" opacity=".65"/><path d="M112 795h286" opacity=".32"/></g>
<circle cx="560" cy="720" r="70" fill="{accent}" opacity=".18"/><path d="M530 720h60M560 690v60" stroke="#FFFFFF" stroke-width="10" stroke-linecap="round"/>
<text x="96" y="872" fill="#AAB8D0" font-family="Microsoft YaHei, sans-serif" font-size="25">原创概念信息图 · 无外部素材时回退</text>
</svg>'''


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_path(task_dir: Path, asset_id: str, mime_type: str) -> Path:
    suffix = _EXTENSIONS.get(mime_type.lower(), ".bin")
    return task_dir / "media-assets" / f"{asset_id}{suffix}"


def _audit_matches_local_file(task_dir: Path, audit: MediaAssetAudit) -> bool:
    path = (task_dir / audit.local_path).resolve()
    return task_dir in path.parents and path.is_file() and _sha256(path) == audit.sha256


def _load_existing_audits(task_dir: Path) -> dict[str, MediaAssetAudit]:
    """Load only structurally valid prior render output; stale entries are reconciled below."""
    path = task_dir / "media_assets.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        audits = [MediaAssetAudit.model_validate(item) for item in payload]
    except (OSError, json.JSONDecodeError, ValidationError, TypeError):
        return {}
    if len({audit.asset_id for audit in audits}) != len(audits):
        return {}
    return {audit.asset_id: audit for audit in audits}


def _download_candidate(candidate: MediaCandidate, destination: Path, max_download_bytes: int) -> None:
    try:
        response = requests.get(
            candidate.source_url, stream=True, timeout=SETTINGS.media_search_timeout_seconds,
            headers={"User-Agent": "semantic-video-animation-agent/0.1 prototype contact"},
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        expected_prefix = "image/" if candidate.asset_kind == "external_image" else "video/"
        if content_type and not content_type.startswith(expected_prefix):
            raise MediaProviderError(f"Downloaded media content type {content_type!r} does not match {candidate.asset_kind}")
        total = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_download_bytes:
                    raise MediaProviderError("External media exceeds MEDIA_MAX_DOWNLOAD_MB")
                output.write(chunk)
    except (OSError, requests.RequestException) as exc:
        destination.unlink(missing_ok=True)
        raise MediaProviderError(f"External media download failed: {exc}") from exc
    if not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise MediaProviderError("External media download produced an empty file")


def _choose_candidate(candidates: list[MediaCandidate]) -> MediaCandidate | None:
    if not candidates:
        return None

    def score(candidate: MediaCandidate) -> tuple[float, int, str]:
        if candidate.width and candidate.height:
            ratio = candidate.height / candidate.width
            portrait_score = 3.0 - abs(ratio - 1.35)
            pixels = candidate.width * candidate.height
        else:
            portrait_score, pixels = 0.0, 0
        return portrait_score, pixels, candidate.id

    return max(candidates, key=score)


def _make_audit(
    task_dir: Path, animation, path: Path, *, asset_kind: str, provider: str, query: str,
    source_url: str | None, source_page_url: str | None, author_or_provider: str, license: str,
    candidate_id: str | None, mime_type: str, acquired_at: str | None = None,
) -> MediaAssetAudit:
    return MediaAssetAudit(
        asset_id=animation.parameters.asset_id, provider=provider, search_query=query, source_url=source_url,
        source_page_url=source_page_url, author_or_provider=author_or_provider, license=license,
        usage_conditions=_PROTOTYPE_USAGE if asset_kind.startswith("external_") else _GENERATED_USAGE,
        acquired_at=acquired_at or datetime.now(timezone.utc).isoformat(), candidate_id=candidate_id,
        local_path=path.relative_to(task_dir).as_posix(), sha256=_sha256(path), asset_kind=asset_kind,
        mime_type=mime_type, usage_start_ms=animation.start_ms, usage_end_ms=animation.end_ms,
    )


def prepare_media_assets(
    task_dir: Path, plan: AnimationPlan, provider: ExternalMediaProvider | None = None, max_download_bytes: int | None = None,
) -> AnimationPlan:
    """Materialize all enabled media visuals and write the authoritative manifest.

    A failed or empty search falls back to an original information graphic.  A
    selected candidate is intentionally strict: it must already exist in the
    task-local candidate manifest, which prevents arbitrary renderer URLs.
    """
    task_dir = task_dir.resolve()
    asset_dir = task_dir / "media-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    # The submitted review plan deliberately has derived audit metadata
    # cleared. Reuse only hash-valid task-local output from the previous render.
    existing = _load_existing_audits(task_dir)
    existing.update({asset.asset_id: asset for asset in plan.media_assets})
    known_candidates = {candidate.id: candidate for candidate in load_candidates(task_dir)}
    active_provider = provider or get_media_provider_by_name(plan.media_provider, SETTINGS)
    limit = max_download_bytes or SETTINGS.media_max_download_mb * 1024 * 1024
    audits: list[MediaAssetAudit] = []

    for animation in plan.animations:
        if animation.type != "media_visual" or not animation.parameters.enabled:
            continue
        params = animation.parameters
        previous = existing.get(params.asset_id)
        if params.selected_candidate_id and params.selected_candidate_id not in known_candidates:
            raise MediaProviderError(f"Selected media candidate does not exist in this task: {params.selected_candidate_id}")
        selection_unchanged = (
            previous
            and previous.search_query == params.search_query
            and (params.selected_candidate_id is None or params.selected_candidate_id == previous.candidate_id)
        )
        if selection_unchanged and _audit_matches_local_file(task_dir, previous):
            audits.append(previous.model_copy(update={
                "search_query": params.search_query, "usage_start_ms": animation.start_ms, "usage_end_ms": animation.end_ms,
            }))
            continue

        candidate: MediaCandidate | None = None
        if params.selected_candidate_id:
            candidate = known_candidates.get(params.selected_candidate_id)
            if candidate is None:
                raise MediaProviderError(f"Selected media candidate does not exist in this task: {params.selected_candidate_id}")
        else:
            try:
                found = active_provider.search(params.search_query, params.desired_asset_kind)
            except MediaProviderError:
                # Wikimedia is the no-key prototype path. A transient network
                # failure must not discard a long ASR/render job: the authored
                # task-local infographic below remains available. Pexels key
                # errors stay explicit so configuration mistakes are visible.
                if active_provider.name not in {"mock", "wikimedia_commons", "manual"}:
                    raise
                found = []
            if found:
                known_candidates = {candidate.id: candidate for candidate in save_candidates(task_dir, found)}
                candidate = _choose_candidate(found)

        if candidate:
            path = _asset_path(task_dir, params.asset_id, candidate.mime_type)
            try:
                _download_candidate(candidate, path, limit)
            except MediaProviderError:
                if params.selected_candidate_id or active_provider.name != "wikimedia_commons":
                    raise
                candidate = None
            if candidate:
                audits.append(_make_audit(
                    task_dir, animation, path, asset_kind=candidate.asset_kind, provider=candidate.provider, query=candidate.query,
                    source_url=candidate.source_url, source_page_url=candidate.source_page_url,
                    author_or_provider=candidate.author_or_provider, license=candidate.license,
                    candidate_id=candidate.id, mime_type=candidate.mime_type,
                ))
                continue

        path = asset_dir / f"{params.asset_id}.svg"
        path.write_text(_fallback_svg(params.title, params.theme, params.accent_color), encoding="utf-8", newline="\n")
        audits.append(_make_audit(
            task_dir, animation, path, asset_kind="generated_infographic", provider="original_infographic",
            query=params.search_query, source_url="generated://semantic-video-animation-agent/knowledge-infographic-v1",
            source_page_url=None, author_or_provider="semantic-video-animation-agent original information graphic",
            license="Original task-local information graphic", candidate_id=None, mime_type="image/svg+xml",
        ))

    if len({asset.asset_id for asset in audits}) != len(audits):
        raise ValueError("each media asset ID may be used by only one visual animation")
    updated = plan.model_copy(update={"media_assets": audits})
    (task_dir / "media_assets.json").write_text(
        json.dumps([asset.model_dump() for asset in audits], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return updated


def renderer_media_assets(task_dir: Path, plan: AnimationPlan) -> list[dict[str, str]]:
    """Expose locally verified assets to Remotion as data URLs, never remote URLs."""
    safe_task_dir = task_dir.resolve()
    values = []
    for asset in plan.media_assets:
        path = (safe_task_dir / asset.local_path).resolve()
        if safe_task_dir not in path.parents or not path.is_file():
            raise ValueError(f"media asset path is not inside the task directory: {asset.asset_id}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != asset.sha256:
            raise ValueError(f"media asset hash mismatch: {asset.asset_id}")
        values.append({"asset_id": asset.asset_id, "data_uri": f"data:{asset.mime_type};base64," + base64.b64encode(data).decode("ascii"), "mime_type": asset.mime_type})
    return values
