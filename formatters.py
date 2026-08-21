"""
Antigravity Telegram Formatting & Text Engine
Provides Hermes-grade Markdown/HTML formatting, table-to-card conversion, and robust fallback delivery.
"""

import re
import html
from typing import List, Tuple

# MarkdownV2 escape characters (outside code blocks)
_MDV2_ESCAPE_CHARS = r'_*[]()~`>#+-=|{}.!'
_MDV2_ESCAPE_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')

# GFM Pipe Table Matcher
_TABLE_BLOCK_RE = re.compile(
    r'(?:^\|[^\n]+\|\r?\n'
    r'^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*\r?\n'
    r'(?:^[^\n]+\|\r?\n?)+)',
    re.MULTILINE
)


def convert_tables_to_cards(text: str) -> str:
    """Converts raw markdown pipe tables into mobile-friendly bullet cards for Telegram."""
    def _table_replacer(match):
        table_str = match.group(0).strip()
        lines = [line.strip() for line in table_str.split("\n") if line.strip()]
        if len(lines) < 2:
            return table_str

        # Parse header
        headers = [c.strip() for c in lines[0].strip("|").split("|")]
        # Skip separator line (line 1)
        data_rows = lines[2:]

        cards = []
        for row in data_rows:
            cols = [c.strip() for c in row.strip("|").split("|")]
            row_items = []
            for i, val in enumerate(cols):
                if not val:
                    continue
                header_name = headers[i] if i < len(headers) else f"Campo {i+1}"
                row_items.append(f"• **{header_name}:** {val}")
            if row_items:
                cards.append("\n".join(row_items))

        return "\n\n".join(cards) if cards else table_str

    try:
        return _TABLE_BLOCK_RE.sub(_table_replacer, text)
    except Exception:
        return text


def ensure_closed_code_blocks(text: str) -> str:
    """Detects and closes unclosed triple-backtick code fences to prevent Telegram entity parse errors."""
    count = text.count("```")
    if count % 2 != 0:
        return text + "\n```"
    return text


def strip_markdown(text: str) -> str:
    """Strips all markdown formatting syntax for foolproof plain text fallback."""
    # Remove code blocks
    cleaned = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', ''), text)
    # Remove inline code
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Remove bold/italic
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
    # Remove escapes
    cleaned = re.sub(r'\\([_*\[\]()~`>#\+\-=|{}.!\\])', r'\1', cleaned)
    return cleaned.strip()


def format_telegram_html(text: str) -> str:
    """Converts standard markdown to clean, safe Telegram HTML."""
    # Pre-process tables to cards
    processed = convert_tables_to_cards(text)
    processed = ensure_closed_code_blocks(processed)

    # Protect code blocks
    code_blocks = []
    def _save_block(m):
        code_blocks.append(m.group(0))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    protected = re.sub(r'```[\s\S]*?```', _save_block, processed)

    # Escape HTML special chars in prose
    escaped = html.escape(protected)

    # Format bold, italic, inline code
    escaped = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', escaped)
    escaped = re.sub(r'(?<!\w)\*([^\*]+)\*(?!\w)', r'<i>\1</i>', escaped)
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)

    # Restore code blocks with clean HTML <pre><code>
    for i, block in enumerate(code_blocks):
        # Extract code content
        inner_lines = block.split("\n")
        lang = inner_lines[0].replace("```", "").strip()
        code_content = "\n".join(inner_lines[1:-1]) if len(inner_lines) > 2 else inner_lines[0].replace("```", "")
        escaped_code = html.escape(code_content)
        if lang:
            replacement = f'<pre><code class="language-{lang}">{escaped_code}</code></pre>'
        else:
            replacement = f'<pre><code>{escaped_code}</code></pre>'
        escaped = escaped.replace(f"__CODE_BLOCK_{i}__", replacement)

    return escaped
