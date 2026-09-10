"""
Antigravity Telegram Formatting & Text Engine v6.2
Provides Hermes-grade Telegram Markdown/HTML formatting:
- Converts markdown headers (###) to clean bold/emoji titles
- Removes raw horizontal rules (---)
- Converts GitHub callouts (> [!NOTE]) into clean quote cards
- Converts tables to mobile-friendly cards
- Ensures code blocks are preserved 100% intact
- Robust fallbacks (Markdown -> Safe HTML -> Clean Plain Text)
"""

import re
import html
import unicodedata
from typing import List, Tuple

# GFM Pipe Table Matcher
_TABLE_BLOCK_RE = re.compile(
    r'(?:^\|[^\n]+\|\r?\n'
    r'^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*\r?\n'
    r'(?:^[^\n]+\|\r?\n?)+)',
    re.MULTILINE
)

_CALLOUT_ICONS = {
    "NOTE": "💡",
    "TIP": "✨",
    "IMPORTANT": "🚨",
    "WARNING": "⚠️",
    "CAUTION": "🛑",
    "INFO": "ℹ️",
    "TODO": "📝",
    "SUCCESS": "✅",
    "FAILURE": "❌"
}


def _protect_code_blocks(text: str) -> Tuple[str, List[str]]:
    """Extracts and protects code blocks from regex modifications."""
    code_blocks = []

    def _repl(match):
        code_blocks.append(match.group(0))
        return f"___CODE_BLOCK_SLOT_{len(code_blocks)-1}___"

    protected = re.sub(r'```[\s\S]*?```', _repl, text)
    return protected, code_blocks


def _restore_code_blocks(text: str, code_blocks: List[str]) -> str:
    """Restores protected code blocks."""
    for idx, block in enumerate(code_blocks):
        text = text.replace(f"___CODE_BLOCK_SLOT_{idx}___", block)
    return text


def convert_tables_to_cards(text: str) -> str:
    """Converts raw markdown pipe tables into mobile-friendly bullet cards for Telegram."""
    def _table_replacer(match):
        table_str = match.group(0).strip()
        lines = [line.strip() for line in table_str.split("\n") if line.strip()]
        if len(lines) < 2:
            return table_str

        headers = [c.strip() for c in lines[0].strip("|").split("|")]
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


def sanitize_telegram_markdown(text: str) -> str:
    """
    Sanitizes GitHub Flavored Markdown into clean Telegram-compatible Markdown.
    Removes raw '###', '---', and transforms callouts and tables.
    """
    if not text:
        return ""

    # 1. Close unclosed code fences & convert tables
    text = ensure_closed_code_blocks(text)
    text = convert_tables_to_cards(text)

    # 2. Protect code blocks so their contents remain untouched
    protected, code_blocks = _protect_code_blocks(text)

    lines = protected.split("\n")
    processed_lines = []

    for line in lines:
        stripped = line.strip()

        # Check for Horizontal Rules (---, ***, ___)
        if re.match(r'^(?:-{3,}|\*{3,}|_{3,})$', stripped):
            # Replace horizontal rule with empty line (clean separation)
            processed_lines.append("")
            continue

        # Check for GitHub Callouts (> [!NOTE], etc.)
        callout_match = re.match(r'^>\s*\[!([A-Za-z]+)\]\s*(.*)$', stripped, re.IGNORECASE)
        if callout_match:
            ctype = callout_match.group(1).upper()
            crest = callout_match.group(2).strip()
            icon = _CALLOUT_ICONS.get(ctype, "📌")
            prefix = f"{icon} **{ctype.title()}:**"
            if crest:
                processed_lines.append(f"{prefix} {crest}")
            else:
                processed_lines.append(prefix)
            continue

        # Check for Blockquotes (> text)
        if stripped.startswith("> "):
            quote_text = stripped[2:].strip()
            processed_lines.append(f"▎ _{quote_text}_")
            continue

        # Check for Markdown Headers (#, ##, ###, ####)
        header_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            clean_title = re.sub(r'^\*+|\*+$', '', title).strip()
            if level == 1:
                processed_lines.append(f"\n📌 **{clean_title.upper()}**")
            elif level == 2:
                processed_lines.append(f"\n🔹 **{clean_title}**")
            else:
                processed_lines.append(f"\n• **{clean_title}**")
            continue

        processed_lines.append(line)

    result = "\n".join(processed_lines)

    # 3. Collapse multiple consecutive empty lines (max 2)
    result = re.sub(r'\n{3,}', '\n\n', result)

    # 4. Restore code blocks
    result = _restore_code_blocks(result, code_blocks)

    return result.strip()


