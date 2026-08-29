from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from sqlalchemy import select

from . import database
from .config import KNOWLEDGE_ROOT, MODEL_ROOT, SETTINGS, Settings
from .models import KnowledgeChunk, KnowledgeDocument


KNOWLEDGE_INDEX_VERSION = "knowledge-index-v1"
SUPPORTED_SOURCE_TYPES = {".txt": "txt", ".md": "md", ".json": "json"}
_LATIN_OR_HAN = re.compile(r"[A-Za-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]+")


class KnowledgeBaseError(RuntimeError):
    pass


class KnowledgeValidationError(KnowledgeBaseError):
    pass


class KnowledgeNotFoundError(KnowledgeBaseError):
    pass


class KnowledgeEmbeddingError(KnowledgeBaseError):
    pass


class EmbeddingProvider(Protocol):
    model_id: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def tokenize_for_retrieval(text: str) -> list[str]:
    """Tokenize Latin terms plus individual and adjacent Han characters."""

    tokens: list[str] = []
    for match in _LATIN_OR_HAN.finditer(text.lower()):
        term = match.group(0)
        if term.isascii():
            tokens.append(term)
            continue
        characters = list(term)
        tokens.extend(characters)
        tokens.extend(
            characters[index] + characters[index + 1]
            for index in range(len(characters) - 1)
        )
    return tokens


class LocalHashEmbeddingProvider:
    """Small, deterministic feature-hash vectors for zero-download local retrieval."""

    model_id = "local-char-feature-hash-v1"

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 32:
            raise KnowledgeEmbeddingError("local hash embedding dimensions must be at least 32")
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        features = tokenize_for_retrieval(text)
        features.extend(
            normalized[index : index + 3]
            for normalized in [re.sub(r"\s+", "", text.lower())]
            for index in range(max(0, len(normalized) - 2))
        )
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return vector if norm == 0 else [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbeddingProvider:
    """Optional BGE-M3 backend that is deliberately cache/local-path only."""

    def __init__(
        self,
        model_name_or_path: str,
        *,
        local_files_only: bool,
        cache_folder: Path = MODEL_ROOT,
    ) -> None:
        if not local_files_only:
            raise KnowledgeEmbeddingError(
                "knowledge embeddings require KNOWLEDGE_EMBEDDING_LOCAL_FILES_ONLY=true"
            )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise KnowledgeEmbeddingError(
                "sentence-transformers is required for the bge_m3 embedding provider"
            ) from exc
        cache_folder.mkdir(parents=True, exist_ok=True)
        try:
            self._model = SentenceTransformer(
                model_name_or_path,
                cache_folder=str(cache_folder),
                local_files_only=True,
                trust_remote_code=False,
            )
        except Exception as exc:
            raise KnowledgeEmbeddingError(
                "configured embedding model is not available in the local model cache"
            ) from exc
        self.model_id = f"sentence-transformers:{model_name_or_path}"

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        values = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in row] for row in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


def embedding_provider_from_settings(settings: Settings = SETTINGS) -> EmbeddingProvider:
    if settings.knowledge_embedding_provider == "local_hash":
        return LocalHashEmbeddingProvider()
    if settings.knowledge_embedding_provider == "bge_m3":
        return SentenceTransformerEmbeddingProvider(
            settings.knowledge_embedding_model,
            local_files_only=settings.knowledge_embedding_local_files_only,
        )
    raise KnowledgeEmbeddingError(
        "KNOWLEDGE_EMBEDDING_PROVIDER must be local_hash or bge_m3"
    )


def _flatten_json(value: object, path: str = "", depth: int = 0) -> list[str]:
    if depth > 32:
        raise KnowledgeValidationError("JSON nesting exceeds 32 levels")
    if isinstance(value, dict):
        lines: list[str] = []
        for key in sorted(value, key=str):
            child_path = f"{path}.{key}" if path else str(key)
            lines.extend(_flatten_json(value[key], child_path, depth + 1))
        return lines
    if isinstance(value, list):
        lines = []
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            lines.extend(_flatten_json(item, child_path, depth + 1))
        return lines
    rendered = "null" if value is None else str(value)
    return [f"{path}: {rendered}" if path else rendered]


