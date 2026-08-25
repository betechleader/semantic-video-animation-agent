import json

import pytest

from backend.app.media_assets import _choose_candidate, prepare_media_assets, renderer_media_assets
from backend.app.media_providers import KnowledgeMediaProvider, MediaProviderError, OpenLibraryBooksProvider, PexelsProvider, WikimediaCommonsProvider, manual_candidate, save_candidates
from backend.app.providers import TranscriptAnimationPlanningProvider
from backend.app.schemas import AnimationPlan, ManualMediaCandidateInput, MediaCandidate, Transcript


class FakeResponse:
    def __init__(self, payload=None, content=b"external image bytes", content_type="image/jpeg") -> None:
        self.payload = payload or {}
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.content


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResponse(self.payload)


def source_transcript() -> Transcript:
    return Transcript.model_validate({
        "language": "zh", "full_text": "介绍一个产品", "segments": [{
            "text": "介绍一个产品", "start_ms": 1000, "end_ms": 4000,
            "words": [{"text": "介绍", "start_ms": 1000, "end_ms": 2000}, {"text": "产品", "start_ms": 2000, "end_ms": 4000}],
        }],
    })


def test_wikimedia_provider_extracts_provenance_and_portrait_candidate() -> None:
    payload = {"query": {"pages": {"1": {"title": "File:Market.jpg", "imageinfo": [{
        "mime": "image/jpeg", "url": "https://upload.wikimedia.org/original.jpg", "thumburl": "https://upload.wikimedia.org/thumb.jpg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Market.jpg", "width": 1200, "height": 1800,
        "thumbwidth": 640, "thumbheight": 960,
        "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "<b>Example author</b>"}},
    }]}}}}
    session = FakeSession(payload)
    candidates = WikimediaCommonsProvider(session=session).search("supermarket product", "external_image")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_url.endswith("thumb.jpg")
    assert candidate.source_page_url.endswith("Market.jpg")
    assert candidate.license == "CC BY-SA 4.0"
    assert candidate.author_or_provider == "Example author"
    assert session.calls[0][1]["params"]["gsrnamespace"] == 6