def format_telegram_html(text: str) -> str:
    """
    Converts standard markdown to clean, safe Telegram HTML.
    Supports <b>, <i>, <code>, <pre>, <blockquote>.
    """
    if not text:
        return ""

    # Sanitize markdown structure first
    sanitized = sanitize_telegram_markdown(text)

    # Protect code blocks
    code_blocks = []
    def _save_block(m):
        code_blocks.append(m.group(0))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    protected = re.sub(r'```[\s\S]*?```', _save_block, sanitized)

    # Escape HTML entities in text
    escaped = html.escape(protected)

    # Bold: **text** or __text__ -> <b>text</b>
    escaped = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', escaped)

    # Italic: *text* or _text_ -> <i>text</i>
    escaped = re.sub(r'(?<!\w)\*([^\*]+)\*(?!\w)', r'<i>\1</i>', escaped)
    escaped = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<i>\1</i>', escaped)

    # Inline code: `code` -> <code>code</code>
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)

    # Quotes: ▎ _text_ -> <blockquote>text</blockquote>
    escaped = re.sub(r'▎\s*<i>(.*?)</i>', r'<blockquote>\1</blockquote>', escaped)

    # Restore code blocks with clean HTML <pre><code>
    for i, block in enumerate(code_blocks):
        inner_lines = block.split("\n")
        lang = inner_lines[0].replace("```", "").strip()
        code_content = "\n".join(inner_lines[1:-1]) if len(inner_lines) > 2 else inner_lines[0].replace("```", "")
        escaped_code = html.escape(code_content)
        if lang:
            replacement = f'<pre><code class="language-{lang}">{escaped_code}</code></pre>'
        else:
            replacement = f'<pre><code>{escaped_code}</code></pre>'
        escaped = escaped.replace(f"__CODE_BLOCK_{i}__", replacement)

    return escaped.strip()


def strip_markdown(text: str) -> str:
    """Strips all markdown formatting syntax for foolproof plain text fallback."""
    if not text:
        return ""

    cleaned = sanitize_telegram_markdown(text)
    cleaned = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', ''), cleaned)
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
    cleaned = re.sub(r'\\([_*\[\]()~`>#\+\-=|{}.!\\])', r'\1', cleaned)
    return cleaned.strip()


# ── TTS Phonetic & Speech Sanitization Engine ───────────────────────────────

_EMOJI_PATTERN = re.compile(
    r'[\U00010000-\U0010ffff]'
    r'|[\u2600-\u27bf]'
    r'|[\u2300-\u23ff]'
    r'|[\u2b50-\u2b55]'
    r'|[\u200d\ufe0e\ufe0f]'
    r'|[📌🔹•💡✨🚨⚠️🛑ℹ️📝✅❌💬⚡🚀🔍⚙️⌛🖼️📎🤔👍]'
)


def _speech_url_replacer(match: re.Match) -> str:
    """Replaces raw URLs with natural speech-friendly descriptions."""
    domain = match.group(1).lower() if match.group(1) else ""
    if "github.com" in domain:
        return " link do GitHub disponível no chat "
    elif "youtube.com" in domain or "youtu.be" in domain:
        return " link do YouTube disponível no chat "
    elif "instagram.com" in domain:
        return " link do Instagram disponível no chat "
    elif "akitaonrails.com" in domain:
        return " link do artigo do Akita no chat "
    elif domain:
        return f" link do site {domain} disponível no chat "
    return " link compartilhado no chat "


