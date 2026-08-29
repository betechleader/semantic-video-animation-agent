from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import KNOWLEDGE_ROOT, PROJECT_ROOT, SETTINGS
from .knowledge_base import KnowledgeBaseError, KnowledgeBaseService


def _project_source(path_text: str) -> Path:
    path = Path(path_text).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise KnowledgeBaseError("CLI import source must be inside the project directory") from exc
    if not path.is_file():
        raise KnowledgeBaseError("CLI import source does not exist or is not a file")
    return path


def _metadata(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError("metadata must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("metadata must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the project-local knowledge base")
    commands = parser.add_subparsers(dest="command", required=True)

    import_parser = commands.add_parser("import", help="Import a UTF-8 txt, md, or json file")
    import_parser.add_argument("path")
    import_parser.add_argument("--metadata", type=_metadata, default={})

    commands.add_parser("list", help="List imported knowledge documents")

    search_parser = commands.add_parser("search", help="Search indexed project knowledge")
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--method", choices=("keyword", "vector", "hybrid"), default="hybrid"
    )
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--rerank", action="store_true")

    delete_parser = commands.add_parser("delete", help="Delete one indexed document")
    delete_parser.add_argument("document_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = KnowledgeBaseService(root=KNOWLEDGE_ROOT, settings=SETTINGS)
    try:
        if args.command == "import":
            source = _project_source(args.path)
            result = service.import_document(source.name, source.read_bytes(), args.metadata)
        elif args.command == "list":
            result = {"documents": service.list_documents()}
        elif args.command == "search":
            result = service.search(
                args.query,
                method=args.method,
                limit=args.limit,
                rerank=args.rerank,
            )
        else:
            result = service.delete_document(args.document_id)
    except KnowledgeBaseError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