def parse_source_content(source_name: str, data: bytes) -> tuple[str, str]:
    if not source_name or source_name != Path(source_name.replace("\\", "/")).name:
        raise KnowledgeValidationError("source name must be a plain file name")
    if len(source_name) > 255:
        raise KnowledgeValidationError("source name must be at most 255 characters")
    suffix = Path(source_name).suffix.lower()
    source_type = SUPPORTED_SOURCE_TYPES.get(suffix)
    if source_type is None:
        raise KnowledgeValidationError("knowledge source must be .txt, .md, or .json")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise KnowledgeValidationError("knowledge source must use UTF-8 encoding") from exc
    if source_type == "json":
        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise KnowledgeValidationError("knowledge JSON is invalid") from exc
        decoded = "\n".join(_flatten_json(payload))
    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise KnowledgeValidationError("knowledge source is empty")
    return source_type, normalized


def split_into_chunks(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    if chunk_chars < 100 or overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise KnowledgeValidationError("knowledge chunk settings are invalid")
    compact = re.sub(r"[ \t]+", " ", text)
    chunks: list[str] = []
    start = 0
    while start < len(compact):
        maximum_end = min(len(compact), start + chunk_chars)
        end = maximum_end
        if maximum_end < len(compact):
            boundary_floor = start + max(1, chunk_chars // 2)
            candidates = [
                compact.rfind(marker, boundary_floor, maximum_end)
                for marker in ("\n\n", "\n", "。", "！", "？", ". ", "; ")
            ]
            boundary = max(candidates)
            if boundary >= boundary_floor:
                end = boundary + 1
        chunk = compact[start:end].strip()
        if chunk and (not chunks or chunk != chunks[-1]):
            chunks.append(chunk)
        if end >= len(compact):
            break
        start = max(start + 1, end - overlap_chars)
    if not chunks:
        raise KnowledgeValidationError("knowledge source produced no chunks")
    return chunks


def _validate_embeddings(vectors: Sequence[Sequence[float]], expected_count: int) -> list[list[float]]:
    if len(vectors) != expected_count or not vectors:
        raise KnowledgeEmbeddingError("embedding provider returned an invalid vector count")
    dimension = len(vectors[0])
    if dimension == 0 or any(len(vector) != dimension for vector in vectors):
        raise KnowledgeEmbeddingError("embedding provider returned inconsistent dimensions")
    normalized: list[list[float]] = []
    for vector in vectors:
        row = [float(value) for value in vector]
        if any(not math.isfinite(value) for value in row):
            raise KnowledgeEmbeddingError("embedding provider returned a non-finite value")
        normalized.append(row)
    return normalized


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


@dataclass(frozen=True)
class _ChunkRecord:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    tokens: list[str]


class KnowledgeBaseService:
    def __init__(
        self,
        *,
        root: Path = KNOWLEDGE_ROOT,
        settings: Settings = SETTINGS,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.root = root.resolve()
        self.settings = settings
        self._provider = embedding_provider

    @property
    def provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = embedding_provider_from_settings(self.settings)
        return self._provider

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise KnowledgeValidationError("knowledge path must stay inside storage/knowledge") from exc
        return resolved

    def _source_path(self, document_id: str, source_type: str) -> Path:
        return self._safe_path(self.root / "sources" / f"{document_id}.{source_type}")

    @staticmethod
    def _serialize_document(document: KnowledgeDocument, *, created: bool | None = None) -> dict:
        payload = {
            "document_id": document.document_id,
            "source_name": document.source_name,
            "source_type": document.source_type,
            "content_sha256": document.content_sha256,
            "summary": document.summary,
            "metadata": document.metadata_json,
            "chunk_count": len(document.chunks),
            "index_version": document.index_version,
            "embedding_model": document.embedding_model,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        }
        if created is not None:
            payload["created"] = created
        return payload

    def import_document(
        self,
        source_name: str,
        data: bytes,
        metadata: dict | None = None,
    ) -> dict:
        maximum_bytes = self.settings.knowledge_max_file_mb * 1024 * 1024
        if not data or len(data) > maximum_bytes:
            raise KnowledgeValidationError(
                f"knowledge source must be between 1 byte and {self.settings.knowledge_max_file_mb} MB"
            )
        metadata = metadata or {}
        if not isinstance(metadata, dict):
            raise KnowledgeValidationError("knowledge metadata must be a JSON object")
        try:
            serialized_metadata = json.dumps(metadata, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise KnowledgeValidationError("knowledge metadata must be JSON serializable") from exc
        if len(serialized_metadata.encode("utf-8")) > 8_000:
            raise KnowledgeValidationError("knowledge metadata is too large")

        source_type, text = parse_source_content(source_name, data)
        content_sha256 = hashlib.sha256(data).hexdigest()
        document_id = f"doc_{content_sha256[:24]}"
        provider = self.provider
        database.initialize_database()

        source_path = self._source_path(document_id, source_type)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        with next(database.get_session()) as session:
            document = session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.content_sha256 == content_sha256
                )
            )
            if (
                document is not None
                and document.index_version == KNOWLEDGE_INDEX_VERSION
                and document.embedding_model == provider.model_id
            ):
                result = self._serialize_document(document, created=False)
                result["reindexed"] = False
                return result

            chunk_texts = split_into_chunks(
                text,
                self.settings.knowledge_chunk_chars,
                self.settings.knowledge_chunk_overlap_chars,
            )
            vectors = _validate_embeddings(
                provider.embed_documents(chunk_texts), len(chunk_texts)
            )
            is_new_document = document is None

            temporary_path = source_path.with_suffix(source_path.suffix + ".tmp")
            temporary_path.write_bytes(data)
            temporary_path.replace(source_path)
            if document is None:
                document = KnowledgeDocument(
                    document_id=document_id,
                    source_name=source_name,
                    source_type=source_type,
                    source_path=source_path.relative_to(self.root).as_posix(),
                    content_sha256=content_sha256,
                    summary=re.sub(r"\s+", " ", text)[:240],
                    metadata_json=metadata,
                    index_version=KNOWLEDGE_INDEX_VERSION,
                    embedding_model=provider.model_id,
                )
                session.add(document)
            else:
                document.source_name = source_name
                document.source_type = source_type
                document.source_path = source_path.relative_to(self.root).as_posix()
                document.summary = re.sub(r"\s+", " ", text)[:240]
                document.metadata_json = metadata
                document.index_version = KNOWLEDGE_INDEX_VERSION
                document.embedding_model = provider.model_id
                document.chunks.clear()

            for ordinal, (chunk_text, embedding) in enumerate(
                zip(chunk_texts, vectors, strict=True)
            ):
                chunk_sha256 = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                chunk_id = hashlib.sha256(
                    f"{document_id}:{ordinal}:{chunk_sha256}".encode("utf-8")
                ).hexdigest()
                document.chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"chunk_{chunk_id[:32]}",
                        ordinal=ordinal,
                        content=chunk_text,
                        content_sha256=chunk_sha256,
                        token_count=len(tokenize_for_retrieval(chunk_text)),
                        metadata_json={"source_type": source_type},
                        embedding_json=embedding,
                        embedding_model=provider.model_id,
                        index_version=KNOWLEDGE_INDEX_VERSION,
                    )
                )
            session.commit()
            session.refresh(document)
            result = self._serialize_document(document, created=is_new_document)
            result["reindexed"] = not is_new_document
            return result

    def list_documents(self) -> list[dict]:
        database.initialize_database()
        with next(database.get_session()) as session:
            documents = session.scalars(
                select(KnowledgeDocument).order_by(
                    KnowledgeDocument.created_at, KnowledgeDocument.document_id
                )
            ).all()
            return [self._serialize_document(document) for document in documents]

    def delete_document(self, document_id: str) -> dict:
        if not re.fullmatch(r"doc_[0-9a-f]{24}", document_id):
            raise KnowledgeNotFoundError("knowledge document not found")
        database.initialize_database()
        with next(database.get_session()) as session:
            document = session.get(KnowledgeDocument, document_id)
            if document is None:
                raise KnowledgeNotFoundError("knowledge document not found")
            source_path = self._safe_path(self.root / document.source_path)
            session.delete(document)
            session.commit()
        if source_path.is_file():
            source_path.unlink()
        return {"document_id": document_id, "deleted": True}

    def _records(self) -> list[_ChunkRecord]:
        database.initialize_database()
        with next(database.get_session()) as session:
            rows = session.execute(
                select(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.document_id)
                .where(KnowledgeChunk.index_version == KNOWLEDGE_INDEX_VERSION)
                .order_by(KnowledgeChunk.chunk_id)
            ).all()
            return [
                _ChunkRecord(chunk=chunk, document=document, tokens=tokenize_for_retrieval(chunk.content))
                for chunk, document in rows
            ]

    @staticmethod
    def _bm25(query_tokens: list[str], records: list[_ChunkRecord]) -> dict[str, float]:
        if not query_tokens or not records:
            return {}
        document_frequencies = Counter(
            token
            for record in records
            for token in set(record.tokens)
        )
        average_length = sum(len(record.tokens) for record in records) / len(records)
        scores: dict[str, float] = {}
        for record in records:
            frequencies = Counter(record.tokens)
            length = len(record.tokens)
            score = 0.0
            for token in set(query_tokens):
                frequency = frequencies[token]
                if frequency == 0:
                    continue
                frequency_docs = document_frequencies[token]
                inverse_frequency = math.log(
                    1 + (len(records) - frequency_docs + 0.5) / (frequency_docs + 0.5)
                )
                denominator = frequency + 1.5 * (
                    1 - 0.75 + 0.75 * length / max(average_length, 1)
                )
                score += inverse_frequency * frequency * 2.5 / denominator
            if score > 0:
                scores[record.chunk.chunk_id] = score
        return scores

    def search(
        self,
        query: str,
        *,
        method: str = "hybrid",
        limit: int = 5,
        rerank: bool = False,
    ) -> dict:
        normalized_query = query.strip()
        if not normalized_query or len(normalized_query) > 500:
            raise KnowledgeValidationError("knowledge query must contain 1 to 500 characters")
        if method not in {"keyword", "vector", "hybrid"}:
            raise KnowledgeValidationError("retrieval method must be keyword, vector, or hybrid")
        if limit < 1 or limit > 20:
            raise KnowledgeValidationError("knowledge result limit must be between 1 and 20")

        records = self._records()
        query_tokens = tokenize_for_retrieval(normalized_query)
        keyword_scores = self._bm25(query_tokens, records)
        vector_scores: dict[str, float] = {}
        if method in {"vector", "hybrid"} and records:
            query_vector = _validate_embeddings([self.provider.embed_query(normalized_query)], 1)[0]
            vector_scores = {
                record.chunk.chunk_id: _cosine(query_vector, record.chunk.embedding_json)
                for record in records
                if record.chunk.embedding_model == self.provider.model_id
            }

        def normalized(scores: dict[str, float]) -> dict[str, float]:
            if not scores:
                return {}
            lowest = min(scores.values())
            highest = max(scores.values())
            if highest == lowest:
                return {key: 1.0 for key in scores}
            return {
                key: (value - lowest) / (highest - lowest)
                for key, value in scores.items()
            }

        normalized_keyword = normalized(keyword_scores)
        normalized_vector = normalized(vector_scores)
        combined: dict[str, float] = {}
        if method == "keyword":
            combined = normalized_keyword
        elif method == "vector":
            combined = normalized_vector
        else:
            candidate_ids = set(normalized_keyword) | set(normalized_vector)
            combined = {
                chunk_id: 0.45 * normalized_keyword.get(chunk_id, 0.0)
                + 0.55 * normalized_vector.get(chunk_id, 0.0)
                for chunk_id in candidate_ids
            }

        record_by_id = {record.chunk.chunk_id: record for record in records}
        deduplicated = {
            chunk_id: score
            for chunk_id, score in combined.items()
            if chunk_id in record_by_id
        }
        if rerank:
            query_set = set(query_tokens)
            for chunk_id in deduplicated:
                record_tokens = set(record_by_id[chunk_id].tokens)
                coverage = len(query_set & record_tokens) / max(len(query_set), 1)
                deduplicated[chunk_id] = 0.8 * deduplicated[chunk_id] + 0.2 * coverage

        ranked = sorted(deduplicated.items(), key=lambda item: (-item[1], item[0]))[:limit]
        results = []
        for chunk_id, score in ranked:
            record = record_by_id[chunk_id]
            results.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": record.document.document_id,
                    "source": record.document.source_name,
                    "content": record.chunk.content,
                    "summary": record.document.summary,
                    "score": round(score, 8),
                    "keyword_score": round(keyword_scores.get(chunk_id, 0.0), 8),
                    "vector_score": round(vector_scores.get(chunk_id, 0.0), 8),
                    "retrieval_method": method,
                    "metadata": {
                        **record.document.metadata_json,
                        **record.chunk.metadata_json,
                    },
                    "index_version": record.chunk.index_version,
                }
            )
        return {
            "query": normalized_query,
            "method": method,
            "reranked": rerank,
            "index_version": KNOWLEDGE_INDEX_VERSION,
            "embedding_model": self.provider.model_id if method in {"vector", "hybrid"} else None,
            "count": len(results),
            "results": results,
        }
