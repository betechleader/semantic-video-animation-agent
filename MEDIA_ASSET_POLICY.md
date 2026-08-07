# External-media prototype policy

> **External-material prototype; not suitable for direct commercial publication.**

This phase may search, download, and composite external images or short video B-roll to validate semantic-animation effects. An external visual is only an illustrative editing asset: it must never be used as factual evidence or cause the planner to assert a fact not present in the transcript.

Each adopted asset is copied into `storage/{task_id}/media-assets/`; Remotion receives only the hash-verified local copy, never a remote URL. `media_assets.json` records the provider, search query, downloaded URL, source page URL when known, named author/provider, declared licence text, acquisition time, task-relative path, SHA-256 digest, MIME type, and exact use interval. Search results that have not been selected stay in `media_candidates.json` for reviewer inspection.

## Provider modes

- `MEDIA_PROVIDER=mock` is the default: no network call is made and a designed original information graphic is used.
- `MEDIA_PROVIDER=knowledge` routes planner-marked book entities to the no-key Open Library Search/Covers APIs and other B-roll to Wikimedia Commons. It is the recommended browser profile.
- `MEDIA_PROVIDER=wikimedia_commons` searches Wikimedia Commons with its no-key Action API and downloads a selected task-local copy.
- `MEDIA_PROVIDER=pexels` supports image/video search when `PEXELS_API_KEY` is set. Without it the API returns an actionable configuration error.
- `MEDIA_PROVIDER=manual` intentionally performs no automatic search. A reviewer can add an explicit `http(s)` image/video URL in the review panel.

Automatic candidates must pass a query-to-title/author relevance threshold before visual shape is considered. An unmatched result falls back to the original graphic; exact reviewer selections remain authoritative and strict.

The system records metadata but **does not determine whether a licence, person release, trademark, editorial use, or platform use is commercially adequate**. A human must inspect the source page, current terms, edition accuracy, factual relevance, visual suitability, and rights before any public/commercial release. If search has no relevant candidate, the download fails, or the default Mock mode is active, the renderer falls back to an original task-local concept graphic.
