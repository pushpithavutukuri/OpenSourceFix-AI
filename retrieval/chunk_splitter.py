"""
chunk_splitter.py

Splits Python source files into semantically meaningful chunks
before embedding. Each chunk = one function or class body.

Why chunking matters:
    A 1000-line file embedded as one vector loses all granularity.
    Embedding function-by-function lets FAISS find the exact
    function relevant to the issue, not just the file.

Chunk schema:
    {
        "chunk_id":   "auth/session.py::refresh_token",
        "file_path":  "auth/session.py",        # relative
        "abs_path":   "/repo/auth/session.py",
        "type":       "function" | "class" | "module",
        "name":       "refresh_token",
        "start_line": 42,
        "end_line":   61,
        "content":    "def refresh_token(...):\n    ..."
    }
"""

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 2000   # keep embedding input manageable


@dataclass
class CodeChunk:
    chunk_id: str          # unique: "rel_path::name"
    file_path: str         # relative to repo root
    abs_path: str
    type: str              # "function" | "class" | "module"
    name: str
    start_line: int
    end_line: int
    content: str


class ChunkSplitter:
    """
    Splits each Python file into function/class-level chunks.
    Falls back to a whole-file "module" chunk for files with no
    top-level definitions (e.g. config files, __init__.py).
    """

    def split_file(self, abs_path: Path, rel_path: str) -> List[CodeChunk]:
        """
        Parse and chunk one file.

        Args:
            abs_path: Absolute path to the .py file.
            rel_path: Path relative to repo root (used as chunk_id prefix).

        Returns:
            List of CodeChunk objects.
        """
        try:
            source = abs_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except Exception as exc:
            logger.warning("Cannot parse %s: %s", abs_path, exc)
            return self._module_chunk(abs_path, rel_path, source)

        lines = source.splitlines()
        chunks: List[CodeChunk] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            # Only top-level and one level deep (methods inside classes)
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 1)
            body_lines = lines[start:end]
            content = "\n".join(body_lines)[:MAX_CHUNK_CHARS]

            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            chunk_id = f"{rel_path}::{node.name}"

            chunks.append(CodeChunk(
                chunk_id=chunk_id,
                file_path=rel_path,
                abs_path=str(abs_path),
                type=kind,
                name=node.name,
                start_line=node.lineno,
                end_line=end,
                content=content,
            ))

        if not chunks:
            chunks = self._module_chunk(abs_path, rel_path, source)

        return chunks

    def split_repository(
        self,
        index: dict,          # RepoIndex from RepositoryIndexer
        repo_root: Path,
    ) -> List[CodeChunk]:
        """
        Chunk every file in the repository index.

        Returns:
            Flat list of all CodeChunk objects across the repo.
        """
        all_chunks: List[CodeChunk] = []
        for rel_path, meta in index.items():
            abs_path = Path(meta.get("abs_path", ""))
            if not abs_path.exists():
                continue
            chunks = self.split_file(abs_path, rel_path)
            all_chunks.extend(chunks)

        logger.info(
            "ChunkSplitter: %d chunks from %d files.",
            len(all_chunks), len(index)
        )
        return all_chunks

    # ── private ────────────────────────────────────────────────────────────

    def _module_chunk(
        self, abs_path: Path, rel_path: str, source: str
    ) -> List[CodeChunk]:
        """Fallback: treat the whole file as one chunk."""
        return [CodeChunk(
            chunk_id=f"{rel_path}::__module__",
            file_path=rel_path,
            abs_path=str(abs_path),
            type="module",
            name="__module__",
            start_line=1,
            end_line=source.count("\n") + 1,
            content=source[:MAX_CHUNK_CHARS],
        )]
