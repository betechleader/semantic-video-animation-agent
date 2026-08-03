"""Copyright-safe media asset preparation.

This first provider deliberately has no network client. It only creates original,
generic SVG illustrations inside the task directory, so no unverified web asset can
enter a render by accident.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import AnimationPlan, MediaAssetAudit


_ORIGINAL_LICENSE = "Original work; commercial short-video and social-platform distribution permitted"
_USAGE_CONDITIONS = "May be resized, cropped, composited, and overlaid with text. It is a generic theme illustration, not a reproduction of a specific cover or trademarked artwork."


def _svg(title: str, theme: str, accent: str) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # A deliberately generic, compact book cue: it contains no cover artwork,
    # logo, or cover-like layout, and its transparent canvas avoids blocking the
    # speaker with a large opaque panel.
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="360" height="430" viewBox="0 0 360 430">
<defs>
  <linearGradient id="cover" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#FFF9E8"/><stop offset="1" stop-color="#EFD9A4"/></linearGradient>
  <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#182033" flood-opacity=".22"/></filter>
</defs>
<g filter="url(#shadow)">
  <path d="M72 96c53-16 98-1 108 22v179c-28-28-72-37-108-20z" fill="url(#cover)" stroke="#D4AD5D" stroke-width="5"/>
  <path d="M288 96c-53-16-98-1-108 22v179c28-28 72-37 108-20z" fill="#FFFDF7" stroke="#D4AD5D" stroke-width="5"/>
  <path d="M180 118v179" stroke="{accent}" stroke-width="7"/>
  <path d="M103 153h47m-47 33h47m-47 33h38m69-66h47m-47 33h47m-47 33h38" stroke="#9EADC2" stroke-width="8" stroke-linecap="round"/>
  <path d="M163 96l17 23 17-23v69l-17-12-17 12z" fill="{accent}"/>
</g>
<circle cx="287" cy="68" r="21" fill="{accent}" opacity=".9"/>
<rect x="48" y="342" width="264" height="50" rx="25" fill="#132238" fill-opacity=".86"/>
<text x="180" y="375" text-anchor="middle" fill="#FFFDF7" font-family="Microsoft YaHei, sans-serif" font-size="25" font-weight="700">{safe_title[:18]}</text>
</svg>'''


def prepare_media_assets(task_dir: Path, plan: AnimationPlan) -> AnimationPlan:
    """Create/verify original media assets and write their immutable audit manifest."""
    task_dir = task_dir.resolve()
    asset_dir = task_dir / "media-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    existing = {asset.asset_id: asset for asset in plan.media_assets}
    audits: list[MediaAssetAudit] = []
    for animation in plan.animations:
        if animation.type != "media_visual":
            continue
        params = animation.parameters
        path = asset_dir / f"{params.asset_id}.svg"
        # A newly planned visual has no trusted audit record yet, so regenerate
        # it from the current title/theme instead of accidentally reusing a
        # previous task-local SVG with the same deterministic asset ID.
        if not path.exists() or params.asset_id not in existing:
            path.write_text(_svg(params.title, params.theme, params.accent_color), encoding="utf-8", newline="\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        previous = existing.get(params.asset_id)
        local_path = path.relative_to(task_dir).as_posix()
        if previous and (previous.asset_kind != "generated_original" or previous.local_path != local_path or previous.sha256 != digest):
            raise ValueError(f"{params.asset_id} has invalid or changed media audit metadata")
        audits.append(MediaAssetAudit(
            asset_id=params.asset_id,
            source_url="generated://semantic-video-animation-agent/original-book-visual-v1",
            author_or_provider="semantic-video-animation-agent original SVG generator",
            license=_ORIGINAL_LICENSE,
            usage_conditions=_USAGE_CONDITIONS,
            acquired_at=previous.acquired_at if previous else datetime.now(timezone.utc).isoformat(),
            local_path=local_path, sha256=digest, asset_kind="generated_original",
        ))
    if len({asset.asset_id for asset in audits}) != len(audits):
        raise ValueError("each media asset ID may be used by only one visual animation")
    updated = plan.model_copy(update={"media_assets": audits})
    (task_dir / "media_assets.json").write_text(
        json.dumps([asset.model_dump() for asset in audits], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return updated


def renderer_media_assets(task_dir: Path, plan: AnimationPlan) -> list[dict[str, str]]:
    """Expose local verified assets to Remotion as data URLs, never remote URLs."""
    safe_task_dir = task_dir.resolve()
    values = []
    for asset in plan.media_assets:
        path = (safe_task_dir / asset.local_path).resolve()
        if safe_task_dir not in path.parents or not path.is_file():
            raise ValueError(f"media asset path is not inside the task directory: {asset.asset_id}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != asset.sha256:
            raise ValueError(f"media asset hash mismatch: {asset.asset_id}")
        values.append({"asset_id": asset.asset_id, "data_uri": "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")})
    return values
