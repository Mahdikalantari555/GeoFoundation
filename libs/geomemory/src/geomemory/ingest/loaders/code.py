"""Python/JavaScript/GEE code loader with AST-based structural extraction."""

from __future__ import annotations

import ast
import collections
import io
import tokenize
from collections.abc import Iterable

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.loaders.base import source_bytes


class CodeLoader:
    """Parse source code into a text document plus AST-derived code units.

    For Python, ``ast`` extracts function/class definitions with signatures,
    docstrings, and line spans. JavaScript/GEE are parsed with a lightweight
    regex-based top-level function extraction fallback.
    """

    def supports(self, source: SourceRef) -> bool:
        if source.path is None:
            return False
        suffix = source.path.lower()
        return suffix.endswith((".py", ".js", ".mjs", ".gee"))

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        raw = source_bytes(source)
        text = raw.decode("utf-8", errors="replace")
        title = source.path.split("/")[-1] if source.path else "Untitled"
        mime = "text/x-python" if source.path.endswith(".py") else "text/javascript"

        units: list[dict[str, str | int | None]] = []
        units = _parse_python(text) if mime == "text/x-python" else _parse_js(text)

        yield ParsedObject(
            source=source,
            mime_type=mime,
            title=title,
            text=text,
            metadata={
                "loader": "CodeLoader",
                "language": "python" if mime == "text/x-python" else "javascript",
                "code_units": units,
            },
        )


def _parse_python(text: str) -> list[dict[str, str | int | None]]:
    """Extract function and class definitions using the ast module."""
    units: list[dict[str, str | int | None]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return units
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            units.append(
                {
                    "type": "class" if isinstance(node, ast.ClassDef) else "function",
                    "name": node.name,
                    "signature": _signature(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "",
                    "docstring": docstring or "",
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno) or node.lineno,
                }
            )
    return units


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstruct a function signature from its arguments."""
    parts: list[str] = []
    posonly = getattr(node.args, "posonlyargs", [])
    args = list(posonly) + list(node.args.args)
    vararg = node.args.vararg
    kwonly = node.args.kwonlyargs
    kwarg = node.args.kwarg
    for arg in args:
        parts.append(arg.arg)
    if vararg:
        parts.append(f"*{vararg.arg}")
    elif kwonly:
        parts.append("*")
    for arg in kwonly:
        parts.append(f"{arg.arg}")
    if kwarg:
        parts.append(f"**{kwarg.arg}")
    return f"{node.name}({', '.join(parts)})"


def _parse_js(text: str) -> list[dict[str, str | int | None]]:
    """Lightweight top-level function extraction for JS/GEE scripts."""
    units: list[dict[str, str | int | None]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("function ", "async function ", "var ", "const ", "let ")) and "=" in stripped:
            name = _extract_js_name(stripped)
            if name:
                units.append(
                    {
                        "type": "function",
                        "name": name,
                        "start_line": i,
                        "end_line": i,
                    }
                )
    return units


def _extract_js_name(line: str) -> str | None:
    """Extract a function/variable name from a JS declaration line."""
    for prefix in ("async function ", "function ", "var ", "const ", "let "):
        if line.startswith(prefix):
            remainder = line[len(prefix) :]
            name = remainder.split("(")[0].split("=")[0].split()[0].strip()
            if name and name.isidentifier():
                return name
    return None


class NotebookLoader:
    """Load Jupyter notebooks cell by cell."""

    def supports(self, source: SourceRef) -> bool:
        return bool(source.path and source.path.lower().endswith(".ipynb"))

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        import json

        raw = source_bytes(source)
        nb = json.loads(raw.decode("utf-8", errors="replace"))
        cells = nb.get("cells", [])
        cell_texts: list[str] = []
        for idx, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "code")
            lines = cell.get("source", [])
            if isinstance(lines, str):
                lines = [lines]
            content = "".join(lines)
            cell_texts.append(f"<!-- cell {idx} [{cell_type}] -->\n{content}")
        full_text = "\n\n".join(cell_texts)
        yield ParsedObject(
            source=source,
            mime_type="application/x-ipynb+json",
            title=source.path.split("/")[-1] if source.path else "Untitled",
            text=full_text,
            metadata={
                "loader": "NotebookLoader",
                "cell_count": len(cells),
                "language": nb.get("metadata", {}).get("language_info", {}).get("name", "python"),
            },
        )


def detect_indentation(text: str) -> int:
    """Return the common leading-space indentation width (0 if none)."""
    if not text:
        return 0
    counter: collections.Counter[int] = collections.Counter()
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if stripped and line.startswith(" "):
            counter[len(line) - len(stripped)] += 1
    return counter.most_common(1)[0][0] if counter else 0


def strip_comments(text: str) -> str:
    """Remove Python comments while preserving strings and indentation."""
    try:
        output: list[str] = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                output.append(" " * len(tok.string))
            else:
                output.append(tok.string)
        return "".join(output)
    except (tokenize.TokenError, IndentationError):
        return text
