import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import database, knowledge_base, knowledge_cli, main
from backend.app.config import SETTINGS
from backend.app.knowledge_base import (
    KnowledgeBaseService,
    KnowledgeEmbeddingError,
    KnowledgeValidationError,
    SentenceTransformerEmbeddingProvider,
)
from backend.app.models import KnowledgeChunk, KnowledgeDocument


class FakeEmbeddingProvider:
    model_id = "fake-embedding-v1"

    def __init__(self) -> None:
        self.document_calls = 0

    @staticmethod
    def _vector(text: str) -> list[float]:
        if "苹果" in text or "水果" in text:
            return [1.0, 0.0, 0.0]
        if "工厂" in text or "制造" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts) -> list[list[float]]:
        self.document_calls += 1
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def configure_knowledge_database(tmp_path: Path, monkeypatch) -> Path:
    storage = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    return storage / "knowledge"


def settings_for_tests(**overrides):
    return replace(
        SETTINGS,
        knowledge_max_file_mb=1,
        knowledge_chunk_chars=120,
        knowledge_chunk_overlap_chars=20,
        knowledge_embedding_provider="local_hash",
        **overrides,
    )


def test_import_txt_md_json_has_stable_ids_metadata_and_idempotency(
    tmp_path: Path, monkeypatch
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    provider = FakeEmbeddingProvider()
    service = KnowledgeBaseService(
        root=root, settings=settings_for_tests(), embedding_provider=provider
    )

    first = service.import_document(
        "fruit.txt",
        "苹果是一种常见水果。\n它含有膳食纤维。".encode(),
        {"topic": "nutrition"},
    )
    duplicate = service.import_document(
        "fruit.txt",
        "苹果是一种常见水果。\n它含有膳食纤维。".encode(),
        {"topic": "changed-but-duplicate"},
    )
    markdown = service.import_document("factory.md", "# 制造\n\n工厂负责制造产品。".encode())
    structured = service.import_document(
        "book.json",
        json.dumps({"title": "心理学与生活", "authors": ["津巴多"]}, ensure_ascii=False).encode(),
    )

    assert first["created"] is True
    assert duplicate["created"] is False
    assert duplicate["document_id"] == first["document_id"]
    assert first["document_id"].startswith("doc_")
    assert first["metadata"] == {"topic": "nutrition"}
    assert markdown["source_type"] == "md"
    assert structured["source_type"] == "json"
    assert provider.document_calls == 3
    documents = service.list_documents()
    assert len(documents) == 3
    assert all(item["index_version"] == "knowledge-index-v1" for item in documents)
    assert (root / "sources" / f"{first['document_id']}.txt").is_file()


def test_fake_vectors_enable_keyword_vector_hybrid_and_optional_rerank(
    tmp_path: Path, monkeypatch
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=settings_for_tests(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    apple = service.import_document("apple.txt", "苹果富含纤维，适合作为日常食物。".encode())
    service.import_document("factory.txt", "工厂通过自动化设备制造产品。".encode())

    keyword = service.search("自动化工厂", method="keyword")
    vector = service.search("水果", method="vector")
    hybrid = service.search("苹果水果", method="hybrid", rerank=True)

    assert keyword["results"][0]["source"] == "factory.txt"
    assert keyword["results"][0]["retrieval_method"] == "keyword"
    assert vector["results"][0]["document_id"] == apple["document_id"]
    assert vector["embedding_model"] == "fake-embedding-v1"
    assert hybrid["reranked"] is True
    assert hybrid["results"][0]["document_id"] == apple["document_id"]
    assert len({item["chunk_id"] for item in hybrid["results"]}) == hybrid["count"]
    assert all("source" in item and "score" in item for item in hybrid["results"])


def test_reimport_reindexes_when_index_version_changes_without_changing_ids(
    tmp_path: Path, monkeypatch
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=settings_for_tests(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    source = "稳定的分块内容用于验证索引升级。".encode()
    first = service.import_document("versioned.txt", source)
    with next(database.get_session()) as session:
        first_chunk_id = session.scalar(
            select(KnowledgeChunk.chunk_id).where(
                KnowledgeChunk.document_id == first["document_id"]
            )
        )

    monkeypatch.setattr(knowledge_base, "KNOWLEDGE_INDEX_VERSION", "knowledge-index-v2")
    second = service.import_document("versioned.txt", source)
    with next(database.get_session()) as session:
        chunk = session.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == first["document_id"]
            )
        )

    assert second["created"] is False
    assert second["reindexed"] is True
    assert second["document_id"] == first["document_id"]
    assert chunk.chunk_id == first_chunk_id
    assert chunk.index_version == "knowledge-index-v2"


def test_delete_is_confined_to_knowledge_root(tmp_path: Path, monkeypatch) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=settings_for_tests(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    imported = service.import_document("safe.txt", "受控知识内容。".encode())
    outside = root.parent / "must-stay.txt"
    outside.write_text("user data", encoding="utf-8")
    with next(database.get_session()) as session:
        document = session.get(KnowledgeDocument, imported["document_id"])
        document.source_path = "../must-stay.txt"
        session.commit()

    with pytest.raises(KnowledgeValidationError, match="inside storage/knowledge"):
        service.delete_document(imported["document_id"])
    assert outside.read_text(encoding="utf-8") == "user data"
    with next(database.get_session()) as session:
        assert session.get(KnowledgeDocument, imported["document_id"]) is not None


def test_sentence_transformer_backend_forces_local_files_only(
    tmp_path: Path, monkeypatch
) -> None:
    captured = {}

    class StubSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            captured.update({"model_name": model_name, **kwargs})

        def encode(self, texts, **kwargs):
            captured["encode"] = kwargs
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=StubSentenceTransformer),
    )
    provider = SentenceTransformerEmbeddingProvider(
        "BAAI/bge-m3", local_files_only=True, cache_folder=tmp_path / "models"
    )
    assert provider.embed_query("离线查询") == [1.0, 0.0]
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["local_files_only"] is True
    assert captured["trust_remote_code"] is False
    assert captured["encode"]["normalize_embeddings"] is True

    with pytest.raises(KnowledgeEmbeddingError, match="LOCAL_FILES_ONLY=true"):
        SentenceTransformerEmbeddingProvider(
            "BAAI/bge-m3", local_files_only=False, cache_folder=tmp_path / "models"
        )


def test_knowledge_api_import_list_search_and_delete_is_offline(
    tmp_path: Path, monkeypatch
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=settings_for_tests(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(main, "_knowledge_service", lambda: service)

    with TestClient(main.app) as client:
        imported_response = client.post(
            "/api/knowledge/documents",
            files={"file": ("facts.txt", "苹果属于水果。".encode(), "text/plain")},
            data={"metadata_json": json.dumps({"scope": "demo"})},
        )
        assert imported_response.status_code == 201
        imported = imported_response.json()

        listed = client.get("/api/knowledge/documents")
        searched = client.post(
            "/api/knowledge/search",
            json={"query": "水果", "method": "hybrid", "limit": 5, "rerank": True},
        )
        deleted = client.delete(f"/api/knowledge/documents/{imported['document_id']}")
        missing = client.delete(f"/api/knowledge/documents/{imported['document_id']}")

    assert listed.status_code == 200
    assert listed.json()["documents"][0]["source_name"] == "facts.txt"
    assert searched.status_code == 200
    assert searched.json()["results"][0]["chunk_id"].startswith("chunk_")
    assert deleted.json() == {"document_id": imported["document_id"], "deleted": True}
    assert missing.status_code == 404
    assert service.list_documents() == []


def test_knowledge_cli_import_search_list_and_delete(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    source = project / "cli.md"
    source.write_text("苹果和其他水果可以作为知识检索示例。", encoding="utf-8")
    monkeypatch.setattr(knowledge_cli, "PROJECT_ROOT", project)
    monkeypatch.setattr(knowledge_cli, "KNOWLEDGE_ROOT", root)

    assert knowledge_cli.main(["import", str(source), "--metadata", '{"owner":"test"}']) == 0
    imported = json.loads(capsys.readouterr().out)
    assert imported["created"] is True
    assert knowledge_cli.main(["list"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"][0]["metadata"] == {"owner": "test"}
    assert knowledge_cli.main(["search", "水果", "--method", "hybrid", "--rerank"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["source"] == "cli.md"
    assert knowledge_cli.main(["delete", imported["document_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["deleted"] is True


@pytest.mark.parametrize(
    ("source_name", "data", "message"),
    [
        ("../escape.txt", b"content", "plain file name"),
        ("notes.pdf", b"content", ".txt, .md, or .json"),
        ("bad.json", b"{", "JSON is invalid"),
        ("empty.md", b"  \n", "source is empty"),
    ],
)
def test_import_rejects_unsafe_or_invalid_sources(
    tmp_path: Path, monkeypatch, source_name: str, data: bytes, message: str
) -> None:
    root = configure_knowledge_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=settings_for_tests(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    with pytest.raises(KnowledgeValidationError, match=re.escape(message)):
        service.import_document(source_name, data)
