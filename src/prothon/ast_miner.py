from __future__ import annotations

import ast
from pathlib import Path


class ASTPatternMiner:
    """Extracts signature-only patterns from Python source code.

    Satisfies R13 and R25-R26 by using AST analysis to discover
    existing conventions without including implementation logic.
    """

    def scan_directory(self, root: Path) -> str:
        """Scan a directory recursively and return a string of signatures.

        Args:
            root: The root directory to scan.

        Returns:
            A string containing discovered signatures grouped by file.
        """
        results = []
        # Sort for deterministic output
        for path in sorted(root.rglob("*.py")):
            # Skip hidden files/dirs, virtualenvs, etc.
            if any(part.startswith(".") for part in path.parts) or "venv" in path.parts:
                continue

            signatures = self.extract_from_file(path)
            if signatures:
                rel_path = path.relative_to(root)
                results.append(f"### {rel_path}\n\n```python\n{signatures}\n```")

        return "\n\n".join(results)

    def extract_from_file(self, path: Path) -> str:
        """Extract top-level signatures from a single Python file.

        Args:
            path: Path to the Python file.

        Returns:
            A string containing unparsed signature-only nodes.
        """
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            return ""

        nodes = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                # Work on a copy to avoid mutating the original tree if needed,
                # but here we just need the unparsed result.
                stripped = self._strip_node(node)
                nodes.append(ast.unparse(stripped))

        return "\n\n".join(nodes)

    def _strip_node(self, node: ast.AST) -> ast.AST:
        """Remove implementation logic from a node recursively.

        Replaces bodies of functions and classes with Ellipsis to
        satisfy the signature-only constraint.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Keep only the signature by replacing the body
            # We use Ellipsis (...) as it's the standard Pythonic way
            node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
            return node

        if isinstance(node, ast.ClassDef):
            new_body: list[ast.stmt] = []
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    stripped = self._strip_node(item)
                    if isinstance(stripped, ast.stmt):
                        new_body.append(stripped)

            if not new_body:
                new_body = [ast.Pass()]

            node.body = new_body
            return node

        return node
