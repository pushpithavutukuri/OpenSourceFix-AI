"""
code_parser.py
Parses Python source files using the built-in AST module.
Extracts functions, classes, and imports.
"""

import ast
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedFile:
    path: Path
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    error: Optional[str] = None


class CodeParser:
    """Extract structural information from Python files via AST."""

    def parse_file(self, file_path: Path) -> ParsedFile:
        """
        Parse a single Python file.

        Args:
            file_path: Absolute path to a .py file.

        Returns:
            ParsedFile with extracted metadata.
        """
        result = ParsedFile(path=file_path)

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError as exc:
            result.error = str(exc)
            logger.warning("Syntax error in %s: %s", file_path, exc)
            return result
        except Exception as exc:
            result.error = str(exc)
            logger.warning("Could not parse %s: %s", file_path, exc)
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                result.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                result.classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result.imports.append(node.module)

        return result

    def parse_files(self, file_paths: List[Path]) -> List[ParsedFile]:
        """Parse multiple files and return all results."""
        return [self.parse_file(p) for p in file_paths]
