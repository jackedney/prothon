from __future__ import annotations

import ast
from pathlib import Path

from prothon.refactor.models import (
    ModuleMetrics,
    PatternOccurrence,
    PatternType,
    SimilarityGroup,
)


def collect_module_metrics(root: Path) -> list[ModuleMetrics]:
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    modules: dict[Path, ModuleMetrics] = {}
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        metrics = _parse_module_metrics(py_file)
        if metrics is not None:
            modules[py_file] = metrics

    _count_inbound_imports(modules, src_dir)
    return list(modules.values())


def _parse_module_metrics(py_file: Path) -> ModuleMetrics | None:
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None

    lines = source.splitlines()
    public_funcs = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    )
    import_count = sum(
        1 for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)
    )
    return ModuleMetrics(
        path=py_file,
        line_count=len(lines),
        public_function_count=public_funcs,
        import_count=import_count,
        imported_by_count=0,
    )


def _count_inbound_imports(modules: dict[Path, ModuleMetrics], src_dir: Path) -> None:
    fqn_to_path = _build_fqn_map(modules, src_dir)
    for py_file in modules:
        targets = _extract_import_targets(py_file, src_dir, fqn_to_path)
        for target in targets:
            modules[target].imported_by_count += 1


def _build_fqn_map(
    modules: dict[Path, ModuleMetrics], src_dir: Path
) -> dict[str, Path]:
    fqn_map: dict[str, Path] = {}
    for py_file in modules:
        rel = py_file.relative_to(src_dir)
        fqn = ".".join(rel.with_suffix("").parts)
        fqn_map[fqn] = py_file
    return fqn_map


def _extract_import_targets(
    py_file: Path, src_dir: Path, fqn_to_path: dict[str, Path]
) -> set[Path]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()

    rel = py_file.relative_to(src_dir)
    importer_parts = list(rel.with_suffix("").parts)
    importer_pkg = importer_parts[:-1]

    targets: set[Path] = set()
    for node in ast.walk(tree):
        candidates = _resolve_import_fqns(node, importer_pkg)
        for resolved in candidates:
            target = fqn_to_path.get(resolved)
            if target and target != py_file:
                targets.add(target)
        if isinstance(node, ast.ImportFrom) and candidates:
            _resolve_submodule_imports(
                node, candidates[0], fqn_to_path, py_file, targets
            )
    return targets


def _resolve_import_fqns(node: ast.AST, importer_pkg: list[str]) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        result = _resolve_import_from(node, importer_pkg)
        return [result] if result else []
    return []


def _resolve_import_from(node: ast.ImportFrom, importer_pkg: list[str]) -> str | None:
    module = node.module or ""
    if not node.level or node.level == 0:
        return module or None
    base_parts = importer_pkg[: len(importer_pkg) - (node.level - 1)]
    if module:
        return ".".join(base_parts + [module]) if base_parts else module
    return ".".join(base_parts) if base_parts else None


def _resolve_submodule_imports(
    node: ast.ImportFrom,
    base_fqn: str,
    fqn_to_path: dict[str, Path],
    py_file: Path,
    targets: set[Path],
) -> None:
    for alias in node.names:
        candidate = f"{base_fqn}.{alias.name}"
        target = fqn_to_path.get(candidate)
        if target and target != py_file:
            targets.add(target)


def collect_pattern_usage(root: Path) -> list[PatternOccurrence]:
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    occurrences: list[PatternOccurrence] = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        occurrences.extend(_scan_file_patterns(tree, py_file))

    return occurrences


def _scan_file_patterns(tree: ast.AST, py_file: Path) -> list[PatternOccurrence]:
    results: list[PatternOccurrence] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and _try_body_has_file_io(node):
            results.append(
                PatternOccurrence(
                    pattern_type=PatternType.TRY_EXCEPT_FILE_IO,
                    file_path=py_file,
                    line_number=node.lineno,
                )
            )

        if (
            isinstance(node, ast.If)
            and _is_path_exists_check(node.test)
            and _has_guard_action(node)
        ):
            results.append(
                PatternOccurrence(
                    pattern_type=PatternType.PATH_EXISTS_GUARD,
                    file_path=py_file,
                    line_number=node.lineno,
                )
            )
    return results


def _try_body_has_file_io(node: ast.Try) -> bool:
    for stmt in node.body:
        for body_node in ast.walk(stmt):
            if isinstance(body_node, ast.Call) and _is_file_io_call(body_node):
                return True
    return False


def _is_file_io_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in (
            "read_text",
            "write_text",
            "read_bytes",
            "write_bytes",
        )
    if isinstance(node.func, ast.Name):
        return node.func.id == "open"
    return False


def _is_path_exists_check(node: ast.expr) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_path_exists_check(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in ("exists", "is_file", "is_dir")
    return False


def _has_guard_action(node: ast.If) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.Return | ast.Raise | ast.Continue | ast.Break):
            return True
    return False


def collect_cross_module_similarities(root: Path) -> list[SimilarityGroup]:
    src_dir = root / "src"
    if not src_dir.exists():
        return []

    func_map: dict[tuple[str, tuple[str, ...]], list[SimilarityGroup]] = {}
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        for entry in _extract_public_signatures(py_file):
            key = (entry.function_name, tuple(entry.parameters))
            func_map.setdefault(key, []).append(entry)

    results: list[SimilarityGroup] = []
    for entries in func_map.values():
        files = {e.file_path for e in entries}
        if len(files) > 1:
            results.extend(entries)
    return results


def _canonical_params(args: ast.arguments) -> list[str]:
    params: list[str] = []
    for arg in args.posonlyargs:
        if arg.arg not in {"self", "cls"}:
            params.append(arg.arg)
    for arg in args.args:
        if arg.arg not in {"self", "cls"}:
            params.append(arg.arg)
    if args.vararg:
        params.append(f"*{args.vararg.arg}")
    for arg in args.kwonlyargs:
        params.append(arg.arg)
    if args.kwarg:
        params.append(f"**{args.kwarg.arg}")
    return params


def _extract_public_signatures(py_file: Path) -> list[SimilarityGroup]:
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    entries: list[SimilarityGroup] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            params = _canonical_params(node.args)
            entries.append(
                SimilarityGroup(
                    function_name=node.name,
                    file_path=py_file,
                    parameters=params,
                )
            )
    return entries
