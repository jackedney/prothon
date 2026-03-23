from __future__ import annotations

import ast
from pathlib import Path


class IdiomMatcher:
    """Identifies and handles signatures for popular libraries.

    Supports FastAPI, Typer, and Pydantic by recognizing their
    specific decorators, default values, and class structures.
    """

    def __init__(self) -> None:
        self.idiom_names = {
            "Depends",
            "Query",
            "Path",
            "Body",
            "Header",
            "Cookie",
            "File",
            "Form",
            "Argument",
            "Option",
            "Field",
            "BaseModel",
            "BaseSettings",
            "SQLModel",
        }
        self.idiom_modules = {"typer", "fastapi", "pydantic", "typing", "dataclasses"}

    def is_idiom_name(self, name: str) -> bool:
        """Check if a name (possibly qualified) is a recognized idiom."""
        if not name:
            return False
        if "." in name:
            module = name.split(".")[0]
            if module in self.idiom_modules:
                return True
            attr = name.split(".")[-1]
            return attr in self.idiom_names
        return name in self.idiom_names

    def is_idiom_node(self, node: ast.AST) -> bool:
        """Check if a node represents a recognized idiom (e.g. Depends())."""
        name = self._get_name(node if not isinstance(node, ast.Call) else node.func)
        return self.is_idiom_name(name)

    def is_idiom_decorator(self, node: ast.AST) -> bool:
        """Check if a decorator node is a recognized idiom decorator."""
        name = self._get_name(node if not isinstance(node, ast.Call) else node.func)

        # FastAPI/Typer route/command decorators often look like @app.get("/")
        if "." in name:
            parts = name.split(".")
            attr = parts[-1]
            if attr in {
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "options",
                "head",
                "trace",
                "command",
            }:
                return True

        return self.is_idiom_name(name) or name in {
            "classmethod",
            "staticmethod",
            "property",
            "abstractmethod",
            "dataclass",
        }

    def _get_name(self, node: ast.AST) -> str:
        """Recursively get the name of a Name or Attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            val = self._get_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        return ""


class ASTPatternMiner:
    """Extracts signature-only patterns from Python source code.

    Satisfies R13 and R25-R26 by using AST analysis to discover
    existing conventions without including implementation logic.
    """

    def __init__(self, matcher: IdiomMatcher | None = None) -> None:
        self.matcher = matcher or IdiomMatcher()

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

    def _strip_node(self, node: ast.AST) -> ast.stmt:
        """Remove implementation logic from a node recursively.

        Replaces bodies of functions and classes with Ellipsis to
        satisfy the signature-only constraint.
        """
        if not isinstance(node, ast.stmt):
            # This should not happen given how it's called, but for safety:
            return ast.Pass()

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Clean decorators
            node.decorator_list = [
                dec
                for dec in node.decorator_list
                if self.matcher.is_idiom_decorator(dec)
            ]

            # Clean default values to avoid implementation logic
            self._clean_defaults(node)

            # Keep only the signature by replacing the body
            node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
            return node

        if isinstance(node, ast.ClassDef):
            is_idiom_class = any(
                self.matcher.is_idiom_name(self.matcher._get_name(base))
                for base in node.bases
            ) or any(
                self.matcher.is_idiom_decorator(dec) for dec in node.decorator_list
            )

            new_body: list[ast.stmt] = []
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    new_body.append(self._strip_node(item))
                elif is_idiom_class and isinstance(item, (ast.AnnAssign, ast.Assign)):
                    # Keep fields for data models (Pydantic, dataclasses, etc.)
                    new_body.append(item)

            if not new_body:
                new_body = [ast.Pass()]

            node.body = new_body
            return node

        return node

    def _clean_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Replaces complex default values with Ellipsis unless they are idioms."""
        for i, default in enumerate(node.args.defaults):
            if default and not self._is_safe_signature_expr(default):
                node.args.defaults[i] = ast.Constant(value=Ellipsis)

        for i, kw_default in enumerate(node.args.kw_defaults):
            if kw_default and not self._is_safe_signature_expr(kw_default):
                node.args.kw_defaults[i] = ast.Constant(value=Ellipsis)

    def _is_safe_signature_expr(self, node: ast.AST) -> bool:
        """Check if an expression is safe for a signature (no implementation logic)."""
        if isinstance(
            node,
            (
                ast.Constant,
                ast.Name,
                ast.Attribute,
                ast.List,
                ast.Dict,
                ast.Tuple,
                ast.Set,
            ),
        ):
            return True
        if self.matcher.is_idiom_node(node):
            return True
        # Handle Annotated[type, metadata]
        if isinstance(node, ast.Subscript):
            name = self.matcher._get_name(node.value)
            if name == "Annotated":
                return True
        return False