def test_open_library_provider_returns_exact_book_cover_with_provenance() -> None:
    payload = {"docs": [{
        "key": "/works/OL23493W", "title": "Psychology and life", "cover_i": 10357001,
        "author_name": ["Philip G. Zimbardo", "Richard J. Gerrig"],
    }]}
    session = FakeSession(payload)

    candidates = OpenLibraryBooksProvider(session=session).search(
        "Psychology and Life Richard J. Gerrig Philip G. Zimbardo", "external_image",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.provider == "open_library"
    assert candidate.source_url == "https://covers.openlibrary.org/b/id/10357001-L.jpg"
    assert candidate.source_page_url == "https://openlibrary.org/works/OL23493W"
    assert "Richard J. Gerrig" in candidate.author_or_provider
    assert session.calls[0][1]["params"]["title"] == "Psychology and Life"


def test_knowledge_provider_routes_book_queries_to_open_library() -> None:
    class BookProvider:
        def search(self, query, asset_kind):
            assert query == "Psychology and Life"
            assert asset_kind == "external_image"
            return []

    class CommonsProvider:
        def search(self, _query, _asset_kind):
            raise AssertionError("book query should not use generic Commons search")

    provider = KnowledgeMediaProvider(book_provider=BookProvider(), commons_provider=CommonsProvider())
    assert provider.search("book: Psychology and Life", "external_image") == []


def test_automatic_candidate_selection_rejects_unrelated_portrait() -> None:
    candidates = [
        MediaCandidate(
            id="candidate_wikimedia_portrait", provider="wikimedia_commons", query="Cinderella fairy tale illustration",
            asset_kind="external_image", source_url="https://example.test/man.jpg", title="David Rice Atchison portrait",
            author_or_provider="contributor", license="review required", mime_type="image/jpeg", width=600, height=1000,
        ),
        MediaCandidate(
            id="candidate_wikimedia_cinderella", provider="wikimedia_commons", query="Cinderella fairy tale illustration",
            asset_kind="external_image", source_url="https://example.test/cinderella.jpg", title="Cinderella fairy tale illustration",
            author_or_provider="contributor", license="review required", mime_type="image/jpeg", width=1200, height=900,
        ),
    ]

    selected = _choose_candidate(candidates, "Cinderella fairy tale illustration")

    assert selected is not None
    assert selected.id == "candidate_wikimedia_cinderella"
    assert _choose_candidate(candidates[:1], "Cinderella fairy tale illustration") is None


@pytest.mark.parametrize(
    ("query", "filename", "expected_provider"),
    [
        ("book: Psychology and Life Richard J. Gerrig", "psychology-and-life-reference.png", "curated_user_reference"),
        ("Cinderella fairy tale illustration", "cinderella-original.png", "curated_original"),
    ],
)
def test_knowledge_provider_prefers_exact_local_entity_assets(
    tmp_path, monkeypatch, query: str, filename: str, expected_provider: str,
) -> None:
    asset_root = tmp_path / "curated"
    asset_root.mkdir()
    expected_bytes = f"local asset: {filename}".encode()
    (asset_root / filename).write_bytes(expected_bytes)
    monkeypatch.setattr("backend.app.media_assets.KNOWLEDGE_ASSET_ROOT", asset_root)

    raw_plan = TranscriptAnimationPlanningProvider().plan(source_transcript())
    data = raw_plan.model_dump()
    data["media_provider"] = "knowledge"
    data["animations"][0]["parameters"]["search_query"] = query
    plan = AnimationPlan.model_validate(data)

    prepared = prepare_media_assets(tmp_path / "task", plan)

    audit = prepared.media_assets[0]
    assert audit.provider == expected_provider
    assert audit.mime_type == "image/png"
    assert (tmp_path / "task" / audit.local_path).read_bytes() == expected_bytes


def test_curated_asset_replaces_a_previous_infographic_fallback(tmp_path, monkeypatch) -> None:
    raw_plan = TranscriptAnimationPlanningProvider().plan(source_transcript())
    data = raw_plan.model_dump()
    data["animations"][0]["parameters"]["search_query"] = "book: Psychology and Life"
    fallback = prepare_media_assets(tmp_path / "task", AnimationPlan.model_validate(data))
    assert fallback.media_assets[0].provider == "original_infographic"

    asset_root = tmp_path / "curated"
    asset_root.mkdir()
    (asset_root / "psychology-and-life-reference.png").write_bytes(b"exact cover")
    monkeypatch.setattr("backend.app.media_assets.KNOWLEDGE_ASSET_ROOT", asset_root)
    data["media_provider"] = "knowledge"

    prepared = prepare_media_assets(tmp_path / "task", AnimationPlan.model_validate(data))

    assert prepared.media_assets[0].provider == "curated_user_reference"
    assert (tmp_path / "task" / prepared.media_assets[0].local_path).read_bytes() == b"exact cover"


def test_selected_external_candidate_is_downloaded_hashed_and_exposed_only_as_task_local_data_url(tmp_path, monkeypatch) -> None:
    raw_plan = TranscriptAnimationPlanningProvider().plan(source_transcript())
    assert raw_plan.animations[0].type == "media_visual"
    candidate = manual_candidate(ManualMediaCandidateInput(
        query="supermarket product", source_url="https://example.test/market.jpg", source_page_url="https://example.test/page",
        title="Market shelf", author_or_provider="Example photographer", license="Prototype test license",
    ))
    save_candidates(tmp_path, [candidate])
    data = raw_plan.model_dump()
    data["animations"][0]["parameters"]["selected_candidate_id"] = candidate.id
    plan = AnimationPlan.model_validate(data)
    monkeypatch.setattr("backend.app.media_assets.requests.get", lambda *args, **kwargs: FakeResponse(content=b"JPEG fixture"))

    prepared = prepare_media_assets(tmp_path, plan)
    audit = prepared.media_assets[0]
    assert audit.asset_kind == "external_image"
    assert audit.provider == "manual"
    assert audit.source_url == "https://example.test/market.jpg"
    assert audit.source_page_url == "https://example.test/page"
    assert audit.candidate_id == candidate.id
    assert audit.usage_start_ms == 1000
    assert audit.usage_end_ms == 3000
    assert (tmp_path / audit.local_path).read_bytes() == b"JPEG fixture"
    assert renderer_media_assets(tmp_path, prepared)[0]["data_uri"].startswith("data:image/jpeg;base64,")
    manifest = json.loads((tmp_path / "media_assets.json").read_text(encoding="utf-8"))
    assert manifest[0]["sha256"] == audit.sha256


def test_missing_or_failed_explicit_candidate_is_never_silently_replaced(tmp_path, monkeypatch) -> None:
    raw_plan = TranscriptAnimationPlanningProvider().plan(source_transcript())
    data = raw_plan.model_dump()
    data["animations"][0]["parameters"]["selected_candidate_id"] = "candidate_missing"
    with pytest.raises(MediaProviderError, match="does not exist in this task"):
        prepare_media_assets(tmp_path, AnimationPlan.model_validate(data))

    candidate = manual_candidate(ManualMediaCandidateInput(
        query="product", source_url="https://example.test/fail.jpg", title="Reviewed selection",
    ))
    save_candidates(tmp_path, [candidate])
    data["animations"][0]["parameters"]["selected_candidate_id"] = candidate.id
    monkeypatch.setattr(
        "backend.app.media_assets._download_candidate",
        lambda *_args: (_ for _ in ()).throw(MediaProviderError("explicit download failed")),
    )
    with pytest.raises(MediaProviderError, match="explicit download failed"):
        prepare_media_assets(tmp_path, AnimationPlan.model_validate(data))


def test_pexels_without_key_has_a_clear_actionable_error() -> None:
    with pytest.raises(MediaProviderError, match="PEXELS_API_KEY"):
        PexelsProvider(None).search("factory", "external_video")


def test_automatic_wikimedia_download_failure_falls_back_to_infographic(tmp_path, monkeypatch) -> None:
    plan = TranscriptAnimationPlanningProvider().plan(source_transcript()).model_copy(update={"media_provider": "wikimedia_commons"})
    candidate = MediaCandidate(
        id="candidate_rate_limited", provider="wikimedia_commons", query="supermarket product",
        asset_kind="external_image", source_url="https://example.com/rate-limited.jpg",
        source_page_url="https://example.com/source", title="candidate", author_or_provider="author",
        license="review required", mime_type="image/jpeg", width=900, height=1600,
    )

    class RateLimitedProvider:
        name = "wikimedia_commons"

        def search(self, _query, _asset_kind):
            return [candidate]

    monkeypatch.setattr(
        "backend.app.media_assets._download_candidate",
        lambda *_args: (_ for _ in ()).throw(MediaProviderError("429")),
    )
    rendered = prepare_media_assets(tmp_path, plan, provider=RateLimitedProvider())
    assert rendered.media_assets[0].provider == "original_infographic"


def test_selected_video_candidate_keeps_a_local_video_data_uri(tmp_path, monkeypatch) -> None:
    raw_plan = TranscriptAnimationPlanningProvider().plan(source_transcript())
    candidate = manual_candidate(ManualMediaCandidateInput(
        query="factory floor", source_url="https://example.test/factory.mp4", title="Factory line",
        asset_kind="external_video", mime_type="video/mp4", duration_seconds=3,
    ))
    save_candidates(tmp_path, [candidate])
    data = raw_plan.model_dump()
    data["animations"][0]["parameters"].update({"selected_candidate_id": candidate.id, "desired_asset_kind": "external_video"})
    monkeypatch.setattr("backend.app.media_assets.requests.get", lambda *args, **kwargs: FakeResponse(content=b"MP4 fixture", content_type="video/mp4"))
    prepared = prepare_media_assets(tmp_path, AnimationPlan.model_validate(data))
    assert prepared.media_assets[0].asset_kind == "external_video"
    assert renderer_media_assets(tmp_path, prepared)[0]["data_uri"].startswith("data:video/mp4;base64,")
