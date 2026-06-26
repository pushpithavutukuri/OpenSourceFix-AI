"""
dependency_graph.py
Builds a file-level dependency graph from parsed import data.
"""

import logging
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

from repository_analysis.code_parser import ParsedFile

logger = logging.getLogger(__name__)


class DependencyGraph:
    """
    Maps each file to the modules it imports.

    Later this will resolve imports to actual repository files,
    enabling a true reverse-dependency lookup.
    """

    def __init__(self):
        # file_path (str) → set of imported module names
        self._graph: Dict[str, Set[str]] = defaultdict(set)

    def build(self, parsed_files: List[ParsedFile]) -> None:
        """
        Populate the graph from a list of ParsedFile objects.

        Args:
            parsed_files: Output of CodeParser.parse_files().
        """
        for pf in parsed_files:
            key = str(pf.path)
            for imp in pf.imports:
                self._graph[key].add(imp)

        logger.info("Dependency graph built for %d files.", len(self._graph))

    def get_dependencies(self, file_path: Path) -> Set[str]:
        """Return the set of imports for a given file."""
        return self._graph.get(str(file_path), set())

    def to_dict(self) -> Dict[str, List[str]]:
        """Serialize the graph to a plain dict (JSON-friendly)."""
        return {k: sorted(v) for k, v in self._graph.items()}

    def files_importing(self, module_name: str) -> List[str]:
        """
        Reverse lookup: which files import a given module?

        Useful for understanding blast radius of a change.
        """
        return [
            file
            for file, imports in self._graph.items()
            if module_name in imports
        ]
