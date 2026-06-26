"""
test_retrieval.py
Unit tests for chunk splitter, FAISS index, and semantic ranker.
Heavy model tests are marked with @pytest.mark.slow and skipped by default.

Run all:       pytest tests/test_retrieval.py
Run fast only: pytest tests/test_retrieval.py -m "not slow"
"""

import pickle
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from retrieval.chunk_splitter import ChunkSplitter, CodeChunk
from retrieval.faiss_index import FAISSIndex, SearchResult


# ── ChunkSplitter ─────────────────────────────────────────────────────────

class TestChunkSplitter:
    def test_extracts_functions_as_chunks(self, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(
            "def login(user, pw):\n"
            "    return user == pw\n"
            "\n"
            "def logout(session):\n"
            "    session.clear()\n"
        )
        chunks = ChunkSplitter().split_file(src, "sample.py")
        names = [c.name for c in chunks]
        assert "login" in names
        assert "logout" in names

    def test_extracts_classes_as_chunks(self, tmp_path):
        src = tmp_path / "auth.py"
        src.write_text("class SessionManager:\n    pass\n")
        chunks = ChunkSplitter().split_file(src, "auth.py")
        assert any(c.type == "class" and c.name == "SessionManager" for c in chunks)

    def test_falls_back_to_module_chunk_on_empty_file(self, tmp_path):
        src = tmp_path / "empty.py"
        src.write_text("# just a comment\nMY_CONST = 42\n")
        chunks = ChunkSplitter().split_file(src, "empty.py")
        assert len(chunks) == 1
        assert chunks[0].type == "module"

    def test_chunk_id_format(self, tmp_path):
        src = tmp_path / "utils.py"
        src.write_text("def helper(): pass\n")
        chunks = ChunkSplitter().split_file(src, "utils/utils.py")
        assert chunks[0].chunk_id == "utils/utils.py::helper"

    def test_handles_syntax_error_gracefully(self, tmp_path):
        src = tmp_path / "broken.py"
        src.write_text("def bad(:\n    pass")
        chunks = ChunkSplitter().split_file(src, "broken.py")
        # Should return a module chunk with whatever content it got
        assert len(chunks) >= 1

    def test_split_repository_uses_index(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("def foo(): pass\n")
        f2 = tmp_path / "b.py"
        f2.write_text("def bar(): pass\n")

        index = {
            "a.py": {"abs_path": str(f1)},
            "b.py": {"abs_path": str(f2)},
        }
        chunks = ChunkSplitter().split_repository(index, tmp_path)
        file_paths = {c.file_path for c in chunks}
        assert "a.py" in file_paths
        assert "b.py" in file_paths


# ── FAISSIndex ────────────────────────────────────────────────────────────

def _make_chunks(n: int) -> list[CodeChunk]:
    return [
        CodeChunk(
            chunk_id=f"file_{i}.py::func_{i}",
            file_path=f"file_{i}.py",
            abs_path=f"/repo/file_{i}.py",
            type="function",
            name=f"func_{i}",
            start_line=1,
            end_line=5,
            content=f"def func_{i}(): pass",
        )
        for i in range(n)
    ]


def _random_embeddings(n: int, dim: int = 384) -> np.ndarray:
    rng = np.random.default_rng(42)
    vecs = rng.random((n, dim)).astype(np.float32)
    # L2-normalize (simulates BGE output)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


class TestFAISSIndex:
    def test_build_and_search(self):
        chunks = _make_chunks(10)
        embeddings = _random_embeddings(10)

        idx = FAISSIndex()
        idx.build(chunks, embeddings)

        assert idx.total_chunks == 10

        query = _random_embeddings(1)
        results = idx.search(query, top_k=3)
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].score >= results[1].score   # sorted descending

    def test_save_and_load(self, tmp_path):
        chunks = _make_chunks(5)
        embeddings = _random_embeddings(5)

        idx = FAISSIndex()
        idx.build(chunks, embeddings)
        idx.save(tmp_path)

        loaded = FAISSIndex.load(tmp_path)
        assert loaded.total_chunks == 5

        query = _random_embeddings(1)
        results = loaded.search(query, top_k=2)
        assert len(results) == 2

    def test_stats(self):
        chunks = _make_chunks(6)
        embeddings = _random_embeddings(6)

        idx = FAISSIndex()
        idx.build(chunks, embeddings)
        stats = idx.stats()

        assert stats["total_chunks"] == 6
        assert "unique_files" in stats
        assert "chunk_types" in stats

    def test_search_before_build_raises(self):
        idx = FAISSIndex()
        with pytest.raises(RuntimeError):
            idx.search(_random_embeddings(1))

    def test_mismatch_raises(self):
        chunks = _make_chunks(5)
        embeddings = _random_embeddings(3)   # wrong count
        idx = FAISSIndex()
        with pytest.raises(AssertionError):
            idx.build(chunks, embeddings)


# ── SemanticRanker (mocked embedder) ─────────────────────────────────────

class TestSemanticRanker:
    def _make_ranker(self, chunks, embeddings):
        from retrieval.semantic_ranker import SemanticRanker
        from retrieval.embedder import Embedder

        faiss_idx = FAISSIndex()
        faiss_idx.build(chunks, embeddings)

        mock_embedder = MagicMock(spec=Embedder)
        mock_embedder.embed_query.return_value = _random_embeddings(1)

        return SemanticRanker(
            embedder=mock_embedder,
            faiss_index=faiss_idx,
            chunk_top_k=10,
            max_files=5,
        )

    def test_rank_returns_results(self):
        from issue_analysis.issue_fetcher import GitHubIssue

        chunks = _make_chunks(10)
        embeddings = _random_embeddings(10)
        ranker = self._make_ranker(chunks, embeddings)

        issue = GitHubIssue(
            number=1, title="login bug", body="session fails",
            author="user", state="open", url="http://x",
        )
        results = ranker.rank(issue)
        assert len(results) > 0
        assert results[0].score >= results[-1].score

    def test_rank_to_tuples_shape(self):
        from issue_analysis.issue_fetcher import GitHubIssue

        chunks = _make_chunks(6)
        embeddings = _random_embeddings(6)
        ranker = self._make_ranker(chunks, embeddings)

        issue = GitHubIssue(
            number=2, title="auth error", body="",
            author="user", state="open", url="http://x",
        )
        tuples = ranker.rank_to_tuples(issue)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in tuples)


# ── Slow tests (require actual BGE model download) ────────────────────────

@pytest.mark.slow
class TestEmbedderIntegration:
    def test_embed_query_shape(self):
        from retrieval.embedder import Embedder
        emb = Embedder()
        vec = emb.embed_query("login fails after session timeout")
        assert vec.shape == (1, emb.dim)
        assert vec.dtype == np.float32

    def test_embed_corpus_normalized(self):
        from retrieval.embedder import Embedder
        emb = Embedder()
        vecs = emb.embed_corpus(["def login(): pass", "class Session: pass"])
        norms = np.linalg.norm(vecs, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)
