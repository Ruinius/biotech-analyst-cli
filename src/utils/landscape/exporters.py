"""
Markdown/CSV exporters for competitive landscape tables.

Functions moved from the generate_landscape_table.py monolith (§3 decomposition).
"""

import csv
import io
import re


def _strip_md(text: str) -> str:
    """Remove Markdown formatting tokens from a cell value."""
    # Expand <br> to " / " (keep single-row layout)
    text = re.sub(r"<br\s*/?>", " / ", text, flags=re.IGNORECASE)
    # Remove bold/italic markers
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)  # single *
    text = re.sub(r"(?<!_)_(?!_)", "", text)  # single _
    # Remove markdown links [text](url) -> text only
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def md_table_to_text_table(md_text: str) -> str:
    """Reformat a pipe-delimited Markdown table so every column is space-padded and
    columns align perfectly when viewed in any plain-text editor.

    The output is still valid Markdown AND human-readable as raw text — exactly like
    a financial balance sheet table. Each cell is padded with spaces to the widest
    value in that column. <br> tags are collapsed to \" / \" inline. Markdown bold,
    italic, and link syntax is stripped from cell text.
    """
    raw_lines = [line.rstrip() for line in md_text.splitlines()]

    # Collect prefix (title, blanks, etc.) and table lines separately
    pre_lines: list[str] = []
    table_lines: list[str] = []
    post_lines: list[str] = []
    in_table = False
    table_done = False

    for line in raw_lines:
        stripped = line.lstrip()
        if not table_done and stripped.startswith("|"):
            in_table = True
            table_lines.append(line)
        elif in_table and not table_done:
            table_done = True
            post_lines.append(line)
        elif table_done:
            post_lines.append(line)
        else:
            pre_lines.append(line)

    if not table_lines:
        return md_text  # Nothing to reformat

    # Parse rows into (kind, [cells])
    # kind: "header" | "divider" | "data"
    parsed: list[tuple[str, list[str]]] = []
    header_seen = False

    for line in table_lines:
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        # Divider row: all non-empty cells match :?-+:?
        if all(re.match(r"^:?-+:?$", c) for c in cols if c):
            parsed.append(("divider", cols))
            header_seen = True
        elif not header_seen:
            parsed.append(("header", [_strip_md(c) for c in cols]))
        else:
            parsed.append(("data", [_strip_md(c) for c in cols]))

    if not parsed:
        return md_text

    # Normalise column count
    n_cols = max(len(cells) for _, cells in parsed)
    parsed = [(kind, cells + [""] * (n_cols - len(cells))) for kind, cells in parsed]

    # Compute per-column widths from header + data rows only
    col_widths = [1] * n_cols
    for kind, cells in parsed:
        if kind == "divider":
            continue
        for ci, cell in enumerate(cells):
            col_widths[ci] = max(col_widths[ci], len(cell))

    # Render aligned rows
    out_lines: list[str] = []
    for kind, cells in parsed:
        if kind == "divider":
            parts = [" " + "-" * col_widths[ci] + " " for ci in range(n_cols)]
        else:
            parts = [f" {cells[ci]:<{col_widths[ci]}} " for ci in range(n_cols)]
        out_lines.append("|" + "|".join(parts) + "|")

    sections = pre_lines + out_lines + post_lines
    return "\n".join(sections) + "\n"


def md_table_to_csv(md_text: str) -> str:
    """Convert a pipe-delimited Markdown table to a properly-quoted CSV string.

    Strips Markdown markup (bold, italic, links) and expands <br> to ' / '
    inline. Uses Python's csv module for RFC-4180 compliant quoting so cells
    containing commas, quotes, or newlines are handled correctly.
    Skips the --- divider row. Returns the CSV as a string (UTF-8 safe).
    """
    raw_lines = [line.rstrip() for line in md_text.splitlines()]

    rows: list[list[str]] = []

    for line in raw_lines:
        if not line.lstrip().startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        # Skip divider rows (--- / :--- / :---:)
        if all(re.match(r"^:?-+:?$", c) for c in cols if c):
            continue
        rows.append([_strip_md(c) for c in cols])

    if not rows:
        return ""

    # Normalise column count
    n_cols = max(len(r) for r in rows)
    rows = [r + [""] * (n_cols - len(r)) for r in rows]

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(rows)
    return buf.getvalue()
