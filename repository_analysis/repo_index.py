"""
repo_index.py
Builds a structured in-memory index of the entire repository.
This is the central data structure that downstream stages query.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from repository_analysis.code_parser import CodeParser, ParsedFile
from repository_analysis.file_scanner import FileScanner
from repository_analysis.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)

# Type alias for the index
RepoIndex = Dict[str, Dict[str, Any]]


class RepositoryIndexer:
    """
    Orchestrates scanning → parsing → indexing for a repository.

    Produces:
        {
            "relative/path/to/file.py": {
                "functions": [...],
                "classes":   [...],
                "imports":   [...],
                "abs_path":  "..."
            },
            ...
        }
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.scanner = FileScanner()
        self.parser = CodeParser()
        self.dep_graph = DependencyGraph()
        self._index: RepoIndex = {}

    def build(self) -> RepoIndex:
        """Scan, parse, and index the repository. Returns the index."""
        scan = self.scanner.scan(self.repo_path)
        parsed_files: List[ParsedFile] = self.parser.parse_files(scan.python_file_paths)
        self.dep_graph.build(parsed_files)

        for pf in parsed_files:
            rel = str(pf.path.relative_to(self.repo_path))
            self._index[rel] = {
                "functions": pf.functions,
                "classes": pf.classes,
                "imports": pf.imports,
                "abs_path": str(pf.path),
                "parse_error": pf.error,
            }

        logger.info("Repository index built — %d files indexed.", len(self._index))
        return self._index

    def save(self, output_path: Path) -> None:
        """Persist the index to a JSON file."""
        output_path.write_text(json.dumps(self._index, indent=2))
        logger.info("Index saved to %s", output_path)

    @property
    def index(self) -> RepoIndex:
        return self._index

    @property
    def dependency_graph(self) -> DependencyGraph:
        return self.dep_graph
