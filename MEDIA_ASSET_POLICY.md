# Media asset and copyright policy

The pipeline must not download, scrape, or automatically place network images into a video. A web image is not eligible merely because it is publicly visible.

The current implementation permits only `generated_original` task-local SVG illustrations. They are generic topic visuals (for example, an open-book illustration) and must not reproduce a specific book cover, logo, trademarked artwork, or recognisable cover composition.

Each rendered asset has a corresponding `media_assets.json` record and plan entry containing its source URI, author/provider, licence, permitted transformations, acquisition time, local path, SHA-256 digest, and asset kind. The renderer verifies the file and digest before it can be passed to Remotion.

Future external providers may be added only after they enforce all of these conditions before download and render: a traceable source URL, named provider or author, an explicit licence that permits commercial short-video/social-platform distribution, and permission to crop, scale, composite, and overlay text. Their original licence terms must be stored with the audit record. If any condition is missing or ambiguous, use the original-illustration fallback.
