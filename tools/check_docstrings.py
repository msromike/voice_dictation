#!/usr/bin/env python3
"""Enforce the two-line comment cap from CLAUDE.md. No stock linter rule does this."""
import ast
import sys
from pathlib import Path

MAX_LINES = 2
ROOT = Path(__file__).parent.parent
SCAN = ["voice-dictation", "tools"]


def check_docstrings(path, src):
    """Yield (line, kind, count) for each docstring over the cap"""
    tree = ast.parse(src, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        count = len(doc.strip().splitlines())
        if count > MAX_LINES:
            line = node.body[0].lineno if node.body else 1
            name = getattr(node, "name", "<module>")
            yield line, f"docstring for '{name}'", count


def check_comment_blocks(src):
    """Yield (line, kind, count) for each run of consecutive # lines over the cap"""
    run_start, run = 0, 0
    for lineno, text in enumerate(src.splitlines(), 1):
        if text.lstrip().startswith("#"):
            if run == 0:
                run_start = lineno
            run += 1
        else:
            if run > MAX_LINES:
                yield run_start, "comment block", run
            run = 0
    if run > MAX_LINES:
        yield run_start, "comment block", run


def targets(argv):
    """Yield paths to check: the file given on argv, else everything in SCAN"""
    if argv:
        path = Path(argv[0]).resolve()
        if path.suffix == ".py" and path.exists():
            yield path
        return
    for folder in SCAN:
        yield from sorted((ROOT / folder).rglob("*.py"))


def main():
    argv = sys.argv[1:]
    violations = 0
    for path in targets(argv):
        src = path.read_text(encoding="utf-8")
        found = list(check_docstrings(path, src)) + list(check_comment_blocks(src))
        for line, kind, count in sorted(found):
            try:
                rel = path.relative_to(ROOT)
            except ValueError:
                rel = path
            print(f"{rel}:{line}: {kind} is {count} lines, cap is {MAX_LINES}")
            violations += 1

    # A single-file run is hook feedback; stay silent when it is clean.
    if not argv:
        print(f"\n{violations} violation(s), cap {MAX_LINES} lines "
              f"(CLAUDE.md ## Code)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
