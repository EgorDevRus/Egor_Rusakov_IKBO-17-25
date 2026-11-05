"""Repository style checker for the rules listed in the assignment.

The checker intentionally duplicates a tiny subset of flake8/radon so
that the project can be verified on a machine where those tools are not
installed.  It checks line length, file and function size, argument
counts, docstrings, identifier naming, comparison magic numbers and
cyclomatic complexity.
"""

import ast
import re
import sys
from pathlib import Path

MAX_LINE = 80
MAX_FILE_LINES = 1000
MAX_FUNCTION_LINES = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10
MAGIC_ALLOWED = frozenset({0, 1, 2})
REQUIRE_DOCSTRINGS = ("src", "tools", "tests")
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
COMPLEXITY_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.IfExp,
    ast.Assert,
)
_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
UNITTEST_METHODS = frozenset({
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "asyncSetUp", "asyncTearDown",
})
_CLASS_RE = re.compile(r"^_?[A-Z][A-Za-z0-9]*$")


def _python_files(arguments: list[str]) -> list[Path]:
    """Collect Python files from the supplied paths."""
    roots = [Path(item) for item in arguments] or [Path("src"),
                                                    Path("tools"),
                                                    Path("tests")]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
    return files


def _own_nodes(node: ast.AST):
    """Yield descendants without entering nested definitions."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (
            ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
        )):
            continue
        yield child
        yield from _own_nodes(child)


def _complexity(node: ast.AST) -> int:
    """Compute cyclomatic complexity of one function."""
    total = 1
    for child in _own_nodes(node):
        if isinstance(child, COMPLEXITY_NODES):
            total += 1
        elif isinstance(child, ast.BoolOp):
            total += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            total += len(child.ifs)
    return total


def _arguments(node: ast.AST) -> int:
    """Count declared arguments, ignoring self and cls."""
    arguments = list(node.args.posonlyargs) + list(node.args.args)
    arguments += list(node.args.kwonlyargs)
    if arguments and arguments[0].arg in {"self", "cls"}:
        arguments = arguments[1:]
    extra = int(node.args.vararg is not None)
    extra += int(node.args.kwarg is not None)
    return len(arguments) + extra


def _magic_number(node: ast.AST) -> bool:
    """Return true for a non-structural numeric literal."""
    if not isinstance(node, ast.Constant):
        return False
    value = node.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value not in MAGIC_ALLOWED


def _check_identifiers(node: ast.AST, path: Path) -> list[str]:
    """Check PEP 8 naming for classes, functions and arguments."""
    issues: list[str] = []
    if isinstance(node, ast.ClassDef):
        if _CLASS_RE.match(node.name) is None:
            issues.append(
                f"{path}:{node.lineno}: class name {node.name!r} is not "
                "CapWords"
            )
        return issues
    if not isinstance(node, FUNCTION_NODES):
        return issues
    if node.name in UNITTEST_METHODS:
        return issues
    if _NAME_RE.match(node.name) is None:
        issues.append(
            f"{path}:{node.lineno}: function name {node.name!r} is not "
            "snake_case"
        )
    for argument in node.args.args + node.args.kwonlyargs:
        if argument.arg in {"self", "cls"}:
            continue
        if _NAME_RE.match(argument.arg) is None:
            issues.append(
                f"{path}:{node.lineno}: argument name "
                f"{argument.arg!r} is not snake_case"
            )
    return issues


def _function_issues(node: ast.AST, path: Path) -> list[str]:
    """Check length, argument count and complexity of a function."""
    issues: list[str] = []
    if not isinstance(node, FUNCTION_NODES):
        return issues
    length = node.end_lineno - node.lineno + 1
    if length > MAX_FUNCTION_LINES:
        issues.append(
            f"{path}:{node.lineno}: function {node.name!r} is "
            f"{length} lines long (> {MAX_FUNCTION_LINES})"
        )
    arguments = _arguments(node)
    if arguments > MAX_ARGUMENTS:
        issues.append(
            f"{path}:{node.lineno}: function {node.name!r} has "
            f"{arguments} arguments (> {MAX_ARGUMENTS})"
        )
    complexity = _complexity(node)
    if complexity > MAX_COMPLEXITY:
        issues.append(
            f"{path}:{node.lineno}: function {node.name!r} has "
            f"cyclomatic complexity {complexity} (> {MAX_COMPLEXITY})"
        )
    return issues


def _docstring_issues(
    node: ast.AST, path: Path, check_docs: bool
) -> list[str]:
    """Check that public and private definitions are documented."""
    is_definition = isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    )
    if not is_definition or not check_docs:
        return []
    if ast.get_docstring(node) is not None:
        return []
    return [f"{path}:{node.lineno}: {node.name!r} has no docstring"]


def _magic_issues(node: ast.AST, path: Path) -> list[str]:
    """Report magic numeric literals used in comparisons."""
    if not isinstance(node, ast.Compare):
        return []
    issues: list[str] = []
    for value in [node.left, *node.comparators]:
        if _magic_number(value):
            issues.append(
                f"{path}:{node.lineno}: magic number {value.value!r} "
                "in a comparison"
            )
    return issues


def _check_node(node: ast.AST, path: Path, check_docs: bool) -> list[str]:
    """Run all per-node checks and return their issues."""
    issues = _docstring_issues(node, path, check_docs)
    issues.extend(_function_issues(node, path))
    issues.extend(_magic_issues(node, path))
    issues.extend(_check_identifiers(node, path))
    return issues


def check_file(path: Path) -> list[str]:
    """Check one Python file and return human-readable issues."""
    issues: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: cannot read file: {exc}"]
    lines = source.splitlines()
    if len(lines) > MAX_FILE_LINES:
        issues.append(
            f"{path}:1: file is {len(lines)} lines long "
            f"(> {MAX_FILE_LINES})"
        )
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE:
            issues.append(
                f"{path}:{number}: line is {len(line)} characters "
                f"(> {MAX_LINE})"
            )
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: syntax error: {exc.msg}"]
    check_docs = any(part in REQUIRE_DOCSTRINGS for part in path.parts)
    if check_docs and ast.get_docstring(tree) is None:
        issues.append(f"{path}:1: module has no docstring")
    for node in ast.walk(tree):
        issues.extend(_check_node(node, path, check_docs))
    return issues


def main(arguments: list[str]) -> int:
    """Run the checker and return a process exit code."""
    files = _python_files(arguments)
    issues: list[str] = []
    for path in files:
        issues.extend(check_file(path))
    for issue in issues:
        print(issue)
    print(f"checked {len(files)} files, found {len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
