"""
test_repository_analysis.py
Unit tests for the repository analysis pipeline.
"""

import ast
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from repository_analysis.file_scanner import FileScanner
from repository_analysis.code_parser import CodeParser
from repository_analysis.dependency_graph import DependencyGraph
from repository_analysis.file_ranker import FileRanker


# ── FileScanner ────────────────────────────────────────────────────────────

class TestFileScanner:
    def test_counts_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "c.txt").write_text("hello")

        result = FileScanner().scan(tmp_path)

        assert result.python_files == 2
        assert result.total_files == 3

    def test_skips_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")
        (tmp_path / "main.py").write_text("pass")

        result = FileScanner().scan(tmp_path)

        assert result.python_files == 1


# ── CodeParser ────────────────────────────────────────────────────────────

class TestCodeParser:
    def test_extracts_functions_classes_imports(self, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "\n"
            "class MyClass:\n"
            "    def my_method(self): pass\n"
            "\n"
            "def standalone(): pass\n"
        )

        result = CodeParser().parse_file(src)

        assert "standalone" in result.functions
        assert "my_method" in result.functions
        assert "MyClass" in result.classes
        assert "os" in result.imports
        assert "pathlib" in result.imports

    def test_handles_syntax_error_gracefully(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(:\n    pass")

        result = CodeParser().parse_file(bad)

        assert result.error is not None
        assert result.functions == []


# ── DependencyGraph ───────────────────────────────────────────────────────

class TestDependencyGraph:
    def test_reverse_lookup(self, tmp_path):
        from repository_analysis.code_parser import ParsedFile

        a = ParsedFile(path=tmp_path / "a.py", imports=["auth", "os"])
        b = ParsedFile(path=tmp_path / "b.py", imports=["auth"])

        graph = DependencyGraph()
        graph.build([a, b])

        files_using_auth = graph.files_importing("auth")
        assert len(files_using_auth) == 2


# ── FileRanker ────────────────────────────────────────────────────────────

class TestFileRanker:
    def test_ranks_by_keyword_match(self):
        index = {
            "auth/session.py": {
                "functions": ["login", "logout", "refresh_session"],
                "classes": [],
                "imports": [],
            },
            "utils/string_utils.py": {
                "functions": ["strip", "format"],
                "classes": [],
                "imports": [],
            },
        }
        keywords = ["login", "session"]

        ranked = FileRanker().rank(index, keywords)

        assert ranked[0][0] == "auth/session.py"
        assert ranked[0][1] > ranked[1][1] if len(ranked) > 1 else True

    def test_returns_empty_for_no_matches(self):
        index = {
            "foo.py": {"functions": [], "classes": [], "imports": []},
        }
        ranked = FileRanker().rank(index, ["nonexistent_xyz"])
        assert ranked == []