def prepare_text_for_speech(text: str, max_chars: int = 6000) -> str:
    """
    Transforms rich markdown agent outputs into clean, natural Portuguese speech for Edge Neural TTS:
    - Replaces huge code blocks with natural contextual announcements
    - Converts raw URLs to speech-friendly verbal references
    - Strips 100% of emojis, symbols, dingbats, and variation selectors (zero emoji reading)
    - Removes raw dividers (---), markdown tags (**, ##, ```), and bullet symbols
    - Expands text limit up to 6,000 characters (~5 min of audio)
    """
    if not text:
        return ""

    # 1. Ensure tables are cards
    text = convert_tables_to_cards(text)

    # 2. Replace code blocks with clean audio descriptions
    def _code_replacer(m):
        code_str = m.group(0)
        lines = [l.strip() for l in code_str.split("\n") if l.strip()]
        lang = ""
        if len(lines) > 0 and lines[0].startswith("```"):
            lang = lines[0].replace("```", "").strip()
        lang_desc = f"em {lang}" if lang else ""
        return f" . Bloco de código {lang_desc} detalhado no chat. "

    text = re.sub(r'```[\s\S]*?```', _code_replacer, text)

    # 3. Replace raw URLs
    text = re.sub(r'https?://(?:www\.)?([a-zA-Z0-9.-]+)(?:/[^\s]*)?', _speech_url_replacer, text)

    # 4. Remove horizontal rules (---, ***, ___, ===)
    text = re.sub(r'(?m)^(?:-{3,}|\*{3,}|_{3,}|={3,})\s*$', '', text)

    # 5. Remove Markdown syntax
    text = re.sub(r'^(?:#{1,6})\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    text = re.sub(r'^>\s*(?:\[![A-Za-z]+\])?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[•\-\*]\s+', '', text, flags=re.MULTILINE)

    # 6. Ultra-Comprehensive Unicode Emoji, Symbol & Pictograph Filtering
    clean_chars = []
    for char in text:
        code = ord(char)
        cat = unicodedata.category(char)

        # Variation Selectors (U+FE00 - U+FE0F), Combining Marks used in emoji sequences (U+20D0 - U+20FF)
        if 0xFE00 <= code <= 0xFE0F or 0x20D0 <= code <= 0x20FF:
            continue

        # Zero Width Joiner / Non-Joiner / Bidi controls
        if code in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF):
            continue

        # Unicode Categories:
        # So = Symbol Other (majority of emojis, pictographs, flags, badges)
        # Sk = Symbol Modifier (skin tone modifiers, tone marks)
        # Co = Private Use
        # Cn = Unassigned
        if cat in ('So', 'Sk', 'Co', 'Cn'):
            continue

        # Specific symbol blocks that might have Sm/Po/Ll categories but are used as icons:
        # Dingbats, Miscellaneous Symbols, Arrows, Box Drawing, Geometric Shapes, SMP symbols
        if (0x2190 <= code <= 0x21FF or  # Arrows (➔, ➜, ⬅, ⬆, ⬇)
            0x2300 <= code <= 0x23FF or  # Misc Technical (⏰, ⏱, ⌛, ⌨)
            0x2460 <= code <= 0x24FF or  # Enclosed Alphanumerics
            0x2500 <= code <= 0x257F or  # Box Drawing
            0x2580 <= code <= 0x259F or  # Block Elements
            0x25A0 <= code <= 0x25FF or  # Geometric Shapes (■, ◆, 🟢, 🔴)
            0x2600 <= code <= 0x27BF or  # Misc Symbols and Dingbats (⚠️, ⚡, ☕, ✨, ❌, ✅)
            0x2900 <= code <= 0x297F or  # Supplemental Arrows
            0x2B00 <= code <= 0x2BFF or  # Misc Symbols and Arrows (⭐, ⬛, ⬜)
            0x3200 <= code <= 0x32FF or  # Enclosed CJK
            0x1F000 <= code <= 0x1FFFF): # All SMP Symbols (Emoticons, Transport, Alchemical, etc.)
            continue

        # Specific known icon characters like ℹ (U+2139), ™, ©, ®
        if code in (0x2139, 0x2122, 0x00A9, 0x00AE):
            continue

        # Decorative bullet characters
        if char in '•·‣⁃◦※★☆✓✔✕✖✗✘☛☞☝☟☜☚':
            continue

        clean_chars.append(char)

    text = "".join(clean_chars)

    # 7. Clean up stray punctuation and whitespace
    text = re.sub(r'[\\|~^<>]', ' ', text)
    text = re.sub(r'\s*([.,!?;:])\s*', r'\1 ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 8. Limit to max_chars with graceful sentence boundary truncation
    if len(text) > max_chars:
        truncated = text[:max_chars]
        last_period = max(truncated.rfind('. '), truncated.rfind('! '), truncated.rfind('? '))
        if last_period > max_chars * 0.75:
            text = truncated[:last_period + 1] + " Áudio completo resumido por limite de tempo. Confira todos os detalhes no texto do chat."
        else:
            text = truncated + "... Confira todos os detalhes no texto do chat."

    return text
